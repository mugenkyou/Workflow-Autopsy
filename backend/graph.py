from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agents.action import ActionAgent
from agents.audit import AuditAgent
from agents.diagnosis import DiagnosisAgent
from agents.monitor import MonitorAgent
from db import get_connection


class AgentState(TypedDict, total=False):
    issues: list[dict[str, Any]]
    current_issue: dict[str, Any]
    diagnosis: dict[str, Any]
    action_result: dict[str, Any]
    audit_entry: dict[str, Any]
    audit_entries: list[dict[str, Any]]
    pipeline_results: list[dict[str, Any]]


monitor_agent = MonitorAgent()
diagnosis_agent = DiagnosisAgent()
action_agent = ActionAgent()
audit_agent = AuditAgent()


def monitor_node(state: AgentState) -> AgentState:
    issues = monitor_agent.run()
    return {
        "issues": issues,
        "audit_entries": state.get("audit_entries", []),
        "pipeline_results": state.get("pipeline_results", []),
    }


def diagnosis_node(state: AgentState) -> AgentState:
    issues = list(state.get("issues", []))
    if not issues:
        return state

    current_issue = issues.pop(0)
    diagnosis = diagnosis_agent.run(current_issue)

    return {
        **state,
        "issues": issues,
        "current_issue": current_issue,
        "diagnosis": diagnosis,
    }


def action_node(state: AgentState) -> AgentState:
    issue = state.get("current_issue", {})
    diagnosis = state.get("diagnosis", {})

    try:
        action_result = action_agent.run(issue, diagnosis)
    except Exception as exc:
        # Continue processing remaining issues instead of crashing the cycle.
        action_result = {
            "action_taken": "action_error",
            "new_status": "unchanged",
            "details": f"DB action failed: {type(exc).__name__}: {exc}",
        }

    return {
        **state,
        "action_result": action_result,
    }


def audit_node(state: AgentState) -> AgentState:
    issue = state.get("current_issue", {})
    diagnosis = state.get("diagnosis", {})
    action_result = state.get("action_result", {})

    audit_entries = list(state.get("audit_entries", []))
    pipeline_results = list(state.get("pipeline_results", []))

    try:
        audit_entry = audit_agent.run(issue, diagnosis, action_result)
    except Exception as exc:
        # Never fail silently. Keep the cycle alive and capture failure context.
        audit_entry = {
            "id": "",
            "workflow_id": issue.get("workflow_id", ""),
            "step_id": issue.get("step_id", ""),
            "agent_name": "AuditAgent",
            "action": "audit_error",
            "reasoning": f"Audit insert failed: {type(exc).__name__}: {exc}",
            "confidence": 0.0,
            "timestamp": "",
        }

    enriched_entry = {
        **audit_entry,
        "issue": issue,
        "diagnosis": diagnosis,
        "action_result": action_result,
    }

    audit_entries.append(enriched_entry)
    pipeline_results.append(
        {
            "issue": issue,
            "diagnosis": diagnosis,
            "action_result": action_result,
            "audit_entry": audit_entry,
        }
    )

    return {
        **state,
        "audit_entry": enriched_entry,
        "audit_entries": audit_entries,
        "pipeline_results": pipeline_results,
    }


def _route_after_monitor(state: AgentState) -> str:
    return "diagnosis" if state.get("issues") else END


def _route_after_audit(state: AgentState) -> str:
    return "diagnosis" if state.get("issues") else END


def _build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("monitor", monitor_node)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("action", action_node)
    graph.add_node("audit", audit_node)

    graph.set_entry_point("monitor")
    graph.add_conditional_edges("monitor", _route_after_monitor, {"diagnosis": "diagnosis", END: END})
    graph.add_edge("diagnosis", "action")
    graph.add_edge("action", "audit")
    graph.add_conditional_edges("audit", _route_after_audit, {"diagnosis": "diagnosis", END: END})

    return graph.compile()


