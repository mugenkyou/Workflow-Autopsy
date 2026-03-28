console.log("Phase 6 Dashboard loading...");
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

function getFailureTypeColor(failureType) {
    if (!failureType) return '#6b7280';
    const f = failureType.toLowerCase();
    if (f === 'stall') return '#8b5cf6';
    if (f === 'duplicate') return '#ef4444';
    if (f === 'sla_breach') return '#f59e0b';
    return '#6b7280';
}

function getRiskRowBackground(riskScore) {
    if (riskScore > 50000) return '#7f1d1d';
    if (riskScore > 10000) return '#7c2d12';
    return '#1f2937';
}

// ============================================================================
// Global State & Polling
// ============================================================================

let workflowsCache = [];
let auditCache = [];
let activeIssuesCache = [];

async function pollWorkflows() {
    try {
        const resp = await fetch('http://localhost:8000/workflows');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        workflowsCache = Array.isArray(data) ? data : [];
    } catch (err) {
        console.error('Workflows fetch error:', err);
    }
}

async function pollAuditLog() {
    try {
        const resp = await fetch('http://localhost:8000/audit-log');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        auditCache = Array.isArray(data) ? data : [];
    } catch (err) {
        console.error('Audit fetch error:', err);
    }
}

async function pollActiveIssues() {
    try {
        const resp = await fetch('http://localhost:8000/active-issues');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        activeIssuesCache = (data.issues || []).sort((a, b) => b.risk_score - a.risk_score);
    } catch (err) {
        console.error('Active issues fetch error:', err);
    }
}

// ============================================================================
// Components
// ============================================================================

function Toast({ message, type = 'info', visible = true, onClose }) {
    if (!visible) return null;
    
    const bgColor = type === 'error' ? '#7f1d1d' : type === 'success' ? '#064e3b' : '#1e40af';
    const borderColor = type === 'error' ? '#991b1b' : type === 'success' ? '#047857' : '#1e40af';
    const textColor = type === 'error' ? '#fca5a5' : type === 'success' ? '#6ee7b7' : '#93c5fd';
    
    useEffect(() => {
        const timer = setTimeout(onClose, 4000);
        return () => clearTimeout(timer);
    }, [onClose]);
    
    return (
        <div style={{
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            background: bgColor,
            border: `1px solid ${borderColor}`,
            borderRadius: '6px',
            padding: '12px 16px',
            color: textColor,
            fontSize: '13px',
            zIndex: 1000,
            animation: 'slideIn 0.3s ease',
            maxWidth: '300px'
        }}>
            {message}
        </div>
    );
}

