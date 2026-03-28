"""
FastAPI application for Process Autopsy Agent — Phase 1.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional
import random
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import get_connection, init_db, seed_data, repair_data
from graph import run_cycle
from agents.monitor import MonitorAgent


# Latest Break It run context for demo isolation
LATEST_INJECTED_RUN_ID: Optional[str] = None
LATEST_INJECTED_WORKFLOW_IDS: set[str] = set()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    model: str


class CurrentStep(BaseModel):
    step_id: str
    step_name: str
    assignee: Optional[str]
    status: str


class WorkflowOut(BaseModel):
    id: str
    name: str
    vendor: str
    po_amount: float
    status: str
    created_at: str
    current_step: Optional[CurrentStep]


class AuditLogEntry(BaseModel):
    id: str
    workflow_id: Optional[str]
    step_id: Optional[str]
    agent_name: Optional[str]
    action: Optional[str]
    reasoning: Optional[str]
    confidence: Optional[float]
    timestamp: Optional[str]


class ActiveIssue(BaseModel):
    workflow_id: str
    step_id: str
    step_name: str
    assignee: str
    failure_type: str
    hours_overdue: float
    risk_score: float
    injected_run_id: Optional[str] = None


class ActiveIssuesResponse(BaseModel):
    success: bool
    issues: List[ActiveIssue]
    total_risk_exposure: float


class EscalationItem(BaseModel):
    id: str
    workflow_id: str
    step_id: str
    step_name: str
    assignee: str
    failure_type: str
    hours_overdue: float
    risk_score: float


class EscalationsResponse(BaseModel):
    success: bool
    issues: List[EscalationItem]
    total_risk_exposure: float


class InjectChaosResponse(BaseModel):
    success: bool
    message: str
    failures_injected: List[str]
    audit_entries: List[AuditLogEntry]
    run_id: Optional[str] = None
    workflow_ids: Optional[List[str]] = None


class InjectFailureRequest(BaseModel):
    workflow_id: str
    failure_type: str  # "stall" | "duplicate" | "sla_breach"
    injected_run_id: Optional[str] = None


class InjectFailureResponse(BaseModel):
    success: bool
    message: str


class RunCycleResponse(BaseModel):
    success: bool
    issues_processed: int
    audit_entries: List[AuditLogEntry]
    message: Optional[str]


def _reset_demo_state(clear_audit_log: bool = True) -> None:
    """Reset workflow/step failure states before a new Break It run."""
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.utcnow().isoformat()

    # Reset workflow-level statuses and clear prior run tags.
    cursor.execute("UPDATE workflows SET status = 'on_track', injected_run_id = NULL")

    # Clear any stale run tags from steps before we rebuild a fresh baseline.
    cursor.execute("UPDATE steps SET injected_run_id = NULL")

    # Clean temporary failure states before repair_data normalizes active steps.
    cursor.execute(
        "UPDATE steps SET status = 'completed', completed_at = COALESCE(completed_at, ?) "
        "WHERE status IN ('stalled', 'breached')",
        (now_iso,),
    )

    # Resolve any open escalations from previous runs.
    cursor.execute(
        "UPDATE escalations SET resolved_at = ? WHERE resolved_at IS NULL",
        (now_iso,),
    )

    # Optional cleanup for demo clarity.
    if clear_audit_log:
        cursor.execute("DELETE FROM audit_log")

    conn.commit()
    conn.close()

    # Rebuild valid baseline step state (exactly one active step per workflow,
    # no stale stalled/breached/duplicate leftovers).
    repair_data()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, seed data, and repair invariants on startup."""
    print("[STARTUP] Starting init_db...")
    init_db()
    print("[STARTUP] init_db complete")
    print("[STARTUP] Starting seed_data...")
    seed_data()
    print("[STARTUP] seed_data complete")
    print("[STARTUP] Starting repair_data...")
    repair_data()
    print("[STARTUP] repair_data complete")
    print("[STARTUP] All startup tasks complete - app ready!")
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Process Autopsy Agent",
    description="Phase 1 — Foundation Backend",
    version="0.1.0",
    lifespan=lifespan,
)
# Auto-reload trigger 

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return system health status."""
    return HealthResponse(status="ok", model="mistral")


@app.get("/workflows", response_model=List[WorkflowOut])
def get_workflows():
    """Return all workflows with their current (in-progress) step."""
    conn = get_connection()
    cursor = conn.cursor()

    workflows = cursor.execute(
        "SELECT id, name, vendor, po_amount, status, created_at FROM workflows ORDER BY created_at"
    ).fetchall()

    if len(workflows) == 0:
        conn.close()
        return []

    results: List[WorkflowOut] = []
    for wf in workflows:
        # Get current step (active/in-progress first, then fallback to last step)
        step_row = cursor.execute(
            "SELECT id, step_name, assignee, status FROM steps "
            "WHERE workflow_id = ? AND completed_at IS NULL "
            "AND status IN ('in_progress','stalled','breached','escalated') "
            "ORDER BY datetime(started_at) DESC, rowid DESC LIMIT 1",
            (wf["id"],),
        ).fetchone()

        if step_row is None:
            # No active step - get the latest step regardless of status
            step_row = cursor.execute(
                "SELECT id, step_name, assignee, status FROM steps "
                "WHERE workflow_id = ? "
                "ORDER BY datetime(started_at) DESC, rowid DESC LIMIT 1",
                (wf["id"],),
            ).fetchone()
            
        if step_row is None:
            continue  # Skip workflows with no steps

        current_step = CurrentStep(
            step_id=step_row["id"],
            step_name=step_row["step_name"],
            assignee=step_row["assignee"],
            status=step_row["status"],
        )

        results.append(
            WorkflowOut(
                id=wf["id"],
                name=wf["name"],
                vendor=wf["vendor"],
                po_amount=wf["po_amount"],
                status=wf["status"],
                created_at=wf["created_at"],
                current_step=current_step,
            )
        )

    conn.close()
    return results
    return results


@app.get("/audit-log", response_model=List[AuditLogEntry])
def get_audit_log():
    """Return the last 50 audit log entries, newest first."""
    conn = get_connection()
    cursor = conn.cursor()

    rows = cursor.execute(
        "SELECT id, workflow_id, step_id, agent_name, action, reasoning, confidence, timestamp "
        "FROM audit_log ORDER BY timestamp DESC LIMIT 50"
    ).fetchall()

    entries = [
        AuditLogEntry(
            id=row["id"],
            workflow_id=row["workflow_id"],
            step_id=row["step_id"],
            agent_name=row["agent_name"],
            action=row["action"],
            reasoning=row["reasoning"],
            confidence=row["confidence"],
            timestamp=row["timestamp"],
        )
        for row in rows
    ]

    conn.close()
    return entries


@app.post("/inject-failure", response_model=InjectFailureResponse)
def inject_failure(payload: InjectFailureRequest):
    """Inject a simulated failure into an existing workflow."""
    valid_types = {"stall", "duplicate", "sla_breach"}
    if payload.failure_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid failure_type '{payload.failure_type}'. Must be one of: {', '.join(sorted(valid_types))}",
        )

    conn = get_connection()
    cursor = conn.cursor()

    # Verify workflow exists
    wf = cursor.execute("SELECT id FROM workflows WHERE id = ?", (payload.workflow_id,)).fetchone()
    if not wf:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Workflow {payload.workflow_id} not found")

    if payload.failure_type == "stall":
        # Set the latest in-progress step to 'stalled'
        step = cursor.execute(
            "SELECT id, sla_hours FROM steps "
            "WHERE workflow_id = ? AND completed_at IS NULL "
            "AND status IN ('in_progress','stalled','breached') "
            "ORDER BY datetime(started_at) DESC, rowid DESC LIMIT 1",
            (payload.workflow_id,),
        ).fetchone()
        if not step:
            conn.close()
            raise HTTPException(status_code=409, detail="No active step found to stall")
        sla_hours = int(step["sla_hours"] or 12)
        overdue_start = (datetime.utcnow() - timedelta(hours=sla_hours + 2)).isoformat()
        cursor.execute(
            "UPDATE steps SET status = 'stalled', started_at = ?, completed_at = NULL, injected_run_id = ? WHERE id = ?",
            (overdue_start, payload.injected_run_id, step["id"]),
        )
        cursor.execute(
            "UPDATE workflows SET status = 'stalled', injected_run_id = ? WHERE id = ?",
            (payload.injected_run_id, payload.workflow_id),
        )
        message = "Step forced overdue and status set to 'stalled'"

    elif payload.failure_type == "duplicate":
        # Mark workflow as duplicate_hold and make active step overdue
        step = cursor.execute(
            "SELECT id, sla_hours FROM steps "
            "WHERE workflow_id = ? AND completed_at IS NULL "
            "ORDER BY datetime(started_at) DESC, rowid DESC LIMIT 1",
            (payload.workflow_id,),
        ).fetchone()
        if step:
            sla_hours = int(step["sla_hours"] or 12)
            overdue_start = (datetime.utcnow() - timedelta(hours=sla_hours + 2)).isoformat()
            cursor.execute(
                "UPDATE steps SET started_at = ?, completed_at = NULL, status = 'in_progress', injected_run_id = ? WHERE id = ?",
                (overdue_start, payload.injected_run_id, step["id"]),
            )
        cursor.execute(
            "UPDATE workflows SET status = 'duplicate_hold', injected_run_id = ? WHERE id = ?",
            (payload.injected_run_id, payload.workflow_id),
        )
        message = "Workflow status set to 'duplicate_hold' and active step forced overdue"

    elif payload.failure_type == "sla_breach":
        # Mark the latest in-progress step as 'breached'
        step = cursor.execute(
            "SELECT id, sla_hours FROM steps "
            "WHERE workflow_id = ? AND completed_at IS NULL "
            "AND status IN ('in_progress','stalled','breached') "
            "ORDER BY datetime(started_at) DESC, rowid DESC LIMIT 1",
            (payload.workflow_id,),
        ).fetchone()
        if not step:
            conn.close()
            raise HTTPException(status_code=409, detail="No active step found to breach")
        sla_hours = int(step["sla_hours"] or 12)
        overdue_start = (datetime.utcnow() - timedelta(hours=sla_hours + 2)).isoformat()
        cursor.execute(
            "UPDATE steps SET status = 'breached', started_at = ?, completed_at = NULL, injected_run_id = ? WHERE id = ?",
            (overdue_start, payload.injected_run_id, step["id"]),
        )
        cursor.execute(
            "UPDATE workflows SET status = 'breached', injected_run_id = ? WHERE id = ?",
            (payload.injected_run_id, payload.workflow_id),
        )
        message = "Step forced overdue and status set to 'breached'"

    conn.commit()
    conn.close()

    return InjectFailureResponse(success=True, message=message)


@app.post("/run-cycle", response_model=RunCycleResponse)
def run_autonomous_cycle():
    """Execute one autonomous cycle of the agent system and return audit entries."""
    try:
        # Call graph.run_cycle() which processes all issues and returns audit entries
        result = run_cycle()
        
        # Count issues processed
        issues_processed = len(result) if result else 0
        
        # Convert to AuditLogEntry models
        entries = [
            AuditLogEntry(
                id=entry.get("id", ""),
                workflow_id=entry.get("workflow_id"),
                step_id=entry.get("step_id"),
                agent_name=entry.get("agent_name"),
                action=entry.get("action"),
                reasoning=entry.get("reasoning"),
                confidence=entry.get("confidence"),
                timestamp=entry.get("timestamp"),
            )
            for entry in result
        ]
        
        return RunCycleResponse(
            success=True,
            issues_processed=issues_processed,
            audit_entries=entries,
            message=f"Cycle complete: {issues_processed} issues processed",
        )
    
    except Exception as e:
        return RunCycleResponse(
            success=False,
            issues_processed=0,
            audit_entries=[],
            message=f"Cycle failed: {str(e)}",
        )


@app.get("/active-issues", response_model=ActiveIssuesResponse)
def get_active_issues():
    """Get all active issues ranked by risk score (highest first)."""
    try:
        # No Break It run yet means no demo issues should be shown.
        if not LATEST_INJECTED_RUN_ID:
            return ActiveIssuesResponse(
                success=True,
                issues=[],
                total_risk_exposure=0.0,
            )

        monitor = MonitorAgent()
        issues = monitor.run()

        # Sort by risk_score descending
        sorted_issues = sorted(issues, key=lambda x: x.get("risk_score", 0), reverse=True)

        # Build a DB-backed run_id map so issue scoping is stable and explicit.
        conn = get_connection()
        cursor = conn.cursor()
        tagged_rows = cursor.execute(
            "SELECT id, injected_run_id FROM workflows "
            "WHERE injected_run_id IS NOT NULL"
        ).fetchall()
        conn.close()

        workflow_run_map = {
            row["id"]: row["injected_run_id"]
            for row in tagged_rows
        }

        # Only return issues from the latest injected run_id.
        filtered_issues = []
        for issue in sorted_issues:
            workflow_id = issue.get("workflow_id")
            issue_run_id = workflow_run_map.get(workflow_id)
            if issue_run_id == LATEST_INJECTED_RUN_ID:
                issue["injected_run_id"] = issue_run_id
                filtered_issues.append(issue)
        
        # Convert to ActiveIssue models
        issue_models = [
            ActiveIssue(
                workflow_id=issue["workflow_id"],
                step_id=issue["step_id"],
                step_name=issue["step_name"],
                assignee=issue["assignee"],
                failure_type=issue["failure_type"],
                hours_overdue=issue["hours_overdue"],
                risk_score=issue["risk_score"],
                injected_run_id=issue.get("injected_run_id"),
            )
            for issue in filtered_issues
        ]
        
        # Calculate total risk exposure (sum of all risk scores)
        total_risk_exposure = sum(issue.risk_score for issue in issue_models)
        
        return ActiveIssuesResponse(
            success=True,
            issues=issue_models,
            total_risk_exposure=round(total_risk_exposure, 2),
        )
    
    except Exception as e:
        print(f"Error in get_active_issues: {e}")
        return ActiveIssuesResponse(
            success=False,
            issues=[],
            total_risk_exposure=0.0,
        )


@app.post("/inject-chaos", response_model=InjectChaosResponse)
def inject_chaos():
    """Inject 3 random failures (stall, duplicate, sla_breach) without running cycle."""
    try:
        global LATEST_INJECTED_RUN_ID, LATEST_INJECTED_WORKFLOW_IDS

        # Fresh demo run: clear previous temporary failure state.
        _reset_demo_state(clear_audit_log=True)

        conn = get_connection()
        cursor = conn.cursor()
        
        # Get all workflow IDs
        all_workflows = cursor.execute("SELECT id, po_amount FROM workflows").fetchall()
        conn.close()
        
        if len(all_workflows) < 3:
            raise HTTPException(status_code=400, detail="Not enough workflows to inject 3 failures")
        
        # Pick 3 random workflows using system entropy so each run is fresh.
        selected = random.SystemRandom().sample(all_workflows, 3)
        workflow_1 = selected[0]["id"]
        workflow_2 = selected[1]["id"]
        workflow_3 = selected[2]["id"]

        run_id = str(uuid.uuid4())
        LATEST_INJECTED_RUN_ID = run_id
        LATEST_INJECTED_WORKFLOW_IDS = {workflow_1, workflow_2, workflow_3}
        
        # Inject the failures
        failures_injected = []
        
        try:
            inject_failure(
                InjectFailureRequest(
                    workflow_id=workflow_1,
                    failure_type="stall",
                    injected_run_id=run_id,
                )
            )
            failures_injected.append(f"stall → {workflow_1}")
        except Exception as e:
            print(f"Failed to inject stall: {e}")
        
        try:
            inject_failure(
                InjectFailureRequest(
                    workflow_id=workflow_2,
                    failure_type="duplicate",
                    injected_run_id=run_id,
                )
            )
            failures_injected.append(f"duplicate → {workflow_2}")
        except Exception as e:
            print(f"Failed to inject duplicate: {e}")
        
        try:
            inject_failure(
                InjectFailureRequest(
                    workflow_id=workflow_3,
                    failure_type="sla_breach",
                    injected_run_id=run_id,
                )
            )
            failures_injected.append(f"sla_breach → {workflow_3}")
        except Exception as e:
            print(f"Failed to inject sla_breach: {e}")
        
        # DO NOT run cycle here — let it run on its own polling schedule (~30s)
        # This enables users to see injected failures in the UI before resolution
        
        return InjectChaosResponse(
            success=True,
            message=f"Chaos injected: {len(failures_injected)} failures (will resolve on next cycle ~30s)",
            failures_injected=failures_injected,
            audit_entries=[],
            run_id=run_id,
            workflow_ids=[workflow_1, workflow_2, workflow_3],
        )
    
    except Exception as e:
        return InjectChaosResponse(
            success=False,
            message=f"Chaos injection failed: {str(e)}",
            failures_injected=[],
            audit_entries=[],
            run_id=None,
            workflow_ids=[],
        )


# ---------------------------------------------------------------------------
# Escalations & Learning Endpoints (Phase 7)
# ---------------------------------------------------------------------------

@app.get("/escalations", response_model=EscalationsResponse)
def get_escalations():
    """Get unresolved escalations for human review."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get unresolved escalations with workflow/step details
        rows = cursor.execute("""
            SELECT e.id, e.workflow_id, e.step_id, e.packet, e.created_at,
                   w.name, w.vendor, s.step_name, s.assignee
            FROM escalations e
            JOIN workflows w ON w.id = e.workflow_id
            JOIN steps s ON s.id = e.step_id
            WHERE e.resolved_at IS NULL
            ORDER BY e.created_at DESC
        """).fetchall()
        
        conn.close()
        
        issue_models = [
            EscalationItem(
                id=row["id"],
                workflow_id=row["workflow_id"],
                step_id=row["step_id"],
                step_name=row["step_name"],
                assignee=row["assignee"] or "unassigned",
                failure_type="escalated",
                hours_overdue=0.0,
                risk_score=9999.0,  # Escalations have highest priority
            )
            for row in rows
        ]
        
        total_risk = sum(issue.risk_score for issue in issue_models)
        
        return EscalationsResponse(
            success=True,
            issues=issue_models,
            total_risk_exposure=round(total_risk, 2),
        )
    
    except Exception as e:
        print(f"Error fetching escalations: {e}")
        return EscalationsResponse(
            success=False,
            issues=[],
            total_risk_exposure=0.0,
        )


