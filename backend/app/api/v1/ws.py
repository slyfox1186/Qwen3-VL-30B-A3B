"""WebSocket endpoints for bidirectional chat streaming with cancellation."""

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from app.api.v1.chat import (
    TOOLS,
    build_current_user_message,
    get_system_prompt,
)
from app.config import get_settings
from app.dependencies import (
    get_history_service_ws,
    get_llm_client,
    get_session_manager_ws,
)
from app.models.domain.message import Message
from app.services.image.converter import ImageConverter
from app.services.image.processor import ImageValidationError
from app.services.llm.client import VLLMClient
from app.services.llm.message_builder import MessageBuilder
from app.services.session.history import ChatHistoryService
from app.services.session.manager import SessionManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws")


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
        max_tokens = data.get("max_tokens") or self.settings.vllm_max_tokens
        temperature = data.get("temperature", 0.7)

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
        llm_messages = [{"role": "system", "content": get_system_prompt(conversation_has_images)}]
        llm_messages.extend(MessageBuilder.build_messages(history_without_current))
        llm_messages.append(
            build_current_user_message(content, image_urls, history_had_images)
        )

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
        """Stream LLM response with progress updates."""
        await self.send_event("start", {"request_id": request_id})

        token_count = 0
        start_time = asyncio.get_event_loop().time()
        progress_interval = 50  # Send progress every N tokens

        try:
            token_generator = self.llm_client.chat_completion_stream(
                messages=llm_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=None if conversation_has_images else TOOLS,
                tool_choice=None if conversation_has_images else "auto",
            )

            # Wrap generator with progress tracking
            async def tracked_generator():
                nonlocal token_count
                async for chunk in token_generator:
                    # Check for cancellation
                    if self._cancelled.is_set():
                        logger.info(f"[{request_id}] Cancellation detected during streaming")
                        break

                    if chunk.get("type") == "content":
                        token_count += 1

                        # Send progress update periodically
                        if token_count % progress_interval == 0:
                            elapsed = asyncio.get_event_loop().time() - start_time
                            tokens_per_sec = token_count / elapsed if elapsed > 0 else 0
                            remaining_tokens = max_tokens - token_count
                            eta_seconds = remaining_tokens / tokens_per_sec if tokens_per_sec > 0 else 0

                            await self.send_event("progress", {
                                "tokens_generated": token_count,
                                "max_tokens": max_tokens,
                                "tokens_per_second": round(tokens_per_sec, 1),
                                "eta_seconds": round(eta_seconds, 1),
                                "percentage": round((token_count / max_tokens) * 100, 1),
                            })

                    yield chunk

            # Use SSEStreamHandler but send via WebSocket
            content_buffer = ""
            thought_buffer = ""
            in_thought = False
            stream_buffer = ""
            start_tag = "<think>"
            end_tag = "</think>"
            content_started = False

            async for chunk in tracked_generator():
                chunk_type = chunk.get("type")

                if chunk_type == "content":
                    token = chunk.get("content", "")
                    if token:
                        stream_buffer += token

                        # Process buffer for tags (same logic as SSEStreamHandler)
                        while stream_buffer:
                            if in_thought:
                                end_idx = stream_buffer.find(end_tag)
                                if end_idx != -1:
                                    thought_chunk = stream_buffer[:end_idx]
                                    if thought_chunk:
                                        thought_buffer += thought_chunk
                                        await self.send_event("thought_delta", {"content": thought_chunk})
                                    await self.send_event("thought_end", {})
                                    in_thought = False
                                    stream_buffer = stream_buffer[end_idx + len(end_tag):]
                                else:
                                    safe_len = len(stream_buffer) - (len(end_tag) - 1)
                                    if safe_len > 0:
                                        chunk_to_send = stream_buffer[:safe_len]
                                        thought_buffer += chunk_to_send
                                        await self.send_event("thought_delta", {"content": chunk_to_send})
                                        stream_buffer = stream_buffer[safe_len:]
                                    break
                            else:
                                start_idx = stream_buffer.find(start_tag)
                                if start_idx != -1:
                                    content_chunk = stream_buffer[:start_idx]
                                    if content_chunk:
                                        content_buffer += content_chunk
                                        if not content_started:
                                            await self.send_event("content_start", {})
                                            content_started = True
                                        await self.send_event("content_delta", {"content": content_chunk})
                                    await self.send_event("thought_start", {})
                                    in_thought = True
                                    stream_buffer = stream_buffer[start_idx + len(start_tag):]
                                else:
                                    safe_len = len(stream_buffer) - (len(start_tag) - 1)
                                    if safe_len > 0:
                                        chunk_to_send = stream_buffer[:safe_len]
                                        content_buffer += chunk_to_send
                                        if not content_started:
                                            await self.send_event("content_start", {})
                                            content_started = True
                                        await self.send_event("content_delta", {"content": chunk_to_send})
                                        stream_buffer = stream_buffer[safe_len:]
                                    break

            # Flush remaining buffer
            if stream_buffer:
                if in_thought:
                    thought_buffer += stream_buffer
                    await self.send_event("thought_delta", {"content": stream_buffer})
                else:
                    content_buffer += stream_buffer
                    if not content_started:
                        await self.send_event("content_start", {})
                        content_started = True
                    await self.send_event("content_delta", {"content": stream_buffer})

            if content_started:
                await self.send_event("content_end", {})

            # Save assistant message
            assistant_message = Message(
                role="assistant",
                content=content_buffer,
                thought=thought_buffer if thought_buffer else None,
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
            # Send partial result on cancellation
            await self.send_event("cancelled", {
                "request_id": request_id,
                "tokens_generated": token_count,
                "partial_content": content_buffer[:500] if content_buffer else None,
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
