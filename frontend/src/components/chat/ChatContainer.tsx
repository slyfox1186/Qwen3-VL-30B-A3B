'use client';

import React, { useEffect, useCallback } from 'react';
import { useChat } from '@/hooks/use-chat';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import Sidebar from './Sidebar';
import { useSessionStore } from '@/stores/session-store';
import { useUIStore } from '@/stores/ui-store';
import { useChatStore } from '@/stores/chat-store';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { PanelLeftOpen, PanelLeftClose, Keyboard, X } from 'lucide-react';
import { toast } from 'sonner';
import { ThemeToggle } from '@/components/theme';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1';

export default function ChatContainer() {
  const {
    messages,
    isStreaming,
    currentContent,
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
  } = useChat();
  const { session, setSession, createSession, clearSession, hasHydrated, error: sessionError } = useSessionStore();
  const { isSidebarOpen, toggleSidebar, setSidebarOpen } = useUIStore();
  const [showShortcuts, setShowShortcuts] = React.useState(false);

  // Status logic
  const isError = !!chatError || !!sessionError;
  const statusText = isError 
    ? 'Error' 
    : !session 
      ? 'Connecting...' 
      : isStreaming 
        ? 'Generating...' 
        : 'Online';
        
  const statusColorClass = isError 
    ? 'error' 
    : !session 
      ? 'offline' 
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
          // Session expired on backend, create new one
          loadedSessionRef.current = null;
          clearSession();
        }
        return;
      }

      // No session, create one
      loadedSessionRef.current = null;
      await createSession();
    };

    initSession();
  }, [hasHydrated, session, createSession, loadHistory, clearSession]);

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
    } catch (error) {
      console.error('Error deleting conversation:', error);
      toast.error('Failed to delete conversation');
    }
  }, [session, clearMessages, clearSession, setSession, loadHistory]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && e.key === 'x') {
        e.preventDefault();
        toggleSidebar();
      }

      // Ctrl+Alt+Shift+D: Delete current conversation
      if (e.ctrlKey && e.altKey && e.shiftKey && e.key === 'D') {
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
        console.error('Proxy fetch failed:', response.status, response.statusText, errorData);
        throw new Error(errorData.error?.message || `Failed to fetch image: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();

      // sendMessage has its own atomic ref-based guard against concurrent calls
      // If a request is already in progress, sendMessage will safely reject
      sendMessage('Describe this image.', [data.data_url]);
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
          </div>
          
          <div className="header-right">
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
            currentSearchResults={currentSearchResults}
            currentSearchQuery={currentSearchQuery}
            onImageReview={handleImageReview}
            editingMessageId={editingMessageId}
            onEditMessage={setEditingMessageId}
            onSaveEdit={editMessage}
            onCancelEdit={() => setEditingMessageId(null)}
            onRegenerate={regenerateResponse}
          />
          
          {/* Gradient fade at bottom of list before input */}
          <div className="chat-fade-overlay" />
        </main>

        <div className="input-area-wrapper">
          <ChatInput 
            onSend={sendMessage} 
            isStreaming={isStreaming}
            onStop={stopGeneration}
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
            </div>
          </div>
        </div>
      )}
    </div>
  );
}