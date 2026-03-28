# Process Autopsy Agent

Process Autopsy Agent is a local-first autonomous workflow intelligence system for Procure-to-Pay (P2P) operations. It monitors active workflow steps, diagnoses likely root causes, executes deterministic corrective actions, and records a complete audit trail.

## What It Does

- Detects overdue in-progress workflow steps
- Computes risk scores for prioritization
- Classifies likely root cause using local Ollama (`mistral`)
- Applies deterministic corrective actions in SQLite
- Writes auditable action history to `audit_log`
- Learns recurring stall patterns in `stall_patterns`
- Produces cycle-level summary with operational and business impact

## Tech Stack

- Python 3.10+
- FastAPI
- SQLite
- Pydantic
- Requests
- LangGraph

## Project Structure

- `backend/main.py`: API server and endpoints
- `backend/db.py`: schema, seed, repair utilities
- `backend/graph.py`: autonomous orchestration and cycle summary
- `backend/agents/monitor.py`: issue detection and risk scoring
- `backend/agents/diagnosis.py`: diagnosis classification
- `backend/agents/action.py`: deterministic action execution
- `backend/agents/audit.py`: audit persistence
- `backend/agents/runner.py`: CLI runner for full cycle
- `tests/test_api.py`: API and data integrity checks

## Setup

```bash
pip install -r requirements.txt
```

Start the backend API:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

If using diagnosis and escalation generation, start Ollama in another terminal:

```bash
ollama run mistral
```

## API Endpoints

- `GET /health`: service health status
- `GET /workflows`: all workflows with current step
- `GET /audit-log`: latest audit log records
- `POST /inject-failure`: inject `stall`, `duplicate`, or `sla_breach`
- `POST /run-cycle`: execute one autonomous cycle and return audit entries

## Live Dashboard

Open the real-time dashboard with live polling and agent activity feed:

```bash
# Ensure API server is running on port 8000
frontend/index.html
```

Or open directly in your browser:
```
file:///path/to/process-autopsy-agent/frontend/index.html
```

**Dashboard features:**
- **Audit Trail** (left panel): Complete audit log with agent badges, timestamps, confidence scores
- **Agent Feed** (right panel): Real-time stream of agent actions with LIVE indicator
- **Auto-polling**: Updates every 3-5 seconds without page refresh
- **Auto-cycle**: Runs autonomous cycle every 30 seconds
- Responsive dark-themed UI built with React (CDN) + Tailwind

## Run Autonomous Cycle

From the project root:

```bash
python backend/agents/runner.py --once
```

Or run graph directly from `backend`:

```bash
python -c "from graph import run_cycle; import json; print(json.dumps(run_cycle(), indent=2))"
```

## Inject Test Failures

To test the system with diverse stalled workflows:

```bash
cd backend
python inject_failures.py
```

This injects 6 diverse test scenarios:

1. **TEST-LongApproval** (15h) → triggers `wrong_approver` diagnosis
2. **TEST-ShortApproval** (1.5h) → triggers `missing_data` diagnosis
3. **TEST-LongPayment** (8h) → triggers `external_hold` diagnosis
4. **TEST-ShortPayment** (2h) → triggers `missing_data` diagnosis
5. **TEST-Invoice** (2h) → triggers `missing_data` diagnosis
6. **TEST-VeryLongApproval** (25h) → triggers `wrong_approver` diagnosis (strong signal)

Then run the autonomous cycle:

```bash
python agents/runner.py --once
```

Expected output: 6 issues processed with diverse diagnoses and actions.

## Runtime Output

Per-issue pipeline output:

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

Cycle summary output includes:

- Issues processed
- Total risk handled
- Action distribution
- Top risk issue
- Average confidence
- Learning insights from `stall_patterns`
- Business impact interpretation

## Deterministic Action Mapping

- `wrong_approver` -> `reroute_approver`
- `external_hold` -> `escalate_sla`
- `duplicate_invoice` -> `flag_duplicate`
- `missing_data` -> `request_data`
- `amount_variance` -> `auto_reject`

## Testing

With API server running:

```bash
python tests/test_api.py
```

Expected result: `10 passed, 0 failed`

## Database Repair

If data state drifts, rebuild and repair:

```bash
python -c "from backend.db import init_db, seed_data, repair_data; init_db(); seed_data(); repair_data(); print('Database restored')"
```

## Notes

- No schema changes are required for normal operation.
- If no issues are detected in a cycle, the system prints a no-impact summary and exits cleanly.
