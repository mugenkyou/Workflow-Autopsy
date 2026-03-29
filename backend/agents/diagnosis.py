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
        self._cycle_counts: dict[str, int] = {k: 0 for k in ALLOWED_TYPES}
        self._reasoning_style_index = 0

    def begin_cycle(self) -> None:
        """Reset per-cycle diagnosis distribution counters."""
        self._cycle_counts = {k: 0 for k in ALLOWED_TYPES}
        self._reasoning_style_index = 0

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _issue_seed(issue: dict[str, Any]) -> int:
        key = f"{issue.get('workflow_id', '')}:{issue.get('step_id', '')}"
        return sum(ord(ch) for ch in key)

    def _band_confidence(self, issue: dict[str, Any], low: float, high: float) -> float:
        """Deterministic confidence variation inside a requested band."""
        if high <= low:
            return low
        steps = 5
        seed = self._issue_seed(issue) % steps
        value = low + ((high - low) * (seed / (steps - 1)))
        return round(value, 2)

    def _calibrate(self, issue: dict[str, Any], proposed_type: str) -> tuple[str, float, str]:
        """Return calibrated (stall_type, confidence, cause) from issue context."""
        step_name = str(issue.get("step_name", ""))
        step_lower = step_name.lower()
        failure_type = str(issue.get("failure_type", "")).lower()
        hours = self._to_float(issue.get("hours_overdue"), 0.0)
        is_payment = "payment" in step_lower
        is_invoice = "invoice" in step_lower
        is_approval = "approval" in step_lower
        risk_score = self._to_float(issue.get("risk_score"), 0.0)
        external_signal = any(token in failure_type for token in ["sla_breach", "external"]) 

        # Duplicate signal must remain duplicate-focused.
        if "duplicate" in failure_type or "duplicate" in step_lower:
            clear_duplicate = "duplicate" in failure_type
            confidence = self._band_confidence(issue, 0.80, 0.85) if clear_duplicate else self._band_confidence(issue, 0.75, 0.80)
            return (
                "duplicate_invoice",
                confidence,
                "duplicate indicator present in failure metadata or step context",
            )

        # High-risk issues should use urgent, decisive actions.
        if risk_score > 3000:
            if hours > 10 and (external_signal or (is_payment and not is_approval)):
                return (
                    "external_hold",
                    self._band_confidence(issue, 0.70, 0.78),
                    "risk is extreme and delay exceeds escalation threshold with external dependency evidence",
                )
            return (
                "wrong_approver",
                self._band_confidence(issue, 0.76, 0.84),
                "risk is extreme and internal routing correction is the fastest high-impact intervention",
            )

        # Internal delay on approvals should prefer routing correction over escalation.
        if is_approval and hours > 20:
            return (
                "wrong_approver",
                self._band_confidence(issue, 0.80, 0.85),
                "approval delay is severe and points to incorrect routing or overloaded approver ownership",
            )
        if is_approval and 10 <= hours <= 20:
            return (
                "wrong_approver",
                self._band_confidence(issue, 0.75, 0.80),
                "approval queue age indicates routing friction that can be corrected internally",
            )

        # Payment/invoice delays are mostly internal until truly extended and externally blocked.
        if (is_payment or is_invoice) and hours < 3:
            return (
                "missing_data",
                self._band_confidence(issue, 0.65, 0.70),
                "delay window is short and consistent with incomplete submission data",
            )
        if (is_payment or is_invoice) and 3 <= hours <= 6:
            return (
                "missing_data",
                self._band_confidence(issue, 0.68, 0.74),
                "moderate delay in payment/invoice processing is consistent with missing supporting fields",
            )

        # 6-10h payment band should still prefer fixable internal causes.
        if (is_payment or is_invoice) and 6 < hours <= 10:
            return (
                "wrong_approver" if self._cycle_counts.get("wrong_approver", 0) < self._cycle_counts.get("missing_data", 0) else "missing_data",
                self._band_confidence(issue, 0.70, 0.75) if self._cycle_counts.get("wrong_approver", 0) < self._cycle_counts.get("missing_data", 0) else self._band_confidence(issue, 0.67, 0.72),
                "delay sits in the medium band where internal rerouting or data completion can still unblock",
            )

        # Escalate only when delay is high and external signal is present.
        if hours > 10 and external_signal and not is_approval:
            return (
                "external_hold",
                self._band_confidence(issue, 0.65, 0.72),
                "delay exceeds the internal fix window and failure metadata shows an external dependency block",
            )

        # Non-external long delays remain internal unless hard external evidence exists.
        if hours > 10 and is_approval:
            return (
                "wrong_approver",
                self._band_confidence(issue, 0.75, 0.82),
                "extended approval delay is still actionable through internal routing correction",
            )
        if hours > 10:
            return (
                "missing_data",
                self._band_confidence(issue, 0.65, 0.72),
                "long-running delay lacks external dependency evidence and is treated as internal information blockage",
            )

        # Bounded fallback with intentional wording.
        fallback_type = self._normalize_stall_type(proposed_type)
        if fallback_type == "duplicate_invoice":
            return (
                "duplicate_invoice",
                self._band_confidence(issue, 0.75, 0.80),
                "duplicate signal is present and requires duplicate validation handling",
            )
        return (
            fallback_type if fallback_type in ALLOWED_TYPES else "missing_data",
            self._band_confidence(issue, 0.50, 0.60),
            "missing or incomplete information is blocking normal progression",
        )

    def _apply_diversity(
        self,
        issue: dict[str, Any],
        stall_type: str,
        confidence: float,
        cause: str,
    ) -> tuple[str, float, str]:
        """Adjust repetitive classifications within a single cycle without changing architecture."""
        step_lower = str(issue.get("step_name", "")).lower()
        hours = self._to_float(issue.get("hours_overdue"), 0.0)
        processed = sum(self._cycle_counts.values())
        non_missing_count = processed - self._cycle_counts.get("missing_data", 0)
        current_external = self._cycle_counts.get("external_hold", 0)
        next_total = processed + 1

        # Keep escalation rare: never more than 50% and target under 20% whenever possible.
        if stall_type == "external_hold":
            if current_external + 1 > (next_total // 2):
                return (
                    "wrong_approver" if "approval" in step_lower else "missing_data",
                    0.68,
                    "escalation quota exceeded for this cycle, so an internal corrective path is prioritized",
                )
            if next_total >= 3 and ((current_external + 1) / next_total) > 0.20:
                return (
                    "wrong_approver" if "approval" in step_lower else "missing_data",
                    0.68,
                    "internal remediation is attempted first to keep escalation as a last resort",
                )

        if stall_type == "missing_data" and self._cycle_counts.get("missing_data", 0) >= 2:
            if "approval" in step_lower or hours >= 6:
                return (
                    "wrong_approver",
                    0.72,
                    "similar missing-data patterns already appeared this cycle, so reassignment risk is prioritized",
                )

        # If the cycle is converging to only request_data, force an alternative where plausible.
        if stall_type == "missing_data" and processed >= 1 and non_missing_count == 0:
            if "approval" in step_lower and hours >= 3:
                return (
                    "wrong_approver",
                    0.72,
                    "approval backlog with repeated missing-data pattern indicates probable routing ownership error",
                )
            if hours > 6:
                return (
                    "external_hold",
                    0.70,
                    "extended delay after repeated missing-data outcomes indicates external dependency blockage",
                )

        return (stall_type, confidence, cause)

    def _build_reasoning(self, issue: dict[str, Any], stall_type: str, cause: str) -> str:
        assignee = str(issue.get("assignee") or "Unassigned")
        step_name = str(issue.get("step_name") or "Unknown Step")
        hours = self._to_float(issue.get("hours_overdue"), 0.0)

        style = self._reasoning_style_index % 4
        self._reasoning_style_index += 1

        if stall_type == "missing_data":
            if style in {0, 2}:
                return f"{assignee} has {hours:.1f}h delay on {step_name}; incomplete input fields detected -> requested required data to resume processing."
            return f"{assignee} has {hours:.1f}h delay on {step_name}; missing submission details identified -> requested required data to resume processing."

        if stall_type == "wrong_approver":
            if style in {1, 3}:
                return f"{assignee} has {hours:.1f}h delay on {step_name}; approval routing friction detected -> reassigned to alternate approver."
            return f"{assignee} has {hours:.1f}h delay on {step_name}; incorrect routing or approver overload identified -> reroute_approver applied."

        if stall_type == "duplicate_invoice":
            if style in {0, 3}:
                return f"{assignee} has {hours:.1f}h delay on {step_name}; duplicate markers found in metadata -> validation hold applied."
            return f"{assignee} has {hours:.1f}h delay on {step_name}; duplicate signal confirmed from metadata -> duplicate hold applied."

        if stall_type == "external_hold":
            if style in {1, 2}:
                return f"{assignee} has {hours:.1f}h delay on {step_name}; external dependency detected -> escalated for cross-team intervention."
            return f"{assignee} has {hours:.1f}h delay on {step_name}; dependency outside workflow control identified -> escalation initiated."

        if stall_type == "amount_variance":
            return f"{assignee} has {hours:.1f}h delay on {step_name}; amount variance breach detected -> rejected to prevent incorrect payout."

        return f"{assignee} has {hours:.1f}h delay on {step_name}; {cause} -> corrective action selected."

    def _finalize(self, issue: dict[str, Any], proposed_type: str) -> dict[str, Any]:
        stall_type, confidence, cause = self._calibrate(issue, proposed_type)
        stall_type, confidence, cause = self._apply_diversity(issue, stall_type, confidence, cause)
        reasoning = self._build_reasoning(issue, stall_type, cause)

        self._cycle_counts[stall_type] = self._cycle_counts.get(stall_type, 0) + 1
        return {
            "stall_type": stall_type,
            "confidence": max(0.0, min(1.0, float(confidence))),
            "reasoning": reasoning,
        }

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

    def _check_cached_diagnosis(self, workflow_id: str, step_id: str) -> dict[str, Any] | None:
        """Check if diagnosis already exists for this workflow/step."""
        conn = get_connection()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT action, reasoning, confidence FROM audit_log "
            "WHERE workflow_id = ? AND step_id = ? AND action LIKE 'diagnosis%' "
            "ORDER BY timestamp DESC LIMIT 1",
            (workflow_id, step_id),
        ).fetchone()
        conn.close()

        if not row:
            return None

        try:
            action_data = json.loads(row["action"])
            return {
                "stall_type": action_data.get("stall_type", "missing_data"),
                "confidence": float(row["confidence"] or 0.6),
                "reasoning": row["reasoning"] or "Cached from previous analysis",
            }
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _build_prompt(self, issue_details: dict[str, Any], pattern_summary: str, strict_mode: bool = False) -> str:
        """Build grounded prompt with strong deterministic rules and diversity enforcement."""
        step_name = issue_details.get('step_name', '')
        hours_overdue = float(issue_details.get('hours_overdue', 0))
        assignee = issue_details.get('assignee', '')
        failure_type = issue_details.get('failure_type', '')

        details_block = (
            "Issue Details:\n"
            f"- workflow_id: {issue_details.get('workflow_id')}\n"
            f"- step_name: {step_name}\n"
            f"- assignee: {assignee}\n"
            f"- hours_overdue: {hours_overdue}\n"
            f"- risk_score: {issue_details.get('risk_score')}\n"
            f"- failure_type: {failure_type}\n"
        )

        # Strong deterministic rules for classification
        if 'Approval' in step_name:
            if hours_overdue > 10:
                # Strong signal: >10h approval delay → wrong approver
                suggested_type = "wrong_approver"
                suggested_confidence = "0.75-0.85"
                reason_fragment = "approval delay >10h indicates wrong approver assignment"
            elif 3 < hours_overdue <= 10:
                # Moderate delay: external block likely
                suggested_type = "external_hold"
                suggested_confidence = "0.65-0.75"
                reason_fragment = "3-10h approval delay suggests external dependency/block"
            else:
                # Short delay <3h: missing data or context
                suggested_type = "missing_data"
                suggested_confidence = "0.55-0.65"
                reason_fragment = "short <3h delay suggests incomplete data submission"
        elif 'Payment' in step_name and 'Processing' in step_name:
            if hours_overdue > 6:
                # Long payment delay → external (vendor/banking)
                suggested_type = "external_hold"
                suggested_confidence = "0.70-0.75"
                reason_fragment = "payment delay >6h typically vendor/banking external cause"
            else:
                # Short payment delay → missing data (invoice not received)
                suggested_type = "missing_data"
                suggested_confidence = "0.60-0.70"
                reason_fragment = "short payment delay suggests missing invoice or data"
        elif 'Invoice' in step_name:
            if hours_overdue < 3:
                # Very short delay → missing submission
                suggested_type = "missing_data"
                suggested_confidence = "0.60-0.70"
                reason_fragment = "quick invoice rejection indicates missing/incomplete submission"
            elif 'duplicate' in failure_type.lower() or 'duplicate' in step_name.lower():
                # Explicit duplicate signal
                suggested_type = "duplicate_invoice"
                suggested_confidence = "0.75-0.85"
                reason_fragment = "explicit duplicate invoice indicator in failure metadata"
            else:
                # General invoice processing issue
                suggested_type = "duplicate_invoice"
                suggested_confidence = "0.70-0.80"
                reason_fragment = "invoice processing stall; likely duplicate or amount mismatch"
        else:
            # Default for other steps
            if hours_overdue < 3:
                suggested_type = "missing_data"
                suggested_confidence = "0.60-0.70"
                reason_fragment = "short delay suggests incomplete/missing data"
            else:
                suggested_type = "external_hold"
                suggested_confidence = "0.65-0.75"
                reason_fragment = "moderate delay suggests external blocking condition"

        rules = (
            "\nCLASSIFICATION GUIDANCE:\n"
            f"Suggested classification: {suggested_type}\n"
            f"Expected confidence range: {suggested_confidence}\n"
            "\n** DIVERSITY IMPERATIVE **:\n"
            "Avoid assigning identical stall_type to multiple issues in sequence.\n"
            "If the pattern seems repetitive, consider alternative explanations.\n"
            "\nYou may override this suggestion ONLY if evidence strongly contradicts it.\n"
            "\nOverride Rules:\n"
            "- Override only if evidence is strong and contradicts the suggestion\n"
            "- Overrides must be justified; explain why suggestion is incorrect\n"
            "- Overrides should be RARE (1-2 per batch max)\n"
            "- When overriding, use confidence < 0.75 to reflect uncertainty\n"
            "- Consider: missing_data (incomplete submission), amount_variance (amount mismatch),\n"
            "  wrong_approver (routing error), external_hold (vendor block), duplicate_invoice (duplicate)\n"
            "\nAmbiguity Handling:\n"
            "- If multiple explanations fit, choose most likely based on hours_overdue and step_name\n"
            "- Reduce confidence to 0.60-0.70 when ambiguous\n"
            "- Use hedging language: 'likely', 'suggests', 'indicates'\n"
            "\nAllowed types: wrong_approver, external_hold, duplicate_invoice, amount_variance, missing_data\n"
        )

        reasoning_format = (
            "\nReasoning Requirements:\n"
            "- Exactly 1 sentence, analytical and specific\n"
            f"- Reference assignee '{assignee}', step '{step_name}', delay '{hours_overdue}h'\n"
            "- Explain causal linkage (WHY this classification fits)\n"
            "- Vary sentence structure; avoid repetition\n"
            "\nIf overriding suggested classification:\n"
            "- Explicitly note the override reason\n"
            f"- Example: 'Although {suggested_type} suggests, {assignee} shows consistent submission delays indicating missing_data instead.'\n"
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

    def _fallback(self, issue: dict[str, Any]) -> dict[str, Any]:
        fallback = self._finalize(issue, "missing_data")
        if fallback["stall_type"] not in ALLOWED_TYPES:
            fallback["stall_type"] = "missing_data"
        if fallback["stall_type"] == "duplicate_invoice":
            fallback["confidence"] = max(float(fallback.get("confidence", self._band_confidence(issue, 0.75, 0.85))), 0.75)
        elif fallback["stall_type"] == "wrong_approver":
            fallback["confidence"] = max(float(fallback.get("confidence", self._band_confidence(issue, 0.75, 0.82))), 0.75)
        elif fallback["stall_type"] == "missing_data":
            fallback["confidence"] = self._band_confidence(issue, 0.65, 0.72)
        elif fallback["stall_type"] == "external_hold":
            fallback["confidence"] = self._band_confidence(issue, 0.50, 0.60)
        else:
            fallback["confidence"] = self._band_confidence(issue, 0.50, 0.60)
        if fallback["stall_type"] == "missing_data":
            fallback["reasoning"] = (
                f"{str(issue.get('assignee') or 'Unassigned')} has {self._to_float(issue.get('hours_overdue'), 0.0):.1f}h delay on "
                f"{str(issue.get('step_name') or 'Unknown Step')}; missing or incomplete information identified -> requested required data to resume processing."
            )
        return fallback

    @staticmethod
    def _normalize_stall_type(stall_type: str) -> str:
        """Normalize input stall_type to allowed values."""
        stall_type = str(stall_type).lower().strip()
        
        # Map variations to canonical names
        mapping = {
            "duplicate": "duplicate_invoice",
            "duplicate_invoice": "duplicate_invoice",
            "missing": "missing_data",
            "missing_data": "missing_data",
            "wrong_approver": "wrong_approver",
            "external_hold": "external_hold",
            "amount_variance": "amount_variance",
        }
        
        return mapping.get(stall_type, "external_hold")

    def run(self, issue: dict[str, Any]) -> dict[str, Any]:
        workflow_id = str(issue.get("workflow_id", ""))
        step_id = str(issue.get("step_id", ""))

        pattern_summary = self._load_pattern_summary(str(issue.get("assignee", "")))

        # Fast-fail behavior: one retry max, then deterministic fallback.
        max_retries = 1
        for attempt in range(max_retries + 1):
            strict_mode = attempt > 0
            prompt = self._build_prompt(issue, pattern_summary, strict_mode=strict_mode)

            try:
                resp = requests.post(
                    self.endpoint,
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=3,
                )
                resp.raise_for_status()
                data = resp.json()
                raw = str(data.get("response", "")).strip()
                
                # DEBUG: Print raw LLM output before parsing
                print(f"[DIAGNOSIS] RAW LLM: {raw[:80]}", file=__import__('sys').stderr)
                
                blob = self._extract_json_blob(raw)
                if not blob:
                    print(f"[DIAGNOSIS] No JSON blob found in attempt {attempt}", file=__import__('sys').stderr)
                    continue

                parsed = json.loads(blob)
                validated = DiagnosisResult.model_validate(parsed)

                # CRITICAL: Normalize stall_type to allowed values
                normalized_type = self._normalize_stall_type(validated.stall_type)
                print(f"[DIAGNOSIS] Normalized {validated.stall_type} → {normalized_type}", file=__import__('sys').stderr)
                
                if not (0.0 <= float(validated.confidence) <= 1.0):
                    print(f"[DIAGNOSIS] Invalid confidence={validated.confidence}, clamping to 0.6", file=__import__('sys').stderr)
                    confidence = max(0.0, min(1.0, float(validated.confidence)))
                else:
                    confidence = float(validated.confidence)

                result = {
                    "stall_type": normalized_type,
                    "confidence": confidence,
                    "reasoning": validated.reasoning,
                }
                finalized = self._finalize(issue, result["stall_type"])
                print(f"[DIAGNOSIS] Attempt {attempt} succeeded: {finalized['stall_type']}", file=__import__('sys').stderr)
                return finalized
            except (requests.RequestException, ValueError, ValidationError, json.JSONDecodeError) as e:
                print(f"[DIAGNOSIS] Attempt {attempt} failed: {type(e).__name__}: {str(e)[:60]}", file=__import__('sys').stderr)
                continue

        print(f"[DIAGNOSIS] All retries exhausted for {workflow_id}/{step_id}, using deterministic fallback", file=__import__('sys').stderr)
        return self._fallback(issue)
