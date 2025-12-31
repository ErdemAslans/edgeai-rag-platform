/**
 * Collaboration API client
 */

import apiClient from './client';

// Types

export interface ShareDocumentRequest {
  document_id: string;
  share_type: 'user' | 'team' | 'public' | 'link';
  shared_with_user_id?: string;
  shared_with_team_id?: string;
  permission: 'view' | 'comment' | 'edit' | 'admin';
  message?: string;
  link_expires_in_days?: number;
  link_password?: string;
}

export interface ShareResponse {
  id: string;
  document_id: string;
  share_type: string;
  permission: string;
  share_link_token?: string;
  created_at: string;
}

export interface SharedDocument {
  share_id: string;
  document_id: string;
  document_title: string;
  permission: string;
  shared_by?: string;
  shared_at: string;
  message?: string;
}

export interface DocumentShare {
  id: string;
  share_type: string;
  permission: string;
  created_at: string;
  shared_with_user_id?: string;
  share_link_token?: string;
  expires_at?: string;
}

export interface Collaborator {
  session_id: string;
  user_id: string;
  user_name: string;
  cursor_position?: {
    line?: number;
    column?: number;
  };
  connected_at: string;
}

export interface Comment {
  id: string;
  content: string;
  user_id?: string;
  user_name: string;
  anchor_type?: string;
  anchor_data?: Record<string, unknown>;
  is_resolved: boolean;
  created_at: string;
  replies: Comment[];
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  message?: string;
  document_id?: string;
  is_read: boolean;
  created_at: string;
}

export interface SessionResponse {
  session_id: string;
  session_token: string;
  document_id: string;
}

// API Functions

/**
 * Share a document
 */
export async function shareDocument(request: ShareDocumentRequest): Promise<ShareResponse> {
  const response = await apiClient.post('/collaboration/share', request);
  return response.data;
}

/**
 * Get documents shared with the current user
 */
export async function getSharedWithMe(
  skip: number = 0,
  limit: number = 50
): Promise<{ shares: SharedDocument[]; total: number }> {
  const response = await apiClient.get('/collaboration/shared-with-me', {
    params: { skip, limit },
  });
  return response.data;
}

/**
 * Get all shares for a document
 */
export async function getDocumentShares(documentId: string): Promise<{ shares: DocumentShare[] }> {
  const response = await apiClient.get(`/collaboration/documents/${documentId}/shares`);
  return response.data;
}

/**
 * Revoke a share
 */
export async function revokeShare(shareId: string): Promise<void> {
  await apiClient.delete(`/collaboration/shares/${shareId}`);
}

/**
 * Update share permission
 */
export async function updateSharePermission(
  shareId: string,
  permission: 'view' | 'comment' | 'edit' | 'admin'
): Promise<{ id: string; permission: string }> {
  const response = await apiClient.patch(`/collaboration/shares/${shareId}/permission`, {
    permission,
  });
  return response.data;
}

/**
 * Start a collaboration session
 */
export async function startSession(
  documentId: string,
  clientId?: string,
  clientInfo?: Record<string, unknown>
): Promise<SessionResponse> {
  const response = await apiClient.post('/collaboration/sessions/start', {
    document_id: documentId,
    client_id: clientId,
    client_info: clientInfo,
  });
  return response.data;
}

/**
 * Send heartbeat to keep session alive
 */
export async function sendHeartbeat(
  sessionId: string,
  cursorPosition?: { line?: number; column?: number },
  viewport?: Record<string, unknown>
): Promise<void> {
  await apiClient.post(`/collaboration/sessions/${sessionId}/heartbeat`, {
    cursor_position: cursorPosition,
    viewport,
  });
}

/**
 * End a collaboration session
 */
export async function endSession(sessionId: string): Promise<void> {
  await apiClient.post(`/collaboration/sessions/${sessionId}/end`);
}

/**
 * Get active collaborators on a document
 */
export async function getCollaborators(documentId: string): Promise<{ collaborators: Collaborator[] }> {
  const response = await apiClient.get(`/collaboration/documents/${documentId}/collaborators`);
  return response.data;
}

/**
 * Add a comment to a document
 */
export async function addComment(
  documentId: string,
  content: string,
  anchorType?: string,
  anchorData?: Record<string, unknown>,
  parentId?: string
): Promise<Comment> {
  const response = await apiClient.post(`/collaboration/documents/${documentId}/comments`, {
    content,
    anchor_type: anchorType,
    anchor_data: anchorData,
    parent_id: parentId,
  });
  return response.data;
}

/**
 * Get comments for a document
 */
export async function getComments(
  documentId: string,
  includeResolved: boolean = false
): Promise<{ comments: Comment[] }> {
  const response = await apiClient.get(`/collaboration/documents/${documentId}/comments`, {
    params: { include_resolved: includeResolved },
  });
  return response.data;
}

/**
 * Resolve a comment
 */
export async function resolveComment(commentId: string): Promise<{ id: string; is_resolved: boolean }> {
  const response = await apiClient.post(`/collaboration/comments/${commentId}/resolve`);
  return response.data;
}

/**
 * Get notifications
 */
export async function getNotifications(
  unreadOnly: boolean = false,
  skip: number = 0,
  limit: number = 50
): Promise<{ notifications: Notification[] }> {
  const response = await apiClient.get('/collaboration/notifications', {
    params: { unread_only: unreadOnly, skip, limit },
  });
  return response.data;
}

/**
 * Mark a notification as read
 */
export async function markNotificationRead(notificationId: string): Promise<void> {
  await apiClient.post(`/collaboration/notifications/${notificationId}/read`);
}

/**
 * Mark all notifications as read
 */
export async function markAllNotificationsRead(): Promise<{ marked_read: number }> {
  const response = await apiClient.post('/collaboration/notifications/read-all');
  return response.data;
}