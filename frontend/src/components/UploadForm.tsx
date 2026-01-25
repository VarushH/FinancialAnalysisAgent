// A form for selecting the PDF file and submitting it. It calls onUpload prop with the selected file.
import React, { useState } from 'react';

interface Props {
  onUpload: (file: File) => void;
}

const UploadForm: React.FC<Props> = ({ onUpload }) => {
  const [file, setFile] = useState<File | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (file) {
      onUpload(file);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input type="file" accept="application/pdf" onChange={e => {
        if (e.target.files) setFile(e.target.files[0]);
      }} />
      <button type="submit" disabled={!file}>Upload & Analyze</button>
    </form>
  );
};

export default UploadForm;
