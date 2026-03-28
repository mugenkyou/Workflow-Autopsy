"""
Database module for Process Autopsy Agent.
Handles SQLite connection, schema initialization, and seed data.
"""

import sqlite3
import uuid
import random
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "autopsy.db"


def get_connection() -> sqlite3.Connection:
    """Return a sqlite3 connection with Row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            vendor TEXT NOT NULL,
            po_amount REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS steps (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            step_name TEXT NOT NULL,
            assignee TEXT,
            sla_hours INTEGER,
            started_at TEXT,
            completed_at TEXT,
            status TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            workflow_id TEXT,
            step_id TEXT,
            agent_name TEXT,
            action TEXT,
            reasoning TEXT,
            confidence REAL,
            timestamp TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stall_patterns (
            id TEXT PRIMARY KEY,
            approver_id TEXT,
            condition TEXT,
            stall_rate REAL,
            sample_count INTEGER,
            last_seen TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            id TEXT PRIMARY KEY,
            workflow_id TEXT,
            step_id TEXT,
            packet TEXT,
            created_at TEXT,
            resolved_at TEXT
        )
    """)

    # Backward-compat cleanup: keep only the newest unresolved escalation
    # per (workflow_id, step_id) so unique index creation won't fail.
    cursor.execute(
        "DELETE FROM escalations "
        "WHERE resolved_at IS NULL AND rowid NOT IN ("
        "  SELECT MAX(rowid) FROM escalations "
        "  WHERE resolved_at IS NULL "
        "  GROUP BY workflow_id, step_id"
        ")"
    )

    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_escalations_open_unique "
        "ON escalations(workflow_id, step_id) WHERE resolved_at IS NULL"
    )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Seed data constants
# ---------------------------------------------------------------------------

VENDORS = [
    "Tata Steel",
    "Reliance Industries",
    "Larsen & Toubro",
    "Infosys",
    "Wipro",
    "Hindustan Unilever",
    "Mahindra & Mahindra",
    "Bharat Electronics",
    "Adani Ports",
    "JSW Steel",
    "Sun Pharma",
    "NTPC Limited",
    "ONGC",
    "Bajaj Auto",
    "Godrej Industries",
]

WORKFLOW_NAMES = [
    "PO-2024-Steel-Import",
    "PO-2024-IT-Services",
    "PO-2024-Construction-Material",
    "PO-2024-Software-License",
    "PO-2024-Cloud-Infra",
    "PO-2024-FMCG-Supply",
    "PO-2024-Auto-Parts",
    "PO-2024-Defence-Electronics",
    "PO-2024-Port-Equipment",
    "PO-2024-Metal-Alloy",
    "PO-2024-Pharma-API",
    "PO-2024-Power-Turbine",
    "PO-2024-Oil-Rig-Parts",
    "PO-2024-Vehicle-Assembly",
    "PO-2024-Chemical-Reagents",
]

STEP_TEMPLATES = [
    ["Invoice Received", "Manager Approval", "Finance Approval", "Payment Processing"],
    ["Purchase Request", "Vendor Selection", "Manager Approval", "Invoice Received", "Payment Processing"],
    ["Invoice Received", "Budget Verification", "Finance Approval", "Payment Processing"],
    ["Purchase Request", "Manager Approval", "Invoice Received", "Finance Approval", "Payment Processing"],
    ["Invoice Received", "Manager Approval", "Finance Approval"],
]

ASSIGNEES = [
    "Aarav Sharma",
    "Priya Patel",
    "Rohan Mehta",
    "Sneha Iyer",
    "Vikram Reddy",
    "Ananya Gupta",
    "Karan Singh",
    "Meera Nair",
    "Arjun Desai",
    "Pooja Verma",
    "Rahul Joshi",
    "Deepika Rao",
    "Amit Kulkarni",
    "Neha Kapoor",
    "Siddharth Bhat",
]

# Stable demo startup: all workflows healthy by default.
WORKFLOW_STATUSES = ["on_track"] * 15


