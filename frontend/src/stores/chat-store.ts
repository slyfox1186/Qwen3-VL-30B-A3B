import { create } from 'zustand';
import { Message, SearchResult } from '@/types/api';

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentContent: string; // Accumulates content during stream
  currentSearchResults: SearchResult[] | undefined;
  currentSearchQuery: string | undefined;
  error: string | null;
  editingMessageId: string | null;

  addMessage: (message: Message) => void;
  setMessages: (messages: Message[]) => void;
  setStreaming: (isStreaming: boolean) => void;
  appendContent: (delta: string) => void;
  setSearchResults: (results: SearchResult[], query?: string) => void;
  resetCurrentStream: () => void;
  setError: (error: string | null) => void;
  setEditingMessageId: (id: string | null) => void;
  removeMessagesFrom: (messageId: string) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  currentContent: '',
  currentSearchResults: undefined,
  currentSearchQuery: undefined,
  error: null,
  editingMessageId: null,

  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setMessages: (messages) => set({ messages }),
  setStreaming: (isStreaming) => set({ isStreaming }),
  appendContent: (delta) => set((state) => ({ currentContent: state.currentContent + delta })),
  setSearchResults: (results, query) => set({ currentSearchResults: results, currentSearchQuery: query }),
  resetCurrentStream: () => set({ currentContent: '', currentSearchResults: undefined, currentSearchQuery: undefined }),
  setError: (error) => set({ error }),
  setEditingMessageId: (id) => set({ editingMessageId: id }),
  removeMessagesFrom: (messageId) =>
    set((state) => {
      const index = state.messages.findIndex((m) => m.id === messageId);
      if (index === -1) return state;
      return { messages: state.messages.slice(0, index) };
    }),
}));
