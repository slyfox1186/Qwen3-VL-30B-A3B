"""SSE streaming handler with <think> tag parsing."""

import json
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class StreamState(Enum):
    """Current state of the stream parser."""

    INITIAL = "initial"
    IN_THINKING = "in_thinking"
    IN_CONTENT = "in_content"
    DONE = "done"


@dataclass
class StreamEvent:
    """SSE event data structure."""

    event: str
    data: dict

    def to_sse(self) -> str:
        """Format as SSE string."""
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


@dataclass
class ThinkingParser:
    """
    Parses <think>...</think> tags from streaming tokens.

    The model outputs thinking in <think> tags:
    <think>Let me analyze this...</think>The answer is...
    """

    state: StreamState = StreamState.INITIAL
    thinking_buffer: str = ""
    content_buffer: str = ""
    token_buffer: str = ""

    # Tag patterns
    THINK_OPEN = "<think>"
    THINK_CLOSE = "</think>"

    def process_token(self, token: str) -> list[StreamEvent]:
        """
        Process a token and emit appropriate events.

        Args:
            token: Raw token from LLM

        Returns:
            List of StreamEvent objects to emit
        """
        events = []
        self.token_buffer += token

        while self.token_buffer:
            if self.state == StreamState.INITIAL:
                events.extend(self._handle_initial())
            elif self.state == StreamState.IN_THINKING:
                events.extend(self._handle_thinking())
            elif self.state == StreamState.IN_CONTENT:
                events.extend(self._handle_content())
            else:
                break

            # Break if we didn't consume anything (waiting for more tokens)
            if not events and self.token_buffer:
                # Check if we're waiting for a potential tag
                if self._might_be_tag():
                    break
                # Otherwise emit what we have
                if self.state == StreamState.IN_THINKING:
                    events.append(self._emit_thinking_delta(self.token_buffer))
                    self.token_buffer = ""
                elif self.state == StreamState.IN_CONTENT:
                    events.append(self._emit_content_delta(self.token_buffer))
                    self.token_buffer = ""
                break

        return events

    def _might_be_tag(self) -> bool:
        """Check if buffer might be start of a tag."""
        if not self.token_buffer:
            return False

        # Check for partial <think> or </think>
        for tag in [self.THINK_OPEN, self.THINK_CLOSE]:
            for i in range(1, len(tag)):
                if self.token_buffer.endswith(tag[:i]):
                    return True
        return False

    def _handle_initial(self) -> list[StreamEvent]:
        """Handle initial state - looking for <think> or content."""
        events = []

        # Look for <think> tag
        if self.THINK_OPEN in self.token_buffer:
            idx = self.token_buffer.index(self.THINK_OPEN)

            # Emit any content before the tag
            if idx > 0:
                pre_content = self.token_buffer[:idx]
                events.append(StreamEvent("content_start", {"type": "content_start"}))
                events.append(self._emit_content_delta(pre_content))
                self.state = StreamState.IN_CONTENT

            # Start thinking mode
            self.token_buffer = self.token_buffer[idx + len(self.THINK_OPEN):]
            events.append(StreamEvent("thinking_start", {"type": "thinking_start"}))
            self.state = StreamState.IN_THINKING

        elif not self._might_be_tag():
            # No tag coming, start content mode
            events.append(StreamEvent("content_start", {"type": "content_start"}))
            events.append(self._emit_content_delta(self.token_buffer))
            self.token_buffer = ""
            self.state = StreamState.IN_CONTENT

        return events

    def _handle_thinking(self) -> list[StreamEvent]:
        """Handle thinking state - looking for </think>."""
        events = []

        if self.THINK_CLOSE in self.token_buffer:
            idx = self.token_buffer.index(self.THINK_CLOSE)

            # Emit thinking content before close tag
            if idx > 0:
                thinking = self.token_buffer[:idx]
                events.append(self._emit_thinking_delta(thinking))

            # End thinking, start content
            self.token_buffer = self.token_buffer[idx + len(self.THINK_CLOSE):]
            events.append(StreamEvent("thinking_end", {"type": "thinking_end"}))
            events.append(StreamEvent("content_start", {"type": "content_start"}))
            self.state = StreamState.IN_CONTENT

        elif not self._might_be_tag():
            # Emit thinking delta
            events.append(self._emit_thinking_delta(self.token_buffer))
            self.token_buffer = ""

        return events

    def _handle_content(self) -> list[StreamEvent]:
        """Handle content state - emit content tokens."""
        events = []

        if self.token_buffer:
            events.append(self._emit_content_delta(self.token_buffer))
            self.token_buffer = ""

        return events

    def _emit_thinking_delta(self, content: str) -> StreamEvent:
        """Emit thinking delta event."""
        self.thinking_buffer += content
        return StreamEvent("thinking_delta", {
            "type": "thinking_delta",
            "content": content,
        })

    def _emit_content_delta(self, content: str) -> StreamEvent:
        """Emit content delta event."""
        self.content_buffer += content
        return StreamEvent("content_delta", {
            "type": "content_delta",
            "content": content,
        })

    def finalize(self) -> list[StreamEvent]:
        """Finalize parsing and emit remaining events."""
        events = []

        # Emit any remaining buffer
        if self.token_buffer:
            if self.state == StreamState.IN_THINKING:
                events.append(self._emit_thinking_delta(self.token_buffer))
                events.append(StreamEvent("thinking_end", {"type": "thinking_end"}))
            elif self.state in (StreamState.IN_CONTENT, StreamState.INITIAL):
                if self.state == StreamState.INITIAL:
                    events.append(StreamEvent("content_start", {"type": "content_start"}))
                events.append(self._emit_content_delta(self.token_buffer))

            self.token_buffer = ""

        # End content if we were in content mode
        if self.state in (StreamState.IN_CONTENT, StreamState.INITIAL):
            events.append(StreamEvent("content_end", {"type": "content_end"}))

        self.state = StreamState.DONE
        return events

    def get_results(self) -> tuple[str, str]:
        """Get final thinking and content buffers."""
        return self.thinking_buffer, self.content_buffer


