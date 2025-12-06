"""Chat endpoints for sync and structured output (WebSocket handles streaming)."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.dependencies import (
    get_history_service,
    get_llm_client,
    get_schema_registry_dep,
    get_schema_validator,
    get_session_manager,
    validate_session,
)
from app.models.domain.message import Message
from app.models.schemas.chat import ChatRequest, ChatResponse
from app.services.image.converter import ImageConverter
from app.services.image.processor import ImageValidationError
from app.services.llm.client import VLLMClient
from app.services.llm.message_builder import MessageBuilder
from app.services.llm.prompts import get_system_prompt
from app.services.schema.registry import SchemaRegistry
from app.services.schema.validator import SchemaValidator
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




def build_current_user_message(
    content: str, image_urls: list[str], history_had_images: bool = False
) -> dict:
    """Build the current user message with optional images for vLLM.

    Args:
        content: The user's text message
        image_urls: List of image data URLs for the current message
        history_had_images: Whether the conversation history contains prior image references
    """
    if not image_urls:
        return {"role": "user", "content": content}

    # For Qwen-VL models, interleave text references with images for better multi-image handling
    # Format: <context> <image 1 marker> <image> <image 2 marker> <image> ... <user text>
    message_content = []

    # CRITICAL: If history had images, add explicit context to prevent confusion
    # The model cannot see previous images - only current ones
    if history_had_images:
        message_content.append({
            "type": "text",
            "text": (
                "[IMPORTANT: Any images mentioned in the conversation history above are NO LONGER "
                "visible to you. You can ONLY see the image(s) attached to THIS message. "
                "Base your analysis SOLELY on the image(s) shown below, not on any prior descriptions.]\n\n"
            ),
        })

    for idx, url in enumerate(image_urls):
        # Add a text marker before each image to help the model track them
        if len(image_urls) > 1:
            message_content.append({
                "type": "text",
                "text": f"[Current Image {idx + 1} of {len(image_urls)}]:",
            })

        message_content.append({
            "type": "image_url",
            "image_url": {"url": url},
        })

    # Add the user's actual query/instruction
    if len(image_urls) > 1:
        instruction = f"\n\nPlease analyze ALL {len(image_urls)} images above. {content}"
    else:
        instruction = content

    message_content.append({"type": "text", "text": instruction})

    logger.info(
        f"Building multimodal message with {len(image_urls)} images "
        f"(history_had_images={history_had_images})"
    )
    return {"role": "user", "content": message_content}


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

    # Check if prior history (excluding current message) had any image attachments
    history_without_current = history[:-1]
    history_had_images = any(
        msg.content.startswith("[") and "image" in msg.content.lower()
        for msg in history_without_current
        if msg.role == "user"
    )

    # Build LLM messages: system prompt + history (text) + current message (with image if present)
    # Determine if this conversation involves images (current or historical)
    conversation_has_images = has_image or history_had_images

    # Always include system prompt (with image context if conversation has images)
    llm_messages = [{"role": "system", "content": get_system_prompt(has_images=conversation_has_images)}]
    llm_messages.extend(MessageBuilder.build_messages(history_without_current))
    llm_messages.append(
        build_current_user_message(request.message, image_urls, history_had_images)
    )

    try:
        # Get complete response
        result = await llm_client.chat_completion(
            messages=llm_messages,
            max_tokens=request.max_tokens or settings.vllm_max_tokens,
            temperature=request.temperature or 0.6,
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


@router.post("/structured", response_model=ChatResponse)
async def chat_structured(
    request: ChatRequest,
    session_id: Annotated[str, Depends(validate_session)],
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
    history_service: Annotated[ChatHistoryService, Depends(get_history_service)],
    llm_client: Annotated[VLLMClient, Depends(get_llm_client)],
    schema_registry: Annotated[SchemaRegistry, Depends(get_schema_registry_dep)],
    schema_validator: Annotated[SchemaValidator, Depends(get_schema_validator)],
):
    """
    Send a message and receive structured JSON response.

    Enables JSON schema validation with automatic retry for LLM responses.
    Use output_schema in the request to specify the expected response format.

    Available built-in schemas:
    - extraction: Entity extraction with name, type, context
    - classification: Category, confidence, reasoning
    - sentiment: Sentiment analysis with score and aspects
    - summary: Title, summary paragraph, key points
    - qa: Question answering with answer, confidence, sources
    - table: Tabular data with headers and rows
    - code: Code generation with language, code, explanation
    """
    settings = get_settings()
    request_id = str(uuid.uuid4())

    # Validate output_schema is provided
    if not request.output_schema:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "MISSING_SCHEMA",
                    "message": "output_schema is required for structured output endpoint",
                }
            },
        )

    # Get the schema
    output_schema = request.output_schema
    if output_schema.name == "custom":
        if not output_schema.schema_:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_SCHEMA",
                        "message": "Custom schema requires 'schema' field with JSON Schema definition",
                    }
                },
            )
        schema = output_schema.schema_
    else:
        schema = schema_registry.get_schema(output_schema.name)
        if not schema:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "UNKNOWN_SCHEMA",
                        "message": f"Unknown schema: {output_schema.name}. "
                        f"Available: {', '.join(schema_registry.list_builtin_schemas())}",
                    }
                },
            )

    # Save user message to history
    user_message = Message(
        role="user",
        content=request.message,
        session_id=session_id,
    )
    await history_service.append_message(
        session_id,
        user_message,
        settings.session_ttl_seconds,
    )

    # Get conversation history
    history = await history_service.get_context_messages(session_id)
    history_without_current = history[:-1]

    # Build LLM messages with schema instruction in system prompt
    schema_instruction = schema_validator.get_schema_instruction(schema)
    system_prompt = get_system_prompt(has_images=False) + "\n\n" + schema_instruction

    llm_messages = [{"role": "system", "content": system_prompt}]
    llm_messages.extend(MessageBuilder.build_messages(history_without_current))
    llm_messages.append({"role": "user", "content": request.message})

    # Attempt to get valid structured response with retries
    max_retries = output_schema.max_retries if output_schema.strict else 0
    retry_count = 0
    best_response = ""
    validation_errors: list[str] = []
    structured_data = None
    result: dict | None = None

    try:
        for attempt in range(max_retries + 1):
            # Call LLM
            result = await llm_client.chat_completion(
                messages=llm_messages,
                max_tokens=request.max_tokens or settings.vllm_max_tokens,
                temperature=request.temperature or 0.6,
            )

            response_content = result["content"]
            best_response = response_content

            # Validate against schema
            parsed_data, errors = schema_validator.validate(response_content, schema)

            if not errors:
                # Success!
                structured_data = parsed_data
                validation_errors = []
                break

            validation_errors = errors
            retry_count = attempt + 1

            if attempt < max_retries:
                # Generate retry prompt
                logger.info(
                    f"[{request_id}] Structured output validation failed (attempt {attempt + 1}): "
                    f"{len(errors)} errors. Retrying..."
                )

                retry_prompt = schema_validator.generate_retry_prompt(
                    request.message,
                    schema,
                    errors,
                    response_content,
                )

                # Update messages for retry
                llm_messages = [{"role": "system", "content": system_prompt}]
                llm_messages.extend(MessageBuilder.build_messages(history_without_current))
                llm_messages.append({"role": "user", "content": retry_prompt})

        # Save assistant message (use best response even if validation failed)
        assistant_message = Message(
            role="assistant",
            content=best_response,
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
            content=best_response,
            usage={
                "prompt_tokens": result["usage"]["prompt_tokens"],
                "completion_tokens": result["usage"]["completion_tokens"],
            } if result and result.get("usage") else None,
            structured_data=structured_data,
            validation_errors=validation_errors if validation_errors else None,
            retry_count=retry_count if retry_count > 0 else None,
        )

    except Exception as e:
        logger.error(f"Structured chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "LLM_ERROR",
                    "message": f"Failed to get response from LLM: {str(e)}",
                }
            },
        )


@router.get("/schemas")
async def list_schemas(
    schema_registry: Annotated[SchemaRegistry, Depends(get_schema_registry_dep)],
):
    """
    List all available schemas for structured output.

    Returns built-in schemas that can be used with the /chat/structured endpoint.
    """
    builtin = schema_registry.list_builtin_schemas()
    custom = schema_registry.list_custom_schemas()

    return {
        "builtin_schemas": builtin,
        "custom_schemas": custom,
        "usage_example": {
            "output_schema": {
                "name": "extraction",
                "strict": True,
                "max_retries": 2,
            }
        },
    }
