import { useEffect, useRef, useState } from 'react';
import { MessageSquare, Plus } from 'lucide-react';
import PageContainer from '@/components/layout/PageContainer';
import MessageBubble from '@/components/chat/MessageBubble';
import ChatInput from '@/components/chat/ChatInput';
import AgentSelector from '@/components/agents/AgentSelector';
import { useChat } from '@/hooks/useChat';
import { useAgents } from '@/hooks/useAgents';
import { AGENTS } from '@/lib/constants';

const Chat = () => {
  const {
    currentConversation,
    conversations,
    sendMessage,
    loadHistory,
    isLoading,
    clearCurrentConversation,
    setCurrentConversationId,
  } = useChat();
  const { agents } = useAgents();
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentConversation]);

  const handleSendMessage = (message: string) => {
    sendMessage(message, selectedConversationId || undefined);
  };

  const handleNewChat = () => {
    clearCurrentConversation();
    setSelectedConversationId(null);
  };

  const handleSelectConversation = (conversationId: string) => {
    setSelectedConversationId(conversationId);
    setCurrentConversationId(conversationId);
    const conversation = conversations.find((c) => c.id === conversationId);
    if (conversation) {
      // Load conversation messages
    }
  };

  return (
    <div className="min-h-screen bg-secondary">
      <aside className="fixed left-0 top-0 h-screen w-80 bg-white border-r border-border flex flex-col z-30">
        <div className="p-4 border-b border-border">
          <button
            onClick={handleNewChat}
            className="flex items-center gap-2 w-full p-2 border border-border rounded-md hover:bg-gray-50 transition-colors"
          >
            <Plus className="w-5 h-5 text-accent" />
            <span className="text-sm font-medium text-text-primary">New Chat</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {conversations.length === 0 ? (
            <div className="p-4 text-center text-text-secondary">
              <p className="text-sm">No conversations yet.</p>
            </div>
          ) : (
            conversations.map((conversation) => (
              <button
                key={conversation.id}
                onClick={() => handleSelectConversation(conversation.id)}
                className={`w-full text-left p-4 border-b border-border hover:bg-gray-50 transition-colors ${
                  selectedConversationId === conversation.id ? 'bg-accent/10' : ''
                }`}
              >
                <p className="text-sm font-medium text-text-primary truncate">
                  {conversation.title}
                </p>
                <p className="text-xs text-text-secondary mt-1 truncate">
                  {conversation.messages[conversation.messages.length - 1]?.content}
                </p>
              </button>
            ))
          )}
        </div>
      </aside>

      <main className="ml-80 h-screen flex flex-col">
        <div className="flex-1 overflow-y-auto p-6">
          {currentConversation.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <MessageSquare className="w-16 h-16 mx-auto text-text-secondary mb-4" />
                <h2 className="text-xl font-semibold text-text-primary mb-2">
                  Start a new conversation
                </h2>
                <p className="text-text-secondary">
                  Ask questions about your documents or start a new chat.
                </p>
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto space-y-4">
              {currentConversation.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="border-t border-border bg-white p-4">
          <div className="max-w-4xl mx-auto mb-3">
            <AgentSelector
              agents={agents.map((a) => a.name)}
              selectedAgent={selectedAgent}
              onSelect={setSelectedAgent}
            />
          </div>
          <ChatInput
            onSend={handleSendMessage}
            isLoading={isLoading}
            placeholder="Ask a question about your documents..."
          />
        </div>
      </main>
    </div>
  );
};

export default Chat;
