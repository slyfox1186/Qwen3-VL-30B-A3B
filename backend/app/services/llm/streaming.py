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
    thought: str | None = None
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
        thought_buffer = ""

        # Tool call accumulation (vLLM streams tool calls in chunks)
        tool_calls: dict[int, dict] = {}  # index -> {name, arguments}

        # Store search results for persistence
        captured_search_results: list[dict] | None = None
        captured_search_query: str | None = None

        # Track if we've started content
        content_started = False

        # Thinking process state
        in_thought = False
        stream_buffer = ""
        start_tag = "<think>"
        end_tag = "</think>"

        # Emit start event
        logger.info(f"[{request_id}] SSE stream starting")
        yield StreamEvent("start", {
            "type": "start",
            "request_id": request_id,
        }).to_sse()

        # Debug: track first N characters to see raw model output
        first_chars_logged = False
        chunk_count = 0

        try:
            async for chunk in token_generator:
                chunk_type = chunk.get("type")
                chunk_count += 1

                if chunk_type == "content":
                    content = chunk.get("content", "")
                    if content:
                        # Log first chunk immediately
                        if chunk_count <= 3:
                            logger.info(f"[{request_id}] Chunk {chunk_count}: {repr(content[:100])}")

                        stream_buffer += content

                        # Log first 200 chars to see if <think> exists
                        if not first_chars_logged and len(stream_buffer) >= 50:
                            logger.info(f"[{request_id}] FIRST 200 CHARS: {repr(stream_buffer[:200])}")
                            first_chars_logged = True

                        # Process buffer for tags
                        while stream_buffer:
                            if in_thought:
                                # Look for closing tag
                                end_idx = stream_buffer.find(end_tag)
                                if end_idx != -1:
                                    # Found end of thought
                                    thought_chunk = stream_buffer[:end_idx]
                                    if thought_chunk:
                                        thought_buffer += thought_chunk
                                        yield StreamEvent("thought_delta", {
                                            "type": "thought_delta",
                                            "content": thought_chunk
                                        }).to_sse()

                                    yield StreamEvent("thought_end", {"type": "thought_end"}).to_sse()
                                    in_thought = False
                                    stream_buffer = stream_buffer[end_idx + len(end_tag):]
                                else:
                                    # No end tag yet
                                    # Keep enough chars to potentially match the start of end_tag
                                    # end_tag is </think>, 8 chars.
                                    # If buffer ends with '<', '</', '</t', etc., we must wait.
                                    safe_len = len(stream_buffer) - (len(end_tag) - 1)
                                    if safe_len > 0:
                                        chunk_to_send = stream_buffer[:safe_len]
                                        thought_buffer += chunk_to_send
                                        yield StreamEvent("thought_delta", {
                                            "type": "thought_delta",
                                            "content": chunk_to_send
                                        }).to_sse()
                                        stream_buffer = stream_buffer[safe_len:]
                                    break
                            else:
                                # Look for starting tag
                                start_idx = stream_buffer.find(start_tag)
                                if start_idx != -1:
                                    # Found start of thought
                                    content_chunk = stream_buffer[:start_idx]
                                    if content_chunk:
                                        content_buffer += content_chunk
                                        if not content_started:
                                            yield StreamEvent("content_start", {"type": "content_start"}).to_sse()
                                            content_started = True
                                        yield StreamEvent("content_delta", {
                                            "type": "content_delta",
                                            "content": content_chunk
                                        }).to_sse()

                                    yield StreamEvent("thought_start", {"type": "thought_start"}).to_sse()
                                    in_thought = True
                                    stream_buffer = stream_buffer[start_idx + len(start_tag):]
                                else:
                                    # No start tag yet
                                    safe_len = len(stream_buffer) - (len(start_tag) - 1)
                                    if safe_len > 0:
                                        chunk_to_send = stream_buffer[:safe_len]
                                        content_buffer += chunk_to_send
                                        if not content_started:
                                            yield StreamEvent("content_start", {"type": "content_start"}).to_sse()
                                            content_started = True
                                        yield StreamEvent("content_delta", {
                                            "type": "content_delta",
                                            "content": chunk_to_send
                                        }).to_sse()
                                        stream_buffer = stream_buffer[safe_len:]
                                    break

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

            # Flush remaining buffer
            if stream_buffer:
                if in_thought:
                    thought_buffer += stream_buffer
                    yield StreamEvent("thought_delta", {
                        "type": "thought_delta",
                        "content": stream_buffer
                    }).to_sse()
                else:
                    content_buffer += stream_buffer
                    if not content_started:
                        yield StreamEvent("content_start", {"type": "content_start"}).to_sse()
                        content_started = True
                    yield StreamEvent("content_delta", {
                        "type": "content_delta",
                        "content": stream_buffer
                    }).to_sse()

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
                    thought=thought_buffer if thought_buffer else None,
                    search_results=captured_search_results,
                    search_query=captured_search_query,
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
