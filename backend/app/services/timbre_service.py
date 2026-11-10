import logging
import io
import wave
from typing import Optional, Tuple, Dict, Any
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Standard language code normalization mapping to BCP-47 locales supported by timbre-v2.5
LANGUAGE_LOCALE_MAP: Dict[str, str] = {
    "ta": "ta-IN",
    "tamil": "ta-IN",
    "ta-in": "ta-IN",
    "tanglish": "ta-IN",
    "en": "en-IN",
    "english": "en-IN",
    "en-in": "en-IN",
    "hi": "hi-IN",
    "hindi": "hi-IN",
    "hi-in": "hi-IN",
    "hinglish": "hi-en",
    "hi-en": "hi-en",
    "te": "te-IN",
    "telugu": "te-IN",
    "kn": "kn-IN",
    "kannada": "kn-IN",
    "ml": "ml-IN",
    "malayalam": "ml-IN",
    "mr": "mr-IN",
    "marathi": "mr-IN",
    "bn": "bn-IN",
    "bengali": "bn-IN",
    "gu": "gu-IN",
    "gujarati": "gu-IN",
    "pa": "pa-IN",
    "punjabi": "pa-IN",
}


class TimbreService:
    """
    Gnani AI Timbre Text-to-Speech integration service.
    Connects to the official Vachana TTS inference endpoint:
    https://api.vachana.ai/api/v1/tts/inference

    Handles synthesizing natural Indic voice audio with timbre-v2.5.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        default_voice: Optional[str] = None,
        timeout_seconds: float = 35.0,
    ):
        self.api_key = api_key if api_key is not None else settings.GNANI_API_KEY
        self.endpoint = endpoint or settings.GNANI_TIMBRE_ENDPOINT
        self.model = model or settings.GNANI_TIMBRE_MODEL
        self.default_voice = default_voice or settings.GNANI_DEFAULT_VOICE
        self.timeout = httpx.Timeout(
            connect=10.0,
            read=timeout_seconds,
            write=15.0,
            pool=10.0,
        )

    def is_configured(self) -> bool:
        """Checks if the service has an API key configured."""
        return bool(self.api_key and self.api_key.strip())

    @staticmethod
    def normalize_language_code(language: Optional[str]) -> str:
        """Maps user/input language string to documented BCP-47 Gnani locale."""
        if not language:
            return "ta-IN"
        clean = language.strip().lower()
        return LANGUAGE_LOCALE_MAP.get(clean, "ta-IN")

    @staticmethod
    def calculate_wav_duration(audio_bytes: bytes) -> Optional[float]:
        """Calculates audio duration in seconds from raw WAV header or byte size."""
        if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
            try:
                with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    bytes_per_sec = rate * channels * sampwidth
                    # Detect streaming WAV placeholder headers (e.g. 0x7FFFFFFF)
                    if frames >= 2147483647 or (bytes_per_sec > 0 and (frames * channels * sampwidth) > len(audio_bytes)):
                        if bytes_per_sec > 0:
                            return round(max(0.1, (len(audio_bytes) - 44) / float(bytes_per_sec)), 2)
                    if rate > 0:
                        return round(frames / float(rate), 2)
            except Exception:
                pass
        return None

    async def synthesize_speech(
        self,
        text: str,
        language: str = "ta-IN",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> Tuple[bytes, str, float]:
        """
        Synthesizes text into speech using Gnani Timbre REST inference.

        Args:
            text: Text string to synthesize.
            language: Target language locale (e.g. 'ta-IN', 'en-IN', 'hi-IN').
            voice: Voice name from catalog (default 'Nalini').
            speed: Speech rate multiplier (0.5 to 2.0).

        Returns:
            Tuple of (audio_bytes: bytes, mime_type: str, duration_sec: float)
        """
        if not self.is_configured():
            logger.warning("Timbre synthesis attempted without GNANI_API_KEY configured.")
            raise ValueError(
                "Gnani Timbre API key is not configured. Please set GNANI_API_KEY in backend/.env"
            )

        if not text or not text.strip():
            raise ValueError("Text payload for speech synthesis cannot be empty.")

        clean_text = text.strip()
        target_locale = self.normalize_language_code(language)
        selected_voice = voice or self.default_voice

        # Request headers per official Gnani TTS spec
        headers = {
            "Content-Type": "application/json",
            "X-API-Key-ID": self.api_key,
        }

        # Request payload per official Gnani TTS inference documentation
        payload = {
            "text": clean_text,
            "voice": selected_voice,
            "model": self.model,
            "language": target_locale,
            "speed": float(speed),
            "audio_config": {
                "sample_rate": 48000,
                "num_channels": 1,
                "sample_width": 2,
                "encoding": "linear_pcm",
                "container": "wav",
            },
        }

        logger.info(
            "Sending synthesis request to Timbre at %s (model=%s, voice=%s, lang=%s, chars=%d)",
            self.endpoint,
            self.model,
            selected_voice,
            target_locale,
            len(clean_text),
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                )
        except httpx.ConnectTimeout:
            logger.error("Connection timeout connecting to Gnani Timbre TTS endpoint.")
            raise ConnectionError(
                f"Connection timed out while reaching Gnani Timbre endpoint ({self.endpoint})."
            )
        except httpx.ReadTimeout:
            logger.error("Read timeout waiting for Gnani Timbre TTS audio generation.")
            raise TimeoutError("Gnani Timbre TTS request timed out while generating audio.")
        except httpx.RequestError as exc:
            logger.error("Network error during Gnani Timbre TTS request: %s", type(exc).__name__)
            raise ConnectionError(f"Network error communicating with Gnani Timbre: {str(exc)}")

        # Handle HTTP error status codes
        if response.status_code == 401 or response.status_code == 403:
            logger.error("Gnani Timbre authentication failure (HTTP %d).", response.status_code)
            raise PermissionError(
                "Gnani Timbre authentication failed. Verify that GNANI_API_KEY is valid and active."
            )
        elif response.status_code in (402, 429):
            logger.error("Gnani Timbre rate limit or credits exhausted (HTTP %d).", response.status_code)
            raise RuntimeError(
                "Gnani Timbre rate limit reached or account credits exhausted (HTTP %d)." % response.status_code
            )
        elif response.status_code == 400:
            error_detail = response.text[:250]
            logger.warning("Gnani Timbre returned HTTP 400 Bad Request: %s", error_detail)
            raise ValueError(f"Gnani Timbre rejected the request: {error_detail}")
        elif response.status_code >= 500:
            logger.error("Gnani Timbre server error (HTTP %d).", response.status_code)
            raise RuntimeError(
                f"Gnani Timbre upstream service error (HTTP {response.status_code})."
            )
        elif response.status_code != 200:
            logger.error("Unexpected response status from Gnani Timbre: %d", response.status_code)
            raise RuntimeError(
                f"Gnani Timbre returned unexpected status code {response.status_code}."
            )

        # Successful response: contains raw binary audio data
        audio_bytes = response.content
        if not audio_bytes or len(audio_bytes) == 0:
            logger.error("Gnani Timbre returned empty binary audio payload.")
            raise ValueError("Gnani Timbre returned 0 bytes of audio data.")

        mime_type = response.headers.get("content-type", "audio/wav").split(";")[0].strip()
        if not mime_type or mime_type == "application/octet-stream":
            mime_type = "audio/wav"

        # Calculate or estimate duration
        duration = self.calculate_wav_duration(audio_bytes)
        if duration is None:
            # Fallback estimation for 48kHz, 16-bit mono PCM WAV (96,000 bytes/sec)
            estimated = max(0.5, round((len(audio_bytes) - 44) / 96000.0, 2))
            duration = estimated

        logger.info(
            "Timbre synthesis succeeded. Generated %d bytes of audio (~%.2fs).",
            len(audio_bytes),
            duration,
        )
        return audio_bytes, mime_type, duration

    async def synthesize(
        self,
        text: str,
        language: str = "ta-IN",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> Tuple[bytes, str, float]:
        """Convenience alias matching route handler invocations."""
        return await self.synthesize_speech(
            text=text,
            language=language,
            voice=voice,
            speed=speed,
        )