def _print_cycle_summary(audit_entries: list[dict[str, Any]]) -> None:
    total_issues_processed = len(audit_entries)
    total_risk_handled = 0.0
    action_counts: dict[str, int] = {}
    highest_risk_issue: dict[str, Any] | None = None
    confidence_total = 0.0
    confidence_count = 0

    for entry in audit_entries:
        issue = entry.get("issue", {}) or {}
        diagnosis = entry.get("diagnosis", {}) or {}
        action_result = entry.get("action_result", {}) or {}

        risk = float(issue.get("risk_score", 0.0) or 0.0)
        total_risk_handled += risk
        if highest_risk_issue is None or risk > float(highest_risk_issue.get("risk_score", 0.0) or 0.0):
            highest_risk_issue = issue

        action_taken = str(action_result.get("action_taken", entry.get("action", "unknown")))
        action_counts[action_taken] = action_counts.get(action_taken, 0) + 1

        confidence = diagnosis.get("confidence", entry.get("confidence", None))
        try:
            if confidence is not None:
                confidence_total += float(confidence)
                confidence_count += 1
        except (TypeError, ValueError):
            pass

    average_confidence = (confidence_total / confidence_count) if confidence_count else 0.0
    recovered_value = total_risk_handled
    workflows_saved = total_issues_processed
    prevented_sla_breaches = action_counts.get("reroute_approver", 0) + action_counts.get("escalate_sla", 0)

    conn = get_connection()
    cur = conn.cursor()
    pattern_rows = cur.execute(
        "SELECT approver_id, sample_count, stall_rate "
        "FROM stall_patterns "
        "ORDER BY sample_count DESC, stall_rate DESC "
        "LIMIT 3"
    ).fetchall()
    conn.close()

    print("======================================")
    print("CYCLE SUMMARY")
    print("======================================")

    if total_issues_processed == 0:
        print("No issues detected")
        print("Issues processed: 0")
        print("Total risk handled: 0.00")
        print("")
        print("Actions taken:")
        print("  - none: 0")
        print("")
        print("Top risk issue:")
        print("  Workflow: n/a")
        print("  Risk: 0.00")
        print("")
        print("Average confidence: 0.00")
        print("")
        print("Learning insights:")
        if pattern_rows:
            for row in pattern_rows:
                print(f"  {row['approver_id']} -> {row['sample_count']} stalls -> {float(row['stall_rate']):.2f}")
        else:
            print("  none")
        print("")
        print("Business impact:")
        print("  No business impact - no issues detected")
        print("")
        print("======================================")
        return

    print(f"Issues processed: {total_issues_processed}")
    print(f"Total risk handled: {total_risk_handled:.2f}")
    print("")
    print("Actions taken:")
    for action_name, count in sorted(action_counts.items()):
        print(f"  - {action_name}: {count}")
    print("")
    print("Top risk issue:")
    print(f"  Workflow: {(highest_risk_issue or {}).get('workflow_id', 'n/a')}")
    print(f"  Risk: {float((highest_risk_issue or {}).get('risk_score', 0.0) or 0.0):.2f}")
    print("")
    print(f"Average confidence: {average_confidence:.2f}")
    print("")
    print("Learning insights:")
    if pattern_rows:
        for row in pattern_rows:
            print(f"  {row['approver_id']} -> {row['sample_count']} stalls -> {float(row['stall_rate']):.2f}")
    else:
        print("  none")
    print("")
    print("Business impact:")
    print(f"  Prevented SLA breaches on {workflows_saved} workflows")
    print(f"  Recovered {recovered_value:.2f} worth of delayed processing")
    print(f"  Preventive actions (reroute/escalate): {prevented_sla_breaches}")
    print("")
    print("======================================")


def run_cycle() -> list[dict[str, Any]]:
    app = _build_graph()
    final_state = app.invoke({"issues": [], "audit_entries": [], "pipeline_results": []})
    results = final_state.get("audit_entries", [])
    print(f"Total issues processed: {len(results)}")
    _print_cycle_summary(results)
    return results


if __name__ == "__main__":
    import json

    print(json.dumps(run_cycle(), indent=2))
