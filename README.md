# Process Autopsy Agent

Real-time multi-agent workflow management for stalled purchase order operations.

The platform detects workflow friction, diagnoses root causes, applies deterministic corrective actions, and records every intervention for auditability. It is built with FastAPI, LangGraph, React/Vite, SQLite, and local Ollama (mistral).

---

## Overview

- Backend API: FastAPI on localhost:8000
- Frontend dashboard: React/Vite on localhost:5175
- Orchestration: Monitor -> Diagnosis -> Action -> Audit
- Data store: SQLite (backend/autopsy.db)
- Inference: Ollama mistral (local)

### Architecture Docs

- [docs/system-architecture.md](docs/system-architecture.md)
- [docs/component-diagram.mmd](docs/component-diagram.mmd)
- [docs/workflow-sequence.mmd](docs/workflow-sequence.mmd)

---

## Getting Started

### Prerequisites

- Python 3.x
- Node.js and npm
- Ollama installed with mistral model

### Backend

```bash
cd backend
pip install -r ../requirements.txt
python -m uvicorn main:app --host localhost --port 8000 --reload
```

### Frontend

```bash
cd frontend-react
npm install
npm run dev
```

---

## Core Capabilities

- Real-time workflow monitoring and risk ranking
- Autonomous issue resolution with deterministic action mapping
- Solved issues tracking with intervention details
- Human-in-the-loop escalation review path
- Break It and Stop Agent controls for demo operations
- Audit transparency with reasoning and confidence logs

---

## API Endpoints

| Endpoint | Method | Purpose |
| --- | --- | --- |
| /health | GET | Service health and model status |
| /workflows | GET | Current workflow state with active step |
| /active-issues | GET | Ranked active issues and total risk exposure |
| /audit-log | GET | Recent intervention audit records |
| /stall-patterns | GET | Learned bottleneck patterns |
| /escalations | GET | Open escalation queue |
| /inject-chaos | POST | Inject 3 demo failures |
| /run-cycle | POST | Execute one orchestration cycle |
| /mark-resolved | POST | Mark escalation as reviewed |
| /stop-agent | POST | Stop active agent processing |

---

## System Demo Flow

1. Start backend and frontend services.
2. Open dashboard at http://localhost:5175.
3. Click Break It to inject controlled failures.
4. Observe issues in Risk Queue and interventions in Audit Trail.
5. Wait for automatic resolution cycle.
6. Open Solved Issues to review intervention outcomes.

---

## Data Model

- workflows: Business workflow headers and overall status
- steps: Per-workflow lifecycle steps with SLA and timestamps
- audit_log: Intervention action, reasoning, confidence, timestamp
- stall_patterns: Aggregated behavior signals
- escalations: Human review queue with resolution timestamps

---

## Troubleshooting

### Backend does not start

```bash
python -c "import fastapi, uvicorn, langgraph, ollama"
netstat -ano | findstr :8000
taskkill /IM python.exe /F
```

### Frontend cannot reach backend

- Verify health endpoint: http://localhost:8000/health
- Verify API base URL in frontend-react/src/api/client.js
- Check browser network and console logs

### Reset local database

```bash
rm backend/autopsy.db
```

Restart backend after deletion to recreate state.

---

## Testing

### API Smoke Check

```bash
curl http://localhost:8000/health
curl http://localhost:8000/workflows
```

### Stop Backend Completely (Windows PowerShell)

```powershell
try { Invoke-RestMethod -Method Post -Uri "http://localhost:8000/stop-agent" | Out-Null } catch {}; (@(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique) + @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*process-autopsy-agent*backend*" } | Select-Object -ExpandProperty ProcessId)) | Select-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
```

### One-Time Backend Injection Test (Windows PowerShell)

Backend must be running on localhost:8000.

```powershell
$base = "http://localhost:8000"; Invoke-RestMethod -Method Post -Uri "$base/stop-agent" | Out-Null; $inject = Invoke-RestMethod -Method Post -Uri "$base/inject-chaos"; $cycle = Invoke-RestMethod -Method Post -Uri "$base/run-cycle"; $issues = Invoke-RestMethod -Method Get -Uri "$base/active-issues"; $audit = Invoke-RestMethod -Method Get -Uri "$base/audit-log"; "Injected failures: $($inject.failures_injected.Count) | Issues processed in one cycle: $($cycle.issues_processed) | Remaining active issues: $($issues.issues.Count) | Audit entries written: $($audit.Count)"
```

### Test Suite

```bash
python tests/test_api.py
```

---

## Project Structure

```text
process-autopsy-agent/
├── backend/
│   ├── main.py
│   ├── db.py
│   ├── graph.py
│   ├── agents/
│   └── autopsy.db
├── docs/
│   ├── system-architecture.md
│   ├── component-diagram.mmd
│   └── workflow-sequence.mmd
├── frontend-react/
│   ├── src/
│   └── package.json
├── tests/
│   └── test_api.py
└── requirements.txt
```

---

## Latest UX Update

- Solved issue drawer is presented as System Intervention.
- Intervention view highlights Cause, System Impact, and Outcome.
- Status badge is shown as Auto-fixed, Waiting on user, or Escalated.
- Confidence is displayed as a percentage when present in audit data.
