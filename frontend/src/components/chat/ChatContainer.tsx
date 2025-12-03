'use client';

import React, { useState, useEffect } from 'react';
import { useChat } from '@/hooks/use-chat';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import Sidebar from './Sidebar';
import { useSessionStore } from '@/stores/session-store';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { PanelLeftOpen, PanelLeftClose } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1';

export default function ChatContainer() {
  const { messages, isStreaming, currentThinking, currentContent, currentSearchResults, currentSearchQuery, sendMessage, stopGeneration, loadHistory, clearMessages } = useChat();
  const { session, setSession, clearSession, hasHydrated } = useSessionStore();

  // Initialize session on mount if none exists (after hydration)
  // If session exists, load its history
  useEffect(() => {
    if (!hasHydrated) return;

    const initSession = async () => {
      if (session) {
        // Session exists, load its history
        const loaded = await loadHistory(session.id);
        if (!loaded) {
          // Session expired on backend, create new one
          clearSession();
        }
        return;
      }

      // No session, create one
      try {
        const res = await fetch(`${API_BASE_URL}/sessions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ metadata: { client: 'web' } }),
        });
        if (!res.ok) throw new Error('Failed to create session');
        const data = await res.json();
        setSession(data);
      } catch (err) {
        console.error('Session initialization failed:', err);
      }
    };

    initSession();
  }, [hasHydrated, session, setSession, loadHistory, clearSession]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && e.key === 'x') {
        e.preventDefault();
        setIsSidebarOpen(prev => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleNewChat = () => {
    clearMessages();
    clearSession();
  };

  return (
    <div className="app-layout">
      <Sidebar 
        isOpen={isSidebarOpen} 
        onClose={() => setIsSidebarOpen(false)} 
        onNewChat={handleNewChat}
      />

      <div className="main-wrapper">
        <header className="chat-header">
          <div className="header-left">
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="toggle-sidebar-btn"
            >
              {isSidebarOpen ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeftOpen className="w-5 h-5" />}
            </Button>
            
            <h1 className="app-title">
              Qwen3-VL Chat
            </h1>
            <div className="header-divider" />
            <div className="status-indicator">
              <div className={cn("status-dot", session ? "online" : "offline")} />
              <span className="status-text">
                {session ? 'Online' : 'Connecting...'}
              </span>
            </div>
          </div>
          
          <div className="header-right">
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
            currentThinking={currentThinking}
            currentContent={currentContent}
            currentSearchResults={currentSearchResults}
            currentSearchQuery={currentSearchQuery}
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
    </div>
  );
}