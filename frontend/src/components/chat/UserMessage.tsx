'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Message } from '@/types/api';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { User, Pencil, X, Check } from 'lucide-react';
import { motion } from 'framer-motion';
import { CopyButton } from '@/components/ui/CopyButton';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import MarkdownItRenderer from './MarkdownItRenderer';

interface UserMessageProps {
  message: Message;
  isEditing?: boolean;
  isStreaming?: boolean;
  onEdit?: (messageId: string) => void;
  onSaveEdit?: (messageId: string, content: string) => void;
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
      onSaveEdit(message.id, editContent.trim());
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
            <div className="user-bubble-wrapper group">
              <div className="user-text-bubble">
                <MarkdownItRenderer content={message.content} className="user-markdown" />
              </div>
              <CopyButton
                text={message.content}
                className="user-copy-button"
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
    </motion.div>
  );
}
