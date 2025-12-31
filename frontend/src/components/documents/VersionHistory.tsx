/**
 * Document Version History Component
 * 
 * Displays version history, allows viewing diffs,
 * comparing versions, and rolling back.
 */

import React, { useState, useEffect } from 'react';
import Card from '../ui/Card';
import Button from '../ui/Button';
import Spinner from '../ui/Spinner';
import Badge from '../ui/Badge';
import Modal from '../ui/Modal';
import {
  getVersionHistory,
  getVersionContent,
  getVersionDiff,
  compareVersions,
  rollbackToVersion,
  VersionInfo,
  DiffResponse,
  CompareResponse,
} from '../../api/versions';

interface VersionHistoryProps {
  documentId: string;
  onVersionRestored?: () => void;
}

const VersionHistory: React.FC<VersionHistoryProps> = ({
  documentId,
  onVersionRestored,
}) => {
  const [loading, setLoading] = useState(true);
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [totalVersions, setTotalVersions] = useState(0);
  const [error, setError] = useState<string | null>(null);
  
  // Modal states
  const [showDiff, setShowDiff] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const [showRollback, setShowRollback] = useState(false);
  
  // Selected versions
  const [selectedVersion, setSelectedVersion] = useState<VersionInfo | null>(null);
  const [compareVersionA, setCompareVersionA] = useState<number | null>(null);
  const [compareVersionB, setCompareVersionB] = useState<number | null>(null);
  
  // Modal data
  const [diffData, setDiffData] = useState<DiffResponse | null>(null);
  const [compareData, setCompareData] = useState<CompareResponse | null>(null);
  const [rollbackReason, setRollbackReason] = useState('');
  const [modalLoading, setModalLoading] = useState(false);

  useEffect(() => {
    loadVersionHistory();
  }, [documentId]);

  const loadVersionHistory = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getVersionHistory(documentId);
      setVersions(response.versions);
      setTotalVersions(response.total_versions);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load version history');
    } finally {
      setLoading(false);
    }
  };

  const handleViewDiff = async (version: VersionInfo) => {
    setSelectedVersion(version);
    setModalLoading(true);
    setShowDiff(true);
    
    try {
      // Get diff from previous version
      const prevVersion = version.version_number > 1 ? version.version_number - 1 : 1;
      const diff = await getVersionDiff(documentId, prevVersion, version.version_number);
      setDiffData(diff);
    } catch (err) {
      setError('Failed to load diff');
    } finally {
      setModalLoading(false);
    }
  };

  const handleCompare = async () => {
    if (!compareVersionA || !compareVersionB) return;
    
    setModalLoading(true);
    setShowCompare(true);
    
    try {
      const comparison = await compareVersions(documentId, compareVersionA, compareVersionB);
      setCompareData(comparison);
    } catch (err) {
      setError('Failed to compare versions');
    } finally {
      setModalLoading(false);
    }
  };

  const handleRollback = async () => {
    if (!selectedVersion) return;
    
    setModalLoading(true);
    
    try {
      await rollbackToVersion(documentId, selectedVersion.version_number, rollbackReason);
      setShowRollback(false);
      setRollbackReason('');
      await loadVersionHistory();
      onVersionRestored?.();
    } catch (err) {
      setError('Failed to rollback');
    } finally {
      setModalLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const getVersionTypeBadge = (type: string) => {
    switch (type) {
      case 'create':
        return <Badge variant="success">Created</Badge>;
      case 'update':
        return <Badge variant="neutral">Updated</Badge>;
      case 'restore':
        return <Badge variant="warning">Restored</Badge>;
      case 'reprocess':
        return <Badge variant="neutral">Reprocessed</Badge>;
      default:
        return <Badge variant="neutral">{type}</Badge>;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Spinner size="md" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-red-500 mb-4">{error}</p>
        <Button onClick={loadVersionHistory}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Version History</h3>
        <span className="text-sm text-gray-500">{totalVersions} versions</span>
      </div>

      {/* Compare selector */}
      <Card className="p-4">
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium">Compare:</span>
          <select
            value={compareVersionA || ''}
            onChange={(e) => setCompareVersionA(Number(e.target.value) || null)}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value="">Select version</option>
            {versions.map((v) => (
              <option key={v.id} value={v.version_number}>
                v{v.version_number}
              </option>
            ))}
          </select>
          <span className="text-gray-400">with</span>
          <select
            value={compareVersionB || ''}
            onChange={(e) => setCompareVersionB(Number(e.target.value) || null)}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value="">Select version</option>
            {versions.map((v) => (
              <option key={v.id} value={v.version_number}>
                v{v.version_number}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            onClick={handleCompare}
            disabled={!compareVersionA || !compareVersionB || compareVersionA === compareVersionB}
          >
            Compare
          </Button>
        </div>
      </Card>

      {/* Version list */}
      <div className="space-y-2">
        {versions.map((version) => (
          <Card key={version.id} className="p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium">v{version.version_number}</span>
                  {getVersionTypeBadge(version.version_type)}
                  <span className="text-sm text-gray-500">
                    {formatDate(version.created_at)}
                  </span>
                </div>
                <p className="text-sm text-gray-600">{version.title}</p>
                {version.change_summary && (
                  <p className="text-sm text-gray-500 mt-1">
                    "{version.change_summary}"
                  </p>
                )}
                {version.diff_stats && (
                  <div className="flex gap-3 mt-2 text-xs">
                    <span className="text-green-600">
                      +{version.diff_stats.lines_added} added
                    </span>
                    <span className="text-red-600">
                      -{version.diff_stats.lines_removed} removed
                    </span>
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                {version.version_number > 1 && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleViewDiff(version)}
                  >
                    View Diff
                  </Button>
                )}
                {version.version_number < totalVersions && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setSelectedVersion(version);
                      setShowRollback(true);
                    }}
                  >
                    Restore
                  </Button>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Diff Modal */}
      <Modal
        isOpen={showDiff}
        onClose={() => setShowDiff(false)}
        title={`Changes in v${selectedVersion?.version_number}`}
      >
        {modalLoading ? (
          <div className="flex justify-center py-8">
            <Spinner size="md" />
          </div>
        ) : diffData ? (
          <div className="space-y-4">
            <div className="text-sm text-gray-600">
              Comparing v{diffData.from_version} → v{diffData.to_version}
            </div>
            <pre className="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm font-mono whitespace-pre-wrap">
              {diffData.diff_content || 'No changes'}
            </pre>
          </div>
        ) : (
          <p>No diff available</p>
        )}
      </Modal>

      {/* Compare Modal */}
      <Modal
        isOpen={showCompare}
        onClose={() => setShowCompare(false)}
        title="Version Comparison"
      >
        {modalLoading ? (
          <div className="flex justify-center py-8">
            <Spinner size="md" />
          </div>
        ) : compareData ? (
          <div className="space-y-4">
            {compareData.same_content ? (
              <Badge variant="success">Content is identical</Badge>
            ) : (
              <Badge variant="warning">Content differs</Badge>
            )}
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h4 className="font-medium mb-2">v{compareData.version_a.number}</h4>
                <p className="text-sm text-gray-600">{compareData.version_a.title}</p>
                <p className="text-xs text-gray-500">{formatDate(compareData.version_a.created_at)}</p>
              </div>
              <div>
                <h4 className="font-medium mb-2">v{compareData.version_b.number}</h4>
                <p className="text-sm text-gray-600">{compareData.version_b.title}</p>
                <p className="text-xs text-gray-500">{formatDate(compareData.version_b.created_at)}</p>
              </div>
            </div>
            
            {compareData.diff && (
              <div>
                <h4 className="font-medium mb-2">Diff</h4>
                <pre className="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm font-mono whitespace-pre-wrap max-h-96">
                  {compareData.diff}
                </pre>
              </div>
            )}
          </div>
        ) : (
          <p>Comparison data not available</p>
        )}
      </Modal>

      {/* Rollback Modal */}
      <Modal
        isOpen={showRollback}
        onClose={() => setShowRollback(false)}
        title={`Restore to v${selectedVersion?.version_number}`}
      >
        <div className="space-y-4">
          <p className="text-gray-600">
            This will restore the document to version {selectedVersion?.version_number}.
            The current state will be saved as a new version before restoration.
          </p>
          
          <div>
            <label className="block text-sm font-medium mb-1">
              Reason for restoration (optional)
            </label>
            <textarea
              value={rollbackReason}
              onChange={(e) => setRollbackReason(e.target.value)}
              className="w-full border rounded-lg p-2"
              rows={3}
              placeholder="Enter reason for restoration..."
            />
          </div>
          
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowRollback(false)}>
              Cancel
            </Button>
            <Button onClick={handleRollback} disabled={modalLoading}>
              {modalLoading ? 'Restoring...' : 'Restore Version'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default VersionHistory;