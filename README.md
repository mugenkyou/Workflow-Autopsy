# Process Autopsy Agent — Phase 7.5 ✓ STABLE

**Full System Stabilization Complete — 2026-03-28**

A multi-agent system for detecting, diagnosing, and resolving stalled purchase order workflows in real-time. Built with **FastAPI**, **LangGraph**, **React/Vite**, and local **Ollama** (mistral).

---

## System Architecture

### Backend (FastAPI + LangGraph)
- **Port**: 8000 (localhost)
- **Database**: SQLite with 15 workflows
- **Agents**: Monitor → Diagnosis → Action → Audit (autonomous 4-agent pipeline)
- **Model**: Ollama mistral (local inference, no cloud calls)

### Frontend (React + Vite)
- **Port**: 5175 (or next available)
- **Components**: WorkflowHeatmap, RiskQueue, AuditTrail, EscalationPreview, StallInsights
- **Polling**: 3-10s intervals for real-time updates
- **Status**: ✓ Fully functional

### Key Endpoints (All Operational ✓)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | System health check |
| `/workflows` | GET | All 15 workflows with current steps |
| `/active-issues` | GET | Risk-ranked issues (highest first) |
| `/audit-log` | GET | Agent action history (last 50) |
| `/escalations` | GET | Unresolved escalations for human review |
| `/stall-patterns` | GET | Learned bottleneck patterns |
| `/inject-chaos` | POST | Inject 3 random failures for demo |
| `/run-cycle` | POST | Execute one agent cycle manually |
| `/mark-resolved` | POST | Mark escalation as reviewed |

---

## Getting Started

### Prerequisites
- Python 3.x (Anaconda recommended)
- Node.js + npm
- Ollama running locally with `mistral` model
- 2-3 GB disk space

### Backend Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Install dependencies
pip install -r ../requirements.txt

# 3. Start server (choose one):

# Option A: Development with hot-reload
python -m uvicorn main:app --host localhost --port 8000 --reload

# Option B: Production (recommended)
python -m uvicorn main:app --host localhost --port 8000
```

Backend will:
- Initialize SQLite database (`autopsy.db`)
- Seed 15 workflows
- Repair state invariants
- Start accepting requests

### Frontend Setup

```bash
# 1. Navigate to frontend
cd frontend-react

# 2. Install dependencies
npm install

# 3. Start dev server
npm run dev

# Opens at http://localhost:5175 (or next available port)
```

---

## System Demo

### 1. Dashboard (Default State)
- **WorkflowHeatmap**: 15 workflow cards (color-coded by status: green=on_track, amber=at_risk, red=breached/stalled)
- **RiskQueue**: Empty (no active issues yet)
- **AuditTrail**: Shows initialization events
- **StallInsights**: Empty (no patterns learned yet)

### 2. Inject Failures (Click "⚡ Break It")
```bash
# Or via API:
curl -X POST http://localhost:8000/inject-chaos
```

**What happens:**
- 3 random failures injected (stall, duplicate, sla_breach)
- Failures visible in RiskQueue within seconds
- Heatmap updates to show affected workflows
- Audit trail logs injection event

### 3. Auto-Resolution (~30s)
- Agents detect failures
- DiagnosisAgent classifies root cause
- ActionAgent proposes resolution
- AuditAgent logs decision
- Issues resolve gracefully
- Metrics accumulate in StallInsights

### 4. Human Escalations
- Critical issues escalate to EscalationPreview
- Human reviews and marks resolved
- System learns from decisions

---

## Database Schema

### Tables
- **workflows**: 15 PO workflows with vendor, amount, status
- **steps**: 60+ process steps (Invoice, Approval, Payment, etc.)
- **audit_log**: Agent actions, reasoning, confidence scores
- **stall_patterns**: Learned behavioral patterns by approver
- **escalations**: Human-reviewed decisions

### State Invariants
- ✓ Each workflow has exactly 1 active step
- ✓ Steps have SLA (12-96 hours)
- ✓ Overdue steps detected automatically
- ✓ Status distribution: 3 stalled, 3 at_risk, 2 breached, 7 on_track

---

## Agents

### 1. Monitor Agent
- Detects overdue in-progress steps
- Classifies failure type (stall, duplicate, sla_breach)
- Computes risk scores (hours_overdue × po_amount × 0.001)
- Returns sorted list of issues

### 2. Diagnosis Agent  
- Fine-tunes reasoning based on issue context
- Adjusts confidence dynamically (0.6-0.9)
- Generates explanation with variance
- Selects override policy if appropriate

### 3. Action Agent
- Implements escalation logic
- Creates audit trail entry
- Marks escalation in database
- Logs reasoning and confidence

### 4. Audit Agent
- Records all agent decisions
- Stores confidence metrics
- Enables process transparency
- Feeds data for pattern learning

---

## API Examples

### Get All Workflows
```bash
curl http://localhost:8000/workflows
# Returns: [{ id, name, vendor, po_amount, status, current_step, ... }, ...]
```

### Get Active Issues (Risk-Ranked)
```bash
curl http://localhost:8000/active-issues
# Returns: { success, issues: [...], total_risk_exposure }
```

### Inject Chaos
```bash
curl -X POST http://localhost:8000/inject-chaos
# Returns: { success, message, failures_injected, audit_entries }
```

### Get Audit Log
```bash
curl http://localhost:8000/audit-log
# Returns: Last 50 agent actions with timestamps
```

---

## Troubleshooting

### Backend won't start
```bash
# Check Python/dependencies
python -c "import fastapi, uvicorn, langgraph, ollama"

