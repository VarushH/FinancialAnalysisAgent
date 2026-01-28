// Enhanced main component with human-in-the-loop approval UI and draft preview
import React, { useState, useEffect, useRef } from 'react';
import UploadForm from './components/UploadForm';
import ProgressList from './components/ProgressList';
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

const App: React.FC = () => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<string[]>([]);
  const [completed, setCompleted] = useState(false);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [isApproving, setIsApproving] = useState(false);
  const [feedback, setFeedback] = useState('');

  // Editable report content
  const [editedAnalysis, setEditedAnalysis] = useState('');
  const [editedCompliance, setEditedCompliance] = useState('');
  const [editedRisk, setEditedRisk] = useState('');
  const editableInitialized = useRef(false);

  // WebSocket reference
  const ws = useRef<WebSocket | null>(null);

  // Handle WebSocket messages
  useEffect(() => {
    if (!sessionId) return;

    const wsUrl = `${process.env.REACT_APP_WS_URL || 'ws://localhost:8000'}/ws/progress/${sessionId}/`;
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

  // Upload file and start analysis
  const handleFileUpload = async (file: File) => {
    const data = new FormData();
    data.append('file', file);
    const uploadRes = await fetch('/api/upload/', { method: 'POST', body: data });
    const uploadJson = await uploadRes.json();
    const id = uploadJson.session_id;
    setSessionId(String(id));
    setMessages(['📤 File uploaded successfully']);

    await fetch(`/api/sessions/${id}/start/`, { method: 'POST' });
    setMessages(prev => [...prev, '🚀 Analysis started']);
  };

  // Approve checkpoint
  const handleApprove = async () => {
    if (!sessionId) return;
    setIsApproving(true);

    try {
      // Build request body with edited content if at report_approval checkpoint
      const requestBody: any = { feedback };
      if (status?.approval_checkpoint === 'report_approval') {
        requestBody.edited_content = {
          analysis: editedAnalysis,
          compliance: editedCompliance,
          risk: editedRisk
        };
        console.log('Sending edited content:', requestBody.edited_content);
      }

      const res = await fetch(`/api/sessions/${sessionId}/approve/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });
      const data = await res.json();
      setMessages(prev => [...prev, `✅ Approved: ${data.approved_checkpoint}`]);
      setFeedback('');

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

  // Render preview section
  const renderPreview = () => {
    if (!status?.preview) return null;
    const preview = status.preview;

    if (preview.type === 'extraction') {
      return (
        <div className="preview-section">
          <h4>📄 {preview.title}</h4>
          <div className="preview-stats">
            <span className="stat">📑 Pages: {preview.pages_count}</span>
            <span className="stat">📊 Tables: {preview.tables_count}</span>
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
          <h4>📋 {preview.title}</h4>
          <p className="edit-hint">✏️ You can edit the content below before approving</p>
          <div className="preview-item">
            <strong>💰 Finance Analysis:</strong>
            <textarea
              className="editable-preview"
              value={editedAnalysis}
              onChange={(e) => setEditedAnalysis(e.target.value)}
              rows={6}
            />
          </div>
          <div className="preview-item">
            <strong>⚖️ Compliance Check:</strong>
            <textarea
              className="editable-preview"
              value={editedCompliance}
              onChange={(e) => setEditedCompliance(e.target.value)}
              rows={6}
            />
          </div>
          <div className="preview-item">
            <strong>📊 Risk Assessment:</strong>
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
    <div className="app-container">
      <h1>📊 Financial Analysis Agent</h1>
      <p className="subtitle">Supervisor Agent Architecture with Human-in-the-Loop</p>

      {!sessionId && <UploadForm onUpload={handleFileUpload} />}

      {sessionId && (
        <div className="session-info">
          <div className="session-badge">Session #{sessionId}</div>
          {status && (
            <div className={`status-badge status-${status.status}`}>
              {status.status.replace('_', ' ').toUpperCase()}
            </div>
          )}
        </div>
      )}

      {sessionId && <ProgressList messages={messages} />}

      {/* Human Approval Section with Preview */}
      {status?.requires_approval && (
        <div className="approval-section">
          <h3>🔔 Human Approval Required</h3>
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
              {isApproving ? '⏳ Approving...' : '✅ Approve & Continue'}
            </button>
          </div>
        </div>
      )}

      {/* Download Report - Only shown after completion, requires user click */}
      {completed && sessionId && (
        <div className="download-section">
          <h3>🎉 Analysis Complete!</h3>
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
            📥 Download Report
          </button>
        </div>
      )}

      {/* Workflow Steps Legend */}
      <div className="workflow-info">
        <h4>Workflow Steps:</h4>
        <ol>
          <li>📄 Document Extraction</li>
          <li>🔔 <em>Human Review Checkpoint</em></li>
          <li>💰 Finance Analysis + ⚖️ Compliance (parallel)</li>
          <li>📊 Risk Assessment</li>
          <li>📝 Report Generation</li>
          <li>🔔 <em>Final Approval Checkpoint</em></li>
          <li>✅ Complete</li>
        </ol>
      </div>
    </div>
  );
};

export default App;
