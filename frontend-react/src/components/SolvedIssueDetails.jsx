import "./SolvedIssueDetails.css";

export default function SolvedIssueDetails({ issue, onClose }) {
  if (!issue) return null;

  const failureTypeColor = {
    stall: "#8b5cf6",
    duplicate: "#ef4444",
    sla_breach: "#f59e0b",
  };

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

          {/* Summary */}
          <div className="detail-section">
            <label>Summary</label>
            <div className="summary-box">
              <p>
                This <strong>{issue.failure_type}</strong> issue in{" "}
                <strong>{issue.workflow_id}</strong> (step:{" "}
                <strong>{issue.step_name}</strong>) was detected and
                automatically resolved by the agent system.
              </p>
            </div>
          </div>

          {/* Resolution Note */}
          <div className="detail-section">
            <label>Resolution</label>
            <div
              className="resolution-box"
              style={{
                borderLeftColor:
                  failureTypeColor[issue.failure_type] || "#6b7280",
              }}
            >
              ✓ Issue automatically resolved and workflow continued
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
