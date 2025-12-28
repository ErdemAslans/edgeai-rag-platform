import { useState } from 'react';
import { ChevronDown, ChevronRight, FileText } from 'lucide-react';
import { SourceReference as SourceRefType } from '@/types';

interface SourceReferenceProps {
  sources: SourceRefType[];
}

const SourceReference = ({ sources }: SourceReferenceProps) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (sources.length === 0) return null;

  return (
    <div className="border-t border-border pt-3">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
      >
        {isExpanded ? (
          <ChevronDown className="w-4 h-4" />
        ) : (
          <ChevronRight className="w-4 h-4" />
        )}
        <span>{sources.length} source{sources.length !== 1 ? 's' : ''} referenced</span>
      </button>

      {isExpanded && (
        <div className="mt-2 space-y-2">
          {sources.map((source, index) => (
            <div
              key={index}
              className="bg-gray-50 border border-border rounded-md p-3"
            >
              <div className="flex items-start gap-2 mb-2">
                <FileText className="w-4 h-4 text-accent mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text-primary truncate">
                    {source.document_name}
                  </p>
                  <p className="text-xs text-text-secondary">
                    Relevance: {(source.score * 100).toFixed(0)}%
                  </p>
                </div>
              </div>
              <p className="text-xs text-text-secondary bg-white border border-border rounded p-2">
                {source.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SourceReference;
