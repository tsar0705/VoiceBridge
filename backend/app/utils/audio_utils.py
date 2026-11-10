import os
import io
import wave
from typing import Optional
from fastapi import HTTPException, UploadFile, status

# Supported by Gnani Prisma STT: flac, mp3, ogg, m4a, wav, aac
SUPPORTED_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aac"}

SUPPORTED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/flac",
    "audio/x-flac",
    "audio/mp3",
    "audio/mpeg",
    "audio/ogg",
    "audio/x-m4a",
    "audio/m4a",
    "audio/aac",
    "audio/x-aac",
}

UNSUPPORTED_EXTENSIONS = {".webm"}
UNSUPPORTED_MIME_TYPES = {"audio/webm", "video/webm"}


def detect_audio_format(audio_bytes: bytes) -> Optional[str]:
    """
    Detects audio format from magic bytes signature.
    Returns: 'wav' | 'flac' | 'ogg' | 'mp3' | 'm4a' | 'aac' | 'webm' | None
    """
    if not audio_bytes or len(audio_bytes) < 4:
        return None

    # WAV (RIFF ... WAVE)
    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return "wav"

    # FLAC (fLaC)
    if audio_bytes[:4] == b"fLaC":
        return "flac"

    # OGG (OggS)
    if audio_bytes[:4] == b"OggS":
        return "ogg"

    # WebM / Matroska (\x1a\x45\xdf\xa3)
    if audio_bytes[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"

    # MP3 (ID3 tag or MPEG sync word 0xFFE0 mask)
    if audio_bytes[:3] == b"ID3":
        return "mp3"
    if len(audio_bytes) >= 2 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0:
        return "mp3"

    # M4A / MP4 (ftyp at offset 4)
    if len(audio_bytes) >= 8 and audio_bytes[4:8] == b"ftyp":
        return "m4a"

    # AAC ADTS sync (0xFFF1 or 0xFFF9)
    if len(audio_bytes) >= 2 and (audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xF6) == 0xF0):
        return "aac"

    return None


def is_valid_wav_header(audio_bytes: bytes) -> bool:
    """Verifies that the byte buffer contains a valid RIFF/WAVE header."""
    return (
        len(audio_bytes) >= 44
        and audio_bytes[:4] == b"RIFF"
        and audio_bytes[8:12] == b"WAVE"
        and audio_bytes[12:16] == b"fmt "
    )


def get_audio_duration_seconds(audio_bytes: bytes) -> Optional[float]:
    """
    Attempts to calculate duration from audio bytes (for standard or streaming WAV containers).
    Returns duration in seconds or None if indeterminate.
    """
    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                bytes_per_sec = rate * channels * sampwidth
                if frames >= 2147483647 or (bytes_per_sec > 0 and (frames * channels * sampwidth) > len(audio_bytes)):
                    if bytes_per_sec > 0:
                        return (len(audio_bytes) - 44) / float(bytes_per_sec)
                if rate > 0:
                    return frames / float(rate)
        except Exception:
            pass
    return None


def validate_audio_file(file: UploadFile, max_size_mb: int = 10) -> None:
    """
    Validates uploaded audio file presence, extension, and content type.
    Rejects unsupported formats such as browser WebM upfront.
    Raises HTTPException if validation fails.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file provided or filename is missing.",
        )

    # Check extension and content-type
    _, ext = os.path.splitext(file.filename.lower())
    content_type = (file.content_type or "").lower().strip()

    # Explicit check for unsupported WebM audio
    if ext in UNSUPPORTED_EXTENSIONS or content_type in UNSUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "UNSUPPORTED_AUDIO_FORMAT: WebM audio is not supported by Gnani Prisma. "
                "Supported formats: flac, mp3, ogg, m4a, wav, aac. Please send PCM WAV audio."
            ),
        )

    if ext and ext not in SUPPORTED_EXTENSIONS:
        if content_type not in SUPPORTED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported audio format '{ext or content_type}'. Supported: {sorted(list(SUPPORTED_EXTENSIONS))}",
            )


def validate_audio_payload(
    audio_bytes: bytes,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    max_size_mb: int = 10,
    max_duration_sec: float = 30.0,
) -> None:
    """
    Validates raw audio byte buffer for emptiness, max size, file signature, and maximum allowed duration.
    Raises ValueError on validation failures.
    """
    if not audio_bytes or len(audio_bytes) == 0:
        raise ValueError("Audio buffer is empty (0 bytes).")

    max_bytes = max_size_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise ValueError(
            f"Audio file size ({len(audio_bytes) / (1024 * 1024):.2f}MB) exceeds maximum allowed limit of {max_size_mb}MB."
        )

    # Reject unsupported WebM magic bytes
    detected_fmt = detect_audio_format(audio_bytes)
    if detected_fmt == "webm":
        raise ValueError(
            "UNSUPPORTED_AUDIO_FORMAT: WebM audio is not supported by Gnani Prisma. "
            "Supported formats: flac, mp3, ogg, m4a, wav, aac. Please send PCM WAV audio."
        )

    # Validate duration if WAV format
    duration = get_audio_duration_seconds(audio_bytes)
    if duration is not None and duration > max_duration_sec:
        raise ValueError(
            f"Audio duration ({duration:.1f}s) exceeds the maximum allowed limit of {max_duration_sec}s."
        )
