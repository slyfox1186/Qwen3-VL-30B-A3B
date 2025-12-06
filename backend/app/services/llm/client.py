"""vLLM client with raw HTTP streaming for reasoning_content support."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


class VLLMClient:
    """
    Async client for vLLM using raw HTTP for streaming.

    Uses httpx for streaming to access vLLM-specific fields like
    reasoning_content which are NOT available through the OpenAI client.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        settings = get_settings()

        self._base_url = (base_url or settings.vllm_base_url).rstrip("/")
        self._api_key = api_key or settings.vllm_api_key
        self._model = model or settings.vllm_model
        self._timeout = timeout or settings.vllm_timeout

        # OpenAI client for non-streaming and health checks
        self._client = AsyncOpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=self._timeout,
        )

        # httpx client for streaming (to access reasoning_content)
        self._http_client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout, connect=10.0),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )

    async def chat_completion_stream(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.6,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Stream chat completion using raw HTTP to access reasoning_content.

        vLLM's reasoning_content field is NOT OpenAI API compatible,
        so we must parse the SSE stream directly.

        Yields:
            Dict with 'type' ('reasoning', 'content', or 'tool_call') and data
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        try:
            async with self._http_client.stream(
                "POST",
                "/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    # SSE format: "data: {...}"
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # Remove "data: " prefix

                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})

                    # Yield reasoning_content (vLLM --reasoning-parser)
                    reasoning = delta.get("reasoning_content")
                    if reasoning:
                        yield {"type": "reasoning", "content": reasoning}

                    # Yield content
                    content = delta.get("content")
                    if content:
                        yield {"type": "content", "content": content}

                    # Yield tool calls
                    tool_calls = delta.get("tool_calls")
                    if tool_calls:
                        for tc in tool_calls:
                            func = tc.get("function", {})
                            yield {
                                "type": "tool_call",
                                "tool_call": {
                                    "id": tc.get("id"),
                                    "index": tc.get("index", 0),
                                    "function": {
                                        "name": func.get("name"),
                                        "arguments": func.get("arguments"),
                                    },
                                },
                            }

        except httpx.HTTPStatusError as e:
            logger.error(f"vLLM HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"vLLM streaming error: {e}")
            raise

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.6,
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
            await self._client.models.list()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http_client.aclose()
