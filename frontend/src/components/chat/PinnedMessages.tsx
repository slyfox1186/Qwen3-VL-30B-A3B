'use client';

import { Pin, X } from 'lucide-react';
import { useCallback } from 'react';

import type { Message } from '@/types/api';

interface PinnedMessagesProps {
  messages: Message[];
  onUnpin: (messageId: string) => void;
  onMessageClick: (messageId: string) => void;
}

export function PinnedMessages({
  messages,
  onUnpin,
  onMessageClick,
}: PinnedMessagesProps) {
  const pinnedMessages = messages.filter((m) => m.is_pinned);

  const formatPreview = useCallback((content: string) => {
    const maxLength = 100;
    const trimmed = content.trim().replace(/\n/g, ' ');
    if (trimmed.length <= maxLength) return trimmed;
    return trimmed.slice(0, maxLength).trim() + '...';
  }, []);

  const formatTime = useCallback((dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }, []);

  if (pinnedMessages.length === 0) {
    return null;
  }

  return (
    <div className="pinned-messages">
      <div className="pinned-header">
        <Pin className="pin-icon" />
        <span>Pinned ({pinnedMessages.length})</span>
      </div>

      <div className="pinned-list">
        {pinnedMessages.map((message) => (
          <div
            key={message.id}
            className="pinned-message"
            onClick={() => onMessageClick(message.id)}
          >
            <div className="pinned-message-content">
              <div className="pinned-message-preview">
                {formatPreview(message.content)}
              </div>
              <div className="pinned-message-meta">
                <span>{message.role === 'user' ? 'You' : 'Assistant'}</span>
                <span>&bull;</span>
                <span>{formatTime(message.created_at)}</span>
              </div>
            </div>

            <div className="pinned-message-actions">
              <button
                className="unpin-button"
                onClick={(e) => {
                  e.stopPropagation();
                  onUnpin(message.id);
                }}
                title="Unpin message"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
