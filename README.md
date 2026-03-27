# Process Autopsy Agent

A local-first agentic system that simulates Procure-to-Pay (P2P) workflows and prepares for autonomous failure detection and recovery.

## Phase 1 — Foundation Backend

Phase 1 delivers a **FastAPI + SQLite** backend with realistic seed data, workflow tracking, and failure injection capabilities.

### Stack

- **Python 3.10+**
- **FastAPI** — async web framework
- **SQLite** — file-based, zero-config database (`autopsy.db`)
- **Pydantic** — request/response validation

### Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
cd backend
uvicorn main:app --reload --port 8000
```

The database and seed data (15 workflows) are created automatically on first startup.

### API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Returns `{"status":"ok","model":"mistral"}` |
| `GET` | `/workflows` | Returns all 15 workflows with their current step |
| `GET` | `/audit-log` | Returns last 50 audit log entries (newest first) |
| `POST` | `/inject-failure` | Injects a failure (`stall`, `duplicate`, `sla_breach`) into a workflow |

### Test Gates

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Workflows (expect 15 items)
curl http://localhost:8000/workflows

# 3. Audit log
curl http://localhost:8000/audit-log

# 4. Inject failure (replace <workflow_id> with a real ID from /workflows)
curl -X POST http://localhost:8000/inject-failure ^
  -H "Content-Type: application/json" ^
  -d "{\"workflow_id\":\"<workflow_id>\",\"failure_type\":\"stall\"}"
```

### Database Schema

| Table | Purpose |
|-------|---------|
| `workflows` | Purchase orders with vendor, amount, and status |
| `steps` | Individual P2P steps linked to workflows |
| `audit_log` | Agent action history |
| `stall_patterns` | Detected approval bottleneck patterns |
| `escalations` | Escalation packets for stalled workflows |