# Check port
netstat -ano | findstr :8000

# Kill old processes
taskkill /IM python.exe /F
```

### React app can't reach API
- Verify backend is running: `curl http://localhost:8000/health`
- Check API base URL in `frontend-react/src/api/client.js` points to `http://localhost:8000`
- Check browser console for CORS errors
- Verify firewall allows localhost:8000

### Database corruption
```bash
# Delete bad database and let system recreate it
rm backend/autopsy.db
# Restart backend
```

### Ollama not responding
```bash
# Verify ollama service
ollama pull mistral
ollama serve
```

---

## Project Structure

```
process-autopsy-agent/
├── backend/
│   ├── main.py              # FastAPI server + endpoints
│   ├── db.py                # SQLite management
│   ├── graph.py             # LangGraph 4-agent pipeline
│   ├── agents/
│   │   ├── monitor.py       # Issue detection
│   │   ├── diagnosis.py     # Root cause analysis
│   │   ├── action.py        # Resolution actions
│   │   └── audit.py         # Decision logging
│   └── autopsy.db           # SQLite database
├── frontend-react/
│   ├── src/
│   │   ├── App.jsx          # Main component + polling logic
│   │   ├── components/      # Heatmap, RiskQueue, AuditTrail, etc.
│   │   └── api/client.js    # Axios API client
│   ├── vite.config.js       # Vite configuration
│   └── package.json         # Dependencies
├── requirements.txt         # Python dependencies
├── README.md               # This file
└── .gitignore
```

---

## Recent Changes (Phase 7.5)

✓ **Fixed /workflows endpoint** — Now gracefully handles DB state variations
✓ **Removed legacy HTML frontend** — Eliminated duplicate UI system
✓ **Verified all endpoints** — All 8 endpoints return 200 OK
✓ **Stabilized backend** — Smooth 30-second cycle with visible demo flow
✓ **React app functional** — Real-time polling on all panels
✓ **Database clean state** — 15 workflows, 15 active steps, proper invariants
✓ **Updated requirements.txt** — Pinned versions for reproducibility

---

## Next Steps (Phase 8+)

- [ ] Add user authentication/session management
- [ ] Implement persistent decision logging for ML training
- [ ] Build admin dashboards for pattern review
- [ ] Add email/Slack notifications for escalations
- [ ] Scale to 100+ workflows
- [ ] Add time-travel debugging (replay cycles)

---

## Testing

### Manual Test Flow
1. Open `http://localhost:5175` in browser
2. Verify dashboard loads with 15 workflow cards
3. Click "⚡ Break It" button
4. Wait 2-5 seconds for RiskQueue to populate
5. Watch AuditTrail update with agent actions
6. Wait ~30 seconds for auto-resolution
7. Verify heatmap returns to original state

### API Test
```bash
curl http://localhost:8000/health
# {"status":"ok","model":"mistral"}

curl http://localhost:8000/workflows | grep -o '"id"' | wc -l
# Should output: 15
```

---

## License & Attribution

Built as Phase 7.5 of Process Autopsy Agent prototype system.
Model: Ollama mistral (local inference)
Frameworks: FastAPI, LangGraph, React, Vite

---

**System Status**: ✓ FULLY OPERATIONAL
**Last Updated**: 2026-03-28
**Tested Endpoints**: 8/8 ✓
**Database State**: CLEAN (15 workflows, 15 active steps)

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
- `GET /active-issues`: all overdue issues ranked by risk_score (Phase 6)
- `POST /inject-failure`: inject `stall`, `duplicate`, or `sla_breach`
- `POST /inject-chaos`: inject 3 random failures and run cycle (Phase 6)
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

**Dashboard features (Phase 5 + Phase 6):**

- **Workflow Heatmap** (left 60%):
  - Responsive grid of all 15 workflows (3 cols desktop, 2 tablet, 1 mobile)
  - Color-coded status badges (green=on_track, amber=at_risk, red=stalled/breached)
  - Left border indicator for risk levels
  - Progress bar showing current step
  - Click any card to open detailed view

- **Audit Trail** (right top): Complete audit log with agent badges, timestamps, confidence scores

- **Risk Queue** (right bottom, Phase 6):
  - Active issues ranked by risk_score (highest ₹ first)
  - Failure type badges (purple=stall, red=duplicate, amber=sla_breach)
  - Risk background coloring (dark red >₹50k, orange >₹10k)
  - Total exposure calculation
  - Auto-resolves when agents fix issues

- **Break It Button** (header, Phase 6):
  - Click to inject 3 random failures
  - Immediate autonomous cycle execution
  - Toast notification feedback
  - Real-time issue tracking in RiskQueue

- **Detail Drawer** (slides from right):
  - Opens on clicking a workflow card
  - Shows vendor, PO amount, current step details
  - Recent audit history for that workflow
  - Smooth animations, click X or outside to close

- **Auto-polling**:
  - Audit log every 3 seconds
  - Workflows every 5 seconds
  - Active issues every 5 seconds (Phase 6)
  - Autonomous cycle every 30 seconds (triggered by Break It)
  - UI updates without page refresh

- **Responsive dark-themed UI** built with React (CDN) + inline styles (no Tailwind dependency)

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
