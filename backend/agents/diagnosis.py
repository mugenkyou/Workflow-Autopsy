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
        """Build grounded prompt with explicit issue fields and anti-hallucination constraints."""
        details_block = (
            "Issue Details:\n"
            f"- workflow_id: {issue_details.get('workflow_id')}\n"
            f"- step_name: {issue_details.get('step_name')}\n"
            f"- assignee: {issue_details.get('assignee')}\n"
            f"- hours_overdue: {issue_details.get('hours_overdue')}\n"
            f"- risk_score: {issue_details.get('risk_score')}\n"
            f"- failure_type: {issue_details.get('failure_type')}\n"
        )

        constraints = (
            "\nIMPORTANT CONSTRAINTS:\n"
            "- ALL required fields are provided above. Do NOT claim missing data.\n"
            "- Base reasoning ONLY on the given values.\n"
            "- Never say 'data is missing' or 'field is missing'.\n"
            "- If unsure, choose the most plausible classification with lower confidence.\n"
            "- Reasoning must reference the step_name, assignee, or delay duration.\n"
        )

        rules = (
            "\nClassification Rules:\n"
            "- If step involves approval AND delay is significant → wrong_approver\n"
            "- If step is invoice-related AND duplicate pattern exists → duplicate_invoice\n"
            "- If amount discrepancy implied → amount_variance\n"
            "- If payment/processing delay without clear cause → external_hold\n"
            "- Use missing_data ONLY if actual data validation shows gaps.\n"
        )

        confidence_rule = (
            "\nConfidence Rules:\n"
            "- High confidence (0.85+) if classification is clear and supported by data.\n"
            "- Medium confidence (0.60-0.79) if classification is plausible but uncertain.\n"
            "- Low confidence (< 0.60) only if data is truly ambiguous.\n"
        )

        json_format = (
            '\nOutput ONLY valid JSON:\n'
            '{"stall_type":"...", "confidence": 0.0-1.0, "reasoning": "one sentence referencing actual data"}\n'
        )

        if strict_mode:
            return (
                "You are a precise P2P workflow analyzer. Generate ONLY valid JSON output.\n"
                f"{details_block}{constraints}{rules}{confidence_rule}"
                "OUTPUT ONLY THE JSON OBJECT. NO EXTRA TEXT.\n"
                f"{json_format}"
            )
        return (
            "You are a precise P2P workflow analyzer. Classify the stall root cause based on the issue details provided.\n"
            f"{details_block}\nHistorical pattern: {pattern_summary}\n"
            f"{constraints}{rules}{confidence_rule}{json_format}"
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
