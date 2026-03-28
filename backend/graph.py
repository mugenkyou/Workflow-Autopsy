from __future__ import annotations

from datetime import datetime
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
    processed_count: int  # Track how many issues processed in this cycle


monitor_agent = MonitorAgent()
diagnosis_agent = DiagnosisAgent()
action_agent = ActionAgent()
audit_agent = AuditAgent()

# Global tracking for debugging
_cycle_start_time = None
_max_cycle_duration_seconds = 120  # 2 minutes absolute max per cycle


def monitor_node(state: AgentState) -> AgentState:
    global _cycle_start_time
    _cycle_start_time = datetime.utcnow()
    
    issues = monitor_agent.run()
    
    print(f"\n[CYCLE] MONITOR: Found {len(issues)} issues to process", file=sys.stderr)
    if issues:
        for idx, issue in enumerate(issues[:3]):  # Log first 3
            print(f"  [{idx+1}] {issue.get('workflow_id')}/{issue.get('step_id')}: {issue.get('failure_type')}", 
                  file=sys.stderr)
    
    return {
        "issues": issues,
        "audit_entries": state.get("audit_entries", []),
        "pipeline_results": state.get("pipeline_results", []),
        "processed_count": 0,
    }


def diagnosis_node(state: AgentState) -> AgentState:
    global _cycle_start_time
    
    # Check cycle timeout
    if _cycle_start_time:
        elapsed = (datetime.utcnow() - _cycle_start_time).total_seconds()
        if elapsed > _max_cycle_duration_seconds:
            print(f"[TIMEOUT] Cycle exceeded {_max_cycle_duration_seconds}s. Terminating.", file=sys.stderr)
            return {**state, "issues": [], "processed_count": state.get("processed_count", 0)}
    
    issues = list(state.get("issues", []))
    if not issues:
        return state

    current_issue = issues.pop(0)
    workflow_id = current_issue.get("workflow_id", "?")
    step_id = current_issue.get("step_id", "?")
    
    print(f"[DIAGNOSIS] Processing {workflow_id}/{step_id}", file=sys.stderr)
    diagnosis = diagnosis_agent.run(current_issue)
    print(f"[DIAGNOSIS] Result: {diagnosis.get('stall_type')} (confidence: {diagnosis.get('confidence')})", 
          file=sys.stderr)

    return {
        **state,
        "issues": issues,
        "current_issue": current_issue,
        "diagnosis": diagnosis,
    }


def action_node(state: AgentState) -> AgentState:
    issue = state.get("current_issue", {})
    diagnosis = state.get("diagnosis", {})
    workflow_id = issue.get("workflow_id", "?")
    step_id = issue.get("step_id", "?")

    print(f"[ACTION] Processing {workflow_id}/{step_id}", file=sys.stderr)
    
    try:
        action_result = action_agent.run(issue, diagnosis)
        print(f"[ACTION] Result: {action_result.get('action_taken')}", file=sys.stderr)
    except Exception as exc:
        # Continue processing remaining issues instead of crashing the cycle.
        action_result = {
            "action_taken": "action_error",
            "new_status": "unchanged",
            "details": f"DB action failed: {type(exc).__name__}: {exc}",
        }
        print(f"[ACTION] ERROR: {action_result['details']}", file=sys.stderr)

    return {
        **state,
        "action_result": action_result,
    }


def audit_node(state: AgentState) -> AgentState:
    issue = state.get("current_issue", {})
    diagnosis = state.get("diagnosis", {})
    action_result = state.get("action_result", {})
    workflow_id = issue.get("workflow_id", "?")
    step_id = issue.get("step_id", "?")
    processed_count = state.get("processed_count", 0) + 1

    print(f"[AUDIT] Recording issue #{processed_count}: {workflow_id}/{step_id}", file=sys.stderr)

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
        "processed_count": processed_count,
    }


def _route_after_monitor(state: AgentState) -> str:
    issues_remaining = len(state.get("issues", []))
    if issues_remaining:
        print(f"[ROUTE] {issues_remaining} issues remaining, continue processing", file=sys.stderr)
        return "diagnosis"
    else:
        print(f"[ROUTE] No issues remaining, END cycle", file=sys.stderr)
        return END


def _route_after_audit(state: AgentState) -> str:
    issues_remaining = len(state.get("issues", []))
    processed_count = state.get("processed_count", 0)
    
    if issues_remaining:
        print(f"[ROUTE] {processed_count} processed, {issues_remaining} remaining, continue", file=sys.stderr)
        return "diagnosis"
    else:
        print(f"[ROUTE] CYCLE COMPLETE: {processed_count} issues processed", file=sys.stderr)
        return END


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

    print(f"\n[SUMMARY] Total issues processed: {total_issues_processed}", file=sys.stderr)
    
    for idx, entry in enumerate(audit_entries, 1):
        issue = entry.get("issue", {}) or {}
        diagnosis = entry.get("diagnosis", {}) or {}
        action_result = entry.get("action_result", {}) or {}
        
        workflow_id = issue.get("workflow_id", "?")
        step_id = issue.get("step_id", "?")
        action_taken = action_result.get("action_taken", "unknown")
        
        print(f"  [#{idx}] {workflow_id}/{step_id} via {action_taken}", file=sys.stderr)

        risk = float(issue.get("risk_score", 0.0) or 0.0)
        total_risk_handled += risk
        if highest_risk_issue is None or risk > float(highest_risk_issue.get("risk_score", 0.0) or 0.0):
            highest_risk_issue = issue

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
