import "./SolvedIssueDetails.css";

const SYSTEM_IMPACT = {
  reroute_approver: "Re-routed approval to the correct approver.",
  escalate_sla: "Escalated to manual review for urgent handling.",
  monitor_only: "Kept the case under active monitoring.",
  flag_duplicate: "Flagged a potential duplicate to avoid duplicate payment.",
  request_data: "Requested documents to unblock processing.",
  auto_reject: "Stopped the request to prevent a mismatch payout.",
  action_error: "Recorded an exception and flagged it for follow-up.",
};

const ACTION_OUTCOME = {
  request_data: {
    text: "Waiting for input from assignee.",
    stepStatus: "pending_data",
    workflowStatus: "waiting_for_data",
  },
  reroute_approver: {
    text: "Reassigned and progressing.",
    stepStatus: "in_progress",
    workflowStatus: "on_track",
  },
  flag_duplicate: {
    text: "Duplicate hold applied.",
    stepStatus: "duplicate_hold",
    workflowStatus: "duplicate_hold",
  },
  escalate_sla: {
    text: "Escalated to human review.",
    stepStatus: "escalated",
    workflowStatus: "escalated",
  },
  auto_reject: {
    text: "Rejected after validation.",
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

function formatType(value) {
  if (!value) return "Unknown";
  return String(value).replace(/_/g, " ");
}

function improveReasoningText(text) {
  const raw = (text || "").trim();
  if (!raw) return "Reasoning unavailable";

  return raw
    .replace(/\bsuggests\b/gi, "shows")
    .replace(/\blikely\b/gi, "")
    .replace(/\bindicates\b/gi, "shows")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function mapOutcome(stepStatus, workflowStatus) {
  const s = String(stepStatus || "").toLowerCase();
  const w = String(workflowStatus || "").toLowerCase();

  if (s === "pending_data") {
    return "Waiting for required data from assignee.";
  }
  if (s === "escalated" || w === "escalated") {
    return "Escalated for manual review.";
  }
  if (s === "completed") {
    return "Issue resolved and workflow continued.";
  }
  if (s === "in_progress") {
    return "Issue resolved and workflow is moving forward.";
  }
  if (s === "rejected") {
    return "Request closed after validation checks.";
  }
  if (w === "duplicate_hold") {
    return "Held for duplicate verification before continuing.";
  }

  return "Intervention completed. Latest workflow update is available.";
}

function getStatusBadge(stepStatus, workflowStatus) {
  const s = String(stepStatus || "").toLowerCase();
  const w = String(workflowStatus || "").toLowerCase();

  if (s === "escalated" || w === "escalated") {
    return { label: "Escalated", tone: "escalated" };
  }
  if (s === "pending_data") {
    return { label: "Waiting on user", tone: "waiting" };
  }

  return { label: "Auto-fixed", tone: "autofixed" };
}

function getLatestAuditEntry(auditLog, workflowId, stepId) {
  if (!Array.isArray(auditLog)) {
    return null;
  }

  let latest = null;
  let latestTs = -1;

  for (const entry of auditLog) {
    if (entry?.workflow_id !== workflowId || entry?.step_id !== stepId) {
      continue;
    }
    const ts = Date.parse(entry?.timestamp || "") || 0;
    if (ts >= latestTs) {
      latest = entry;
      latestTs = ts;
    }
  }

  return latest;
}

export default function SolvedIssueDetails({ issue, auditLog = [], workflow, onClose }) {
  if (!issue) return null;

  const failureTypeColor = {
    stall: "#8b5cf6",
    duplicate: "#ef4444",
    duplicate_invoice: "#ef4444",
    sla_breach: "#f59e0b",
  };

  const relatedAuditEntry = getLatestAuditEntry(
    auditLog,
    issue.workflow_id,
    issue.step_id,
  );

  const diagnosisReasoning =
    improveReasoningText(relatedAuditEntry?.reasoning);
  const actionTaken = relatedAuditEntry?.action || "unavailable";
  const impactDetails =
    SYSTEM_IMPACT[actionTaken] ||
    "Applied a corrective action to keep the workflow moving.";
  const confidencePercent =
    typeof relatedAuditEntry?.confidence === "number"
      ? `${Math.round(relatedAuditEntry.confidence * 100)}% confidence`
      : null;
  const actionOutcome = ACTION_OUTCOME[actionTaken] || null;

  const finalStepStatus =
    actionOutcome?.stepStatus || workflow?.current_step?.status || "Unavailable";
  const finalWorkflowStatus =
    actionOutcome?.workflowStatus || workflow?.status || "Unavailable";
  const outcomeText =
    actionOutcome?.text || mapOutcome(finalStepStatus, finalWorkflowStatus);
  const statusBadge = getStatusBadge(finalStepStatus, finalWorkflowStatus);

  return (
    <div className="solved-details-overlay" onClick={onClose}>
      <div
        className="solved-details-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="solved-details-header">
          <div>
            <h2>System Intervention</h2>
            <span className={`intervention-status ${statusBadge.tone}`}>
              {statusBadge.label}
            </span>
          </div>
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
                <strong>Issue Type:</strong> {formatType(issue.failure_type)}
              </p>
              <p>
                <strong>Cause:</strong> {diagnosisReasoning}
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
            <label>System Impact</label>
            <div
              className="resolution-box"
              style={{
                borderLeftColor:
                  failureTypeColor[issue.failure_type] || "#6b7280",
              }}
            >
              <p>
                <strong>Intervention:</strong> {impactDetails}
              </p>
              <p>
                <strong>Action Tag:</strong> {actionTaken}
              </p>
            </div>
          </div>

          {/* Result */}
          <div className="detail-section">
            <label>Outcome</label>
            <div className="summary-box">
              <p>
                {outcomeText}
              </p>
              <p>
                <strong>Step Status:</strong> {formatType(finalStepStatus)}
              </p>
              <p>
                <strong>Workflow Status:</strong> {formatType(finalWorkflowStatus)}
              </p>
              <p>
                <strong>Updated:</strong>{" "}
                {formatTime(relatedAuditEntry?.timestamp || issue.resolvedAt)}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
