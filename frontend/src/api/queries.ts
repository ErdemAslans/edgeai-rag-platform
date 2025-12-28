import api from './client';
import { QueryResponse, ChatHistory, Message } from '@/types';

interface QueryHistoryAPIResponse {
  queries: Array<{
    query_id: string;
    query: string;
    response: string;
    sources: Array<{
      document_id: string;
      document_name: string;
      chunk_id: string;
      content: string;
      score: number;
    }>;
    agent_used: string;
  }>;
  total: number;
  skip: number;
  limit: number;
}

export const askQuestion = async (query: string, documentIds?: string[]): Promise<QueryResponse> => {
  const response = await api.post<{ query_id: string; query: string; response: string; sources: any[]; agent_used: string }>('/queries/ask', {
    query,
    document_ids: documentIds,
  });
  // Map backend response to frontend type
  return {
    id: response.data.query_id,
    query: response.data.query,
    response: response.data.response,
    sources: response.data.sources,
    agent_used: response.data.agent_used,
    created_at: new Date().toISOString(),
  };
};

export const sendChatMessage = async (message: string, conversationId?: string): Promise<QueryResponse> => {
  const response = await api.post<{ message_id: string; response: string; context_used: any[] }>('/queries/chat', {
    message,
    conversation_id: conversationId,
  });
  // Map backend response to frontend type
  return {
    id: response.data.message_id,
    query: message,
    response: response.data.response,
    sources: [],
    agent_used: 'document_analyzer',
    created_at: new Date().toISOString(),
  };
};

export const getQueryHistory = async (): Promise<QueryResponse[]> => {
  const response = await api.get<QueryHistoryAPIResponse>('/queries/history');
  // Map backend response to frontend type
  return response.data.queries.map(q => ({
    id: q.query_id,
    query: q.query,
    response: q.response,
    sources: q.sources,
    agent_used: q.agent_used,
    created_at: new Date().toISOString(),
  }));
};

// Use query history as chat history since backend doesn't have separate chat history
export const getChatHistory = async (): Promise<ChatHistory[]> => {
  const response = await api.get<QueryHistoryAPIResponse>('/queries/history');
  // Convert query history to chat history format
  // Group by date or create single conversations from queries
  return response.data.queries.map((q, index) => ({
    id: q.query_id,
    title: q.query.slice(0, 50) + (q.query.length > 50 ? '...' : ''),
    messages: [
      {
        id: `${q.query_id}-user`,
        role: 'user' as const,
        content: q.query,
        timestamp: new Date().toISOString(),
      },
      {
        id: `${q.query_id}-assistant`,
        role: 'assistant' as const,
        content: q.response,
        timestamp: new Date().toISOString(),
        agent: q.agent_used,
        sources: q.sources,
      },
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }));
};
