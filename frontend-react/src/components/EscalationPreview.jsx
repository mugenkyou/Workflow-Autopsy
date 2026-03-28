import "./EscalationPreview.css";

export default function EscalationPreview({
  escalation,
  onMarkResolved,
  onClose,
}) {
  return (
    <div className="escalation-overlay" onClick={onClose}>
      <div className="escalation-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="escalation-header">
          <div className="header-content">
            <h2>🚨 Human Review Required</h2>
            <p>This workflow needs human decision-making intervention</p>
          </div>
          <button className="close-btn" onClick={onClose}>
            ×
          </button>
        </div>

        {/* Workflow Details */}
        <div className="escalation-section">
          <h3>Workflow Information</h3>
          <div className="info-grid">
            <div className="info-item">
              <span className="label">Workflow</span>
              <span className="value">{escalation.step_name}</span>
            </div>
            <div className="info-item">
              <span className="label">Step</span>
              <span className="value">{escalation.step_name}</span>
            </div>
            <div className="info-item">
              <span className="label">Assignee</span>
              <span className="value">{escalation.assignee}</span>
            </div>
            <div className="info-item">
              <span className="label">Risk Score</span>
              <span className="value">
                ₹{escalation.risk_score?.toFixed(0) || "—"}
              </span>
            </div>
          </div>
        </div>

        {/* Issue Summary */}
        <div className="escalation-section">
          <h3>Issue Summary</h3>
          <div className="issue-summary">
            <p>
              This {escalation.failure_type} has been{" "}
              <strong>
                overdue for {escalation.hours_overdue?.toFixed(1)} hours
              </strong>
              .
            </p>
            <p className="mt-1">
              The system's agents have attempted standard resolution procedures,
              but cannot proceed without human judgment.
            </p>
          </div>
        </div>

        {/* Agent Attempts */}
        <div className="escalation-section">
          <h3>What Agents Attempted</h3>
          <ul className="agent-attempts">
            <li>✓ Analyzed workflow history and patterns</li>
            <li>✓ Checked for approval bottlenecks</li>
            <li>✓ Verified vendor and amount accuracy</li>
            <li>✗ Unable to resolve without human guidance</li>
          </ul>
        </div>

        {/* Action Options */}
        <div className="escalation-section">
          <h3>Recommended Actions</h3>
          <div className="action-options">
            <div className="action-card">
              <div className="action-title">Option A: Expedite</div>
              <div className="action-desc">
                Approve workflow for immediate processing
              </div>
              <div className="risk-note">
                ⚠️ Bypasses standard approval chain
              </div>
            </div>
            <div className="action-card">
              <div className="action-title">Option B: Review</div>
              <div className="action-desc">
                Route to senior approver for detailed review
              </div>
              <div className="risk-note">⚠️ May add additional days</div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="escalation-footer">
          <button className="btn-secondary" onClick={onClose}>
            Review Later
          </button>
          <button className="btn-primary" onClick={onMarkResolved}>
            ✓ Mark as Reviewed
          </button>
        </div>
      </div>
    </div>
  );
}
