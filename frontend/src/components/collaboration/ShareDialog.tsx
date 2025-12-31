/**
 * Share Dialog Component
 * 
 * Modal dialog for sharing documents with users, teams, or generating share links.
 */

import React, { useState } from 'react';
import Modal from '../ui/Modal';
import Button from '../ui/Button';
import Input from '../ui/Input';
import { shareDocument, ShareDocumentRequest } from '../../api/collaboration';

interface ShareDialogProps {
  isOpen: boolean;
  onClose: () => void;
  documentId: string;
  documentTitle: string;
  onShareCreated?: () => void;
}

type ShareType = 'user' | 'link' | 'public';
type Permission = 'view' | 'comment' | 'edit' | 'admin';

const ShareDialog: React.FC<ShareDialogProps> = ({
  isOpen,
  onClose,
  documentId,
  documentTitle,
  onShareCreated,
}) => {
  const [shareType, setShareType] = useState<ShareType>('user');
  const [email, setEmail] = useState('');
  const [permission, setPermission] = useState<Permission>('view');
  const [message, setMessage] = useState('');
  const [expiresInDays, setExpiresInDays] = useState<number | undefined>();
  const [linkPassword, setLinkPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shareLink, setShareLink] = useState<string | null>(null);

  const handleShare = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const request: ShareDocumentRequest = {
        document_id: documentId,
        share_type: shareType === 'user' ? 'user' : shareType === 'link' ? 'link' : 'public',
        permission,
        message: message || undefined,
      };

      if (shareType === 'user') {
        // In a real app, we'd look up the user by email
        // For now, we'll show an error
        setError('User lookup by email not implemented. Use user ID directly.');
        setIsLoading(false);
        return;
      }

      if (shareType === 'link') {
        request.link_expires_in_days = expiresInDays;
        request.link_password = linkPassword || undefined;
      }

      const result = await shareDocument(request);

      if (result.share_link_token) {
        const baseUrl = window.location.origin;
        setShareLink(`${baseUrl}/shared/${result.share_link_token}`);
      } else {
        onShareCreated?.();
        onClose();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to share document');
    } finally {
      setIsLoading(false);
    }
  };

  const copyShareLink = () => {
    if (shareLink) {
      navigator.clipboard.writeText(shareLink);
    }
  };

  const resetForm = () => {
    setShareType('user');
    setEmail('');
    setPermission('view');
    setMessage('');
    setExpiresInDays(undefined);
    setLinkPassword('');
    setError(null);
    setShareLink(null);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={`Share "${documentTitle}"`}>
      <div className="space-y-4">
        {/* Share Type Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Share Type
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShareType('user')}
              className={`flex-1 py-2 px-4 rounded-md border ${
                shareType === 'user'
                  ? 'bg-blue-50 border-blue-500 text-blue-700'
                  : 'border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              <span className="block text-sm font-medium">User</span>
              <span className="block text-xs text-gray-500">Share with specific user</span>
            </button>
            <button
              type="button"
              onClick={() => setShareType('link')}
              className={`flex-1 py-2 px-4 rounded-md border ${
                shareType === 'link'
                  ? 'bg-blue-50 border-blue-500 text-blue-700'
                  : 'border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              <span className="block text-sm font-medium">Link</span>
              <span className="block text-xs text-gray-500">Anyone with link</span>
            </button>
            <button
              type="button"
              onClick={() => setShareType('public')}
              className={`flex-1 py-2 px-4 rounded-md border ${
                shareType === 'public'
                  ? 'bg-blue-50 border-blue-500 text-blue-700'
                  : 'border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              <span className="block text-sm font-medium">Public</span>
              <span className="block text-xs text-gray-500">Visible to all</span>
            </button>
          </div>
        </div>

        {/* User Email Input */}
        {shareType === 'user' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              User Email
            </label>
            <Input
              type="email"
              value={email}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
              placeholder="Enter user email"
            />
          </div>
        )}

        {/* Permission Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Permission
          </label>
          <select
            value={permission}
            onChange={(e) => setPermission(e.target.value as Permission)}
            className="w-full rounded-md border border-gray-300 py-2 px-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="view">View only</option>
            <option value="comment">Can comment</option>
            <option value="edit">Can edit</option>
            <option value="admin">Admin</option>
          </select>
        </div>

        {/* Link Options */}
        {shareType === 'link' && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Link Expiration (days)
              </label>
              <Input
                type="number"
                value={expiresInDays || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setExpiresInDays(e.target.value ? parseInt(e.target.value) : undefined)}
                placeholder="Never expires"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Password Protection (optional)
              </label>
              <Input
                type="password"
                value={linkPassword}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLinkPassword(e.target.value)}
                placeholder="Leave empty for no password"
              />
            </div>
          </>
        )}

        {/* Message */}
        {shareType === 'user' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Message (optional)
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Add a message for the recipient"
              rows={2}
              className="w-full rounded-md border border-gray-300 py-2 px-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}

        {/* Share Link Display */}
        {shareLink && (
          <div className="bg-green-50 border border-green-200 rounded-md p-4">
            <p className="text-sm text-green-800 font-medium mb-2">Share link created!</p>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={shareLink}
                readOnly
                className="flex-1 text-sm bg-white border border-green-300 rounded px-2 py-1"
              />
              <Button variant="secondary" onClick={copyShareLink}>
                Copy
              </Button>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-3">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-4">
          <Button variant="secondary" onClick={handleClose}>
            {shareLink ? 'Done' : 'Cancel'}
          </Button>
          {!shareLink && (
            <Button onClick={handleShare} disabled={isLoading}>
              {isLoading ? 'Sharing...' : 'Share'}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
};

export default ShareDialog;