'use client';

import React, { useEffect, useCallback, useState, useRef } from 'react';
import { useChat } from '@/hooks/use-chat';
import MessageList from './MessageList';
import ChatInput, { ChatInputHandle } from './ChatInput';
import Sidebar from './Sidebar';
import StreamProgressBar from './StreamProgressBar';
import SearchPanel from '@/components/search/SearchPanel';
import { useSearch, SearchMatch } from '@/hooks/use-search';
import { useSessionStore } from '@/stores/session-store';
import { useUIStore } from '@/stores/ui-store';
import { useChatStore } from '@/stores/chat-store';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { PanelLeftOpen, PanelLeftClose, Keyboard, X, Search, Download } from 'lucide-react';
import { toast } from 'sonner';
import { ThemeToggle } from '@/components/theme';
import ExportDialog from './ExportDialog';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1';

export default function ChatContainer() {
  const chatInputRef = useRef<ChatInputHandle>(null);
  const {
    messages,
    isStreaming,
    currentContent,
    currentThought,
    currentSearchResults,
    currentSearchQuery,
    sendMessage,
    stopGeneration,
    loadHistory,
    clearMessages,
    editMessage,
    regenerateResponse,
    editingMessageId,
    setEditingMessageId,
    error: chatError,
    streamProgress,
    isCancelling,
  } = useChat();
  const { session, setSession, createSession, clearSession, hasHydrated, error: sessionError } = useSessionStore();
  const { isSidebarOpen, toggleSidebar, setSidebarOpen } = useUIStore();
  const { open: openSearch } = useSearch();
  const [showShortcuts, setShowShortcuts] = React.useState(false);
  const [showExport, setShowExport] = React.useState(false);
  const [isBackendReady, setIsBackendReady] = useState(false);

  // Health check for backend connectivity (checks Redis + vLLM readiness)
  useEffect(() => {
    let isMounted = true;
    let retryTimeout: NodeJS.Timeout;

    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/health/ready`, {
          method: 'GET',
          signal: AbortSignal.timeout(5000),
        });
        if (isMounted) {
          if (res.ok) {
            const data = await res.json();
            // Only mark as ready if overall status is "ok" (all services healthy)
            setIsBackendReady(data.status === 'ok');
            if (data.status !== 'ok') {
              // Retry if degraded (some services not ready)
              retryTimeout = setTimeout(checkHealth, 2000);
            }
          } else {
            setIsBackendReady(false);
            retryTimeout = setTimeout(checkHealth, 2000);
          }
        }
      } catch {
        if (isMounted) {
          setIsBackendReady(false);
          // Retry after 2 seconds if not ready
          retryTimeout = setTimeout(checkHealth, 2000);
        }
      }
    };

    checkHealth();

    return () => {
      isMounted = false;
      if (retryTimeout) clearTimeout(retryTimeout);
    };
  }, []);

  // Handle search result click - navigate to session and highlight message
  const handleSearchResultClick = useCallback(async (match: SearchMatch) => {
    if (match.session_id === session?.id) {
      // Already in this session, just scroll to message
      const element = document.getElementById(`message-${match.message_id}`);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        element.classList.add('highlight-flash');
        setTimeout(() => element.classList.remove('highlight-flash'), 2000);
      }
    } else {
      // Switch to the session
      const newSession = await useSessionStore.getState().sessions.find(s => s.id === match.session_id);
      if (newSession) {
        setSession(newSession);
        loadedSessionRef.current = newSession.id;
        await loadHistory(newSession.id);
        // After loading, scroll to the message
        setTimeout(() => {
          const element = document.getElementById(`message-${match.message_id}`);
          if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            element.classList.add('highlight-flash');
            setTimeout(() => element.classList.remove('highlight-flash'), 2000);
          }
        }, 500);
      } else {
        toast.info('Session not found locally. Try refreshing.');
      }
    }
  }, [session, setSession, loadHistory]);

  // Status logic
  const isError = !!chatError || !!sessionError;
  const getStatusText = () => {
    if (isError) return 'Error';
    if (!isBackendReady) return 'Connecting...';
    if (!session) return 'Initializing...';
    if (isCancelling) return 'Cancelling...';
    if (isStreaming && streamProgress) {
      return `${streamProgress.tokensPerSecond.toFixed(1)} tok/s`;
    }
    if (isStreaming) return 'Generating...';
    return 'Online';
  };
  const statusText = getStatusText();

  const statusColorClass = isError
    ? 'error'
    : !isBackendReady
      ? 'offline'
      : !session
        ? 'offline'
        : isCancelling
          ? 'cancelling'
          : isStreaming
            ? 'streaming'
            : 'online';

  // Track which session ID we've loaded history for to avoid re-loading
  // when session metadata changes (like title updates)
  const loadedSessionRef = React.useRef<string | null>(null);

  // Initialize session on mount if none exists (after hydration)
  // If session exists, load its history (only once per session ID)
  useEffect(() => {
    if (!hasHydrated) return;

    const initSession = async () => {
      if (session) {
        // Only load history if we haven't already loaded for this session ID
        if (loadedSessionRef.current === session.id) {
          return;
        }

        // Session exists, load its history
        const loaded = await loadHistory(session.id);
        if (loaded) {
          loadedSessionRef.current = session.id;
        } else {
          // Session expired on backend (404) - remove it from local list and switch to another
          const { sessions, removeSession } = useSessionStore.getState();
          const expiredSessionId = session.id;

          // Find remaining sessions after removing the expired one
          const remainingSessions = sessions.filter(s => s.id !== expiredSessionId);

          // Remove the expired session from local storage
          removeSession(expiredSessionId);

          if (remainingSessions.length > 0) {
            // Switch to the most recent session
            const nextSession = remainingSessions[0];
            loadedSessionRef.current = nextSession.id;
            setSession(nextSession);
            await loadHistory(nextSession.id);
          } else {
            // No other sessions exist, create a new one
            loadedSessionRef.current = null;
            clearSession();
          }
        }
        return;
      }

      // No session, create one
      loadedSessionRef.current = null;
      await createSession();
    };

    initSession();
  }, [hasHydrated, session, createSession, loadHistory, clearSession, setSession]);

  const handleDeleteConversation = useCallback(async () => {
    if (!session) return;

    const sessionIdToDelete = session.id;
    const { sessions, removeSession } = useSessionStore.getState();

    // Find remaining sessions after deletion (excluding current)
    const remainingSessions = sessions.filter(s => s.id !== sessionIdToDelete);

    try {
      // Delete from backend
      const res = await fetch(`${API_BASE_URL}/sessions/${sessionIdToDelete}`, {
        method: 'DELETE',
      });

      if (!res.ok && res.status !== 404) {
        toast.error('Failed to delete conversation');
        return;
      }

      // Remove from local store
      removeSession(sessionIdToDelete);
      clearMessages();

      if (remainingSessions.length === 0) {
        // No other conversations - create a new one
        loadedSessionRef.current = null;
        clearSession();
        toast.success('Conversation deleted. Creating new chat...');
      } else {
        // Switch to the most recently used session (first in list)
        const nextSession = remainingSessions[0];
        loadedSessionRef.current = nextSession.id;
        setSession(nextSession);
        await loadHistory(nextSession.id);
        toast.success('Conversation deleted. Switched to previous chat.');
      }

      // Focus the input box after delete
      setTimeout(() => chatInputRef.current?.focus(), 100);
    } catch (error) {
      console.error('Error deleting conversation:', error);
      toast.error('Failed to delete conversation');
    }
  }, [session, clearMessages, clearSession, setSession, loadHistory]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Alt+X: Toggle Sidebar
      if (e.altKey && (e.code === 'KeyX' || e.key.toLowerCase() === 'x')) {
        e.preventDefault();
        toggleSidebar();
      }

      // Ctrl+Alt+Shift+D: Delete current conversation
      if (e.ctrlKey && e.altKey && e.shiftKey && (e.code === 'KeyD' || e.key.toLowerCase() === 'd')) {
        e.preventDefault();
        handleDeleteConversation();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleDeleteConversation, toggleSidebar]);

  const handleNewChat = () => {
    loadedSessionRef.current = null;
    clearMessages();
    clearSession();
  };

  const handleImageReview = useCallback(async (imageUrl: string) => {
    // Check streaming state from store (not closure) to avoid stale value
    if (useChatStore.getState().isStreaming) {
      toast.error('Please wait for the current response to complete');
      return;
    }

    try {
      toast.info('Fetching image for review...');

      // Use backend proxy to bypass CORS restrictions
      const proxyUrl = `${API_BASE_URL}/images/proxy`;
      console.log(`Fetching image from proxy: ${proxyUrl} for url: ${imageUrl}`);

      const response = await fetch(proxyUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: imageUrl }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const message = errorData.detail?.error?.message
          || errorData.error?.message
          || `Failed to fetch image: ${response.status} ${response.statusText}`;
        toast.error(message);
        return;
      }

      const data = await response.json();

      // sendMessage has its own atomic ref-based guard against concurrent calls
      // If a request is already in progress, sendMessage will safely reject
      sendMessage('Describe this image in GREAT DETAIL.', [data.data_url]);
    } catch (error) {
      console.error('Error fetching image for review:', error);
      const message = error instanceof Error ? error.message : 'Failed to fetch image';
      toast.error(message);
    }
  }, [sendMessage]);

  return (
    <div className="app-layout">
      <Sidebar 
        isOpen={isSidebarOpen} 
        onClose={() => setSidebarOpen(false)} 
        onNewChat={handleNewChat}
      />

      <div className="main-wrapper">
        <header className="chat-header">
          <div className="header-left">
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={toggleSidebar}
              className="toggle-sidebar-btn"
            >
              {isSidebarOpen ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeftOpen className="w-5 h-5" />}
            </Button>
            
            <h1 className="app-title">
              Qwen3-VL Chat
            </h1>
            <div className="header-divider" />
            <div className="status-indicator">
              <div className={cn("status-dot", statusColorClass)} />
              <span className="status-text">
                {statusText}
              </span>
            </div>
            {isStreaming && streamProgress && (
              <StreamProgressBar progress={streamProgress} isCancelling={isCancelling} />
            )}
          </div>

          <div className="header-right">
            <Button
              variant="ghost"
              size="icon"
              onClick={openSearch}
              title="Search (Ctrl+K)"
            >
              <Search className="w-4 h-4 text-muted-foreground" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowExport(true)}
              disabled={messages.length === 0}
              title="Export Conversation"
            >
              <Download className="w-4 h-4 text-muted-foreground" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowShortcuts(true)}
              title="Keyboard Shortcuts"
            >
              <Keyboard className="w-4 h-4 text-muted-foreground" />
            </Button>
            <ThemeToggle />
            {session && (
              <div className="session-badge">
                <span className="session-label">Session</span>
                <code className="session-id">{session.id.slice(0, 8)}</code>
              </div>
            )}
          </div>
        </header>
        
        <main className="chat-content-area">
          <MessageList
            messages={messages}
            isStreaming={isStreaming}
            currentContent={currentContent}
            currentThought={currentThought}
            currentSearchResults={currentSearchResults}
            currentSearchQuery={currentSearchQuery}
            onImageReview={handleImageReview}
            editingMessageId={editingMessageId}
            onEditMessage={setEditingMessageId}
            onSaveEdit={editMessage}
            onCancelEdit={() => setEditingMessageId(null)}
            onRegenerate={regenerateResponse}
          />
          
        </main>

        <div className="input-area-wrapper">
          <ChatInput
            ref={chatInputRef}
            onSend={sendMessage}
            isStreaming={isStreaming}
            onStop={stopGeneration}
            hasMessages={messages.length > 0}
          />
        </div>
      </div>

      {showShortcuts && (
        <div className="shortcuts-backdrop" onClick={() => setShowShortcuts(false)}>
          <div className="shortcuts-modal" onClick={e => e.stopPropagation()}>
            <div className="shortcuts-header">
              <h2 className="shortcuts-title">Keyboard Shortcuts</h2>
              <button onClick={() => setShowShortcuts(false)} className="shortcuts-close-btn">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="shortcuts-grid">
              <div className="shortcut-item">
                <span className="shortcut-desc">Send Message</span>
                <div className="shortcut-keys">
                  <kbd className="kbd">Enter</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">New Line</span>
                <div className="shortcut-keys">
                  <kbd className="kbd">Shift</kbd> + <kbd className="kbd">Enter</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Toggle Sidebar</span>
                <div className="shortcut-keys">
                  <kbd className="kbd">Alt</kbd> + <kbd className="kbd">X</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Save Edit</span>
                <div className="shortcut-keys">
                  <kbd className="kbd">Ctrl</kbd> + <kbd className="kbd">Enter</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Cancel Edit</span>
                <div className="shortcut-keys">
                  <kbd className="kbd">Esc</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Delete Chat</span>
                <div className="shortcut-keys">
                  <kbd className="kbd">Ctrl</kbd> + <kbd className="kbd">Alt</kbd> + <kbd className="kbd">Shift</kbd> + <kbd className="kbd">D</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Search</span>
                <div className="shortcut-keys">
                  <kbd className="kbd">Ctrl</kbd> + <kbd className="kbd">K</kbd>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <SearchPanel onResultClick={handleSearchResultClick} />

      <ExportDialog
        isOpen={showExport}
        onClose={() => setShowExport(false)}
        messages={messages}
        sessionTitle={session?.metadata?.title as string | undefined}
      />
    </div>
  );
}