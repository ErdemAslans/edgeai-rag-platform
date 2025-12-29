import api from './client';
import { Document, DocumentUploadResponse } from '@/types';

interface DocumentAPIResponse {
  id: string;
  user_id: string;
  filename: string;
  content_type: string;
  file_path: string;
  file_size: number;
  status: string;
  chunk_count: number;
  error_message: string | null;
  doc_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string | null;
}

interface DocumentListAPIResponse {
  documents: DocumentAPIResponse[];
  total: number;
  skip: number;
  limit: number;
}

const mapDocumentResponse = (doc: DocumentAPIResponse): Document => ({
  id: doc.id,
  filename: doc.filename,
  file_type: doc.content_type,
  file_size: doc.file_size,
  status: doc.status as 'pending' | 'processing' | 'completed' | 'failed',
  chunk_count: doc.chunk_count,
  uploaded_at: doc.created_at,
  user_id: doc.user_id,
});

export const uploadDocument = async (file: File): Promise<DocumentUploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post<DocumentAPIResponse>('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  // Map backend response to frontend type
  return {
    id: response.data.id,
    filename: response.data.filename,
    status: response.data.status,
    message: 'Document uploaded successfully',
  };
};

export const getDocuments = async (): Promise<Document[]> => {
  const response = await api.get<DocumentListAPIResponse>('/documents');
  return response.data.documents.map(mapDocumentResponse);
};

export const deleteDocument = async (id: string): Promise<void> => {
  await api.delete(`/documents/${id}`);
};
