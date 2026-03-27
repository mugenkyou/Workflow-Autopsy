from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agents.action import ActionAgent
from agents.audit import AuditAgent
from agents.diagnosis import DiagnosisAgent
from agents.monitor import MonitorAgent


class AgentState(TypedDict, total=False):
    issues: list[dict[str, Any]]
    current_issue: dict[str, Any]
    diagnosis: dict[str, Any]
    action_result: dict[str, Any]
    audit_entry: dict[str, Any]
    audit_entries: list[dict[str, Any]]


monitor_agent = MonitorAgent()
diagnosis_agent = DiagnosisAgent()
action_agent = ActionAgent()
audit_agent = AuditAgent()


def monitor_node(state: AgentState) -> AgentState:
    issues = monitor_agent.run()
    return {
        "issues": issues,
        "audit_entries": state.get("audit_entries", []),
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

    audit_entries.append(audit_entry)

    return {
        **state,
        "audit_entry": audit_entry,
        "audit_entries": audit_entries,
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


def run_cycle() -> list[dict[str, Any]]:
    app = _build_graph()
    final_state = app.invoke({"issues": [], "audit_entries": []})
    return final_state.get("audit_entries", [])


if __name__ == "__main__":
    import json

    print(json.dumps(run_cycle(), indent=2))
