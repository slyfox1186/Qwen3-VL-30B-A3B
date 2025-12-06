"""Audio processing and transcription service.

Supports:
- Audio format detection and validation
- Duration extraction
- Transcription via Whisper-compatible API
- Audio segmentation for long files
"""

import base64
import logging
import subprocess
from dataclasses import dataclass
from io import BytesIO
from tempfile import NamedTemporaryFile
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AudioInfo:
    """Information about an audio file."""

    format: str
    mime_type: str
    duration_seconds: float
    sample_rate: int | None = None
    channels: int | None = None
    size_bytes: int = 0


@dataclass
class TranscriptionResult:
    """Result of audio transcription."""

    text: str
    language: str | None = None
    segments: list[dict[str, Any]] | None = None
    duration_seconds: float = 0.0


class AudioProcessingError(Exception):
    """Raised when audio processing fails."""

    pass


class AudioProcessor:
    """
    Processes audio files for transcription and analysis.

    Features:
    - Format detection (wav, mp3, ogg, flac, m4a)
    - Duration and metadata extraction
    - Transcription via external API
    - Audio segmentation for long files
    """

    MIME_TYPES = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
        "m4a": "audio/mp4",
        "webm": "audio/webm",
    }

    FORMAT_SIGNATURES = {
        b"RIFF": "wav",  # Check for WAVE after
        b"\xff\xfb": "mp3",
        b"\xff\xfa": "mp3",
        b"\xff\xf3": "mp3",
        b"\xff\xf2": "mp3",
        b"ID3": "mp3",
        b"OggS": "ogg",
        b"fLaC": "flac",
    }

    def __init__(
        self,
        max_duration_seconds: int = 600,  # 10 minutes
        max_size_bytes: int = 50 * 1024 * 1024,  # 50MB
        whisper_api_url: str | None = None,
    ):
        self._max_duration = max_duration_seconds
        self._max_size = max_size_bytes
        self._whisper_url = whisper_api_url

    def _detect_format(self, data: bytes) -> str | None:
        """Detect audio format from magic bytes."""
        if len(data) < 12:
            return None

        # Check WAV (RIFF + WAVE)
        if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
            return "wav"

        # Check M4A/MP4 audio (ftyp box)
        if data[4:8] == b"ftyp":
            return "m4a"

        # Check other formats
        for sig, fmt in self.FORMAT_SIGNATURES.items():
            if data.startswith(sig):
                return fmt

        return None

    def get_info(self, audio_bytes: bytes) -> AudioInfo:
        """
        Get information about an audio file.

        Args:
            audio_bytes: Raw audio bytes

        Returns:
            AudioInfo with format, duration, etc.

        Raises:
            AudioProcessingError: If audio is invalid
        """
        if len(audio_bytes) > self._max_size:
            raise AudioProcessingError(
                f"Audio size {len(audio_bytes) / 1024 / 1024:.1f}MB "
                f"exceeds maximum {self._max_size / 1024 / 1024:.0f}MB"
            )

        format = self._detect_format(audio_bytes)
        if not format:
            raise AudioProcessingError("Unsupported or unrecognized audio format")

        mime_type = self.MIME_TYPES.get(format, f"audio/{format}")

        # Try to get duration using ffprobe
        duration = self._get_duration(audio_bytes)

        if duration and duration > self._max_duration:
            raise AudioProcessingError(
                f"Audio duration {duration:.0f}s exceeds maximum {self._max_duration}s"
            )

        return AudioInfo(
            format=format,
            mime_type=mime_type,
            duration_seconds=duration or 0.0,
            size_bytes=len(audio_bytes),
        )

    def _get_duration(self, audio_bytes: bytes) -> float | None:
        """Get audio duration using ffprobe."""
        try:
            with NamedTemporaryFile(suffix=".audio", delete=True) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()

                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v", "quiet",
                        "-show_entries", "format=duration",
                        "-of", "csv=p=0",
                        tmp.name,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0 and result.stdout.strip():
                    return float(result.stdout.strip())

        except (subprocess.SubprocessError, ValueError, OSError) as e:
            logger.debug(f"ffprobe duration extraction failed: {e}")

        return None

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
        model: str = "whisper-1",
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.

        Args:
            audio_bytes: Raw audio bytes
            language: Optional language hint (ISO 639-1)
            model: Whisper model to use

        Returns:
            TranscriptionResult with text and metadata

        Raises:
            AudioProcessingError: If transcription fails
        """
        import httpx

        info = self.get_info(audio_bytes)

        if not self._whisper_url:
            raise AudioProcessingError(
                "Whisper API URL not configured. "
                "Set WHISPER_API_URL environment variable."
            )

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Create multipart form data
                files = {
                    "file": (f"audio.{info.format}", BytesIO(audio_bytes), info.mime_type),
                }
                data = {
                    "model": model,
                }
                if language:
                    data["language"] = language

                response = await client.post(
                    f"{self._whisper_url}/v1/audio/transcriptions",
                    files=files,
                    data=data,
                )

                if response.status_code != 200:
                    raise AudioProcessingError(
                        f"Transcription API error: {response.status_code}"
                    )

                result = response.json()

                return TranscriptionResult(
                    text=result.get("text", ""),
                    language=result.get("language"),
                    segments=result.get("segments"),
                    duration_seconds=info.duration_seconds,
                )

        except httpx.HTTPError as e:
            raise AudioProcessingError(f"Transcription request failed: {e}") from e

    def to_base64(self, audio_bytes: bytes) -> str:
        """Convert audio bytes to base64 string."""
        return base64.b64encode(audio_bytes).decode("utf-8")

    def from_base64(self, base64_data: str) -> bytes:
        """Decode base64 audio data."""
        # Remove data URL prefix if present
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]

        try:
            return base64.b64decode(base64_data)
        except Exception as e:
            raise AudioProcessingError(f"Invalid base64 encoding: {e}") from e


# Global instance
_audio_processor: AudioProcessor | None = None


def get_audio_processor() -> AudioProcessor:
    """Get or create the global audio processor."""
    global _audio_processor
    if _audio_processor is None:
        from app.config import get_settings

        settings = get_settings()
        _audio_processor = AudioProcessor(
            whisper_api_url=getattr(settings, "whisper_api_url", None),
        )
    return _audio_processor
