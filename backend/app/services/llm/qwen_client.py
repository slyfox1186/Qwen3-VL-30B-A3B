"""Qwen-Agent client for proper Qwen3 tool calling with parallel function calls."""

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

from qwen_agent.llm import get_chat_model

from app.config import get_settings
from app.services.llm.token_utils import calculate_max_tokens

logger = logging.getLogger(__name__)

# Regex patterns for parsing tool calls from raw content
TOOL_CALL_XML_PATTERN = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL
)
QWEN_FUNCTION_PATTERN = re.compile(
    r"✿FUNCTION✿:\s*(\w+)\s*\n✿ARGS✿:\s*", re.DOTALL
)

def extract_balanced_json(text: str, start_index: int) -> str | None:
    """Extract JSON object with balanced brace matching."""
    depth = 0
    start = -1
    in_string = False
    escape_next = False

    for i in range(start_index, len(text)):
        char = text[i]

        if char == '"' and not escape_next:
            in_string = not in_string

        if char == '\\' and not escape_next:
            escape_next = True
            continue
        escape_next = False

        if not in_string:
            if char == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start != -1:
                    json_str = text[start:i + 1]
                    try:
                        json.loads(json_str)
                        return json_str
                    except json.JSONDecodeError:
                        start = -1
                        depth = 0
                if depth < 0:
                    return None

    return None


