"""
Consistency validation tests for diagnosis->action mapping and audit quality.

Run: python backend/tests/test_consistency.py
(backend API must be running on localhost:8000)
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
import sqlite3
import sys

BASE = "http://localhost:8000"
DB_PATH = Path(__file__).resolve().parent.parent / "autopsy.db"
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from graph import run_cycle  # noqa: E402

MAPPING = {
    "wrong_approver": "reroute_approver",
    "missing_data": "request_data",
    "duplicate_invoice": "flag_duplicate",
    "amount_variance": "auto_reject",
    "external_hold": "escalate_sla",
}


def _request(method: str, path: str):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"HTTP {exc.code} for {method} {path}: {raw}")


def _get(path: str):
    return _request("GET", path)


def _post(path: str):
    return _request("POST", path)


def _clear_audit() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM audit_log")
        conn.commit()
    finally:
        conn.close()


def _prepare_and_run_cycle() -> list[dict]:
    _post("/stop-agent")
    _clear_audit()
    _post("/inject-chaos")

    results = run_cycle()
    if not results:
        results = run_cycle()
    return results


def mapping_test() -> None:
    results = _prepare_and_run_cycle()
    assert results, "Expected at least one processed issue for mapping test"

    for entry in results:
        diagnosis = entry.get("diagnosis", {}) or {}
        action_result = entry.get("action_result", {}) or {}
        stall_type = diagnosis.get("stall_type")
        action_taken = action_result.get("action_taken")
        expected = MAPPING.get(stall_type)
        assert expected is not None, f"Unexpected stall_type in result: {stall_type}"
        assert action_taken == expected, (
            f"Action mismatch for {stall_type}: expected {expected}, got {action_taken}"
        )

    print("PASS  mapping_test")


def no_placeholder_test() -> None:
    _prepare_and_run_cycle()
    logs = _get("/audit-log")
    banned_tokens = {"pending", "not captured", "default fallback", "reasoning unavailable"}

    for row in logs:
        for key in ("workflow_id", "step_id", "action", "reasoning", "timestamp"):
            value = str(row.get(key) or "").strip().lower()
            assert value, f"Missing required audit field: {key}"
            for token in banned_tokens:
                assert token not in value, f"Placeholder token '{token}' found in {key}: {row.get(key)}"

    print("PASS  no_placeholder_test")


def reasoning_presence_test() -> None:
    _prepare_and_run_cycle()
    logs = _get("/audit-log")
    assert logs, "Expected audit rows for reasoning presence test"

    for row in logs:
        reasoning = str(row.get("reasoning") or "").strip()
        assert reasoning, f"Empty reasoning for audit id={row.get('id')}"

    print("PASS  reasoning_presence_test")


if __name__ == "__main__":
    tests = [mapping_test, no_placeholder_test, reasoning_presence_test]
    passed = 0
    failed = 0

    print("=" * 60)
    print("Consistency Validation")
    print("=" * 60)

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")

    print("=" * 60)
    print(f"{passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)
