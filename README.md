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

### 1. Install dependencies

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

### 2. Run backend

```bash
cd backend
python -m uvicorn main:app --host localhost --port 8000 --reload
```

### 3. Run frontend

In a second terminal:

```bash
cd frontend-react
npm run dev
```

### 4. Open dashboard

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
