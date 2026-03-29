import "./IssueDetails.css";

const ACTION_DETAILS = {
  reroute_approver: "Reassigned to backup approver based on past patterns.",
  escalate_sla: "Escalated due to unresolved delay requiring human decision.",
  flag_duplicate: "Workflow flagged due to duplicate invoice detection.",
  request_data: "Requested invoice metadata and supporting documents.",
  auto_reject: "Rejected due to variance beyond acceptable threshold.",
  action_error: "Action execution failed and was routed for immediate review.",
};

const TERMINAL_ACTIONS = new Set([
  "flag_duplicate",
  "escalate_sla",
  "auto_reject",
]);

const ACTION_STATUS_DISPLAY = {
  request_data: {
    result: "Waiting for input",
    stepStatus: "pending_data",
    workflowStatus: "waiting_for_data",
  },
  reroute_approver: {
    result: "Reassigned and progressing",
    stepStatus: "in_progress",
    workflowStatus: "on_track",
  },
  flag_duplicate: {
    result: "Duplicate hold",
    stepStatus: "duplicate_hold",
    workflowStatus: "duplicate_hold",
  },
  escalate_sla: {
    result: "Escalated to human",
    stepStatus: "escalated",
    workflowStatus: "escalated",
  },
  auto_reject: {
    result: "Rejected",
    stepStatus: "rejected",
    workflowStatus: "rejected",
  },
};

function formatTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

function normalizeText(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function learningResponseForRate(stallRate) {
  if (stallRate >= 0.7) {
    return "System elevated this issue to high-priority routing and favored decisive intervention paths.";
  }
  if (stallRate >= 0.4) {
    return "System increased monitoring weight and steered action toward bottleneck removal.";
  }
  return "System treated this as a weak prior and kept tighter observation during diagnosis/action.";
}

export default function IssueDetails({
  issue,
  workflow,
  auditEntry,
  stallPatterns = [],
  isStillActive,
  onClose,
}) {
  if (!issue) return null;

  const actionTaken = String(auditEntry?.action || "unavailable");
  const actionDetails =
    ACTION_DETAILS[actionTaken] || "Awaiting action details.";
  const diagnosisType = issue.failure_type || "unknown";
  const diagnosisReasoning =
    auditEntry?.reasoning ||
    "Issue context indicates a likely operational bottleneck requiring corrective action.";
  const confidence =
    typeof auditEntry?.confidence === "number"
      ? `${(auditEntry.confidence * 100).toFixed(0)}%`
      : "50%";
  const actionStatus = ACTION_STATUS_DISPLAY[actionTaken] || null;
  const isTerminalAction = TERMINAL_ACTIONS.has(actionTaken);

  const displayStepStatus =
    actionStatus?.stepStatus || workflow?.current_step?.status || "in_progress";
  const displayWorkflowStatus =
    actionStatus?.workflowStatus || workflow?.status || "in_progress";
  const resultLabel = actionStatus?.result
    ? actionStatus.result
    : isStillActive || !isTerminalAction
      ? "Monitoring / in progress"
      : "Issue resolved";
  const resultTimeLabel = isTerminalAction ? "Completed" : "In progress";

  const matchedPattern = stallPatterns.find(
    (pattern) =>
      normalizeText(pattern.approver_id) === normalizeText(issue.assignee),
  );

  const learningAppliedSummary = matchedPattern
    ? `This issue matches past pattern for ${issue.assignee}: ${matchedPattern.condition}.`
    : null;

  const learningAppliedResponse = matchedPattern
    ? learningResponseForRate(Number(matchedPattern.stall_rate) || 0)
    : null;

  const timeline = [
    {
      label: "Detected",
      detail: `${issue.step_name} entered risk queue`,
      time: isStillActive ? "Active now" : "Resolved from queue",
    },
    {
      label: "Diagnosed",
      detail: `Type: ${diagnosisType}`,
      time: formatTime(auditEntry?.timestamp),
    },
    {
      label: "Action",
      detail: actionTaken,
      time: formatTime(auditEntry?.timestamp),
    },
    {
      label: "Result",
      detail: resultLabel,
      time: resultTimeLabel,
    },
  ];

  return (
    <aside className="issue-details" aria-label="Issue details panel">
      <div className="issue-details-header">
        <div>
          <h3>Issue Details</h3>
          <p>AI diagnosis and action trace</p>
        </div>
        <button
          className="issue-details-close"
          onClick={onClose}
          aria-label="Close issue details"
        >
          ×
        </button>
      </div>

      <section className="issue-section">
        <h4>1. Issue Summary</h4>
        <div className="kv-grid">
          <div>
            <span className="k">Workflow</span>
            <span className="v">{workflow?.name || issue.workflow_id}</span>
          </div>
          <div>
            <span className="k">Step</span>
            <span className="v">{issue.step_name}</span>
          </div>
          <div>
            <span className="k">Risk</span>
            <span className="v">₹{(issue.risk_score || 0).toFixed(0)}</span>
          </div>
          <div>
            <span className="k">Assignee</span>
            <span className="v">{issue.assignee}</span>
          </div>
        </div>
      </section>

      <section className="issue-section">
        <h4>2. Diagnosis (LLM output)</h4>
        <div className="kv-grid single">
          <div>
            <span className="k">stall_type</span>
            <span className="v">{diagnosisType}</span>
          </div>
          <div>
            <span className="k">reasoning</span>
            <span className="v block">{diagnosisReasoning}</span>
          </div>
          <div>
            <span className="k">confidence</span>
            <span className="v">{confidence}</span>
          </div>
        </div>
      </section>

      <section className="issue-section">
        <h4>3. Action Taken</h4>
        <div className="kv-grid single">
          <div>
            <span className="k">action_taken</span>
            <span className="v">{actionTaken}</span>
          </div>
          <div>
            <span className="k">new_status</span>
            <span className="v">{displayStepStatus}</span>
          </div>
          <div>
            <span className="k">details</span>
            <span className="v block">{actionDetails}</span>
          </div>
        </div>
      </section>

      <section className="issue-section">
        <h4>4. Result</h4>
        <div className="kv-grid single">
          <div>
            <span className="k">workflow status</span>
            <span className="v">{displayWorkflowStatus}</span>
          </div>
          <div>
            <span className="k">step status after action</span>
            <span className="v">{displayStepStatus}</span>
          </div>
        </div>
      </section>

      <section className="issue-section">
        <h4>5. Learning Applied</h4>
        {matchedPattern ? (
          <div className="learning-applied">
            <p>{learningAppliedSummary}</p>
            <p>{learningAppliedResponse}</p>
          </div>
        ) : (
          <div className="learning-applied learning-applied-empty">
            <p>
              No strong historical pattern found for this assignee yet. System
              used standard diagnosis and action flow.
            </p>
          </div>
        )}
      </section>

      <section className="issue-section">
        <h4>6. Timeline</h4>
        <div className="timeline">
          {timeline.map((item, idx) => (
            <div key={`${item.label}-${idx}`} className="timeline-item">
              <div className="timeline-dot" />
              <div>
                <div className="timeline-label">{item.label}</div>
                <div className="timeline-detail">{item.detail}</div>
                <div className="timeline-time">{item.time}</div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </aside>
  );
}
