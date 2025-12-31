import api from './client';

export interface DashboardStats {
  total_documents: number;
  queries_today: number;
  active_agents: number;
  avg_response_time: number;
}

export interface RecentActivity {
  id: string;
  type: 'upload' | 'query' | 'agent_execution';
  description: string;
  timestamp: string;
}

export interface DashboardResponse {
  stats: DashboardStats;
  recent_activity: RecentActivity[];
}

export const getDashboard = async (): Promise<DashboardResponse> => {
  const response = await api.get<DashboardResponse>('/dashboard');
  return response.data;
};

export const getDashboardStats = async (): Promise<DashboardStats> => {
  const response = await api.get<DashboardStats>('/dashboard/stats');
  return response.data;
};

export const getRecentActivity = async (limit: number = 10): Promise<RecentActivity[]> => {
  const response = await api.get<RecentActivity[]>('/dashboard/activity', {
    params: { limit },
  });
  return response.data;
};
