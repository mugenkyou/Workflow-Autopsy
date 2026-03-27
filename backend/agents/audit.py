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
        workflow_id = str(issue.get("workflow_id", ""))
        step_id = str(issue.get("step_id", ""))
        action_taken = str(action_result.get("action_taken", "unknown_action"))
        reasoning = str(diagnosis.get("reasoning", ""))
        confidence = float(diagnosis.get("confidence", 0.0))

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
