# Last Updated: 2025-12-03

## Purpose
Domain entities representing core business objects (Message, Session, ImageAttachment).

## Key Files
- `message.py` - Message dataclass with role, content, thinking, images, search results, JSON serialization
- `session.py` - Session dataclass with user_id, timestamps, message_count, metadata, touch/increment methods

## Dependencies/Relations
Used by `services/session/`, `services/llm/`. Converted to/from schemas in `api/v1/`.
