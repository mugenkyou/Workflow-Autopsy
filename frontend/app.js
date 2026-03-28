console.log("App.js starting...");

const { useState, useEffect } = React;

function App() {
    const [workflows, setWorkflows] = useState([]);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {
        console.log("App useEffect: loading data");
        loadData();
        // Poll every 5 seconds
        const interval = setInterval(loadData, 5000);
        return () => clearInterval(interval);
    }, []);
    
    async function loadData() {
        try {
            console.log("Fetching workflows...");
            const resp = await fetch('http://localhost:8000/workflows');
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            console.log("Got workflows:", data.length);
            setWorkflows(data);
            setLoading(false);
            setError(null);
        } catch (err) {
            console.error("Error loading workflows:", err);
            setError(String(err));
            setLoading(false);
        }
    }
    
    const getStatusColor = (status) => {
        if (status === 'on_track') return '#059669';
        if (status === 'at_risk') return '#d97706';
        if (status === 'breach' || status === 'breached') return '#dc2626';
        return '#666666';
    };
    
    return (
        <div style={{
            padding: '20px',
            background: '#0f172a',
            color: '#e2e8f0',
            minHeight: '100vh',
            fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
            <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
                <h1 style={{ marginTop: 0, marginBottom: '10px' }}>Process Autopsy Agent Dashboard</h1>
                <p style={{ margin: '0 0 20px 0', color: '#94a3b8', fontSize: '14px' }}>
                    Loaded: {workflows.length} workflows
                    {loading && ' (loading...)'}
                </p>
                
                {error && (
                    <div style={{
                        background: '#7f1d1d',
                        border: '1px solid #991b1b',
                        color: '#fca5a5',
                        padding: '15px',
                        borderRadius: '6px',
                        marginBottom: '20px'
                    }}>
                        <strong>Error:</strong> {error}
                    </div>
                )}
                
                {loading && workflows.length === 0 && (
                    <div style={{ color: '#94a3b8' }}>Loading workflows...</div>
                )}
                
                {workflows.length > 0 && (
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                        gap: '16px'
                    }}>
                        {workflows.map((wf) => (
                            <div key={wf.id} style={{
                                background: '#1e293b',
                                border: '1px solid #334155',
                                borderRadius: '8px',
                                padding: '16px',
                                borderLeft: `4px solid ${getStatusColor(wf.status)}`
                            }}>
                                <h3 style={{ marginTop: 0, marginBottom: '8px', fontSize: '16px' }}>
                                    {wf.name}
                                </h3>
                                <p style={{ margin: '4px 0', fontSize: '13px', color: '#cbd5e1' }}>
                                    <strong>Vendor:</strong> {wf.vendor}
                                </p>
                                <p style={{ margin: '4px 0', fontSize: '13px' }}>
                                    <strong>Amount:</strong> <span style={{ color: '#86efac' }}>₹{wf.po_amount?.toLocaleString('en-IN', {maximumFractionDigits: 0})}</span>
                                </p>
                                <p style={{ margin: '4px 0', fontSize: '13px' }}>
                                    <strong>Status:</strong> <span style={{
                                        display: 'inline-block',
                                        background: getStatusColor(wf.status),
                                        color: 'white',
                                        padding: '2px 8px',
                                        borderRadius: '4px',
                                        fontSize: '12px'
                                    }}>
                                        {wf.status}
                                    </span>
                                </p>
                                {wf.current_step && (
                                    <p style={{ margin: '4px 0', fontSize: '13px', color: '#cbd5e1' }}>
                                        <strong>Step:</strong> {wf.current_step.step_name}
                                    </p>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

console.log("Creating React root...");
const root = ReactDOM.createRoot(document.getElementById('root'));
console.log("Rendering App...");
root.render(<App />);
console.log("App rendered");
