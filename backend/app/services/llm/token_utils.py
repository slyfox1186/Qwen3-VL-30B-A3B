"""Token counting utilities using tiktoken.

Provides dynamic max_tokens calculation based on prompt size
to prevent exceeding model context limits.
"""

import json
import logging
from functools import lru_cache
from typing import Any

import tiktoken

from app.config import get_settings

logger = logging.getLogger(__name__)

# Qwen models use cl100k_base encoding (same as GPT-4)
DEFAULT_ENCODING = "cl100k_base"

# Minimal buffer for tokenizer variance
TOKEN_SAFETY_BUFFER = 10


@lru_cache(maxsize=1)
def get_encoding() -> tiktoken.Encoding:
    """Get cached tiktoken encoding."""
    return tiktoken.get_encoding(DEFAULT_ENCODING)


def count_message_tokens(messages: list[dict[str, Any]]) -> int:
    """
    Count tokens in a list of chat messages.

    Args:
        messages: List of message dicts with 'role' and 'content'

    Returns:
        Estimated token count
    """
    encoding = get_encoding()
    total_tokens = 0

    for message in messages:
        # Each message has overhead for role, delimiters
        total_tokens += 4  # <|im_start|>role\n ... <|im_end|>\n

        role = message.get("role", "")
        content = message.get("content", "")

        # Count role tokens
        total_tokens += len(encoding.encode(role))

        # Handle content (can be string or list for multimodal)
        if isinstance(content, str):
            total_tokens += len(encoding.encode(content))
        elif isinstance(content, list):
            # Multimodal content
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text = part.get("text", "")
                        total_tokens += len(encoding.encode(text))
                    elif part.get("type") == "image_url":
                        # Images use ~85 tokens for low detail, ~765 for high
                        # Use conservative estimate
                        total_tokens += 765
                elif isinstance(part, str):
                    total_tokens += len(encoding.encode(part))

        # Handle tool calls in assistant messages
        tool_calls = message.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                # Tool call overhead
                total_tokens += 10
                func = tc.get("function", {})
                if func.get("name"):
                    total_tokens += len(encoding.encode(func["name"]))
                if func.get("arguments"):
                    total_tokens += len(encoding.encode(func["arguments"]))

    # Add priming tokens
    total_tokens += 3

    return total_tokens


def count_tools_tokens(tools: list[dict[str, Any]] | None) -> int:
    """
    Count tokens used by tool definitions.

    Args:
        tools: List of tool definitions in OpenAI format

    Returns:
        Estimated token count for tools
    """
    if not tools:
        return 0

    encoding = get_encoding()
    # Serialize tools to JSON and count
    tools_json = json.dumps(tools)
    return len(encoding.encode(tools_json))


def calculate_max_tokens(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    requested_max_tokens: int | None = None,
) -> int:
    """
    Calculate safe max_tokens value based on prompt size.

    Ensures total (prompt + completion) doesn't exceed model context.

    Args:
        messages: Chat messages to send
        tools: Optional tool definitions
        requested_max_tokens: User-requested max tokens (will be capped if needed)

    Returns:
        Safe max_tokens value
    """
    settings = get_settings()
    model_context = settings.vllm_max_model_len

    # Count input tokens
    prompt_tokens = count_message_tokens(messages)
    tools_tokens = count_tools_tokens(tools)
    total_input = prompt_tokens + tools_tokens

    # Calculate available tokens for completion
    available_tokens = model_context - total_input - TOKEN_SAFETY_BUFFER

    if available_tokens <= 0:
        logger.warning(
            f"Prompt too long: {total_input} tokens, model context: {model_context}. "
            "Setting minimum completion tokens."
        )
        # Return minimum to at least try (vLLM will error if truly over)
        return 100

    # Use requested max if it fits, otherwise cap at available
    if requested_max_tokens:
        max_tokens = min(requested_max_tokens, available_tokens)
    else:
        # Default to all available space
        max_tokens = available_tokens

    logger.debug(
        f"Token calculation: prompt={prompt_tokens}, tools={tools_tokens}, "
        f"available={available_tokens}, max_tokens={max_tokens}"
    )

    return max(100, int(max_tokens))


def estimate_tokens(text: str) -> int:
    """
    Quick token estimate for a single string.

    Args:
        text: Text to estimate

    Returns:
        Token count
    """
    encoding = get_encoding()
    return len(encoding.encode(text))
