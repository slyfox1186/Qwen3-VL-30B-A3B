/**
 * Export utilities for conversations.
 *
 * Supports:
 * - Markdown export with full formatting
 * - JSON export with all metadata
 * - PDF export using browser print
 */

import { Message } from '@/types/api';

export interface ExportOptions {
  format: 'markdown' | 'json' | 'pdf';
  includeThoughts: boolean;
  includeImages: boolean;
  includeTimestamps: boolean;
  sessionTitle?: string;
}

interface ExportResult {
  content: string;
  filename: string;
  mimeType: string;
}

/**
 * Format a date for export.
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format a date for filenames.
 */
function formatDateForFilename(dateStr?: string): string {
  const date = dateStr ? new Date(dateStr) : new Date();
  return date.toISOString().split('T')[0];
}

/**
 * Export conversation to Markdown format.
 */
export function exportToMarkdown(
  messages: Message[],
  options: ExportOptions
): ExportResult {
  const lines: string[] = [];
  const dateStr = formatDateForFilename(messages[0]?.created_at);
  const title = options.sessionTitle || 'Conversation';

  // Header
  lines.push(`# ${title}`);
  lines.push('');
  lines.push(`**Exported:** ${new Date().toLocaleString()}`);
  lines.push(`**Messages:** ${messages.length}`);
  lines.push('');
  lines.push('---');
  lines.push('');

  for (const msg of messages) {
    // Role header
    const role = msg.role === 'user' ? '👤 User' : '🤖 Assistant';
    lines.push(`## ${role}`);

    // Timestamp
    if (options.includeTimestamps && msg.created_at) {
      lines.push(`*${formatDate(msg.created_at)}*`);
    }
    lines.push('');

    // Thinking section
    if (options.includeThoughts && msg.thought) {
      lines.push('<details>');
      lines.push('<summary>💭 Thinking</summary>');
      lines.push('');
      lines.push('```');
      lines.push(msg.thought);
      lines.push('```');
      lines.push('');
      lines.push('</details>');
      lines.push('');
    }

    // Content
    lines.push(msg.content || '');
    lines.push('');

    // Images
    if (options.includeImages && msg.images && msg.images.length > 0) {
      lines.push('**Attached Images:**');
      msg.images.forEach((img, i) => {
        if (img.startsWith('data:')) {
          lines.push(`- Image ${i + 1}: (embedded data URL)`);
        } else {
          lines.push(`- ![Image ${i + 1}](${img})`);
        }
      });
      lines.push('');
    }

    // Search results
    if (msg.search_results && msg.search_results.length > 0) {
      lines.push('**Related Images:**');
      msg.search_results.forEach((result, i) => {
        if (result.title) {
          lines.push(`- [${result.title}](${result.link || result.thumbnail})`);
        } else {
          lines.push(`- [Image ${i + 1}](${result.link || result.thumbnail})`);
        }
      });
      lines.push('');
    }

    lines.push('---');
    lines.push('');
  }

  // Footer
  lines.push('');
  lines.push('---');
  lines.push('*Exported from Qwen3-VL Chat*');

  return {
    content: lines.join('\n'),
    filename: `${title.replace(/[^a-z0-9]/gi, '-').toLowerCase()}-${dateStr}.md`,
    mimeType: 'text/markdown',
  };
}

/**
 * Export conversation to JSON format.
 */
export function exportToJSON(
  messages: Message[],
  options: ExportOptions
): ExportResult {
  const dateStr = formatDateForFilename(messages[0]?.created_at);
  const title = options.sessionTitle || 'Conversation';

  const exportData = {
    title,
    exportedAt: new Date().toISOString(),
    messageCount: messages.length,
    options: {
      includeThoughts: options.includeThoughts,
      includeImages: options.includeImages,
      includeTimestamps: options.includeTimestamps,
    },
    messages: messages.map((msg) => ({
      id: msg.id,
      role: msg.role,
      content: msg.content,
      ...(options.includeThoughts && msg.thought ? { thought: msg.thought } : {}),
      ...(options.includeTimestamps && msg.created_at ? { created_at: msg.created_at } : {}),
      ...(options.includeImages && msg.images?.length ? { images: msg.images } : {}),
      ...(msg.search_results?.length ? { search_results: msg.search_results } : {}),
      ...(msg.search_query ? { search_query: msg.search_query } : {}),
    })),
  };

  return {
    content: JSON.stringify(exportData, null, 2),
    filename: `${title.replace(/[^a-z0-9]/gi, '-').toLowerCase()}-${dateStr}.json`,
    mimeType: 'application/json',
  };
}