function RiskQueue({ issues, totalExposure }) {
    const [resolvedIds, setResolvedIds] = useState(new Set());
    
    return (
        <div style={{ padding: '16px', borderTop: '1px solid #334155' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <h3 style={{ margin: 0, fontSize: '14px', color: '#f1f5f9', fontWeight: 'bold' }}>
                    Active Issues
                </h3>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                    Exposure: {formatCurrency(totalExposure)}
                </span>
            </div>
            
            {issues.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '20px', color: '#10b981' }}>
                    <span style={{ fontSize: '24px' }}>✓</span>
                    <p style={{ margin: '8px 0 0 0', fontSize: '13px' }}>All issues resolved</p>
                </div>
            ) : (
                <div style={{ space: '6px' }}>
                    {issues.map((issue, idx) => (
                        <div
                            key={issue.step_id}
                            style={{
                                background: getRiskRowBackground(issue.risk_score),
                                border: '1px solid #475569',
                                borderRadius: '4px',
                                padding: '10px',
                                marginBottom: '6px',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                fontSize: '12px',
                                animation: 'slideIn 0.3s ease'
                            }}
                        >
                            <div style={{ flex: 1 }}>
                                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                                    <span style={{ fontWeight: 'bold', color: '#9ca3af', fontSize: '11px' }}>#{idx + 1}</span>
                                    <span style={{
                                        background: getFailureTypeColor(issue.failure_type),
                                        color: 'white',
                                        padding: '2px 6px',
                                        borderRadius: '3px',
                                        fontSize: '10px',
                                        fontWeight: 'bold'
                                    }}>
                                        {issue.failure_type}
                                    </span>
                                    <span style={{ color: '#cbd5e1', fontWeight: 'bold' }}>
                                        {issue.step_name}
                                    </span>
                                </div>
                                <p style={{ margin: '2px 0', fontSize: '11px', color: '#9ca3af' }}>
                                    {issue.hours_overdue}h overdue • {issue.assignee}
                                </p>
                            </div>
                            <span style={{
                                color: '#86efac',
                                fontWeight: 'bold',
                                fontSize: '13px',
                                minWidth: '80px',
                                textAlign: 'right'
                            }}>
                                {formatCurrency(issue.risk_score)}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

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
    const [activeIssues, setActiveIssues] = useState([]);
    const [selectedWorkflow, setSelectedWorkflow] = useState(null);
    const [toastVisible, setToastVisible] = useState(false);
    const [toastMessage, setToastMessage] = useState('');
    const [toastType, setToastType] = useState('info');
    const [breakItLoading, setBreakItLoading] = useState(false);
    const [totalExposure, setTotalExposure] = useState(0);
    
    const showToast = (message, type = 'info') => {
        setToastMessage(message);
        setToastType(type);
        setToastVisible(true);
    };
    
    const handleBreakIt = async () => {
        setBreakItLoading(true);
        try {
            const resp = await fetch('http://localhost:8000/inject-chaos', { method: 'POST' });
            if (resp.ok) {
                showToast('3 failures injected — agents triaging', 'info');
                // Re-poll immediately
                setTimeout(() => {
                    pollActiveIssues();
                    setActiveIssues([...activeIssuesCache]);
                }, 500);
            } else {
                showToast('Failed to inject chaos', 'error');
            }
        } catch (err) {
            showToast(`Error: ${err.message}`, 'error');
        } finally {
            setBreakItLoading(false);
        }
    };
    
    useEffect(() => {
        console.log("App mounted, starting polling...");
        
        const loadData = async () => {
            await pollWorkflows();
            await pollAuditLog();
            await pollActiveIssues();
            setWorkflows([...workflowsCache]);
            setAuditLog([...auditCache]);
            setActiveIssues([...activeIssuesCache]);
            setTotalExposure(activeIssuesCache.reduce((sum, issue) => sum + issue.risk_score, 0));
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
        
        const issuesInterval = setInterval(() => {
            pollActiveIssues();
            setActiveIssues([...activeIssuesCache]);
            setTotalExposure(activeIssuesCache.reduce((sum, issue) => sum + issue.risk_score, 0));
        }, 5000);
        
        return () => {
            clearInterval(workflowInterval);
            clearInterval(auditInterval);
            clearInterval(issuesInterval);
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
            {/* Header with Break It Button */}
            <div style={{
                background: '#1e293b',
                borderBottom: '1px solid #334155',
                padding: '12px 20px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexShrink: 0
            }}>
                <div>
                    <h1 style={{ margin: '0 0 4px 0', fontSize: '20px', fontWeight: 'bold' }}>
                        Process Autopsy Agent Dashboard
                    </h1>
                    <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                        Real-time autonomous workflow monitoring
                    </p>
                </div>
                
                <button
                    onClick={handleBreakIt}
                    disabled={breakItLoading}
                    style={{
                        background: breakItLoading ? '#dc2626' : '#ef4444',
                        color: 'white',
                        border: 'none',
                        padding: '10px 16px',
                        borderRadius: '6px',
                        cursor: breakItLoading ? 'wait' : 'pointer',
                        fontWeight: 'bold',
                        fontSize: '13px',
                        display: 'flex',
                        gap: '6px',
                        alignItems: 'center',
                        transition: 'all 0.3s ease',
                        opacity: breakItLoading ? 0.7 : 1
                    }}
                >
                    ⚡ {breakItLoading ? 'Injecting...' : 'Break It'}
                </button>
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
                
                {/* Right Panel: Audit Trail + Risk Queue (40%) */}
                <div style={{
                    flex: '1',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                    background: '#0f172a'
                }}>
                    {/* Audit Trail */}
                    <div style={{
                        flex: '1',
                        borderBottom: '1px solid #334155',
                        overflow: 'hidden'
                    }}>
                        <AuditTrail auditLog={auditLog} />
                    </div>
                    
                    {/* Risk Queue */}
                    <div style={{
                        flex: '1',
                        overflow: 'y-auto',
                        borderTop: '1px solid #334155'
                    }}>
                        <RiskQueue issues={activeIssues} totalExposure={totalExposure} />
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
            
            {/* Toast Notification */}
            <Toast
                message={toastMessage}
                type={toastType}
                visible={toastVisible}
                onClose={() => setToastVisible(false)}
            />
        </div>
    );
}

// ============================================================================
// Render
// ============================================================================

console.log("Rendering Phase 6 app...");
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
