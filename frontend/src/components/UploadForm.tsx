// Modern upload form with drag and drop styling
import React, { useState, useRef } from 'react';

interface Props {
  onUpload: (file: File) => void;
}

const UploadForm: React.FC<Props> = ({ onUpload }) => {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (file) {
      setIsUploading(true);
      await onUpload(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.type === 'application/pdf') {
      setFile(droppedFile);
    }
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <form onSubmit={handleSubmit} className="upload-form">
      <div
        className={`upload-dropzone ${isDragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          onChange={e => {
            if (e.target.files) setFile(e.target.files[0]);
          }}
          style={{ display: 'none' }}
        />

        <div className="upload-icon">
          {file ? '📄' : '📁'}
        </div>

        <div className="upload-text">
          {file ? (
            <>
              <span className="file-name">{file.name}</span>
              <span className="file-size">({(file.size / 1024 / 1024).toFixed(2)} MB)</span>
            </>
          ) : (
            <>
              <span className="upload-title">Drop your PDF here</span>
              <span className="upload-subtitle">or click to browse</span>
            </>
          )}
        </div>
      </div>

      <button
        type="submit"
        disabled={!file || isUploading}
        className="upload-button"
      >
        {isUploading ? (
          <>⏳ Uploading...</>
        ) : (
          <>🚀 Upload & Analyze</>
        )}
      </button>
    </form>
  );
};

export default UploadForm;
