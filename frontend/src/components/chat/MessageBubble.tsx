import { Message, RoutingInfo, AgentFramework } from '@/types';
import { formatDateTime } from '@/lib/utils';
import SourceReference from './SourceReference';
import { Bot, Zap, Clock, GitBranch, Users, Sparkles } from 'lucide-react';

// Extended message interface for routing info
interface ExtendedMessage extends Message {
  routing?: RoutingInfo;
  executionTime?: number;
  framework?: AgentFramework;
  reasoningTrace?: string;
}

interface MessageBubbleProps {
  message: ExtendedMessage;
}

// Agent display names and colors
const AGENT_INFO: Record<string, { label: string; color: string }> = {
  // Custom agents
  rag_query: { label: '📄 RAG Search', color: 'text-blue-600' },
  summarizer: { label: '📝 Summarizer', color: 'text-blue-600' },
  document_analyzer: { label: '🔍 Analyzer', color: 'text-blue-600' },
  sql_generator: { label: '🗄️ SQL Generator', color: 'text-blue-600' },
  query_router: { label: '🚦 Router', color: 'text-blue-600' },
  // LangGraph agents
  lg_research: { label: '🔬 LG Research', color: 'text-purple-600' },
  lg_analysis: { label: '📊 LG Analysis', color: 'text-purple-600' },
  lg_reasoning: { label: '💡 LG Reasoning', color: 'text-purple-600' },
  // CrewAI agents
  crew_research: { label: '👥 Research Crew', color: 'text-green-600' },
  crew_qa: { label: '✅ QA Crew', color: 'text-green-600' },
  crew_code_review: { label: '💻 Code Review Crew', color: 'text-green-600' },
  // GenAI agents
  genai_conversational: { label: '💬 GenAI Chat', color: 'text-orange-600' },
  genai_task_executor: { label: '⚡ GenAI Task', color: 'text-orange-600' },
  genai_knowledge: { label: '📚 GenAI Knowledge', color: 'text-orange-600' },
  genai_reasoning: { label: '🧠 GenAI Reasoning', color: 'text-orange-600' },
  genai_creative: { label: '✨ GenAI Creative', color: 'text-orange-600' },
  error: { label: '❌ Error', color: 'text-red-600' },
};

// Framework display info
const FRAMEWORK_INFO: Record<string, { label: string; color: string; bgColor: string; icon: React.ReactNode }> = {
  custom: { label: 'Custom', color: 'text-blue-600', bgColor: 'bg-blue-100', icon: <Bot className="w-3 h-3" /> },
  langgraph: { label: 'LangGraph', color: 'text-purple-600', bgColor: 'bg-purple-100', icon: <GitBranch className="w-3 h-3" /> },
  crewai: { label: 'CrewAI', color: 'text-green-600', bgColor: 'bg-green-100', icon: <Users className="w-3 h-3" /> },
  genai: { label: 'GenAI', color: 'text-orange-600', bgColor: 'bg-orange-100', icon: <Sparkles className="w-3 h-3" /> },
};

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.role === 'user';
  const agentInfo = message.agent ? AGENT_INFO[message.agent] || { label: message.agent, color: 'text-accent' } : null;
  const frameworkInfo = message.framework ? FRAMEWORK_INFO[message.framework] || FRAMEWORK_INFO.custom : null;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[70%] rounded-lg p-4 ${
          isUser
            ? 'bg-accent/10 text-text-primary'
            : 'bg-white border border-border text-text-primary'
        }`}
      >
        {/* Agent info header */}
        {agentInfo && !isUser && (
          <div className="flex flex-wrap items-center gap-2 mb-2 pb-2 border-b border-border/50">
            <Bot className="w-4 h-4 text-accent" />
            <span className={`text-xs font-medium ${agentInfo.color}`}>
              {agentInfo.label}
            </span>
            {/* Framework badge */}
            {frameworkInfo && (
              <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${frameworkInfo.bgColor} ${frameworkInfo.color}`}>
                {frameworkInfo.icon}
                {frameworkInfo.label}
              </span>
            )}
            {/* Routing confidence */}
            {message.routing && (
              <span className="flex items-center gap-1 text-xs text-text-secondary">
                <Zap className="w-3 h-3" />
                {Math.round(message.routing.confidence * 100)}%
              </span>
            )}
            {/* Execution time */}
            {message.executionTime && (
              <span className="flex items-center gap-1 text-xs text-text-secondary">
                <Clock className="w-3 h-3" />
                {Math.round(message.executionTime)}ms
              </span>
            )}
          </div>
        )}
        
        <p className="text-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
        </p>
        
        {/* Routing reason tooltip */}
        {message.routing && message.routing.reason && !isUser && (
          <div className="mt-2 p-2 bg-secondary/50 rounded text-xs text-text-secondary">
            <span className="font-medium">Routing:</span> {message.routing.reason}
          </div>
        )}
        
        {/* Reasoning trace (for reasoning agents) */}
        {message.reasoningTrace && !isUser && (
          <details className="mt-2">
            <summary className="text-xs text-text-secondary cursor-pointer hover:text-accent">
              View reasoning trace
            </summary>
            <div className="mt-1 p-2 bg-secondary/50 rounded text-xs text-text-secondary whitespace-pre-wrap">
              {message.reasoningTrace}
            </div>
          </details>
        )}
        
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3">
            <SourceReference sources={message.sources} />
          </div>
        )}
        
        <p className="text-xs text-text-secondary mt-2">
          {formatDateTime(message.timestamp)}
        </p>
      </div>
    </div>
  );
};

export default MessageBubble;
