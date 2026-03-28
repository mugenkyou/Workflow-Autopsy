import "./SolvedIssues.css";

function formatTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString();
}

export default function SolvedIssues({ issues, onIssueClick }) {
  return (
    <div className="solved-issues">
      <div className="solved-header">
        <h3>Solved Issues</h3>
        <span className="solved-badge">{issues.length}</span>
      </div>

      <div className="solved-list">
        {issues.length === 0 ? (
          <p className="empty">No solved issues yet</p>
        ) : (
          issues.map((issue) => (
            <div
              key={issue.id}
              className="solved-item"
              role="button"
              tabIndex={0}
              onClick={() => onIssueClick?.(issue)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onIssueClick?.(issue);
                }
              }}
            >
              <div className="solved-top">
                <span className="solved-type">
                  {issue.failure_type?.toUpperCase() || "ISSUE"}
                </span>
                <span className="solved-time">
                  {formatTime(issue.resolvedAt)}
                </span>
              </div>
              <div className="solved-body">
                <p>{issue.step_name}</p>
                <small>{issue.workflow_id}</small>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
