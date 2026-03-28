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
// Components
// ============================================================================

function AuditTrail() {
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
    
    useEffect(() => {
        // Initialize polling on mount
        initializePolling();
        setMounted(true);
    }, []);
    
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
                {/* Audit Trail (70%) */}
                <div className="flex-1 border-r border-slate-700 overflow-hidden">
                    <div className="px-4 py-2 bg-slate-800 border-b border-slate-700">
                        <h2 className="text-sm font-semibold text-white">Audit Trail</h2>
                    </div>
                    <AuditTrail />
                </div>
                
                {/* Agent Feed (30%) */}
                <div className="w-1/3 overflow-hidden">
                    <AgentFeed />
                </div>
            </div>
        </div>
    );
}

// ============================================================================
// Render
// ============================================================================

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
