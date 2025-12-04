import React, { useState, useRef } from 'react';
import { X, ExternalLink, ZoomIn, ImageIcon, ZoomOut, Download, RotateCcw } from 'lucide-react';
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
  onImageReview?: (imageUrl: string) => void;
}

export function ImageViewer({ images, query, onImageReview }: ImageViewerProps) {
  const [selectedImage, setSelectedImage] = useState<SearchResult | null>(null);
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // Helper to select image and reset zoom state
  const selectImage = (img: SearchResult | null) => {
    setSelectedImage(img);
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const handleImageClick = (img: SearchResult, e: React.MouseEvent) => {
    if (e.ctrlKey && e.shiftKey && onImageReview) {
      e.preventDefault();
      e.stopPropagation();
      const imageUrl = img.original_image || img.link || img.thumbnail;
      if (imageUrl) {
        onImageReview(imageUrl);
      }
      return;
    }
    selectImage(img);
  };

  const handleZoomIn = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setScale(s => Math.min(s + 0.5, 4));
  };

  const handleZoomOut = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setScale(s => Math.max(s - 0.5, 1));
    if (scale <= 1.5) setPosition({ x: 0, y: 0 });
  };

  const handleReset = (e?: React.MouseEvent) => {
    e?.stopPropagation();
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

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!selectedImage) return;
    try {
      const response = await fetch(selectedImage.original_image || selectedImage.link);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = selectedImage.title || 'download';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

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
              onClick={(e) => handleImageClick(img, e)}
              layoutId={`image-${idx}`}
            >
              <div className="w-full h-full overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img 
                  src={img.original_image || img.link || img.thumbnail} 
                  alt={img.title}
                  className="image-viewer-image group-hover:scale-110"
                  loading="lazy"
                />
              </div>

              <div className="image-viewer-overlay group-hover:opacity-100" />
              
              <div className="image-viewer-info group-hover:translate-y-0 group-hover:opacity-100">
                <p className="text-sm font-medium text-white line-clamp-1 leading-tight drop-shadow-md">
                  {img.title}
                </p>
                <p className="text-[10px] text-white/70 mt-1 truncate font-mono">
                  {new URL(img.link).hostname.replace('www.', '')}
                </p>
              </div>

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
            onClick={() => selectImage(null)}
          >
            {/* Controls */}
            <motion.div 
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              className="lightbox-controls"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-2 mr-4 bg-black/40 backdrop-blur-md rounded-full p-1 border border-white/10">
                <Button
                   variant="ghost" size="icon"
                   className="h-8 w-8 text-white/70 hover:text-white rounded-full hover:bg-white/10"
                   onClick={handleZoomOut}
                   disabled={scale <= 1}
                >
                  <ZoomOut className="h-4 w-4" />
                </Button>
                <span className="text-xs font-mono text-white/70 w-8 text-center">
                  {Math.round(scale * 100)}%
                </span>
                <Button
                   variant="ghost" size="icon"
                   className="h-8 w-8 text-white/70 hover:text-white rounded-full hover:bg-white/10"
                   onClick={handleZoomIn}
                   disabled={scale >= 4}
                >
                  <ZoomIn className="h-4 w-4" />
                </Button>
                 <Button
                   variant="ghost" size="icon"
                   className="h-8 w-8 text-white/70 hover:text-white rounded-full hover:bg-white/10"
                   onClick={handleReset}
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </Button>
              </div>

              <Button
                variant="outline"
                size="icon"
                className="bg-black/20 border-white/10 text-white hover:bg-white/10 hover:text-white rounded-full backdrop-blur-md transition-colors"
                onClick={handleDownload}
                title="Download"
              >
                <Download className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="bg-black/20 border-white/10 text-white hover:bg-white/10 hover:text-white rounded-full backdrop-blur-md transition-colors"
                onClick={() => window.open(selectedImage.original_image || selectedImage.link, '_blank')}
                title="Open original"
              >
                <ExternalLink className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="bg-white/10 border-white/10 text-white hover:bg-white/20 hover:text-white rounded-full backdrop-blur-md transition-colors"
                onClick={() => selectImage(null)}
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
            >
              <div 
                ref={containerRef}
                className={cn("lightbox-image-wrapper", scale > 1 ? "cursor-grab active:cursor-grabbing" : "cursor-default")}
                onClick={(e) => e.stopPropagation()}
                onWheel={handleWheel}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                style={{
                  transform: `scale(${scale}) translate(${position.x / scale}px, ${position.y / scale}px)`,
                  transition: isDragging ? 'none' : 'transform 0.1s ease-out'
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={selectedImage.original_image || selectedImage.link}
                  alt={selectedImage.title}
                  className="lightbox-image"
                  draggable={false}
                />
              </div>

              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="lightbox-caption"
                style={{ opacity: scale > 1 ? 0 : 1, pointerEvents: scale > 1 ? 'none' : 'auto' }}
                onClick={(e) => e.stopPropagation()}
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
