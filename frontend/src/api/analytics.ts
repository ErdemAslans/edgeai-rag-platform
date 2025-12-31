/**
 * Analytics API client for frontend
 */

import apiClient from './client';

// Types
export interface DailyCount {
  date: string;
  count: number;
}

export interface AgentCount {
  agent: string;
  count: number;
}

export interface UsageSummary {
  period_days: number;
  total_queries: number;
  daily_queries: DailyCount[];
  avg_response_time_ms: number;
  total_tokens: number;
  avg_tokens_per_query: number;
  queries_by_agent: AgentCount[];
  estimated_cost: number;
}

export interface KeywordCount {
  keyword: string;
  count: number;
}

export interface TimePatterns {
  by_hour: Record<string, number>;
  by_day_of_week: Record<string, number>;
  peak_hour: number;
  peak_day: string;
}

export interface QueryPatterns {
  period_days: number;
  total_queries_analyzed: number;
  top_keywords: KeywordCount[];
  query_type_distribution: Record<string, number>;
  time_patterns: TimePatterns;
}

export interface DocumentTypeCount {
  type: string;
  count: number;
}

export interface DocumentAnalytics {
  period_days: number;
  total_documents: number;
  documents_by_status: Record<string, number>;
  documents_by_type: DocumentTypeCount[];
  total_chunks: number;
  avg_chunks_per_document: number;
}

export interface DailyCost {
  date: string;
  cost: number;
}

export interface AgentCost {
  agent: string;
  tokens: number;
  cost: number;
}

export interface CostBreakdown {
  llm_inference: number;
  embeddings: number;
  other: number;
}

export interface CostTracking {
  period_days: number;
  total_tokens: number;
  total_cost: number;
  daily_costs: DailyCost[];
  cost_by_agent: AgentCost[];
  projected_monthly_cost: number;
  cost_breakdown: CostBreakdown;
}

export interface ResponseTimePercentiles {
  p50: number;
  p90: number;
  p99: number;
  min: number;
  max: number;
  avg: number;
}

export interface PerformanceMetrics {
  period_days: number;
  total_queries: number;
  response_time_percentiles: ResponseTimePercentiles;
  error_rate: number;
  cache_hit_rate: number;
  satisfaction_rate: number;
  availability: number;
}

export interface TrendingTopic {
  topic: string;
  current_count: number;
  previous_count: number;
  growth_rate: number;
  trend: 'up' | 'down' | 'stable';
}

export interface DashboardData {
  usage: UsageSummary;
  performance: PerformanceMetrics;
  trending: TrendingTopic[];
  document_stats: DocumentAnalytics;
}

// API Functions

/**
 * Get usage summary
 */
export async function getUsageSummary(days: number = 30): Promise<UsageSummary> {
  const response = await apiClient.get<UsageSummary>('/analytics/usage', {
    params: { days },
  });
  return response.data;
}

/**
 * Get system-wide usage summary (admin)
 */
export async function getSystemUsageSummary(days: number = 30): Promise<UsageSummary> {
  const response = await apiClient.get<UsageSummary>('/analytics/usage/system', {
    params: { days },
  });
  return response.data;
}

/**
 * Get query patterns
 */
export async function getQueryPatterns(days: number = 30, topN: number = 20): Promise<QueryPatterns> {
  const response = await apiClient.get<QueryPatterns>('/analytics/patterns', {
    params: { days, top_n: topN },
  });
  return response.data;
}

/**
 * Get document analytics
 */
export async function getDocumentAnalytics(days: number = 30): Promise<DocumentAnalytics> {
  const response = await apiClient.get<DocumentAnalytics>('/analytics/documents', {
    params: { days },
  });
  return response.data;
}

/**
 * Get cost tracking
 */
export async function getCostTracking(days: number = 30): Promise<CostTracking> {
  const response = await apiClient.get<CostTracking>('/analytics/costs', {
    params: { days },
  });
  return response.data;
}

/**
 * Get system-wide cost tracking (admin)
 */
export async function getSystemCostTracking(days: number = 30): Promise<CostTracking> {
  const response = await apiClient.get<CostTracking>('/analytics/costs/system', {
    params: { days },
  });
  return response.data;
}

/**
 * Get performance metrics
 */
export async function getPerformanceMetrics(days: number = 7): Promise<PerformanceMetrics> {
  const response = await apiClient.get<PerformanceMetrics>('/analytics/performance', {
    params: { days },
  });
  return response.data;
}

/**
 * Get trending topics
 */
export async function getTrendingTopics(days: number = 7, topN: number = 10): Promise<TrendingTopic[]> {
  const response = await apiClient.get<TrendingTopic[]>('/analytics/trending', {
    params: { days, top_n: topN },
  });
  return response.data;
}

/**
 * Get combined dashboard data
 */
export async function getDashboardData(): Promise<DashboardData> {
  const response = await apiClient.get<DashboardData>('/analytics/dashboard');
  return response.data;
}

/**
 * Export analytics data
 */
export async function exportAnalytics(days: number = 30, format: 'json' | 'csv' = 'json'): Promise<Blob | object> {
  if (format === 'csv') {
    const response = await apiClient.get('/analytics/export', {
      params: { days, format },
      responseType: 'blob',
    });
    return response.data;
  }
  
  const response = await apiClient.get('/analytics/export', {
    params: { days, format },
  });
  return response.data;
}

/**
 * Download analytics as CSV
 */
export async function downloadAnalyticsCSV(days: number = 30): Promise<void> {
  const blob = await exportAnalytics(days, 'csv') as Blob;
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `analytics_${days}d.csv`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}