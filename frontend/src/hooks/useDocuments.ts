import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getDocuments, uploadDocument, deleteDocument } from '@/api/documents';
import { Document, DocumentUploadResponse } from '@/types';
import { useToast } from '@/components/ui/Toast';

export const useDocuments = () => {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const { data: documents = [], isLoading, error } = useQuery({
    queryKey: ['documents'],
    queryFn: getDocuments,
  });

  const uploadMutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: (data: DocumentUploadResponse) => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      addToast('Document uploaded successfully!', 'success');
    },
    onError: (error: any) => {
      addToast(error.response?.data?.detail || 'Failed to upload document.', 'error');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      addToast('Document deleted successfully!', 'success');
    },
    onError: (error: any) => {
      addToast(error.response?.data?.detail || 'Failed to delete document.', 'error');
    },
  });

  return {
    documents,
    isLoading,
    error,
    uploadDocument: uploadMutation.mutate,
    isUploading: uploadMutation.isPending,
    deleteDocument: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
  };
};
