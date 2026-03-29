# Architecture

## System Overview

Process Autopsy Agent is an autonomous workflow recovery platform that detects operational disruptions, diagnoses likely causes, executes deterministic remediation, and produces a complete audit record for every intervention. The design emphasizes operational consistency, explainability, and fast recovery under risk.

## Agent Breakdown

### MonitorAgent

Detects active workflow disruptions from status, SLA timing, and risk conditions. Produces ranked issue candidates for orchestration.

### DiagnosisAgent

Classifies disruption cause using contextual reasoning and confidence scoring. Generates structured diagnosis output that remains policy-compatible.

### ActionAgent

Executes deterministic remediation policy based on diagnosis class. The action path is controlled by deterministic mappings, not unconstrained LLM output.

### AuditAgent

Writes immutable intervention records, including action, reasoning, confidence, timestamps, and workflow context.

## Data Flow

Issue -> Diagnosis -> Action -> Audit -> Learning

1. MonitorAgent emits issue context.
2. DiagnosisAgent classifies root cause.
3. ActionAgent applies policy-driven correction.
4. AuditAgent records lifecycle evidence.
5. Learning signals are updated from action outcomes and stall patterns.

## Database Tables

### workflows

Workflow headers and top-level status.

### steps

Per-workflow step lifecycle, assignee, SLA metadata, and progression state.

### audit_log

Decision journal with action, reasoning, confidence, and timestamps.

### stall_patterns

Historical disruption patterns used to improve prioritization and diagnosis quality.

### escalations

Human-review queue for high-severity or dependency-blocked cases.

## Key Design Decisions

- Deterministic actions: diagnosis informs action class, but execution remains policy-bound.
- Audit-first design: every intervention is recorded for traceability and review.
- Learning loop: historical pattern signals improve future prioritization and response consistency.

## Why This Matters

Operational workflow disruptions create payment delays, approval bottlenecks, and financial risk. This system reduces recovery time by combining autonomous detection, deterministic remediation, and transparent decision evidence, enabling teams to recover faster while maintaining control and auditability.
