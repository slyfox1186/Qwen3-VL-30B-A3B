/**
 * WebSocket-based chat hook with bidirectional streaming.
 *
 * Features:
 * - Real-time bidirectional communication
 * - Cancellation support
 * - Progress tracking with token counts and ETA
 * - Automatic reconnection
 * - Fallback to SSE if WebSocket fails
 */

import { useCallback, useRef, useEffect } from 'react';
import { useChatStore } from '@/stores/chat-store';
import { useSessionStore } from '@/stores/session-store';
import { Message, SearchResult } from '@/types/api';
import { v4 as uuidv4 } from 'uuid';
import { generateTitleFromMessage } from '@/lib/title-utils';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1';
const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');

interface WebSocketMessage {
  type: string;
  [key: string]: unknown;
}

export function useWebSocketChat() {
  const {
    messages,
    addMessage,
    setMessages,
    isStreaming,
    setStreaming,
    appendContent,
    appendThought,
    setSearchResults,
    resetCurrentStream,
    currentContent,
    currentThought,
    currentSearchResults,
    currentSearchQuery,
    setError: setChatError,
    editingMessageId,
    setEditingMessageId,
    removeMessagesFrom,
    setStreamProgress,
    setCancelling,
    streamProgress,
    isCancelling,
  } = useChatStore();

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, [setMessages]);

  const { session, createSession, updateSessionTitle, generateLLMTitle } = useSessionStore();

  // WebSocket reference
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const requestInProgressRef = useRef(false);

  // Cleanup on unmount
  useEffect(() => {
    const ws = wsRef.current;
    const timeout = reconnectTimeoutRef.current;
    return () => {
      if (ws) {
        ws.close();
      }
      if (timeout) {
        clearTimeout(timeout);
      }
    };
  }, []);

  const connectWebSocket = useCallback((): Promise<WebSocket> => {
    return new Promise((resolve, reject) => {
      // Close existing connection
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        resolve(wsRef.current);
        return;
      }

      const ws = new WebSocket(`${WS_BASE_URL}/ws/chat`);

      ws.onopen = () => {
        console.log('[WebSocket] Connected');
        wsRef.current = ws;
        resolve(ws);
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        reject(error);
      };

      ws.onclose = (event) => {
        console.log('[WebSocket] Closed:', event.code, event.reason);
        wsRef.current = null;
      };
    });
  }, []);

  const loadHistory = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/history`);
      if (!res.ok) {
        if (res.status === 404) {
          setMessages([]);
          return false;
        }
        throw new Error('Failed to load history');
      }
      const data = await res.json();
      const historyMessages: Message[] = data.messages.map((msg: {
        id: string;
        role: string;
        content: string;
        thought?: string;
        created_at: string;
        search_results?: SearchResult[];
        search_query?: string;
      }) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        thought: msg.thought,
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

  // SSE fallback for when WebSocket is unavailable (defined before sendMessage)
  const sendMessageSSE = useCallback(async (
    content: string,
    images: string[],
    currentSession: { id: string; message_count: number },
    isFirstMessage: boolean
  ) => {
    try {
      const processedImages = images.map((img) => {
        const data = img.split(',')[1] || img;
        return { data };
      });

      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': currentSession.id,
        },
        body: JSON.stringify({
          message: content,
          images: processedImages,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error?.message || `Error ${response.status}`);
      }

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let capturedSearchResults: SearchResult[] | undefined;
      let capturedSearchQuery: string | undefined;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6);
            if (jsonStr.trim() === '[DONE]') continue;

            try {
              const event = JSON.parse(jsonStr);

              switch (event.type) {
                case 'content_delta':
                  if (event.content) appendContent(event.content);
                  break;
                case 'thought_delta':
                  if (event.content) appendThought(event.content);
                  break;
                case 'images':
                  if (event.images) {
                    capturedSearchResults = event.images;
                    capturedSearchQuery = event.query;
                    setSearchResults(event.images, event.query);
                  }
                  break;
                case 'error':
                  setChatError(event.error || 'Unknown stream error');
                  break;
              }
            } catch (e) {
              console.warn('Failed to parse SSE event:', e);
            }
          }
        }
      }

      // Finalize message
      const state = useChatStore.getState();
      const assistantMessage: Message = {
        id: uuidv4(),
        role: 'assistant',
        content: state.currentContent,
        thought: state.currentThought,
        search_results: capturedSearchResults || state.currentSearchResults,
        search_query: capturedSearchQuery || state.currentSearchQuery,
        created_at: new Date().toISOString(),
      };
      addMessage(assistantMessage);

      if (isFirstMessage && content) {
        const fallbackTitle = generateTitleFromMessage(content);
        updateSessionTitle(currentSession.id, fallbackTitle);
        generateLLMTitle(currentSession.id).catch(() => {});
      }

    } catch (err) {
      if (err instanceof Error) {
        setChatError(err.message);
      } else {
        setChatError('An unknown error occurred');
      }
    } finally {
      requestInProgressRef.current = false;
      setStreaming(false);
      resetCurrentStream();
    }
  }, [addMessage, appendContent, appendThought, setSearchResults, setChatError,
      setStreaming, resetCurrentStream, updateSessionTitle, generateLLMTitle]);

  const sendMessage = useCallback(async (content: string, images: string[] = []) => {
    console.log('[sendMessage] Called with:', { content: content.slice(0, 30), imagesCount: images.length });

    if (requestInProgressRef.current) {
      console.warn('[sendMessage] BLOCKED: request already in progress');
      return;
    }
    requestInProgressRef.current = true;

    setStreaming(true);
    setChatError(null);

    // Ensure session exists
    let currentSession = session;
    if (!currentSession) {
      currentSession = await createSession();
      if (!currentSession) {
        setChatError('Could not initialize session');
        setStreaming(false);
        requestInProgressRef.current = false;
        return;
      }
    }

    const isFirstMessage = currentSession.message_count === 0 && messages.length === 0;

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
    resetCurrentStream();

    try {
      // Try WebSocket first
      const ws = await connectWebSocket();

      // Process images
      const processedImages = images.map((img) => {
        const data = img.split(',')[1] || img;
        return { data };
      });

      // Set up message handler
      let capturedSearchResults: SearchResult[] | undefined;
      let capturedSearchQuery: string | undefined;

      const handleMessage = (event: MessageEvent) => {
        const data: WebSocketMessage = JSON.parse(event.data);

        switch (data.type) {
          case 'start':
            console.log('[WebSocket] Stream started:', data.request_id);
            break;

          case 'progress':
            setStreamProgress({
              tokensGenerated: data.tokens_generated as number,
              maxTokens: data.max_tokens as number,
              tokensPerSecond: data.tokens_per_second as number,
              etaSeconds: data.eta_seconds as number,
              percentage: data.percentage as number,
            });
            break;

          case 'content_delta':
            if (data.content) appendContent(data.content as string);
            break;

          case 'thought_delta':
            if (data.content) appendThought(data.content as string);
            break;

          case 'images':
            if (data.images) {
              capturedSearchResults = data.images as SearchResult[];
              capturedSearchQuery = data.query as string;
              setSearchResults(capturedSearchResults, capturedSearchQuery);
            }
            break;

          case 'done':
            console.log('[WebSocket] Stream complete:', data);
            finalizeMessage(capturedSearchResults, capturedSearchQuery);
            cleanup();
            break;

          case 'cancelled':
            console.log('[WebSocket] Stream cancelled:', data);
            finalizeMessage(capturedSearchResults, capturedSearchQuery, true);
            cleanup();
            break;

          case 'error':
            setChatError((data.message as string) || 'Unknown error');
            cleanup();
            break;
        }
      };

      const finalizeMessage = (
        searchResults?: SearchResult[],
        searchQuery?: string,
        wasCancelled = false
      ) => {
        const state = useChatStore.getState();
        if (state.currentContent || wasCancelled) {
          const assistantMessage: Message = {
            id: uuidv4(),
            role: 'assistant',
            content: state.currentContent,
            thought: state.currentThought || undefined,
            search_results: searchResults || state.currentSearchResults,
            search_query: searchQuery || state.currentSearchQuery,
            created_at: new Date().toISOString(),
          };
          addMessage(assistantMessage);
        }
      };

      const cleanup = () => {
        ws.removeEventListener('message', handleMessage);
        requestInProgressRef.current = false;
        setStreaming(false);
        setCancelling(false);
        resetCurrentStream();
      };

      ws.addEventListener('message', handleMessage);

      // Send chat message
      ws.send(JSON.stringify({
        type: 'chat',
        session_id: currentSession.id,
        message: content,
        images: processedImages,
      }));

      // Auto-generate title for first message
      if (isFirstMessage && content) {
        const fallbackTitle = generateTitleFromMessage(content);
        updateSessionTitle(currentSession.id, fallbackTitle);
        generateLLMTitle(currentSession.id).catch(() => {});
      }

    } catch (error) {
      console.error('[sendMessage] WebSocket failed, falling back to SSE:', error);
      // Fall back to SSE if WebSocket fails
      await sendMessageSSE(content, images, currentSession, isFirstMessage);
    }
  }, [
    session, createSession, addMessage, setStreaming, resetCurrentStream,
    appendContent, appendThought, setSearchResults, setChatError, messages,
    updateSessionTitle, generateLLMTitle, connectWebSocket, setStreamProgress, setCancelling,
    sendMessageSSE
  ]);

  const stopGeneration = useCallback(() => {
    setCancelling(true);

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'cancel' }));
    }
  }, [setCancelling]);

  const editMessage = useCallback(
    async (messageId: string, newContent: string, images: string[] = []) => {
      if (!session || isStreaming) return;

      try {
        const res = await fetch(`${API_BASE_URL}/sessions/${session.id}/history/truncate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message_id: messageId }),
        });

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(errorData.error?.message || 'Failed to edit message');
        }

        removeMessagesFrom(messageId);
        setEditingMessageId(null);
        await sendMessage(newContent, images);
      } catch (err) {
        console.error('Edit message error:', err);
        setChatError(err instanceof Error ? err.message : 'Failed to edit message');
      }
    },
    [session, isStreaming, removeMessagesFrom, setEditingMessageId, sendMessage, setChatError]
  );

  const regenerateResponse = useCallback(
    async (messageId: string) => {
      if (!session || isStreaming) return;

      removeMessagesFrom(messageId);
      setStreaming(true);
      resetCurrentStream();

      try {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          // Use WebSocket for regeneration
          wsRef.current.send(JSON.stringify({
            type: 'regenerate',
            session_id: session.id,
            message_id: messageId,
          }));
        } else {
          // Fall back to SSE
          const response = await fetch(`${API_BASE_URL}/chat/regenerate`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Session-ID': session.id,
            },
            body: JSON.stringify({ message_id: messageId }),
          });

          if (!response.ok) {
            throw new Error('Failed to regenerate');
          }

          // Process SSE stream (similar to sendMessageSSE)
          if (response.body) {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split('\n');
              buffer = lines.pop() || '';

              for (const line of lines) {
                if (line.startsWith('data: ')) {
                  const jsonStr = line.slice(6);
                  try {
                    const event = JSON.parse(jsonStr);
                    if (event.type === 'content_delta') appendContent(event.content);
                    if (event.type === 'thought_delta') appendThought(event.content);
                  } catch (e) {
                    console.warn('Parse error:', e);
                  }
                }
              }
            }
          }

          const state = useChatStore.getState();
          const assistantMessage: Message = {
            id: uuidv4(),
            role: 'assistant',
            content: state.currentContent,
            thought: state.currentThought,
            created_at: new Date().toISOString(),
          };
          addMessage(assistantMessage);
        }
      } catch (err) {
        setChatError(err instanceof Error ? err.message : 'Failed to regenerate');
      } finally {
        setStreaming(false);
        resetCurrentStream();
      }
    },
    [session, isStreaming, removeMessagesFrom, setStreaming, resetCurrentStream,
     appendContent, appendThought, addMessage, setChatError]
  );

  return {
    sendMessage,
    stopGeneration,
    loadHistory,
    clearMessages,
    editMessage,
    regenerateResponse,
    messages,
    isStreaming,
    currentContent,
    currentThought,
    currentSearchResults,
    currentSearchQuery,
    editingMessageId,
    setEditingMessageId,
    error: useChatStore((state) => state.error),
    streamProgress,
    isCancelling,
  };
}
