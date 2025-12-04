"""Chat endpoints with SSE streaming."""

import json
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.dependencies import (
    get_history_service,
    get_llm_client,
    get_session_manager,
    validate_session,
)
from app.models.domain.message import Message
from app.models.schemas.chat import ChatRequest, ChatResponse, RegenerateRequest
from app.services.image.converter import ImageConverter
from app.services.image.processor import ImageValidationError
from app.services.llm.client import VLLMClient
from app.services.llm.message_builder import MessageBuilder
from app.services.llm.streaming import SSEStreamHandler, StreamResult
from app.services.session.history import ChatHistoryService
from app.services.session.manager import SessionManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat")


# Tool definition for image search (OpenAI-compatible format)
IMAGE_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_images",
        "description": "Search for images on the internet. Use when user asks for images, pictures, photos, or visual examples.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for images"
                }
            },
            "required": ["query"]
        }
    }
}

TOOLS = [IMAGE_SEARCH_TOOL]


def build_current_user_message(content: str, image_urls: list[str]) -> dict:
    """Build the current user message with optional image for vLLM."""
    if not image_urls:
        return {"role": "user", "content": content}

    # Multimodal format: image first, then text
    message_content = []
    for url in image_urls:
        message_content.append({
            "type": "image_url",
            "image_url": {"url": url},
        })
    message_content.append({"type": "text", "text": content})

    return {"role": "user", "content": message_content}


@router.post("")
async def chat_stream(
    request: ChatRequest,
    session_id: Annotated[str, Depends(validate_session)],
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
    history_service: Annotated[ChatHistoryService, Depends(get_history_service)],
    llm_client: Annotated[VLLMClient, Depends(get_llm_client)],
):
    """
    Send a message and receive streaming response via SSE.

    The response is a text/event-stream with the following events:
    - start: Stream initialized
    - content_start: Main response started
    - content_delta: Response content chunk
    - content_end: Response complete
    - images: Image search results (when tool is used)
    - done: Stream finished
    - error: Error occurred
    """
    settings = get_settings()
    request_id = str(uuid.uuid4())
    converter = ImageConverter()

    # Process images if provided (for LLM request only, not stored)
    image_urls = []
    has_image = False

    if request.images:
        for i, img in enumerate(request.images):
            try:
                data_url = converter.to_data_url(img.data, img.media_type)
                image_urls.append(data_url)
                has_image = True
            except ImageValidationError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": e.message,
                            "details": {"field": f"images[{i}]", "reason": e.message},
                        }
                    },
                )

    # Save user message to history (text only, note if images were attached)
    user_content = request.message
    if has_image:
        image_count = len(image_urls)
        image_label = "Image" if image_count == 1 else f"{image_count} images"
        user_content = f"[{image_label} attached]\n{request.message}"

    user_message = Message(
        role="user",
        content=user_content,
        session_id=session_id,
    )
    await history_service.append_message(
        session_id,
        user_message,
        settings.session_ttl_seconds,
    )

    # Get conversation history (text only)
    history = await history_service.get_context_messages(session_id)

    # Build LLM messages: history (text) + current message (with image if present)
    llm_messages = MessageBuilder.build_messages(history[:-1])  # Exclude current msg
    llm_messages.append(build_current_user_message(request.message, image_urls))

    # Holder to capture streaming result for persistence
    result_holder: list[StreamResult] = []

    async def generate():
        """Generate SSE events from LLM stream."""
        try:
            # Get token stream from LLM
            # Disable tools when image is attached - forces LLM to describe the image
            # instead of being tempted to call search_images
            token_generator = llm_client.chat_completion_stream(
                messages=llm_messages,
                max_tokens=request.max_tokens or settings.vllm_max_tokens,
                temperature=request.temperature or 0.7,
                tools=None if has_image else TOOLS,
                tool_choice=None if has_image else "auto",
            )

            # Stream response, capturing result
            async for sse_chunk in SSEStreamHandler.stream_response(
                token_generator, request_id, result_holder
            ):
                yield sse_chunk

            # After streaming completes, save assistant message to history
            if result_holder:
                stream_result = result_holder[0]
                assistant_message = Message(
                    role="assistant",
                    content=stream_result.content,
                    search_results=stream_result.search_results,
                    search_query=stream_result.search_query,
                    session_id=session_id,
                )
                await history_service.append_message(
                    session_id,
                    assistant_message,
                    settings.session_ttl_seconds,
                )
                # Update session message count (user + assistant = 2)
                await session_manager.increment_message_count(session_id, 2)

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': str(e), 'code': 'LLM_ERROR'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
        },
    )


