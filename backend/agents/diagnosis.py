from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any

import requests
from pydantic import BaseModel, ValidationError

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import get_connection


ALLOWED_TYPES = {
    "missing_data",
    "wrong_approver",
    "duplicate_invoice",
    "amount_variance",
    "external_hold",
}


class DiagnosisResult(BaseModel):
    stall_type: str
    confidence: float
    reasoning: str


class DiagnosisAgent:
    """Classify root cause for a monitored issue using local Ollama."""

    def __init__(self, endpoint: str = "http://localhost:11434/api/generate", model: str = "mistral") -> None:
        self.endpoint = endpoint
        self.model = model

    @staticmethod
    def _extract_json_blob(text: str) -> str | None:
        text = text.strip()
        if text.startswith("{") and text.endswith("}"):
            return text
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        return match.group(0) if match else None

    def _load_pattern_summary(self, approver_id: str) -> str:
        conn = get_connection()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT condition, stall_rate, sample_count, last_seen "
            "FROM stall_patterns WHERE approver_id = ? "
            "ORDER BY last_seen DESC LIMIT 1",
            (approver_id,),
        ).fetchone()
        conn.close()

        if not row:
            return "none"

        return (
            f"condition={row['condition']}, stall_rate={row['stall_rate']}, "
            f"sample_count={row['sample_count']}, last_seen={row['last_seen']}"
        )

    def _build_prompt(self, issue_details: dict[str, Any], pattern_summary: str, strict_mode: bool = False) -> str:
        """Build grounded prompt with suggested classification and controlled override capability."""
        step_name = issue_details.get('step_name', '')
        hours_overdue = float(issue_details.get('hours_overdue', 0))
        assignee = issue_details.get('assignee', '')

        details_block = (
            "Issue Details:\n"
            f"- workflow_id: {issue_details.get('workflow_id')}\n"
            f"- step_name: {step_name}\n"
            f"- assignee: {assignee}\n"
            f"- hours_overdue: {hours_overdue}\n"
            f"- risk_score: {issue_details.get('risk_score')}\n"
            f"- failure_type: {issue_details.get('failure_type')}\n"
        )

        # Determine classification based on explicit rules
        if 'Payment' in step_name and 'Processing' in step_name:
            suggested_type = "external_hold"
            suggested_confidence = "0.70-0.75"
            reason_fragment = "payment delays are external (vendor/banking)"
        elif 'Approval' in step_name and hours_overdue > 20:
            suggested_type = "wrong_approver"
            suggested_confidence = "0.80-0.85"
            reason_fragment = "delay >20h indicates wrong approver"
        elif 'Approval' in step_name and 6 <= hours_overdue <= 20:
            suggested_type = "external_hold"
            suggested_confidence = "0.65-0.75"
            reason_fragment = "moderate 6-20h delay suggests external block"
        elif 'Approval' in step_name:  # <6 hours
            suggested_type = "external_hold"
            suggested_confidence = "0.55-0.65"
            reason_fragment = "short <6h delay, likely vendor/workflow"
        elif 'Invoice' in step_name:
            suggested_type = "duplicate_invoice"
            suggested_confidence = "0.70-0.80"
            reason_fragment = "invoice processing issue"
        else:
            suggested_type = "external_hold"
            suggested_confidence = "0.65-0.75"
            reason_fragment = "default external cause"

        rules = (
            "\nCLASSIFICATION GUIDANCE:\n"
            f"Suggested classification: {suggested_type}\n"
            f"Expected confidence range: {suggested_confidence}\n"
            "\nYou may override this suggestion ONLY if strong evidence contradicts it.\n"
            "\nOverride Rules:\n"
            "- Override only if reasoning strongly supports a different cause\n"
            "- If overriding, clearly explain why the suggested classification is incorrect\n"
            "- Overrides should be rare (not more than 1-2 in a batch)\n"
            "- If you override, reduce confidence below 0.75\n"
            "\nAmbiguity Handling:\n"
            "- If multiple explanations are plausible, pick the most likely\n"
            "- BUT reduce confidence to 0.60-0.70 to reflect uncertainty\n"
            "- Include uncertainty language in reasoning\n"
            "\nAllowed types: wrong_approver, external_hold, duplicate_invoice, amount_variance, missing_data\n"
        )

        reasoning_format = (
            "\nReasoning Requirements:\n"
            "- Exactly 1 sentence\n"
            f"- Reference '{assignee}' (assignee name) and '{step_name}' (step)\n"
            f"- Reference '{hours_overdue}' hours overdue\n"
            "- Explain causal logic (WHY this classification)\n"
            "\nIf overriding suggested classification:\n"
            "- Include a phrase explaining disagreement\n"
            f"- Example: 'Although delay suggests {suggested_type}, evidence indicates external dependency instead.'\n"
            "\nDo NOT use identical reasoning patterns in each response.\n"
        )

        json_format = (
            '\nOutput format:\n'
            '{"stall_type":"example", "confidence": 0.75, "reasoning": "your analytical sentence here"}\n'
            'Must be valid JSON with confidence between 0.0 and 1.0.\n'
        )

        if strict_mode:
            return (
                "You are a contextual P2P workflow analyst. Output valid JSON only.\n"
                f"{details_block}{rules}{reasoning_format}{json_format}"
                "Analyze carefully. Output ONLY the json object, no extra text.\n"
            )
        return (
            "Analyze this P2P workflow issue and provide reasoned classification.\n"
            f"{details_block}\nHistorical pattern: {pattern_summary}\n"
            f"{rules}{reasoning_format}{json_format}"
        )

    def _fallback(self) -> dict[str, Any]:
        return {
            "stall_type": "external_hold",
            "confidence": 0.5,
            "reasoning": "Default fallback due to classification failure",
        }

    def run(self, issue: dict[str, Any]) -> dict[str, Any]:
        pattern_summary = self._load_pattern_summary(str(issue.get("assignee", "")))

        max_retries = 2
        for attempt in range(max_retries + 1):
            strict_mode = attempt > 0
            prompt = self._build_prompt(issue, pattern_summary, strict_mode=strict_mode)

            try:
                resp = requests.post(
                    self.endpoint,
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                raw = str(data.get("response", "")).strip()
                
                # DEBUG: Print raw LLM output before parsing
                print(f"RAW LLM OUTPUT: {raw}", file=__import__('sys').stderr)
                
                blob = self._extract_json_blob(raw)
                if not blob:
                    print(f"DEBUG: No JSON blob found in {raw[:60]}...", file=__import__('sys').stderr)
                    continue

                parsed = json.loads(blob)
                validated = DiagnosisResult.model_validate(parsed)

                if validated.stall_type not in ALLOWED_TYPES:
                    print(f"DEBUG: Invalid stall_type={validated.stall_type}", file=__import__('sys').stderr)
                    continue
                if not (0.0 <= float(validated.confidence) <= 1.0):
                    print(f"DEBUG: Invalid confidence={validated.confidence}", file=__import__('sys').stderr)
                    continue

                print(f"DEBUG: Attempt {attempt} succeeded", file=__import__('sys').stderr)
                return validated.model_dump()
            except (requests.RequestException, ValueError, ValidationError, json.JSONDecodeError) as e:
                print(f"DEBUG: Attempt {attempt} failed: {type(e).__name__}", file=__import__('sys').stderr)
                continue

        print("DEBUG: All retries exhausted, using fallback", file=__import__('sys').stderr)
        return self._fallback()
