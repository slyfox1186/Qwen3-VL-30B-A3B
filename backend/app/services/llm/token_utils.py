"""Token counting utilities using Qwen's actual tokenizer.

Provides dynamic max_tokens calculation based on prompt size
to prevent exceeding model context limits.
"""

import json
import logging
from functools import lru_cache
from typing import Any

from transformers import AutoTokenizer

from app.config import get_settings

logger = logging.getLogger(__name__)

# Small safety buffer for edge cases
TOKEN_SAFETY_BUFFER = 10


@lru_cache(maxsize=1)
def get_tokenizer() -> AutoTokenizer:
    """Get cached Qwen tokenizer instance."""
    settings = get_settings()
    model_name = settings.vllm_model
    logger.info(f"Loading tokenizer for model: {model_name}")
    return AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)


def count_message_tokens(messages: list[dict[str, Any]]) -> int:
    """
    Count tokens in a list of chat messages using Qwen's tokenizer.

    Args:
        messages: List of message dicts with 'role' and 'content'

    Returns:
        Actual token count
    """
    tokenizer = get_tokenizer()

    # Use apply_chat_template to get the exact tokenized prompt
    try:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        tokens = tokenizer.encode(text)
        return len(tokens)
    except Exception as e:
        logger.warning(f"Failed to use chat template, falling back to simple count: {e}")
        # Fallback: count each message separately
        total_tokens = 0
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, str):
                total_tokens += len(tokenizer.encode(content))
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            total_tokens += len(tokenizer.encode(part.get("text", "")))
                        elif part.get("type") == "image_url":
                            # Images use variable tokens based on resolution
                            total_tokens += 1000  # Conservative estimate
                    elif isinstance(part, str):
                        total_tokens += len(tokenizer.encode(part))
            # Add overhead per message
            total_tokens += 10
        return total_tokens


def count_tools_tokens(tools: list[dict[str, Any]] | None) -> int:
    """
    Count tokens used by tool definitions.

    Args:
        tools: List of tool definitions in OpenAI format

    Returns:
        Token count for tools
    """
    if not tools:
        return 0

    tokenizer = get_tokenizer()
    tools_json = json.dumps(tools)
    return len(tokenizer.encode(tools_json))


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

    # Count input tokens using actual Qwen tokenizer
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
        return 100

    # Use requested max if it fits, otherwise cap at available
    if requested_max_tokens:
        max_tokens = min(requested_max_tokens, available_tokens)
    else:
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
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text))
