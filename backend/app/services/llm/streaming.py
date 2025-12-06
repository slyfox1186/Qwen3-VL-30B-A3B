"""SSE streaming handler for vLLM responses."""

import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from app.services.functions import FunctionExecutor, get_function_registry

logger = logging.getLogger(__name__)

# Global executor instance for function calls
_function_executor: FunctionExecutor | None = None


def get_function_executor() -> FunctionExecutor:
    """Get or create the global function executor."""
    global _function_executor
    if _function_executor is None:
        _function_executor = FunctionExecutor()
    return _function_executor


@dataclass
class StreamEvent:
    """SSE event data structure."""

    event: str
    data: dict

    def to_sse(self) -> str:
        """Format as SSE string."""
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


@dataclass
class StreamResult:
    """Result from streaming with accumulated content."""

    content: str
    thought: str | None = None
    search_results: list[dict] | None = None
    search_query: str | None = None
    function_calls: list[dict] | None = field(default=None)


class SSEStreamHandler:
    """
    Handles SSE streaming from vLLM.

    Wraps LLM token stream and emits properly formatted SSE events.
    """

    @staticmethod
    async def stream_response(
        token_generator: AsyncGenerator[dict[str, Any], None],
        request_id: str,
        result_holder: list[StreamResult] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream response from vLLM with native tool call handling.

        Args:
            token_generator: Async generator yielding dicts with 'type' and data
            request_id: Request identifier
            result_holder: Optional list to store final StreamResult (for caller to retrieve)

        Yields:
            SSE formatted strings
        """
        from app.services.web_access import get_web_access_service

        web_service = get_web_access_service()
        content_buffer = ""
        thought_buffer = ""

        # Tool call accumulation (vLLM streams tool calls in chunks)
        tool_calls: dict[int, dict] = {}  # index -> {name, arguments}

        # Store search results for persistence
        captured_search_results: list[dict] | None = None
        captured_search_query: str | None = None

        # Track if we've started content
        content_started = False

        # Thinking process state
        # vLLM with --reasoning-parser sends reasoning in a separate field
        # We track if we've emitted thought_start to handle both modes
        thought_started = False
        chunk_count = 0

        # Emit start event
        logger.info(f"[{request_id}] SSE stream starting")
        yield StreamEvent("start", {
            "type": "start",
            "request_id": request_id,
        }).to_sse()

        try:
            async for chunk in token_generator:
                chunk_type = chunk.get("type")
                chunk_count += 1

                # Handle reasoning content from vLLM --reasoning-parser
                if chunk_type == "reasoning":
                    reasoning = chunk.get("content", "")
                    if reasoning:
                        if not thought_started:
                            yield StreamEvent("thought_start", {"type": "thought_start"}).to_sse()
                            thought_started = True
                        thought_buffer += reasoning
                        yield StreamEvent("thought_delta", {
                            "type": "thought_delta",
                            "content": reasoning
                        }).to_sse()

                elif chunk_type == "content":
                    content = chunk.get("content", "")
                    if content:
                        # Log first chunk
                        if chunk_count <= 3:
                            logger.info(f"[{request_id}] Chunk {chunk_count}: {repr(content[:100])}")

                        # End thinking if we were in it and now getting content
                        if thought_started and not content_started:
                            yield StreamEvent("thought_end", {"type": "thought_end"}).to_sse()

                        if not content_started:
                            yield StreamEvent("content_start", {"type": "content_start"}).to_sse()
                            content_started = True

                        content_buffer += content
                        yield StreamEvent("content_delta", {
                            "type": "content_delta",
                            "content": content
                        }).to_sse()

                elif chunk_type == "tool_call":
                    # Accumulate tool call data (streamed in chunks)
                    tc = chunk.get("tool_call", {})
                    idx = tc.get("index", 0)
                    func = tc.get("function", {})

                    if idx not in tool_calls:
                        tool_calls[idx] = {"name": "", "arguments": ""}

                    if func.get("name"):
                        tool_calls[idx]["name"] = func["name"]
                    if func.get("arguments"):
                        tool_calls[idx]["arguments"] += func["arguments"]

            # End thinking if it was started but no content followed
            if thought_started and not content_started:
                yield StreamEvent("thought_end", {"type": "thought_end"}).to_sse()

            # Process accumulated tool calls
            function_results: list[dict] = []
            registry = get_function_registry()
            executor = get_function_executor()

            for idx, tc in tool_calls.items():
                tool_name = tc.get("name", "")
                arguments_str = tc.get("arguments", "")

                if tool_name == "search_images":
                    try:
                        args = json.loads(arguments_str) if arguments_str else {}
                        query = args.get("query", "")

                        if query:
                            results = await web_service.search_images(query, num_results=5)

                            captured_search_results = [
                                {
                                    "title": r.title,
                                    "link": r.link,
                                    "thumbnail": r.thumbnail,
                                    "original_image": r.original_image
                                } for r in results
                            ]
                            captured_search_query = query

                            yield StreamEvent("images", {
                                "type": "images",
                                "images": captured_search_results,
                                "query": query
                            }).to_sse()

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse tool arguments: {e}")

                elif registry.get(tool_name):
                    # Execute registered built-in function
                    try:
                        args = json.loads(arguments_str) if arguments_str else {}
                        result = await executor.execute(tool_name, args)

                        function_call_result = {
                            "name": tool_name,
                            "arguments": args,
                            "success": result.success,
                            "result": result.result,
                            "error": result.error,
                            "execution_time_ms": result.execution_time_ms,
                            "from_cache": result.from_cache,
                        }
                        function_results.append(function_call_result)

                        # Emit function result event
                        yield StreamEvent("function_result", {
                            "type": "function_result",
                            "function": tool_name,
                            "arguments": args,
                            "success": result.success,
                            "result": result.result,
                            "error": result.error,
                        }).to_sse()

                        logger.info(
                            f"[{request_id}] Function {tool_name} executed: "
                            f"success={result.success}, "
                            f"time={result.execution_time_ms:.1f}ms"
                        )

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse function arguments: {e}")
                        yield StreamEvent("function_error", {
                            "type": "function_error",
                            "function": tool_name,
                            "error": f"Invalid arguments: {e}",
                        }).to_sse()
                else:
                    logger.warning(f"Unknown tool: {tool_name}")

            # Emit content_end if we had content
            if content_started:
                yield StreamEvent("content_end", {"type": "content_end"}).to_sse()

            # Store result for caller if holder provided
            if result_holder is not None:
                result_holder.append(StreamResult(
                    content=content_buffer,
                    thought=thought_buffer if thought_buffer else None,
                    search_results=captured_search_results,
                    search_query=captured_search_query,
                    function_calls=function_results if function_results else None,
                ))

            # Emit done event
            logger.info(f"[{request_id}] SSE stream complete: {chunk_count} chunks, content={len(content_buffer)} chars, thought={len(thought_buffer)} chars")
            yield StreamEvent("done", {
                "type": "done",
                "request_id": request_id,
            }).to_sse()

        except Exception as e:
            logger.error(f"[{request_id}] Stream error: {e}")
            yield StreamEvent("error", {
                "type": "error",
                "error": str(e),
                "request_id": request_id,
                "code": "LLM_ERROR",
            }).to_sse()