class MarkResolvedRequest(BaseModel):
    escalation_id: str


class MarkResolvedResponse(BaseModel):
    success: bool
    message: str


@app.post("/mark-resolved", response_model=MarkResolvedResponse)
def mark_escalation_resolved(payload: MarkResolvedRequest):
    """Mark an escalation as reviewed/resolved by human."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verify escalation exists
        esc = cursor.execute(
            "SELECT id, workflow_id, step_id FROM escalations WHERE id = ?", (payload.escalation_id,)
        ).fetchone()
        
        if not esc:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Escalation {payload.escalation_id} not found")
        
        # Mark escalation as resolved
        now = datetime.utcnow().isoformat()
        cursor.execute(
            "UPDATE escalations SET resolved_at = ? WHERE id = ?",
            (now, payload.escalation_id),
        )
        
        # Also resolve the associated step and workflow so the monitor
        # stops re-detecting them as active issues
        cursor.execute(
            "UPDATE steps SET status = 'completed', completed_at = ? WHERE id = ?",
            (now, esc["step_id"]),
        )
        cursor.execute(
            "UPDATE workflows SET status = 'on_track' WHERE id = ?",
            (esc["workflow_id"],),
        )
        
        conn.commit()
        conn.close()
        
        return MarkResolvedResponse(
            success=True,
            message="Escalation marked as reviewed",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        return MarkResolvedResponse(
            success=False,
            message=f"Error marking escalation: {str(e)}",
        )


class StallPattern(BaseModel):
    approver_id: str
    condition: str
    stall_rate: float
    sample_count: int


class StallPatternsResponse(BaseModel):
    success: bool
    patterns: List[StallPattern]


@app.get("/stall-patterns", response_model=StallPatternsResponse)
def get_stall_patterns():
    """Get top 5 stall patterns by rate (learned behavioral patterns)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        rows = cursor.execute("""
            SELECT approver_id, condition, stall_rate, sample_count
            FROM stall_patterns
            ORDER BY stall_rate DESC
            LIMIT 5
        """).fetchall()
        
        conn.close()
        
        patterns = [
            StallPattern(
                approver_id=row["approver_id"],
                condition=row["condition"],
                stall_rate=float(row["stall_rate"]),
                sample_count=int(row["sample_count"]),
            )
            for row in rows
        ]
        
        return StallPatternsResponse(
            success=True,
            patterns=patterns,
        )
    
    except Exception as e:
        print(f"Error fetching stall patterns: {e}")
        return StallPatternsResponse(
            success=False,
            patterns=[],
        )


class SimpleResponse(BaseModel):
    success: bool
    message: str


@app.post("/stop-agent", response_model=SimpleResponse)
def stop_agent():
    """Stop agent processing. (Demo mode: returns success)"""
    global LATEST_INJECTED_RUN_ID, LATEST_INJECTED_WORKFLOW_IDS
    LATEST_INJECTED_RUN_ID = None
    LATEST_INJECTED_WORKFLOW_IDS = set()

    # Stop also resets demo state so the next Break It starts clean.
    _reset_demo_state(clear_audit_log=True)

    return SimpleResponse(
        success=True,
        message="Agent processing stopped",
    )
