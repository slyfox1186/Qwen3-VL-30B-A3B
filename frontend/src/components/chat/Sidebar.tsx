'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { useSessionStore } from '@/stores/session-store';
import { Plus, MessageSquare, Trash2, X } from 'lucide-react';
import { cn } from '@/lib/utils';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
}

export default function Sidebar({ isOpen, onClose, onNewChat }: SidebarProps) {
  const { sessions, session: currentSession, setSession, removeSession } = useSessionStore();

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        removeSession(sessionId);
      } else {
        console.error('Failed to delete session');
      }
    } catch (error) {
      console.error('Error deleting session:', error);
    }
  };

  return (
    <AnimatePresence mode="wait">
      {isOpen && (
        <motion.div
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 280, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.3, ease: "easeInOut" }}
          className="sidebar-container"
        >
          <div className="sidebar-header">
            <span className="sidebar-title">Conversations</span>
            <Button variant="ghost" size="icon" onClick={onClose} className="sidebar-close-mobile">
              <X className="w-4 h-4" />
            </Button>
          </div>

          <div className="sidebar-actions">
            <Button 
              onClick={onNewChat} 
              className="new-chat-button" 
              variant="outline"
            >
              <Plus className="w-4 h-4" />
              New Chat
            </Button>
          </div>

          <div className="sidebar-list">
            {sessions.length === 0 ? (
              <div className="empty-state">
                No recent conversations
              </div>
            ) : (
              sessions.map((s) => (
                <div 
                  key={s.id} 
                  className={cn(
                    "session-item group",
                    currentSession?.id === s.id 
                      ? "active" 
                      : "inactive"
                  )}
                  onClick={() => setSession(s)}
                >
                  <MessageSquare className="session-icon" />
                  <span className="session-text">
                    {new Date(s.created_at).toLocaleString(undefined, { 
                      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' 
                    })}
                  </span>
                  
                  {/* Delete Button (visible on hover) */}
                  <div className="delete-session-wrapper opacity-0 transition-opacity group-hover:opacity-100">
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="delete-session-button"
                      onClick={(e) => handleDeleteSession(e, s.id)}
                      title="Delete conversation"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
          
          <div className="sidebar-footer">
            v1.0.0 • Qwen3-VL
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}