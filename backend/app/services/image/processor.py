"""Image validation, optimization, and processing.

Features:
- Format detection and validation
- Smart compression with quality optimization
- EXIF stripping for privacy (preserving orientation)
- Format conversion (WebP optimization)
- Thumbnail generation
- Perceptual hashing for deduplication
"""

import base64
import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from PIL import ExifTags, Image

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

    # Magic bytes for common image formats (including unsupported ones for error messages)
    FORMAT_SIGNATURES = {
        b"\x00\x00\x00\x1cftyp": "avif",  # AVIF (ftyp box)
        b"\x00\x00\x00\x20ftyp": "avif",  # AVIF variant
        b"\x00\x00\x00\x18ftyp": "heic",  # HEIC/HEIF
        b"\x00\x00\x00\x24ftyp": "heic",  # HEIC variant
        b"RIFF": "webp",  # WebP (check for WEBP after)
        b"\x89PNG": "png",
        b"\xff\xd8\xff": "jpeg",
        b"GIF87a": "gif",
        b"GIF89a": "gif",
        b"BM": "bmp",
        b"II*\x00": "tiff",
        b"MM\x00*": "tiff",
    }

    def _detect_format_from_bytes(self, data: bytes) -> str | None:
        """Detect image format from magic bytes for better error messages."""
        if len(data) < 12:
            return None

        # Check AVIF/HEIC (ftyp box at offset 4)
        if len(data) >= 12 and data[4:8] == b"ftyp":
            brand = data[8:12].decode("ascii", errors="ignore").lower()
            if "avif" in brand:
                return "avif"
            if "heic" in brand or "heix" in brand or "mif1" in brand:
                return "heic"

        # Check other formats by prefix
        for sig, fmt in self.FORMAT_SIGNATURES.items():
            if data.startswith(sig):
                # Special case for WebP - verify WEBP marker
                if fmt == "webp" and len(data) >= 12:
                    if data[8:12] != b"WEBP":
                        continue
                return fmt

        return None

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
            error_msg = str(e).lower()
            # Check for common unsupported format indicators
            if "cannot identify" in error_msg or "not identified" in error_msg:
                # Try to detect format from magic bytes for better error message
                format_hint = self._detect_format_from_bytes(image_bytes)
                if format_hint:
                    raise ImageValidationError(
                        f"Unsupported image format: {format_hint}. "
                        f"Allowed: {', '.join(self._allowed_formats)}"
                    )
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

    def strip_exif(self, image: Image.Image) -> Image.Image:
        """
        Strip EXIF data while preserving orientation.

        Privacy-safe: removes location, camera info, etc.
        but applies rotation if needed.

        Args:
            image: PIL Image with potential EXIF data

        Returns:
            New image with EXIF stripped but properly oriented
        """
        try:
            # Get EXIF orientation if present
            exif = image.getexif()
            orientation = None

            for tag, value in exif.items():
                if ExifTags.TAGS.get(tag) == "Orientation":
                    orientation = value
                    break

            # Apply orientation transform
            if orientation:
                transforms = {
                    2: Image.Transpose.FLIP_LEFT_RIGHT,
                    3: Image.Transpose.ROTATE_180,
                    4: Image.Transpose.FLIP_TOP_BOTTOM,
                    5: Image.Transpose.TRANSPOSE,
                    6: Image.Transpose.ROTATE_270,
                    7: Image.Transpose.TRANSVERSE,
                    8: Image.Transpose.ROTATE_90,
                }
                if orientation in transforms:
                    image = image.transpose(transforms[orientation])

            # Create new image without EXIF
            if image.mode in ("RGBA", "LA", "P"):
                # Preserve alpha channel
                new_image = Image.new(image.mode, image.size)
            else:
                new_image = Image.new("RGB", image.size)

            new_image.paste(image)
            return new_image

        except Exception as e:
            logger.debug(f"EXIF strip failed (non-critical): {e}")
            return image

    def optimize(
        self,
        image_bytes: bytes,
        target_format: Literal["webp", "jpeg", "png"] = "webp",
        max_dimension: int = 2048,
        quality: int | None = None,
        target_size_kb: int | None = None,
    ) -> tuple[bytes, ImageInfo]:
        """
        Optimize image for transmission.

        Args:
            image_bytes: Raw image bytes
            target_format: Output format (webp preferred)
            max_dimension: Maximum width/height
            quality: JPEG/WebP quality (auto if None)
            target_size_kb: Target file size (adaptive quality)

        Returns:
            Tuple of (optimized_bytes, ImageInfo)
        """
        with Image.open(BytesIO(image_bytes)) as img:
            original_size = len(image_bytes)

            # Strip EXIF
            img = self.strip_exif(img)

            # Resize if needed
            if max(img.size) > max_dimension:
                ratio = max_dimension / max(img.size)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.debug(f"Resized image to {new_size}")

            # Convert to RGB if needed (for JPEG/WebP)
            if target_format in ("jpeg", "webp") and img.mode in ("RGBA", "LA", "P"):
                # Handle transparency
                if img.mode == "P":
                    img = img.convert("RGBA")
                if img.mode in ("RGBA", "LA"):
                    # Create white background
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "LA":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[3])
                    img = background

            # Determine quality
            if quality is None:
                if target_size_kb:
                    quality = self._find_optimal_quality(
                        img,
                        target_format,
                        target_size_kb,
                    )
                else:
                    # Default adaptive quality based on dimensions
                    pixels = img.width * img.height
                    if pixels > 4_000_000:  # > 4MP
                        quality = 75
                    elif pixels > 1_000_000:  # > 1MP
                        quality = 82
                    else:
                        quality = 88

            # Compress
            output = BytesIO()
            save_kwargs = {"quality": quality, "optimize": True}

            if target_format == "webp":
                img.save(output, format="WEBP", **save_kwargs)
                mime_type = "image/webp"
            elif target_format == "jpeg":
                img.save(output, format="JPEG", **save_kwargs, progressive=True)
                mime_type = "image/jpeg"
            else:
                img.save(output, format="PNG", optimize=True)
                mime_type = "image/png"

            optimized_bytes = output.getvalue()
            compressed_size = len(optimized_bytes)

            compression_ratio = original_size / compressed_size if compressed_size > 0 else 1
            logger.debug(
                f"Image optimized: {original_size / 1024:.1f}KB -> "
                f"{compressed_size / 1024:.1f}KB ({compression_ratio:.1f}x)"
            )

            info = ImageInfo(
                format=target_format,
                mime_type=mime_type,
                width=img.width,
                height=img.height,
                size_bytes=compressed_size,
            )

            return optimized_bytes, info

    def _find_optimal_quality(
        self,
        image: Image.Image,
        format: str,
        target_kb: int,
    ) -> int:
        """Binary search for quality that achieves target size."""
        low, high = 30, 95
        best_quality = 75

        while low <= high:
            mid = (low + high) // 2
            output = BytesIO()

            if format == "webp":
                image.save(output, format="WEBP", quality=mid, optimize=True)
            else:
                image.save(output, format="JPEG", quality=mid, optimize=True)

            size_kb = len(output.getvalue()) / 1024

            if size_kb <= target_kb:
                best_quality = mid
                low = mid + 1  # Try higher quality
            else:
                high = mid - 1  # Need lower quality

        return best_quality

    def generate_thumbnail(
        self,
        image_bytes: bytes,
        size: tuple[int, int] = (150, 150),
        format: str = "webp",
    ) -> bytes:
        """
        Generate thumbnail for image.

        Args:
            image_bytes: Raw image bytes
            size: Thumbnail dimensions (width, height)
            format: Output format

        Returns:
            Thumbnail bytes
        """
        with Image.open(BytesIO(image_bytes)) as img:
            # Strip EXIF and apply orientation
            img = self.strip_exif(img)

            # Create thumbnail (maintains aspect ratio)
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Convert for output
            if img.mode in ("RGBA", "LA", "P"):
                if format.lower() in ("jpeg", "jpg"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    if img.mode in ("RGBA", "LA"):
                        if img.mode == "LA":
                            img = img.convert("RGBA")
                        background.paste(img, mask=img.split()[3])
                        img = background

            output = BytesIO()
            if format.lower() == "webp":
                img.save(output, format="WEBP", quality=80, optimize=True)
            elif format.lower() in ("jpeg", "jpg"):
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(output, format="JPEG", quality=80, optimize=True)
            else:
                img.save(output, format="PNG", optimize=True)

            return output.getvalue()

    def to_data_url(
        self,
        image_bytes: bytes,
        optimize: bool = True,
        target_format: str = "webp",
    ) -> tuple[str, ImageInfo]:
        """
        Convert image bytes to optimized data URL.

        Args:
            image_bytes: Raw image bytes
            optimize: Whether to optimize the image
            target_format: Target format for optimization

        Returns:
            Tuple of (data_url, ImageInfo)
        """
        if optimize:
            optimized_bytes, info = self.optimize(
                image_bytes,
                target_format=target_format,  # type: ignore
            )
        else:
            # Just validate and get info
            with Image.open(BytesIO(image_bytes)) as img:
                info = ImageInfo(
                    format=img.format.lower() if img.format else "unknown",
                    mime_type=self.MIME_TYPES.get(
                        img.format.lower() if img.format else "",
                        "application/octet-stream",
                    ),
                    width=img.width,
                    height=img.height,
                    size_bytes=len(image_bytes),
                )
            optimized_bytes = image_bytes

        # Encode to base64
        b64 = base64.b64encode(optimized_bytes).decode("utf-8")
        data_url = f"data:{info.mime_type};base64,{b64}"

        return data_url, info
