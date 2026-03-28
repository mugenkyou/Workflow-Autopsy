import "./RiskQueue.css";

export default function RiskQueue({ issues }) {
  const getFailureColor = (type) => {
    switch (type) {
      case "stall":
        return "#f59e0b";
      case "sla_breach":
        return "#ef4444";
      case "duplicate":
        return "#f59e0b";
      case "escalated":
        return "#9333ea";
      default:
        return "#6b7280";
    }
  };

  const totalRisk = issues.reduce(
    (sum, issue) => sum + (issue.risk_score || 0),
    0,
  );

  return (
    <div className="risk-queue">
      <div className="queue-header">
        <h3>Active Issues</h3>
        <span className="risk-badge">{issues.length} issues</span>
      </div>

      <div className="queue-stats">
        <div className="stat">
          <span className="label">Total Risk</span>
          <span className="value">₹{totalRisk.toFixed(0)}</span>
        </div>
      </div>

      <div className="issues-list">
        {issues.length === 0 ? (
          <p className="empty">No active issues</p>
        ) : (
          issues.slice(0, 10).map((issue, idx) => (
            <div
              key={`${issue.workflow_id}-${idx}`}
              className="issue-item"
              style={{ borderLeftColor: getFailureColor(issue.failure_type) }}
            >
              <div className="issue-header">
                <span
                  className="type-badge"
                  style={{ background: getFailureColor(issue.failure_type) }}
                >
                  {issue.failure_type.toUpperCase()}
                </span>
                <span className="risk-score">
                  ₹{issue.risk_score.toFixed(0)}
                </span>
              </div>
              <div className="issue-body">
                <p className="step-name">{issue.step_name}</p>
                <p className="assignee">{issue.assignee}</p>
                <p className="hours">{issue.hours_overdue}h overdue</p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