@dataclass
class StreamResult:
    """Result from streaming with accumulated content."""

    thinking: str
    content: str
    search_results: list[dict] | None = None
    search_query: str | None = None


class SSEStreamHandler:
    """
    Handles SSE streaming with <think> tag parsing.

    Wraps LLM token stream and emits properly formatted SSE events.
    """

    @staticmethod
    async def stream_response(
        token_generator: AsyncGenerator[dict[str, Any], None],
        request_id: str,
        result_holder: list[StreamResult] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream response with thinking tag parsing and native vLLM tool call handling.

        Args:
            token_generator: Async generator yielding dicts with 'type' and data
            request_id: Request identifier
            result_holder: Optional list to store final StreamResult (for caller to retrieve)

        Yields:
            SSE formatted strings
        """
        from app.services.web_access import get_web_access_service

        parser = ThinkingParser()
        web_service = get_web_access_service()

        # Tool call accumulation (vLLM streams tool calls in chunks)
        tool_calls: dict[int, dict] = {}  # index -> {name, arguments}

        # Store search results for persistence
        captured_search_results: list[dict] | None = None
        captured_search_query: str | None = None

        # Emit start event
        yield StreamEvent("start", {
            "type": "start",
            "request_id": request_id,
        }).to_sse()

        try:
            async for chunk in token_generator:
                chunk_type = chunk.get("type")

                if chunk_type == "content":
                    # Process content through thinking parser
                    content = chunk.get("content", "")
                    events = parser.process_token(content)
                    for event in events:
                        yield event.to_sse()

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

            # Finalize and emit remaining events
            final_events = parser.finalize()
            for event in final_events:
                yield event.to_sse()

            # Get final content
            thinking, content = parser.get_results()

            # Store result for caller if holder provided
            if result_holder is not None:
                result_holder.append(StreamResult(
                    thinking=thinking,
                    content=content,
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


def parse_thinking_from_text(text: str) -> tuple[str | None, str]:
    """
    Parse <think> tags from complete text.

    Args:
        text: Complete response text

    Returns:
        Tuple of (thinking_content, main_content)
    """
    pattern = r"<think>(.*?)</think>"
    match = re.search(pattern, text, re.DOTALL)

    if match:
        thinking = match.group(1).strip()
        content = re.sub(pattern, "", text, flags=re.DOTALL).strip()
        return thinking, content

    return None, text
