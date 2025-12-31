/**
 * Document versioning API client
 */

import apiClient from './client';

// Types
export interface VersionInfo {
  id: string;
  version_number: number;
  version_type: string;
  title: string;
  content_hash: string | null;
  file_size: number | null;
  change_summary: string | null;
  changed_by: string | null;
  created_at: string;
  diff_stats: {
    lines_added: number;
    lines_removed: number;
    lines_changed: number;
  } | null;
}

export interface VersionHistoryResponse {
  document_id: string;
  total_versions: number;
  versions: VersionInfo[];
}

export interface VersionContentResponse {
  document_id: string;
  version_number: number;
  title: string;
  content: string | null;
  created_at: string;
}

export interface DiffResponse {
  from_version: number;
  to_version: number;
  from_version_info: {
    title: string | null;
    created_at: string | null;
  };
  to_version_info: {
    title: string | null;
    created_at: string | null;
  };
  diff_content: string | null;
}

export interface CompareResponse {
  version_a: {
    number: number;
    title: string;
    content: string | null;
    content_hash: string | null;
    created_at: string;
    changed_by: string | null;
  };
  version_b: {
    number: number;
    title: string;
    content: string | null;
    content_hash: string | null;
    created_at: string;
    changed_by: string | null;
  };
  diff: string | null;
  same_content: boolean;
}

export interface RollbackResponse {
  success: boolean;
  message: string;
  new_version_number: number;
}

export interface AuditLogEntry {
  id: string;
  action: string;
  action_details: Record<string, unknown> | null;
  user_id: string | null;
  version_id: string | null;
  ip_address: string | null;
  success: boolean;
  error_message: string | null;
  created_at: string;
}

export interface AuditLogResponse {
  document_id: string;
  entries: AuditLogEntry[];
}

export interface CreateVersionResponse {
  version_id: string;
  version_number: number;
  created_at: string;
}

// API Functions

/**
 * Get version history for a document
 */
export async function getVersionHistory(
  documentId: string,
  skip: number = 0,
  limit: number = 50
): Promise<VersionHistoryResponse> {
  const response = await apiClient.get<VersionHistoryResponse>(
    `/documents/${documentId}/versions`,
    { params: { skip, limit } }
  );
  return response.data;
}

/**
 * Get content of a specific version
 */
export async function getVersionContent(
  documentId: string,
  versionNumber: number
): Promise<VersionContentResponse> {
  const response = await apiClient.get<VersionContentResponse>(
    `/documents/${documentId}/versions/${versionNumber}`
  );
  return response.data;
}

/**
 * Get diff between two versions
 */
export async function getVersionDiff(
  documentId: string,
  fromVersion: number,
  toVersion?: number
): Promise<DiffResponse> {
  const response = await apiClient.get<DiffResponse>(
    `/documents/${documentId}/versions/${fromVersion}/diff`,
    { params: toVersion ? { to_version: toVersion } : {} }
  );
  return response.data;
}

/**
 * Compare two versions side by side
 */
export async function compareVersions(
  documentId: string,
  versionA: number,
  versionB: number
): Promise<CompareResponse> {
  const response = await apiClient.get<CompareResponse>(
    `/documents/${documentId}/versions/${versionA}/compare/${versionB}`
  );
  return response.data;
}

/**
 * Rollback to a previous version
 */
export async function rollbackToVersion(
  documentId: string,
  versionNumber: number,
  reason?: string
): Promise<RollbackResponse> {
  const response = await apiClient.post<RollbackResponse>(
    `/documents/${documentId}/versions/${versionNumber}/rollback`,
    reason ? { reason } : {}
  );
  return response.data;
}

/**
 * Get audit log for a document
 */
export async function getAuditLog(
  documentId: string,
  skip: number = 0,
  limit: number = 100
): Promise<AuditLogResponse> {
  const response = await apiClient.get<AuditLogResponse>(
    `/documents/${documentId}/versions/audit-log`,
    { params: { skip, limit } }
  );
  return response.data;
}

/**
 * Create a manual version snapshot
 */
export async function createVersion(
  documentId: string,
  changeSummary?: string
): Promise<CreateVersionResponse> {
  const response = await apiClient.post<CreateVersionResponse>(
    `/documents/${documentId}/versions`,
    changeSummary ? { change_summary: changeSummary } : {}
  );
  return response.data;
}