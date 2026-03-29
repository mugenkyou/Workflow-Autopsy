import "./AuditTrail.css";

export default function AuditTrail({ logs }) {
  const getAgentColor = (agentName) => {
    if (!agentName) return "#6b7280";
    if (agentName.includes("Monitor")) return "#3b82f6";
    if (agentName.includes("Diagnosis")) return "#8b5cf6";
    if (agentName.includes("Action")) return "#10b981";
    if (agentName.includes("Audit")) return "#f59e0b";
    return "#6b7280";
  };

  const sortedLogs = [...logs].sort((a, b) => {
    const aTs = Date.parse(a?.timestamp || "") || 0;
    const bTs = Date.parse(b?.timestamp || "") || 0;
    return bTs - aTs;
  });

  const expandedEvents = sortedLogs.flatMap((log, idx) => {
    const baseId =
      log.id ||
      `${log.timestamp || "ts"}-${log.workflow_id || "wf"}-${log.step_id || "step"}-${idx}`;

    const context = [log.workflow_id, log.step_id].filter(Boolean).join(" / ");
    const contextText = context ? ` (${context})` : "";

    return [
      {
        ...log,
        id: `${baseId}:diagnosis`,
        agent_name: "DiagnosisAgent",
        action: `classified:${log.action || "unknown"}`,
        reasoning:
          log.reasoning || `Diagnosed issue and selected action${contextText}.`,
        confidence: log.confidence,
        _order: 0,
      },
      {
        ...log,
        id: `${baseId}:action`,
        agent_name: "ActionAgent",
        action: log.action || "execute_action",
        reasoning: `Executed corrective action${contextText}.`,
        confidence: null,
        _order: 1,
      },
      {
        ...log,
        id: `${baseId}:audit`,
        agent_name: "AuditAgent",
        action: "audit_recorded",
        reasoning: `Captured lifecycle record${contextText}.`,
        confidence: null,
        _order: 2,
      },
    ];
  });

  expandedEvents.sort((a, b) => {
    const aTs = Date.parse(a?.timestamp || "") || 0;
    const bTs = Date.parse(b?.timestamp || "") || 0;
    if (bTs !== aTs) return bTs - aTs;
    return (a._order || 0) - (b._order || 0);
  });

  return (
    <div className="audit-trail">
      <div className="trail-header">
        <h3>Audit Trail</h3>
        <span className="log-count">{expandedEvents.length} events</span>
      </div>

      <div className="trail-events">
        {expandedEvents.length === 0 ? (
          <p className="empty">No audit events</p>
        ) : (
          expandedEvents.map((log) => (
            <div key={log.id} className="event">
              <div
                className="event-marker"
                style={{ background: getAgentColor(log.agent_name) }}
              ></div>
              <div className="event-content">
                <div className="event-agent">{log.agent_name || "System"}</div>
                <div className="event-action">{log.action}</div>
                {log.reasoning && (
                  <div className="event-reasoning">{log.reasoning}</div>
                )}
                <div className="event-time">
                  {log.timestamp
                    ? new Date(log.timestamp).toLocaleTimeString()
                    : "—"}
                </div>
              </div>
              {log.confidence && (
                <div className="event-confidence">
                  {(log.confidence * 100).toFixed(0)}%
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
