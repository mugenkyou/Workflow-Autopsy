"""Quick test gate runner for Phase 1 backend."""
import urllib.request
import json

BASE = "http://localhost:8000"

def test_health():
    resp = json.loads(urllib.request.urlopen(f"{BASE}/health").read())
    assert resp == {"status": "ok", "model": "mistral"}, f"FAIL: {resp}"
    print("PASS  /health ->", resp)

def test_workflows():
    data = json.loads(urllib.request.urlopen(f"{BASE}/workflows").read())
    assert isinstance(data, list), "FAIL: not a list"
    assert len(data) == 15, f"FAIL: expected 15, got {len(data)}"
    for w in data:
        assert "current_step" in w, f"FAIL: missing current_step in {w['id']}"
        if w["current_step"]:
            assert "step_name" in w["current_step"]
            assert "assignee" in w["current_step"]
            assert "status" in w["current_step"]
    statuses = [w["status"] for w in data]
    assert statuses.count("stalled") >= 3, f"FAIL: stalled count {statuses.count('stalled')}"
    assert statuses.count("at_risk") >= 3, f"FAIL: at_risk count {statuses.count('at_risk')}"
    assert statuses.count("breached") >= 2, f"FAIL: breached count {statuses.count('breached')}"
    print(f"PASS  /workflows -> {len(data)} workflows")
    for w in data:
        cs = w["current_step"]
        step_info = f"{cs['step_name']} ({cs['status']})" if cs else "None"
        print(f"      {w['name']:30s}  {w['vendor']:25s}  {w['status']:15s}  step: {step_info}")
    return data[0]["id"]

def test_audit_log():
    data = json.loads(urllib.request.urlopen(f"{BASE}/audit-log").read())
    assert isinstance(data, list), "FAIL: not a list"
    print(f"PASS  /audit-log -> {len(data)} entries")

def test_inject_failure(workflow_id):
    for ftype in ["stall", "duplicate", "sla_breach"]:
        body = json.dumps({"workflow_id": workflow_id, "failure_type": ftype}).encode()
        req = urllib.request.Request(
            f"{BASE}/inject-failure",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = json.loads(urllib.request.urlopen(req).read())
        assert resp["success"] is True, f"FAIL inject {ftype}: {resp}"
        print(f"PASS  /inject-failure ({ftype}) -> {resp['message']}")

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 1 Test Gates")
    print("=" * 60)
    test_health()
    wf_id = test_workflows()
    test_audit_log()
    test_inject_failure(wf_id)
    print("=" * 60)
    print("ALL GATES PASSED")
    print("=" * 60)
