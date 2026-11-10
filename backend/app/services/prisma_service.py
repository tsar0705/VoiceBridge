import logging
import time
from typing import Optional, Tuple, Dict, Any
import httpx

from app.config import settings
from app.utils.audio_utils import validate_audio_payload

logger = logging.getLogger(__name__)


class PrismaService:
    """
    Gnani AI Prisma Speech-to-Text integration service.
    Connects to the official Vachana STT v3 REST endpoint (https://api.vachana.ai/stt/v3).
    Supports multilingual Indian speech recognition and code-mixed transcription.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 35.0,
    ):
        self.api_key = api_key if api_key is not None else settings.GNANI_API_KEY
        self.endpoint = endpoint or settings.GNANI_PRISMA_ENDPOINT
        self.model = model or settings.GNANI_PRISMA_MODEL
        self.timeout = httpx.Timeout(
            connect=10.0,
            read=timeout_seconds,
            write=15.0,
            pool=10.0,
        )

    def is_configured(self) -> bool:
        """Checks if the service has an API key configured."""
        return bool(self.api_key and self.api_key.strip())

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        content_type: str = "audio/wav",
        language_code: Optional[str] = "indic-auto",
        code_mix: bool = True,
    ) -> Tuple[str, Optional[str], Optional[float]]:
        """
        Transcribes audio bytes using the official Gnani Prisma STT v3 API.

        Args:
            audio_bytes: Raw binary audio payload.
            filename: Original or default audio filename.
            content_type: Audio MIME type (e.g. 'audio/wav', 'audio/webm').
            language_code: Target language or 'indic-auto' for automatic language detection.
            code_mix: Whether to enable code-mixed transcription.

        Returns:
            Tuple of (transcript: str, detected_language_code: Optional[str], confidence: Optional[float])
        """
        if not self.is_configured():
            logger.warning("Prisma transcription attempted without GNANI_API_KEY configured.")
            raise ValueError(
                "Gnani Prisma API key is not configured. Please set GNANI_API_KEY in backend/.env"
            )

        # Validate audio payload constraints (size, duration max 30s)
        validate_audio_payload(
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
            max_size_mb=settings.MAX_AUDIO_SIZE_MB,
            max_duration_sec=float(settings.MAX_RECORDING_DURATION_SEC),
        )

        # Build multipart form data per official Gnani STT v3 spec
        # Headers: X-API-Key-ID (without logging the key)
        headers = {
            "X-API-Key-ID": self.api_key,
        }

        # Form fields
        data = {
            "model": self.model,
        }

        # Language code handling: indic-auto or specific / codemix
        if code_mix and language_code in ("indic-auto", "codemix", None):
            data["language_code"] = "indic-auto"
            data["format"] = "codemix"
        elif language_code:
            data["language_code"] = language_code

        files = {
            "audio_file": (filename, audio_bytes, content_type or "audio/wav")
        }

        logger.info(
            "Sending transcription request to Prisma STT at %s with model=%s, language=%s",
            self.endpoint,
            self.model,
            data.get("language_code"),
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint,
                    headers=headers,
                    data=data,
                    files=files,
                )
        except httpx.ConnectTimeout:
            logger.error("Connection timeout connecting to Gnani Prisma STT endpoint.")
            raise ConnectionError(
                f"Connection timed out while reaching Gnani Prisma endpoint ({self.endpoint})."
            )
        except httpx.ReadTimeout:
            logger.error("Read timeout waiting for Gnani Prisma STT response.")
            raise TimeoutError("Gnani Prisma STT request timed out while processing audio.")
        except httpx.RequestError as exc:
            logger.error("Network error during Gnani Prisma STT request: %s", type(exc).__name__)
            raise ConnectionError(f"Network error communicating with Gnani Prisma: {str(exc)}")

        # Handle HTTP error status codes
        if response.status_code == 401 or response.status_code == 403:
            logger.error("Gnani Prisma authentication failure (HTTP %d).", response.status_code)
            raise PermissionError(
                "Gnani Prisma authentication failed. Verify that GNANI_API_KEY is valid and active."
            )
        elif response.status_code in (402, 429):
            logger.error("Gnani Prisma rate limit or credits exhausted (HTTP %d).", response.status_code)
            raise RuntimeError(
                "Gnani Prisma rate limit reached or account credits exhausted (HTTP %d)." % response.status_code
            )
        elif response.status_code == 400:
            error_detail = response.text[:200]
            logger.warning("Gnani Prisma returned HTTP 400 Bad Request: %s", error_detail)
            raise ValueError(f"Gnani Prisma rejected the audio request: {error_detail}")
        elif response.status_code >= 500:
            logger.error("Gnani Prisma server error (HTTP %d).", response.status_code)
            raise RuntimeError(
                f"Gnani Prisma upstream service error (HTTP {response.status_code})."
            )
        elif response.status_code != 200:
            logger.error("Unexpected response status from Gnani Prisma: %d", response.status_code)
            raise RuntimeError(
                f"Gnani Prisma returned unexpected status code {response.status_code}."
            )

        # Parse and normalize successful response
        try:
            result = response.json()
        except Exception as json_err:
            logger.error("Failed to parse JSON response from Gnani Prisma: %s", json_err)
            raise ValueError("Gnani Prisma returned a non-JSON response.")

        transcript, detected_lang, confidence = self._normalize_response(result)
        logger.info(
            "Prisma transcription succeeded. Detected language: %s, Length: %d chars",
            detected_lang,
            len(transcript),
        )
        return transcript, detected_lang, confidence

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        content_type: str = "audio/wav",
        language_code: Optional[str] = "indic-auto",
        code_mix: bool = True,
    ) -> Tuple[str, Optional[str], Optional[float]]:
        """Convenience alias matching route handler invocations."""
        return await self.transcribe_audio(
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
            language_code=language_code,
            code_mix=code_mix,
        )

    def _normalize_response(self, data: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[float]]:
        """
        Normalizes varying response shapes from Gnani STT API into a consistent tuple.
        Extracts transcript, detected_language_code, and confidence.
        """
        # Transcript extraction with fallbacks
        transcript = (
            data.get("transcript")
            or data.get("transcription")
            or data.get("text")
            or ""
        )

        if not transcript and isinstance(data.get("results"), list) and len(data["results"]) > 0:
            first_result = data["results"][0]
            if isinstance(first_result, dict):
                transcript = first_result.get("transcript") or first_result.get("text") or ""

        # Language code extraction
        detected_lang = (
            data.get("detected_language_code")
            or data.get("language_code")
            or data.get("language")
            or data.get("detected_language")
        )

        # Confidence extraction
        raw_confidence = data.get("confidence")
        confidence: Optional[float] = None
        if raw_confidence is not None:
            try:
                confidence = float(raw_confidence)
            except (ValueError, TypeError):
                confidence = None

        return str(transcript).strip(), detected_lang, confidence
