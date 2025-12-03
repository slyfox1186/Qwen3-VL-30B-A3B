import React, { useState } from 'react';
import { X, ExternalLink, ZoomIn, ImageIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { motion, AnimatePresence } from 'framer-motion';

interface SearchResult {
  title: string;
  link: string;
  thumbnail?: string;
  original_image?: string;
}

interface ImageViewerProps {
  images: SearchResult[];
  query?: string;
}

export function ImageViewer({ images, query }: ImageViewerProps) {
  const [selectedImage, setSelectedImage] = useState<SearchResult | null>(null);

  if (!images || images.length === 0) return null;

  return (
    <div className="image-viewer-container">
      {query && (
        <motion.div 
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          className="image-viewer-header"
        >
          <div className="image-viewer-header-text">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
            </span>
            Visual Results for <span className="text-primary font-bold">&quot;{query}&quot;</span>
          </div>
          <div className="image-viewer-badge">
            {images.length} items
          </div>
        </motion.div>
      )}
      
      {/* High-end Grid Layout */}
      <div className="image-viewer-grid">
        {images.map((img, idx) => {
          // Intelligent layout: first item is large if we have enough items
          const isLarge = idx === 0 && images.length >= 3;
          
          return (
            <motion.div
              key={`${img.link}-${idx}`}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, delay: idx * 0.05, ease: [0.23, 1, 0.32, 1] }}
              className={cn(
                "image-viewer-card group",
                isLarge ? "large" : "standard"
              )}
              onClick={() => setSelectedImage(img)}
              layoutId={`image-${idx}`}
            >
              {/* Image with subtle parallax-like scale on hover */}
              <div className="w-full h-full overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img 
                  src={img.original_image || img.link || img.thumbnail} 
                  alt={img.title}
                  className="image-viewer-image group-hover:scale-110"
                  loading="lazy"
                />
              </div>

              {/* Glassmorphism Overlay */}
              <div className="image-viewer-overlay group-hover:opacity-100" />
              
              <div className="image-viewer-info group-hover:translate-y-0 group-hover:opacity-100">
                <p className="text-sm font-medium text-white line-clamp-1 leading-tight drop-shadow-md">
                  {img.title}
                </p>
                <p className="text-[10px] text-white/70 mt-1 truncate font-mono">
                  {new URL(img.link).hostname.replace('www.', '')}
                </p>
              </div>

              {/* Hover Icon */}
              <div className="image-viewer-zoom-icon group-hover:opacity-100 group-hover:translate-y-0">
                <ZoomIn className="w-3.5 h-3.5" />
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Immersive Lightbox */}
      <AnimatePresence>
        {selectedImage && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="lightbox-overlay"
            onClick={() => setSelectedImage(null)}
          >
            {/* Controls */}
            <motion.div 
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              className="lightbox-controls"
              onClick={(e) => e.stopPropagation()}
            >
              <Button
                variant="outline"
                size="icon"
                className="bg-black/20 border-white/10 text-white hover:bg-white/10 hover:text-white rounded-full backdrop-blur-md transition-colors"
                onClick={() => window.open(selectedImage.original_image || selectedImage.link, '_blank')}
              >
                <ExternalLink className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="bg-white/10 border-white/10 text-white hover:bg-white/20 hover:text-white rounded-full backdrop-blur-md transition-colors"
                onClick={() => setSelectedImage(null)}
              >
                <X className="h-5 w-5" />
              </Button>
            </motion.div>

            {/* Main Image Content */}
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="lightbox-content"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="lightbox-image-wrapper">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={selectedImage.original_image || selectedImage.link}
                  alt={selectedImage.title}
                  className="lightbox-image"
                />
              </div>

              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="lightbox-caption"
              >
                <h3 className="text-xl font-medium text-white/90 mb-1">{selectedImage.title}</h3>
                <a 
                  href={selectedImage.link}
                  target="_blank"
                  rel="noopener noreferrer" 
                  className="text-sm text-white/50 hover:text-primary transition-colors flex items-center justify-center gap-1.5 group"
                >
                  <ImageIcon className="w-3 h-3" />
                  <span className="truncate max-w-[300px]">{selectedImage.link}</span>
                  <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </a>
              </motion.div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
