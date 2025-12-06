/**
 * Chat hook with WebSocket bidirectional streaming.
 *
 * Features:
 * - Real-time bidirectional communication
 * - Cancellation support
 * - Progress tracking with token counts and ETA
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

export function useChat() {
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
        // Save message if there's content, thought, or was cancelled
        if (state.currentContent || state.currentThought || wasCancelled) {
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
          console.log('[finalizeMessage] Added message:', {
            contentLen: state.currentContent.length,
            thoughtLen: state.currentThought.length,
          });
        } else {
          console.warn('[finalizeMessage] No content or thought to save');
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
      console.error('[sendMessage] WebSocket error:', error);
      setChatError(error instanceof Error ? error.message : 'WebSocket connection failed');
      requestInProgressRef.current = false;
      setStreaming(false);
    }
  }, [
    session, createSession, addMessage, setStreaming, resetCurrentStream,
    appendContent, appendThought, setSearchResults, setChatError, messages,
    updateSessionTitle, generateLLMTitle, connectWebSocket, setStreamProgress, setCancelling
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
        // Connect WebSocket if not already connected
        const ws = await connectWebSocket();

        // Set up message handler for regeneration response
        const handleMessage = (event: MessageEvent) => {
          const data: WebSocketMessage = JSON.parse(event.data);

          switch (data.type) {
            case 'start':
              console.log('[WebSocket] Regenerate started:', data.request_id);
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

            case 'done':
              console.log('[WebSocket] Regenerate complete:', data);
              finalizeRegenerate();
              cleanup();
              break;

            case 'cancelled':
              console.log('[WebSocket] Regenerate cancelled:', data);
              finalizeRegenerate();
              cleanup();
              break;

            case 'error':
              setChatError((data.message as string) || 'Unknown error');
              cleanup();
              break;
          }
        };

        const finalizeRegenerate = () => {
          const state = useChatStore.getState();
          if (state.currentContent) {
            const assistantMessage: Message = {
              id: uuidv4(),
              role: 'assistant',
              content: state.currentContent,
              thought: state.currentThought || undefined,
              created_at: new Date().toISOString(),
            };
            addMessage(assistantMessage);
          }
        };

        const cleanup = () => {
          ws.removeEventListener('message', handleMessage);
          setStreaming(false);
          setCancelling(false);
          resetCurrentStream();
        };

        ws.addEventListener('message', handleMessage);

        // Send regenerate request via WebSocket
        ws.send(JSON.stringify({
          type: 'regenerate',
          session_id: session.id,
          message_id: messageId,
        }));

      } catch (err) {
        setChatError(err instanceof Error ? err.message : 'Failed to regenerate');
        setStreaming(false);
        resetCurrentStream();
      }
    },
    [session, isStreaming, removeMessagesFrom, setStreaming, resetCurrentStream,
     appendContent, appendThought, addMessage, setChatError, connectWebSocket, setStreamProgress, setCancelling]
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
