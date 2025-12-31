import { useState } from 'react';
import { Search, Filter, Play, RefreshCw, X } from 'lucide-react';
import PageContainer from '@/components/layout/PageContainer';
import Header from '@/components/layout/Header';
import DocumentUpload from '@/components/documents/DocumentUpload';
import DocumentCard from '@/components/documents/DocumentCard';
import Button from '@/components/ui/Button';
import Modal from '@/components/ui/Modal';
import { useDocuments } from '@/hooks/useDocuments';
import { Document } from '@/types';
import { formatFileSize } from '@/lib/utils';

type StatusFilter = 'all' | 'pending' | 'processing' | 'completed' | 'failed';
type TypeFilter = 'all' | 'pdf' | 'txt' | 'docx' | 'xlsx' | 'other';

const Documents = () => {
  const { documents, isLoading, uploadDocument, deleteDocument, processDocument, isUploading, isProcessing, refetch } = useDocuments();
  const [searchQuery, setSearchQuery] = useState('');
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all');

  const getFileTypeCategory = (fileType: string): TypeFilter => {
    const type = fileType.toLowerCase();
    if (type.includes('pdf')) return 'pdf';
    if (type.includes('text') || type.includes('txt')) return 'txt';
    if (type.includes('word') || type.includes('docx')) return 'docx';
    if (type.includes('excel') || type.includes('xlsx') || type.includes('spreadsheet')) return 'xlsx';
    return 'other';
  };

  const filteredDocuments = documents.filter((doc) => {
    const matchesSearch = doc.filename.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || doc.status === statusFilter;
    const matchesType = typeFilter === 'all' || getFileTypeCategory(doc.file_type) === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });

  const activeFiltersCount = (statusFilter !== 'all' ? 1 : 0) + (typeFilter !== 'all' ? 1 : 0);

  const clearFilters = () => {
    setStatusFilter('all');
    setTypeFilter('all');
  };

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
        <div className="relative">
          <button
            onClick={() => setIsFilterOpen(!isFilterOpen)}
            className={`flex items-center gap-2 px-4 py-2 border rounded-md bg-white text-text-primary hover:bg-gray-50 transition-colors ${
              activeFiltersCount > 0 ? 'border-accent' : 'border-border'
            }`}
          >
            <Filter className="w-5 h-5" />
            Filter
            {activeFiltersCount > 0 && (
              <span className="bg-accent text-white text-xs px-1.5 py-0.5 rounded-full">
                {activeFiltersCount}
              </span>
            )}
          </button>

          {isFilterOpen && (
            <div className="absolute right-0 top-12 w-64 bg-white border border-border rounded-md shadow-lg z-10 p-4">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-medium text-text-primary">Filters</h4>
                <button
                  onClick={() => setIsFilterOpen(false)}
                  className="text-text-secondary hover:text-text-primary"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-2">
                    Status
                  </label>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
                    className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  >
                    <option value="all">All Statuses</option>
                    <option value="pending">Pending</option>
                    <option value="processing">Processing</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-text-primary mb-2">
                    File Type
                  </label>
                  <select
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value as TypeFilter)}
                    className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  >
                    <option value="all">All Types</option>
                    <option value="pdf">PDF</option>
                    <option value="txt">Text</option>
                    <option value="docx">Word</option>
                    <option value="xlsx">Excel</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                {activeFiltersCount > 0 && (
                  <button
                    onClick={clearFilters}
                    className="w-full text-sm text-accent hover:underline"
                  >
                    Clear all filters
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {activeFiltersCount > 0 && (
        <div className="mb-4 flex items-center gap-2 text-sm text-text-secondary">
          <span>Active filters:</span>
          {statusFilter !== 'all' && (
            <span className="px-2 py-1 bg-gray-100 rounded-md flex items-center gap-1">
              Status: {statusFilter}
              <button onClick={() => setStatusFilter('all')} className="hover:text-text-primary">
                <X className="w-3 h-3" />
              </button>
            </span>
          )}
          {typeFilter !== 'all' && (
            <span className="px-2 py-1 bg-gray-100 rounded-md flex items-center gap-1">
              Type: {typeFilter}
              <button onClick={() => setTypeFilter('all')} className="hover:text-text-primary">
                <X className="w-3 h-3" />
              </button>
            </span>
          )}
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
        </div>
      ) : filteredDocuments.length === 0 ? (
        <div className="text-center py-12 text-text-secondary">
          <p>No documents found.</p>
          <p className="mt-2 text-sm">
            {documents.length > 0
              ? 'Try adjusting your search or filters.'
              : 'Upload your first document to get started.'}
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
              <p className={`capitalize font-medium ${
                selectedDocument.status === 'completed' ? 'text-green-600' :
                selectedDocument.status === 'processing' ? 'text-blue-600' :
                selectedDocument.status === 'failed' ? 'text-red-600' :
                'text-yellow-600'
              }`}>{selectedDocument.status}</p>
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
            
            {(selectedDocument.status === 'pending' || selectedDocument.status === 'failed') && (
              <div className="pt-4 border-t border-border">
                <Button
                  variant="primary"
                  onClick={() => {
                    processDocument(selectedDocument.id);
                    setSelectedDocument(null);
                  }}
                  disabled={isProcessing}
                  className="w-full flex items-center justify-center gap-2"
                >
                  <Play className="w-4 h-4" />
                  {isProcessing ? 'Processing...' : 'Process Document'}
                </Button>
              </div>
            )}
            
            {selectedDocument.status === 'completed' && (
              <div className="pt-4 border-t border-border">
                <Button
                  variant="secondary"
                  onClick={() => {
                    processDocument(selectedDocument.id);
                    setSelectedDocument(null);
                  }}
                  disabled={isProcessing}
                  className="w-full flex items-center justify-center gap-2"
                >
                  <RefreshCw className="w-4 h-4" />
                  {isProcessing ? 'Processing...' : 'Reprocess Document'}
                </Button>
              </div>
            )}
            
            {selectedDocument.status === 'processing' && (
              <div className="pt-4 border-t border-border">
                <div className="flex items-center justify-center gap-2 text-blue-600">
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Document is being processed...</span>
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}
    </PageContainer>
  );
};

export default Documents;
