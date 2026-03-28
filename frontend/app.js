console.log("Phase 5 Dashboard loading...");
const { useState, useEffect } = React;

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
    if (!status) return '#666666';
    const s = status.toLowerCase();
    if (s === 'on_track' || s === 'in_progress') return '#10b981';
    if (s === 'at_risk') return '#f59e0b';
    if (s === 'stalled' || s === 'breached' || s === 'duplicate_hold') return '#ef4444';
    return '#666666';
}

function getStatusBorderColor(status) {
    if (!status) return 'transparent';
    const s = status.toLowerCase();
    if (s === 'stalled' || s === 'breached') return '#ef4444';
    if (s === 'at_risk') return '#f59e0b';
    return 'transparent';
}

// ============================================================================
// Global State & Polling
// ============================================================================

let workflowsCache = [];
let auditCache = [];

async function pollWorkflows() {
    try {
        const resp = await fetch('http://localhost:8000/workflows');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        workflowsCache = Array.isArray(data) ? data : [];
        console.log("Workflows fetched:", workflowsCache.length);
    } catch (err) {
        console.error("Workflows fetch error:", err);
    }
}

async function pollAuditLog() {
    try {
        const resp = await fetch('http://localhost:8000/audit-log');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        auditCache = Array.isArray(data) ? data : [];
        console.log("Audit entries fetched:", auditCache.length);
    } catch (err) {
        console.error("Audit fetch error:", err);
    }
}

// ============================================================================
// Components
// ============================================================================

function WorkflowCard({ workflow, onClick }) {
    const borderColor = getStatusBorderColor(workflow.status);
    
    return (
        <div
            onClick={onClick}
            style={{
                background: '#1e293b',
                border: `1px solid #334155`,
                borderLeft: borderColor !== 'transparent' ? `4px solid ${borderColor}` : '1px solid #334155',
                borderRadius: '8px',
                padding: '16px',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                userSelect: 'none',
                transform: 'translateY(0)',
            }}
            onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-4px)';
                e.currentTarget.style.boxShadow = '0 10px 25px rgba(0,0,0,0.3)';
                e.currentTarget.style.borderColor = '#475569';
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = 'none';
                e.currentTarget.style.borderColor = '#334155';
            }}
        >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ fontSize: '10px', color: '#64748b' }}>{workflow.id?.substring(0, 8)}...</span>
                <span style={{
                    display: 'inline-block',
                    background: getStatusColor(workflow.status),
                    color: 'white',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 'bold'
                }}>
                    {workflow.status}
                </span>
            </div>
            
            <h3 style={{ margin: '0 0 6px 0', fontSize: '14px', fontWeight: 'bold', color: '#f1f5f9' }}>
                {workflow.name}
            </h3>
            <p style={{ margin: '4px 0', fontSize: '12px', color: '#cbd5e1' }}>
                {workflow.vendor}
            </p>
            <p style={{ margin: '8px 0', fontSize: '14px', color: '#86efac', fontWeight: 'bold' }}>
                {formatCurrency(workflow.po_amount)}
            </p>
            
            {workflow.current_step && (
                <p style={{ margin: '6px 0', fontSize: '11px', color: '#94a3b8' }}>
                    Step: {workflow.current_step.step_name}
                </p>
            )}
            
            <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #334155' }}>
                <p style={{ margin: '0', fontSize: '11px', color: '#64748b' }}>
                    {formatTimeAgo(workflow.created_at)}
                </p>
            </div>
        </div>
    );
}

