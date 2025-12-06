'use client';

import React, { useRef, useEffect, useCallback } from 'react';
import { Message } from '@/types/api';
import { ScrollArea } from '@/components/ui/scroll-area';
import { motion } from 'framer-motion';

import UserMessage from './UserMessage';
import AIMessage from './AIMessage';
import QwenLogo from './QwenLogo';

// Threshold in pixels - user must scroll within this distance from bottom to re-enable autoscroll
// Low threshold (15px) ensures user must deliberately scroll to bottom to re-engage
const SCROLL_RE_ENABLE_THRESHOLD = 15;

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
  currentContent: string;
  currentThought?: string;
  editingMessageId: string | null;
  onEditMessage?: (messageId: string) => void;
  onSaveEdit?: (messageId: string, content: string) => void;
  onCancelEdit?: () => void;
  onRegenerate?: (messageId: string) => void;
}

export default function MessageList({
  messages,
  isStreaming,
  currentContent,
  currentThought,
  editingMessageId,
  onEditMessage,
  onSaveEdit,
  onCancelEdit,
  onRegenerate,
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const userScrolledAwayRef = useRef(false);
  const thinkingBubbleOpenedRef = useRef(false);

  // Scroll to bottom helper
  const scrollToBottom = useCallback(() => {
    const scrollContainer = scrollRef.current?.querySelector('[data-radix-scroll-area-viewport]');
    if (scrollContainer) {
      scrollContainer.scrollTo({ top: scrollContainer.scrollHeight, behavior: 'smooth' });
    }
  }, []);

  // Handle thinking bubble toggle - when opened, re-enable auto-scroll and scroll to bottom
  const handleThinkingToggle = useCallback((isOpen: boolean) => {
    thinkingBubbleOpenedRef.current = isOpen;
    if (isOpen) {
      userScrolledAwayRef.current = false;
      // Small delay to let the bubble expand before scrolling
      requestAnimationFrame(() => {
        requestAnimationFrame(scrollToBottom);
      });
    }
  }, [scrollToBottom]);

  // Wheel event listener - directly detect user intent to scroll up
  // This fires BEFORE scroll events, capturing raw user input for immediate response
  useEffect(() => {
    const scrollContainer = scrollRef.current?.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement | null;
    if (!scrollContainer) return;

    const handleWheel = (e: WheelEvent) => {
      // deltaY < 0 means scrolling UP (user wants to see previous content)
      if (e.deltaY < 0) {
        userScrolledAwayRef.current = true;
      }
    };

    scrollContainer.addEventListener('wheel', handleWheel, { passive: true });
    return () => scrollContainer.removeEventListener('wheel', handleWheel);
  }, []);

  // Scroll event listener - only used to detect when user scrolls back to bottom
  // This re-enables autoscroll when user deliberately returns to the end
  useEffect(() => {
    const scrollContainer = scrollRef.current?.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement | null;
    if (!scrollContainer) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

      // Re-enable autoscroll only when user scrolls very close to bottom
      if (distanceFromBottom < SCROLL_RE_ENABLE_THRESHOLD) {
        userScrolledAwayRef.current = false;
      }
    };

    scrollContainer.addEventListener('scroll', handleScroll, { passive: true });
    return () => scrollContainer.removeEventListener('scroll', handleScroll);
  }, []);

  // Auto-scroll only if user hasn't scrolled away
  useEffect(() => {
    if (userScrolledAwayRef.current) return;
    scrollToBottom();
  }, [messages, currentContent, currentThought, scrollToBottom]);

  // Keep scrolling when thinking bubble is open and content updates (but respect user scroll-away)
  useEffect(() => {
    if (thinkingBubbleOpenedRef.current && isStreaming && currentThought && !userScrolledAwayRef.current) {
      scrollToBottom();
    }
  }, [currentThought, isStreaming, scrollToBottom]);

  // Note: We intentionally DO NOT reset scroll state when streaming starts.
  // This gives users full control - once they scroll away, they stay scrolled away
  // until they deliberately scroll back to the bottom.

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
              onRegenerate={onRegenerate}
              onThinkingToggle={handleThinkingToggle}
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
              thought: currentThought,
              created_at: new Date().toISOString(),
            }}
            isStreaming={true}
            onThinkingToggle={handleThinkingToggle}
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
