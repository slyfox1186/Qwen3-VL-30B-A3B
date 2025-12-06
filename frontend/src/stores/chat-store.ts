import { create } from 'zustand';
import { Message } from '@/types/api';

/**
 * Streaming progress information for real-time updates.
 */
export interface StreamProgress {
  tokensGenerated: number;
  maxTokens: number;
  tokensPerSecond: number;
  etaSeconds: number;
  percentage: number;
}

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentContent: string; // Accumulates content during stream
  currentThought: string; // Accumulates thought during stream
  error: string | null;
  editingMessageId: string | null;

  // Progress tracking for bidirectional streaming
  streamProgress: StreamProgress | null;
  isCancelling: boolean;

  addMessage: (message: Message) => void;
  setMessages: (messages: Message[]) => void;
  setStreaming: (isStreaming: boolean) => void;
  appendContent: (delta: string) => void;
  appendThought: (delta: string) => void;
  resetCurrentStream: () => void;
  setError: (error: string | null) => void;
  setEditingMessageId: (id: string | null) => void;
  removeMessagesFrom: (messageId: string) => void;
  setStreamProgress: (progress: StreamProgress | null) => void;
  setCancelling: (isCancelling: boolean) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  currentContent: '',
  currentThought: '',
  error: null,
  editingMessageId: null,
  streamProgress: null,
  isCancelling: false,

  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setMessages: (messages) => set({ messages }),
  setStreaming: (isStreaming) => set({ isStreaming }),
  appendContent: (delta) => set((state) => ({ currentContent: state.currentContent + delta })),
  appendThought: (delta) => set((state) => ({ currentThought: state.currentThought + delta })),
  resetCurrentStream: () => set({
    currentContent: '',
    currentThought: '',
    streamProgress: null,
    isCancelling: false,
  }),
  setError: (error) => set({ error }),
  setEditingMessageId: (id) => set({ editingMessageId: id }),
  removeMessagesFrom: (messageId) =>
    set((state) => {
      const index = state.messages.findIndex((m) => m.id === messageId);
      if (index === -1) return state;
      return { messages: state.messages.slice(0, index) };
    }),
  setStreamProgress: (progress) => set({ streamProgress: progress }),
  setCancelling: (isCancelling) => set({ isCancelling }),
}));
