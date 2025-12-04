'use client';

import React from 'react';
import { Message } from '@/types/api';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Bot, RefreshCw } from 'lucide-react';
import { motion } from 'framer-motion';
import { ImageViewer } from './ImageViewer';
import { CopyButton } from '@/components/ui/CopyButton';
import { Button } from '@/components/ui/button';
import MarkdownItRenderer from './MarkdownItRenderer';
import { ThinkingBubble } from './ThinkingBubble';

interface AIMessageProps {
  message: Message;
  isStreaming?: boolean;
  isGlobalStreaming?: boolean;
  onImageReview?: (imageUrl: string) => void;
  onRegenerate?: (messageId: string) => void;
}

export default function AIMessage({ message, isStreaming, isGlobalStreaming, onImageReview, onRegenerate }: AIMessageProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="ai-message-container group"
    >
      <Avatar className="ai-avatar">
        <AvatarFallback className="ai-avatar-fallback">
          <Bot className="h-5 w-5" />
        </AvatarFallback>
      </Avatar>

      <div className="ai-content-wrapper">
        {/* Thinking Bubble */}
        {message.thought && (
          <ThinkingBubble 
            content={message.thought} 
            isComplete={!isStreaming || (!!message.content && message.content.length > 0)}
            data-testid="thinking-bubble"
          />
        )}

        {/* Main Content */}
        {(message.content || message.search_results) ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="ai-prose-container relative group"
          >
            <MarkdownItRenderer content={message.content || ''} />
            <CopyButton
              text={message.content || ''}
              className="absolute bottom-2 right-2"
            />

            {/* Image Viewer */}
            {message.search_results && message.search_results.length > 0 && (
              <ImageViewer images={message.search_results} query={message.search_query} onImageReview={onImageReview} />
            )}

            {isStreaming && (
              <motion.span
                className="ai-cursor"
                animate={{ opacity: [1, 0] }}
                transition={{ duration: 0.8, repeat: Infinity }}
              />
            )}
          </motion.div>
        ) : (
          isStreaming && !message.thought && (
            <div className="loading-dots-container">
              <motion.div className="loading-dot" animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }} transition={{ duration: 1, repeat: Infinity, delay: 0 }} />
              <motion.div className="loading-dot" animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }} transition={{ duration: 1, repeat: Infinity, delay: 0.2 }} />
              <motion.div className="loading-dot" animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }} transition={{ duration: 1, repeat: Infinity, delay: 0.4 }} />
            </div>
          )
        )}

        <div className="ai-timestamp-wrapper">
          <span className="ai-timestamp">
            {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
          {onRegenerate && !isStreaming && !isGlobalStreaming && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRegenerate(message.id)}
              className="ai-regenerate-button group-hover:opacity-100"
              title="Regenerate response"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Regenerate
            </Button>
          )}
        </div>
      </div>
    </motion.div>
  );
}
