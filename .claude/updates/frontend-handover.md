# Frontend Update for Backend Engineer (Claude 4.5 Opus)

**From:** Gemini 3.0 (Frontend Engineer)
**Date:** December 3, 2025
**Status:** Frontend Implementation Complete ✅

I have completed the Next.js 16 / React 19 frontend implementation. It is fully aligned with the provided API contract. Here are the specific integration details you need to know to ensure the backend `Qwen3-VL` service connects seamlessly.

## 1. API Integration & Endpoints
I am targeting `http://localhost:8080/api/v1` by default.

### Session Management
- **Creation:** On first load, I call `POST /sessions` with body `{"metadata": {"client": "web"}}`.
- **Persistence:** I store the returned `id` in `localStorage` (via Zustand).
- **Headers:** Every subsequent request includes the header:
  ```http
  X-Session-ID: <session_uuid>
  ```

### Chat & Streaming (SSE)
I am using the **Streaming** endpoint (`POST /chat`) exclusively for user interactions.

**Request Format:**
I send JSON with the following structure. Note how I handle images:
```json
{
  "message": "User query here",
  "images": [
    {
      "data": "raw_base64_string_without_prefix" 
    }
  ]
}
```
*Implementation Note:* My code (`use-chat.ts`) strips the data URI prefix (e.g., `data:image/jpeg;base64,`) before sending. The backend should expect **raw base64 strings** in the `data` field, or handle validation if a prefix slips through (though I have logic to prevent it).

**Response Handling (SSE Events):**
I am listening for these specific event types:
- `thinking_delta`: Appended to the "Reasoning Process" collapsible UI block.
- `content_delta`: Appended to the main markdown assistant message.
- `error`: Displays a toast/error state to the user.
- `done`: Triggers final message consolidation (though I update the UI in real-time).

## 2. UI/UX Constraints Implemented
- **Image Limits:** The frontend enforces a max of **4 images** per message and **10MB** per file.
- **Thinking UI:** The UI expects the backend to separate reasoning from content. If `thinking_delta` is never sent, the "Reasoning Process" accordion will simply not appear.

## 3. Types Reference
I have defined the following TypeScript interfaces which essentially mirror your Pydantic models. Please ensure your responses match:

```typescript
export type SSEEventType = 
  | 'start' 
  | 'thinking_start' 
  | 'thinking_delta' 
  | 'thinking_end' 
  | 'content_start' 
  | 'content_delta' 
  | 'content_end' 
  | 'done' 
  | 'error';

export interface SSEEvent {
  type: SSEEventType;
  request_id?: string;
  content?: string; // Used for both thinking_delta and content_delta
  error?: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
  };
}
```

## 4. Handover
The frontend build is passing (`npm run build`) and linting is clean. I am ready to run `npm run dev` as soon as the backend is live at port `8080`.

**Action Item:** Please proceed with the Backend implementation as planned in `frolicking-booping-quilt.md`. No changes to the API contract are required from my side.
