"""
FastAPI application for Process Autopsy Agent — Phase 1.
"""

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import get_connection, init_db, seed_data, repair_data
from graph import run_cycle


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


class InjectFailureRequest(BaseModel):
    workflow_id: str
    failure_type: str  # "stall" | "duplicate" | "sla_breach"


class InjectFailureResponse(BaseModel):
    success: bool
    message: str


class RunCycleResponse(BaseModel):
    success: bool
    issues_processed: int
    audit_entries: List[AuditLogEntry]
    message: Optional[str]


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, seed data, and repair invariants on startup."""
    init_db()
    seed_data()
    repair_data()
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
    """Return all 15 workflows with their current (in-progress) step."""
    conn = get_connection()
    cursor = conn.cursor()

    workflows = cursor.execute(
        "SELECT id, name, vendor, po_amount, status, created_at FROM workflows ORDER BY created_at"
    ).fetchall()

    if len(workflows) != 15:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Expected 15 workflows, found {len(workflows)}")

    results: List[WorkflowOut] = []
    for wf in workflows:
        active_count = cursor.execute(
            "SELECT COUNT(*) FROM steps "
            "WHERE workflow_id = ? AND completed_at IS NULL AND status IN ('in_progress','stalled','breached','escalated')",
            (wf["id"],),
        ).fetchone()[0]
        if active_count != 1:
            conn.close()
            raise HTTPException(
                status_code=500,
                detail=f"Workflow {wf['id']} has {active_count} active steps; expected 1",
            )

        # Current step = latest active step where completed_at IS NULL
        step_row = cursor.execute(
            "SELECT id, step_name, assignee, status FROM steps "
            "WHERE workflow_id = ? AND completed_at IS NULL "
            "AND status IN ('in_progress','stalled','breached','escalated') "
            "ORDER BY datetime(started_at) DESC, rowid DESC LIMIT 1",
            (wf["id"],),
        ).fetchone()

        if not step_row:
            conn.close()
            raise HTTPException(status_code=500, detail=f"Workflow {wf['id']} has no current step")

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
            "SELECT id FROM steps "
            "WHERE workflow_id = ? AND completed_at IS NULL "
            "AND status IN ('in_progress','stalled','breached') "
            "ORDER BY datetime(started_at) DESC, rowid DESC LIMIT 1",
            (payload.workflow_id,),
        ).fetchone()
        if not step:
            conn.close()
            raise HTTPException(status_code=409, detail="No active step found to stall")

        cursor.execute("UPDATE steps SET status = 'stalled' WHERE id = ?", (step["id"],))
        cursor.execute("UPDATE workflows SET status = 'stalled' WHERE id = ?", (payload.workflow_id,))
        message = "Step status set to 'stalled'"

    elif payload.failure_type == "duplicate":
        # Mark workflow as duplicate_hold
        cursor.execute("UPDATE workflows SET status = 'duplicate_hold' WHERE id = ?", (payload.workflow_id,))
        message = "Workflow status set to 'duplicate_hold'"

    elif payload.failure_type == "sla_breach":
        # Mark the latest in-progress step as 'breached'
        step = cursor.execute(
            "SELECT id FROM steps "
            "WHERE workflow_id = ? AND completed_at IS NULL "
            "AND status IN ('in_progress','stalled','breached') "
            "ORDER BY datetime(started_at) DESC, rowid DESC LIMIT 1",
            (payload.workflow_id,),
        ).fetchone()
        if not step:
            conn.close()
            raise HTTPException(status_code=409, detail="No active step found to breach")

        cursor.execute("UPDATE steps SET status = 'breached' WHERE id = ?", (step["id"],))
        cursor.execute("UPDATE workflows SET status = 'breached' WHERE id = ?", (payload.workflow_id,))
        message = "Step status set to 'breached'"

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
