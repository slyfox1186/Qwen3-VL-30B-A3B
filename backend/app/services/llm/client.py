"""vLLM OpenAI-compatible client."""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


class VLLMClient:
    """
    Async client for vLLM using OpenAI-compatible API.

    Supports both streaming and non-streaming completions
    for multimodal (vision-language) models.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        settings = get_settings()

        self._base_url = base_url or settings.vllm_base_url
        self._api_key = api_key or settings.vllm_api_key
        self._model = model or settings.vllm_model
        self._timeout = timeout or settings.vllm_timeout

        self._client = AsyncOpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=self._timeout,
        )

    async def chat_completion_stream(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Stream chat completion with tool support.

        Args:
            messages: Chat messages in OpenAI format
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            tools: Optional list of tool definitions
            tool_choice: Optional tool choice ("auto", "none", or specific tool)

        Yields:
            Dict with 'type' ('content' or 'tool_call') and data
        """
        try:
            kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "max_completion_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }
            if tools:
                kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

            stream = await self._client.chat.completions.create(**kwargs)

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Yield content tokens
                if delta.content:
                    yield {"type": "content", "content": delta.content}

                # Yield tool calls
                if delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        yield {
                            "type": "tool_call",
                            "tool_call": {
                                "id": tool_call.id,
                                "index": tool_call.index,
                                "function": {
                                    "name": tool_call.function.name if tool_call.function else None,
                                    "arguments": tool_call.function.arguments if tool_call.function else None,
                                }
                            }
                        }

        except Exception as e:
            logger.error(f"vLLM streaming error: {e}")
            raise

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """
        Non-streaming chat completion.

        Args:
            messages: Chat messages in OpenAI format
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Dict with content and usage info
        """
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
            )

            choice = response.choices[0]
            usage = response.usage

            return {
                "content": choice.message.content,
                "finish_reason": choice.finish_reason,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                },
            }

        except Exception as e:
            logger.error(f"vLLM completion error: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check if vLLM server is healthy.

        Returns:
            True if server is responsive
        """
        try:
            # Try to list models as a health check
            await self._client.models.list()
            return True
        except Exception as e:
            logger.error(f"vLLM health check failed: {e}")
            return False
