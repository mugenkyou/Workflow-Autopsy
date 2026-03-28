#!/usr/bin/env python3
"""Inject test failures into the database for system validation."""

import sys
from pathlib import Path
import uuid
from datetime import datetime, timedelta

from db import get_connection

def inject_failures():
    """Inject diverse test failures to trigger varied diagnoses and actions."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Clear previous test data
    cur.execute("DELETE FROM workflows WHERE name LIKE 'TEST-%'")
    conn.commit()
    
    failures = [
        {
            "name": "TEST-LongApproval",
            "vendor": "VendorA",
            "po_amount": 50000,
            "step_name": "Manager Approval",
            "assignee": "Rohit Sharma",
            "hours_overdue": 15,  # >10 → wrong_approver
            "sla_hours": 4
        },
        {
            "name": "TEST-ShortApproval",
            "vendor": "VendorB",
            "po_amount": 30000,
            "step_name": "Finance Approval",
            "assignee": "Priya Patel",
            "hours_overdue": 1.5,  # <3 → missing_data
            "sla_hours": 4
        },
        {
            "name": "TEST-LongPayment",
            "vendor": "VendorC",
            "po_amount": 75000,
            "step_name": "Payment Processing",
            "assignee": "Raj Kumar",
            "hours_overdue": 8,  # >6 → external_hold
            "sla_hours": 6
        },
        {
            "name": "TEST-ShortPayment",
            "vendor": "VendorD",
            "po_amount": 20000,
            "step_name": "Payment Processing",
            "assignee": "Amit Kulkarni",
            "hours_overdue": 2,  # <6 → missing_data
            "sla_hours": 6
        },
        {
            "name": "TEST-Invoice",
            "vendor": "VendorE",
            "po_amount": 45000,
            "step_name": "Invoice Verification",
            "assignee": "Aarav Sharma",
            "hours_overdue": 2,  # <3 → missing_data
            "sla_hours": 3
        },
        {
            "name": "TEST-VeryLongApproval",
            "vendor": "VendorF",
            "po_amount": 100000,
            "step_name": "Director Approval",
            "assignee": "Nikita Singh",
            "hours_overdue": 25,  # Very long > 10 → strong wrong_approver
            "sla_hours": 4
        },
    ]
    
    for i, f in enumerate(failures):
        workflow_id = str(uuid.uuid4())
        step_id = str(uuid.uuid4())
        
        # Create workflow
        created_at = datetime.now() - timedelta(hours=f["hours_overdue"] + 2)
        cur.execute("""
            INSERT INTO workflows (id, name, vendor, po_amount, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (workflow_id, f["name"], f["vendor"], f["po_amount"], "stalled", 
              created_at.isoformat()))
        
        # Create step (started but not completed)
        step_started = created_at + timedelta(hours=1)
        cur.execute("""
            INSERT INTO steps (id, workflow_id, step_name, status, assignee, sla_hours, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (step_id, workflow_id, f["step_name"], "in_progress", f["assignee"], 
              f["sla_hours"], step_started.isoformat()))
        
        print(f"✓ Injected: {f['name']:25s} {f['step_name']:25s} Assignee: {f['assignee']:15s} ({f['hours_overdue']:5.1f}h overdue)")
    
    conn.commit()
    conn.close()
    
    print(f"\n✓ Total: {len(failures)} test failures injected")
    print("\nReady to run:")
    print("  python -c \"from backend.agents.graph import run_cycle; run_cycle()\"")
    print("\nOr run API tests:")
    print("  python tests/test_api.py")

if __name__ == "__main__":
    inject_failures()
