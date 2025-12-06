'use client';

import { FolderPlus, MessageSquare, X } from 'lucide-react';
import { useCallback, useState } from 'react';

import type { Message, Thread } from '@/types/api';

interface ThreadOrganizerProps {
  isOpen: boolean;
  onClose: () => void;
  threads: Thread[];
  messages: Message[];
  activeThreadId: string | null;
  onThreadSelect: (threadId: string) => void;
  onCreateThread: (name: string) => void;
  onDeleteThread: (threadId: string) => void;
}

export function ThreadOrganizer({
  isOpen,
  onClose,
  threads,
  messages,
  activeThreadId,
  onThreadSelect,
  onCreateThread,
}: ThreadOrganizerProps) {
  const [isCreating, setIsCreating] = useState(false);
  const [newThreadName, setNewThreadName] = useState('');

  const getThreadPreview = useCallback(
    (thread: Thread) => {
      const threadMessages = messages.filter((m) => m.thread_id === thread.id);
      if (threadMessages.length === 0) return 'No messages';

      const firstMessage = threadMessages[0];
      const preview = firstMessage.content.slice(0, 50);
      return preview + (firstMessage.content.length > 50 ? '...' : '');
    },
    [messages]
  );

  const getThreadMessageCount = useCallback(
    (thread: Thread) => {
      return messages.filter((m) => m.thread_id === thread.id).length;
    },
    [messages]
  );

  const handleCreateThread = useCallback(() => {
    if (newThreadName.trim()) {
      onCreateThread(newThreadName.trim());
      setNewThreadName('');
      setIsCreating(false);
    }
  }, [newThreadName, onCreateThread]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        handleCreateThread();
      } else if (e.key === 'Escape') {
        setIsCreating(false);
        setNewThreadName('');
      }
    },
    [handleCreateThread]
  );

  return (
    <div className={`thread-organizer ${isOpen ? 'open' : ''}`}>
      <div className="thread-organizer-header">
        <h2 className="thread-organizer-title">Threads</h2>
        <button className="thread-organizer-close" onClick={onClose}>
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="thread-organizer-content">
        {threads.length === 0 && !isCreating ? (
          <div className="no-threads">
            <MessageSquare className="no-threads-icon" />
            <p className="no-threads-text">
              No threads yet. Create one to organize your messages.
            </p>
          </div>
        ) : (
          <div className="thread-list">
            {threads.map((thread) => (
              <div
                key={thread.id}
                className={`thread-list-item ${activeThreadId === thread.id ? 'active' : ''}`}
                onClick={() => onThreadSelect(thread.id)}
              >
                <div className="thread-list-item-header">
                  <span className="thread-list-item-name">
                    {thread.name || 'Untitled Thread'}
                  </span>
                  <span className="thread-list-item-count">
                    {getThreadMessageCount(thread)} messages
                  </span>
                </div>
                <div className="thread-list-item-preview">
                  {getThreadPreview(thread)}
                </div>
              </div>
            ))}
          </div>
        )}

        {isCreating ? (
          <div className="create-thread-input-container">
            <input
              type="text"
              className="create-thread-input"
              placeholder="Thread name..."
              value={newThreadName}
              onChange={(e) => setNewThreadName(e.target.value)}
              onKeyDown={handleKeyDown}
              autoFocus
            />
          </div>
        ) : (
          <button
            className="create-thread-button"
            onClick={() => setIsCreating(true)}
          >
            <FolderPlus className="w-4 h-4" />
            <span>Create Thread</span>
          </button>
        )}
      </div>
    </div>
  );
}
