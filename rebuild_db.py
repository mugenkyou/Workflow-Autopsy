#!/usr/bin/env python3
"""Quick script to rebuild and verify the database."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import get_connection, init_db, seed_data, repair_data

print("Rebuilding database...")
init_db()
seed_data()
repair_data()

conn = get_connection()
cur = conn.cursor()

# Verify counts
wf_count = cur.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
steps_count = cur.execute("SELECT COUNT(*) FROM steps").fetchone()[0]
audit_count = cur.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

conn.close()

print(f"✓ Database rebuilt successfully!")
print(f"  Workflows: {wf_count}")
print(f"  Steps: {steps_count}")
print(f"  Audit log entries: {audit_count}")

if wf_count == 15:
    print("\n✓ Database is ready!")
    print("\nTo see the dashboard:")
    print("  1. Stop the API server (Ctrl+C in uvicorn terminal)")
    print("  2. Start it again: uvicorn main:app --reload --port 8000")
    print("  3. Refresh the dashboard in your browser")
else:
    print(f"\n✗ ERROR: Expected 15 workflows, got {wf_count}")
