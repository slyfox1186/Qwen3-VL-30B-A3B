'use client';

import React, { useMemo, useEffect, useSyncExternalStore, useRef, useCallback } from 'react';
import markdownIt from 'markdown-it';
import hljs from 'highlight.js';
import DOMPurify from 'dompurify';
import 'highlight.js/styles/atom-one-dark.css';
import '@/styles/markdown-it-renderer.css';

interface MarkdownItRendererProps {
  content: string;
  className?: string;
}

function subscribe() {
  return () => {};
}

// SVG icons as strings for injection into HTML
const copyIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
const checkIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="text-green-500"><polyline points="20 6 9 17 4 12"/></svg>`;

export default function MarkdownItRenderer({ content, className }: MarkdownItRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const isMounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false
  );

  // Handle copy button clicks
  const handleCopyClick = useCallback(async (button: HTMLButtonElement) => {
    const rawCode = button.getAttribute('data-code');
    if (!rawCode) return;
    const code = decodeURIComponent(rawCode);

    try {
      let copied = false;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(code);
        copied = true;
      } else {
        // Fallback for environments where navigator.clipboard is undefined
        const textArea = document.createElement('textarea');
        textArea.value = code;
        
        // Ensure the textarea is not visible but part of the DOM
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        textArea.style.top = '0';
        
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
          copied = document.execCommand('copy');
          if (!copied) {
             console.error('Fallback: Copying text command was unsuccessful');
          }
        } catch (err) {
          console.error('Fallback: Oops, unable to copy', err);
        }
        
        document.body.removeChild(textArea);
      }

      if (copied) {
        button.innerHTML = checkIcon;
        button.classList.add('copied');
        setTimeout(() => {
          button.innerHTML = copyIcon;
          button.classList.remove('copied');
        }, 2000);
      }
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }, []);

  // Attach click handlers to copy buttons after render
  useEffect(() => {
    if (!isMounted || !containerRef.current) return;

    const buttons = containerRef.current.querySelectorAll('.code-copy-btn');
    const handleClick = (e: Event) => {
      e.preventDefault();
      e.stopPropagation();
      handleCopyClick(e.currentTarget as HTMLButtonElement);
    };

    buttons.forEach((btn) => {
      btn.addEventListener('click', handleClick);
    });

    return () => {
      buttons.forEach((btn) => {
        btn.removeEventListener('click', handleClick);
      });
    };
  }, [isMounted, content, handleCopyClick]);

  useEffect(() => {
    if (isMounted) {
      // Configure DOMPurify hooks once on client
      DOMPurify.addHook('afterSanitizeAttributes', function (node) {
        if ('target' in node) {
          node.setAttribute('target', '_blank');
          node.setAttribute('rel', 'noopener noreferrer');
        }
      });
    }
  }, [isMounted]);

  const md = useMemo(() => {
    return markdownIt({
      html: true,
      breaks: true,
      linkify: true,
      typographer: true,
      highlight: function (str, lang) {
        // Encode the code for the data attribute
        const encodedCode = encodeURIComponent(str);
        const langDisplay = lang || 'text';

        const header = `<div class="code-block-header"><span class="code-language-badge">${langDisplay}</span><button class="code-copy-btn" data-code="${encodedCode}" title="Copy code">${copyIcon}</button></div>`;

        if (lang && hljs.getLanguage(lang)) {
          try {
            const highlighted = hljs.highlight(str, { language: lang, ignoreIllegals: true }).value;
            return `<div class="code-block-wrapper">${header}<pre class="hljs language-${lang}"><code>${highlighted}</code></pre></div>`;
          } catch {
            // Ignore error
          }
        }

        return `<div class="code-block-wrapper">${header}<pre class="hljs"><code>${markdownIt().utils.escapeHtml(str)}</code></pre></div>`;
      }
    });
  }, []);

  const html = useMemo(() => {
    if (!isMounted) return '';

    const rawHTML = md.render(content);
    return DOMPurify.sanitize(rawHTML, {
      ADD_ATTR: [
        'target', 'data-code', 'class', 
        'viewBox', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 
        'x', 'y', 'rx', 'ry', 'd', 'width', 'height', 'xmlns', 'points'
      ],
      ADD_TAGS: ['button', 'svg', 'rect', 'path', 'polyline'],
      FORBID_TAGS: ['style', 'script'],
    });
  }, [content, md, isMounted]);

  if (!isMounted) {
    return <div className={`markdown-body ${className || ''}`} />;
  }

  return (
    <div
      ref={containerRef}
      className={`markdown-body ${className || ''}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}