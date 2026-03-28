import "./StallInsights.css";

export default function StallInsights({ patterns }) {
  const getPatternColor = (stallRate) => {
    if (stallRate > 0.7) return "#ef4444";
    if (stallRate > 0.4) return "#f59e0b";
    return "#10b981";
  };

  const formatApprover = (value) => {
    const text = String(value || "").trim();
    return text || "Unknown approver";
  };

  const describeCondition = (condition) => {
    const text = String(condition || "").trim();
    if (!text) {
      return "Delays recur under similar approval conditions.";
    }
    return `When ${text.toLowerCase()}.`;
  };

  const describePatternImpact = (stallRate) => {
    if (stallRate >= 0.7) {
      return "Repeated severe bottleneck: approvals frequently block downstream payment steps.";
    }
    if (stallRate >= 0.4) {
      return "Recurring slowdown: this approver-pattern combination often delays SLA completion.";
    }
    return "Early warning signal: occasional stall behavior that the system monitors proactively.";
  };

  const describeFrequency = (stallRate, sampleCount) => {
    const percent = Math.round(stallRate * 100);
    const count = Number.isFinite(sampleCount) ? sampleCount : 0;
    return `Stalls in ${percent}% of ${count} similar cases, so future matches are treated as elevated risk.`;
  };

  const systemResponse = (stallRate) => {
    if (stallRate >= 0.7) {
      return "The system fast-tracks diagnosis and favors reroute or escalation actions earlier in the cycle.";
    }
    if (stallRate >= 0.4) {
      return "The system increases monitoring priority and biases action selection toward bottleneck removal.";
    }
    return "The system keeps this pattern as a soft prior and watches for confirmation before stronger intervention.";
  };

  return (
    <div className="stall-insights">
      <div className="insights-header">
        <h3>🧠 Agent Learning: Stall Patterns</h3>
        <p className="subtitle">
          The system learns recurring failure patterns and adjusts actions automatically
        </p>
      </div>

      <div className="patterns-container">
        {patterns.length === 0 ? (
          <p className="empty-patterns">Learning patterns in progress...</p>
        ) : (
          patterns.map((pattern, idx) => {
            const color = getPatternColor(pattern.stall_rate);
            const approver = formatApprover(pattern.approver_id);
            const condition = describeCondition(pattern.condition);
            const problemDescription = describePatternImpact(pattern.stall_rate);
            const frequency = describeFrequency(pattern.stall_rate, pattern.sample_count);
            const response = systemResponse(pattern.stall_rate);
            return (
              <div key={idx} className="pattern-row">
                <div className="pattern-info">
                  <div className="approver-name">{approver}</div>
                  <div className="problem-description">{problemDescription}</div>
                  <div className="condition">{condition}</div>
                  <div className="frequency">Frequency: {frequency}</div>
                  <div className="system-response">
                    <span className="arrow">→</span> System response: {response}
                  </div>
                </div>

                <div className="pattern-metric">
                  <div className="bar-container">
                    <div
                      className="bar-fill"
                      style={{
                        width: `${Math.round(pattern.stall_rate * 100)}%`,
                        background: color,
                      }}
                    ></div>
                  </div>
                  <span className="rate-label" style={{ color }}>
                    risk
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
