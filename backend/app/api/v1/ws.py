"""WebSocket endpoints for bidirectional chat streaming with cancellation."""

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from app.api.v1.chat import build_current_user_message
from app.config import get_settings
from app.dependencies import (
    get_history_service_ws,
    get_llm_client,
    get_session_manager_ws,
)
from app.models.domain.message import Message
from app.services.functions.executor import FunctionExecutor
from app.services.functions.registry import get_function_registry
from app.services.image.converter import ImageConverter
from app.services.image.processor import ImageValidationError
from app.services.llm.client import VLLMClient
from app.services.llm.message_builder import MessageBuilder
from app.services.llm.prompts import get_system_prompt
from app.services.llm.token_utils import calculate_max_tokens
from app.services.session.history import ChatHistoryService
from app.services.session.manager import SessionManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws")

# Maximum number of tool call iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 10


class WebSocketChatHandler:
    """
    Handles WebSocket chat connections with bidirectional communication.

    Features:
    - Real-time token streaming with progress updates
    - Cancellation support via client message
    - Progress events with token counts and ETA
    """

    def __init__(
        self,
        websocket: WebSocket,
        session_manager: SessionManager,
        history_service: ChatHistoryService,
        llm_client: VLLMClient,
    ):
        self.websocket = websocket
        self.session_manager = session_manager
        self.history_service = history_service
        self.llm_client = llm_client
        self.settings = get_settings()
        self.converter = ImageConverter()
        self.function_executor = FunctionExecutor(registry=get_function_registry())

        # Cancellation control
        self._cancelled = asyncio.Event()
        self._generation_task: asyncio.Task | None = None

    async def send_event(self, event_type: str, data: dict[str, Any]) -> bool:
        """Send an event to the client. Returns False if connection closed."""
        if self.websocket.client_state != WebSocketState.CONNECTED:
            return False

        try:
            await self.websocket.send_json({
                "type": event_type,
                **data,
            })
            return True
        except Exception as e:
            logger.warning(f"Failed to send WebSocket event: {e}")
            return False

    async def handle_message(self, data: dict[str, Any]) -> None:
        """Handle incoming WebSocket message."""
        msg_type = data.get("type")

        if msg_type == "chat":
            await self._handle_chat_message(data)
        elif msg_type == "cancel":
            await self._handle_cancel()
        elif msg_type == "ping":
            await self.send_event("pong", {"timestamp": data.get("timestamp")})
        else:
            await self.send_event("error", {
                "code": "INVALID_MESSAGE_TYPE",
                "message": f"Unknown message type: {msg_type}",
            })

    async def _handle_cancel(self) -> None:
        """Handle cancellation request from client."""
        logger.info("Received cancellation request")
        self._cancelled.set()

        if self._generation_task and not self._generation_task.done():
            self._generation_task.cancel()
            await self.send_event("cancelled", {
                "message": "Generation cancelled by user",
            })

    async def _handle_chat_message(self, data: dict[str, Any]) -> None:
        """Handle chat message and stream response."""
        session_id = data.get("session_id")
        content = data.get("message", "")
        images_data = data.get("images", [])
        requested_max_tokens = data.get("max_tokens")
        temperature = data.get("temperature", 0.6)

        if not session_id:
            await self.send_event("error", {
                "code": "MISSING_SESSION",
                "message": "session_id is required",
            })
            return

        # Validate session
        session = await self.session_manager.get_session(session_id)
        if not session:
            await self.send_event("error", {
                "code": "INVALID_SESSION",
                "message": "Session not found or expired",
            })
            return

        request_id = str(uuid.uuid4())
        self._cancelled.clear()

        # Process images
        image_urls = []
        has_image = False

        for i, img_data in enumerate(images_data):
            try:
                img_bytes = img_data.get("data", "")
                media_type = img_data.get("media_type")
                data_url = self.converter.to_data_url(img_bytes, media_type)
                image_urls.append(data_url)
                has_image = True
            except ImageValidationError as e:
                await self.send_event("error", {
                    "code": "VALIDATION_ERROR",
                    "message": e.message,
                    "field": f"images[{i}]",
                })
                return

        # Save user message
        user_content = content
        if has_image:
            image_count = len(image_urls)
            image_label = "Image" if image_count == 1 else f"{image_count} images"
            user_content = f"[{image_label} attached]\n{content}"

        user_message = Message(
            role="user",
            content=user_content,
            session_id=session_id,
        )
        await self.history_service.append_message(
            session_id,
            user_message,
            self.settings.session_ttl_seconds,
        )

        # Get history and build context
        history = await self.history_service.get_context_messages(session_id)
        history_without_current = history[:-1]
        history_had_images = any(
            msg.content.startswith("[") and "image" in msg.content.lower()
            for msg in history_without_current
            if msg.role == "user"
        )

        conversation_has_images = has_image or history_had_images
        llm_messages = [{"role": "system", "content": get_system_prompt(has_images=conversation_has_images)}]
        llm_messages.extend(MessageBuilder.build_messages(history_without_current))
        llm_messages.append(
            build_current_user_message(content, image_urls, history_had_images)
        )

        # Calculate safe max_tokens based on prompt size
        max_tokens = calculate_max_tokens(llm_messages, requested_max_tokens=requested_max_tokens)

        # Start generation with cancellation support
        self._generation_task = asyncio.create_task(
            self._stream_response(
                request_id=request_id,
                session_id=session_id,
                llm_messages=llm_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                conversation_has_images=conversation_has_images,
            )
        )

        try:
            await self._generation_task
        except asyncio.CancelledError:
            logger.info(f"[{request_id}] Generation task cancelled")

    async def _stream_response(
        self,
        request_id: str,
        session_id: str,
        llm_messages: list[dict],
        max_tokens: int,
        temperature: float,
        conversation_has_images: bool,
    ) -> None:
        """Stream LLM response with progress updates and tool call handling."""
        await self.send_event("start", {"request_id": request_id})

        token_count = 0
        start_time = asyncio.get_event_loop().time()
        progress_interval = 50  # Send progress every N tokens

        # Get tools from function registry (includes memory tools)
        registry = get_function_registry()
        tools = registry.get_openai_tools() if not conversation_has_images else None

        # Track overall state across tool iterations
        final_content_buffer = ""
        final_thought_buffer = ""
        content_started = False

        try:
            # Tool call loop - model may call tools multiple times
            iteration = 0
            while iteration < MAX_TOOL_ITERATIONS:
                iteration += 1

                token_generator = self.llm_client.chat_completion_stream(
                    messages=llm_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=tools,
                    tool_choice="auto" if tools else None,
                )

                # Buffer for this iteration
                content_buffer = ""

                # Tool call accumulation
                tool_calls: dict[int, dict] = {}  # index -> {id, name, arguments}
                has_tool_calls = False

                async for chunk in token_generator:
                    # Check for cancellation
                    if self._cancelled.is_set():
                        logger.info(f"[{request_id}] Cancellation detected during streaming")
                        break

                    chunk_type = chunk.get("type")
                    chunk_content = chunk.get("content", "")

                    # Handle tool calls
                    if chunk_type == "tool_call":
                        has_tool_calls = True
                        tc = chunk.get("tool_call", {})
                        idx = tc.get("index", 0)

                        if idx not in tool_calls:
                            tool_calls[idx] = {
                                "id": tc.get("id"),
                                "name": None,
                                "arguments": "",
                            }

                        func_data = tc.get("function", {})
                        if func_data.get("name"):
                            tool_calls[idx]["name"] = func_data["name"]
                        if func_data.get("arguments"):
                            tool_calls[idx]["arguments"] += func_data["arguments"]

                        continue

                    # Handle reasoning (thinking) - send as thought_delta
                    if chunk_type == "reasoning":
                        token = chunk_content
                        if not token:
                            continue

                        token_count += 1
                        if token_count % progress_interval == 0:
                            elapsed = asyncio.get_event_loop().time() - start_time
                            tokens_per_sec = token_count / elapsed if elapsed > 0 else 0
                            remaining_tokens = max_tokens - token_count
                            eta = remaining_tokens / tokens_per_sec if tokens_per_sec > 0 else 0
                            await self.send_event("progress", {
                                "tokens_generated": token_count,
                                "max_tokens": max_tokens,
                                "tokens_per_second": round(tokens_per_sec, 1),
                                "eta_seconds": round(eta, 1),
                                "percentage": round((token_count / max_tokens) * 100, 1),
                            })

                        final_thought_buffer += token
                        await self.send_event("thought_delta", {"content": token})

                    # Handle content (response) - send as content_delta
                    elif chunk_type == "content":
                        token = chunk_content
                        if not token:
                            continue

                        token_count += 1
                        if token_count % progress_interval == 0:
                            elapsed = asyncio.get_event_loop().time() - start_time
                            tokens_per_sec = token_count / elapsed if elapsed > 0 else 0
                            remaining_tokens = max_tokens - token_count
                            eta = remaining_tokens / tokens_per_sec if tokens_per_sec > 0 else 0
                            await self.send_event("progress", {
                                "tokens_generated": token_count,
                                "max_tokens": max_tokens,
                                "tokens_per_second": round(tokens_per_sec, 1),
                                "eta_seconds": round(eta, 1),
                                "percentage": round((token_count / max_tokens) * 100, 1),
                            })

                        if not content_started:
                            await self.send_event("content_start", {})
                            content_started = True

                        content_buffer += token
                        await self.send_event("content_delta", {"content": token})

                # Accumulate buffer
                final_content_buffer += content_buffer

                # Process tool calls if any
                if has_tool_calls and tool_calls:
                    logger.info(f"[{request_id}] Processing {len(tool_calls)} tool calls")

                    # Build assistant message with tool calls for context
                    assistant_tool_msg: dict[str, Any] = {"role": "assistant", "content": None}
                    tool_call_list = []
                    for idx in sorted(tool_calls.keys()):
                        tc = tool_calls[idx]
                        if tc["name"] and tc["id"]:
                            tool_call_list.append({
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                },
                            })
                    assistant_tool_msg["tool_calls"] = tool_call_list
                    llm_messages.append(assistant_tool_msg)

                    # Execute each tool and add results
                    for tc_entry in tool_call_list:
                        func_name = tc_entry["function"]["name"]
                        func_args_str = tc_entry["function"]["arguments"]
                        tc_id = tc_entry["id"]

                        try:
                            func_args = json.loads(func_args_str) if func_args_str else {}
                        except json.JSONDecodeError:
                            func_args = {}
                            logger.warning(
                                f"[{request_id}] Failed to parse tool args: {func_args_str}"
                            )

                        logger.info(f"[{request_id}] Executing tool: {func_name}({func_args})")

                        # Execute the function
                        result = await self.function_executor.execute(func_name, func_args)

                        # Format result for LLM
                        if result.success:
                            result_content = json.dumps(result.result, default=str)
                        else:
                            result_content = json.dumps({"error": result.error})

                        # Add tool result message
                        llm_messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": result_content,
                        })

                        logger.info(
                            f"[{request_id}] Tool {func_name} result: "
                            f"success={result.success}, time={result.execution_time_ms:.1f}ms"
                        )

                    # Continue loop to get model's response to tool results
                    continue

                # No tool calls - we're done
                break

            # End content if started
            if content_started:
                await self.send_event("content_end", {})

            # Log final state
            logger.info(
                f"[{request_id}] === STREAM COMPLETE ===\n"
                f"  iterations={iteration}, content_len={len(final_content_buffer)}"
            )

            # Save assistant message
            assistant_message = Message(
                role="assistant",
                content=final_content_buffer,
                session_id=session_id,
            )
            await self.history_service.append_message(
                session_id,
                assistant_message,
                self.settings.session_ttl_seconds,
            )
            await self.session_manager.increment_message_count(session_id, 2)

            # Send final stats
            elapsed = asyncio.get_event_loop().time() - start_time
            await self.send_event("done", {
                "request_id": request_id,
                "tokens_generated": token_count,
                "duration_seconds": round(elapsed, 2),
                "tokens_per_second": round(token_count / elapsed, 1) if elapsed > 0 else 0,
                "cancelled": self._cancelled.is_set(),
            })

        except asyncio.CancelledError:
            await self.send_event("cancelled", {
                "request_id": request_id,
                "tokens_generated": token_count,
                "partial_content": final_content_buffer[:500] if final_content_buffer else None,
            })
            raise

        except Exception as e:
            logger.error(f"[{request_id}] WebSocket stream error: {e}")
            await self.send_event("error", {
                "code": "LLM_ERROR",
                "message": str(e),
                "request_id": request_id,
            })


