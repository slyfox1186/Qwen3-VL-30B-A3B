'use client';

import React from 'react';
import { motion } from 'framer-motion';

export default function QwenLogo({ className }: { className?: string }) {
  return (
    <div className={`qwen-logo-container ${className || ''}`}>
      <svg
        viewBox="0 0 400 400"
        className="w-full h-full max-w-[500px] max-h-[500px]"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="qwen-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--token-color-primary)" />
            <stop offset="50%" stopColor="#a855f7" /> {/* Purple/Violet accent */}
            <stop offset="100%" stopColor="#3b82f6" /> {/* Blue accent */}
          </linearGradient>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="10" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <radialGradient id="core-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--token-color-primary)" stopOpacity="0.4" />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
        </defs>

        {/* Outer rotating rings */}
        <motion.g
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: "200px 200px" }}
        >
          <circle cx="200" cy="200" r="180" stroke="url(#qwen-gradient)" strokeWidth="2" strokeOpacity="0.2" strokeDasharray="20 20" />
        </motion.g>
        
        <motion.g
          animate={{ rotate: -360 }}
          transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: "200px 200px" }}
        >
          <circle cx="200" cy="200" r="160" stroke="url(#qwen-gradient)" strokeWidth="1" strokeOpacity="0.3" strokeDasharray="40 40" />
        </motion.g>

        {/* Central Geometric Structure - Abstract Q / Eye */}
        <motion.g
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 1, ease: "easeOut" }}
        >
             {/* Background Glow */}
            <circle cx="200" cy="200" r="100" fill="url(#core-glow)" />

            {/* Main Shape */}
            <path
              d="M200 80 L270 140 L270 260 L200 320 L130 260 L130 140 Z"
              stroke="url(#qwen-gradient)"
              strokeWidth="4"
              fill="none"
              filter="url(#glow)"
            />
            
            {/* Inner details */}
            <path
              d="M200 110 L240 150 L240 250 L200 290 L160 250 L160 150 Z"
              stroke="var(--token-color-text)"
              strokeWidth="1"
              strokeOpacity="0.5"
              fill="none"
            />
            
            {/* Central "Core" */}
            <motion.circle
                cx="200"
                cy="200"
                r="20"
                fill="url(#qwen-gradient)"
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            />
            
             {/* "Q" stylized tail */}
            <motion.path
                d="M240 250 L280 290"
                stroke="url(#qwen-gradient)"
                strokeWidth="8"
                strokeLinecap="round"
                filter="url(#glow)"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ delay: 0.5, duration: 1 }}
            />
        </motion.g>

        {/* Floating Particles */}
        {[...Array(6)].map((_, i) => (
             <motion.circle
                key={i}
                r="3"
                fill="url(#qwen-gradient)"
                initial={{ x: 200, y: 200 }}
                animate={{
                    x: 200 + Math.cos(i * 60 * (Math.PI / 180)) * 120,
                    y: 200 + Math.sin(i * 60 * (Math.PI / 180)) * 120,
                    opacity: [0, 1, 0]
                }}
                transition={{
                    duration: 3,
                    repeat: Infinity,
                    delay: i * 0.2,
                    ease: "easeInOut"
                }}
             />
        ))}
      </svg>
      
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1, duration: 0.8 }}
        className="qwen-logo-text-wrapper"
      >
        <h1 className="qwen-logo-title">
          QWEN 3
        </h1>
        <p className="qwen-logo-subtitle">
          Visual Language Intelligence
        </p>
      </motion.div>
    </div>
  );
}
