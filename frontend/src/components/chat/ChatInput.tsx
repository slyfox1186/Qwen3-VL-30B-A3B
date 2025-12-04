'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, ImagePlus, StopCircle, X, Paperclip, Mic, MicOff, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';

// Speech Recognition Interfaces
interface SpeechRecognitionEvent extends Event {
  results: {
    [key: number]: {
      [key: number]: {
        transcript: string;
      };
    };
  } & Iterable<unknown>;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: (event: Event) => void;
  onend: (event: Event) => void;
  onerror: (event: SpeechRecognitionErrorEvent) => void;
  onresult: (event: SpeechRecognitionEvent) => void;
}

interface ChatInputProps {
  onSend: (content: string, images: string[]) => void;
  onStop: () => void;
  isStreaming: boolean;
}

const SUGGESTIONS = [
  "Describe this image",
  "Summarize this text",
  "Write a Python script",
  "Explain quantum physics"
];

export default function ChatInput({ onSend, onStop, isStreaming }: ChatInputProps) {
  const [input, setInput] = useState('');
  const [images, setImages] = useState<string[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // Initialize Speech Recognition
  useEffect(() => {
    if (typeof window !== 'undefined') {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const SpeechRecognitionConstructor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      
      if (SpeechRecognitionConstructor) {
        const recognition = new SpeechRecognitionConstructor() as SpeechRecognition;
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => setIsListening(true);
        recognition.onend = () => setIsListening(false);
        recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
          console.error('Speech recognition error', event.error);
          setIsListening(false);
          toast.error('Voice input failed: ' + event.error);
        };
        recognition.onresult = (event: SpeechRecognitionEvent) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const result = (event.results as any)[0][0];
          const transcript = result.transcript;
          setInput(prev => (prev ? prev + ' ' + transcript : transcript));
        };

        recognitionRef.current = recognition;
      }
    }
  }, []);

  const toggleVoiceInput = () => {
    if (!recognitionRef.current) {
      toast.error('Speech recognition not supported in this browser.');
      return;
    }
    
    if (isListening) {
      recognitionRef.current.stop();
    } else {
      recognitionRef.current.start();
      toast.info('Listening...');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if ((!input.trim() && images.length === 0) || isStreaming) return;
    onSend(input, images);
    setInput('');
    setImages([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const processFiles = useCallback((files: FileList | File[]) => {
    const validFiles: File[] = [];
    Array.from(files).forEach(file => {
      if (file.size > 10 * 1024 * 1024) {
        toast.error(`File ${file.name} exceeds 10MB limit`);
        return;
      }
      if (!file.type.startsWith('image/')) {
        toast.error(`File ${file.name} is not an image`);
        return;
      }
      validFiles.push(file);
    });

    if (images.length + validFiles.length > 4) {
      toast.error('Max 4 images allowed');
      return;
    }

    validFiles.forEach(file => {
      const reader = new FileReader();
      reader.onloadend = () => {
        if (reader.result && typeof reader.result === 'string') {
          setImages(prev => [...prev, reader.result as string].slice(0, 4));
        }
      };
      reader.readAsDataURL(file);
    });
  }, [images]);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      processFiles(e.target.files);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeImage = (index: number) => {
    setImages(prev => prev.filter((_, i) => i !== index));
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    const files: File[] = [];
    for (const item of items) {
      if (item.type.indexOf('image') !== -1) {
        const file = item.getAsFile();
        if (file) files.push(file);
      }
    }
    if (files.length > 0) {
      e.preventDefault();
      processFiles(files);
    }
  };

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files) {
      processFiles(e.dataTransfer.files);
    }
  }, [processFiles]);

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  return (
    <div className="chat-input-container">
      {/* Suggestions */}
      <AnimatePresence>
        {!input && images.length === 0 && !isStreaming && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="suggestions-container"
          >
            {SUGGESTIONS.map((s, i) => (
              <button 
                key={i} 
                onClick={() => handleSuggestionClick(s)}
                className="suggestion-chip"
              >
                <Sparkles className="w-3 h-3 mr-1.5 text-primary" />
                {s}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div 
        layout
        className={cn(
          "chat-input-wrapper",
          isDragging ? "dragging" : "default",
          isListening ? "listening" : ""
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
              className="drag-overlay"
            >
              <div className="drag-overlay-content">
                <ImagePlus className="w-10 h-10 animate-bounce" />
                Drop images here
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Image Previews */}
        <AnimatePresence>
          {images.length > 0 && (
            <motion.div 
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="image-preview-container"
            >
              {images.map((img, idx) => (
                <motion.div 
                  key={idx} 
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.5, opacity: 0 }}
                  className="image-preview-item group"
                >
                  <div className="image-preview-box">
                    <Image 
                      src={img} 
                      alt="preview" 
                      fill
                      className="object-cover" 
                      unoptimized
                    />
                  </div>
                  <button 
                    onClick={() => removeImage(idx)}
                    className="image-preview-remove"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Input Area */}
        <div className="chat-input-controls">
          <div className="flex items-center gap-1">
            <Button 
              variant="ghost" 
              size="icon" 
              className="attach-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isStreaming || images.length >= 4}
              title="Attach images"
            >
              <Paperclip className="w-5 h-5" />
              <span className="sr-only">Attach files</span>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className={cn("voice-button", isListening && "text-red-500 animate-pulse")}
              onClick={toggleVoiceInput}
              disabled={isStreaming}
              title={isListening ? "Stop recording" : "Voice input"}
            >
              {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
            </Button>
          </div>
          
          <input 
            type="file" 
            ref={fileInputRef}
            className="hidden"
            accept="image/jpeg,image/png,image/webp,image/gif"
            multiple
            onChange={handleImageUpload}
          />

          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={isListening ? "Listening..." : "Ask anything about images..."}
            className="chat-textarea"
            rows={1}
          />

          <div className="pb-0.5">
            {isStreaming ? (
               <Button 
                 size="icon" 
                 variant="destructive" 
                 className="stop-button"
                 onClick={onStop}
               >
                 <StopCircle className="w-5 h-5 fill-current" />
               </Button>
            ) : (
              <Button 
                size="icon" 
                className={cn("send-button", (input.trim() || images.length > 0) ? "opacity-100" : "opacity-50")}
                onClick={handleSend}
                disabled={!input.trim() && images.length === 0}
              >
                <Send className="w-5 h-5 ml-0.5" />
              </Button>
            )}
          </div>
        </div>
      </motion.div>
      
      <div className="chat-footer-text">
        <p className="chat-footer-caption">
          Qwen3-VL-30B-A3B • AI Generated Content
        </p>
      </div>
    </div>
  );
}