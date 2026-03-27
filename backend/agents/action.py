from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
import re
import sys
from typing import Any

import requests

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import get_connection


class ActionAgent:
    """Execute deterministic corrective actions based on diagnosis output."""

    BACKUP_APPROVERS = [
        "Priya Mehta",
        "Rohit Sharma",
        "Ananya Iyer",
    ]

    def __init__(self, endpoint: str = "http://localhost:11434/api/generate", model: str = "mistral") -> None:
        self.endpoint = endpoint
        self.model = model

    def _select_backup_approver(self, current_assignee: str, workflow_id: str, step_id: str) -> str:
        """Pick a deterministic backup approver that differs from current assignee."""
        seed = f"{workflow_id}:{step_id}"
        idx = sum(ord(ch) for ch in seed) % len(self.BACKUP_APPROVERS)

        candidate = self.BACKUP_APPROVERS[idx]
        if candidate != current_assignee:
            return candidate

        # Deterministic fallback to next name if collision
        return self.BACKUP_APPROVERS[(idx + 1) % len(self.BACKUP_APPROVERS)]

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    def _generate_escalation_summary(self, issue: dict[str, Any], diagnosis: dict[str, Any]) -> str:
        """Generate exactly 3 sentences for escalation packet; fallback deterministically on failure."""
        prompt = (
            "Write exactly 3 short sentences for an escalation summary. "
            "Do not use bullets or numbering.\n"
            f"workflow_id={issue.get('workflow_id')}\n"
            f"step_name={issue.get('step_name')}\n"
            f"assignee={issue.get('assignee')}\n"
            f"hours_overdue={issue.get('hours_overdue')}\n"
            f"risk_score={issue.get('risk_score')}\n"
            f"stall_type={diagnosis.get('stall_type')}\n"
            f"reasoning={diagnosis.get('reasoning')}"
        )
        try:
            resp = requests.post(
                self.endpoint,
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=20,
            )
            resp.raise_for_status()
            raw = str(resp.json().get("response", "")).strip()
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw) if s.strip()]
            if len(sentences) >= 3:
                summary = " ".join(sentences[:3]).strip()
                if summary:
                    return summary
        except Exception:
            pass

        return (
            f"Step {issue.get('step_name')} is overdue by {issue.get('hours_overdue')} hours. "
            f"Diagnosis indicates {diagnosis.get('stall_type')} requiring urgent escalation. "
            "Immediate cross-team follow-up is recommended to prevent further SLA breach."
        )

    def _update_stall_patterns(self, conn, approver_id: str, stall_type: str) -> None:
        """Upsert learning signals into stall_patterns without schema changes."""
        cur = conn.cursor()
        now = self._now_iso()
        condition = f"stall_type={stall_type}"
        normalized_approver = (approver_id or "unassigned").strip() or "unassigned"

        row = cur.execute(
            "SELECT id, sample_count, stall_rate FROM stall_patterns WHERE approver_id = ? LIMIT 1",
            (normalized_approver,),
        ).fetchone()

        stalled_event = 1 if stall_type in {"wrong_approver", "external_hold"} else 0
        if row:
            prev_sample_count = int(row["sample_count"])
            new_sample_count = prev_sample_count + 1
            prev_rate = float(row["stall_rate"])
            prev_stalled = prev_rate * prev_sample_count
            stalled_count = prev_stalled + stalled_event
            new_rate = stalled_count / max(new_sample_count, 1)
            cur.execute(
                "UPDATE stall_patterns SET condition = ?, stall_rate = ?, sample_count = ?, last_seen = ? WHERE id = ?",
                (condition, new_rate, new_sample_count, now, row["id"]),
            )
        else:
            sample_count = 1
            stall_rate = float(stalled_event)
            cur.execute(
                "INSERT INTO stall_patterns (id, approver_id, condition, stall_rate, sample_count, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), normalized_approver, condition, stall_rate, sample_count, now),
            )

    def _safe_status_update(self, cur, step_id: str, target_status: str) -> str:
        """Preserve compatibility when status enum is stricter in some environments."""
        try:
            cur.execute("UPDATE steps SET status = ? WHERE id = ?", (target_status, step_id))
            return target_status
        except Exception:
            cur.execute("UPDATE steps SET status = 'in_progress' WHERE id = ?", (step_id,))
            return "in_progress"

    def run(self, issue: dict[str, Any], diagnosis: dict[str, Any]) -> dict[str, str]:
        """Apply exactly one deterministic action for each issue/diagnosis pair."""
        workflow_id = str(issue.get("workflow_id", ""))
        step_id = str(issue.get("step_id", ""))
        step_name = str(issue.get("step_name", ""))
        assignee = str(issue.get("assignee", "unassigned"))

        stall_type = str(diagnosis.get("stall_type", "external_hold"))
        diag_reasoning = str(diagnosis.get("reasoning", ""))

        conn = get_connection()
        cur = conn.cursor()

        try:
            if stall_type == "wrong_approver":
                action_taken = "reroute_approver"
                row = cur.execute("SELECT assignee FROM steps WHERE id = ?", (step_id,)).fetchone()
                old_assignee = (row["assignee"] if row and row["assignee"] else assignee)
                backup = self._select_backup_approver(assignee, workflow_id, step_id)
                cur.execute(
                    "UPDATE steps SET assignee = ?, status = 'in_progress' WHERE id = ?",
                    (backup, step_id),
                )
                new_status = "in_progress"
                details = f"Reassigned from {old_assignee} to {backup}"

            elif stall_type == "external_hold":
                action_taken = "escalate_sla"
                new_status = self._safe_status_update(cur, step_id, "escalated")
                summary = self._generate_escalation_summary(issue, diagnosis)
                if not summary.strip():
                    summary = (
                        f"Step {step_name} is overdue by {issue.get('hours_overdue')} hours. "
                        "Escalation is required due to external dependencies. "
                        "Immediate follow-up is recommended."
                    )
                packet = {
                    "summary": summary,
                    "diagnosis": stall_type,
                    "diagnosis_reasoning": diag_reasoning,
                    "priority": "high" if float(issue.get("risk_score", 0)) > 1500 else "medium",
                    "created_at": self._now_iso(),
                }
                cur.execute(
                    "INSERT INTO escalations (id, workflow_id, step_id, packet, created_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), workflow_id, step_id, json.dumps(packet), self._now_iso()),
                )
                details = f"Escalated (summary: {summary[:100]})"

            elif stall_type == "duplicate_invoice":
                action_taken = "flag_duplicate"
                cur.execute("UPDATE workflows SET status = 'duplicate_hold' WHERE id = ?", (workflow_id,))
                new_status = "duplicate_hold"
                details = "Workflow status changed to duplicate_hold"

            elif stall_type == "missing_data":
                action_taken = "request_data"
                new_status = self._safe_status_update(cur, step_id, "pending_data")
                details = "Step marked pending_data; requested invoice metadata and supporting documents"

            elif stall_type == "amount_variance":
                action_taken = "auto_reject"
                new_status = self._safe_status_update(cur, step_id, "rejected")
                details = "Step rejected due to amount variance against expected value"

            else:
                action_taken = "escalate_sla"
                new_status = self._safe_status_update(cur, step_id, "escalated")
                packet = {
                    "summary": "Unknown diagnosis type encountered; deterministic escalation triggered.",
                    "diagnosis": stall_type,
                    "diagnosis_reasoning": diag_reasoning,
                    "priority": "medium",
                    "created_at": self._now_iso(),
                }
                cur.execute(
                    "INSERT INTO escalations (id, workflow_id, step_id, packet, created_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), workflow_id, step_id, json.dumps(packet), self._now_iso()),
                )
                details = "Unknown diagnosis type escalated deterministically"

            self._update_stall_patterns(conn, approver_id=assignee, stall_type=stall_type)
            conn.commit()
            return {
                "action_taken": action_taken,
                "new_status": new_status,
                "details": details,
            }
        except Exception as exc:
            conn.rollback()
            return {
                "action_taken": "action_error",
                "new_status": "unchanged",
                "details": f"Action failed: {type(exc).__name__}: {exc}",
            }
        finally:
            conn.close()
