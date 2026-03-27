"""
Test gates for Process Autopsy Agent — Phase 1 (with Phase 2 invariants).
Validates all API endpoints and DB invariants.

Run: python tests/test_api.py  (server must be running on port 8000)
"""

import urllib.request
import json
import sys
import os
from datetime import datetime
from pathlib import Path

BASE = "http://localhost:8000"


def _get(path: str):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read())


def _post(path: str, body: dict):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req).read())


# ---------- Core endpoint tests ----------


def test_health():
    resp = _get("/health")
    assert resp == {"status": "ok", "model": "mistral"}, f"FAIL: {resp}"
    print("PASS  /health ->", resp)


def test_workflows_count():
    data = _get("/workflows")
    assert isinstance(data, list), "FAIL: not a list"
    assert len(data) == 15, f"FAIL: expected 15 workflows, got {len(data)}"
    print(f"PASS  /workflows -> {len(data)} workflows")


def test_workflows_have_current_step():
    """Every workflow MUST have exactly 1 current_step."""
    data = _get("/workflows")
    for w in data:
        assert w["current_step"] is not None, f"FAIL: workflow {w['id']} ({w['name']}) has no current_step"
        for key in ("step_name", "assignee", "status"):
            assert key in w["current_step"], f"FAIL: missing {key} in current_step"
    print("PASS  /workflows -> all 15 workflows have current_step")


def test_no_pending_steps():
    """No step should have status 'pending'."""
    data = _get("/workflows")
    for w in data:
        cs = w["current_step"]
        assert cs["status"] != "pending", f"FAIL: workflow {w['id']} current_step has status 'pending'"
    print("PASS  No current_step has status 'pending'")


def test_workflows_status_distribution():
    data = _get("/workflows")
    statuses = [w["status"] for w in data]
    assert statuses.count("stalled") >= 3, f"FAIL: stalled={statuses.count('stalled')}, need >=3"
    assert statuses.count("at_risk") >= 3, f"FAIL: at_risk={statuses.count('at_risk')}, need >=3"
    assert statuses.count("breached") >= 2, f"FAIL: breached={statuses.count('breached')}, need >=2"
    print("PASS  /workflows -> status distribution meets requirements")
    for w in data:
        cs = w["current_step"]
        step_info = f"{cs['step_name']} ({cs['status']})" if cs else "None"
        print(f"      {w['name']:30s}  {w['vendor']:25s}  {w['status']:15s}  step: {step_info}")


def test_in_progress_count():
    """At least 5 current steps should be 'in_progress'."""
    data = _get("/workflows")
    in_prog = sum(1 for w in data if w["current_step"] and w["current_step"]["status"] == "in_progress")
    assert in_prog >= 5, f"FAIL: only {in_prog} in_progress steps, need >= 5"
    print(f"PASS  {in_prog} workflows have in_progress current step (>= 5)")


def test_audit_log():
    data = _get("/audit-log")
    assert isinstance(data, list), "FAIL: not a list"
    print(f"PASS  /audit-log -> {len(data)} entries")


# ---------- Inject failure tests (use on_track workflows only) ----------

# Cache IDs once before any inject test mutates DB state
_INJECT_TEST_IDS = None

def _get_inject_ids():
    global _INJECT_TEST_IDS
    if _INJECT_TEST_IDS is None:
        data = _get("/workflows")
        _INJECT_TEST_IDS = [w["id"] for w in data if w["status"] == "on_track"]
    return _INJECT_TEST_IDS


def _restore_workflow(workflow_id: str):
    """Restore a workflow to on_track status after inject test."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
    from db import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE workflows SET status = 'on_track' WHERE id = ?", (workflow_id,))
    # Also reset the current step to in_progress
    cursor.execute(
        "UPDATE steps SET status = 'in_progress', completed_at = NULL "
        "WHERE workflow_id = ? AND completed_at IS NULL",
        (workflow_id,),
    )
    conn.commit()
    conn.close()


def test_inject_failure_stall():
    ids = _get_inject_ids()
    assert len(ids) >= 3, f"Need at least 3 on_track workflows, got {len(ids)}"
    resp = _post("/inject-failure", {"workflow_id": ids[0], "failure_type": "stall"})
    assert resp["success"] is True, f"FAIL: {resp}"
    print(f"PASS  /inject-failure (stall) -> {resp['message']}")
    # Restore workflow for next test
    _restore_workflow(ids[0])


def test_inject_failure_duplicate():
    ids = _get_inject_ids()
    resp = _post("/inject-failure", {"workflow_id": ids[1], "failure_type": "duplicate"})
    assert resp["success"] is True, f"FAIL: {resp}"
    print(f"PASS  /inject-failure (duplicate) -> {resp['message']}")
    # Restore workflow for next test
    _restore_workflow(ids[1])


def test_inject_failure_sla_breach():
    ids = _get_inject_ids()
    resp = _post("/inject-failure", {"workflow_id": ids[2], "failure_type": "sla_breach"})
    assert resp["success"] is True, f"FAIL: {resp}"
    print(f"PASS  /inject-failure (sla_breach) -> {resp['message']}")
    # Restore workflow for next test
    _restore_workflow(ids[2])


# ---------- Runner ----------

ALL_TESTS = [
    test_health,
    test_workflows_count,
    test_workflows_have_current_step,
    test_no_pending_steps,
    test_workflows_status_distribution,
    test_in_progress_count,
    test_audit_log,
    test_inject_failure_stall,
    test_inject_failure_duplicate,
    test_inject_failure_sla_breach,
]

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 1 Test Gates (with Phase 2 invariants)")
    print("=" * 60)
    passed, failed = 0, 0
    for fn in ALL_TESTS:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"FAIL  {fn.__name__}: {e}")
            failed += 1
    print("=" * 60)
    print(f"{passed} passed, {failed} failed")
    if failed:
        print("SOME GATES FAILED")
        sys.exit(1)
    else:
        print("ALL GATES PASSED")
