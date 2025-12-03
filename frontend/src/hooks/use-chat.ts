import { useCallback, useRef } from 'react';
import { useChatStore } from '@/stores/chat-store';
import { useSessionStore } from '@/stores/session-store';
import { Message, SSEEvent, SearchResult } from '@/types/api';
import { v4 as uuidv4 } from 'uuid';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1';

export function useChat() {
  const {
    messages,
    addMessage,
    setMessages,
    isStreaming,
    setStreaming,
    appendThinking,
    appendContent,
    setSearchResults,
    resetCurrentStream,
    currentThinking,
    currentContent,
    currentSearchResults,
    currentSearchQuery,
    setError: setChatError
  } = useChatStore();

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, [setMessages]);

  const { session, setSession } = useSessionStore();
  const abortControllerRef = useRef<AbortController | null>(null);

  const loadHistory = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/history`);
      if (!res.ok) {
        if (res.status === 404) {
          // Session expired, clear it
          setMessages([]);
          return false;
        }
        throw new Error('Failed to load history');
      }
      const data = await res.json();
      const historyMessages: Message[] = data.messages.map((msg: { id: string; role: string; content: string; thinking?: string; created_at: string; search_results?: SearchResult[]; search_query?: string }) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        thinking: msg.thinking,
        search_results: msg.search_results,
        search_query: msg.search_query,
        created_at: msg.created_at,
      }));
      setMessages(historyMessages);
      return true;
    } catch (err) {
      console.error('Failed to load history:', err);
      return false;
    }
  }, [setMessages]);

  const createSession = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ metadata: { client: 'web' } }),
      });
      if (!res.ok) throw new Error('Failed to create session');
      const data = await res.json();
      setSession(data);
      return data;
    } catch (err) {
      console.error('Session creation failed:', err);
      return null;
    }
  }, [setSession]);

  const sendMessage = useCallback(async (content: string, images: string[] = []) => {
    setChatError(null);
    
    // Ensure session exists
    let currentSession = session;
    if (!currentSession) {
      currentSession = await createSession();
      if (!currentSession) {
        setChatError('Could not initialize session');
        return;
      }
    }

    // Add user message immediately
    const userMsgId = uuidv4();
    const userMessage: Message = {
      id: userMsgId,
      role: 'user',
      content,
      images,
      created_at: new Date().toISOString(),
    };
    addMessage(userMessage);

    setStreaming(true);
    resetCurrentStream();
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': currentSession.id,
        },
        body: JSON.stringify({
          message: content,
          images: images.map(img => ({ data: img.split(',')[1] || img })), // Strip prefix if present, backend might handle it but being safe
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
         const errorData = await response.json().catch(() => ({}));
         throw new Error(errorData.error?.message || `Error ${response.status}`);
      }

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep the last incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6);
            if (jsonStr.trim() === '[DONE]') continue; // OpenAI style, just in case
            
            try {
              const event: SSEEvent = JSON.parse(jsonStr);
              
              switch (event.type) {
                case 'thinking_delta':
                  if (event.content) appendThinking(event.content);
                  break;
                case 'content_delta':
                  if (event.content) appendContent(event.content);
                  break;
                case 'images':
                  if (event.images) setSearchResults(event.images, event.query);
                  break;
                case 'error':
                  setChatError(event.error || 'Unknown stream error');
                  break;
                case 'done':
                  // Finalize message
                  break;
              }
            } catch (e) {
              console.warn('Failed to parse SSE event:', e);
            }
          }
        }
      }

      // After stream ends, add the assistant message to the list
      const state = useChatStore.getState();
      const assistantMessage: Message = {
        id: uuidv4(),
        role: 'assistant',
        content: state.currentContent,
        thinking: state.currentThinking,
        search_results: state.currentSearchResults,
        search_query: state.currentSearchQuery,
        created_at: new Date().toISOString(),
      };
      addMessage(assistantMessage);

    } catch (err: unknown) {
      if (err instanceof Error) {
        if (err.name === 'AbortError') {
          console.log('Request aborted');
        } else {
          setChatError(err.message);
        }
      } else {
        setChatError('An unknown error occurred');
      }
    } finally {
      setStreaming(false);
      resetCurrentStream();
      abortControllerRef.current = null;
    }
  }, [session, createSession, addMessage, setStreaming, resetCurrentStream, appendThinking, appendContent, setSearchResults, setChatError]);

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  return {
    sendMessage,
    stopGeneration,
    loadHistory,
    clearMessages,
    messages,
    isStreaming,
    currentThinking,
    currentContent,
    currentSearchResults,
    currentSearchQuery,
    error: useChatStore(state => state.error),
  };
}
