from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime

from pathlib import Path
import sys

AGENTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = AGENTS_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from graph import run_cycle


def execute_cycle() -> None:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    entries = run_cycle()

    if not entries:
        print(f"[{now}] No overdue in_progress issues found.")
        return

    print(f"[{now}] Autonomous cycle complete. Audit entries created: {len(entries)}")
    for entry in entries:
        issue = entry.get("issue", {})
        diagnosis = entry.get("diagnosis", {})
        action_result = entry.get("action_result", {})

        print("ISSUE:")
        print(f"  Workflow: {issue.get('workflow_id', '')}")
        print(f"  Step: {issue.get('step_name', '')}")
        print(f"  Risk: {issue.get('risk_score', '')}")
        print("")
        print("DIAGNOSIS:")
        print(f"  Type: {diagnosis.get('stall_type', '')}")
        print(f"  Confidence: {float(diagnosis.get('confidence', 0.0)):.2f}")
        print(f"  Reason: {diagnosis.get('reasoning', '')}")
        print("")
        print("ACTION:")
        print(f"  Action: {action_result.get('action_taken', '')}")
        print(f"  Result: {action_result.get('details', '')}")
        print("")
        print("--------------------------------------")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run autonomous Monitor + Diagnosis + Action + Audit loop.")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    args = parser.parse_args()

    while True:
        try:
            execute_cycle()
        except Exception as exc:  # Keep loop resilient in long-running mode
            ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Runner error: {exc}")

        if args.once:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
