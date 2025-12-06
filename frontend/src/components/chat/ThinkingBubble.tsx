'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft, ChevronDown, BrainCircuit } from 'lucide-react';
import MarkdownItRenderer from './MarkdownItRenderer';
import { CopyButton } from '@/components/ui/CopyButton';

interface ThinkingBubbleProps {
  content: string;
  isComplete?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
}

export const ThinkingBubble: React.FC<ThinkingBubbleProps> = ({ content, isComplete = true, onOpenChange }) => {
  const [isOpen, setIsOpen] = useState(false);

  const handleToggle = () => {
    const newOpenState = !isOpen;
    setIsOpen(newOpenState);
    onOpenChange?.(newOpenState);
  };

  if (!content) return null;

  return (
    <div className="thinking-bubble-container group">
      <button
        onClick={handleToggle}
        className="thinking-toggle-button"
      >
        <div className="thinking-toggle-left">
          <BrainCircuit className="thinking-icon" />
          <span className="thinking-label">
            {isComplete ? 'Thought Process' : 'Thinking...'}
          </span>
        </div>
        {isOpen ? (
          <ChevronDown className="thinking-chevron" />
        ) : (
          <ChevronLeft className="thinking-chevron" />
        )}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="thinking-content-wrapper"
          >
            <div className="thinking-content">
              <MarkdownItRenderer content={content} />
              <CopyButton
                text={content}
                className="thinking-copy-button"
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
