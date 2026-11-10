import io
import wave
import pytest
from app.utils.audio_utils import (
    get_audio_duration_seconds,
    validate_audio_payload,
    detect_audio_format,
    is_valid_wav_header,
    validate_audio_file,
)


def make_test_wav(duration_sec: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Generates a valid in-memory PCM WAV audio byte buffer."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        num_frames = int(duration_sec * sample_rate)
        wf.writeframes(b"\x00\x00" * num_frames)
    return buf.getvalue()


def test_get_audio_duration_seconds_valid():
    """Verify exact duration extracted from a valid WAV header."""
    wav_bytes = make_test_wav(duration_sec=3.5, sample_rate=16000)
    duration = get_audio_duration_seconds(wav_bytes)
    assert duration is not None
    assert round(duration, 1) == 3.5


def test_get_audio_duration_seconds_invalid():
    """Verify non-WAV bytes return None without raising an error."""
    assert get_audio_duration_seconds(b"random-non-wav-bytes") is None
    assert get_audio_duration_seconds(b"") is None


def test_validate_audio_payload_empty_fails():
    """Empty audio payload should raise ValueError."""
    with pytest.raises(ValueError, match="Audio buffer is empty"):
        validate_audio_payload(b"")


def test_validate_audio_payload_size_limit_fails():
    """Audio exceeding max size should raise ValueError."""
    oversized = b"0" * (11 * 1024 * 1024)
    with pytest.raises(ValueError, match="exceeds maximum allowed limit of 10MB"):
        validate_audio_payload(oversized, max_size_mb=10)


def test_validate_audio_payload_duration_limit_fails():
    """WAV audio exceeding 30-second duration should raise ValueError."""
    long_wav = make_test_wav(duration_sec=35.0)
    with pytest.raises(ValueError, match="exceeds the maximum allowed limit of 30.0s"):
        validate_audio_payload(long_wav, max_duration_sec=30.0)


def test_validate_audio_payload_valid_passes():
    """Valid audio within 30s limit should pass validation without error."""
    valid_wav = make_test_wav(duration_sec=5.0)
    validate_audio_payload(valid_wav, max_duration_sec=30.0)


def test_detect_audio_format_signatures():
    """Verify magic bytes signature detection for all major audio formats."""
    # WAV
    wav_bytes = make_test_wav(1.0)
    assert detect_audio_format(wav_bytes) == "wav"

    # WebM / Matroska
    webm_bytes = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81"
    assert detect_audio_format(webm_bytes) == "webm"

    # FLAC
    flac_bytes = b"fLaC\x00\x00\x00\x22"
    assert detect_audio_format(flac_bytes) == "flac"

    # OGG
    ogg_bytes = b"OggS\x00\x02\x00\x00"
    assert detect_audio_format(ogg_bytes) == "ogg"

    # MP3 ID3
    mp3_bytes = b"ID3\x03\x00\x00\x00"
    assert detect_audio_format(mp3_bytes) == "mp3"

    # Unknown
    assert detect_audio_format(b"unknown") is None


def test_is_valid_wav_header():
    """Verify is_valid_wav_header accurately identifies canonical RIFF/WAVE containers."""
    valid_wav = make_test_wav(1.0)
    assert is_valid_wav_header(valid_wav) is True
    assert is_valid_wav_header(b"not-a-wav-file") is False
    assert is_valid_wav_header(b"RIFF\x00\x00\x00\x00NOTW") is False


def test_validate_audio_payload_webm_rejected():
    """Verify that WebM payload is detected and rejected with clear error."""
    webm_bytes = b"\x1a\x45\xdf\xa3" + b"\x00" * 100
    with pytest.raises(ValueError, match="UNSUPPORTED_AUDIO_FORMAT: WebM audio is not supported"):
        validate_audio_payload(webm_bytes)


def test_validate_audio_file_webm_rejected():
    """Verify validate_audio_file raises 415 for WebM files before any external processing."""
    from unittest.mock import MagicMock
    from fastapi import HTTPException

    mock_file = MagicMock()
    mock_file.filename = "recording.webm"
    mock_file.content_type = "audio/webm"

    with pytest.raises(HTTPException) as exc_info:
        validate_audio_file(mock_file)
    assert exc_info.value.status_code == 415
    assert "UNSUPPORTED_AUDIO_FORMAT" in exc_info.value.detail

