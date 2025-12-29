import { useMutation } from '@tanstack/react-query';
import { askQuestion, getChatHistory } from '@/api/queries';
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
    mutationFn: async ({ message, documentIds }: { message: string; documentIds?: string[] }) => {
      setLoading(true);
      // Use askQuestion which supports RAG with document_ids
      const response = await askQuestion(message, documentIds);
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

  const sendMessage = (message: string, documentIds?: string[]) => {
    sendMessageMutation.mutate({ message, documentIds });
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
