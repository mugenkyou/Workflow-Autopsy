import "./StallInsights.css";

export default function StallInsights({ patterns }) {
  const getPatternColor = (stallRate) => {
    if (stallRate > 0.7) return "#ef4444";
    if (stallRate > 0.4) return "#f59e0b";
    return "#10b981";
  };

  return (
    <div className="stall-insights">
      <div className="insights-header">
        <h3>🧠 Agent Learning: Stall Patterns</h3>
        <p className="subtitle">
          Agent pre-emptively routes around these bottlenecks
        </p>
      </div>

      <div className="patterns-container">
        {patterns.length === 0 ? (
          <p className="empty-patterns">Learning patterns in progress...</p>
        ) : (
          patterns.map((pattern, idx) => {
            const color = getPatternColor(pattern.stall_rate);
            const percent = Math.round(pattern.stall_rate * 100);
            return (
              <div key={idx} className="pattern-row">
                <div className="pattern-info">
                  <div className="approver-name">{pattern.approver_id}</div>
                  <div className="condition">{pattern.condition}</div>
                  <div className="sample-count">
                    {pattern.sample_count} observed
                  </div>
                </div>

                <div className="pattern-metric">
                  <div className="bar-container">
                    <div
                      className="bar-fill"
                      style={{
                        width: `${percent}%`,
                        background: color,
                      }}
                    ></div>
                  </div>
                  <span className="rate-label" style={{ color }}>
                    {percent}%
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
