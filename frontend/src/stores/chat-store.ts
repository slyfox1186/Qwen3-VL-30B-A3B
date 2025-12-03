import { create } from 'zustand';
import { Message, SearchResult } from '@/types/api';

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentThinking: string; // Accumulates thinking during stream
  currentContent: string; // Accumulates content during stream
  currentSearchResults: SearchResult[] | undefined;
  currentSearchQuery: string | undefined;
  error: string | null;
  
  addMessage: (message: Message) => void;
  setMessages: (messages: Message[]) => void;
  setStreaming: (isStreaming: boolean) => void;
  appendThinking: (delta: string) => void;
  appendContent: (delta: string) => void;
  setSearchResults: (results: SearchResult[], query?: string) => void;
  resetCurrentStream: () => void;
  setError: (error: string | null) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  currentThinking: '',
  currentContent: '',
  currentSearchResults: undefined,
  currentSearchQuery: undefined,
  error: null,

  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setMessages: (messages) => set({ messages }),
  setStreaming: (isStreaming) => set({ isStreaming }),
  appendThinking: (delta) => set((state) => ({ currentThinking: state.currentThinking + delta })),
  appendContent: (delta) => set((state) => ({ currentContent: state.currentContent + delta })),
  setSearchResults: (results, query) => set({ currentSearchResults: results, currentSearchQuery: query }),
  resetCurrentStream: () => set({ currentThinking: '', currentContent: '', currentSearchResults: undefined, currentSearchQuery: undefined }),
  setError: (error) => set({ error }),
}));
