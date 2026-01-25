// The main component handles file selection, uploading, starting the analysis, and managing WebSocket messages. After upload and start, it listens to the WebSocket for progress messages and updates state accordingly. When completed, it shows a download link.
import React, { useState, useEffect, useRef } from 'react';
import UploadForm from './components/UploadForm';
import ProgressList from './components/ProgressList';

const App: React.FC = () => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<string[]>([]);
  const [completed, setCompleted] = useState(false);

  // WebSocket reference
  const ws = useRef<WebSocket | null>(null);

  // Handle progress messages from WebSocket
  useEffect(() => {
    if (!sessionId) return;
    const wsUrl = `${process.env.REACT_APP_WS_URL || `ws://localhost:8000`}/ws/progress/${sessionId}/`;
    ws.current = new WebSocket(wsUrl);
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const msg: string = data.message;
      setMessages(prev => [...prev, msg]);
      if (msg.includes('completed')) {
        setCompleted(true);
      }
    };
    return () => { ws.current?.close(); };
  }, [sessionId]);

  // Upload file and start analysis
  const handleFileUpload = async (file: File) => {
    // Upload
    const data = new FormData();
    data.append('file', file);
    const uploadRes = await fetch(`/api/upload/`, { method: 'POST', body: data });
    const uploadJson = await uploadRes.json();
    const id = uploadJson.session_id;
    setSessionId(String(id));
    // Start analysis
    await fetch(`/api/start/${id}/`, { method: 'POST' });
  };

  return (
    <div>
      <h1>Financial Analysis</h1>
      {!sessionId && <UploadForm onUpload={handleFileUpload} />}
      {sessionId && <ProgressList messages={messages} />}
      {completed && sessionId && (
        <a href={`/api/report/${sessionId}/`} target="_blank" rel="noopener noreferrer">
          Download Report
        </a>
      )}
    </div>
  );
};

export default App;
