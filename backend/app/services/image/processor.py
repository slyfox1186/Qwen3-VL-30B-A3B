"""Image validation and processing."""

import base64
import logging
from dataclasses import dataclass
from io import BytesIO

from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)


class ImageValidationError(Exception):
    """Raised when image validation fails."""

    def __init__(self, message: str, field: str = "images"):
        self.message = message
        self.field = field
        super().__init__(message)


@dataclass
class ImageInfo:
    """Information about a validated image."""

    format: str
    mime_type: str
    width: int
    height: int
    size_bytes: int


class ImageProcessor:
    """
    Validates and processes images for the vision model.

    Features:
    - Format detection
    - Size validation
    - Dimension extraction
    - Base64 decoding
    """

    MIME_TYPES = {
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }

    def __init__(
        self,
        max_size_bytes: int | None = None,
        allowed_formats: set[str] | None = None,
    ):
        settings = get_settings()
        self._max_size = max_size_bytes or settings.max_image_size_bytes
        self._allowed_formats = allowed_formats or set(settings.allowed_image_formats)

    def validate_and_get_info(
        self,
        base64_data: str,
        provided_media_type: str | None = None,
    ) -> tuple[bytes, ImageInfo]:
        """
        Validate base64 image and return bytes with info.

        Args:
            base64_data: Base64 encoded image (with or without data URL prefix)
            provided_media_type: Optional MIME type hint

        Returns:
            Tuple of (image_bytes, ImageInfo)

        Raises:
            ImageValidationError: If validation fails
        """
        # Remove data URL prefix if present
        if "," in base64_data:
            header, base64_data = base64_data.split(",", 1)

        # Decode base64
        try:
            image_bytes = base64.b64decode(base64_data)
        except Exception as e:
            raise ImageValidationError(f"Invalid base64 encoding: {e}")

        # Check size
        size_bytes = len(image_bytes)
        if size_bytes > self._max_size:
            max_mb = self._max_size / (1024 * 1024)
            actual_mb = size_bytes / (1024 * 1024)
            raise ImageValidationError(
                f"Image size {actual_mb:.1f}MB exceeds maximum {max_mb:.0f}MB"
            )

        # Validate image and detect format using PIL (imghdr is deprecated)
        try:
            with Image.open(BytesIO(image_bytes)) as img:
                img.verify()

            # Re-open to get format and dimensions (verify() can modify state)
            with Image.open(BytesIO(image_bytes)) as img:
                detected_format = img.format.lower() if img.format else None
                width, height = img.size

        except Exception as e:
            raise ImageValidationError(f"Invalid or corrupted image: {e}")

        if not detected_format or detected_format not in self._allowed_formats:
            raise ImageValidationError(
                f"Unsupported image format: {detected_format}. "
                f"Allowed: {', '.join(self._allowed_formats)}"
            )

        mime_type = self.MIME_TYPES.get(detected_format, f"image/{detected_format}")

        info = ImageInfo(
            format=detected_format,
            mime_type=mime_type,
            width=width,
            height=height,
            size_bytes=size_bytes,
        )

        logger.debug(
            f"Validated image: {info.format} {info.width}x{info.height} "
            f"({info.size_bytes / 1024:.1f}KB)"
        )

        return image_bytes, info

    def validate(self, base64_data: str) -> bool:
        """
        Simple validation check.

        Returns True if valid, raises ImageValidationError if not.
        """
        self.validate_and_get_info(base64_data)
        return True
