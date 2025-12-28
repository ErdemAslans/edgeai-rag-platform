import { create } from 'zustand';
import { Message, ChatHistory } from '@/types';

interface ChatState {
  currentConversation: Message[];
  conversations: ChatHistory[];
  currentConversationId: string | null;
  isLoading: boolean;
  
  setCurrentConversation: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  setConversations: (conversations: ChatHistory[]) => void;
  setCurrentConversationId: (id: string | null) => void;
  setLoading: (loading: boolean) => void;
  clearCurrentConversation: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  currentConversation: [],
  conversations: [],
  currentConversationId: null,
  isLoading: false,
  
  setCurrentConversation: (messages) => set({ currentConversation: messages }),
  
  addMessage: (message) =>
    set((state) => ({
      currentConversation: [...state.currentConversation, message],
    })),
  
  setConversations: (conversations) => set({ conversations }),
  
  setCurrentConversationId: (id) => set({ currentConversationId: id }),
  
  setLoading: (loading) => set({ isLoading: loading }),
  
  clearCurrentConversation: () =>
    set({
      currentConversation: [],
      currentConversationId: null,
    }),
}));
