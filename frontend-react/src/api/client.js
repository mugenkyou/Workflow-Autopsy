import axios from "axios";

const API_BASE = "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

export const fetchWorkflows = () => api.get("/workflows");
export const fetchAuditLog = () => api.get("/audit-log");
export const fetchActiveIssues = () => api.get("/active-issues");
export const fetchEscalations = () => api.get("/escalations");
export const fetchStallPatterns = () => api.get("/stall-patterns");
export const injectChaos = () => api.post("/inject-chaos");
export const stopAgent = () => api.post("/stop-agent");
export const markEscalationResolved = (escalationId) =>
  api.post("/mark-resolved", { escalation_id: escalationId });
export const runCycle = () => api.post("/run-cycle");