function WorkflowHeatmap({ workflows, onSelectWorkflow }) {
    return (
        <div style={{ height: '100%', overflowY: 'auto', padding: '16px' }}>
            <h2 style={{ margin: '0 0 16px 0', fontSize: '18px', color: '#f1f5f9' }}>Workflow Heatmap</h2>
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: '12px'
            }}>
                {workflows.length === 0 ? (
                    <p style={{ color: '#64748b' }}>No workflows loaded</p>
                ) : (
                    workflows.map(wf => (
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
        .slice(0, 5);
    
    return (
        <>
            {isOpen && (
                <div
                    style={{
                        position: 'fixed',
                        inset: 0,
                        background: 'rgba(0, 0, 0, 0.5)',
                        zIndex: 40,
                        transition: 'opacity 0.3s ease'
                    }}
                    onClick={onClose}
                />
            )}
            
            <div
                style={{
                    position: 'fixed',
                    right: 0,
                    top: 0,
                    height: '100%',
                    width: '380px',
                    background: '#1e293b',
                    borderLeft: '1px solid #334155',
                    boxShadow: '0 0 30px rgba(0,0,0,0.5)',
                    zIndex: 50,
                    transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
                    transition: 'transform 0.3s ease',
                    overflowY: 'auto'
                }}
            >
                <div style={{ padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h2 style={{ margin: 0, fontSize: '16px', color: '#f1f5f9' }}>{workflow.name}</h2>
                        <button
                            onClick={onClose}
                            style={{
                                background: 'transparent',
                                border: 'none',
                                color: '#94a3b8',
                                fontSize: '20px',
                                cursor: 'pointer',
                                padding: '0',
                                width: '24px',
                                height: '24px'
                            }}
                        >
                            ×
                        </button>
                    </div>
                    
                    <div style={{ marginBottom: '20px', paddingBottom: '16px', borderBottom: '1px solid #334155' }}>
                        <div style={{ marginBottom: '10px' }}>
                            <p style={{ margin: '0 0 4px 0', fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Vendor</p>
                            <p style={{ margin: 0, fontSize: '14px', color: '#e2e8f0' }}>{workflow.vendor}</p>
                        </div>
                        
                        <div style={{ marginBottom: '10px' }}>
                            <p style={{ margin: '0 0 4px 0', fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>PO Amount</p>
                            <p style={{ margin: 0, fontSize: '14px', color: '#86efac', fontWeight: 'bold' }}>
                                {formatCurrency(workflow.po_amount)}
                            </p>
                        </div>
                        
                        <div>
                            <p style={{ margin: '0 0 4px 0', fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Status</p>
                            <span style={{
                                display: 'inline-block',
                                background: getStatusColor(workflow.status),
                                color: 'white',
                                padding: '4px 8px',
                                borderRadius: '4px',
                                fontSize: '12px',
                                fontWeight: 'bold'
                            }}>
                                {workflow.status}
                            </span>
                        </div>
                    </div>
                    
                    {workflow.current_step && (
                        <div style={{ marginBottom: '20px', paddingBottom: '16px', borderBottom: '1px solid #334155' }}>
                            <h3 style={{ margin: '0 0 10px 0', fontSize: '13px', color: '#e2e8f0', fontWeight: 'bold' }}>Current Step</h3>
                            <div style={{ background: '#0f172a', borderRadius: '6px', padding: '12px' }}>
                                <p style={{ margin: '0 0 6px 0', fontSize: '12px', color: '#e2e8f0' }}>
                                    <strong>{workflow.current_step.step_name}</strong>
                                </p>
                                {workflow.current_step.assignee && (
                                    <p style={{ margin: '4px 0', fontSize: '11px', color: '#94a3b8' }}>
                                        Assignee: {workflow.current_step.assignee}
                                    </p>
                                )}
                                <p style={{ margin: '4px 0', fontSize: '11px' }}>
                                    Status: <span style={{ color: getStatusColor(workflow.current_step.status) }}>
                                        {workflow.current_step.status}
                                    </span>
                                </p>
                            </div>
                        </div>
                    )}
                    
                    {workflowAuditEntries.length > 0 && (
                        <div>
                            <h3 style={{ margin: '0 0 10px 0', fontSize: '13px', color: '#e2e8f0', fontWeight: 'bold' }}>Recent Activity</h3>
                            <div style={{ space: '8px' }}>
                                {workflowAuditEntries.map((entry, idx) => (
                                    <div key={idx} style={{
                                        background: '#0f172a',
                                        borderRadius: '6px',
                                        padding: '10px',
                                        marginBottom: '8px',
                                        borderLeft: `3px solid ${getStatusColor(entry.agent_name)}`
                                    }}>
                                        <p style={{ margin: '0 0 4px 0', fontSize: '11px', color: '#94a3b8' }}>
                                            {formatTimeAgo(entry.timestamp)}
                                        </p>
                                        <p style={{ margin: '0 0 2px 0', fontSize: '12px', color: '#e2e8f0', fontWeight: 'bold' }}>
                                            {entry.action}
                                        </p>
                                        {entry.reasoning && (
                                            <p style={{ margin: '4px 0 0 0', fontSize: '11px', color: '#cbd5e1' }}>
                                                {entry.reasoning}
                                            </p>
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

function AuditTrail({ auditLog }) {
    return (
        <div style={{ height: '100%', overflowY: 'auto', padding: '16px' }}>
            <h3 style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#f1f5f9', fontWeight: 'bold' }}>Audit Trail</h3>
            <div style={{ space: '8px' }}>
                {auditLog.length === 0 ? (
                    <p style={{ fontSize: '12px', color: '#64748b' }}>No activity yet</p>
                ) : (
                    auditLog.slice(0, 10).map((entry, idx) => (
                        <div key={idx} style={{
                            background: '#0f172a',
                            borderRadius: '6px',
                            padding: '10px',
                            marginBottom: '8px',
                            fontSize: '11px'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                <span style={{ color: '#f59e0b', fontWeight: 'bold' }}>
                                    {entry.agent_name || 'System'}
                                </span>
                                <span style={{ color: '#64748b' }}>
                                    {formatTimeAgo(entry.timestamp)}
                                </span>
                            </div>
                            <p style={{ margin: '4px 0 0 0', color: '#e2e8f0' }}>
                                {entry.action}
                            </p>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

function App() {
    const [workflows, setWorkflows] = useState([]);
    const [auditLog, setAuditLog] = useState([]);
    const [selectedWorkflow, setSelectedWorkflow] = useState(null);
    const [error, setError] = useState(null);
    
    useEffect(() => {
        console.log("App mounted, starting polling...");
        
        const loadData = async () => {
            await pollWorkflows();
            await pollAuditLog();
            setWorkflows([...workflowsCache]);
            setAuditLog([...auditCache]);
        };
        
        loadData();
        
        const workflowInterval = setInterval(() => {
            pollWorkflows();
            setWorkflows([...workflowsCache]);
        }, 5000);
        
        const auditInterval = setInterval(() => {
            pollAuditLog();
            setAuditLog([...auditCache]);
        }, 3000);
        
        return () => {
            clearInterval(workflowInterval);
            clearInterval(auditInterval);
        };
    }, []);
    
    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            height: '100vh',
            background: '#0f172a',
            color: '#e2e8f0'
        }}>
            {/* Header */}
            <div style={{
                background: '#1e293b',
                borderBottom: '1px solid #334155',
                padding: '16px 20px',
                flexShrink: 0
            }}>
                <h1 style={{ margin: '0 0 4px 0', fontSize: '20px', fontWeight: 'bold' }}>
                    Process Autopsy Agent Dashboard
                </h1>
                <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                    Real-time autonomous workflow monitoring
                </p>
            </div>
            
            {/* Main Content */}
            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                {/* Left: Workflow Heatmap (60%) */}
                <div style={{
                    flex: '1.5',
                    borderRight: '1px solid #334155',
                    overflow: 'hidden',
                    background: '#0f172a'
                }}>
                    <WorkflowHeatmap
                        workflows={workflows}
                        onSelectWorkflow={setSelectedWorkflow}
                    />
                </div>
                
                {/* Right: Audit Trail + Agent Feed (40%) */}
                <div style={{
                    flex: '1',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden'
                }}>
                    {/* Audit Trail */}
                    <div style={{
                        flex: '1',
                        borderBottom: '1px solid #334155',
                        overflow: 'hidden',
                        background: '#0f172a'
                    }}>
                        <AuditTrail auditLog={auditLog} />
                    </div>
                    
                    {/* Agent Feed Placeholder */}
                    <div style={{
                        flex: '1',
                        overflow: 'hidden',
                        background: '#0f172a',
                        padding: '16px'
                    }}>
                        <h3 style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#f1f5f9', fontWeight: 'bold' }}>
                            Agent Feed
                        </h3>
                        <div style={{ color: '#64748b', fontSize: '12px' }}>
                            Live agent activity will appear here
                        </div>
                    </div>
                </div>
            </div>
            
            {/* Detail Drawer */}
            <DetailDrawer
                workflow={selectedWorkflow}
                auditLog={auditLog}
                isOpen={!!selectedWorkflow}
                onClose={() => setSelectedWorkflow(null)}
            />
        </div>
    );
}

// ============================================================================
// Render
// ============================================================================

console.log("Rendering app...");
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