/**
 * Generate HTML content for PDF export (uses browser print).
 */
export function generatePDFHTML(
  messages: Message[],
  options: ExportOptions
): string {
  const title = options.sessionTitle || 'Conversation';

  const styles = `
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        line-height: 1.6;
        color: #1a1a1a;
        padding: 2rem;
        max-width: 800px;
        margin: 0 auto;
      }
      h1 { font-size: 1.75rem; margin-bottom: 0.5rem; }
      .meta { color: #666; font-size: 0.875rem; margin-bottom: 2rem; }
      .message { margin-bottom: 1.5rem; padding: 1rem; border-radius: 0.5rem; }
      .message-user { background: #f0f4ff; border-left: 4px solid #4a6cf7; }
      .message-assistant { background: #f0fff4; border-left: 4px solid #22c55e; }
      .role { font-weight: 600; font-size: 0.875rem; margin-bottom: 0.5rem; }
      .role-user { color: #4a6cf7; }
      .role-assistant { color: #22c55e; }
      .timestamp { color: #888; font-size: 0.75rem; margin-bottom: 0.5rem; }
      .content { white-space: pre-wrap; }
      .thinking {
        background: #fff8dc;
        padding: 0.75rem;
        margin-top: 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.875rem;
        color: #666;
      }
      .thinking-label { font-weight: 600; color: #b8860b; margin-bottom: 0.25rem; }
      pre { background: #f4f4f4; padding: 0.5rem; border-radius: 0.25rem; overflow-x: auto; }
      code { font-family: 'Monaco', 'Consolas', monospace; font-size: 0.875rem; }
      .footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #eee; font-size: 0.75rem; color: #888; }
      @media print {
        body { padding: 0; }
        .message { break-inside: avoid; }
      }
    </style>
  `;

  const header = `
    <h1>${escapeHtml(title)}</h1>
    <div class="meta">
      Exported: ${new Date().toLocaleString()} · ${messages.length} messages
    </div>
  `;

  const messageHtml = messages
    .map((msg) => {
      const roleClass = msg.role === 'user' ? 'user' : 'assistant';
      const roleLabel = msg.role === 'user' ? '👤 User' : '🤖 Assistant';

      let html = `<div class="message message-${roleClass}">`;
      html += `<div class="role role-${roleClass}">${roleLabel}</div>`;

      if (options.includeTimestamps && msg.created_at) {
        html += `<div class="timestamp">${formatDate(msg.created_at)}</div>`;
      }

      html += `<div class="content">${escapeHtml(msg.content || '')}</div>`;

      if (options.includeThoughts && msg.thought) {
        html += `
          <div class="thinking">
            <div class="thinking-label">💭 Thinking</div>
            <pre><code>${escapeHtml(msg.thought)}</code></pre>
          </div>
        `;
      }

      html += '</div>';
      return html;
    })
    .join('\n');

  const footer = `
    <div class="footer">
      Exported from Qwen3-VL Chat
    </div>
  `;

  return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>${escapeHtml(title)}</title>
      ${styles}
    </head>
    <body>
      ${header}
      ${messageHtml}
      ${footer}
    </body>
    </html>
  `;
}

/**
 * Escape HTML special characters.
 */
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Download a file with the given content.
 */
export function downloadFile(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Open PDF in new window for printing.
 */
export function openPDFWindow(html: string): void {
  const printWindow = window.open('', '_blank');
  if (printWindow) {
    printWindow.document.write(html);
    printWindow.document.close();
    // Wait for content to load, then trigger print
    printWindow.onload = () => {
      printWindow.print();
    };
  }
}

/**
 * Export conversation with the specified format.
 */
export function exportConversation(
  messages: Message[],
  options: ExportOptions
): void {
  if (messages.length === 0) {
    console.warn('No messages to export');
    return;
  }

  switch (options.format) {
    case 'markdown': {
      const md = exportToMarkdown(messages, options);
      downloadFile(md.content, md.filename, md.mimeType);
      break;
    }
    case 'json': {
      const json = exportToJSON(messages, options);
      downloadFile(json.content, json.filename, json.mimeType);
      break;
    }
    case 'pdf': {
      const html = generatePDFHTML(messages, options);
      openPDFWindow(html);
      break;
    }
  }
}
