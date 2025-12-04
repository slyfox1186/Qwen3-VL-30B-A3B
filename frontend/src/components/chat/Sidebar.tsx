'use client';

import React, { useState, useRef, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { useSessionStore } from '@/stores/session-store';
import { Plus, MessageSquare, Trash2, X, Pencil, Search, Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Session } from '@/types/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
}

type DateGroup = 'Today' | 'Yesterday' | 'Previous 7 Days' | 'Older';

export default function Sidebar({ isOpen, onClose, onNewChat }: SidebarProps) {
  const { sessions, session: currentSession, setSession, removeSession, updateSessionTitle } = useSessionStore();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when editing starts
  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  const handleStartEdit = (e: React.MouseEvent, s: Session) => {
    e.stopPropagation();
    setEditingId(s.id);
    setEditValue((s.metadata?.title as string) || '');
  };

  const handleSaveEdit = async () => {
    if (editingId && editValue.trim()) {
      await updateSessionTitle(editingId, editValue.trim());
    }
    setEditingId(null);
    setEditValue('');
  };

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      setEditingId(null);
      setEditValue('');
    }
  };

  const getSessionTitle = (s: Session): string => {
    const title = s.metadata?.title as string | undefined;
    if (title) return title;

    return new Date(s.created_at).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        // If deleting current session, switch to another one first if available
        if (currentSession?.id === sessionId) {
          const remaining = sessions.filter(s => s.id !== sessionId);
          if (remaining.length > 0) {
            setSession(remaining[0]);
          }
        }
        removeSession(sessionId);
      } else {
        console.error('Failed to delete session');
      }
    } catch (error) {
      console.error('Error deleting session:', error);
    }
  };

  // Grouping Logic
  const groupedSessions = useMemo(() => {
    const groups: Record<DateGroup, Session[]> = {
      'Today': [],
      'Yesterday': [],
      'Previous 7 Days': [],
      'Older': []
    };

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const lastWeek = new Date(today);
    lastWeek.setDate(lastWeek.getDate() - 7);

    // Filter by search first
    const filtered = sessions.filter(s => {
      if (!searchQuery) return true;
      const title = (s.metadata?.title as string) || '';
      return title.toLowerCase().includes(searchQuery.toLowerCase());
    });

    // Sort by date desc
    const sorted = [...filtered].sort((a, b) => 
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    sorted.forEach(session => {
      const date = new Date(session.created_at);
      
      if (date >= today) {
        groups['Today'].push(session);
      } else if (date >= yesterday) {
        groups['Yesterday'].push(session);
      } else if (date >= lastWeek) {
        groups['Previous 7 Days'].push(session);
      } else {
        groups['Older'].push(session);
      }
    });

    return groups;
  }, [sessions, searchQuery]);

  const hasSessions = sessions.length > 0;

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

          <div className="sidebar-actions space-y-3">
            <Button 
              onClick={onNewChat} 
              className="new-chat-button" 
              variant="outline"
            >
              <Plus className="w-4 h-4" />
              New Chat
            </Button>
            
            <div className="sidebar-search-wrapper">
              <Search className="search-icon" />
              <input 
                type="text" 
                placeholder="Search chats..." 
                className="sidebar-search-input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>

          <div className="sidebar-list">
            {!hasSessions ? (
              <div className="empty-state">
                No conversations yet
              </div>
            ) : (
              Object.entries(groupedSessions).map(([group, groupSessions]) => {
                if (groupSessions.length === 0) return null;

                return (
                  <div key={group} className="session-group">
                    <div className="group-header">
                      <Calendar className="w-3 h-3 mr-1.5 opacity-50" />
                      {group}
                    </div>
                    <div className="group-items">
                      {groupSessions.map((s) => (
                        <div
                          key={s.id}
                          className={cn(
                            "session-item group",
                            currentSession?.id === s.id ? "active" : "inactive"
                          )}
                          onClick={() => !editingId && setSession(s)}
                        >
                          <MessageSquare className="session-icon" />

                          {editingId === s.id ? (
                            <input
                              ref={inputRef}
                              type="text"
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              onBlur={handleSaveEdit}
                              onKeyDown={handleEditKeyDown}
                              className="session-edit-input"
                              onClick={(e) => e.stopPropagation()}
                            />
                          ) : (
                            <span className="session-text" title={getSessionTitle(s)}>
                              {getSessionTitle(s)}
                            </span>
                          )}

                          {editingId !== s.id && (
                            <div className="edit-session-wrapper z-20 opacity-0 transition-opacity group-hover:opacity-100">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="edit-session-button"
                                onClick={(e) => handleStartEdit(e, s)}
                                title="Rename conversation"
                              >
                                <Pencil className="w-3 h-3" />
                              </Button>
                            </div>
                          )}

                          <div className="delete-session-wrapper z-20 opacity-0 transition-opacity group-hover:opacity-100">
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
                      ))}
                    </div>
                  </div>
                );
              })
            )}
            
            {hasSessions && Object.values(groupedSessions).every(g => g.length === 0) && searchQuery && (
               <div className="empty-state">
                No results found
              </div>
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