from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import get_connection


class MonitorAgent:
    """Detect overdue in-progress steps and classify likely failure type."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def _is_duplicate_invoice(conn, workflow_id: str, vendor: str, po_amount: float, created_at: str) -> bool:
        """Check same vendor+amount in the last 30 days for a different workflow."""
        cur = conn.cursor()
        try:
            created_dt = datetime.fromisoformat(created_at)
        except ValueError:
            return False

        window_start = (created_dt - timedelta(days=30)).isoformat()
        row = cur.execute(
            "SELECT COUNT(*) FROM workflows "
            "WHERE id != ? AND vendor = ? AND po_amount = ? "
            "AND created_at >= ? AND created_at <= ?",
            (workflow_id, vendor, po_amount, window_start, created_at),
        ).fetchone()
        return bool(row and row[0] > 0)

    @staticmethod
    def _failure_type(step_name: str, is_duplicate: bool) -> str:
        if "Approval" in step_name:
            return "stall"
        if "Invoice" in step_name and is_duplicate:
            return "duplicate"
        return "sla_breach"

    @staticmethod
    def _was_recently_processed(conn, workflow_id: str, step_id: str, time_window_minutes: int = 5) -> bool:
        """Check if this workflow/step pair was processed in audit_log within the last N minutes."""
        cur = conn.cursor()
        cutoff_time = (datetime.utcnow() - timedelta(minutes=time_window_minutes)).isoformat()
        row = cur.execute(
            "SELECT COUNT(*) as cnt FROM audit_log "
            "WHERE workflow_id = ? AND step_id = ? AND timestamp >= ? "
            "LIMIT 1",
            (workflow_id, step_id, cutoff_time),
        ).fetchone()
        was_processed = bool(row and row["cnt"] > 0)
        if was_processed:
            print(f"[DEDUP] Skipping {workflow_id}/{step_id}: recently processed", file=__import__('sys').stderr)
        return was_processed

    def run(self) -> list[dict[str, Any]]:
        """Return overdue in-progress issues + stalled/breached steps, ordered by descending risk score."""
        conn = get_connection()
        cur = conn.cursor()

        # Query 1: Overdue in-progress steps
        rows = cur.execute(
            "SELECT s.id AS step_id, s.workflow_id, s.step_name, s.assignee, s.sla_hours, s.started_at, "
            "s.status, w.vendor, w.po_amount, w.created_at "
            "FROM steps s "
            "JOIN workflows w ON w.id = s.workflow_id "
            "WHERE s.status = 'in_progress' AND s.completed_at IS NULL "
            "AND w.status != 'duplicate_hold'"
        ).fetchall()

        now = datetime.utcnow()
        issues: list[dict[str, Any]] = []

        for row in rows:
            if not row["started_at"] or row["sla_hours"] is None:
                continue

            try:
                started_at = datetime.fromisoformat(row["started_at"])
            except ValueError:
                continue

            deadline = started_at + timedelta(hours=float(row["sla_hours"]))
            if deadline >= now:
                continue

            hours_overdue = max((now - deadline).total_seconds() / 3600.0, 0.0)
            po_amount = float(row["po_amount"])
            risk_score = hours_overdue * po_amount * 0.001

            duplicate = self._is_duplicate_invoice(
                conn=conn,
                workflow_id=row["workflow_id"],
                vendor=row["vendor"],
                po_amount=po_amount,
                created_at=row["created_at"],
            )
            failure_type = self._failure_type(row["step_name"], duplicate)

            # CRITICAL: Check if recently processed to prevent reprocessing
            if self._was_recently_processed(conn, row["workflow_id"], row["step_id"]):
                continue

            issue = {
                "workflow_id": row["workflow_id"],
                "step_id": row["step_id"],
                "step_name": row["step_name"],
                "assignee": row["assignee"] or "unassigned",
                "hours_overdue": round(hours_overdue, 2),
                "risk_score": round(risk_score, 2),
                "failure_type": failure_type,
            }
            issues.append(issue)

            ts = now.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] ISSUE: {issue['workflow_id']} | {issue['step_name']} | Risk: {issue['risk_score']:.2f}")

        # Query 2: Stalled and breached steps (only if overdue)
        failed_rows = cur.execute(
            "SELECT s.id AS step_id, s.workflow_id, s.step_name, s.assignee, s.sla_hours, s.started_at, "
            "s.status, w.vendor, w.po_amount, w.created_at "
            "FROM steps s "
            "JOIN workflows w ON w.id = s.workflow_id "
            "WHERE s.status IN ('stalled', 'breached') AND s.completed_at IS NULL"
        ).fetchall()

        for row in failed_rows:
            if not row["started_at"]:
                continue

            try:
                started_at = datetime.fromisoformat(row["started_at"])
            except ValueError:
                continue

            if row["sla_hours"] is None:
                continue

            deadline = started_at + timedelta(hours=float(row["sla_hours"]))
            if deadline >= now:
                continue

            # For failed steps, compute hours overdue from SLA deadline
            hours_overdue = max((now - deadline).total_seconds() / 3600.0, 0.0)
            po_amount = float(row["po_amount"])
            risk_score = hours_overdue * po_amount * 0.001

            # Classify failure type based on step status
            failure_type = "stall" if row["status"] == "stalled" else "sla_breach"

            # CRITICAL: Check if recently processed to prevent reprocessing
            if self._was_recently_processed(conn, row["workflow_id"], row["step_id"]):
                continue

            issue = {
                "workflow_id": row["workflow_id"],
                "step_id": row["step_id"],
                "step_name": row["step_name"],
                "assignee": row["assignee"] or "unassigned",
                "hours_overdue": round(hours_overdue, 2),
                "risk_score": round(risk_score, 2),
                "failure_type": failure_type,
            }
            issues.append(issue)

            ts = now.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] INJECTED: {issue['workflow_id']} | {issue['step_name']} ({failure_type}) | Risk: {issue['risk_score']:.2f}")

        # Query 3: Duplicate workflows (only if overdue)
        dup_rows = cur.execute(
            "SELECT s.id AS step_id, s.workflow_id, s.step_name, s.assignee, s.sla_hours, s.started_at, "
            "w.vendor, w.po_amount, w.created_at "
            "FROM steps s "
            "JOIN workflows w ON w.id = s.workflow_id "
            "WHERE w.status = 'duplicate_hold' AND s.completed_at IS NULL "
            "ORDER BY s.started_at DESC LIMIT 1"
        ).fetchall()

        for row in dup_rows:
            if not row["started_at"]:
                continue

            try:
                started_at = datetime.fromisoformat(row["started_at"])
            except ValueError:
                continue

            if row["sla_hours"] is None:
                continue

            deadline = started_at + timedelta(hours=float(row["sla_hours"]))
            if deadline >= now:
                continue

            # For duplicate workflows, compute hours overdue from SLA deadline
            hours_overdue = max((now - deadline).total_seconds() / 3600.0, 0.0)
            po_amount = float(row["po_amount"])
            risk_score = hours_overdue * po_amount * 0.001

            # CRITICAL: Check if recently processed to prevent reprocessing
            if self._was_recently_processed(conn, row["workflow_id"], row["step_id"]):
                continue

            issue = {
                "workflow_id": row["workflow_id"],
                "step_id": row["step_id"],
                "step_name": row["step_name"],
                "assignee": row["assignee"] or "unassigned",
                "hours_overdue": round(hours_overdue, 2),
                "risk_score": round(risk_score, 2),
                "failure_type": "duplicate",
            }
            issues.append(issue)

            ts = now.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] DUPLICATE: {issue['workflow_id']} | {issue['step_name']} | Risk: {issue['risk_score']:.2f}")

        conn.close()

        issues.sort(key=lambda x: x["risk_score"], reverse=True)
        return issues