def seed_data() -> None:
    """Insert 15 realistic workflows with steps. Idempotent — skips if data exists."""
    conn = get_connection()
    cursor = conn.cursor()

    count = cursor.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
    if count > 0:
        conn.close()
        return

    random.seed(42)  # deterministic for reproducibility
    base_time = datetime(2024, 11, 1, 9, 0, 0)

    for idx in range(15):
        workflow_id = str(uuid.uuid4())
        workflow_status = WORKFLOW_STATUSES[idx]
        created_at = (base_time + timedelta(days=idx, hours=random.randint(0, 8))).isoformat()
        po_amount = round(random.uniform(50_000, 500_000), 2)

        cursor.execute(
            "INSERT INTO workflows (id, name, vendor, po_amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (workflow_id, WORKFLOW_NAMES[idx], VENDORS[idx], po_amount, workflow_status, created_at),
        )

        # Pick a step template (3-5 steps)
        steps = STEP_TEMPLATES[idx % len(STEP_TEMPLATES)]
        num_steps = len(steps)

        # Decide which step is the "current" in-progress step
        # For completed workflows we still need at least one in_progress per requirement
        in_progress_idx = random.randint(max(0, num_steps - 2), num_steps - 1)

        for step_idx, step_name in enumerate(steps):
            step_id = str(uuid.uuid4())
            assignee = ASSIGNEES[(idx + step_idx) % len(ASSIGNEES)]
            sla_hours = random.choice([24, 48, 72, 96])

            step_started = (
                datetime.fromisoformat(created_at) + timedelta(hours=step_idx * sla_hours * 0.5)
            ).isoformat()

            if step_idx < in_progress_idx:
                # completed step
                step_completed = (
                    datetime.fromisoformat(step_started) + timedelta(hours=random.randint(2, sla_hours))
                ).isoformat()
                step_status = "completed"
            elif step_idx == in_progress_idx:
                # current in-progress step
                step_completed = None
                if workflow_status == "stalled":
                    step_status = "stalled"
                elif workflow_status == "breached":
                    step_status = "breached"
                elif workflow_status == "at_risk":
                    step_status = "in_progress"
                else:
                    step_status = "in_progress"
            else:
                # future step, not yet active
                step_completed = None
                step_started = None
                step_status = "in_progress"

            cursor.execute(
                "INSERT INTO steps (id, workflow_id, step_name, assignee, sla_hours, started_at, completed_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (step_id, workflow_id, step_name, assignee, sla_hours, step_started, step_completed, step_status),
            )

    conn.commit()
    conn.close()


