# Last Updated: 2025-12-03

## Purpose
Source root containing Next.js app, React components, custom hooks, state stores, types, and styles.

## Key Files
- `app/` - Next.js App Router pages (page.tsx, layout.tsx)
- `components/` - UI components (chat, ui primitives, upload)
- `hooks/` - Custom hooks (use-chat for SSE, message sending)
- `stores/` - Zustand stores (chat-store, session-store)
- `types/` - TypeScript interfaces (api.ts for Message, Session, SSEEvent)
- `lib/` - Utilities (utils.ts for cn helper)
- `styles/` - Global CSS (Tailwind)

## Dependencies/Relations
Entry point for frontend. Used by `frontend/` Next.js runtime.
