'use client';

import React from 'react';
import { StreamProgress } from '@/stores/chat-store';
import '@/styles/components/stream-progress.css';

interface StreamProgressBarProps {
  progress: StreamProgress;
  isCancelling: boolean;
}

export default function StreamProgressBar({ progress, isCancelling }: StreamProgressBarProps) {
  const { tokensGenerated, maxTokens, tokensPerSecond, etaSeconds, percentage } = progress;

  const formatETA = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  return (
    <div className={`stream-progress ${isCancelling ? 'cancelling' : ''}`}>
      <div className="progress-bar-container">
        <div
          className="progress-bar-fill"
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      <div className="progress-stats">
        <span className="progress-tokens">
          {tokensGenerated.toLocaleString()}/{maxTokens.toLocaleString()} tokens
        </span>
        <span className="progress-separator">|</span>
        <span className="progress-speed">{tokensPerSecond.toFixed(1)} tok/s</span>
        {etaSeconds > 0 && (
          <>
            <span className="progress-separator">|</span>
            <span className="progress-eta">~{formatETA(etaSeconds)}</span>
          </>
        )}
      </div>
    </div>
  );
}
