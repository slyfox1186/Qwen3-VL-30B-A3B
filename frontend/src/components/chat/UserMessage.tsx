'use client';

import React from 'react';
import { Message } from '@/types/api';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { User } from 'lucide-react';
import Image from 'next/image';
import { motion } from 'framer-motion';

interface UserMessageProps {
  message: Message;
}

export default function UserMessage({ message }: UserMessageProps) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="user-message-container group"
    >
      <div className="user-message-content-wrapper">
        {/* Images Grid */}
        {message.images && message.images.length > 0 && (
          <div className="user-images-grid">
            {message.images.map((img, idx) => (
              <motion.div 
                key={idx} 
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.1 * idx }}
                className="user-image-wrapper"
              >
                <Image 
                  src={img.startsWith('data:') ? img : `data:image/jpeg;base64,${img}`} 
                  alt={`User uploaded ${idx + 1}`}
                  fill
                  className="user-image"
                  unoptimized
                />
              </motion.div>
            ))}
          </div>
        )}

        {/* Message Bubble */}
        {message.content && (
           <div className="user-text-bubble">
             <p className="user-text">{message.content}</p>
           </div>
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