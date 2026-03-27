from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime

from diagnosis import DiagnosisAgent
from monitor import MonitorAgent


def run_cycle(monitor: MonitorAgent, diagnosis: DiagnosisAgent) -> None:
    issues = monitor.run()
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    if not issues:
        print(f"[{now}] No overdue in_progress issues found.")
        return

    print(f"[{now}] Issues found: {len(issues)}")
    for issue in issues:
        result = diagnosis.run(issue)
        print(
            "ISSUE -> DIAGNOSIS | "
            f"workflow_id={issue['workflow_id']} | "
            f"step={issue['step_name']} | "
            f"risk_score={issue['risk_score']:.2f} | "
            f"stall_type={result['stall_type']} | "
            f"confidence={result['confidence']:.2f} | "
            f"reasoning={result['reasoning']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Monitor + Diagnosis loop.")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    args = parser.parse_args()

    monitor = MonitorAgent()
    diagnosis = DiagnosisAgent()

    while True:
        try:
            run_cycle(monitor, diagnosis)
        except Exception as exc:  # Keep loop resilient in long-running mode
            ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Runner error: {exc}")

        if args.once:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
