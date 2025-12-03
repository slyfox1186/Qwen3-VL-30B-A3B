'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, ImagePlus, StopCircle, X, Paperclip } from 'lucide-react';
import { cn } from '@/lib/utils';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';

interface ChatInputProps {
  onSend: (content: string, images: string[]) => void;
  onStop: () => void;
  isStreaming: boolean;
}

export default function ChatInput({ onSend, onStop, isStreaming }: ChatInputProps) {
  const [input, setInput] = useState('');
  const [images, setImages] = useState<string[]>([]); // Base64 strings
  const [isDragging, setIsDragging] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

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

  return (
    <div className="chat-input-container">
      <motion.div 
        layout
        className={cn(
          "chat-input-wrapper",
          isDragging ? "dragging" : "default"
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
                    className="image-preview-remove group-hover:opacity-100"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Input Area */}
        <div className="chat-input-controls">
          <Button 
            variant="ghost" 
            size="icon" 
            className="attach-button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isStreaming || images.length >= 4}
          >
            <Paperclip className="w-5 h-5" />
            <span className="sr-only">Attach files</span>
          </Button>
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
            placeholder="Ask anything about images..."
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