/**
 * Comment Section Component
 * 
 * Displays and manages comments on a document.
 */

import React, { useState, useEffect, useCallback } from 'react';
import Button from '../ui/Button';
import { 
  getComments, 
  addComment, 
  resolveComment, 
  Comment 
} from '../../api/collaboration';

interface CommentSectionProps {
  documentId: string;
  canComment?: boolean;
}

interface CommentItemProps {
  comment: Comment;
  onReply: (parentId: string) => void;
  onResolve: (commentId: string) => void;
  canComment?: boolean;
  depth?: number;
}

const CommentItem: React.FC<CommentItemProps> = ({
  comment,
  onReply,
  onResolve,
  canComment = true,
  depth = 0,
}) => {
  const maxDepth = 3;
  const canNest = depth < maxDepth;

  return (
    <div className={`${depth > 0 ? 'ml-6 border-l-2 border-gray-200 pl-4' : ''}`}>
      <div className={`bg-white rounded-lg p-4 ${comment.is_resolved ? 'opacity-60' : ''}`}>
        {/* Comment header */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium">
              {comment.user_name.charAt(0).toUpperCase()}
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900">{comment.user_name}</p>
              <p className="text-xs text-gray-500">
                {new Date(comment.created_at).toLocaleString()}
              </p>
            </div>
          </div>
          {comment.is_resolved && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
              Resolved
            </span>
          )}
        </div>

        {/* Comment content */}
        <p className="text-gray-700 text-sm mb-3">{comment.content}</p>

        {/* Comment actions */}
        {canComment && !comment.is_resolved && (
          <div className="flex items-center space-x-4">
            {canNest && (
              <button
                onClick={() => onReply(comment.id)}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                Reply
              </button>
            )}
            <button
              onClick={() => onResolve(comment.id)}
              className="text-sm text-gray-600 hover:text-gray-800"
            >
              Resolve
            </button>
          </div>
        )}
      </div>

      {/* Replies */}
      {comment.replies && comment.replies.length > 0 && (
        <div className="mt-2 space-y-2">
          {comment.replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              onReply={onReply}
              onResolve={onResolve}
              canComment={canComment}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const CommentSection: React.FC<CommentSectionProps> = ({
  documentId,
  canComment = true,
}) => {
  const [comments, setComments] = useState<Comment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newComment, setNewComment] = useState('');
  const [replyingTo, setReplyingTo] = useState<string | null>(null);
  const [showResolved, setShowResolved] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchComments = useCallback(async () => {
    try {
      const result = await getComments(documentId, showResolved);
      setComments(result.comments);
    } catch (err) {
      setError('Failed to load comments');
      console.error('Failed to fetch comments:', err);
    } finally {
      setIsLoading(false);
    }
  }, [documentId, showResolved]);

  useEffect(() => {
    fetchComments();
  }, [fetchComments]);

  const handleSubmit = async () => {
    if (!newComment.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await addComment(
        documentId,
        newComment.trim(),
        undefined,
        undefined,
        replyingTo || undefined
      );
      setNewComment('');
      setReplyingTo(null);
      await fetchComments();
    } catch (err) {
      setError('Failed to add comment');
      console.error('Failed to add comment:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResolve = async (commentId: string) => {
    try {
      await resolveComment(commentId);
      await fetchComments();
    } catch (err) {
      setError('Failed to resolve comment');
      console.error('Failed to resolve comment:', err);
    }
  };

  const handleReply = (parentId: string) => {
    setReplyingTo(parentId);
    // Focus on the input
    const input = document.getElementById('comment-input');
    input?.focus();
  };

  const cancelReply = () => {
    setReplyingTo(null);
  };

  if (isLoading) {
    return (
      <div className="p-4">
        <div className="animate-pulse space-y-4">
          <div className="h-20 bg-gray-200 rounded" />
          <div className="h-20 bg-gray-200 rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          Comments ({comments.length})
        </h3>
        <label className="flex items-center text-sm text-gray-600">
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)}
            className="mr-2 rounded border-gray-300"
          />
          Show resolved
        </label>
      </div>

      {/* Error display */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* Comment input */}
      {canComment && (
        <div className="mb-4">
          {replyingTo && (
            <div className="mb-2 flex items-center justify-between bg-blue-50 px-3 py-2 rounded">
              <span className="text-sm text-blue-800">Replying to comment</span>
              <button
                onClick={cancelReply}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                Cancel
              </button>
            </div>
          )}
          <textarea
            id="comment-input"
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder={replyingTo ? 'Write a reply...' : 'Write a comment...'}
            rows={3}
            className="w-full rounded-md border border-gray-300 py-2 px-3 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
          <div className="mt-2 flex justify-end">
            <Button
              onClick={handleSubmit}
              disabled={isSubmitting || !newComment.trim()}
            >
              {isSubmitting ? 'Posting...' : replyingTo ? 'Reply' : 'Comment'}
            </Button>
          </div>
        </div>
      )}

      {/* Comments list */}
      <div className="space-y-4">
        {comments.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-500">No comments yet</p>
            {canComment && (
              <p className="text-sm text-gray-400 mt-1">
                Be the first to leave a comment
              </p>
            )}
          </div>
        ) : (
          comments.map((comment) => (
            <CommentItem
              key={comment.id}
              comment={comment}
              onReply={handleReply}
              onResolve={handleResolve}
              canComment={canComment}
            />
          ))
        )}
      </div>
    </div>
  );
};

export default CommentSection;