/**
 * Feedback API client for adaptive learning system
 */

import apiClient from './client';

// Types
export interface FeedbackCreate {
  query_id: string;
  feedback_type?: 'thumbs_up' | 'thumbs_down' | 'rating' | 'detailed';
  is_positive: boolean;
  rating?: number;
  category?: 'irrelevant' | 'incomplete' | 'incorrect' | 'too_long' | 'too_short' | 'wrong_sources' | 'slow' | 'other';
  comment?: string;
}

export interface QuickFeedback {
  query_id: string;
  is_positive: boolean;
}

export interface FeedbackResponse {
  id: string;
  query_id: string;
  user_id: string;
  feedback_type: string;
  is_positive: boolean;
  rating?: number;
  category?: string;
  comment?: string;
  agent_used: string;
  created_at: string;
}

export interface AgentStats {
  agent_name: string;
  total_feedback: number;
  positive_feedback: number;
  negative_feedback: number;
  satisfaction_rate: number;
  avg_rating?: number;
  category_breakdown: Record<string, number>;
  period_start: string;
  period_end: string;
}

export interface RoutingWeights {
  weights: Record<string, number>;
  last_updated: string;
}

export interface LearningInsight {
  insight_type: string;
  title: string;
  description: string;
  impact: 'high' | 'medium' | 'low';
  recommendation: string;
  data: Record<string, unknown>;
}

export interface LearningAnalytics {
  total_feedback_count: number;
  positive_rate: number;
  agents_performance: AgentStats[];
  active_patterns_count: number;
  insights: LearningInsight[];
  period_start: string;
  period_end: string;
}

export interface FeedbackSummary {
  total_feedbacks: number;
  positive_feedbacks: number;
  negative_feedbacks: number;
  satisfaction_rate: number;
  by_agent: Record<string, { positive: number; negative: number }>;
  by_category: Record<string, number>;
  trend: 'improving' | 'stable' | 'declining';
}

export interface QueryPattern {
  id: string;
  pattern_name: string;
  pattern_description?: string;
  keywords: string[];
  best_agent: string;
  best_framework?: string;
  sample_size: number;
  confidence: number;
  avg_satisfaction: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// API Functions

/**
 * Submit detailed feedback for a query
 */
export async function submitFeedback(data: FeedbackCreate): Promise<FeedbackResponse> {
  const response = await apiClient.post<FeedbackResponse>('/api/v1/feedback', data);
  return response.data;
}

/**
 * Submit quick thumbs up/down feedback
 */
export async function submitQuickFeedback(data: QuickFeedback): Promise<FeedbackResponse> {
  const response = await apiClient.post<FeedbackResponse>('/api/v1/feedback/quick', data);
  return response.data;
}

/**
 * Get feedback submitted by current user
 */
export async function getMyFeedback(limit = 50, offset = 0): Promise<FeedbackResponse[]> {
  const response = await apiClient.get<FeedbackResponse[]>('/api/v1/feedback/my', {
    params: { limit, offset },
  });
  return response.data;
}

/**
 * Get feedback for a specific query
 */
export async function getQueryFeedback(queryId: string): Promise<FeedbackResponse[]> {
  const response = await apiClient.get<FeedbackResponse[]>(`/api/v1/feedback/query/${queryId}`);
  return response.data;
}

/**
 * Get statistics for a specific agent
 */
export async function getAgentStats(agentName: string, days = 30): Promise<AgentStats> {
  const response = await apiClient.get<AgentStats>(`/api/v1/feedback/stats/agent/${agentName}`, {
    params: { days },
  });
  return response.data;
}

/**
 * Get statistics for all agents
 */
export async function getAllAgentStats(days = 30): Promise<AgentStats[]> {
  const response = await apiClient.get<AgentStats[]>('/api/v1/feedback/stats/all', {
    params: { days },
  });
  return response.data;
}

/**
 * Get current routing weights
 */
export async function getRoutingWeights(): Promise<RoutingWeights> {
  const response = await apiClient.get<RoutingWeights>('/api/v1/feedback/routing-weights');
  return response.data;
}

/**
 * Get learning analytics and insights
 */
export async function getLearningAnalytics(days = 30): Promise<LearningAnalytics> {
  const response = await apiClient.get<LearningAnalytics>('/api/v1/feedback/analytics', {
    params: { days },
  });
  return response.data;
}

/**
 * Get feedback summary
 */
export async function getFeedbackSummary(days = 7): Promise<FeedbackSummary> {
  const response = await apiClient.get<FeedbackSummary>('/api/v1/feedback/summary', {
    params: { days },
  });
  return response.data;
}

/**
 * Get all query patterns
 */
export async function getQueryPatterns(includeInactive = false): Promise<QueryPattern[]> {
  const response = await apiClient.get<QueryPattern[]>('/api/v1/feedback/patterns', {
    params: { include_inactive: includeInactive },
  });
  return response.data;
}

/**
 * Create a new query pattern
 */
export async function createPattern(data: {
  pattern_name: string;
  pattern_description?: string;
  keywords: string[];
  best_agent: string;
  best_framework?: string;
}): Promise<QueryPattern> {
  const response = await apiClient.post<QueryPattern>('/api/v1/feedback/patterns', data);
  return response.data;
}

/**
 * Update a query pattern
 */
export async function updatePattern(
  patternId: string,
  data: Partial<{
    pattern_name: string;
    pattern_description: string;
    keywords: string[];
    best_agent: string;
    best_framework: string;
    is_active: boolean;
  }>
): Promise<QueryPattern> {
  const response = await apiClient.patch<QueryPattern>(`/api/v1/feedback/patterns/${patternId}`, data);
  return response.data;
}

/**
 * Delete a query pattern
 */
export async function deletePattern(patternId: string): Promise<void> {
  await apiClient.delete(`/api/v1/feedback/patterns/${patternId}`);
}