@router.websocket("/chat")
async def websocket_chat(
    websocket: WebSocket,
    session_manager: SessionManager = Depends(get_session_manager_ws),
    history_service: ChatHistoryService = Depends(get_history_service_ws),
    llm_client: VLLMClient = Depends(get_llm_client),
):
    """
    WebSocket endpoint for bidirectional chat streaming.

    Client messages:
    - {"type": "chat", "session_id": "...", "message": "...", "images": [...]}
    - {"type": "cancel"}
    - {"type": "ping", "timestamp": ...}

    Server events:
    - start: Stream initialized
    - progress: Token count and ETA updates
    - thought_start/thought_delta/thought_end: Thinking process
    - content_start/content_delta/content_end: Response content
    - done: Completion with stats
    - cancelled: User cancelled generation
    - error: Error occurred
    - pong: Response to ping
    """
    await websocket.accept()
    logger.info("WebSocket connection established")

    handler = WebSocketChatHandler(
        websocket=websocket,
        session_manager=session_manager,
        history_service=history_service,
        llm_client=llm_client,
    )

    try:
        while True:
            try:
                data = await websocket.receive_json()
                await handler.handle_message(data)
            except json.JSONDecodeError:
                await handler.send_event("error", {
                    "code": "INVALID_JSON",
                    "message": "Invalid JSON message",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cancel any ongoing generation
        if handler._generation_task and not handler._generation_task.done():
            handler._generation_task.cancel()
