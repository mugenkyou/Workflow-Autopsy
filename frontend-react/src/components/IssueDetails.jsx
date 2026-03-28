import "./IssueDetails.css";

const ACTION_DETAILS = {
  reroute_approver: "Approver was reassigned to remove workflow bottleneck.",
  escalate_sla: "Issue escalated due to external dependency risk.",
  monitor_only: "External delay noted; system continues monitoring.",
  flag_duplicate: "Workflow flagged for duplicate handling.",
  request_data: "Additional data requested to proceed.",
  auto_reject: "Step rejected due to amount variance.",
  action_error: "Action failed and was recorded for follow-up.",
};

function formatTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

export default function IssueDetails({
  issue,
  workflow,
  auditEntry,
  isStillActive,
  onClose,
}) {
  if (!issue) return null;

  const actionTaken = auditEntry?.action || "pending";
  const actionDetails =
    ACTION_DETAILS[actionTaken] || "Action details not captured in audit log.";
  const diagnosisType = issue.failure_type || "unknown";
  const diagnosisReasoning =
    auditEntry?.reasoning || "Diagnosis reasoning not available yet.";
  const confidence =
    typeof auditEntry?.confidence === "number"
      ? `${(auditEntry.confidence * 100).toFixed(0)}%`
      : "—";

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
      detail: isStillActive ? "Monitoring / in progress" : "Issue resolved",
      time: isStillActive ? "In progress" : "Completed",
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
            <span className="v">{workflow?.current_step?.status || "—"}</span>
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
            <span className="v">{workflow?.status || "—"}</span>
          </div>
          <div>
            <span className="k">step status after action</span>
            <span className="v">{workflow?.current_step?.status || "—"}</span>
          </div>
        </div>
      </section>

      <section className="issue-section">
        <h4>5. Timeline</h4>
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
