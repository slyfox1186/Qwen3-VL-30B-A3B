'use client';

import { ChevronDown, MessageSquare } from 'lucide-react';
import { useCallback, useState } from 'react';

import type { Message, Thread } from '@/types/api';

interface ThreadViewProps {
  thread: Thread;
  messages: Message[];
  onToggle: (threadId: string) => void;
  renderMessage: (message: Message) => React.ReactNode;
}

export function ThreadView({
  thread,
  messages,
  onToggle,
  renderMessage,
}: ThreadViewProps) {
  const [isOpen, setIsOpen] = useState(!thread.collapsed);

  // Get messages that belong to this thread
  const threadMessages = messages.filter((m) => m.thread_id === thread.id);

  // Sort by thread position if available, otherwise by created_at
  const sortedMessages = [...threadMessages].sort((a, b) => {
    if (a.thread_position !== undefined && b.thread_position !== undefined) {
      return a.thread_position - b.thread_position;
    }
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  });

  const handleToggle = useCallback(() => {
    setIsOpen(!isOpen);
    onToggle(thread.id);
  }, [isOpen, thread.id, onToggle]);

  if (threadMessages.length === 0) {
    return null;
  }

  return (
    <div className="thread-view">
      <button
        className="thread-header"
        onClick={handleToggle}
        data-state={isOpen ? 'open' : 'closed'}
      >
        <div className="thread-header-left">
          <MessageSquare className="thread-icon" />
          <span className="thread-name">{thread.name || 'Thread'}</span>
          <span className="thread-count">
            {threadMessages.length} message
            {threadMessages.length !== 1 ? 's' : ''}
          </span>
        </div>
        <ChevronDown className="thread-chevron" />
      </button>

      <div className="thread-content" data-state={isOpen ? 'open' : 'closed'}>
        <div className="thread-messages">
          {sortedMessages.map((message) => renderMessage(message))}
        </div>
      </div>
    </div>
  );
}