def repair_data() -> None:
    """Normalize DB state to enforce Phase 2 invariants.

    - No step has status 'pending' (replace with 'in_progress')
    - Every workflow has exactly 1 active step (completed_at IS NULL)
    - Timestamps are recalculated relative to current time
    - Startup is clean: no overdue active steps
    """
    conn = get_connection()
    cursor = conn.cursor()

    allowed_active = ("in_progress",)
    allowed_all = ("in_progress", "completed", "stalled", "breached")
    now = datetime.utcnow()

    # ---- 0. Normalize workflow statuses to canonical distribution ----
    canonical_statuses = ["on_track"] * 15
    ordered_wfs = cursor.execute("SELECT id FROM workflows ORDER BY created_at").fetchall()
    for i, wf in enumerate(ordered_wfs):
        if i < len(canonical_statuses):
            cursor.execute(
                "UPDATE workflows SET status = ? WHERE id = ?",
                (canonical_statuses[i], wf["id"]),
            )

    # Clean demo startup: clear unresolved historical escalations.
    cursor.execute(
        "UPDATE escalations SET resolved_at = ? WHERE resolved_at IS NULL",
        (now.isoformat(),),
    )

    # ---- 1. Normalize step statuses ----
    cursor.execute("UPDATE steps SET status = 'in_progress' WHERE status = 'pending'")
    cursor.execute("UPDATE steps SET status = 'in_progress' WHERE completed_at IS NULL AND status IN ('stalled', 'breached')")
    cursor.execute("UPDATE workflows SET status = 'on_track' WHERE status IN ('stalled', 'breached', 'duplicate_hold', 'escalated')")
    cursor.execute(
        "UPDATE steps SET status = 'in_progress' "
        "WHERE completed_at IS NULL AND status NOT IN (?, ?, ?, ?)",
        allowed_all,
    )
    cursor.execute(
        "UPDATE steps SET status = 'completed' "
        "WHERE completed_at IS NOT NULL AND status != 'completed'"
    )

    # ---- 2. Enforce exactly 1 active step per workflow ----
    workflow_ids = [row[0] for row in cursor.execute("SELECT id FROM workflows").fetchall()]

    for wf_id in workflow_ids:
        active_steps = cursor.execute(
            "SELECT id, rowid, started_at FROM steps "
            "WHERE workflow_id = ? AND completed_at IS NULL AND status IN (?) "
            "ORDER BY datetime(COALESCE(started_at, '1970-01-01T00:00:00')) DESC, rowid DESC",
            (wf_id, *allowed_active),
        ).fetchall()

        if len(active_steps) == 0:
            last_step = cursor.execute(
                "SELECT id FROM steps WHERE workflow_id = ? "
                "ORDER BY datetime(COALESCE(started_at, '1970-01-01T00:00:00')) DESC, rowid DESC LIMIT 1",
                (wf_id,),
            ).fetchone()
            if last_step:
                cursor.execute(
                    "UPDATE steps SET completed_at = NULL, status = 'in_progress', "
                    "started_at = COALESCE(started_at, ?) WHERE id = ?",
                    ((now - timedelta(hours=1)).isoformat(), last_step[0]),
                )
                cursor.execute(
                    "UPDATE steps SET completed_at = ?, status = 'completed' "
                    "WHERE workflow_id = ? AND completed_at IS NULL AND id != ?",
                    (now.isoformat(), wf_id, last_step[0]),
                )
        elif len(active_steps) > 1:
            keep_id = active_steps[0]["id"]
            for step in active_steps[1:]:
                cursor.execute(
                    "UPDATE steps SET completed_at = ?, status = 'completed' WHERE id = ?",
                    (now.isoformat(), step["id"]),
                )
            cursor.execute(
                "UPDATE steps SET status = CASE WHEN status IN (?) THEN status ELSE 'in_progress' END "
                "WHERE id = ?",
                (*allowed_active, keep_id),
            )

    # ---- 3. Recalculate timestamps relative to now ----
    random.seed(99)
    all_workflows = cursor.execute("SELECT id FROM workflows ORDER BY created_at").fetchall()

    for wf in all_workflows:
        wf_id = wf["id"]
        steps = cursor.execute(
            "SELECT id FROM steps WHERE workflow_id = ? ORDER BY rowid",
            (wf_id,),
        ).fetchall()

        active_row = cursor.execute(
            "SELECT id, status FROM steps "
            "WHERE workflow_id = ? AND completed_at IS NULL AND status IN (?) "
            "ORDER BY datetime(COALESCE(started_at, '1970-01-01T00:00:00')) DESC, rowid DESC LIMIT 1",
            (wf_id, *allowed_active),
        ).fetchone()
        if not active_row:
            continue
        active_id = active_row["id"]

        for i, step in enumerate(steps):
            sla = random.choice([12, 18, 24])
            if step["id"] == active_id:
                # Keep active steps safely within SLA at startup.
                started_at = (now - timedelta(hours=random.randint(1, 3))).isoformat()
                cursor.execute(
                    "UPDATE steps SET started_at = ?, completed_at = NULL, sla_hours = ?, "
                    "status = CASE WHEN status IN (?) THEN status ELSE 'in_progress' END "
                    "WHERE id = ?",
                    (started_at, sla, *allowed_active, step["id"]),
                )
            else:
                start_offset = (len(steps) - i) * 28 + random.randint(1, 8)
                started_dt = now - timedelta(hours=start_offset)
                duration = random.randint(1, max(1, sla - 1))
                completed_dt = started_dt + timedelta(hours=duration)
                if completed_dt >= now:
                    completed_dt = now - timedelta(minutes=random.randint(5, 120))

                cursor.execute(
                    "UPDATE steps SET started_at = ?, completed_at = ?, sla_hours = ?, status = 'completed' WHERE id = ?",
                    (started_dt.isoformat(), completed_dt.isoformat(), sla, step["id"]),
                )

    # ---- 4. Ensure zero overdue active steps at startup ----
    overdue_count = cursor.execute(
        "SELECT COUNT(*) FROM steps "
        "WHERE completed_at IS NULL AND status IN (?) "
        "AND datetime(started_at, '+' || sla_hours || ' hours') < datetime('now')",
        allowed_active,
    ).fetchone()[0]

    if overdue_count > 0:
        rows = cursor.execute(
            "SELECT id, sla_hours FROM steps "
            "WHERE completed_at IS NULL AND status IN (?) "
            "AND datetime(started_at, '+' || sla_hours || ' hours') < datetime('now') "
            "ORDER BY datetime(started_at) ASC",
            allowed_active,
        ).fetchall()
        for row in rows:
            safe_hours = max(1, int((row["sla_hours"] or 12) // 2))
            cursor.execute(
                "UPDATE steps SET started_at = ? WHERE id = ?",
                ((now - timedelta(hours=safe_hours)).isoformat(), row["id"]),
            )

    # ---- 5. Ensure at least 5 active in_progress steps ----
    in_prog = cursor.execute(
        "SELECT COUNT(*) FROM steps WHERE completed_at IS NULL AND status = 'in_progress'"
    ).fetchone()[0]
    if in_prog < 5:
        candidates = cursor.execute(
            "SELECT id FROM steps "
            "WHERE completed_at IS NULL AND status IN ('stalled', 'breached') "
            "ORDER BY datetime(started_at) DESC LIMIT ?",
            (5 - in_prog,),
        ).fetchall()
        for c in candidates:
            cursor.execute("UPDATE steps SET status = 'in_progress' WHERE id = ?", (c[0],))

    # ---- 6. Final sweep ----
    cursor.execute("UPDATE steps SET status = 'in_progress' WHERE status = 'pending'")

    conn.commit()
    conn.close()
