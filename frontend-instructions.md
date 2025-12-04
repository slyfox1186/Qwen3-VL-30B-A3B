# Frontend Enhancement Instructions

> **CRITICAL DIRECTIVE**: You are a TypeScript/CSS specialist. Your ONLY objective is to enhance the frontend code. You are STRICTLY FORBIDDEN from modifying any backend files. If you encounter backend issues, document them in `backend-critique.md` for human review.

---

## Table of Contents

1. [Absolute Constraints](#absolute-constraints)
2. [Project Overview](#project-overview)
3. [Technology Stack](#technology-stack)
4. [Architecture Overview](#architecture-overview)
5. [File-by-File Reference](#file-by-file-reference)
6. [Backend API Contract](#backend-api-contract)
7. [Styling System](#styling-system)
8. [State Management](#state-management)
9. [Enhancement Guidelines](#enhancement-guidelines)
10. [Quality Standards](#quality-standards)
11. [Backend Issue Reporting](#backend-issue-reporting)

---

## Absolute Constraints

### FORBIDDEN Actions

```
YOU MUST NEVER:
1. Modify ANY file in the /backend directory
2. Change ANY Python file (.py)
3. Alter backend API endpoints, schemas, or logic
4. Modify requirements.txt or any backend configuration
5. Suggest "quick fixes" to backend code
6. Create new backend routes or services
7. Touch anything in /backend/app, /backend/scripts, or /backend/tests
```

### REQUIRED Actions

```
YOU MUST ALWAYS:
1. Work EXCLUSIVELY within /frontend directory
2. Document backend issues in /backend-critique.md (create if needed)
3. Create dedicated CSS files for every TSX component
4. Run `npm run lint` after every change
5. Maintain TypeScript strict mode compliance
6. Preserve existing API contracts exactly as defined
7. Use the cn() utility for all className compositions
```

### If You Encounter Backend Issues

When you discover a backend problem (API returning wrong data, missing endpoints, incorrect schemas, performance issues), you MUST:

1. **STOP** - Do not attempt to fix it
2. **DOCUMENT** - Add detailed entry to `backend-critique.md`
3. **WORKAROUND** - Implement frontend-only defensive handling if possible
4. **CONTINUE** - Resume frontend work

---

## Project Overview

**Qwen3-VL Chat** is a vision-language model chat interface featuring:
- Real-time SSE streaming for AI responses
- Multimodal input (text + images)
- Image search results display
- Theme switching (light/dark/system)
- Message editing and regeneration
- Session management with history

### Directory Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # Root layout, fonts, ThemeProvider
│   │   └── page.tsx            # Home page → ChatContainer
│   │
│   ├── components/
│   │   ├── chat/               # Chat interface components
│   │   │   ├── AIMessage.tsx
│   │   │   ├── ChatContainer.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── ImageViewer.tsx
│   │   │   ├── MarkdownItRenderer.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── QwenLogo.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── UserMessage.tsx
│   │   │
│   │   ├── theme/              # Theme system
│   │   │   ├── index.ts
│   │   │   ├── ThemeProvider.tsx
│   │   │   └── ThemeToggle.tsx
│   │   │
│   │   ├── ui/                 # Radix UI primitives (shadcn)
│   │   │   ├── avatar.tsx
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── collapsible.tsx
│   │   │   ├── CopyButton.tsx
│   │   │   ├── input.tsx
│   │   │   ├── scroll-area.tsx
│   │   │   ├── sheet.tsx
│   │   │   ├── skeleton.tsx
│   │   │   ├── textarea.tsx
│   │   │   └── tooltip.tsx
│   │   │
│   │   └── upload/             # Upload components (placeholder)
│   │
│   ├── hooks/
│   │   └── use-chat.ts         # Core chat logic, SSE handling
│   │
│   ├── lib/
│   │   ├── title-utils.ts      # Title generation utility
│   │   └── utils.ts            # cn() helper
│   │
│   ├── stores/                 # Zustand state management
│   │   ├── chat-store.ts       # Messages, streaming state
│   │   ├── session-store.ts    # Session persistence
│   │   ├── theme-store.ts      # Theme preferences
│   │   └── ui-store.ts         # UI state (sidebar)
│   │
│   ├── styles/
│   │   ├── components/         # Component-specific CSS
│   │   │   ├── ai-message.css
│   │   │   ├── chat-container.css
│   │   │   ├── chat-input.css
│   │   │   ├── copy-button.css
│   │   │   ├── image-viewer.css
│   │   │   ├── message-list.css
│   │   │   ├── sidebar.css
│   │   │   └── user-message.css
│   │   ├── globals.css         # CSS variables, theme definitions
│   │   ├── index.css           # Main entry, imports all CSS
│   │   └── markdown-it-renderer.css
│   │
│   └── types/
│       └── api.ts              # TypeScript interfaces for API
│
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.ts
└── eslint.config.mjs
```

---

## Technology Stack

| Category | Technology | Version | Purpose |
|----------|------------|---------|---------|
| Framework | Next.js | 16.0.7 | React framework with App Router |
| React | React | 19.2.0 | UI library |
| State | Zustand | 5.0.9 | State management with persist |
| Styling | Tailwind CSS | 4.x | Utility-first CSS |
| Animation | Framer Motion | 12.x | Animations and transitions |
| UI Primitives | Radix UI | Various | Accessible components |
| Markdown | markdown-it | 14.1.0 | Markdown parsing |
| Syntax | highlight.js | 11.x | Code highlighting |
| Sanitization | DOMPurify | 3.3.0 | HTML sanitization |
| Icons | Lucide React | 0.555.0 | Icon library |
| Notifications | Sonner | 2.0.7 | Toast notifications |
| HTTP | Fetch API | Native | API communication |

---

## Architecture Overview

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐ │
│  │   Stores     │────▶│    Hooks     │────▶│   Components     │ │
│  │  (Zustand)   │◀────│  (use-chat)  │◀────│   (React)        │ │
│  └──────────────┘     └──────────────┘     └──────────────────┘ │
│         │                    │                                   │
│         │                    │                                   │
│         ▼                    ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    fetch() + SSE                            ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
└──────────────────────────────│───────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BACKEND (DO NOT MODIFY)                        │
│                   http://localhost:8080/api/v1                   │
└─────────────────────────────────────────────────────────────────┘
```

### Component Hierarchy

```
RootLayout (layout.tsx)
└── ThemeProvider
    └── Page (page.tsx)
        └── ChatContainer
            ├── Sidebar
            │   └── Session list + New chat button
            ├── Header
            │   ├── ThemeToggle
            │   └── Session badge
            ├── MessageList
            │   ├── UserMessage (multiple)
            │   │   └── Edit mode / View mode
            │   ├── AIMessage (multiple)
            │   │   ├── MarkdownItRenderer
            │   │   ├── ImageViewer
            │   │   └── Regenerate button
            │   └── QwenLogo (empty state)
            └── ChatInput
                └── Image upload + Send button
```

---

## File-by-File Reference

### App Layer

#### `src/app/layout.tsx`
**Purpose**: Root layout with fonts, metadata, and providers

**Key Elements**:
- Geist Sans/Mono fonts via next/font
- ThemeProvider wrapper for theme management
- Sonner Toaster for notifications
- Anti-FOUC inline script for theme initialization

**Backend Relationship**: None directly

**Enhancement Opportunities**:
- Add SEO meta tags
- Implement loading states
- Add error boundaries

---

#### `src/app/page.tsx`
**Purpose**: Home page rendering the chat interface

**Content**: Simply renders `<ChatContainer />`

**Enhancement Opportunities**:
- Add suspense boundaries
- Implement route-based loading

---

### Chat Components

#### `src/components/chat/ChatContainer.tsx`
**Purpose**: Main orchestrator for the chat interface

**State Dependencies**:
- `useChat()` hook for messaging
- `useSessionStore` for session management
- `useUIStore` for sidebar state

**Backend Endpoints Used**:
- `DELETE /sessions/{id}` - Delete conversation
- `POST /images/proxy` - Proxy image fetches (CORS bypass)

**Props Passed Down**:
- MessageList: messages, streaming state, edit handlers
- ChatInput: send handler, streaming state
- Sidebar: session data, new chat handler

**Enhancement Opportunities**:
- Add keyboard shortcut hints overlay
- Implement connection status indicator improvements
- Add message search functionality

---

#### `src/components/chat/MessageList.tsx`
**Purpose**: Renders message history and streaming message

**Props**:
```typescript
interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
  currentContent: string;
  currentSearchResults?: SearchResult[];
  currentSearchQuery?: string;
  onImageReview?: (imageUrl: string) => void;
  editingMessageId: string | null;
  onEditMessage?: (messageId: string) => void;
  onSaveEdit?: (messageId: string, content: string, images: string[]) => void;
  onCancelEdit?: () => void;
  onRegenerate?: (messageId: string) => void;
}
```

**Key Behaviors**:
- Auto-scrolls on new content
- Dynamically keys UserMessage for edit state reset
- Shows QwenLogo for empty state

**CSS File**: `styles/components/message-list.css`

---

#### `src/components/chat/UserMessage.tsx`
**Purpose**: Displays user messages with edit capability

**Features**:
- Inline edit mode with textarea
- Image grid for attached images
- Copy button for message content
- Keyboard shortcuts (Ctrl+Enter save, Esc cancel)

**Props**:
```typescript
interface UserMessageProps {
  message: Message;
  isEditing?: boolean;
  isStreaming?: boolean;
  onEdit?: (messageId: string) => void;
  onSaveEdit?: (messageId: string, content: string, images: string[]) => void;
  onCancelEdit?: () => void;
}
```

**CSS File**: `styles/components/user-message.css`

**Enhancement Opportunities**:
- Add image removal during edit
- Implement drag-to-reorder images
- Add character count indicator

---

#### `src/components/chat/AIMessage.tsx`
**Purpose**: Displays AI responses with markdown rendering

**Features**:
- Markdown rendering via MarkdownItRenderer
- Copy button for full response
- Regenerate button (visible on hover)
- Image search results via ImageViewer
- Loading dots animation during streaming

**Props**:
```typescript
interface AIMessageProps {
  message: Message;
  isStreaming?: boolean;
  isGlobalStreaming?: boolean;
  onImageReview?: (imageUrl: string) => void;
  onRegenerate?: (messageId: string) => void;
}
```

**CSS File**: `styles/components/ai-message.css`

**Enhancement Opportunities**:
- Add response rating (thumbs up/down)
- Implement copy code blocks individually
- Add "read aloud" functionality

---

#### `src/components/chat/ChatInput.tsx`
**Purpose**: Message input with image upload

**Features**:
- Auto-resizing textarea
- Image paste/drop support
- Image preview with removal
- Send button with loading state
- Stop generation button

**Backend Relationship**: Images sent as base64 in chat request

**CSS File**: `styles/components/chat-input.css`

**Enhancement Opportunities**:
- Add voice input
- Implement prompt templates/suggestions
- Add file attachment support

---

#### `src/components/chat/MarkdownItRenderer.tsx`
**Purpose**: Renders markdown with syntax highlighting

**Features**:
- markdown-it parsing with HTML support
- highlight.js for code blocks
- DOMPurify sanitization
- Injected copy buttons on code blocks
- External link handling (target="_blank")

**CSS File**: `styles/markdown-it-renderer.css`

**Enhancement Opportunities**:
- Add line numbers to code blocks
- Implement collapsible long code blocks
- Add mermaid diagram support

---

#### `src/components/chat/ImageViewer.tsx`
**Purpose**: Displays image search results in a modal grid

**Features**:
- Lightbox modal for full-size viewing
- Grid layout with hover effects
- "Review with AI" button for each image
- Thumbnail fallback handling

**CSS File**: `styles/components/image-viewer.css`

**Enhancement Opportunities**:
- Add image zoom/pan
- Implement keyboard navigation
- Add download button

---

#### `src/components/chat/Sidebar.tsx`
**Purpose**: Session list and navigation

**Features**:
- Session history list
- Inline title editing
- New chat button
- Session deletion
- Collapsible on mobile

**CSS File**: `styles/components/sidebar.css`

**Enhancement Opportunities**:
- Add session search/filter
- Implement session grouping by date
- Add session export

---

#### `src/components/chat/QwenLogo.tsx`
**Purpose**: Animated logo for empty state

**Enhancement Opportunities**:
- Add interactive hover effects
- Implement typing suggestions below logo

---

### Theme Components

#### `src/components/theme/ThemeProvider.tsx`
**Purpose**: Applies theme class to document root

**Behavior**:
- Listens to system preference changes
- Syncs resolved theme to document.documentElement
- Provides theme context (if needed)

---

#### `src/components/theme/ThemeToggle.tsx`
**Purpose**: Theme cycling button

**Cycle**: Light → Dark → System → Light

**Icons**: Sun (light), Moon (dark), Monitor (system)

---

### UI Components (Radix-based)

All UI components in `src/components/ui/` follow shadcn/ui patterns:

| Component | Base | Purpose |
|-----------|------|---------|
| `avatar.tsx` | @radix-ui/react-avatar | User/AI avatars |
| `button.tsx` | Native + CVA | Action buttons |
| `card.tsx` | Native | Card containers |
| `collapsible.tsx` | @radix-ui/react-collapsible | Expandable sections |
| `CopyButton.tsx` | Custom | Copy to clipboard |
| `input.tsx` | Native | Text inputs |
| `scroll-area.tsx` | @radix-ui/react-scroll-area | Custom scrollbars |
| `sheet.tsx` | @radix-ui/react-dialog | Slide-out panels |
| `skeleton.tsx` | Native | Loading placeholders |
| `textarea.tsx` | Native | Multi-line inputs |
| `tooltip.tsx` | @radix-ui/react-tooltip | Hover tooltips |

**Modification Guidelines**:
- Preserve variant system (CVA patterns)
- Maintain accessibility attributes
- Use cn() for all className compositions

---

### Hooks

#### `src/hooks/use-chat.ts`
**Purpose**: Core chat functionality and API communication

**Exports**:
```typescript
{
  sendMessage: (content: string, images?: string[]) => Promise<void>;
  stopGeneration: () => void;
  loadHistory: (sessionId: string) => Promise<boolean>;
  clearMessages: () => void;
  editMessage: (messageId: string, content: string, images?: string[]) => Promise<void>;
  regenerateResponse: (messageId: string) => Promise<void>;
  messages: Message[];
  isStreaming: boolean;
  currentContent: string;
  currentSearchResults?: SearchResult[];
  currentSearchQuery?: string;
  editingMessageId: string | null;
  setEditingMessageId: (id: string | null) => void;
  error: string | null;
}
```

**Backend Endpoints Used**:
- `POST /chat` - SSE streaming chat
- `POST /chat/regenerate` - Regenerate AI response
- `GET /sessions/{id}/history` - Load message history
- `POST /sessions/{id}/history/truncate` - Truncate for edit

**SSE Event Types Handled**:
- `content_delta` - Streaming text chunks
- `images` - Image search results
- `error` - Error messages
- `done` - Stream completion

**Enhancement Opportunities**:
- Add retry logic for failed requests
- Implement optimistic updates
- Add request queuing

---

### Stores

#### `src/stores/chat-store.ts`
**State**:
```typescript
interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentContent: string;
  currentSearchResults?: SearchResult[];
  currentSearchQuery?: string;
  error: string | null;
  editingMessageId: string | null;
}
```

**Actions**: addMessage, setMessages, appendContent, setSearchResults, resetCurrentStream, removeMessagesFrom

---

#### `src/stores/session-store.ts`
**State**:
```typescript
interface SessionState {
  session: Session | null;
  sessions: Session[];
  isLoading: boolean;
  error: string | null;
  hasHydrated: boolean;
  isCreating: boolean;
}
```

**Persistence**: localStorage via `session-storage` key

**Backend Endpoints Used**:
- `POST /sessions` - Create session
- `PATCH /sessions/{id}` - Update metadata/title

---

#### `src/stores/theme-store.ts`
**State**:
```typescript
interface ThemeState {
  theme: 'light' | 'dark' | 'system';
  resolvedTheme: 'light' | 'dark';
}
```

**Persistence**: localStorage via `theme-storage` key

---

#### `src/stores/ui-store.ts`
**State**:
```typescript
interface UIState {
  isSidebarOpen: boolean;
  hasHydrated: boolean;
}
```

**Persistence**: localStorage via `ui-storage` key

---

### Types

#### `src/types/api.ts`
**Interfaces**:
```typescript
interface Session {
  id: string;
  user_id?: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  metadata?: Record<string, unknown>;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  images?: string[];
  search_results?: SearchResult[];
  search_query?: string;
  created_at: string;
}

interface SearchResult {
  title: string;
  link: string;
  thumbnail?: string;
  original_image?: string;
  snippet?: string;
}

interface SSEEvent {
  type: SSEEventType;
  request_id?: string;
  content?: string;
  images?: SearchResult[];
  query?: string;
  error?: string;
  code?: string;
}

type SSEEventType = 'start' | 'content_start' | 'content_delta' |
                    'content_end' | 'images' | 'done' | 'error';
```

**IMPORTANT**: These types MUST match backend schemas exactly. Do not modify without backend alignment.

---

### Utilities

#### `src/lib/utils.ts`
```typescript
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

**Usage**: ALL className compositions must use cn()

---

#### `src/lib/title-utils.ts`
```typescript
export function generateTitleFromMessage(message: string): string
```

**Purpose**: Auto-generate conversation titles from first message

---

## Backend API Contract

### Base URL
```
NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1'
```

### Endpoints Used by Frontend

| Method | Endpoint | Purpose | Used In |
|--------|----------|---------|---------|
| POST | `/sessions` | Create new session | session-store.ts |
| GET | `/sessions/{id}` | Get session details | (indirect) |
| PATCH | `/sessions/{id}` | Update session metadata | session-store.ts |
| DELETE | `/sessions/{id}` | Delete session | ChatContainer.tsx |
| GET | `/sessions/{id}/history` | Load chat history | use-chat.ts |
| POST | `/sessions/{id}/history/truncate` | Truncate for editing | use-chat.ts |
| POST | `/chat` | Send message (SSE stream) | use-chat.ts |
| POST | `/chat/regenerate` | Regenerate AI response | use-chat.ts |
| POST | `/images/proxy` | Proxy external images | ChatContainer.tsx |

### Request Headers
```typescript
{
  'Content-Type': 'application/json',
  'X-Session-ID': sessionId  // Required for /chat endpoints
}
```

### SSE Stream Format
```
data: {"type": "content_delta", "content": "Hello"}

data: {"type": "images", "images": [...], "query": "..."}

data: {"type": "done"}
```

---

## Styling System

### CSS Architecture

```
styles/
├── index.css              # Entry point, imports all
├── globals.css            # CSS variables, theme colors
├── markdown-it-renderer.css
└── components/            # One CSS file per component
    ├── ai-message.css
    ├── chat-container.css
    ├── chat-input.css
    ├── copy-button.css
    ├── image-viewer.css
    ├── message-list.css
    ├── sidebar.css
    └── user-message.css
```

### Theme Variables (globals.css)

```css
:root {
  --background: ...;
  --foreground: ...;
  --primary: ...;
  --primary-foreground: ...;
  --secondary: ...;
  --muted: ...;
  --accent: ...;
  --border: ...;
  --ring: ...;
  /* ... more semantic tokens */
}

.dark {
  /* Dark mode overrides */
}
```

### Styling Rules

1. **Every TSX file MUST have a corresponding CSS file**
2. **Use Tailwind @apply in CSS files, not inline styles**
3. **Use semantic class names matching component structure**
4. **Use CSS variables for all colors (never hardcode)**
5. **Include dark mode variants where needed**
6. **Group related styles with comments**

### Example Pattern
```css
/* styles/components/my-component.css */

.my-component-container {
  @apply flex flex-col gap-4 p-4;
}

.my-component-header {
  @apply text-lg font-semibold text-foreground;
}

.my-component-content {
  @apply bg-background border border-border rounded-lg;
}
```

---

## State Management

### Store Patterns

```typescript
// Standard Zustand store with persist
export const useMyStore = create<MyState>()(
  persist(
    (set, get) => ({
      // State
      value: initialValue,

      // Actions
      setValue: (value) => set({ value }),

      // Async actions
      fetchData: async () => {
        set({ isLoading: true });
        try {
          const data = await fetch(...);
          set({ data, isLoading: false });
        } catch (error) {
          set({ error: error.message, isLoading: false });
        }
      },
    }),
    {
      name: 'storage-key',
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);
```

### Hydration Handling

All persisted stores include `hasHydrated` flag. Components must check this before rendering persisted state:

```typescript
const { session, hasHydrated } = useSessionStore();

useEffect(() => {
  if (!hasHydrated) return;
  // Safe to use persisted state
}, [hasHydrated]);
```

---

## Enhancement Guidelines

### Before Making Changes

1. **Read the entire file** - Understand existing patterns
2. **Check CSS file** - Ensure styling file exists
3. **Verify types** - Don't break TypeScript contracts
4. **Check dependencies** - Understand component relationships

### Change Checklist

- [ ] TypeScript compiles without errors
- [ ] ESLint passes without warnings
- [ ] CSS file created/updated for component
- [ ] cn() used for all className compositions
- [ ] Dark mode variants included where needed
- [ ] Accessibility attributes preserved
- [ ] No hardcoded colors (use CSS variables)
- [ ] No inline styles (use CSS files)
- [ ] Animation uses Framer Motion patterns
- [ ] State updates follow Zustand patterns

### Performance Considerations

1. **Memoization** - Use React.memo for expensive components
2. **Callbacks** - Use useCallback for handler props
3. **Selectors** - Use Zustand selectors for partial state
4. **Keys** - Use stable, unique keys for lists
5. **Lazy loading** - Consider dynamic imports for heavy components

---

## Quality Standards

### TypeScript

- Strict mode enabled (tsconfig.json)
- Explicit return types for functions
- Interface over type for objects
- No `any` types (use `unknown` if needed)
- Proper generic constraints

### React

- Functional components only
- Hooks follow rules of hooks
- No prop drilling beyond 2 levels (use context/stores)
- Error boundaries for critical sections
- Suspense boundaries for async operations

### CSS

- BEM-like naming with component prefixes
- Mobile-first responsive design
- Consistent spacing scale (Tailwind)
- Accessible color contrast ratios
- Smooth transitions (150-300ms)

### Accessibility

- Semantic HTML elements
- ARIA labels where needed
- Keyboard navigation support
- Focus indicators visible
- Screen reader friendly

---

## Backend Issue Reporting

### When to Report

Report to `backend-critique.md` when you encounter:

1. **API returning unexpected data** - Wrong types, missing fields
2. **Missing endpoints** - Features that need backend support
3. **Performance issues** - Slow responses, timeouts
4. **Error handling gaps** - Unclear error messages
5. **Security concerns** - Potential vulnerabilities
6. **Schema mismatches** - Frontend types don't match API

### Report Format

Create or append to `/backend-critique.md`:

```markdown
## Issue: [Brief Title]

**Date**: YYYY-MM-DD
**Severity**: Critical | High | Medium | Low
**Component**: [Frontend file that encountered issue]

### Description
[Detailed description of the issue]

### Expected Behavior
[What should happen]

### Actual Behavior
[What actually happens]

### API Endpoint
[Affected endpoint, if applicable]

### Request/Response Sample
```json
// Sample request
{ ... }

// Sample response (or error)
{ ... }
```

### Frontend Workaround
[How frontend is handling this, if at all]

### Suggested Backend Fix
[Non-binding suggestion for backend team]

---
```

### Example Entry

```markdown
## Issue: Session history missing pagination metadata

**Date**: 2025-12-03
**Severity**: Medium
**Component**: src/hooks/use-chat.ts

### Description
The GET `/sessions/{id}/history` endpoint returns messages but doesn't include
total count or pagination info in a consistent location.

### Expected Behavior
Response should include `total`, `limit`, `offset` at top level.

### Actual Behavior
Pagination info is sometimes missing or nested inconsistently.

### Frontend Workaround
Currently loading all messages and handling pagination client-side.

### Suggested Backend Fix
Standardize response format:
```json
{
  "messages": [...],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

---
```

---

## Quick Reference

### Commands

```bash
# Development
cd frontend && npm run dev

# Linting
cd frontend && npm run lint

# Build
cd frontend && npm run build

# Full project lint (from root)
python3 run_linter.py
```

### File Creation Template

When creating a new component:

1. Create `src/components/[area]/MyComponent.tsx`
2. Create `src/styles/components/my-component.css`
3. Add import to `src/styles/index.css`
4. Export from `src/components/[area]/index.ts` (if exists)

### Import Order

```typescript
// 1. React
import React, { useState, useEffect } from 'react';

// 2. External libraries
import { motion } from 'framer-motion';
import { SomeIcon } from 'lucide-react';

// 3. Internal components
import { Button } from '@/components/ui/button';

// 4. Hooks and stores
import { useChat } from '@/hooks/use-chat';
import { useChatStore } from '@/stores/chat-store';

// 5. Types
import { Message } from '@/types/api';

// 6. Utilities
import { cn } from '@/lib/utils';
```

---

## Final Reminder

```
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   YOUR SOLE OBJECTIVE: ENHANCE FRONTEND CODE                    ║
║                                                                  ║
║   ✓ Modify files in /frontend                                   ║
║   ✓ Create CSS files for components                             ║
║   ✓ Improve TypeScript types and patterns                       ║
║   ✓ Enhance UI/UX and accessibility                             ║
║   ✓ Document backend issues in backend-critique.md              ║
║                                                                  ║
║   ✗ NEVER touch /backend directory                              ║
║   ✗ NEVER modify Python files                                   ║
║   ✗ NEVER change API contracts                                  ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```
