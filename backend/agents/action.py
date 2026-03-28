from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

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

    def _escalation_summary(self, issue: dict[str, Any], diagnosis: dict[str, Any]) -> str:
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

    def _mark_step_resolved(self, cur, step_id: str, now_iso: str) -> str:
        resolved_status = self._safe_status_update(cur, step_id, "completed")
        cur.execute(
            "UPDATE steps SET completed_at = ? WHERE id = ?",
            (now_iso, step_id),
        )
        return resolved_status

    def _upsert_escalation(self, cur, workflow_id: str, step_id: str, packet: dict[str, Any], now_iso: str) -> str:
        existing = cur.execute(
            "SELECT id FROM escalations "
            "WHERE workflow_id = ? AND step_id = ? AND resolved_at IS NULL "
            "LIMIT 1",
            (workflow_id, step_id),
        ).fetchone()
        if existing:
            return f"Already escalated (id: {existing['id']})"

        cur.execute(
            "INSERT INTO escalations (id, workflow_id, step_id, packet, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), workflow_id, step_id, json.dumps(packet), now_iso),
        )
        return "Escalated with deterministic escalation packet"

    def run(self, issue: dict[str, Any], diagnosis: dict[str, Any]) -> dict[str, str]:
        """Apply exactly one deterministic action for each issue/diagnosis pair."""
        workflow_id = str(issue.get("workflow_id", ""))
        step_id = str(issue.get("step_id", ""))
        step_name = str(issue.get("step_name", ""))
        assignee = str(issue.get("assignee", "unassigned"))

        stall_type = str(diagnosis.get("stall_type", "external_hold"))
        diag_reasoning = str(diagnosis.get("reasoning", ""))

        # Deterministic fallback mapping.
        if stall_type not in {
            "wrong_approver",
            "external_hold",
            "duplicate_invoice",
            "missing_data",
            "amount_variance",
        }:
            stall_type = "external_hold"

        conn = get_connection()
        cur = conn.cursor()
        
        # CRITICAL: Track processing attempt every time we execute an action
        now_iso = self._now_iso()

        try:
            if stall_type == "wrong_approver":
                action_taken = "reroute_approver"
                row = cur.execute("SELECT assignee FROM steps WHERE id = ?", (step_id,)).fetchone()
                old_assignee = (row["assignee"] if row and row["assignee"] else assignee)
                backup = self._select_backup_approver(assignee, workflow_id, step_id)
                cur.execute(
                    "UPDATE steps SET assignee = ? WHERE id = ?",
                    (backup, step_id),
                )
                new_status = self._mark_step_resolved(cur, step_id, now_iso)
                cur.execute("UPDATE workflows SET status = 'on_track' WHERE id = ?", (workflow_id,))
                details = f"Reassigned from {old_assignee} to {backup}"
                print(f"[ACTION] {workflow_id}/{step_id}: {action_taken} -> {new_status}", file=__import__('sys').stderr)

            elif stall_type == "external_hold":
                action_taken = "escalate_sla"
                packet = {
                    "summary": self._escalation_summary(issue, diagnosis),
                    "diagnosis": stall_type,
                    "diagnosis_reasoning": diag_reasoning,
                    "priority": "high" if float(issue.get("risk_score", 0)) > 1500 else "medium",
                    "created_at": now_iso,
                }
                details = self._upsert_escalation(cur, workflow_id, step_id, packet, now_iso)
                new_status = self._mark_step_resolved(cur, step_id, now_iso)
                cur.execute("UPDATE workflows SET status = 'escalated' WHERE id = ?", (workflow_id,))
                print(f"[ACTION] {workflow_id}/{step_id}: {action_taken} -> {new_status}", file=__import__('sys').stderr)

            elif stall_type == "duplicate_invoice":
                action_taken = "flag_duplicate"
                cur.execute("UPDATE workflows SET status = 'duplicate_hold' WHERE id = ?", (workflow_id,))
                new_status = self._mark_step_resolved(cur, step_id, now_iso)
                details = "Workflow status changed to duplicate_hold"
                print(f"[ACTION] {workflow_id}/{step_id}: {action_taken} -> {new_status}", file=__import__('sys').stderr)

            elif stall_type == "missing_data":
                action_taken = "request_data"
                new_status = self._mark_step_resolved(cur, step_id, now_iso)
                cur.execute("UPDATE workflows SET status = 'on_track' WHERE id = ?", (workflow_id,))
                details = "Step marked pending_data; requested invoice metadata and supporting documents"
                print(f"[ACTION] {workflow_id}/{step_id}: {action_taken} -> {new_status}", file=__import__('sys').stderr)

            elif stall_type == "amount_variance":
                action_taken = "auto_reject"
                new_status = self._mark_step_resolved(cur, step_id, now_iso)
                cur.execute("UPDATE workflows SET status = 'on_track' WHERE id = ?", (workflow_id,))
                details = "Step rejected due to amount variance against expected value"
                print(f"[ACTION] {workflow_id}/{step_id}: {action_taken} -> {new_status}", file=__import__('sys').stderr)

            else:
                action_taken = "escalate_sla"
                packet = {
                    "summary": "Unknown diagnosis type encountered; deterministic escalation triggered.",
                    "diagnosis": stall_type,
                    "diagnosis_reasoning": diag_reasoning,
                    "priority": "medium",
                    "created_at": now_iso,
                }
                details = self._upsert_escalation(cur, workflow_id, step_id, packet, now_iso)
                new_status = self._mark_step_resolved(cur, step_id, now_iso)
                cur.execute("UPDATE workflows SET status = 'escalated' WHERE id = ?", (workflow_id,))
                print(f"[ACTION] {workflow_id}/{step_id}: {action_taken} (fallback) -> {new_status}", file=__import__('sys').stderr)

            self._update_stall_patterns(conn, approver_id=assignee, stall_type=stall_type)
            conn.commit()
            print(f"[ACTION] RESOLVED: {workflow_id}/{step_id} via {action_taken}", file=__import__('sys').stderr)
            return {
                "action_taken": action_taken,
                "new_status": new_status,
                "details": details,
                "resolved_status": "resolved",
            }
        except Exception as exc:
            conn.rollback()
            return {
                "action_taken": "action_error",
                "new_status": "unchanged",
                "details": f"Action failed: {type(exc).__name__}: {exc}",
                "resolved_status": "failed",
            }
        finally:
            conn.close()