class QwenAgentClient:
    """
    Async client for vLLM using Qwen-Agent for proper tool calling.

    Uses the official Qwen-Agent framework which:
    - Enables parallel_function_calls for batch tool execution
    - Uses Qwen's native function calling format
    - Parses multiple tool call formats (function_call, ✿FUNCTION✿, <tool_call>)
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        max_context: int | None = None,
        timeout: float | None = None,
    ):
        settings = get_settings()

        self._base_url = (base_url or settings.vllm_base_url).rstrip("/")
        self._api_key = api_key or settings.vllm_api_key
        self._model = model or settings.vllm_model
        self._max_context = max_context or settings.vllm_max_model_len
        self._timeout = timeout or settings.vllm_timeout
        self._default_max_tokens = settings.vllm_max_tokens

        # Initialize Qwen-Agent LLM with OpenAI-compatible config
        # NOTE: fncall_prompt_type='nous' (Hermes-style) is the DEFAULT and RECOMMENDED
        # Do NOT use 'qwen' - the docs say 'nous' works best for Qwen3
        self._llm = get_chat_model({
            "model": self._model,
            "model_type": "oai",  # Use OpenAI-compatible API (vLLM)
            "model_server": self._base_url,
            "api_key": self._api_key or "EMPTY",
            "generate_cfg": {
                # 'nous' (Hermes-style) is the default, explicitly set for clarity
                "fncall_prompt_type": "nous",
                "temperature": 0.6,
                "top_p": 0.95,
                "top_k": 20,
                "max_tokens": self._default_max_tokens,
                # Enable thinking mode for reasoning visibility
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": True}
                },
            },
        })

        logger.info(
            f"QwenAgentClient initialized: model={self._model}, "
            f"server={self._base_url}, max_context={self._max_context}"
        )

    def _tools_to_functions(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        """Convert OpenAI tools format to Qwen functions format."""
        if not tools:
            return []

        functions = []
        for tool in tools:
            if tool.get("type") == "function" and tool.get("function"):
                functions.append(tool["function"])
        return functions

    def _parse_tool_calls_from_content(
        self, content: str, tool_calls_seen: set[str]
    ) -> list[dict[str, Any]]:
        """
        Parse tool calls from content using multiple formats.

        Supports:
        1. <tool_call>{...}</tool_call> XML format (vLLM default)
        2. ✿FUNCTION✿: name ✿ARGS✿: {...} (Qwen3 native)
        3. {"_tool_call": true, "name": ..., "arguments": ...} (embedded JSON)
        """
        tool_calls = []

        # 1. Parse <tool_call> XML format
        for match in TOOL_CALL_XML_PATTERN.finditer(content):
            try:
                tool_json = json.loads(match.group(1))
                name = tool_json.get("name", "")
                args = tool_json.get("arguments", {})
                if isinstance(args, dict):
                    args = json.dumps(args)

                sig = f"{name}:{args}"
                if sig not in tool_calls_seen:
                    tool_calls_seen.add(sig)
                    tool_calls.append({
                        "type": "tool_call",
                        "tool_call": {
                            "id": f"call_{name}_{len(tool_calls_seen)}",
                            "index": len(tool_calls_seen) - 1,
                            "function": {"name": name, "arguments": args},
                        },
                    })
                    logger.info(f"Parsed <tool_call> XML: {name}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse <tool_call> JSON: {e}")

        # 2. Parse ✿FUNCTION✿ markers
        for match in QWEN_FUNCTION_PATTERN.finditer(content):
            name = match.group(1)
            args_start = match.end()
            args_json = extract_balanced_json(content, args_start)

            if args_json:
                sig = f"{name}:{args_json}"
                if sig not in tool_calls_seen:
                    tool_calls_seen.add(sig)
                    tool_calls.append({
                        "type": "tool_call",
                        "tool_call": {
                            "id": f"call_{name}_{len(tool_calls_seen)}",
                            "index": len(tool_calls_seen) - 1,
                            "function": {"name": name, "arguments": args_json},
                        },
                    })
                    logger.info(f"Parsed ✿FUNCTION✿ marker: {name}")

        # 3. Parse embedded JSON tool calls
        if content.strip().startswith("{") and "_tool_call" in content:
            try:
                parsed = json.loads(content.strip())
                if parsed.get("_tool_call"):
                    name = parsed.get("name", "")
                    args = json.dumps(parsed.get("arguments", {}))
                    sig = f"{name}:{args}"
                    if sig not in tool_calls_seen:
                        tool_calls_seen.add(sig)
                        tool_calls.append({
                            "type": "tool_call",
                            "tool_call": {
                                "id": f"call_{name}_{len(tool_calls_seen)}",
                                "index": len(tool_calls_seen) - 1,
                                "function": {"name": name, "arguments": args},
                            },
                        })
                        logger.info(f"Parsed embedded JSON tool call: {name}")
            except json.JSONDecodeError:
                pass

        return tool_calls

    async def chat_completion_stream(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.6,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,  # noqa: ARG002
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Stream chat completion using Qwen-Agent for proper tool calling.

        Key features:
        - parallel_function_calls=True for batch tool execution
        - Parses multiple tool call formats (function_call, ✿FUNCTION✿, <tool_call>)
        - Streaming with async wrapper for sync qwen-agent
        - Dynamic max_tokens calculation to prevent context overflow

        Yields:
            Dict with 'type' ('reasoning', 'content', or 'tool_call') and data
        """
        # Calculate safe max_tokens dynamically based on message size (use original tools format)
        safe_max_tokens = calculate_max_tokens(
            messages, tools=tools, requested_max_tokens=max_tokens
        )
        logger.info(f"Dynamic max_tokens: requested={max_tokens}, safe={safe_max_tokens}")

        functions = self._tools_to_functions(tools)

        # Use async queue + thread pool for sync qwen-agent streaming
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        # Capture instance variables for nested function
        llm = self._llm
        parse_tool_calls = self._parse_tool_calls_from_content
        effective_max_tokens = safe_max_tokens  # Capture for closure

        def run_sync():
            """Run synchronous qwen-agent streaming in thread pool."""
            full_content = ""
            full_reasoning = ""
            last_content_len = 0  # Track what we've already sent
            last_reasoning_len = 0  # Track reasoning content sent
            tool_calls_seen: set[str] = set()
            iteration_count = 0

            def process_responses(responses_list: list) -> None:
                """Process a list of response messages."""
                nonlocal full_content, full_reasoning, last_content_len, last_reasoning_len

                if not responses_list:
                    return

                for msg in responses_list:
                    if not isinstance(msg, dict):
                        continue

                    # Handle function_call in message (Qwen-Agent format)
                    if "function_call" in msg and msg["function_call"]:
                        fc = msg["function_call"]
                        name = fc.get("name", "")
                        args = fc.get("arguments", "{}")

                        if name:
                            sig = f"{name}:{args}"
                            if sig not in tool_calls_seen:
                                tool_calls_seen.add(sig)
                                queue.put_nowait((
                                    "chunk",
                                    {
                                        "type": "tool_call",
                                        "tool_call": {
                                            "id": f"call_{name}_{len(tool_calls_seen)}",
                                            "index": len(tool_calls_seen) - 1,
                                            "function": {"name": name, "arguments": args},
                                        },
                                    },
                                ))
                                logger.info(f"Received function_call: {name}")

                    # Handle reasoning_content (thinking) - Qwen-Agent returns this separately
                    # CRITICAL: Qwen-Agent streaming sends accumulated content, not deltas
                    if "reasoning_content" in msg and msg["reasoning_content"]:
                        reasoning = msg["reasoning_content"]
                        full_reasoning = reasoning

                        # Only send delta (new reasoning since last send)
                        if len(reasoning) > last_reasoning_len:
                            delta = reasoning[last_reasoning_len:]
                            last_reasoning_len = len(reasoning)

                            queue.put_nowait((
                                "chunk",
                                {"type": "reasoning", "content": delta},
                            ))

                    # Handle content in message (final response)
                    # CRITICAL: Qwen-Agent streaming sends accumulated content, not deltas
                    # We must only send the NEW characters (delta) to avoid duplicates
                    if "content" in msg and msg["content"]:
                        content = msg["content"]
                        full_content = content

                        # Only send delta (new content since last send)
                        if len(content) > last_content_len:
                            delta = content[last_content_len:]
                            last_content_len = len(content)

                            queue.put_nowait((
                                "chunk",
                                {"type": "content", "content": delta},
                            ))

            try:
                # Try streaming first
                for responses in llm.chat(
                    messages=messages,
                    functions=functions if functions else None,
                    stream=True,
                    extra_generate_cfg={
                        "parallel_function_calls": True,
                        "max_tokens": effective_max_tokens,
                    },
                ):
                    iteration_count += 1
                    process_responses(responses)

            except (IndexError, KeyError) as e:
                # ROBUST FALLBACK: If streaming fails, try non-streaming
                logger.warning(
                    f"Qwen-Agent streaming failed ({type(e).__name__}: {e}), "
                    f"falling back to non-streaming mode"
                )
                try:
                    responses = llm.chat(
                        messages=messages,
                        functions=functions if functions else None,
                        stream=False,
                        extra_generate_cfg={
                            "parallel_function_calls": True,
                            "max_tokens": effective_max_tokens,
                        },
                    )
                    process_responses(responses)
                    iteration_count = 1
                except Exception as fallback_error:
                    logger.error(f"Non-streaming fallback also failed: {fallback_error}")
                    queue.put_nowait(("error", fallback_error))
                    return

            except Exception as e:
                logger.error(f"Qwen-Agent error: {e}")
                queue.put_nowait(("error", e))
                return

            # If streaming yielded nothing, try non-streaming as fallback
            if iteration_count == 0:
                logger.warning("Streaming yielded nothing, trying non-streaming fallback")
                try:
                    responses = llm.chat(
                        messages=messages,
                        functions=functions if functions else None,
                        stream=False,
                        extra_generate_cfg={
                            "parallel_function_calls": True,
                            "max_tokens": effective_max_tokens,
                        },
                    )
                    process_responses(responses)
                except Exception as e:
                    logger.error(f"Non-streaming fallback failed: {e}")
                    queue.put_nowait(("error", e))
                    return

            # Parse tool calls from accumulated content (fallback parsing)
            if full_content:
                parsed_tools = parse_tool_calls(full_content, tool_calls_seen)
                for tool_call in parsed_tools:
                    queue.put_nowait(("chunk", tool_call))

            queue.put_nowait(("done", None))

        # Start sync streaming in thread pool
        task = asyncio.create_task(asyncio.to_thread(run_sync))

        try:
            while True:
                status, data = await asyncio.wait_for(queue.get(), timeout=self._timeout)

                if status == "done":
                    break
                if status == "error":
                    raise data  # type: ignore[misc]
                if status == "chunk" and data:
                    yield data

        except TimeoutError:
            logger.error("Qwen-Agent streaming timed out")
            task.cancel()
            raise

        # Ensure thread completes
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except (TimeoutError, asyncio.CancelledError):
            pass

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

        def run_sync():
            responses = self._llm.chat(
                messages=messages,
                functions=None,
                stream=False,
                extra_generate_cfg={
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            return responses

        try:
            responses = await asyncio.to_thread(run_sync)

            # Extract content from last assistant message
            content = None
            for msg in reversed(responses):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    break

            return {
                "content": content,
                "finish_reason": "stop",
                "usage": {
                    "prompt_tokens": 0,  # qwen-agent doesn't expose this
                    "completion_tokens": 0,
                },
            }

        except Exception as e:
            logger.error(f"Qwen-Agent completion error: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check if vLLM server is healthy.

        Returns:
            True if server is responsive
        """
        try:
            # Simple test message
            responses = await asyncio.to_thread(
                lambda: self._llm.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    functions=None,
                    stream=False,
                    extra_generate_cfg={"max_tokens": 1},
                )
            )
            return bool(responses)
        except Exception:
            return False

    async def close(self) -> None:
        """Close the client (no-op for qwen-agent)."""
        pass
