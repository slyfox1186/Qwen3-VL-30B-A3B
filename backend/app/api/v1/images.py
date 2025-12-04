"""Image proxy endpoint to bypass CORS restrictions."""

import asyncio
import base64
import logging
from urllib.parse import urlparse

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


async def fetch_image_with_curl(url: str, referer: str, timeout: float) -> bytes:
    """Fetch image using curl subprocess for better compatibility."""
    cmd = [
        "curl",
        "-sS",  # Silent but show errors
        "-L",  # Follow redirects
        "--max-time", str(int(timeout)),
        "--max-filesize", str(MAX_IMAGE_SIZE),
        "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0",
        "-H", "Accept: image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5",
        "-H", f"Referer: {referer}",
        url,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await asyncio.wait_for(
        proc.communicate(),
        timeout=timeout + 5,  # Extra buffer for process overhead
    )

    if proc.returncode != 0:
        error_msg = stderr.decode().strip() if stderr else f"curl exit code {proc.returncode}"
        raise RuntimeError(error_msg)

    return stdout


@router.post("/proxy", response_model=ImageProxyResponse)
async def proxy_image(request: ImageProxyRequest):
    """
    Fetch an image from an external URL and return as base64 data URL.

    This endpoint bypasses CORS restrictions by fetching the image server-side.
    """
    url = str(request.url)

    # Extract origin from URL for Referer header (prevents hotlink blocking)
    parsed = urlparse(url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"
    logger.info(f"Proxying image from {url} with referer {referer}")

    try:
        image_bytes = await fetch_image_with_curl(url, referer, FETCH_TIMEOUT)

        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "IMAGE_TOO_LARGE", "message": "Image exceeds 10MB"}},
            )

        if len(image_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": {"code": "EMPTY_RESPONSE", "message": "Empty response from server"}},
            )

    except TimeoutError:
        logger.warning(f"Timeout fetching image: {url}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": {"code": "FETCH_TIMEOUT", "message": "Image fetch timed out"}},
        )
    except RuntimeError as e:
        error_str = str(e).lower()
        logger.warning(f"Curl error fetching image {url}: {e}")

        # Parse curl error messages
        if "403" in error_str or "forbidden" in error_str:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FETCH_FAILED", "message": "Access denied (HTTP 403)"}},
            )
        elif "404" in error_str or "not found" in error_str:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Image not found (HTTP 404)"}},
            )
        elif "timeout" in error_str or "timed out" in error_str:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"error": {"code": "FETCH_TIMEOUT", "message": "Image fetch timed out"}},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": {"code": "FETCH_FAILED", "message": f"Failed to fetch image: {e}"}},
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