@router.post("/sync", response_model=ChatResponse)
async def chat_sync(
    request: ChatRequest,
    session_id: Annotated[str, Depends(validate_session)],
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
    history_service: Annotated[ChatHistoryService, Depends(get_history_service)],
    llm_client: Annotated[VLLMClient, Depends(get_llm_client)],
):
    """
    Send a message and receive complete response (non-streaming).

    Alternative to SSE streaming for simpler clients.
    """
    settings = get_settings()
    request_id = str(uuid.uuid4())
    converter = ImageConverter()

    # Process images if provided (for LLM request only, not stored)
    image_urls = []
    has_image = False

    if request.images:
        for i, img in enumerate(request.images):
            try:
                data_url = converter.to_data_url(img.data, img.media_type)
                image_urls.append(data_url)
                has_image = True
            except ImageValidationError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": e.message,
                            "details": {"field": f"images[{i}]", "reason": e.message},
                        }
                    },
                )

    # Save user message to history (text only, note if images were attached)
    user_content = request.message
    if has_image:
        image_count = len(image_urls)
        image_label = "Image" if image_count == 1 else f"{image_count} images"
        user_content = f"[{image_label} attached]\n{request.message}"

    user_message = Message(
        role="user",
        content=user_content,
        session_id=session_id,
    )
    await history_service.append_message(
        session_id,
        user_message,
        settings.session_ttl_seconds,
    )

    # Get conversation history (text only)
    history = await history_service.get_context_messages(session_id)

    # Build LLM messages: history (text) + current message (with image if present)
    llm_messages = MessageBuilder.build_messages(history[:-1])
    llm_messages.append(build_current_user_message(request.message, image_urls))

    try:
        # Get complete response
        result = await llm_client.chat_completion(
            messages=llm_messages,
            max_tokens=request.max_tokens or settings.vllm_max_tokens,
            temperature=request.temperature or 0.7,
        )

        # Create and save assistant message
        assistant_message = Message(
            role="assistant",
            content=result["content"],
            session_id=session_id,
        )
        await history_service.append_message(
            session_id,
            assistant_message,
            settings.session_ttl_seconds,
        )

        # Update session message count
        await session_manager.increment_message_count(session_id, 2)

        return ChatResponse(
            request_id=request_id,
            session_id=session_id,
            content=result["content"],
            usage={
                "prompt_tokens": result["usage"]["prompt_tokens"],
                "completion_tokens": result["usage"]["completion_tokens"],
            } if result.get("usage") else None,
        )

    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "LLM_ERROR",
                    "message": f"Failed to get response from LLM: {str(e)}",
                }
            },
        )


@router.post("/regenerate")
async def regenerate_response(
    request: RegenerateRequest,
    session_id: Annotated[str, Depends(validate_session)],
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
    history_service: Annotated[ChatHistoryService, Depends(get_history_service)],
    llm_client: Annotated[VLLMClient, Depends(get_llm_client)],
):
    """
    Regenerate an AI response.

    Removes the specified AI message and generates a new response
    based on the preceding conversation context.
    """
    settings = get_settings()
    request_id = str(uuid.uuid4())

    # Get current history
    messages = await history_service.get_history(session_id)

    # Find the AI message to regenerate
    ai_index = None
    for i, msg in enumerate(messages):
        if msg.id == request.message_id:
            ai_index = i
            break

    if ai_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "MESSAGE_NOT_FOUND", "message": "Message not found"}},
        )

    if messages[ai_index].role != "assistant":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_MESSAGE", "message": "Can only regenerate assistant messages"}},
        )

    if ai_index == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "NO_CONTEXT", "message": "No preceding user message found"}},
        )

    # Truncate at the AI message (removes it, keeps user message before it)
    await history_service.truncate_at_message(
        session_id,
        request.message_id,
        settings.session_ttl_seconds,
    )

    # Get updated history for LLM context
    history = await history_service.get_context_messages(session_id)
    llm_messages = MessageBuilder.build_messages(history)

    # Holder to capture streaming result
    result_holder: list[StreamResult] = []

    async def generate():
        """Generate SSE events from LLM stream."""
        try:
            token_generator = llm_client.chat_completion_stream(
                messages=llm_messages,
                max_tokens=settings.vllm_max_tokens,
                temperature=0.7,
                tools=TOOLS,
                tool_choice="auto",
            )

            async for sse_chunk in SSEStreamHandler.stream_response(
                token_generator, request_id, result_holder
            ):
                yield sse_chunk

            # Save new assistant message
            if result_holder:
                stream_result = result_holder[0]
                assistant_message = Message(
                    role="assistant",
                    content=stream_result.content,
                    search_results=stream_result.search_results,
                    search_query=stream_result.search_query,
                    session_id=session_id,
                )
                await history_service.append_message(
                    session_id,
                    assistant_message,
                    settings.session_ttl_seconds,
                )
                await session_manager.increment_message_count(session_id, 1)

        except Exception as e:
            logger.error(f"Regenerate stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': str(e), 'code': 'LLM_ERROR'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
        },
    )
