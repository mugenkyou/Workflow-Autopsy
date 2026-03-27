"""
FastAPI application for Process Autopsy Agent — Phase 1.
"""

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import get_connection, init_db, seed_data


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


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and seed data on startup."""
    init_db()
    seed_data()
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

    results: List[WorkflowOut] = []
    for wf in workflows:
        # Current step = latest step where completed_at IS NULL
        step_row = cursor.execute(
            "SELECT id, step_name, assignee, status FROM steps "
            "WHERE workflow_id = ? AND completed_at IS NULL "
            "ORDER BY rowid DESC LIMIT 1",
            (wf["id"],),
        ).fetchone()

        current_step = None
        if step_row:
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
            "SELECT id FROM steps WHERE workflow_id = ? AND completed_at IS NULL ORDER BY rowid DESC LIMIT 1",
            (payload.workflow_id,),
        ).fetchone()
        if step:
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
            "SELECT id FROM steps WHERE workflow_id = ? AND completed_at IS NULL ORDER BY rowid DESC LIMIT 1",
            (payload.workflow_id,),
        ).fetchone()
        if step:
            cursor.execute("UPDATE steps SET status = 'breached' WHERE id = ?", (step["id"],))
            cursor.execute("UPDATE workflows SET status = 'breached' WHERE id = ?", (payload.workflow_id,))
        message = "Step status set to 'breached'"

    conn.commit()
    conn.close()

    return InjectFailureResponse(success=True, message=message)
