// Main component with human-in-the-loop approval UI, draft preview, and workflow stepper
import React, { useState, useEffect, useRef } from 'react';
import UploadForm from './components/UploadForm';
import ProgressList from './components/ProgressList';
import Stepper, { Step } from './components/Stepper';
import Icon from './components/Icon';
import WorkflowGuide from './components/WorkflowGuide';
import './App.css';

interface Preview {
  type: string;
  title: string;
  pages_count?: number;
  sample_content?: string;
  tables_count?: number;
  analysis?: string;
  compliance?: string;
  risk?: string;
  report_path?: string;
}

interface SessionStatus {
  status: string;
  requires_approval: boolean;
  approval_checkpoint: string | null;
  current_step: string | null;
  preview?: Preview;
  report_available?: boolean;
  report_url?: string;
}

const WORKFLOW_STEPS: Step[] = [
  { key: 'upload', label: 'Upload', icon: 'upload-cloud' },
  { key: 'extraction', label: 'Extraction', icon: 'file-text' },
  { key: 'review', label: 'Review', icon: 'search' },
  { key: 'analysis', label: 'Analysis', icon: 'dollar-sign' },
  { key: 'approval', label: 'Approval', icon: 'bell' },
  { key: 'complete', label: 'Complete', icon: 'check-circle' },
];

