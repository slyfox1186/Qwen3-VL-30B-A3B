# Last Updated: 2025-12-04

## Purpose
Zustand state management stores for chat, session, UI, theme, and search state.

## Key Files
- `chat-store.ts` - Chat state: messages[], isStreaming, currentThinking/Content (accumulators), currentSearchResults, error. Actions: addMessage, appendThinking/Content, setSearchResults, resetCurrentStream.
- `session-store.ts` - Session persistence: session object, setSession, clearSession, hasHydrated flag for SSR.
- `ui-store.ts` - UI state: isSidebarOpen, toggleSidebar, setSidebarOpen. Persisted to localStorage.
- `theme-store.ts` - Theme state: theme (light/dark/system), resolvedTheme, colorTheme. Persisted to localStorage.
- `search-store.ts` - Search state: isOpen, filters, results, isSearching, recentSearches. Actions: open, close, performSearch, setFilters.

## Dependencies/Relations
Used by `hooks/use-chat`, `hooks/use-search`, `components/chat/`. Provides reactive state for UI updates.
