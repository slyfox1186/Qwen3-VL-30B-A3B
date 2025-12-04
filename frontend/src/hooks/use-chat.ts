import { useCallback, useRef } from 'react';
import { useChatStore } from '@/stores/chat-store';
import { useSessionStore } from '@/stores/session-store';
import { Message, SSEEvent, SearchResult } from '@/types/api';
import { v4 as uuidv4 } from 'uuid';
import { generateTitleFromMessage } from '@/lib/title-utils';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1';

export function useChat() {
  const {
    messages,
    addMessage,
    setMessages,
    isStreaming,
    setStreaming,
    appendContent,
    setSearchResults,
    resetCurrentStream,
    currentContent,
    currentSearchResults,
    currentSearchQuery,
    setError: setChatError,
    editingMessageId,
    setEditingMessageId,
    removeMessagesFrom,
  } = useChatStore();

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, [setMessages]);

  const { session, createSession, updateSessionTitle, generateLLMTitle } = useSessionStore();
  const abortControllerRef = useRef<AbortController | null>(null);
  // Atomic lock to prevent concurrent sendMessage calls (ref survives re-renders)
  const requestInProgressRef = useRef(false);

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
      const historyMessages: Message[] = data.messages.map((msg: { id: string; role: string; content: string; created_at: string; search_results?: SearchResult[]; search_query?: string }) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
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

    // Atomic lock using ref - prevents TOCTOU race condition
    // Refs are synchronous and don't cause re-renders, making this truly atomic
    if (requestInProgressRef.current) {
      console.warn('[sendMessage] BLOCKED: request already in progress');
      return;
    }
    requestInProgressRef.current = true;
    console.log('[sendMessage] Lock acquired');

    // Also set streaming for UI state
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

    // Check if this is the first message (for auto-titling)
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
    abortControllerRef.current = new AbortController();

    try {
      // Process images and log for debugging
      const processedImages = images.map((img, idx) => {
        const data = img.split(',')[1] || img;
        console.log(`[sendMessage] Image ${idx + 1}/${images.length}: ${data.length} chars, prefix: ${data.slice(0, 20)}...`);
        return { data };
      });
      console.log(`[sendMessage] Sending ${processedImages.length} images to backend`);

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

      // Capture results locally to ensure they are preserved for the final message
      let capturedSearchResults: SearchResult[] | undefined;
      let capturedSearchQuery: string | undefined;

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
                case 'content_delta':
                  if (event.content) appendContent(event.content);
                  break;
                case 'images':
                  console.log('[SSE] images event received:', {
                    imagesCount: event.images?.length,
                    query: event.query,
                    requestInProgress: requestInProgressRef.current
                  });
                  if (event.images) {
                    capturedSearchResults = event.images;
                    capturedSearchQuery = event.query;
                    setSearchResults(event.images, event.query);
                    console.log('[SSE] capturedSearchResults set:', capturedSearchResults.length);
                  }
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
      console.log('[sendMessage] Creating assistant message:', {
        capturedSearchResults: capturedSearchResults?.length,
        capturedSearchQuery,
        stateSearchResults: state.currentSearchResults?.length,
        stateSearchQuery: state.currentSearchQuery,
        contentLength: state.currentContent.length,
      });
      const assistantMessage: Message = {
        id: uuidv4(),
        role: 'assistant',
        content: state.currentContent,
        search_results: capturedSearchResults || state.currentSearchResults,
        search_query: capturedSearchQuery || state.currentSearchQuery,
        created_at: new Date().toISOString(),
      };
      console.log('[sendMessage] Final message search_results:', assistantMessage.search_results?.length);
      addMessage(assistantMessage);

      // Auto-generate title for first message
      if (isFirstMessage && content) {
        // Immediately set truncation-based title as placeholder
        const fallbackTitle = generateTitleFromMessage(content);
        updateSessionTitle(currentSession.id, fallbackTitle);

        // Fire and forget: async call to generate LLM title in background
        generateLLMTitle(currentSession.id).catch(() => {
          // Already have fallback title, silently ignore errors
        });
      }

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
      console.log('[sendMessage] Finally block - releasing lock');
      requestInProgressRef.current = false;
      setStreaming(false);
      resetCurrentStream();
      abortControllerRef.current = null;
    }
  }, [session, createSession, addMessage, setStreaming, resetCurrentStream, appendContent, setSearchResults, setChatError, messages, updateSessionTitle, generateLLMTitle]);

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  const editMessage = useCallback(
    async (messageId: string, newContent: string, images: string[] = []) => {
      if (!session || isStreaming) return;

      try {
        // Truncate history at this message on backend
        const res = await fetch(`${API_BASE_URL}/sessions/${session.id}/history/truncate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message_id: messageId }),
        });

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(errorData.error?.message || 'Failed to edit message');
        }

        // Remove messages from local state
        removeMessagesFrom(messageId);
        setEditingMessageId(null);

        // Send the edited message
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

      // Remove the AI message from local state immediately
      removeMessagesFrom(messageId);

      setStreaming(true);
      resetCurrentStream();
      abortControllerRef.current = new AbortController();

      try {
        const response = await fetch(`${API_BASE_URL}/chat/regenerate`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': session.id,
          },
          body: JSON.stringify({ message_id: messageId }),
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
                const event: SSEEvent = JSON.parse(jsonStr);

                switch (event.type) {
                  case 'content_delta':
                    if (event.content) appendContent(event.content);
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

        // Add the regenerated assistant message
        const state = useChatStore.getState();
        const assistantMessage: Message = {
          id: uuidv4(),
          role: 'assistant',
          content: state.currentContent,
          search_results: capturedSearchResults || state.currentSearchResults,
          search_query: capturedSearchQuery || state.currentSearchQuery,
          created_at: new Date().toISOString(),
        };
        addMessage(assistantMessage);
      } catch (err: unknown) {
        if (err instanceof Error) {
          if (err.name !== 'AbortError') {
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
    },
    [session, isStreaming, removeMessagesFrom, setStreaming, resetCurrentStream, appendContent, setSearchResults, addMessage, setChatError]
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
    currentSearchResults,
    currentSearchQuery,
    editingMessageId,
    setEditingMessageId,
    error: useChatStore((state) => state.error),
  };
}
