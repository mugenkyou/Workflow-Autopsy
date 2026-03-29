import { useEffect, useRef, useState } from "react";
import {
  fetchWorkflows,
  fetchAuditLog,
  fetchActiveIssues,
  fetchEscalations,
  fetchStallPatterns,
  injectChaos,
  stopAgent,
  markEscalationResolved,
  runCycle,
} from "./api/client";
import WorkflowHeatmap from "./components/WorkflowHeatmap";
import RiskQueue from "./components/RiskQueue";
import AuditTrail from "./components/AuditTrail";
import EscalationPreview from "./components/EscalationPreview";
import IssueDetails from "./components/IssueDetails";
import SolvedIssues from "./components/SolvedIssues";
import SolvedIssueDetails from "./components/SolvedIssueDetails";
import StallInsights from "./components/StallInsights";
import "./App.css";

export default function App() {
  // Demo-stable flag: escalation UI and polling are disabled by default.
  const ENABLE_ESCALATION = false;
  const ESCALATION_COOLDOWN_MS = 60000;
  const ESCALATION_SNOOZE_MS = 5 * 60 * 1000;

  const [workflows, setWorkflows] = useState([]);
  const [auditLog, setAuditLog] = useState([]);
  const [activeIssues, setActiveIssues] = useState([]);
  const [solvedIssues, setSolvedIssues] = useState([]);
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [selectedSolvedIssue, setSelectedSolvedIssue] = useState(null);
  const [escalations, setEscalations] = useState([]);
  const [escalationQueue, setEscalationQueue] = useState([]);
  const [stallPatterns, setStallPatterns] = useState([]);
  const [selectedEscalation, setSelectedEscalation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [resolutionLocked, setResolutionLocked] = useState(false);
  const [currentRunId, setCurrentRunId] = useState(null);
  const [currentRunWorkflowIds, setCurrentRunWorkflowIds] = useState([]);
  const [heatmapRevision, setHeatmapRevision] = useState(0);
  const [toasts, setToasts] = useState([]);
  const [apiErrors, setApiErrors] = useState({});
  const shownEscalationIdsRef = useRef(new Set());
  const dismissedUntilRef = useRef(new Map());
  const activeIssueMapRef = useRef(new Map());
  const resolutionLockedRef = useRef(false);
  const seenInjectedIssuesRef = useRef(false);

  const parseInjectedWorkflowIds = (failuresInjected) => {
    if (!Array.isArray(failuresInjected)) return [];
    return failuresInjected
      .map((entry) => {
        const text = String(entry || "");
        const parts = text.split(/→|->/);
        return (parts[parts.length - 1] || "").trim();
      })
      .filter(Boolean);
  };

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

        const incomingIssues = res.data?.issues || [];
        const scopedIncomingIssues = currentRunId
          ? incomingIssues.filter(
              (issue) => issue.injected_run_id === currentRunId,
            )
          : [];
        const incomingMap = new Map(
          scopedIncomingIssues.map((issue) => [
            `${issue.workflow_id}|${issue.step_id}`,
            issue,
          ]),
        );

        const resolvedNow = [];
        activeIssueMapRef.current.forEach((oldIssue, key) => {
          if (!incomingMap.has(key)) {
            resolvedNow.push({
              id: `${key}-${Date.now()}`,
              ...oldIssue,
              resolvedAt: new Date().toISOString(),
            });
          }
        });

        if (resolvedNow.length > 0) {
          setSolvedIssues((prev) => [...resolvedNow, ...prev].slice(0, 25));
        }

        activeIssueMapRef.current = incomingMap;
        setActiveIssues(scopedIncomingIssues);

        if (resolutionLockedRef.current) {
          if (scopedIncomingIssues.length > 0) {
            seenInjectedIssuesRef.current = true;
          }

          if (
            seenInjectedIssuesRef.current &&
            scopedIncomingIssues.length === 0
          ) {
            resolutionLockedRef.current = false;
            setResolutionLocked(false);
            seenInjectedIssuesRef.current = false;
            setCurrentRunId(null);
            setCurrentRunWorkflowIds([]);
            addToast("Agents resolved all injected issues", "success");
          }
        }

        setApiErrors((prev) => ({ ...prev, issues: null }));
      } catch (err) {
        console.error("Active issues fetch error:", err.message);
        setApiErrors((prev) => ({ ...prev, issues: err.message }));
      }
    };
    pollIssues();
    const interval = setInterval(pollIssues, 5000);
    return () => clearInterval(interval);
  }, [currentRunId]);

  // Show next queued escalation when no modal is open.
  useEffect(() => {
    if (selectedEscalation || escalationQueue.length === 0) {
      return;
    }

    const now = Date.now();
    const next = escalationQueue.find((item) => {
      const dismissedUntil = dismissedUntilRef.current.get(item.id) || 0;
      return dismissedUntil <= now;
    });

    if (!next) {
      return;
    }

    setEscalationQueue((prev) => prev.filter((item) => item.id !== next.id));
    shownEscalationIdsRef.current.add(next.id);
    setSelectedEscalation(next);
  }, [selectedEscalation, escalationQueue]);

  // Poll escalations every 5s
  useEffect(() => {
    if (!ENABLE_ESCALATION) {
      return;
    }

    const pollEscalations = async () => {
      try {
        console.log("Fetching escalations...");
        const res = await fetchEscalations();
        console.log("Escalations response:", res.data);
        const newEscalations = res.data?.issues || [];
        const now = Date.now();
        const activeIds = new Set(newEscalations.map((e) => e.id));

        setEscalations(newEscalations);
        setEscalationQueue((prev) =>
          prev.filter((item) => activeIds.has(item.id)),
        );

        if (selectedEscalation && !activeIds.has(selectedEscalation.id)) {
          setSelectedEscalation(null);
        }

        const queueCandidates = newEscalations.filter((item) => {
          if (!item.id) {
            return false;
          }
          const dismissedUntil = dismissedUntilRef.current.get(item.id) || 0;
          if (dismissedUntil > now) {
            return false;
          }
          return !shownEscalationIdsRef.current.has(item.id);
        });

        if (queueCandidates.length > 0) {
          setEscalationQueue((prev) => {
            const existingIds = new Set(prev.map((item) => item.id));
            const additions = queueCandidates.filter(
              (item) => !existingIds.has(item.id),
            );
            return additions.length ? [...prev, ...additions] : prev;
          });
        }

        setApiErrors((prev) => ({ ...prev, escalations: null }));
      } catch (err) {
        console.error("Escalations fetch error:", err.message);
        setApiErrors((prev) => ({ ...prev, escalations: err.message }));
      }
    };
    pollEscalations();
    const interval = setInterval(pollEscalations, 5000);
    return () => clearInterval(interval);
  }, [selectedEscalation, ENABLE_ESCALATION]);

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
    const interval = setInterval(pollPatterns, 15000);
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
    if (resolutionLockedRef.current) {
      addToast("Wait for current injected issues to resolve", "info");
      return;
    }

    setSolvedIssues([]);
    setActiveIssues([]);
    activeIssueMapRef.current = new Map();
    seenInjectedIssuesRef.current = false;
    setCurrentRunId(null);
    setCurrentRunWorkflowIds([]);
    setHeatmapRevision((prev) => prev + 1);

    setLoading(true);
    try {
      const res = await injectChaos();
      const runId = res.data?.run_id || null;
      const workflowIds = Array.isArray(res.data?.workflow_ids)
        ? res.data.workflow_ids
        : parseInjectedWorkflowIds(res.data?.failures_injected);
      resolutionLockedRef.current = true;
      setResolutionLocked(true);
      setCurrentRunId(runId);
      setCurrentRunWorkflowIds(workflowIds);
      addToast(`✓ ${res.data.message}`, "success");
    } catch (err) {
      addToast(`✗ ${err.message}`, "error");
    }
    setLoading(false);
  };

  const handleStopAgent = async () => {
    try {
      await stopAgent();
      // Immediately clear everything and unlock Break It
      resolutionLockedRef.current = false;
      setResolutionLocked(false);
      setActiveIssues([]);
      setSolvedIssues([]);
      activeIssueMapRef.current = new Map();
      seenInjectedIssuesRef.current = false;
      setCurrentRunId(null);
      setCurrentRunWorkflowIds([]);
      setHeatmapRevision((prev) => prev + 1);
      addToast("Agent stopped. Break It is ready again.", "success");
    } catch (err) {
      addToast(`Error: ${err.message}`, "error");
    }
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
      setEscalations((prev) => prev.filter((e) => e.id !== escalationId));
      setEscalationQueue((prev) => prev.filter((e) => e.id !== escalationId));
      dismissedUntilRef.current.delete(escalationId);
      setSelectedEscalation(null);
      addToast("Escalation marked as reviewed", "success");
    } catch (err) {
      addToast(`Error: ${err.message}`, "error");
    }
  };

  const handleEscalationClose = () => {
    if (!selectedEscalation) {
      return;
    }
    const escalationId = selectedEscalation.id;
    dismissedUntilRef.current.set(
      escalationId,
      Date.now() + ESCALATION_COOLDOWN_MS,
    );
    setTimeout(() => {
      shownEscalationIdsRef.current.delete(escalationId);
    }, ESCALATION_COOLDOWN_MS);
    setSelectedEscalation(null);
  };

  const handleEscalationSnooze = () => {
    if (!selectedEscalation) {
      return;
    }
    const escalationId = selectedEscalation.id;
    dismissedUntilRef.current.set(
      escalationId,
      Date.now() + ESCALATION_SNOOZE_MS,
    );
    setTimeout(() => {
      shownEscalationIdsRef.current.delete(escalationId);
    }, ESCALATION_SNOOZE_MS);
    setSelectedEscalation(null);
    addToast("Escalation snoozed for 5 minutes", "info");
  };

  const handleIssueClick = (issue) => {
    setSelectedIssue(issue);
  };

  const handleSolvedIssueClick = (issue) => {
    setSelectedSolvedIssue(issue);
  };

  const selectedWorkflow = selectedIssue
    ? workflows.find((wf) => wf.id === selectedIssue.workflow_id) || null
    : null;

  const selectedIssueAuditEntry = selectedIssue
    ? auditLog.find(
        (entry) =>
          entry.workflow_id === selectedIssue.workflow_id &&
          entry.step_id === selectedIssue.step_id,
      ) || null
    : null;

  const selectedIssueStillActive = selectedIssue
    ? activeIssues.some(
        (issue) =>
          issue.workflow_id === selectedIssue.workflow_id &&
          issue.step_id === selectedIssue.step_id,
      )
    : false;

  const highlightedWorkflowIds = [
    ...new Set(activeIssues.map((issue) => issue.workflow_id)),
  ];

  return (
    <div className="app">
      {/* Header */}
      <div className="header">
        <h1>Process Autopsy Agent</h1>
        <div className="header-actions">
          {(resolutionLocked || activeIssues.length > 0) && (
            <span className="resolving-chip">Agent resolving issues...</span>
          )}
          <button
            className="break-it-btn"
            onClick={handleBreakIt}
            disabled={loading || resolutionLocked}
          >
            {resolutionLocked ? "Resolving..." : "⚡ Break It"}
          </button>
          <button className="stop-agent-btn" onClick={handleStopAgent}>
            ◼ Stop Agent
          </button>
        </div>
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
          <WorkflowHeatmap
            key={`heatmap-${heatmapRevision}-${currentRunId || "none"}`}
            workflows={workflows}
            activeIssues={activeIssues}
            highlightedWorkflowIds={highlightedWorkflowIds}
            forceGreenForNonHighlighted={currentRunWorkflowIds.length > 0}
          />
        </div>

        {/* Middle: Active + Solved Issues */}
        <div className="middle-panel">
          <RiskQueue issues={activeIssues} onIssueClick={handleIssueClick} />
          <SolvedIssues
            issues={solvedIssues}
            onIssueClick={handleSolvedIssueClick}
          />
        </div>

        {/* Right: Audit Trail */}
        <div className="right-panel">
          <AuditTrail logs={auditLog} />
        </div>
      </div>

      {/* Bottom: Stall Insights */}
      <div className="stall-insights-section">
        <StallInsights patterns={stallPatterns} />
      </div>

      {/* Escalation Modal */}
      {ENABLE_ESCALATION && selectedEscalation && (
        <EscalationPreview
          escalation={selectedEscalation}
          onMarkResolved={() => handleMarkResolved(selectedEscalation.id)}
          onSnooze={handleEscalationSnooze}
          onClose={handleEscalationClose}
        />
      )}

      {selectedIssue && (
        <IssueDetails
          issue={selectedIssue}
          workflow={selectedWorkflow}
          auditEntry={selectedIssueAuditEntry}
          stallPatterns={stallPatterns}
          isStillActive={selectedIssueStillActive}
          onClose={() => setSelectedIssue(null)}
        />
      )}

      {selectedSolvedIssue && (
        <SolvedIssueDetails
          issue={selectedSolvedIssue}
          auditLog={auditLog}
          workflow={
            workflows.find((wf) => wf.id === selectedSolvedIssue.workflow_id) ||
            null
          }
          onClose={() => setSelectedSolvedIssue(null)}
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
