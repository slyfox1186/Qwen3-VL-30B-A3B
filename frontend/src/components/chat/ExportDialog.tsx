'use client';

import React, { useState } from 'react';
import { X, Download, FileText, FileJson, FileType } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { Message } from '@/types/api';
import { exportConversation, ExportOptions } from '@/lib/export-utils';
import { cn } from '@/lib/utils';
import '@/styles/components/export-dialog.css';

interface ExportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  messages: Message[];
  sessionTitle?: string;
}

type ExportFormat = 'markdown' | 'json' | 'pdf';

const formatOptions: { id: ExportFormat; label: string; icon: React.ReactNode; desc: string }[] = [
  {
    id: 'markdown',
    label: 'Markdown',
    icon: <FileText className="w-5 h-5" />,
    desc: 'Human-readable with formatting',
  },
  {
    id: 'json',
    label: 'JSON',
    icon: <FileJson className="w-5 h-5" />,
    desc: 'Machine-readable with metadata',
  },
  {
    id: 'pdf',
    label: 'PDF',
    icon: <FileType className="w-5 h-5" />,
    desc: 'Print-ready document',
  },
];

export default function ExportDialog({
  isOpen,
  onClose,
  messages,
  sessionTitle,
}: ExportDialogProps) {
  const [format, setFormat] = useState<ExportFormat>('markdown');
  const [includeThoughts, setIncludeThoughts] = useState(true);
  const [includeImages, setIncludeImages] = useState(true);
  const [includeTimestamps, setIncludeTimestamps] = useState(true);

  const handleExport = () => {
    const options: ExportOptions = {
      format,
      includeThoughts,
      includeImages,
      includeTimestamps,
      sessionTitle,
    };

    exportConversation(messages, options);
    onClose();
  };

  // Count messages with thoughts and images
  const thoughtCount = messages.filter((m) => m.thought).length;
  const imageCount = messages.filter((m) => m.images?.length || m.search_results?.length).length;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            className="export-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="export-dialog"
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          >
            <div className="export-header">
              <div className="export-title">
                <Download className="w-5 h-5" />
                <span>Export Conversation</span>
              </div>
              <button onClick={onClose} className="export-close-btn">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="export-body">
              {/* Format Selection */}
              <div className="export-section">
                <label className="export-label">Format</label>
                <div className="format-grid">
                  {formatOptions.map((opt) => (
                    <button
                      key={opt.id}
                      onClick={() => setFormat(opt.id)}
                      className={cn('format-option', format === opt.id && 'active')}
                    >
                      <div className="format-icon">{opt.icon}</div>
                      <div className="format-info">
                        <span className="format-name">{opt.label}</span>
                        <span className="format-desc">{opt.desc}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Options */}
              <div className="export-section">
                <label className="export-label">Include</label>
                <div className="option-list">
                  <label className="option-item">
                    <input
                      type="checkbox"
                      checked={includeThoughts}
                      onChange={(e) => setIncludeThoughts(e.target.checked)}
                      className="option-checkbox"
                    />
                    <span className="option-text">
                      Thinking sections
                      {thoughtCount > 0 && (
                        <span className="option-count">({thoughtCount})</span>
                      )}
                    </span>
                  </label>
                  <label className="option-item">
                    <input
                      type="checkbox"
                      checked={includeImages}
                      onChange={(e) => setIncludeImages(e.target.checked)}
                      className="option-checkbox"
                    />
                    <span className="option-text">
                      Images & attachments
                      {imageCount > 0 && (
                        <span className="option-count">({imageCount})</span>
                      )}
                    </span>
                  </label>
                  <label className="option-item">
                    <input
                      type="checkbox"
                      checked={includeTimestamps}
                      onChange={(e) => setIncludeTimestamps(e.target.checked)}
                      className="option-checkbox"
                    />
                    <span className="option-text">Timestamps</span>
                  </label>
                </div>
              </div>

              {/* Summary */}
              <div className="export-summary">
                <span>{messages.length} messages</span>
                <span className="summary-dot">·</span>
                <span>{format.toUpperCase()} format</span>
              </div>
            </div>

            <div className="export-footer">
              <button onClick={onClose} className="export-cancel-btn">
                Cancel
              </button>
              <button
                onClick={handleExport}
                disabled={messages.length === 0}
                className="export-confirm-btn"
              >
                <Download className="w-4 h-4" />
                Export
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
