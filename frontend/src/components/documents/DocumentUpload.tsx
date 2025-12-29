import { useState, useRef } from 'react';
import { Upload, FileText, X } from 'lucide-react';
import { uploadDocument } from '@/api/documents';
import { useToast } from '@/components/ui/Toast';
import { DocumentUploadResponse } from '@/types';

interface DocumentUploadProps {
  onUploadComplete: (response: DocumentUploadResponse) => void;
}

const DocumentUpload = ({ onUploadComplete }: DocumentUploadProps) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addToast } = useToast();

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleFileSelect = (file: File) => {
    // Validate by file extension instead of MIME type for better compatibility
    const validExtensions = ['pdf', 'txt', 'csv', 'xlsx', 'xls'];
    const fileExtension = file.name.split('.').pop()?.toLowerCase() || '';
    
    if (!validExtensions.includes(fileExtension)) {
      addToast('Invalid file type. Please upload PDF, TXT, CSV, or Excel files.', 'error');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      addToast('File size exceeds 10MB limit.', 'error');
      return;
    }

    setSelectedFile(file);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    try {
      const response = await uploadDocument(selectedFile);
      addToast('Document uploaded successfully!', 'success');
      onUploadComplete(response);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      addToast('Failed to upload document. Please try again.', 'error');
    } finally {
      setIsUploading(false);
    }
  };

  const clearSelectedFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-4">
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          isDragging ? 'border-accent bg-accent/5' : 'border-border hover:border-gray-300'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={handleInputChange}
          accept=".pdf,.txt,.csv,.xlsx,.xls"
        />
        
        {!selectedFile ? (
          <div>
            <Upload className="w-12 h-12 mx-auto text-text-secondary mb-4" />
            <p className="text-text-primary mb-2">
              Drag and drop a file here, or{' '}
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-accent hover:underline"
              >
                browse
              </button>
            </p>
            <p className="text-sm text-text-secondary">
              PDF, TXT, CSV, or Excel files up to 10MB
            </p>
          </div>
        ) : (
          <div className="flex items-center justify-between bg-white border border-border rounded-md p-4">
            <div className="flex items-center gap-3">
              <FileText className="w-8 h-8 text-accent" />
              <div className="text-left">
                <p className="text-sm font-medium text-text-primary">{selectedFile.name}</p>
                <p className="text-xs text-text-secondary">
                  {(selectedFile.size / 1024).toFixed(1)} KB
                </p>
              </div>
            </div>
            <button
              onClick={clearSelectedFile}
              className="p-1 hover:bg-gray-100 rounded-md transition-colors"
            >
              <X className="w-5 h-5 text-text-secondary" />
            </button>
          </div>
        )}
      </div>

      {selectedFile && (
        <div className="flex justify-end">
          <button
            onClick={handleUpload}
            disabled={isUploading}
            className="btn btn-primary btn-md"
          >
            {isUploading ? 'Uploading...' : 'Upload Document'}
          </button>
        </div>
      )}
    </div>
  );
};

export default DocumentUpload;
