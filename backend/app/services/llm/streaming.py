"""SSE streaming handler for vLLM responses."""

import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


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
    search_results: list[dict] | None = None
    search_query: str | None = None


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

        # Tool call accumulation (vLLM streams tool calls in chunks)
        tool_calls: dict[int, dict] = {}  # index -> {name, arguments}

        # Store search results for persistence
        captured_search_results: list[dict] | None = None
        captured_search_query: str | None = None

        # Track if we've started content
        content_started = False

        # Emit start event
        yield StreamEvent("start", {
            "type": "start",
            "request_id": request_id,
        }).to_sse()

        try:
            async for chunk in token_generator:
                chunk_type = chunk.get("type")

                if chunk_type == "content":
                    content = chunk.get("content", "")
                    if content:
                        content_buffer += content

                        # Emit content_start on first content
                        if not content_started:
                            yield StreamEvent("content_start", {
                                "type": "content_start"
                            }).to_sse()
                            content_started = True

                        # Emit content delta
                        yield StreamEvent("content_delta", {
                            "type": "content_delta",
                            "content": content,
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

            # Process accumulated tool calls
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
                else:
                    logger.warning(f"Unknown tool: {tool_name}")

            # Emit content_end if we had content
            if content_started:
                yield StreamEvent("content_end", {"type": "content_end"}).to_sse()

            # Store result for caller if holder provided
            if result_holder is not None:
                result_holder.append(StreamResult(
                    content=content_buffer,
                    search_results=captured_search_results,
                    search_query=captured_search_query,
                ))

            # Emit done event
            yield StreamEvent("done", {
                "type": "done",
                "request_id": request_id,
            }).to_sse()

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield StreamEvent("error", {
                "type": "error",
                "error": str(e),
                "request_id": request_id,
                "code": "LLM_ERROR",
            }).to_sse()
