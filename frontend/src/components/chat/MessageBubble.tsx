import { Message, RoutingInfo } from '@/types';
import { formatDateTime } from '@/lib/utils';
import SourceReference from './SourceReference';
import { Bot, Zap, Clock } from 'lucide-react';

// Extended message interface for routing info
interface ExtendedMessage extends Message {
  routing?: RoutingInfo;
  executionTime?: number;
}

interface MessageBubbleProps {
  message: ExtendedMessage;
}

// Agent display names and colors
const AGENT_INFO: Record<string, { label: string; color: string }> = {
  rag_query: { label: '📄 RAG Search', color: 'text-blue-600' },
  summarizer: { label: '📝 Summarizer', color: 'text-green-600' },
  document_analyzer: { label: '🔍 Analyzer', color: 'text-purple-600' },
  sql_generator: { label: '🗄️ SQL Generator', color: 'text-orange-600' },
  query_router: { label: '🚦 Router', color: 'text-yellow-600' },
  error: { label: '❌ Error', color: 'text-red-600' },
};

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.role === 'user';
  const agentInfo = message.agent ? AGENT_INFO[message.agent] || { label: message.agent, color: 'text-accent' } : null;

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
          <div className="flex items-center gap-2 mb-2 pb-2 border-b border-border/50">
            <Bot className="w-4 h-4 text-accent" />
            <span className={`text-xs font-medium ${agentInfo.color}`}>
              {agentInfo.label}
            </span>
            {/* Routing confidence */}
            {message.routing && (
              <span className="flex items-center gap-1 text-xs text-text-secondary">
                <Zap className="w-3 h-3" />
                {Math.round(message.routing.confidence * 100)}% confidence
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
