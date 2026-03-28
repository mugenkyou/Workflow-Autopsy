import "./SolvedIssueDetails.css";

const ACTION_DETAILS = {
  reroute_approver: "Approver was rerouted to remove the bottleneck.",
  escalate_sla: "Issue was escalated for SLA intervention.",
  monitor_only: "Delay was acknowledged and tracked for monitoring.",
  flag_duplicate: "Workflow was flagged as duplicate for safe handling.",
  request_data: "Additional data was requested to proceed.",
  auto_reject: "Step was rejected due to amount variance.",
  action_error: "Action failed and was logged for follow-up.",
};

function formatTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

function formatType(value) {
  if (!value) return "Unknown";
  return String(value).replace(/_/g, " ");
}

export default function SolvedIssueDetails({ issue, auditLog = [], workflow, onClose }) {
  if (!issue) return null;

  const failureTypeColor = {
    stall: "#8b5cf6",
    duplicate: "#ef4444",
    duplicate_invoice: "#ef4444",
    sla_breach: "#f59e0b",
  };

  const relatedAuditEntry =
    auditLog.find(
      (entry) =>
        entry.workflow_id === issue.workflow_id && entry.step_id === issue.step_id,
    ) || null;

  const diagnosisReasoning =
    relatedAuditEntry?.reasoning?.trim() || "Reasoning unavailable";
  const actionTaken = relatedAuditEntry?.action || "unavailable";
  const actionDetails = ACTION_DETAILS[actionTaken] || "Action details unavailable";
  const confidencePercent =
    typeof relatedAuditEntry?.confidence === "number"
      ? `${Math.round(relatedAuditEntry.confidence * 100)}% confidence`
      : null;

  const finalStepStatus = workflow?.current_step?.status || "Unavailable";
  const finalWorkflowStatus = workflow?.status || "Unavailable";

  return (
    <div className="solved-details-overlay" onClick={onClose}>
      <div
        className="solved-details-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="solved-details-header">
          <h2>Resolved Issue</h2>
          <button className="solved-details-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="solved-details-content">
          {/* Issue Type Badge */}
          <div className="detail-section">
            <label>Issue Type</label>
            <div
              className="detail-badge"
              style={{
                backgroundColor:
                  failureTypeColor[issue.failure_type] || "#6b7280",
              }}
            >
              {issue.failure_type?.toUpperCase() || "ISSUE"}
            </div>
          </div>

          {/* Workflow & Step */}
          <div className="detail-row">
            <div className="detail-section">
              <label>Workflow ID</label>
              <p>{issue.workflow_id}</p>
            </div>
            <div className="detail-section">
              <label>Step</label>
              <p>{issue.step_name}</p>
            </div>
          </div>

          {/* Risk Info */}
          {issue.risk_score && (
            <div className="detail-section">
              <label>Risk Score</label>
              <p>
                ₹{" "}
                {(issue.risk_score || 0).toLocaleString("en-IN", {
                  maximumFractionDigits: 0,
                })}
              </p>
            </div>
          )}

          {/* Timestamp */}
          <div className="detail-section">
            <label>Resolved At</label>
            <p>
              {issue.resolvedAt
                ? new Date(issue.resolvedAt).toLocaleString()
                : "—"}
            </p>
          </div>

          {/* Diagnosis */}
          <div className="detail-section">
            <label>Diagnosis</label>
            <div className="summary-box">
              <p>
                <strong>Type:</strong> {formatType(issue.failure_type)}
              </p>
              <p>
                <strong>Reasoning:</strong> {diagnosisReasoning}
              </p>
              {confidencePercent && (
                <p>
                  <strong>Confidence:</strong> {confidencePercent}
                </p>
              )}
            </div>
          </div>

          {/* Action */}
          <div className="detail-section">
            <label>Action</label>
            <div
              className="resolution-box"
              style={{
                borderLeftColor:
                  failureTypeColor[issue.failure_type] || "#6b7280",
              }}
            >
              <p>
                <strong>Action Taken:</strong> {actionTaken}
              </p>
              <p>
                <strong>Details:</strong> {actionDetails}
              </p>
            </div>
          </div>

          {/* Result */}
          <div className="detail-section">
            <label>Result</label>
            <div className="summary-box">
              <p>
                <strong>Final Step Status:</strong> {finalStepStatus}
              </p>
              <p>
                <strong>Workflow Status:</strong> {finalWorkflowStatus}
              </p>
              <p>
                <strong>Audit Timestamp:</strong> {formatTime(relatedAuditEntry?.timestamp || issue.resolvedAt)}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
