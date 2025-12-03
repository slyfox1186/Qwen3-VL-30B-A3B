# Last Updated: 2025-12-03

## Purpose
vLLM integration: OpenAI-compatible client, SSE streaming with <think> tag parsing, message formatting.

## Key Files
- `client.py` - VLLMClient wraps AsyncOpenAI for streaming/non-streaming chat completions, tool support, health checks
- `streaming.py` - SSEStreamHandler parses <think>...</think> tags from token stream, emits structured SSE events
- `message_builder.py` - MessageBuilder converts domain Messages to OpenAI format for vLLM

## Dependencies/Relations
Used by `api/v1/chat.py`. Depends on openai library, `models/domain/`, `config.py`.
