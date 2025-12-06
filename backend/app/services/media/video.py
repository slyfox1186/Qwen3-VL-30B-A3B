"""Video processing service.

Supports:
- Video format detection and validation
- Frame extraction at intervals or key frames
- Thumbnail generation
- Duration and metadata extraction
"""

import base64
import logging
import subprocess
from dataclasses import dataclass
from io import BytesIO
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    """Information about a video file."""

    format: str
    mime_type: str
    duration_seconds: float
    width: int
    height: int
    fps: float | None = None
    size_bytes: int = 0


@dataclass
class ExtractedFrame:
    """A frame extracted from video."""

    timestamp: float
    image_bytes: bytes
    width: int
    height: int


class VideoProcessingError(Exception):
    """Raised when video processing fails."""

    pass


class VideoProcessor:
    """
    Processes video files for frame extraction and analysis.

    Features:
    - Format detection (mp4, webm, mov, avi)
    - Duration and metadata extraction via ffprobe
    - Frame extraction at intervals
    - Key frame extraction
    - Thumbnail generation
    """

    MIME_TYPES = {
        "mp4": "video/mp4",
        "webm": "video/webm",
        "mov": "video/quicktime",
        "avi": "video/x-msvideo",
        "mkv": "video/x-matroska",
    }

    def __init__(
        self,
        max_duration_seconds: int = 300,  # 5 minutes
        max_size_bytes: int = 100 * 1024 * 1024,  # 100MB
        default_frame_interval: float = 5.0,  # seconds
        max_frames: int = 20,
    ):
        self._max_duration = max_duration_seconds
        self._max_size = max_size_bytes
        self._frame_interval = default_frame_interval
        self._max_frames = max_frames

    def _detect_format(self, data: bytes) -> str | None:
        """Detect video format from magic bytes."""
        if len(data) < 12:
            return None

        # Check MP4/MOV (ftyp box)
        if data[4:8] == b"ftyp":
            brand = data[8:12].decode("ascii", errors="ignore").lower()
            if "qt" in brand or "mov" in brand:
                return "mov"
            return "mp4"

        # Check WebM/MKV (EBML header)
        if data[:4] == b"\x1a\x45\xdf\xa3":
            # Need to check further to distinguish WebM from MKV
            if b"webm" in data[:100].lower():
                return "webm"
            return "mkv"

        # Check AVI (RIFF + AVI)
        if data[:4] == b"RIFF" and data[8:12] == b"AVI ":
            return "avi"

        return None

    def get_info(self, video_bytes: bytes) -> VideoInfo:
        """
        Get information about a video file.

        Args:
            video_bytes: Raw video bytes

        Returns:
            VideoInfo with format, duration, dimensions, etc.

        Raises:
            VideoProcessingError: If video is invalid
        """
        if len(video_bytes) > self._max_size:
            raise VideoProcessingError(
                f"Video size {len(video_bytes) / 1024 / 1024:.1f}MB "
                f"exceeds maximum {self._max_size / 1024 / 1024:.0f}MB"
            )

        format = self._detect_format(video_bytes)
        if not format:
            raise VideoProcessingError("Unsupported or unrecognized video format")

        mime_type = self.MIME_TYPES.get(format, f"video/{format}")

        # Get metadata using ffprobe
        metadata = self._get_metadata(video_bytes)

        if metadata.get("duration", 0) > self._max_duration:
            raise VideoProcessingError(
                f"Video duration {metadata['duration']:.0f}s "
                f"exceeds maximum {self._max_duration}s"
            )

        return VideoInfo(
            format=format,
            mime_type=mime_type,
            duration_seconds=metadata.get("duration", 0.0),
            width=metadata.get("width", 0),
            height=metadata.get("height", 0),
            fps=metadata.get("fps"),
            size_bytes=len(video_bytes),
        )

    def _get_metadata(self, video_bytes: bytes) -> dict[str, Any]:
        """Get video metadata using ffprobe."""
        metadata: dict[str, Any] = {}

        try:
            with NamedTemporaryFile(suffix=".video", delete=True) as tmp:
                tmp.write(video_bytes)
                tmp.flush()

                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v", "quiet",
                        "-show_entries",
                        "format=duration:stream=width,height,r_frame_rate",
                        "-of", "csv=p=0",
                        tmp.name,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    for line in lines:
                        parts = line.split(",")
                        if len(parts) >= 3:
                            # Stream info: width,height,fps
                            try:
                                metadata["width"] = int(parts[0])
                                metadata["height"] = int(parts[1])
                                # Parse fps fraction (e.g., "30/1")
                                if "/" in parts[2]:
                                    num, den = parts[2].split("/")
                                    metadata["fps"] = float(num) / float(den)
                            except (ValueError, ZeroDivisionError):
                                pass
                        elif len(parts) == 1:
                            # Duration
                            try:
                                metadata["duration"] = float(parts[0])
                            except ValueError:
                                pass

        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"ffprobe metadata extraction failed: {e}")

        return metadata

    def extract_frames(
        self,
        video_bytes: bytes,
        interval_seconds: float | None = None,
        max_frames: int | None = None,
    ) -> list[ExtractedFrame]:
        """
        Extract frames from video at regular intervals.

        Args:
            video_bytes: Raw video bytes
            interval_seconds: Time between frames (default: auto)
            max_frames: Maximum number of frames to extract

        Returns:
            List of ExtractedFrame objects
        """
        info = self.get_info(video_bytes)
        max_frames = max_frames or self._max_frames

        # Calculate interval to get desired number of frames
        if interval_seconds is None:
            if info.duration_seconds > 0:
                interval_seconds = info.duration_seconds / min(max_frames, 10)
            else:
                interval_seconds = self._frame_interval

        frames: list[ExtractedFrame] = []

        try:
            with NamedTemporaryFile(suffix=".video", delete=True) as tmp:
                tmp.write(video_bytes)
                tmp.flush()

                with TemporaryDirectory() as tmpdir:
                    # Extract frames using ffmpeg
                    result = subprocess.run(
                        [
                            "ffmpeg",
                            "-i", tmp.name,
                            "-vf", f"fps=1/{interval_seconds}",
                            "-frames:v", str(max_frames),
                            "-q:v", "2",
                            f"{tmpdir}/frame_%04d.jpg",
                        ],
                        capture_output=True,
                        timeout=60,
                    )

                    if result.returncode != 0:
                        logger.warning(f"ffmpeg frame extraction failed: {result.stderr}")
                        return frames

                    # Load extracted frames
                    import os
                    frame_files = sorted(
                        [f for f in os.listdir(tmpdir) if f.startswith("frame_")]
                    )

                    for i, fname in enumerate(frame_files[:max_frames]):
                        frame_path = f"{tmpdir}/{fname}"
                        with open(frame_path, "rb") as f:
                            frame_bytes = f.read()

                        with Image.open(BytesIO(frame_bytes)) as img:
                            frames.append(ExtractedFrame(
                                timestamp=i * interval_seconds,
                                image_bytes=frame_bytes,
                                width=img.width,
                                height=img.height,
                            ))

        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Frame extraction failed: {e}")

        return frames

    def generate_thumbnail(
        self,
        video_bytes: bytes,
        size: tuple[int, int] = (320, 180),
        timestamp: float = 0.0,
    ) -> bytes | None:
        """
        Generate a thumbnail from video.

        Args:
            video_bytes: Raw video bytes
            size: Thumbnail dimensions (width, height)
            timestamp: Time position in seconds

        Returns:
            Thumbnail JPEG bytes or None on failure
        """
        try:
            with NamedTemporaryFile(suffix=".video", delete=True) as tmp:
                tmp.write(video_bytes)
                tmp.flush()

                with NamedTemporaryFile(suffix=".jpg", delete=True) as thumb:
                    result = subprocess.run(
                        [
                            "ffmpeg",
                            "-ss", str(timestamp),
                            "-i", tmp.name,
                            "-vframes", "1",
                            "-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease",
                            "-q:v", "2",
                            "-y",
                            thumb.name,
                        ],
                        capture_output=True,
                        timeout=30,
                    )

                    if result.returncode == 0:
                        thumb.seek(0)
                        return thumb.read()

        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Thumbnail generation failed: {e}")

        return None

    def to_base64(self, video_bytes: bytes) -> str:
        """Convert video bytes to base64 string."""
        return base64.b64encode(video_bytes).decode("utf-8")

    def from_base64(self, base64_data: str) -> bytes:
        """Decode base64 video data."""
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]

        try:
            return base64.b64decode(base64_data)
        except Exception as e:
            raise VideoProcessingError(f"Invalid base64 encoding: {e}") from e


# Global instance
_video_processor: VideoProcessor | None = None


def get_video_processor() -> VideoProcessor:
    """Get or create the global video processor."""
    global _video_processor
    if _video_processor is None:
        _video_processor = VideoProcessor()
    return _video_processor
