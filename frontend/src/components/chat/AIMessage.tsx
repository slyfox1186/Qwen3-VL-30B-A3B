'use client';

import React, { useState } from 'react';
import { Message } from '@/types/api';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Bot, ChevronDown, BrainCircuit } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/cjs/styles/prism';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import { ImageViewer } from './ImageViewer';

interface AIMessageProps {
  message: Message;
  isStreaming?: boolean;
  onImageReview?: (imageUrl: string) => void;
}

export default function AIMessage({ message, isStreaming, onImageReview }: AIMessageProps) {
  const [isThinkingOpen, setIsThinkingOpen] = useState(true);
  
  const hasThinking = !!message.thinking && message.thinking.length > 0;

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
        {/* Thinking Block */}
        <AnimatePresence initial={false}>
          {hasThinking && (
            <motion.div
              className="thinking-block"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              <button 
                onClick={() => setIsThinkingOpen(!isThinkingOpen)}
                className="thinking-header"
              >
                <div className="flex items-center gap-2">
                  <BrainCircuit className="h-3.5 w-3.5" />
                  <span>Reasoning Process</span>
                  {isStreaming && !message.content && (
                    <span className="flex gap-0.5 items-center ml-1">
                      <motion.span className="w-1 h-1 bg-primary rounded-full" animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1.5, repeat: Infinity }} />
                      <motion.span className="w-1 h-1 bg-primary rounded-full" animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1.5, delay: 0.2, repeat: Infinity }} />
                      <motion.span className="w-1 h-1 bg-primary rounded-full" animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1.5, delay: 0.4, repeat: Infinity }} />
                    </span>
                  )}
                </div>
                <motion.div
                  animate={{ rotate: isThinkingOpen ? 180 : 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <ChevronDown className="h-3.5 w-3.5" />
                </motion.div>
              </button>
              
              <motion.div
                initial={false}
                animate={{ height: isThinkingOpen ? 'auto' : 0, opacity: isThinkingOpen ? 1 : 0 }}
                transition={{ duration: 0.3, ease: "easeInOut" }}
                className="thinking-content-wrapper"
              >
                <div className="thinking-text">
                  {message.thinking}
                  {isStreaming && !message.content && (
                     <motion.span 
                       className="thinking-cursor"
                       animate={{ opacity: [1, 0] }}
                       transition={{ duration: 0.8, repeat: Infinity }}
                     />
                  )}
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Main Content */}
        {message.content || message.search_results ? (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="ai-prose-container"
          >
            <ReactMarkdown
              components={{
                code({ inline, className, children, ...props }: React.ComponentPropsWithoutRef<'code'> & { inline?: boolean }) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match ? (
                    <div className="code-block-wrapper group">
                      <div className="code-language-badge">
                        {match[1]}
                      </div>
                      <SyntaxHighlighter
                        {...props}
                        style={oneDark}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{ margin: 0, borderRadius: 0, padding: '1.25rem' }}
                        codeTagProps={{ style: { fontSize: '0.85rem', fontFamily: 'var(--font-geist-mono)' } }}
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    </div>
                  ) : (
                    <code {...props} className={cn("inline-code", className)}>
                      {children}
                    </code>
                  );
                },
                p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
                ul: ({ children }) => <ul className="my-4 ml-6 list-disc [&>li]:mt-2">{children}</ul>,
                ol: ({ children }) => <ol className="my-4 ml-6 list-decimal [&>li]:mt-2">{children}</ol>,
                li: ({ children }) => <li className="pl-1">{children}</li>,
                h1: ({ children }) => <h1 className="text-2xl font-bold tracking-tight mt-6 mb-4">{children}</h1>,
                h2: ({ children }) => <h2 className="text-xl font-semibold tracking-tight mt-5 mb-3">{children}</h2>,
                h3: ({ children }) => <h3 className="text-lg font-semibold tracking-tight mt-4 mb-2">{children}</h3>,
                blockquote: ({ children }) => <blockquote className="mt-4 mb-4 border-l-2 border-primary/50 pl-4 italic text-muted-foreground">{children}</blockquote>,
              }}
            >
              {message.content || ''}
            </ReactMarkdown>
            
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
          isStreaming && !hasThinking && (
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
           {/* Future: Copy / Regenerate buttons could go here */}
        </div>
      </div>
    </motion.div>
  );
}