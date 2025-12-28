import { Message } from '@/types';
import { formatDateTime } from '@/lib/utils';
import SourceReference from './SourceReference';

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[70%] rounded-lg p-4 ${
          isUser
            ? 'bg-accent/10 text-text-primary'
            : 'bg-white border border-border text-text-primary'
        }`}
      >
        {message.agent && !isUser && (
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-medium text-accent">
              {message.agent}
            </span>
          </div>
        )}
        
        <p className="text-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
        </p>
        
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
