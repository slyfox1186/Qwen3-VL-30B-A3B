'use client';

import React, { useRef, useEffect } from 'react';
import { Message, SearchResult } from '@/types/api';
import { ScrollArea } from '@/components/ui/scroll-area';
import { motion } from 'framer-motion';

import UserMessage from './UserMessage';
import AIMessage from './AIMessage';
import QwenLogo from './QwenLogo';

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
  currentContent: string;
  currentSearchResults?: SearchResult[];
  currentSearchQuery?: string;
  onImageReview?: (imageUrl: string) => void;
  editingMessageId: string | null;
  onEditMessage?: (messageId: string) => void;
  onSaveEdit?: (messageId: string, content: string, images: string[]) => void;
  onCancelEdit?: () => void;
  onRegenerate?: (messageId: string) => void;
}

export default function MessageList({
  messages,
  isStreaming,
  currentContent,
  currentSearchResults,
  currentSearchQuery,
  onImageReview,
  editingMessageId,
  onEditMessage,
  onSaveEdit,
  onCancelEdit,
  onRegenerate,
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      const scrollContainer = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTo({
          top: scrollContainer.scrollHeight,
          behavior: 'smooth'
        });
      }
    }
  }, [messages, currentContent, isStreaming, currentSearchResults]);

  return (
    <ScrollArea className="scroll-area" ref={scrollRef}>
      <div className="message-list-wrapper">
        {messages.map((msg) => (
          msg.role === 'user' ? (
            <UserMessage
              key={`${msg.id}-${editingMessageId === msg.id ? 'editing' : 'view'}`}
              message={msg}
              isEditing={editingMessageId === msg.id}
              isStreaming={isStreaming}
              onEdit={onEditMessage}
              onSaveEdit={onSaveEdit}
              onCancelEdit={onCancelEdit}
            />
          ) : (
            <AIMessage
              key={msg.id}
              message={msg}
              isGlobalStreaming={isStreaming}
              onImageReview={onImageReview}
              onRegenerate={onRegenerate}
            />
          )
        ))}

        {isStreaming && (
          <AIMessage
            key="streaming-ai"
            message={{
              id: 'streaming',
              role: 'assistant',
              content: currentContent,
              search_results: currentSearchResults,
              search_query: currentSearchQuery,
              created_at: new Date().toISOString(),
            }}
            isStreaming={true}
            onImageReview={onImageReview}
          />
        )}

        {messages.length === 0 && !isStreaming && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="empty-state-container flex flex-col items-center justify-center h-full min-h-[60vh]"
          >
            <QwenLogo />
          </motion.div>
        )}
      </div>
    </ScrollArea>
  );
}
