import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import Image from 'next/image';

interface AttachmentZoneProps {
  images: string[];
  onRemove: (index: number) => void;
}

export function AttachmentZone({ images, onRemove }: AttachmentZoneProps) {
  return (
    <AnimatePresence>
      {images.length > 0 && (
        <motion.div 
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="attachment-zone-container"
        >
          {images.map((img, idx) => (
            <motion.div 
              key={idx} 
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.5, opacity: 0 }}
              className="attachment-item group"
            >
              <Image 
                src={img} 
                alt="preview" 
                fill
                className="object-cover" 
                unoptimized
              />
              <button 
                onClick={() => onRemove(idx)}
                className="attachment-remove-btn"
              >
                <X className="w-3 h-3" />
              </button>
            </motion.div>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
