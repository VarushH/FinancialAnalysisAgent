// Enhanced ProgressList with message type styling
import React from 'react';

interface Props {
  messages: string[];
}

const ProgressList: React.FC<Props> = ({ messages }) => {
  if (messages.length === 0) {
    return (
      <div className="no-messages">
        Waiting for progress updates...
      </div>
    );
  }

  return (
    <ul>
      {messages.map((msg, idx) => (
        <li key={idx} className={getMessageClass(msg)}>
          {msg}
        </li>
      ))}
    </ul>
  );
};

// Helper to determine message styling based on content
const getMessageClass = (msg: string): string => {
  if (msg.includes('❌') || msg.toLowerCase().includes('error') || msg.toLowerCase().includes('failed')) {
    return 'message-error';
  }
  if (msg.includes('✅') || msg.toLowerCase().includes('complete')) {
    return 'message-success';
  }
  if (msg.includes('⏸️') || msg.toLowerCase().includes('awaiting') || msg.toLowerCase().includes('approval')) {
    return 'message-warning';
  }
  if (msg.includes('🚀') || msg.includes('📤')) {
    return 'message-info';
  }
  return '';
};

export default ProgressList;
