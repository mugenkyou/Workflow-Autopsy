import { useState } from "react";
import "./WorkflowHeatmap.css";

export default function WorkflowHeatmap({
  workflows,
  activeIssues,
  highlightedWorkflowIds = [],
  forceGreenForNonHighlighted = false,
}) {
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);

  const highlightedSet = new Set(highlightedWorkflowIds);

  const getStatusColor = (status) => {
    switch (status) {
      case "on_track":
        return "#10b981";
      case "at_risk":
        return "#f59e0b";
      case "breached":
        return "#ef4444";
      case "stalled":
        return "#ef4444";
      case "completed":
        return "#6b7280";
      case "duplicate_hold":
        return "#10b981";
      default:
        return "#6b7280";
    }
  };

  const hasActiveIssue = (workflowId) => {
    return activeIssues.some((issue) => issue.workflow_id === workflowId);
  };

  const getDisplayStatus = (workflow) => {
    if (!forceGreenForNonHighlighted) {
      return workflow.status;
    }
    return highlightedSet.has(workflow.id) ? workflow.status : "on_track";
  };

  return (
    <div className="heatmap-container">
      <h2>Workflow Heatmap</h2>
      <div className="workflow-grid">
        {workflows.length === 0 ? (
          <p className="empty-state">No workflows loaded</p>
        ) : (
          workflows.map((workflow) => (
            <div
              key={workflow.id}
              className={`workflow-card ${hasActiveIssue(workflow.id) ? "has-issue" : ""}`}
              style={{
                borderLeftColor: getStatusColor(getDisplayStatus(workflow)),
              }}
              onClick={() => setSelectedWorkflow(workflow)}
            >
              <div className="card-header">
                <span
                  className="status-badge"
                  style={{
                    background: getStatusColor(getDisplayStatus(workflow)),
                  }}
                >
                  {getDisplayStatus(workflow)}
                </span>
              </div>
              <div className="card-body">
                <p className="workflow-name">{workflow.name}</p>
                <p className="vendor">{workflow.vendor}</p>
                <p className="amount">₹{workflow.po_amount.toFixed(0)}</p>
              </div>
              <div className="card-footer">
                <span className="step-name">
                  {workflow.current_step?.step_name}
                </span>
              </div>
            </div>
          ))
        )}
      </div>

      {selectedWorkflow && (
        <div
          className="workflow-detail-modal"
          onClick={() => setSelectedWorkflow(null)}
        >
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button
              className="close-btn"
              onClick={() => setSelectedWorkflow(null)}
            >
              ×
            </button>
            <h3>{selectedWorkflow.name}</h3>
            <p>
              <strong>Vendor:</strong> {selectedWorkflow.vendor}
            </p>
            <p>
              <strong>Amount:</strong> ₹{selectedWorkflow.po_amount}
            </p>
            <p>
              <strong>Status:</strong> {selectedWorkflow.status}
            </p>
            <p>
              <strong>Current Step:</strong>{" "}
              {selectedWorkflow.current_step?.step_name}
            </p>
            <p>
              <strong>Assignee:</strong>{" "}
              {selectedWorkflow.current_step?.assignee}
            </p>
            <p>
              <strong>Created:</strong> {selectedWorkflow.created_at}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
