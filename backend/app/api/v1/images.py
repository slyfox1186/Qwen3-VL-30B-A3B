"""Image proxy endpoint to bypass CORS restrictions."""

import base64
import logging

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from app.services.image.processor import ImageProcessor, ImageValidationError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/images")

# Timeout for fetching external images
FETCH_TIMEOUT = 15.0
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB


class ImageProxyRequest(BaseModel):
    """Request to proxy an image from external URL."""

    url: HttpUrl = Field(..., description="URL of the image to fetch")


class ImageProxyResponse(BaseModel):
    """Proxied image as base64 data URL."""

    data_url: str = Field(..., description="Base64 data URL of the image")
    mime_type: str = Field(..., description="Detected MIME type")
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")


@router.post("/proxy", response_model=ImageProxyResponse)
async def proxy_image(request: ImageProxyRequest):
    """
    Fetch an image from an external URL and return as base64 data URL.

    This endpoint bypasses CORS restrictions by fetching the image server-side.
    """
    url = str(request.url)

    try:
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Check content length
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_IMAGE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "IMAGE_TOO_LARGE", "message": "Image exceeds 10MB"}},
                )

            image_bytes = response.content

            if len(image_bytes) > MAX_IMAGE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "IMAGE_TOO_LARGE", "message": "Image exceeds 10MB"}},
                )

    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching image: {url}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": {"code": "FETCH_TIMEOUT", "message": "Image fetch timed out"}},
        )
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error fetching image {url}: {e.response.status_code}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "FETCH_FAILED",
                    "message": f"Failed to fetch image: HTTP {e.response.status_code}",
                }
            },
        )
    except httpx.RequestError as e:
        logger.warning(f"Request error fetching image {url}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "FETCH_FAILED", "message": "Failed to fetch image"}},
        )

    # Validate and get image info
    try:
        processor = ImageProcessor()
        base64_data = base64.b64encode(image_bytes).decode("utf-8")
        _, info = processor.validate_and_get_info(base64_data)
    except ImageValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_IMAGE", "message": e.message}},
        )

    data_url = f"data:{info.mime_type};base64,{base64_data}"

    return ImageProxyResponse(
        data_url=data_url,
        mime_type=info.mime_type,
        width=info.width,
        height=info.height,
    )
