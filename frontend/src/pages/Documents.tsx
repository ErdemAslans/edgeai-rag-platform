import { useState } from 'react';
import { Search, Filter } from 'lucide-react';
import PageContainer from '@/components/layout/PageContainer';
import Header from '@/components/layout/Header';
import DocumentUpload from '@/components/documents/DocumentUpload';
import DocumentCard from '@/components/documents/DocumentCard';
import Button from '@/components/ui/Button';
import Modal from '@/components/ui/Modal';
import { useDocuments } from '@/hooks/useDocuments';
import { Document } from '@/types';
import { formatFileSize } from '@/lib/utils';

const Documents = () => {
  const { documents, isLoading, uploadDocument, deleteDocument, isUploading } = useDocuments();
  const [searchQuery, setSearchQuery] = useState('');
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);

  const filteredDocuments = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleUploadComplete = (response: any) => {
    setIsUploadModalOpen(false);
  };

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to delete this document?')) {
      deleteDocument(id);
    }
  };

  const handleDocumentClick = (document: Document) => {
    setSelectedDocument(document);
  };

  return (
    <PageContainer>
      <Header
        title="Documents"
        subtitle="Manage your uploaded documents"
        actions={
          <Button
            variant="primary"
            onClick={() => setIsUploadModalOpen(true)}
          >
            Upload Document
          </Button>
        }
      />

      <div className="mb-6 flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-secondary" />
          <input
            type="text"
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-border rounded-md bg-white text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
          />
        </div>
        <button className="flex items-center gap-2 px-4 py-2 border border-border rounded-md bg-white text-text-primary hover:bg-gray-50 transition-colors">
          <Filter className="w-5 h-5" />
          Filter
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
        </div>
      ) : filteredDocuments.length === 0 ? (
        <div className="text-center py-12 text-text-secondary">
          <p>No documents found.</p>
          <p className="mt-2 text-sm">
            Upload your first document to get started.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredDocuments.map((document) => (
            <DocumentCard
              key={document.id}
              document={document}
              onDelete={handleDelete}
              onClick={() => handleDocumentClick(document)}
            />
          ))}
        </div>
      )}

      <Modal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        title="Upload Document"
        size="lg"
      >
        <DocumentUpload onUploadComplete={handleUploadComplete} />
      </Modal>

      {selectedDocument && (
        <Modal
          isOpen={!!selectedDocument}
          onClose={() => setSelectedDocument(null)}
          title={selectedDocument.filename}
          size="lg"
        >
          <div className="space-y-4">
            <div>
              <p className="text-sm text-text-secondary mb-1">File Name</p>
              <p className="text-text-primary font-medium">{selectedDocument.filename}</p>
            </div>
            <div>
              <p className="text-sm text-text-secondary mb-1">File Size</p>
              <p className="text-text-primary">{formatFileSize(selectedDocument.file_size)}</p>
            </div>
            <div>
              <p className="text-sm text-text-secondary mb-1">File Type</p>
              <p className="text-text-primary">{selectedDocument.file_type}</p>
            </div>
            <div>
              <p className="text-sm text-text-secondary mb-1">Status</p>
              <p className="text-text-primary capitalize">{selectedDocument.status}</p>
            </div>
            <div>
              <p className="text-sm text-text-secondary mb-1">Chunks</p>
              <p className="text-text-primary">{selectedDocument.chunk_count}</p>
            </div>
            <div>
              <p className="text-sm text-text-secondary mb-1">Uploaded</p>
              <p className="text-text-primary">
                {new Date(selectedDocument.uploaded_at).toLocaleString()}
              </p>
            </div>
          </div>
        </Modal>
      )}
    </PageContainer>
  );
};

export default Documents;
