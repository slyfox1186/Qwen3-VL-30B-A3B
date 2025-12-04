'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Message } from '@/types/api';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { User, Pencil, X, Check, ZoomIn, ZoomOut, RotateCcw, Download, ChevronLeft, ChevronRight } from 'lucide-react';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import { CopyButton } from '@/components/ui/CopyButton';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

interface UserMessageProps {
  message: Message;
  isEditing?: boolean;
  isStreaming?: boolean;
  onEdit?: (messageId: string) => void;
  onSaveEdit?: (messageId: string, content: string, images: string[]) => void;
  onCancelEdit?: () => void;
}

export default function UserMessage({
  message,
  isEditing = false,
  isStreaming = false,
  onEdit,
  onSaveEdit,
  onCancelEdit,
}: UserMessageProps) {
  const [editContent, setEditContent] = useState(message.content);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Lightbox state
  const [selectedImageIndex, setSelectedImageIndex] = useState<number | null>(null);
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });

  const images = message.images || [];
  const selectedImage = selectedImageIndex !== null ? images[selectedImageIndex] : null;

  const openLightbox = (index: number) => {
    setSelectedImageIndex(index);
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const closeLightbox = () => {
    setSelectedImageIndex(null);
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const goToPrevious = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (selectedImageIndex !== null && selectedImageIndex > 0) {
      setSelectedImageIndex(selectedImageIndex - 1);
      setScale(1);
      setPosition({ x: 0, y: 0 });
    }
  };

  const goToNext = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (selectedImageIndex !== null && selectedImageIndex < images.length - 1) {
      setSelectedImageIndex(selectedImageIndex + 1);
      setScale(1);
      setPosition({ x: 0, y: 0 });
    }
  };

  const handleZoomIn = (e: React.MouseEvent) => {
    e.stopPropagation();
    setScale(s => Math.min(s + 0.5, 4));
  };

  const handleZoomOut = (e: React.MouseEvent) => {
    e.stopPropagation();
    setScale(s => Math.max(s - 0.5, 1));
    if (scale <= 1.5) setPosition({ x: 0, y: 0 });
  };

  const handleReset = (e: React.MouseEvent) => {
    e.stopPropagation();
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const handleWheel = (e: React.WheelEvent) => {
    if (selectedImage) {
      e.stopPropagation();
      const delta = e.deltaY * -0.002;
      const newScale = Math.min(Math.max(1, scale + delta), 4);
      setScale(newScale);
      if (newScale === 1) setPosition({ x: 0, y: 0 });
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (scale > 1) {
      e.preventDefault();
      setIsDragging(true);
      dragStart.current = { x: e.clientX - position.x, y: e.clientY - position.y };
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging && scale > 1) {
      e.preventDefault();
      setPosition({
        x: e.clientX - dragStart.current.x,
        y: e.clientY - dragStart.current.y
      });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!selectedImage) return;
    const a = document.createElement('a');
    a.href = selectedImage.startsWith('data:') ? selectedImage : `data:image/jpeg;base64,${selectedImage}`;
    a.download = `image-${selectedImageIndex}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  // Keyboard navigation
  useEffect(() => {
    if (selectedImageIndex === null) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeLightbox();
      if (e.key === 'ArrowLeft' && selectedImageIndex > 0) {
        setSelectedImageIndex(selectedImageIndex - 1);
        setScale(1);
        setPosition({ x: 0, y: 0 });
      }
      if (e.key === 'ArrowRight' && selectedImageIndex < images.length - 1) {
        setSelectedImageIndex(selectedImageIndex + 1);
        setScale(1);
        setPosition({ x: 0, y: 0 });
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedImageIndex, images.length]);

  // Focus and set cursor when entering edit mode
  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.setSelectionRange(
        textareaRef.current.value.length,
        textareaRef.current.value.length
      );
    }
  }, [isEditing]);

  const handleSave = () => {
    if (editContent.trim() && onSaveEdit) {
      onSaveEdit(message.id, editContent.trim(), message.images || []);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      onCancelEdit?.();
    }
  };
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="user-message-container group"
    >
      <div className="user-message-content-wrapper">
        {/* Images Grid */}
        {images.length > 0 && (
          <div className="user-images-grid">
            {images.map((img, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.1 * idx }}
                className="user-image-wrapper cursor-pointer group/img"
                onClick={() => openLightbox(idx)}
              >
                <Image
                  src={img.startsWith('data:') ? img : `data:image/jpeg;base64,${img}`}
                  alt={`User uploaded ${idx + 1}`}
                  fill
                  className="user-image"
                  unoptimized
                />
                <div className="absolute inset-0 bg-black/0 group-hover/img:bg-black/20 transition-colors flex items-center justify-center">
                  <ZoomIn className="w-5 h-5 text-white opacity-0 group-hover/img:opacity-100 transition-opacity drop-shadow-lg" />
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Edit Mode */}
        {isEditing ? (
          <div className="user-edit-container">
            <Textarea
              ref={textareaRef}
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              onKeyDown={handleKeyDown}
              className="user-edit-textarea"
              placeholder="Edit your message..."
              rows={3}
            />
            <div className="user-edit-actions">
              <span className="user-edit-hint">Ctrl+Enter to save, Esc to cancel</span>
              <div className="user-edit-buttons">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onCancelEdit}
                  className="user-edit-cancel"
                >
                  <X className="w-4 h-4 mr-1" />
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleSave}
                  disabled={!editContent.trim()}
                  className="user-edit-save"
                >
                  <Check className="w-4 h-4 mr-1" />
                  Save & Send
                </Button>
              </div>
            </div>
          </div>
        ) : (
          /* Message Bubble */
          message.content && (
            <div className="relative group">
              <div className="user-text-bubble">
                <p className="user-text">{message.content}</p>
              </div>
              <div className="user-message-actions">
                <CopyButton
                  text={message.content}
                  className="text-muted-foreground hover:text-foreground hover:bg-muted h-7 w-7"
                />
                {onEdit && !isStreaming && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onEdit(message.id)}
                    className="user-edit-button"
                    title="Edit message"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </Button>
                )}
              </div>
            </div>
          )
        )}

        <span className="user-timestamp group-hover:opacity-100">
          {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>

      <Avatar className="user-avatar">
        <AvatarFallback className="user-avatar-fallback">
          <User className="h-4 w-4 text-muted-foreground" />
        </AvatarFallback>
      </Avatar>

      {/* Lightbox Modal */}
      <AnimatePresence>
        {selectedImage && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center"
            onClick={closeLightbox}
          >
            {/* Controls */}
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              className="absolute top-4 right-4 flex items-center gap-2 z-10"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-1 bg-black/40 backdrop-blur-md rounded-full p-1 border border-white/10">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-white/70 hover:text-white rounded-full hover:bg-white/10"
                  onClick={handleZoomOut}
                  disabled={scale <= 1}
                >
                  <ZoomOut className="h-4 w-4" />
                </Button>
                <span className="text-xs font-mono text-white/70 w-10 text-center">
                  {Math.round(scale * 100)}%
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-white/70 hover:text-white rounded-full hover:bg-white/10"
                  onClick={handleZoomIn}
                  disabled={scale >= 4}
                >
                  <ZoomIn className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-white/70 hover:text-white rounded-full hover:bg-white/10"
                  onClick={handleReset}
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </Button>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 bg-black/40 border border-white/10 text-white/70 hover:text-white rounded-full hover:bg-white/10 backdrop-blur-md"
                onClick={handleDownload}
                title="Download"
              >
                <Download className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 bg-white/10 border border-white/10 text-white hover:bg-white/20 rounded-full backdrop-blur-md"
                onClick={(e) => { e.stopPropagation(); closeLightbox(); }}
              >
                <X className="h-5 w-5" />
              </Button>
            </motion.div>

            {/* Navigation Arrows */}
            {images.length > 1 && (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    "absolute left-4 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full bg-black/40 border border-white/10 text-white/70 hover:text-white hover:bg-white/10 backdrop-blur-md z-10",
                    selectedImageIndex === 0 && "opacity-30 cursor-not-allowed"
                  )}
                  onClick={goToPrevious}
                  disabled={selectedImageIndex === 0}
                >
                  <ChevronLeft className="h-6 w-6" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    "absolute right-4 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full bg-black/40 border border-white/10 text-white/70 hover:text-white hover:bg-white/10 backdrop-blur-md z-10",
                    selectedImageIndex === images.length - 1 && "opacity-30 cursor-not-allowed"
                  )}
                  onClick={goToNext}
                  disabled={selectedImageIndex === images.length - 1}
                >
                  <ChevronRight className="h-6 w-6" />
                </Button>
              </>
            )}

            {/* Image */}
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="relative max-w-[90vw] max-h-[85vh] flex items-center justify-center"
              onClick={(e) => e.stopPropagation()}
              onWheel={handleWheel}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
            >
              <div
                className={cn(
                  "relative",
                  scale > 1 ? "cursor-grab active:cursor-grabbing" : "cursor-default"
                )}
                style={{
                  transform: `scale(${scale}) translate(${position.x / scale}px, ${position.y / scale}px)`,
                  transition: isDragging ? 'none' : 'transform 0.1s ease-out'
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={selectedImage.startsWith('data:') ? selectedImage : `data:image/jpeg;base64,${selectedImage}`}
                  alt="Full size preview"
                  className="max-w-[90vw] max-h-[85vh] object-contain rounded-lg shadow-2xl"
                  draggable={false}
                />
              </div>
            </motion.div>

            {/* Image Counter */}
            {images.length > 1 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/40 backdrop-blur-md rounded-full px-4 py-2 border border-white/10"
              >
                <span className="text-sm text-white/70 font-medium">
                  {(selectedImageIndex ?? 0) + 1} / {images.length}
                </span>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}