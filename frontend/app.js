const { useState, useEffect, useRef } = React;

// ============================================================================
// State Management Module
// ============================================================================

let auditLogData = [];
let workflowsData = [];
let lastActivityTime = Date.now();
let updateSubscribers = [];

function notifySubscribers() {
    updateSubscribers.forEach(cb => cb());
}

function subscribeToUpdates(callback) {
    updateSubscribers.push(callback);
}

function getAuditLog() {
    return [...auditLogData];
}

function getWorkflows() {
    return [...workflowsData];
}

function getLastActivityTime() {
    return lastActivityTime;
}

// ============================================================================
// Polling Module
// ============================================================================

const API_BASE = 'http://localhost:8000';

async function pollAuditLog() {
    try {
        const resp = await fetch(`${API_BASE}/audit-log`);
        if (!resp.ok) return;
        
        const data = await resp.json();
        
        // Detect new entries by id
        const existingIds = new Set(auditLogData.map(e => e.id));
        const newEntries = data.filter(e => !existingIds.has(e.id));
        
        if (newEntries.length > 0) {
            auditLogData = data;
            lastActivityTime = Date.now();
            notifySubscribers();
        }
    } catch (err) {
        console.warn('Audit log poll failed:', err);
    }
}

async function pollWorkflows() {
    try {
        const resp = await fetch(`${API_BASE}/workflows`);
        if (!resp.ok) return;
        
        const data = await resp.json();
        workflowsData = data;
    } catch (err) {
        console.warn('Workflows poll failed:', err);
    }
}

