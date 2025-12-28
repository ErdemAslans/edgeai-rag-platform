import { FileText, Trash2 } from 'lucide-react';
import { Document } from '@/types';
import { formatDate, formatFileSize } from '@/lib/utils';
import Badge from '@/components/ui/Badge';

interface DocumentCardProps {
  document: Document;
  onDelete: (id: string) => void;
  onClick: () => void;
}

const DocumentCard = ({ document, onDelete, onClick }: DocumentCardProps) => {
  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'processing':
        return 'warning';
      case 'failed':
        return 'error';
      default:
        return 'neutral';
    }
  };

  return (
    <div
      onClick={onClick}
      className="card p-6 cursor-pointer group"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-accent/10 rounded-md">
            <FileText className="w-6 h-6 text-accent" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-text-primary truncate">
              {document.filename}
            </h3>
            <p className="text-sm text-text-secondary">
              {formatFileSize(document.file_size)}
            </p>
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(document.id);
          }}
          className="opacity-0 group-hover:opacity-100 p-1 hover:bg-error/10 rounded-md transition-all"
        >
          <Trash2 className="w-4 h-4 text-error" />
        </button>
      </div>

      <div className="flex items-center justify-between">
        <Badge variant={getStatusVariant(document.status)}>
          {document.status}
        </Badge>
        <p className="text-xs text-text-secondary">
          {formatDate(document.uploaded_at)}
        </p>
      </div>
    </div>
  );
};

export default DocumentCard;
