import api from './client';
import { Agent, AgentExecution } from '@/types';

interface AgentListAPIResponse {
  agents: Array<{
    name: string;
    description: string;
    status: string;
    capabilities: string[];
  }>;
  total: number;
}

interface AgentLogsAPIResponse {
  logs: Array<{
    id: string;
    agent_name: string;
    action: string | null;
    status: string;
    execution_time_ms: number | null;
    created_at: string;
    error_message: string | null;
  }>;
  total: number;
  skip: number;
  limit: number;
}

interface AgentExecuteAPIResponse {
  execution_id: string;
  agent_name: string;
  status: string;
  output: Record<string, unknown>;
  execution_time_ms: number;
}

export const getAgents = async (): Promise<Agent[]> => {
  const response = await api.get<AgentListAPIResponse>('/agents/');
  // Map backend response to frontend type
  return response.data.agents.map(a => ({
    name: a.name,
    description: a.description,
    status: a.status as 'active' | 'inactive',
  }));
};

export const executeAgent = async (name: string, params: Record<string, unknown>): Promise<AgentExecution> => {
  const response = await api.post<AgentExecuteAPIResponse>(`/agents/${name}/execute`, { input_data: params });
  // Map backend response to frontend type
  return {
    id: response.data.execution_id,
    agent_name: response.data.agent_name,
    action: 'execute',
    duration: response.data.execution_time_ms,
    status: response.data.status as 'success' | 'failed' | 'pending',
    timestamp: new Date().toISOString(),
    details: response.data.output,
  };
};

export const getAgentLogs = async (): Promise<AgentExecution[]> => {
  const response = await api.get<AgentLogsAPIResponse>('/agents/logs');
  // Map backend response to frontend type
  return response.data.logs.map(log => ({
    id: log.id,
    agent_name: log.agent_name,
    action: log.action || 'execute',
    duration: log.execution_time_ms || 0,
    status: log.status as 'success' | 'failed' | 'pending',
    timestamp: log.created_at,
    details: log.error_message ? { error: log.error_message } : undefined,
  }));
};