async function runCycle() {
    try {
        const resp = await fetch(`${API_BASE}/run-cycle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        if (!resp.ok) return;
        
        const result = await resp.json();
        if (result.success) {
            lastActivityTime = Date.now();
            // Trigger audit log poll to fetch new entries
            pollAuditLog();
        }
    } catch (err) {
        console.warn('Cycle run failed:', err);
    }
}

// Start polling
function initializePolling() {
    // Initial fetch
    pollAuditLog();
    pollWorkflows();
    
    // Poll audit log every 3 seconds
    setInterval(pollAuditLog, 3000);
    
    // Poll workflows every 5 seconds
    setInterval(pollWorkflows, 5000);
    
    // Run cycle every 30 seconds
    setInterval(runCycle, 30000);
}

// ============================================================================
// Utility Functions
// ============================================================================

function formatTimeAgo(isoString) {
    if (!isoString) return 'N/A';
    try {
        const date = new Date(isoString);
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);
        
        if (seconds < 60) return `${seconds}s ago`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        return `${Math.floor(seconds / 86400)}d ago`;
    } catch {
        return 'N/A';
    }
}

function formatCurrency(amount) {
    if (!amount && amount !== 0) return '₹0';
    const num = parseFloat(amount);
    return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function getStatusColor(status) {
    if (!status) return 'bg-gray-500';
    const s = status.toLowerCase();
    if (s === 'on_track' || s === 'in_progress') return 'bg-green-600';
    if (s === 'at_risk') return 'bg-amber-500';
    if (s === 'stalled' || s === 'breached' || s === 'duplicate_hold') return 'bg-red-600';
    return 'bg-gray-500';
}

function getStatusTextColor(status) {
    if (!status) return 'text-gray-300';
    const s = status.toLowerCase();
    if (s === 'on_track' || s === 'in_progress') return 'text-green-300';
    if (s === 'at_risk') return 'text-amber-300';
    if (s === 'stalled' || s === 'breached' || s === 'duplicate_hold') return 'text-red-300';
    return 'text-gray-300';
}

// ============================================================================
// Components
// ============================================================================

function WorkflowCard({ workflow, onClick }) {
    const getBorderClass = () => {
        if (!workflow.status) return '';
        const s = workflow.status.toLowerCase();
        if (s === 'breached' || s === 'stalled') return 'border-l-4 border-l-red-600';
        if (s === 'at_risk') return 'border-l-4 border-l-amber-500';
        return '';
    };
    
    return (
        <div
            onClick={onClick}
            className={`bg-slate-800 border border-slate-700 rounded-lg p-4 cursor-pointer transition-all hover:translate-y-[-4px] hover:shadow-lg hover:border-slate-600 ${getBorderClass()}`}
        >
            {/* Header */}
            <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-gray-500">{workflow.id?.substring(0, 8)}...</span>
                <span className={`text-xs font-bold ${getStatusTextColor(workflow.status)} ${getStatusColor(workflow.status)} px-2 py-1 rounded`}>
                    {workflow.status || 'unknown'}
                </span>
            </div>
            
            {/* Content */}
            <div className="mb-3">
                <p className="font-semibold text-white truncate">{workflow.name || 'N/A'}</p>
                <p className="text-xs text-gray-400">{workflow.vendor || 'N/A'}</p>
                <p className="text-sm font-semibold text-green-300 mt-1">{formatCurrency(workflow.po_amount)}</p>
            </div>
            
            {/* Progress */}
            <div className="mb-2">
                <div className="bg-slate-700 rounded h-2 overflow-hidden">
                    <div
                        className="bg-blue-500 h-full transition-all"
                        style={{ width: '60%' }}
                    />
                </div>
                <p className="text-xs text-gray-500 mt-1">{workflow.current_step?.step_name || 'N/A'}</p>
            </div>
            
            {/* Time */}
            <p className="text-xs text-gray-500">{formatTimeAgo(workflow.created_at)}</p>
        </div>
    );
}

function WorkflowHeatmap({ workflows, onSelectWorkflow }) {
    const [workflowList, setWorkflowList] = useState([]);
    
    useEffect(() => {
        setWorkflowList(workflows);
    }, [workflows]);
    
    return (
        <div className="h-full overflow-y-auto p-4">
            <h2 className="text-lg font-bold text-white mb-4">Workflow Heatmap</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 auto-rows-max">
                {workflowList.length === 0 ? (
                    <p className="text-gray-500">No workflows loaded</p>
                ) : (
                    workflowList.map(wf => (
                        <WorkflowCard
                            key={wf.id}
                            workflow={wf}
                            onClick={() => onSelectWorkflow(wf)}
                        />
                    ))
                )}
            </div>
        </div>
    );
}

function DetailDrawer({ workflow, auditLog, isOpen, onClose }) {
    if (!workflow) return null;
    
    const workflowAuditEntries = auditLog
        .filter(entry => entry.workflow_id === workflow.id)
        .slice(0, 3);
    
    return (
        <>
            {/* Overlay */}
            {isOpen && (
                <div
                    className="fixed inset-0 bg-black bg-opacity-50 z-40 transition-opacity"
                    onClick={onClose}
                />
            )}
            
            {/* Drawer */}
            <div
                className={`fixed right-0 top-0 h-full w-96 bg-slate-800 border-l border-slate-700 shadow-2xl transform transition-transform z-50 overflow-y-auto ${
                    isOpen ? 'translate-x-0' : 'translate-x-full'
                }`}
            >
                <div className="p-6">
                    {/* Header */}
                    <div className="flex justify-between items-center mb-6">
                        <h2 className="text-xl font-bold text-white">{workflow.name}</h2>
                        <button
                            onClick={onClose}
                            className="text-gray-400 hover:text-white transition-colors"
                        >
                            ✕
                        </button>
                    </div>
                    
                    {/* Workflow Details */}
                    <div className="space-y-3 mb-6 pb-6 border-b border-slate-700">
                        <div>
                            <p className="text-xs text-gray-500 uppercase">Vendor</p>
                            <p className="text-white font-semibold">{workflow.vendor}</p>
                        </div>
                        <div>
                            <p className="text-xs text-gray-500 uppercase">PO Amount</p>
                            <p className="text-green-300 font-semibold">{formatCurrency(workflow.po_amount)}</p>
                        </div>
                        <div>
                            <p className="text-xs text-gray-500 uppercase">Status</p>
                            <span className={`inline-block text-xs font-bold ${getStatusTextColor(workflow.status)} ${getStatusColor(workflow.status)} px-3 py-1 rounded mt-1`}>
                                {workflow.status}
                            </span>
                        </div>
                    </div>
                    
                    {/* Current Step */}
                    {workflow.current_step && (
                        <div className="mb-6 pb-6 border-b border-slate-700">
                            <h3 className="text-sm font-semibold text-white mb-3">Current Step</h3>
                            <div className="bg-slate-700 rounded p-3 space-y-2">
                                <div>
                                    <p className="text-xs text-gray-500">Step</p>
                                    <p className="text-white text-sm font-semibold">{workflow.current_step.step_name}</p>
                                </div>
                                <div className="flex justify-between">
                                    <div>
                                        <p className="text-xs text-gray-500">Assignee</p>
                                        <p className="text-white text-sm">{workflow.current_step.assignee || 'N/A'}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-gray-500">Status</p>
                                        <p className={`text-sm font-semibold ${getStatusTextColor(workflow.current_step.status)}`}>
                                            {workflow.current_step.status}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                    
                    {/* Audit History */}
                    {workflowAuditEntries.length > 0 && (
                        <div>
                            <h3 className="text-sm font-semibold text-white mb-3">Recent Audit</h3>
                            <div className="space-y-2">
                                {workflowAuditEntries.map(entry => (
                                    <div key={entry.id} className="bg-slate-700 rounded p-2 text-xs">
                                        <p className="text-gray-400">{formatTimeAgo(entry.timestamp)}</p>
                                        <p className="text-white font-semibold">{entry.action}</p>
                                        {entry.reasoning && (
                                            <p className="text-gray-400 mt-1">{entry.reasoning}</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
    const [entries, setEntries] = useState([]);
    
    useEffect(() => {
        setEntries(getAuditLog());
        subscribeToUpdates(() => setEntries(getAuditLog()));
    }, []);
    
    const getAgentColor = (agentName) => {
        if (!agentName) return 'bg-gray-600';
        if (agentName.includes('Monitor')) return 'bg-blue-600';
        if (agentName.includes('Diagnosis')) return 'bg-purple-600';
        if (agentName.includes('Action')) return 'bg-green-600';
        if (agentName.includes('Audit')) return 'bg-gray-600';
        return 'bg-gray-500';
    };
    
    const getConfidenceColor = (confidence) => {
        if (!confidence) return 'bg-gray-500';
        if (confidence >= 0.8) return 'bg-green-600';
        if (confidence >= 0.6) return 'bg-amber-500';
        return 'bg-red-600';
    };
    
    const timeAgo = (isoString) => {
        if (!isoString) return 'N/A';
        try {
            const date = new Date(isoString);
            const now = new Date();
            const seconds = Math.floor((now - date) / 1000);
            
            if (seconds < 60) return `${seconds}s ago`;
            if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
            return `${Math.floor(seconds / 3600)}h ago`;
        } catch {
            return 'N/A';
        }
    };
    
    return (
        <div className="h-full overflow-y-auto p-4 space-y-3">
            {entries.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                    No activity yet
                </div>
            ) : (
                entries.map((entry) => (
                    <div key={entry.id} className="slide-in bg-slate-800 rounded-lg p-4 border border-slate-700 hover:border-slate-600 transition-colors">
                        <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <span className={`${getAgentColor(entry.agent_name)} px-2 py-1 rounded text-xs font-semibold text-white`}>
                                    {entry.agent_name || 'System'}
                                </span>
                                <span className="text-xs text-gray-400">{timeAgo(entry.timestamp)}</span>
                            </div>
                        </div>
                        
                        <div className="mb-2">
                            <p className="font-semibold text-white">{entry.action || 'N/A'}</p>
                        </div>
                        
                        {entry.reasoning && (
                            <div className="mb-2">
                                <p className="text-xs text-gray-400">{entry.reasoning}</p>
                            </div>
                        )}
                        
                        {entry.confidence !== null && entry.confidence !== undefined && (
                            <div className="flex items-center gap-2">
                                <div className="w-16">
                                    <div className="bg-slate-700 rounded h-2 overflow-hidden">
                                        <div
                                            className={`h-full ${getConfidenceColor(entry.confidence)}`}
                                            style={{ width: `${Math.min(100, entry.confidence * 100)}%` }}
                                        />
                                    </div>
                                </div>
                                <span className="text-xs text-gray-400">{(entry.confidence * 100).toFixed(0)}%</span>
                            </div>
                        )}
                    </div>
                ))
            )}
        </div>
    );
}

function AgentFeed() {
    const [feedItems, setFeedItems] = useState([]);
    const [isLive, setIsLive] = useState(false);
    
    useEffect(() => {
        const update = () => {
            const entries = getAuditLog().slice(0, 20);
            setFeedItems(entries);
            
            // Check if activity is recent
            const timeSinceActivity = Date.now() - getLastActivityTime();
            setIsLive(timeSinceActivity < 5000);
        };
        
        update();
        subscribeToUpdates(update);
        
        // Update live status every second
        const liveCheckInterval = setInterval(() => {
            setIsLive(Date.now() - getLastActivityTime() < 5000);
        }, 1000);
        
        return () => clearInterval(liveCheckInterval);
    }, []);
    
    return (
        <div className="h-full overflow-y-auto p-4 flex flex-col">
            <div className="flex items-center justify-between mb-4 sticky top-0 bg-slate-900 py-2">
                <h3 className="font-bold text-sm text-white">Agent Feed</h3>
                <div className={`flex items-center gap-2 ${isLive ? 'pulse-green' : ''}`}>
                    <div className={`w-2 h-2 rounded-full ${isLive ? 'bg-green-500' : 'bg-gray-500'}`} />
                    <span className="text-xs font-semibold">{isLive ? 'LIVE' : 'IDLE'}</span>
                </div>
            </div>
            
            <div className="space-y-2 flex-1">
                {feedItems.length === 0 ? (
                    <div className="text-center text-gray-500 py-4">
                        Waiting for activity
                    </div>
                ) : (
                    feedItems.map((item, idx) => (
                        <div key={item.id} className="text-xs text-gray-300 py-1 px-2 bg-slate-800 rounded">
                            <span className="font-semibold">{item.agent_name || 'System'}</span>
                            <span className="text-gray-500"> → </span>
                            <span>{item.action || 'action'}</span>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

function App() {
    const [mounted, setMounted] = useState(false);
    const [selectedWorkflow, setSelectedWorkflow] = useState(null);
    const [workflows, setWorkflows] = useState([]);
    const [auditLog, setAuditLog] = useState([]);
    
    useEffect(() => {
        // Initialize polling on mount
        initializePolling();
        
        // Subscribe to updates
        subscribeToUpdates(() => {
            setWorkflows(getWorkflows());
            setAuditLog(getAuditLog());
        });
        
        // Initial data load
        setWorkflows(getWorkflows());
        setAuditLog(getAuditLog());
        
        setMounted(true);
    }, []);
    
    const handleDrawerClose = () => {
        setSelectedWorkflow(null);
    };
    
    if (!mounted) return <div className="text-center py-8">Loading...</div>;
    
    return (
        <div className="flex flex-col h-screen">
            {/* Header */}
            <div className="bg-slate-800 border-b border-slate-700 px-6 py-4">
                <h1 className="text-2xl font-bold text-white">Process Autopsy Agent Dashboard</h1>
                <p className="text-sm text-gray-400">Real-time autonomous workflow monitoring</p>
            </div>
            
            {/* Main Content */}
            <div className="flex flex-1 overflow-hidden">
                {/* Workflow Heatmap (60%) */}
                <div className="w-3/5 border-r border-slate-700 overflow-hidden bg-slate-900">
                    <WorkflowHeatmap
                        workflows={workflows}
                        onSelectWorkflow={setSelectedWorkflow}
                    />
                </div>
                
                {/* Right Panel (40%): AuditTrail + AgentFeed stacked */}
                <div className="w-2/5 flex flex-col overflow-hidden">
                    {/* Audit Trail */}
                    <div className="flex-1 border-b border-slate-700 overflow-hidden flex flex-col">
                        <div className="px-4 py-2 bg-slate-800 border-b border-slate-700 flex-shrink-0">
                            <h2 className="text-sm font-semibold text-white">Audit Trail</h2>
                        </div>
                        <div className="flex-1 overflow-y-auto">
                            <AuditTrail />
                        </div>
                    </div>
                    
                    {/* Agent Feed */}
                    <div className="flex-1 overflow-hidden flex flex-col">
                        <AgentFeed />
                    </div>
                </div>
            </div>
            
            {/* Detail Drawer */}
            <DetailDrawer
                workflow={selectedWorkflow}
                auditLog={auditLog}
                isOpen={!!selectedWorkflow}
                onClose={handleDrawerClose}
            />
        </div>
    );
}

// ============================================================================
// Render
// ============================================================================

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