const App: React.FC = () => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<string[]>([]);
  const [completed, setCompleted] = useState(false);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [isApproving, setIsApproving] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [extractionApproved, setExtractionApproved] = useState(false);
  const [sidebarTab, setSidebarTab] = useState<'overview' | 'workflow'>('overview');

  // Editable report content
  const [editedAnalysis, setEditedAnalysis] = useState('');
  const [editedCompliance, setEditedCompliance] = useState('');
  const [editedRisk, setEditedRisk] = useState('');
  const editableInitialized = useRef(false);

  // WebSocket reference
  const ws = useRef<WebSocket | null>(null);

  // Handle WebSocket messages
  // Connects to the backend Django Channels consumer to receive real-time updates
  useEffect(() => {
    if (!sessionId) return;
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = process.env.REACT_APP_WS_URL || `${wsProtocol}//${window.location.host}`;
    const wsUrl = `${wsHost}/ws/progress/${sessionId}/`;

    ws.current = new WebSocket(wsUrl);

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.message) {
        setMessages(prev => [...prev, data.message]);
        // Check for approval keywords
        if (data.message.toLowerCase().includes('awaiting') ||
          data.message.toLowerCase().includes('approval')) {
          fetchStatus();
        }
        if (data.message.toLowerCase().includes('completed')) {
          setCompleted(true);
          fetchStatus();
        }
      }
    };

    ws.current.onerror = () => {
      setMessages(prev => [...prev, '⚠️ WebSocket connection error']);
    };

    return () => { ws.current?.close(); };
  }, [sessionId]);

  // Fetch session status
  const fetchStatus = async () => {
    if (!sessionId) return;
    try {
      const res = await fetch(`/api/sessions/${sessionId}/status/`);
      const data = await res.json();
      setStatus(data);

      // Initialize editable fields ONLY ONCE when report preview first appears
      if (data.preview?.type === 'report' && !editableInitialized.current) {
        setEditedAnalysis(data.preview.analysis || '');
        setEditedCompliance(data.preview.compliance || '');
        setEditedRisk(data.preview.risk || '');
        editableInitialized.current = true;
      }

      if (data.status === 'completed') {
        setCompleted(true);
      }
    } catch (err) {
      console.error('Failed to fetch status:', err);
    }
  };

  // Poll status periodically
  useEffect(() => {
    if (!sessionId) return;
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [sessionId]);

  // Query state
  const [userQuery, setUserQuery] = useState('');

  // Upload file and start analysis
  // 1. Uploads file to /api/upload/ -> gets session_id
  // 2. Calls /api/sessions/{id}/start/ with optional user query
  const handleFileUpload = async (file: File) => {
    const data = new FormData();
    data.append('file', file);
    const uploadRes = await fetch('/api/upload/', { method: 'POST', body: data });
    const uploadJson = await uploadRes.json();
    const id = uploadJson.session_id;
    setSessionId(String(id));
    setMessages(['📤 File uploaded successfully']);

    // Pass optional query to start endpoint
    await fetch(`/api/sessions/${id}/start/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: userQuery })
    });
    setMessages(prev => [...prev, '🚀 Analysis started']);
  };

  // Approve checkpoint
  // Sends approval signal to backend to resume workflow.
  // Can include edited content if at 'report_approval' stage.
  const handleApprove = async () => {
    if (!sessionId) return;
    setIsApproving(true);
    const checkpointBeingApproved = status?.approval_checkpoint;

    try {
      // Build request body with edited content if at report_approval checkpoint
      const requestBody: any = { feedback };
      if (checkpointBeingApproved === 'report_approval') {
        requestBody.edited_content = {
          analysis: editedAnalysis,
          compliance: editedCompliance,
          risk: editedRisk
        };
      }

      const res = await fetch(`/api/sessions/${sessionId}/approve/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });
      const data = await res.json();
      setMessages(prev => [...prev, `✅ Approved: ${data.approved_checkpoint}`]);
      setFeedback('');

      if (checkpointBeingApproved === 'extraction_review') {
        setExtractionApproved(true);
      }

      // Reset edited fields
      setEditedAnalysis('');
      setEditedCompliance('');
      setEditedRisk('');

      fetchStatus();
    } catch (err) {
      setMessages(prev => [...prev, '❌ Failed to approve']);
    } finally {
      setIsApproving(false);
    }
  };

  // Get checkpoint display name
  const getCheckpointName = (checkpoint: string | null) => {
    if (!checkpoint) return '';
    const names: Record<string, string> = {
      'extraction_review': 'Document Extraction Review',
      'report_approval': 'Final Report Approval'
    };
    return names[checkpoint] || checkpoint;
  };

  // Derive the active step index for the workflow stepper from session state
  const getActiveStepIndex = (): number => {
    if (!sessionId) return 0;
    if (completed || status?.status === 'completed') return 5;
    if (status?.approval_checkpoint === 'report_approval') return 4;
    if (extractionApproved) return 3;
    if (status?.approval_checkpoint === 'extraction_review') return 2;
    return 1;
  };

  // Render preview section
  // Dynamically renders content based on checkpoint type (extraction vs report)
  const renderPreview = () => {
    if (!status?.preview) return null;
    const preview = status.preview;

    if (preview.type === 'extraction') {
      return (
        <div className="preview-section">
          <h4><Icon name="file-text" size={16} /> {preview.title}</h4>
          <div className="preview-stats">
            <span className="stat">Pages: {preview.pages_count}</span>
            <span className="stat">Tables: {preview.tables_count}</span>
          </div>
          <div className="preview-content">
            <strong>Sample Content:</strong>
            <pre>{preview.sample_content}</pre>
          </div>
        </div>
      );
    }

    if (preview.type === 'report') {
      return (
        <div className="preview-section">
          <h4><Icon name="file-text" size={16} /> {preview.title}</h4>
          <p className="edit-hint">You can edit the content below before approving</p>
          <div className="preview-item">
            <strong><Icon name="dollar-sign" size={14} /> Finance Analysis</strong>
            <textarea
              className="editable-preview"
              value={editedAnalysis}
              onChange={(e) => setEditedAnalysis(e.target.value)}
              rows={6}
            />
          </div>
          <div className="preview-item">
            <strong><Icon name="shield" size={14} /> Compliance Check</strong>
            <textarea
              className="editable-preview"
              value={editedCompliance}
              onChange={(e) => setEditedCompliance(e.target.value)}
              rows={6}
            />
          </div>
          <div className="preview-item">
            <strong><Icon name="bar-chart" size={14} /> Risk Assessment</strong>
            <textarea
              className="editable-preview"
              value={editedRisk}
              onChange={(e) => setEditedRisk(e.target.value)}
              rows={6}
            />
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="page">
      <div className="bg-decoration" aria-hidden="true" />

      <header className="top-nav">
        <div className="top-nav-inner">
          <div className="brand">
            <div className="brand-icon"><Icon name="chart" size={20} /></div>
            <div>
              <h1>Financial Analysis Agent</h1>
              <p className="subtitle">Supervisor Agent Architecture with Human-in-the-Loop</p>
            </div>
          </div>
          <div className="tech-pills">
            <span className="tech-pill">LangGraph</span>
            <span className="tech-pill">Groq</span>
            <span className="tech-pill">Qdrant</span>
          </div>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-card">
            <div className="sidebar-tabs">
              <button
                type="button"
                className={`sidebar-tab ${sidebarTab === 'overview' ? 'active' : ''}`}
                onClick={() => setSidebarTab('overview')}
              >
                Overview
              </button>
              <button
                type="button"
                className={`sidebar-tab ${sidebarTab === 'workflow' ? 'active' : ''}`}
                onClick={() => setSidebarTab('workflow')}
              >
                Workflow
              </button>
            </div>

            {sidebarTab === 'overview' ? (
              <>
                <p className="sidebar-lead">
                  Upload a financial PDF and a supervisor agent coordinates extraction,
                  analysis, compliance, and risk checks — pausing for your approval at
                  every key decision point.
                </p>
                <ul className="feature-list">
                  <li>
                    <span className="feature-icon"><Icon name="cpu" size={16} /></span>
                    <div>
                      <strong>Multi-Agent Orchestration</strong>
                      <span>5 specialized agents coordinated by a LangGraph supervisor</span>
                    </div>
                  </li>
                  <li>
                    <span className="feature-icon"><Icon name="users" size={16} /></span>
                    <div>
                      <strong>Human-in-the-Loop</strong>
                      <span>Review and edit results before they're finalized</span>
                    </div>
                  </li>
                  <li>
                    <span className="feature-icon"><Icon name="search" size={16} /></span>
                    <div>
                      <strong>RAG-Powered Q&amp;A</strong>
                      <span>Ask a question; re-ranked retrieval grounds the answer</span>
                    </div>
                  </li>
                  <li>
                    <span className="feature-icon"><Icon name="zap" size={16} /></span>
                    <div>
                      <strong>Real-Time Progress</strong>
                      <span>Live WebSocket updates as each agent runs</span>
                    </div>
                  </li>
                </ul>
              </>
            ) : (
              <WorkflowGuide />
            )}
          </div>
        </aside>

        <main className="app-container">
          {!sessionId ? (
            <div className="upload-section-wrapper">
              <UploadForm onUpload={handleFileUpload} />
              <div className="query-input-section">
                <label htmlFor="userQuery" className="query-label">
                  Ask a specific question (optional)
                </label>
                <input
                  type="text"
                  id="userQuery"
                  className="query-input"
                  value={userQuery}
                  onChange={(e) => setUserQuery(e.target.value)}
                  placeholder="e.g. What is the consolidated revenue for 2024?"
                />
                <small className="query-hint">
                  If provided, the agent will use RAG to answer this specific question.
                </small>
              </div>
            </div>
          ) : (
            <>
              <div className="session-info">
                <div className="session-badge">Session #{sessionId}</div>
                {status && (
                  <div className={`status-badge status-${status.status}`}>
                    {status.status.replace('_', ' ').toUpperCase()}
                  </div>
                )}
              </div>

              <Stepper steps={WORKFLOW_STEPS} activeIndex={getActiveStepIndex()} />
            </>
          )}

          {sessionId && <ProgressList messages={messages} />}

          {/* Human Approval Section with Preview */}
          {status?.requires_approval && (
            <div className="approval-section">
              <h3><Icon name="bell" size={17} /> Human Approval Required</h3>
              <p className="checkpoint-name">
                Checkpoint: <strong>{getCheckpointName(status.approval_checkpoint)}</strong>
              </p>

              {/* Draft Preview */}
              {renderPreview()}

              <div className="approval-form">
                <textarea
                  placeholder="Optional feedback or notes..."
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  rows={3}
                />
                <button
                  className="approve-button"
                  onClick={handleApprove}
                  disabled={isApproving}
                >
                  <Icon name={isApproving ? 'clock' : 'check-circle'} size={16} />
                  {isApproving ? 'Approving...' : 'Approve & Continue'}
                </button>
              </div>
            </div>
          )}

          {/* Download Report - Only shown after completion, requires user click */}
          {completed && sessionId && (
            <div className="download-section">
              <h3><Icon name="check-circle" size={18} /> Analysis Complete</h3>
              <button
                className="download-button"
                onClick={async () => {
                  try {
                    const response = await fetch(`/api/sessions/${sessionId}/report/`);
                    if (!response.ok) {
                      const errorData = await response.json().catch(() => ({}));
                      console.error('Download error:', response.status, errorData);
                      alert(`Report not available: ${errorData.error || response.statusText}`);
                      return;
                    }
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `financial_report_${sessionId}.pdf`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                  } catch (err) {
                    console.error('Download exception:', err);
                    alert('Failed to download report. Please try again.');
                  }
                }}
              >
                <Icon name="download" size={16} />
                Download Report
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
