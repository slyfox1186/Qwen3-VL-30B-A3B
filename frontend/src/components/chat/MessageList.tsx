'use client';

import React, { useRef, useEffect, useCallback } from 'react';
import { Message, SearchResult } from '@/types/api';
import { ScrollArea } from '@/components/ui/scroll-area';
import { motion } from 'framer-motion';

import UserMessage from './UserMessage';
import AIMessage from './AIMessage';
import QwenLogo from './QwenLogo';

// Threshold in pixels - if user scrolls more than this distance from bottom, auto-scroll stops
// Using 150px to give users a clear escape from autoscroll
const SCROLL_THRESHOLD = 150;

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
  currentContent: string;
  currentThought?: string;
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
  currentThought,
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

  // Handle user scroll - detect if they scrolled away from bottom
  // Once user scrolls away during streaming, stay "scrolled away" until streaming stops
  useEffect(() => {
    const scrollContainer = scrollRef.current?.querySelector('[data-radix-scroll-area-viewport]');
    if (!scrollContainer) return;

    let lastScrollTop = scrollContainer.scrollTop;
    let lastScrollTime = 0;

    const handleScroll = () => {
      const now = Date.now();
      const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      const scrolledUp = scrollTop < lastScrollTop - 5; // 5px tolerance for noise

      lastScrollTop = scrollTop;

      // If user actively scrolls up (not just smooth scroll animation), mark as scrolled away
      if (scrolledUp && distanceFromBottom > SCROLL_THRESHOLD) {
        userScrolledAwayRef.current = true;
        lastScrollTime = now;
      }

      // Only re-enable autoscroll if user manually scrolls to bottom AND we're not mid-scroll
      // (wait 200ms after last scroll to distinguish user intent from animation)
      if (distanceFromBottom < 30 && now - lastScrollTime > 200) {
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
  }, [messages, currentContent, currentThought, currentSearchResults, scrollToBottom]);

  // Keep scrolling when thinking bubble is open and content updates (but respect user scroll-away)
  useEffect(() => {
    if (thinkingBubbleOpenedRef.current && isStreaming && currentThought && !userScrolledAwayRef.current) {
      scrollToBottom();
    }
  }, [currentThought, isStreaming, scrollToBottom]);

  // Reset scroll state when new message starts
  useEffect(() => {
    if (isStreaming) {
      userScrolledAwayRef.current = false;
    }
  }, [isStreaming]);

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
              search_results: currentSearchResults,
              search_query: currentSearchQuery,
              created_at: new Date().toISOString(),
            }}
            isStreaming={true}
            onImageReview={onImageReview}
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
