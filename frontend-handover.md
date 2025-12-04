# Issue: Thinking Process and Response Merged in UI

## Goal
The objective is to separate the LLM's internal "thought process" (enclosed in `<think>` tags) from its final "response" content. 
- **Thinking Process**: Should be displayed in a separate, collapsible "Thinking Bubble" component, distinct from the main response.
- **Final Response**: Should be displayed in the standard chat bubble (`ai-prose-container`).
- **Visuals**: They must be visually distinct (different backgrounds, borders, spacing) and not appear as a single merged block.

## Current Implementation Status
1.  **Backend (`streaming.py`)**: 
    - Implemented an SSE stream parser to detect `<think>` and `</think>` tags.
    - Emits specific events: `thought_start`, `thought_delta`, `thought_end`.
    - Separates `content` (final response) from `thought` (internal monologue).

2.  **Frontend Store (`chat-store.ts`)**: 
    - Updated to handle `thought_delta` SSE events.
    - Stores `thought` in a separate field in the `Message` object.

3.  **Frontend UI (`AIMessage.tsx`)**: 
    - Renders `ThinkingBubble` *before* the `ai-prose-container` (Main Content).
    - `ThinkingBubble` has its own styling (border, different background).

## The Problem
The user reports: **"the thinking and final response were in the same bubble"** and specifically notes **"that didn't work your last attempt class='ai-message-container group'"**.

### Analysis of Failure
Despite the code changes appearing correct in the file system, the user sees them merged. This suggests one of two things:

1.  **Backend Parsing Failure**: The model is NOT emitting `<think>` tags as expected, or the parser is failing to catch them. 
    - *Result*: The raw `<think>` tags and thought text are treated as standard `content`.
    - *Consequence*: Since `message.thought` is empty, `ThinkingBubble` is NOT rendered. The text (including tags) is rendered by `MarkdownItRenderer` inside `ai-prose-container`.

2.  **Structure/CSS Issue**: The user's reference to `ai-message-container group` might imply they are looking at the outer wrapper and seeing that visually, the "separate" components still look like one unit, perhaps due to layout behavior (e.g., flex gaps not working, or backgrounds merging). 
    - *However*, `ThinkingBubble` has `mb-6` and distinct borders, so this is less likely unless the parser failed.

### Detailed File Context for Debugging

#### `AIMessage.tsx` (Current Structure)
```tsx
<div className="ai-message-container group"> { /* Flex container */ }
  <Avatar />
  <div className="ai-content-wrapper"> { /* Flex col */ }
    
    {/* 1. Thinking Bubble (Should be separate) */}
    {message.thought && ( <ThinkingBubble ... /> )}

    {/* 2. Main Content (Should be separate) */}
    {(message.content || ...) ? (
       <div className="ai-prose-container"> ... </div>
    ) : ...}
    
  </div>
</div>
```

#### `streaming.py` (Parser Logic)
It looks for `<think>` and `</think>` literally.
- If the model outputs `<think>\n` (with newline), it should work.
- If the model outputs `Thought:` or something else, it fails.

## Request for Assistance
Please analyze why the "Thinking Bubble" separation might be failing. 
- Is the parser logic in `backend/app/services/llm/streaming.py` robust enough?
- Could `MarkdownItRenderer` be swallowing the tags before the store sees them? (Unlikely, logic is in backend).
- Most likely: The model output format does not match the parser's expectation (`<think>...`), causing the thought text to leak into `content`.

## Next Steps
1.  Verify the exact output format of the model (logs needed).
2.  If the model is outputting raw text without tags, or different tags, update the backend parser.
3.  If the model IS outputting tags, verify why `message.thought` remains empty or why it leaks into `content`.
