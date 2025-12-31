/**
 * Shared With Me Page
 * 
 * Shows documents that have been shared with the current user.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import { getSharedWithMe, SharedDocument } from '../api/collaboration';

const SharedWithMe: React.FC = () => {
  const navigate = useNavigate();
  const [shares, setShares] = useState<SharedDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSharedDocuments = useCallback(async () => {
    try {
      setIsLoading(true);
      const result = await getSharedWithMe(0, 100);
      setShares(result.shares);
    } catch (err) {
      setError('Failed to load shared documents');
      console.error('Failed to fetch shared documents:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSharedDocuments();
  }, [fetchSharedDocuments]);

  const getPermissionBadgeVariant = (permission: string) => {
    switch (permission) {
      case 'admin':
        return 'error';
      case 'edit':
        return 'success';
      case 'comment':
        return 'warning';
      default:
        return 'neutral';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const handleDocumentClick = (documentId: string) => {
    navigate(`/documents/${documentId}`);
  };

  if (isLoading) {
    return (
      <PageContainer>
        <div className="flex items-center justify-center h-64">
          <Spinner size="lg" />
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Shared With Me</h1>
        <p className="text-gray-600 mt-1">
          Documents that others have shared with you
        </p>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {shares.length === 0 ? (
        <Card>
          <div className="text-center py-12">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
              />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              No shared documents
            </h3>
            <p className="mt-2 text-gray-500">
              Documents shared with you will appear here.
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {shares.map((share) => (
            <Card
              key={share.share_id}
              className="hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => handleDocumentClick(share.document_id)}
            >
              <div className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-medium text-gray-900 truncate">
                      {share.document_title}
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                      Shared {formatDate(share.shared_at)}
                    </p>
                  </div>
                  <Badge variant={getPermissionBadgeVariant(share.permission)}>
                    {share.permission}
                  </Badge>
                </div>

                {share.message && (
                  <div className="mt-3 p-2 bg-gray-50 rounded text-sm text-gray-600">
                    "{share.message}"
                  </div>
                )}

                <div className="mt-4 flex items-center text-sm text-gray-500">
                  <svg
                    className="w-4 h-4 mr-1"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                    />
                  </svg>
                  <span>
                    {share.shared_by ? `Shared by user` : 'Unknown sharer'}
                  </span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </PageContainer>
  );
};

export default SharedWithMe;