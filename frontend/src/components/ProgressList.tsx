// Displays a list of progress messages as they arrive.
import React from 'react';

interface Props {
  messages: string[];
}

const ProgressList: React.FC<Props> = ({ messages }) => (
  <ul>
    {messages.map((msg, idx) => (
      <li key={idx}>{msg}</li>
    ))}
  </ul>
);

export default ProgressList;
