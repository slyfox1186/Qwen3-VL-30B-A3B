# Last Updated: 2025-12-03

## Purpose
Data models: domain entities (Message, Session) and Pydantic schemas (request/response).

## Key Files
- `domain/` - Business logic models (Message, Session) with JSON serialization
- `schemas/` - Pydantic validation schemas for API (chat, session, common)

## Dependencies/Relations
Domain models used by `services/`, schemas used by `api/v1/`.
