# Last Updated: 2025-12-03

## Purpose
Pydantic schemas for API request/response validation.

## Key Files
- `chat.py` - ChatRequest (message, images, max_tokens), ChatResponse, StreamEvent, TokenUsage
- `session.py` - SessionCreate, SessionResponse, HistoryMessage, SessionHistory (with pagination)
- `common.py` - HealthResponse, DetailedHealthResponse, ServiceHealth

## Dependencies/Relations
Used by `api/v1/` for request validation and response serialization. Validates data from frontend.
