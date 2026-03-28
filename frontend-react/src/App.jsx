import { useState, useEffect } from "react";
import {
  fetchWorkflows,
  fetchAuditLog,
  fetchActiveIssues,
  fetchEscalations,
  fetchStallPatterns,
  injectChaos,
  runCycle,
} from "./api/client";
import WorkflowHeatmap from "./components/WorkflowHeatmap";
import RiskQueue from "./components/RiskQueue";
import AuditTrail from "./components/AuditTrail";
import EscalationPreview from "./components/EscalationPreview";
import StallInsights from "./components/StallInsights";
import "./App.css";

export default function App() {
  const [workflows, setWorkflows] = useState([]);
  const [auditLog, setAuditLog] = useState([]);
  const [activeIssues, setActiveIssues] = useState([]);
  const [escalations, setEscalations] = useState([]);
  const [stallPatterns, setStallPatterns] = useState([]);
  const [selectedEscalation, setSelectedEscalation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [apiErrors, setApiErrors] = useState({});

  // Log API base URL on mount
  useEffect(() => {
    console.log("App mounted, API base: http://localhost:8000");
  }, []);

  // Poll workflows every 5s
  useEffect(() => {
    const pollWorkflows = async () => {
      try {
        console.log("Fetching workflows...");
        const res = await fetchWorkflows();
        console.log("Workflows response:", res.data);
        setWorkflows(res.data);
        setApiErrors((prev) => ({ ...prev, workflows: null }));
      } catch (err) {
        console.error(
          "Workflows fetch error:",
          err.message,
          err.response?.status,
        );
        setApiErrors((prev) => ({ ...prev, workflows: err.message }));
      }
    };
    pollWorkflows();
    const interval = setInterval(pollWorkflows, 5000);
    return () => clearInterval(interval);
  }, []);

  // Poll audit log every 3s
  useEffect(() => {
    const pollAudit = async () => {
      try {
        console.log("Fetching audit log...");
        const res = await fetchAuditLog();
        console.log("Audit log response:", res.data);
        setAuditLog(res.data);
        setApiErrors((prev) => ({ ...prev, audit: null }));
      } catch (err) {
        console.error("Audit log fetch error:", err.message);
        setApiErrors((prev) => ({ ...prev, audit: err.message }));
      }
    };
    pollAudit();
    const interval = setInterval(pollAudit, 3000);
    return () => clearInterval(interval);
  }, []);

  // Poll active issues every 5s
  useEffect(() => {
    const pollIssues = async () => {
      try {
        console.log("Fetching active issues...");
        const res = await fetchActiveIssues();
        console.log("Active issues response:", res.data);
        setActiveIssues(res.data?.issues || []);
        setApiErrors((prev) => ({ ...prev, issues: null }));
      } catch (err) {
        console.error("Active issues fetch error:", err.message);
        setApiErrors((prev) => ({ ...prev, issues: err.message }));
      }
    };
    pollIssues();
    const interval = setInterval(pollIssues, 5000);
    return () => clearInterval(interval);
  }, []);

  // Poll escalations every 5s
  useEffect(() => {
    const pollEscalations = async () => {
      try {
        console.log("Fetching escalations...");
        const res = await fetchEscalations();
        console.log("Escalations response:", res.data);
        const newEscalations = res.data?.issues || [];
        setEscalations(newEscalations);
        setApiErrors((prev) => ({ ...prev, escalations: null }));
        // Trigger modal if new escalation exists
        if (newEscalations.length > 0 && !selectedEscalation) {
          setSelectedEscalation(newEscalations[0]);
        }
      } catch (err) {
        console.error("Escalations fetch error:", err.message);
        setApiErrors((prev) => ({ ...prev, escalations: err.message }));
      }
    };
    pollEscalations();
    const interval = setInterval(pollEscalations, 5000);
    return () => clearInterval(interval);
  }, [selectedEscalation]);

  // Poll stall patterns every 10s
  useEffect(() => {
    const pollPatterns = async () => {
      try {
        console.log("Fetching stall patterns...");
        const res = await fetchStallPatterns();
        console.log("Stall patterns response:", res.data);
        setStallPatterns(res.data?.patterns || []);
        setApiErrors((prev) => ({ ...prev, patterns: null }));
      } catch (err) {
        console.error("Stall patterns fetch error:", err.message);
        setApiErrors((prev) => ({ ...prev, patterns: err.message }));
      }
    };
    pollPatterns();
    const interval = setInterval(pollPatterns, 10000);
    return () => clearInterval(interval);
  }, []);

  // Auto-run cycle every 30s
  useEffect(() => {
    const runCycleInterval = setInterval(() => {
      runCycle().catch((err) => console.error("Run cycle error:", err.message));
    }, 30000);
    return () => clearInterval(runCycleInterval);
  }, []);

  const handleBreakIt = async () => {
    setLoading(true);
    try {
      const res = await injectChaos();
      addToast(`✓ ${res.data.message}`, "success");
    } catch (err) {
      addToast(`✗ ${err.message}`, "error");
    }
    setLoading(false);
  };

  const addToast = (message, type = "info") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  const handleMarkResolved = async (escalationId) => {
    try {
      await markEscalationResolved(escalationId);
      setEscalations((prev) =>
        prev.filter((e) => e.workflow_id !== escalationId),
      );
      setSelectedEscalation(null);
      addToast("Escalation marked as reviewed", "success");
    } catch (err) {
      addToast(`Error: ${err.message}`, "error");
    }
  };

  return (
    <div className="app">
      {/* Header */}
      <div className="header">
        <h1>Process Autopsy Agent</h1>
        <button
          className="break-it-btn"
          onClick={handleBreakIt}
          disabled={loading}
        >
          ⚡ Break It
        </button>
      </div>

      {/* Debug/Error Section */}
      {Object.values(apiErrors).some((e) => e) && (
        <div
          style={{
            background: "#2d1f1f",
            border: "1px solid #ef4444",
            borderRadius: "6px",
            padding: "1rem",
            margin: "1rem",
            color: "#fca5a5",
            fontSize: "0.9rem",
            maxHeight: "100px",
            overflow: "auto",
          }}
        >
          <strong>⚠️ API Errors:</strong>
          <div>
            {Object.entries(apiErrors).map(
              ([key, err]) =>
                err && (
                  <div key={key}>
                    {key}: {err}
                  </div>
                ),
            )}
          </div>
        </div>
      )}

      {/* Main Layout: Heatmap (60%) | Right Panel (40%) */}
      <div className="main-layout">
        {/* Left: Heatmap */}
        <div className="left-panel">
          <WorkflowHeatmap workflows={workflows} activeIssues={activeIssues} />
        </div>

        {/* Right: Risk Queue + Audit Trail */}
        <div className="right-panel">
          <RiskQueue issues={activeIssues} />
          <AuditTrail logs={auditLog} />
        </div>
      </div>

      {/* Bottom: Stall Insights */}
      <div className="stall-insights-section">
        <StallInsights patterns={stallPatterns} />
      </div>

      {/* Escalation Modal */}
      {selectedEscalation && (
        <EscalationPreview
          escalation={selectedEscalation}
          onMarkResolved={() =>
            handleMarkResolved(selectedEscalation.workflow_id)
          }
          onClose={() => setSelectedEscalation(null)}
        />
      )}

      {/* Toast Notifications */}
      <div className="toasts">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast ${toast.type}`}>
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  );
}
