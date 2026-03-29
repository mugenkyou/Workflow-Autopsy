# Process Autopsy Agent - Autonomous Workflow Recovery System

Autonomous detection, diagnosis, and recovery for disrupted enterprise workflows.

## Overview

Process Autopsy Agent continuously monitors workflow operations, detects disruptions, classifies root causes, applies deterministic recovery actions, and records every decision for traceability. The platform combines agentic orchestration with LLM-assisted diagnosis while keeping execution policy deterministic and auditable. It is designed for live operational demos and practical workflow resilience use cases where consistency, explainability, and response speed matter.

## Key Capabilities

- Autonomous issue detection from workflow state and SLA timing signals
- LLM-based diagnosis for root-cause classification
- Deterministic recovery actions mapped to diagnosis categories
- Financial risk prioritization using dynamic risk scoring
- Full audit trail with reasoning and confidence scoring
- Learning loop from past disruptions through stall pattern aggregation

## System Architecture

The runtime path is intentionally linear and auditable:

Monitor -> Diagnosis -> Action -> Audit -> Learning

Monitor identifies active disruptions. Diagnosis classifies probable causes and confidence. Action executes deterministic remediation (no free-form LLM control over execution). Audit writes a durable decision log. Learning updates historical stall patterns for future prioritization and diagnosis quality.

For full technical detail, see [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/system-architecture.md](docs/system-architecture.md).

## How It Works

1. Detect issue in active workflow state.
2. Diagnose cause using contextual classification.
3. Execute deterministic fix based on policy mapping.
4. Log decision, confidence, and action result.
5. Learn pattern signals from observed disruptions.

## Demo Features

- Break It control to inject realistic workflow disruptions
- Live audit feed showing diagnosis, action, and audit events
- Risk-priority queue of active disruptions
- Workflow heatmap for visual operational status
- Stall learning panel for historical behavior insights

## Tech Stack

- Backend: FastAPI, SQLite, LangGraph
- Frontend: React + Tailwind-oriented UI structure (with component CSS styling)
- LLM: Mistral via local Ollama endpoint

## Setup Instructions

### 1. Install and prepare Ollama (required for DiagnosisAgent)

This project uses a local Ollama server with the `mistral` model for diagnosis.

1. Install Ollama: https://ollama.com/download
2. Start Ollama (it should run on `http://localhost:11434`)
3. Pull the required model:

```bash
ollama pull mistral
```

Optional quick check:

```bash
ollama run mistral "Say hello"
```

### 2. Install dependencies

Backend dependencies:

```bash
pip install -r requirements.txt
```

Frontend dependencies:

```bash
cd frontend-react
npm install
cd ..
```

### 3. Run backend

```bash
cd backend
python -m uvicorn main:app --host localhost --port 8000 --reload
```

### 4. Run frontend

In a second terminal:

```bash
cd frontend-react
npm run dev
```

### 5. Open dashboard

Navigate to http://localhost:5175

## How to Demo

1. Open the dashboard and confirm baseline workflows are stable.
2. Click Break It to inject disruptions.
3. Observe Risk Queue prioritization and heatmap changes.
4. Watch live Audit Trail updates (diagnosis -> action -> audit).
5. Observe system-driven recovery and learning signal updates.

## Example Output

```text
2026-03-29T02:31:37Z | DiagnosisAgent | classified:reroute_approver
Rohit Sharma has 12.0h delay on Finance Approval; approval routing friction detected -> reassigned to alternate approver.
confidence=0.78

2026-03-29T02:31:37Z | ActionAgent | reroute_approver
Executed corrective action (workflow_123 / step_456).

2026-03-29T02:31:37Z | AuditAgent | audit_recorded
Captured lifecycle record (workflow_123 / step_456).
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
├── ARCHITECTURE.md
├── DEMO.md
├── LICENSE
├── README.md
├── backend/
│   ├── main.py
│   ├── graph.py
│   ├── db.py
│   └── agents/
├── frontend-react/
│   ├── package.json
│   └── src/
├── docs/
│   ├── system-architecture.md
│   ├── component-diagram.mmd
│   └── workflow-sequence.mmd
├── tests/
└── requirements.txt
```

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
