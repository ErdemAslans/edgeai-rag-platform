import { useMutation } from '@tanstack/react-query';
import { sendChatMessage, getChatHistory } from '@/api/queries';
import { QueryResponse, ChatHistory } from '@/types';
import { useChatStore } from '@/stores/chatStore';
import { useToast } from '@/components/ui/Toast';

export const useChat = () => {
  const { addToast } = useToast();
  const {
    currentConversation,
    conversations,
    setCurrentConversation,
    addMessage,
    setConversations,
    setCurrentConversationId,
    clearCurrentConversation,
    isLoading,
    setLoading,
  } = useChatStore();

  const sendMessageMutation = useMutation({
    mutationFn: async ({ message, conversationId }: { message: string; conversationId?: string }) => {
      setLoading(true);
      const response = await sendChatMessage(message, conversationId);
      return response;
    },
    onSuccess: (data: QueryResponse, variables) => {
      const userMessage = {
        id: Date.now().toString(),
        role: 'user' as const,
        content: variables.message,
        timestamp: new Date().toISOString(),
      };

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant' as const,
        content: data.response,
        timestamp: new Date().toISOString(),
        agent: data.agent_used,
        sources: data.sources,
      };

      addMessage(userMessage);
      addMessage(assistantMessage);
      setLoading(false);
    },
    onError: (error: any) => {
      setLoading(false);
      addToast(error.response?.data?.detail || 'Failed to send message. Please try again.', 'error');
    },
  });

  const loadHistoryMutation = useMutation({
    mutationFn: getChatHistory,
    onSuccess: (data: ChatHistory[]) => {
      setConversations(data);
    },
    onError: (error: any) => {
      addToast('Failed to load chat history.', 'error');
    },
  });

  const sendMessage = (message: string, conversationId?: string) => {
    sendMessageMutation.mutate({ message, conversationId });
  };

  const loadHistory = () => {
    loadHistoryMutation.mutate();
  };

  return {
    currentConversation,
    conversations,
    sendMessage,
    loadHistory,
    isLoading,
    clearCurrentConversation,
    setCurrentConversationId,
  };
};
