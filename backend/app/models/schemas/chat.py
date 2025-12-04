"""Pydantic schemas for chat API."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.config import get_settings


class ImageInput(BaseModel):
    """Base64 encoded image input."""

    data: str = Field(..., description="Base64 encoded image data")
    media_type: str | None = Field(
        None,
        description="MIME type (auto-detected if not provided)",
    )


class ChatRequest(BaseModel):
    """Chat message request."""

    message: str = Field(..., min_length=1, max_length=32000)
    images: list[ImageInput] | None = Field(
        None,
        description="Optional images for multimodal input",
    )
    max_tokens: int | None = Field(2048, ge=1, le=4096)
    temperature: float | None = Field(0.7, ge=0.0, le=2.0)

    @field_validator("images")
    @classmethod
    def validate_images_count(cls, v):
        if v:
            settings = get_settings()
            max_images = settings.max_images_per_message
            if len(v) > max_images:
                raise ValueError(f"Maximum {max_images} images allowed per message")
        return v


class TokenUsage(BaseModel):
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int


class ChatResponse(BaseModel):
    """Non-streaming chat response."""

    request_id: str
    session_id: str
    content: str
    thought: str | None = None
    usage: TokenUsage | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StreamEvent(BaseModel):
    """SSE stream event data."""

    type: str = Field(
        ...,
        description="Event type: start, thought_start, thought_delta, thought_end, content_start, content_delta, content_end, done, error",
    )
    content: str | None = None
    thought: str | None = None
    request_id: str | None = None
    usage: TokenUsage | None = None
    error: str | None = None
    code: str | None = None


class RegenerateRequest(BaseModel):
    """Request to regenerate an AI response."""

    message_id: str = Field(..., description="ID of the AI message to regenerate")
