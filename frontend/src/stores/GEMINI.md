# Last Updated: 2025-12-03

## Purpose
Zustand state management stores for chat and session state.

## Key Files
- `chat-store.ts` - Chat state: messages[], isStreaming, currentThinking/Content (accumulators), currentSearchResults, error. Actions: addMessage, appendThinking/Content, setSearchResults, resetCurrentStream.
- `session-store.ts` - Session persistence: session object, setSession, clearSession, hasHydrated flag for SSR.

## Dependencies/Relations
Used by `hooks/use-chat`, `components/chat/`. Provides reactive state for UI updates.
