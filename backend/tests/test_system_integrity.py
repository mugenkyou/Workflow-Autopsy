"""
System integrity tests for deterministic issue processing.

Run: python backend/tests/test_system_integrity.py
(backend API must be running on localhost:8000)
"""

from __future__ import annotations

import json
import sqlite3
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

BASE = "http://localhost:8000"
DB_PATH = Path(__file__).resolve().parent.parent / "autopsy.db"

# Allow direct import of backend modules for targeted test controls.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _request(method: str, path: str, body: dict | None = None) -> dict | list:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"HTTP {exc.code} for {method} {path}: {raw}")


def _get(path: str) -> dict | list:
    return _request("GET", path)


def _post(path: str, body: dict | None = None) -> dict | list:
    return _request("POST", path, body)


def _pair_counts_from_audit_log() -> Counter:
    logs = _get("/audit-log")
    counter: Counter = Counter()
    for row in logs:
        pair = (row.get("workflow_id"), row.get("step_id"))
        counter[pair] += 1
    return counter


def _clear_audit_log() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM audit_log")
        conn.commit()
    finally:
        conn.close()


def _ensure_processed_pairs() -> set[tuple[str, str]]:
    """Return processed workflow/step pairs after at most two cycle triggers."""
    for _ in range(2):
        _post("/run-cycle")
        pairs = {
            (entry.get("workflow_id"), entry.get("step_id"))
            for entry in _get("/audit-log")
            if entry.get("workflow_id") and entry.get("step_id")
        }
        if pairs:
            return pairs
    return set()


def _assert_api_running() -> None:
    health = _get("/health")
    assert health.get("status") == "ok", f"Unexpected /health response: {health}"


def no_reprocessing_test() -> None:
    _post("/stop-agent")
    _clear_audit_log()
    _post("/inject-chaos")

    first_pairs = _ensure_processed_pairs()
    assert first_pairs, "No issues processed in first cycle"
    before_counts = _pair_counts_from_audit_log()

    second_cycle = _post("/run-cycle")
    assert second_cycle.get("success") is True, f"Second cycle failed: {second_cycle}"
    assert int(second_cycle.get("issues_processed", -1)) == 0, (
        "Second cycle should process zero issues once first cycle has resolved them"
    )

    after_counts = _pair_counts_from_audit_log()
    repeated = [
        pair for pair in first_pairs if after_counts[pair] > before_counts[pair]
    ]
    assert not repeated, f"Issues were reprocessed: {repeated}"

    print("PASS  no_reprocessing_test")


def resolution_test() -> None:
    _post("/stop-agent")
    _clear_audit_log()
    _post("/inject-chaos")

    before = _get("/active-issues")
    before_count = len(before.get("issues", []))
    assert before_count > 0, "Expected active issues right after chaos injection"

    run = _post("/run-cycle")
    assert run.get("success") is True, f"Cycle failed: {run}"

    after = _get("/active-issues")
    after_count = len(after.get("issues", []))
    assert after_count <= before_count, "Active issues did not reduce after cycle"

    print("PASS  resolution_test")


def single_processing_test() -> None:
    _post("/stop-agent")
    _clear_audit_log()
    _post("/inject-chaos")
    run = _post("/run-cycle")
    assert run.get("success") is True, f"Cycle failed: {run}"

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT workflow_id, step_id, COUNT(*) as c "
            "FROM audit_log GROUP BY workflow_id, step_id HAVING COUNT(*) > 1"
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 0, f"Duplicate audit rows found: {rows}"
    print("PASS  single_processing_test")


def llm_fallback_test() -> None:
    from graph import diagnosis_agent

    _post("/stop-agent")
    _clear_audit_log()

    original_endpoint = diagnosis_agent.endpoint
    diagnosis_agent.endpoint = "http://127.0.0.1:1/api/generate"
    try:
        _post("/inject-chaos")
        _post("/run-cycle")
        _post("/run-cycle")

        actions = [entry.get("action") for entry in _get("/audit-log")]
        assert "escalate_sla" in actions, (
            "Fallback path should produce deterministic escalate_sla action"
        )

        remaining = _get("/active-issues")
        remaining_count = len(remaining.get("issues", []))
        assert remaining_count == 0, "Issues remained active after fallback action"
    finally:
        diagnosis_agent.endpoint = original_endpoint

    print("PASS  llm_fallback_test")


ALL_TESTS = [
    no_reprocessing_test,
    resolution_test,
    single_processing_test,
    llm_fallback_test,
]


if __name__ == "__main__":
    _assert_api_running()
    passed = 0
    failed = 0

    print("=" * 60)
    print("System Integrity Validation")
    print("=" * 60)

    for test in ALL_TESTS:
        try:
            test()
            passed += 1
        except Exception as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")

    print("=" * 60)
    print(f"{passed} passed, {failed} failed")

    if failed:
        sys.exit(1)
