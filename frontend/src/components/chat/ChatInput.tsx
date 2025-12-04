'use client';

import React from 'react';
import { Paperclip, Send, StopCircle, Mic, MicOff, ImagePlus } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { AnimatePresence, motion } from 'framer-motion';
import { useComposer } from './composer/useComposer';
import { PromptDeck } from './composer/PromptDeck';
import { AttachmentZone } from './composer/AttachmentZone';

interface ChatInputProps {
  onSend: (content: string, images: string[]) => void;
  onStop: () => void;
  isStreaming: boolean;
}

export default function ChatInput({ onSend, onStop, isStreaming }: ChatInputProps) {
  const {
    input,
    setInput,
    images,
    isDragging,
    isListening,
    handleSend,
    handleImageUpload,
    removeImage,
    toggleVoiceInput,
    textareaRef,
    fileInputRef,
    onDragOver,
    onDragLeave,
    onDrop
  } = useComposer({ onSend, isStreaming });

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
        isVisible={!input && images.length === 0 && !isStreaming} 
      />

      <div 
        className={cn(
          "composer-wrapper",
          isDragging && "ring-2 ring-primary/50 bg-primary/5",
          isListening && "listening"
        )}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        {/* Drag Overlay */}
        <AnimatePresence>
          {isDragging && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 z-50 flex items-center justify-center bg-background/60 backdrop-blur-sm rounded-[2rem]"
            >
              <div className="flex flex-col items-center text-primary font-medium animate-bounce">
                <ImagePlus className="w-10 h-10 mb-2" />
                <span>Drop images to attach</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Attachments */}
        <AttachmentZone images={images} onRemove={removeImage} />

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
            <input 
              type="file" 
              ref={fileInputRef}
              className="hidden"
              accept="image/jpeg,image/png,image/webp,image/gif"
              multiple
              onChange={handleImageUpload}
            />
            
            <button 
              onClick={() => fileInputRef.current?.click()}
              disabled={isStreaming || images.length >= 4}
              className="tool-button"
              title="Attach images"
            >
              <Paperclip className="w-5 h-5" />
            </button>
            
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
                  disabled={!input.trim() && images.length === 0}
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
          Qwen3-VL-30B-A3B • AI Generated Content
        </p>
      </div>
    </div>
  );
}
