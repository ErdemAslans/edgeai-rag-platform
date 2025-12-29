export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface LoginRequest {
  username: string;  // OAuth2 uses 'username' field
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
}

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count: number;
  uploaded_at: string;
  user_id: string;
}

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  status: string;
  message: string;
}

export interface SourceReference {
  document_id: string;
  document_name: string;
  chunk_id: string;
  content: string;
  score: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  agent?: string;
  sources?: SourceReference[];
  routing?: RoutingInfo;
  executionTime?: number;
}

export interface RoutingInfo {
  selected_agent: string;
  confidence: number;
  reason: string;
}

export interface QueryResponse {
  id: string;
  query: string;
  response: string;
  sources: SourceReference[];
  agent_used: string;
  created_at: string;
  routing?: RoutingInfo;
  execution_time_ms?: number;
}

export type QueryMode = 'auto' | 'rag' | 'summarize' | 'analyze' | 'sql';

export interface ChatHistory {
  id: string;
  title: string;
  messages: Message[];
  created_at: string;
  updated_at: string;
}

export interface Agent {
  name: string;
  description: string;
  status: 'active' | 'inactive';
  capabilities?: string[];
}

export interface AgentExecution {
  id: string;
  agent_name: string;
  action: string;
  duration: number;
  status: 'success' | 'failed' | 'pending';
  timestamp: string;
  details?: Record<string, unknown>;
}

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
