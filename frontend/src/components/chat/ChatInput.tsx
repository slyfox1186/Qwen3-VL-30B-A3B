'use client';

import React, { useImperativeHandle, forwardRef } from 'react';
import { Send, StopCircle, Mic, MicOff } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { AnimatePresence, motion } from 'framer-motion';
import { useComposer } from './composer/useComposer';
import { PromptDeck } from './composer/PromptDeck';

interface ChatInputProps {
  onSend: (content: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  hasMessages: boolean;
}

export interface ChatInputHandle {
  focus: () => void;
}

const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(({ onSend, onStop, isStreaming, hasMessages }, ref) => {
  const {
    input,
    setInput,
    isListening,
    handleSend,
    toggleVoiceInput,
    textareaRef,
  } = useComposer({ onSend, isStreaming });

  // Expose focus method to parent
  useImperativeHandle(ref, () => ({
    focus: () => {
      textareaRef.current?.focus();
    }
  }), [textareaRef]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestionSelect = (text: string) => {
    setInput(text);
    textareaRef.current?.focus();
  };

  return (
    <div className="composer-container">
      <PromptDeck
        onSelect={handleSuggestionSelect}
        isVisible={!input && !isStreaming && !hasMessages}
      />

      <div
        className={cn(
          "composer-wrapper",
          isListening && "listening"
        )}
      >
        {/* Input Area */}
        <div className="composer-input-area">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? "Listening..." : "Ask anything..."}
            className="composer-textarea"
            rows={1}
          />
        </div>

        {/* Footer Tools & Send */}
        <div className="composer-footer">
          <div className="composer-tools">
            <button
              onClick={toggleVoiceInput}
              disabled={isStreaming}
              className={cn("tool-button", isListening && "active")}
              title={isListening ? "Stop recording" : "Voice input"}
            >
              {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
            </button>
          </div>

          <div className="send-button-wrapper">
            <AnimatePresence mode="wait">
              {isStreaming ? (
                <motion.button
                  key="stop"
                  initial={{ scale: 0.5, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.5, opacity: 0 }}
                  onClick={onStop}
                  className="composer-stop-button"
                >
                  <StopCircle className="w-5 h-5 fill-current" />
                </motion.button>
              ) : (
                <motion.button
                  key="send"
                  initial={{ scale: 0.5, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.5, opacity: 0 }}
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="composer-send-button"
                >
                  <Send className="w-5 h-5 ml-0.5" />
                </motion.button>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      <div className="text-center mt-3">
        <p className="text-[10px] text-muted-foreground/50 uppercase tracking-widest font-medium">
          Qwen3-30B-A3B • AI Generated Content
        </p>
      </div>
    </div>
  );
});

ChatInput.displayName = 'ChatInput';

export default ChatInput;
