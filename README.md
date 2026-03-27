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

| Method | Endpoint          | Description                                                            |
| ------ | ----------------- | ---------------------------------------------------------------------- |
| `GET`  | `/health`         | Returns `{"status":"ok","model":"mistral"}`                            |
| `GET`  | `/workflows`      | Returns all 15 workflows with their current step                       |
| `GET`  | `/audit-log`      | Returns last 50 audit log entries (newest first)                       |
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

| Table            | Purpose                                         |
| ---------------- | ----------------------------------------------- |
| `workflows`      | Purchase orders with vendor, amount, and status |
| `steps`          | Individual P2P steps linked to workflows        |
| `audit_log`      | Agent action history                            |
| `stall_patterns` | Detected approval bottleneck patterns           |
| `escalations`    | Escalation packets for stalled workflows        |

---

## Phase 2 — Monitor & Diagnosis Agents

Phase 2 adds autonomous failure detection and root-cause classification using a local LLM.

### Architecture

- **MonitorAgent** — Queries overdue in-progress steps, computes risk scores, classifies failure types
- **DiagnosisAgent** — Calls local Ollama (mistral) to classify stall root causes (missing_data, wrong_approver, duplicate_invoice, amount_variance, external_hold)
- **Runner** — Orchestrates continuous or one-off Monitor→Diagnosis cycles

### Setup

Ensure Ollama is running locally:

```bash
# In a separate terminal, start Ollama
ollama run mistral
```

Ensure backend is running (Phase 1):

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Run Agent Loop

**Continuous mode** (runs every 30 seconds):

```bash
python backend/agents/runner.py
```

**Single cycle** (runs once and exits):

```bash
python backend/agents/runner.py --once
```

### Example Output

```
[2026-03-27 16:32:49] ISSUE: adb05b5a-8586-4832-a96f-c6825b95aab0 | Payment Processing | ₹5722.17
[2026-03-27 16:32:49] Issues found: 4
ISSUE -> DIAGNOSIS | workflow_id=adb05b5a-8586-4832-a96f-c6825b95aab0 | step=Payment Processing | risk_score=5722.17 | stall_type=external_hold | confidence=0.50 | reasoning=Default fallback due to classification failure
```

### How It Works

1. **Monitor** scans the database for overdue steps (where `started_at + sla_hours < now`)
2. Each overdue step gets a **risk_score** = `hours_overdue × po_amount × 0.001`
3. Steps are classified by failure type:
   - "Approval" steps → `stall`
   - "Invoice" steps with duplicate detection → `duplicate`
   - Others → `sla_breach`
4. **Diagnosis** takes each issue and calls Ollama to determine the underlying cause:
   - Strict JSON-only prompt ensures valid responses
   - Retry logic (max 2 retries) on parse/validation failure
   - Fallback only after retries exhausted
   - Debug logging shows raw LLM output for inspection
5. Results are printed in a structured format for inspection or downstream processing

### Diagnosis Agent Features

- **Strict JSON enforcement** — Mistral responses are strictly validated as JSON
- **Smart retry logic** — Retries with stricter prompts before falling back
- **Debug output** — RAW LLM OUTPUT logged to stderr for troubleshooting
- **Pydantic validation** — All diagnosis results validated against schema
- **Allowed classifications** — `missing_data`, `wrong_approver`, `duplicate_invoice`, `amount_variance`, `external_hold`

---

## Phase 3 — Autonomous 4-Agent System (LangGraph)

Phase 3 upgrades orchestration to a full autonomous cycle:

- **MonitorAgent** — Finds overdue in-progress steps ordered by risk score
- **DiagnosisAgent** — Classifies root-cause type with validated JSON output
- **ActionAgent** — Executes deterministic database mutations per diagnosis
- **AuditAgent** — Writes one auditable record per processed issue

### Deterministic Action Mapping

- `wrong_approver` → `reroute_approver`
- `external_hold` → `escalate_sla`
- `duplicate_invoice` → `flag_duplicate`
- `missing_data` → `request_data`
- `amount_variance` → `auto_reject`

`ActionAgent` also updates learning signals in `stall_patterns` (upsert + sample_count/stall_rate/last_seen updates).

### Graph Flow

`monitor -> diagnosis -> action -> audit -> (loop until no issues) -> END`

Each issue produces:

- Exactly one action result
- Exactly one audit log entry (via `AuditAgent`)

The graph prints cycle observability to help demos and validation:

- `Total issues processed: <count>`

### Run Phase 3

From the `backend` directory:

```bash
python -c "from graph import run_cycle; import json; print(json.dumps(run_cycle(), indent=2))"
```

Or use the runner from project root:

```bash
python backend/agents/runner.py --once
```

Runner now executes the autonomous graph and prints pipeline/audit results.

### Runner Demo Output

Runner prints each processed issue in a readable pipeline format:

```text
ISSUE:
   Workflow: <id>
   Step: <step_name>
   Risk: <risk_score>

DIAGNOSIS:
   Type: <stall_type>
   Confidence: <confidence>
   Reason: <reasoning>

ACTION:
   Action: <action_taken>
   Result: <details>

--------------------------------------
```

---

## Testing

### Run Phase 1 Tests

```bash
# Ensure backend server is running
cd backend
uvicorn main:app --reload --port 8000
```

In another terminal:

```bash
python tests/test_api.py
```

**Expected output:** ✅ 10 passed, 0 failed

Phase 1 test coverage:

- ✅ `/health` endpoint returns correct JSON
- ✅ `/workflows` returns exactly 15 workflows
- ✅ All workflows have exactly 1 current_step
- ✅ No step has status 'pending'
- ✅ Status distribution: 3+ stalled, 3+ at_risk, 2+ breached, 7 on_track
- ✅ At least 5 workflows have in_progress current step
- ✅ `/audit-log` returns audit entries
- ✅ `/inject-failure` — stall fixture works
- ✅ `/inject-failure` — duplicate fixture works
- ✅ `/inject-failure` — sla_breach fixture works

### Database Reset

If the database gets corrupted or out of sync, rebuild it:

```bash
python -c "from backend.db import init_db, seed_data, repair_data; init_db(); seed_data(); repair_data(); print('Database restored')"
```

This ensures:

- All 15 workflows present with correct status distribution
- Exactly 1 active step per workflow
- No 'pending' statuses
- Dynamic timestamps (1-48 hours ago)
- Minimum 5 overdue steps for agent detection
