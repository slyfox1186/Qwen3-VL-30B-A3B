"""Image format conversion utilities."""

import base64
import logging

from app.services.image.processor import ImageProcessor

logger = logging.getLogger(__name__)


class ImageConverter:
    """
    Converts images between formats for vLLM compatibility.

    The vLLM multimodal API expects images as data URLs:
    data:image/jpeg;base64,/9j/4AAQ...
    """

    def __init__(self, processor: ImageProcessor | None = None):
        self._processor = processor or ImageProcessor()

    def to_data_url(
        self,
        base64_data: str,
        media_type: str | None = None,
    ) -> str:
        """
        Convert base64 image to data URL format.

        Args:
            base64_data: Base64 encoded image data
            media_type: Optional MIME type (auto-detected if not provided)

        Returns:
            Data URL string: data:image/jpeg;base64,...

        Raises:
            ImageValidationError: If image is invalid
        """
        # Check if already a data URL
        if base64_data.startswith("data:"):
            # Still validate it
            self._processor.validate(base64_data)
            return base64_data

        # Validate and get info
        image_bytes, info = self._processor.validate_and_get_info(
            base64_data, media_type
        )

        # Use detected or provided MIME type
        mime = media_type or info.mime_type

        # Re-encode to ensure clean base64
        clean_base64 = base64.b64encode(image_bytes).decode("utf-8")

        return f"data:{mime};base64,{clean_base64}"

    def extract_base64(self, data_url_or_base64: str) -> str:
        """
        Extract base64 data from data URL or return as-is.

        Args:
            data_url_or_base64: Either a data URL or raw base64

        Returns:
            Raw base64 string
        """
        if "," in data_url_or_base64 and data_url_or_base64.startswith("data:"):
            return data_url_or_base64.split(",", 1)[1]
        return data_url_or_base64

    def get_mime_type(self, data_url_or_base64: str) -> str:
        """
        Get MIME type from data URL or detect from base64.

        Args:
            data_url_or_base64: Either a data URL or raw base64

        Returns:
            MIME type string
        """
        # Try to extract from data URL header
        if data_url_or_base64.startswith("data:"):
            header = data_url_or_base64.split(",", 1)[0]
            # Format: data:image/jpeg;base64
            mime = header.replace("data:", "").replace(";base64", "")
            if mime:
                return mime

        # Detect from image data
        _, info = self._processor.validate_and_get_info(data_url_or_base64)
        return info.mime_type
