# System Architecture

This document captures the runtime architecture for the Process Autopsy Agent and links the source Mermaid diagrams used by the project.

## 1) Component Diagram

Source: [component-diagram.mmd](component-diagram.mmd)

```mermaid
flowchart LR
    subgraph UI[Frontend - React/Vite]
        APP[App.jsx]
        HEATMAP[WorkflowHeatmap]
        RISK[RiskQueue]
        AUDIT[AuditTrail]
        ESC[EscalationPreview]
        STALL[StallInsights]
    end

    subgraph API[Backend - FastAPI]
        MAIN[main.py]
        MON[MonitorAgent]
        DIAG[DiagnosisAgent]
        ACT[ActionAgent]
        AUT[AuditAgent]
        GRAPH[LangGraph Orchestrator]
        DBMOD[db.py]
    end

    subgraph DATA[Data Layer]
        SQLITE[(SQLite\nautopsy.db)]
        PAT[(stall_patterns)]
        ESCAL[(escalations)]
        AUD[(audit_log)]
    end

    subgraph LLM[Inference]
        OLL[Ollama\nmistral]
    end

    APP -->|REST polling| MAIN
    MAIN --> GRAPH
    GRAPH --> MON
    GRAPH --> DIAG
    GRAPH --> ACT
    GRAPH --> AUT

    DIAG -->|diagnosis prompt| OLL

    MAIN --> DBMOD
    DBMOD --> SQLITE
    SQLITE --> PAT
    SQLITE --> ESCAL
    SQLITE --> AUD

    MAIN -->|/workflows| HEATMAP
    MAIN -->|/active-issues| RISK
    MAIN -->|/audit-log| AUDIT
    MAIN -->|/escalations| ESC
    MAIN -->|/stall-patterns| STALL
```

## 2) Workflow Sequence Diagram

Source: [workflow-sequence.mmd](workflow-sequence.mmd)

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant UI as React Dashboard
    participant API as FastAPI
    participant M as MonitorAgent
    participant D as DiagnosisAgent
    participant A as ActionAgent
    participant Au as AuditAgent
    participant DB as SQLite
    participant LLM as Ollama (mistral)

    User->>UI: Click Break It
    UI->>API: POST /inject-chaos
    API->>DB: Mark random steps as stalled/breached/duplicate
    API-->>UI: Chaos injected (success)

    loop Polling (3s/5s/10s)
        UI->>API: GET /workflows, /active-issues, /audit-log, /escalations, /stall-patterns
        API->>DB: Query current state
        API-->>UI: Latest workflow + issue snapshots
    end

    UI->>API: POST /run-cycle (every 30s)
    API->>M: run()
    M->>DB: Find overdue/failed active steps
    M-->>API: Ranked issues

    loop For each issue
        API->>D: Diagnose issue
        D->>LLM: Prompt for stall_type + confidence + reasoning
        LLM-->>D: Diagnosis response
        D-->>API: Structured diagnosis

        API->>A: Execute action policy
        A->>DB: Update workflow/step/escalation state
        A-->>API: Action result

        API->>Au: Persist audit
        Au->>DB: Insert audit_log entry
        Au-->>API: Audit confirmation
    end

    API-->>UI: Cycle complete

    alt Human review required
        UI->>User: Show EscalationPreview modal
        User->>UI: Mark as Reviewed
        UI->>API: POST /mark-resolved
        API->>DB: Set escalations.resolved_at
        API-->>UI: Resolved success
    end
```

## 3) Notes

- Frontend is polling-based, so UI state reflects backend changes without manual refresh.
- The diagnosis stage is the only stage that depends on LLM inference.
- Escalations support a human-in-the-loop review path via /mark-resolved.
