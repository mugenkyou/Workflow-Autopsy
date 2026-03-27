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
            created_at TEXT
        )
    """)

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

# Status distribution: indices 0-2 stalled, 3-5 at_risk, 6-7 breached, 8-14 on_track
WORKFLOW_STATUSES = (
    ["stalled"] * 3
    + ["at_risk"] * 3
    + ["breached"] * 2
    + ["on_track"] * 7
)


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
                # future step, not started
                step_completed = None
                step_started = None
                step_status = "pending"

            cursor.execute(
                "INSERT INTO steps (id, workflow_id, step_name, assignee, sla_hours, started_at, completed_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (step_id, workflow_id, step_name, assignee, sla_hours, step_started, step_completed, step_status),
            )

    conn.commit()
    conn.close()
