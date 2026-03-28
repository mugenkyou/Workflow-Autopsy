import './AuditTrail.css'

export default function AuditTrail({ logs }) {
  const getAgentColor = (agentName) => {
    if (!agentName) return '#6b7280'
    if (agentName.includes('Monitor')) return '#3b82f6'
    if (agentName.includes('Diagnosis')) return '#8b5cf6'
    if (agentName.includes('Action')) return '#10b981'
    if (agentName.includes('Audit')) return '#f59e0b'
    return '#6b7280'
  }

  return (
    <div className="audit-trail">
      <div className="trail-header">
        <h3>Audit Trail</h3>
        <span className="log-count">{logs.length} events</span>
      </div>

      <div className="trail-events">
        {logs.length === 0 ? (
          <p className="empty">No audit events</p>
        ) : (
          logs.slice(0, 20).map((log, idx) => (
            <div key={log.id || idx} className="event">
              <div className="event-marker" style={{ background: getAgentColor(log.agent_name) }}></div>
              <div className="event-content">
                <div className="event-agent">{log.agent_name || 'System'}</div>
                <div className="event-action">{log.action}</div>
                {log.reasoning && <div className="event-reasoning">{log.reasoning}</div>}
                <div className="event-time">{log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '—'}</div>
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
  )
}
