# Last Updated: 2025-12-06

## Purpose
Chat interface components for message display, input, streaming, and session management.

## Key Files
- `ChatContainer.tsx` - Main container with session init, sidebar toggle, header, message list, input area
- `MessageList.tsx` - Renders message history + current streaming message with thinking/content
- `ChatInput.tsx` - Textarea with send/stop buttons, keyboard shortcuts
- `AIMessage.tsx` - Assistant message with thinking collapsible, markdown content, search results
- `UserMessage.tsx` - User message with text content
- `Sidebar.tsx` - Session list, new chat button, settings

## Dependencies/Relations
Used by `app/page.tsx`. Depends on `hooks/use-chat`, `stores/chat-store`, `stores/session-store`, `ui/` components.
