# Last Updated: 2025-12-03

## Purpose
Custom React hooks for chat functionality and API integration.

## Key Files
- `use-chat.ts` - Main chat hook: sendMessage (SSE streaming), stopGeneration, loadHistory, clearMessages. Parses SSE events (thinking_delta, content_delta, images, error, done), updates chat store, manages AbortController.

## Dependencies/Relations
Used by `components/chat/ChatContainer.tsx`. Depends on `stores/chat-store`, `stores/session-store`, `types/api`.
