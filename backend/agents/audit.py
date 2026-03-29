from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import get_connection


class AuditAgent:
    """Persist one auditable record per processed issue."""

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    def run(self, issue: dict[str, Any], diagnosis: dict[str, Any], action_result: dict[str, Any]) -> dict[str, Any]:
        workflow_id = str(issue.get("workflow_id") or "unknown_workflow")
        step_id = str(issue.get("step_id") or "unknown_step")
        action_taken = str(action_result.get("action_taken") or "escalate_sla")

        reasoning = str(diagnosis.get("reasoning") or "").strip()
        if not reasoning:
            details = str(action_result.get("details") or "").strip()
            reasoning = details or "The system selected a deterministic corrective action based on issue context."

        raw_confidence = diagnosis.get("confidence", 0.5)
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            confidence = 0.0

        if confidence < 0.0:
            confidence = 0.0
        if confidence > 1.0:
            confidence = 1.0

        entry = {
            "id": str(uuid.uuid4()),
            "workflow_id": workflow_id,
            "step_id": step_id,
            "agent_name": "AuditAgent",
            "action": action_taken,
            "reasoning": reasoning,
            "confidence": confidence,
            "timestamp": self._now_iso(),
        }

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO audit_log (id, workflow_id, step_id, agent_name, action, reasoning, confidence, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry["id"],
                    entry["workflow_id"],
                    entry["step_id"],
                    entry["agent_name"],
                    entry["action"],
                    entry["reasoning"],
                    entry["confidence"],
                    entry["timestamp"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return entry
