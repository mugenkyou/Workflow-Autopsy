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

    def _build_prompt(self, issue_summary: str, pattern_summary: str, strict_prefix: str = "") -> str:
        base = (
            "You are a P2P workflow diagnosis system. Analyze the issue.\n"
            f"Issue: {issue_summary}\n"
            f"Historical pattern: {pattern_summary}\n\n"
            "Classify into EXACTLY one of:\n"
            "missing_data, wrong_approver, duplicate_invoice, amount_variance, external_hold\n\n"
            "Return ONLY valid JSON:\n"
            '{"stall_type": "...", "confidence": 0.0-1.0, "reasoning": "one short sentence"}'
        )
        if strict_prefix:
            return f"{strict_prefix}\n{base}"
        return base

    def _fallback(self) -> dict[str, Any]:
        return {
            "stall_type": "external_hold",
            "confidence": 0.5,
            "reasoning": "Default fallback due to classification failure",
        }

    def run(self, issue: dict[str, Any]) -> dict[str, Any]:
        issue_summary = (
            f"workflow_id={issue.get('workflow_id')}, step_id={issue.get('step_id')}, "
            f"step_name={issue.get('step_name')}, assignee={issue.get('assignee')}, "
            f"hours_overdue={issue.get('hours_overdue')}, risk_score={issue.get('risk_score')}, "
            f"failure_type={issue.get('failure_type')}"
        )
        pattern_summary = self._load_pattern_summary(str(issue.get("assignee", "")))

        max_retries = 2
        for attempt in range(max_retries + 1):
            strict_prefix = "OUTPUT ONLY VALID JSON. NO EXTRA TEXT." if attempt > 0 else ""
            prompt = self._build_prompt(issue_summary, pattern_summary, strict_prefix)

            try:
                resp = requests.post(
                    self.endpoint,
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=5,
                )
                resp.raise_for_status()
                data = resp.json()
                raw = str(data.get("response", "")).strip()
                blob = self._extract_json_blob(raw)
                if not blob:
                    continue

                parsed = json.loads(blob)
                validated = DiagnosisResult.model_validate(parsed)

                if validated.stall_type not in ALLOWED_TYPES:
                    continue
                if not (0.0 <= float(validated.confidence) <= 1.0):
                    continue

                return validated.model_dump()
            except (requests.RequestException, ValueError, ValidationError, json.JSONDecodeError):
                continue

        return self._fallback()
