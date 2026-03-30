# Workflow Autopsy

[![Repository](https://img.shields.io/badge/GitHub-mugenkyou%2FWorkflow--Autopsy-blue?logo=github)](https://github.com/mugenkyou/Workflow-Autopsy)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An automated detection, diagnosis, and recovery system for stalled enterprise workflows.

## Overview

Workflow Autopsy continuously monitors workflow operations (such as Purchase-to-Pay pipelines), flags stalled states or SLA breaches, diagnoses root causes, and executes policy-mapped recovery actions. By decoupling LLM-assisted diagnosis from deterministic execution policies, it ensures all recovery actions remain safe, compliant, and auditable.

---

## Key Features

- **Stall Detection:** Scans workflow databases for overdue tasks or SLA violations.
- **LLM-Assisted Diagnosis:** Uses local LLMs (Mistral via Ollama) to analyze contextual signals and classify root causes with confidence scoring.
- **Deterministic Recovery:** Maps classified root causes directly to predefined operational policies (e.g., rerouting approvals, retrying payments). The LLM does not have direct execution privileges.
- **Dynamic Risk Scoring:** Prioritizes active issues using financial risk metrics and SLA urgency.
- **Traceable Auditing:** Logs every detection, diagnosis reasoning, and corrective action in a central database.
- **Pattern Learning:** Aggregates historical stall data to optimize triage logic and future diagnosis context.

---

## System Architecture

The issue resolution cycle follows a linear, predictable sequence:

```
[Monitor] ──> [Diagnose] ──> [Action] ──> [Audit] ──> [Learn]
```

1. **Monitor:** Scans database, identifies stalled items, and ranks them by risk.
2. **Diagnose:** Classifies the issue type using contextual LLM prompting.
3. **Action:** Executes the predefined, policy-safe recovery action.
4. **Audit:** Records the decision history, reasoning, and result.
5. **Learn:** Updates historical stall patterns to optimize future triage.

For detailed design notes, see [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/system-architecture.md](docs/system-architecture.md).

---

## Setup Instructions

### Prerequisites

Workflow Autopsy uses a local [Ollama](https://ollama.com) server running the `mistral` model for diagnosis.

1. Download and install [Ollama](https://ollama.com/download).
2. Start Ollama and verify it is running on `http://localhost:11434`.
3. Pull the required model:
   ```bash
   ollama pull mistral
   ```

### 1. Install Dependencies

**Backend:**
```bash
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend-react
npm install
cd ..
```

### 2. Start the Backend

```bash
cd backend
python -m uvicorn main:app --host localhost --port 8000 --reload
```

### 3. Start the Frontend

In a separate terminal:
```bash
cd frontend-react
npm run dev
```

### 4. Open the Dashboard

Navigate to the local URL displayed by the Vite frontend (usually `http://localhost:5173` or `http://localhost:5175`).

---

## How to Demo

1. Open the React Dashboard and verify current workflows are running.
2. Click **Break It** to inject workflow disruptions (stalls, SLA breaches, etc.).
3. Observe how issues are prioritized in the **Risk Queue** and visualized on the workflow heatmap.
4. Watch the **Audit Trail** update in real time as issues cycle through detection, diagnosis, and automated resolution.
5. Inspect the **Stall Learning** tab to see aggregated historical patterns.

---

## Troubleshooting & Utilities

### Resetting the Database
To clear the state and start fresh:
```bash
# macOS/Linux/Git Bash
rm backend/autopsy.db

# Windows PowerShell
Remove-Item backend/autopsy.db -ErrorAction SilentlyContinue
```
*Note: The backend will automatically recreate and seed the database on restart.*

### Stopping the Backend
To completely shut down the backend and free port `8000`:
- **Linux/macOS:** Kill the uvicorn process or run `kill $(lsof -t -i:8000)`.
- **Windows (PowerShell):**
  ```powershell
  Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess -Force
  ```

---

## Project Structure

```text
Workflow-Autopsy/
├── ARCHITECTURE.md
├── LICENSE
├── README.md
├── requirements.txt
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
└── tests/
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
