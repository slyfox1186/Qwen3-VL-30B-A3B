'use client';

import React, { useRef, useEffect } from 'react';
import { Message, SearchResult } from '@/types/api';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Brain, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

import UserMessage from './UserMessage';
import AIMessage from './AIMessage';

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
  currentThinking: string;
  currentContent: string;
  currentSearchResults?: SearchResult[];
  currentSearchQuery?: string;
}

export default function MessageList({ 
  messages, 
  isStreaming, 
  currentThinking, 
  currentContent,
  currentSearchResults,
  currentSearchQuery
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
  }, [messages, currentThinking, currentContent, isStreaming, currentSearchResults]);

  return (
    <ScrollArea className="scroll-area" ref={scrollRef}>
      <div className="message-list-wrapper">
        {messages.map((msg) => (
          msg.role === 'user' ? (
            <UserMessage key={msg.id} message={msg} />
          ) : (
            <AIMessage key={msg.id} message={msg} />
          )
        ))}
        
        {isStreaming && (
          <AIMessage 
            key="streaming-ai" 
            message={{
              id: 'streaming',
              role: 'assistant',
              content: currentContent,
              thinking: currentThinking,
              search_results: currentSearchResults,
              search_query: currentSearchQuery,
              created_at: new Date().toISOString(),
            }}
            isStreaming={true}
          />
        )}
        
        {messages.length === 0 && !isStreaming && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="empty-state-container"
          >
            <div className="empty-state-icon-wrapper">
              <div className="empty-state-glow" />
              <div className="empty-state-icon-box">
                <Brain className="empty-state-main-icon" />
                <motion.div 
                  className="empty-state-sparkle-wrapper"
                  animate={{ rotate: [0, 15, -15, 0] }}
                  transition={{ duration: 4, repeat: Infinity, repeatDelay: 1 }}
                >
                  <Sparkles className="empty-state-sparkle" />
                </motion.div>
              </div>
            </div>
            <h2 className="empty-state-title">Qwen3-VL-30B-A3B</h2>
            <p className="empty-state-description">
              Ready to analyze images and solve complex problems with advanced visual reasoning.
            </p>
            
            <div className="suggestions-grid">
               {['Analyze this chart', 'Explain this diagram', 'Extract code from screenshot', 'Identify this object'].map((label, i) => (
                 <motion.div 
                   key={label}
                   initial={{ opacity: 0, y: 10 }}
                   animate={{ opacity: 1, y: 0 }}
                   transition={{ delay: 0.2 + (i * 0.1) }}
                   className="suggestion-card"
                 >
                   {label}
                 </motion.div>
               ))}
            </div>
          </motion.div>
        )}
      </div>
    </ScrollArea>
  );
}