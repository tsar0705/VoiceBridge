import pytest
import io
import wave
import base64
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.prisma_service import PrismaService
from app.services.timbre_service import TimbreService

client = TestClient(app)


def make_test_wav(duration_sec: float = 1.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * int(duration_sec * 16000))
    return buf.getvalue()


def test_transcribe_endpoint_empty_file():
    """Empty uploaded file must return 400."""
    response = client.post(
        "/api/voice/transcribe",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_transcribe_endpoint_unsupported_file_type():
    """Unsupported extension and MIME should return 415."""
    response = client.post(
        "/api/voice/transcribe",
        files={"file": ("virus.exe", b"fake binary", "application/x-msdownload")},
    )
    assert response.status_code == 415


def test_transcribe_endpoint_success():
    """Mock successful STT flow through the route."""
    wav_bytes = make_test_wav(1.0)

    with patch.object(
        PrismaService,
        "transcribe_audio",
        return_value=("Vanakkam, epdi irukeenga?", "ta", 0.95),
    ):
        response = client.post(
            "/api/voice/transcribe",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
            data={"language": "indic-auto", "code_mix": "true"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["transcript"] == "Vanakkam, epdi irukeenga?"
        assert data["detected_language"] == "ta"
        assert data["confidence"] == 0.95
        assert data["model"] == "prisma-v3.0"
        assert "processing_time_ms" in data


def test_synthesize_endpoint_empty_text():
    """Synthesize with empty text should return 422 or 400."""
    response = client.post(
        "/api/voice/synthesize",
        json={"text": "", "language": "ta"},
    )
    assert response.status_code in (400, 422)


def test_synthesize_endpoint_success():
    """Mock successful TTS flow through the route."""
    dummy_audio = make_test_wav(1.0)

    with patch.object(
        TimbreService,
        "synthesize_speech",
        return_value=(dummy_audio, "audio/wav", 1.0),
    ):
        response = client.post(
            "/api/voice/synthesize",
            json={"text": "வணக்கம்", "language": "ta", "speed": 1.0},
        )
        assert response.status_code == 200
        data = response.json()
        assert "audio_base64" in data
        assert data["format"] == "audio/wav"
        assert data["duration_sec"] == 1.0
        assert data["model"] == "timbre-v2.5"

        # Verify Base64 decodes back to original binary
        decoded = base64.b64decode(data["audio_base64"])
        assert decoded == dummy_audio


def test_transcribe_unsupported_webm_rejected():
    """Verify that uploading a WebM recording to /transcribe returns 415."""
    webm_bytes = b"\x1a\x45\xdf\xa3" + b"\x00" * 200
    response = client.post(
        "/api/voice/transcribe",
        files={"file": ("recording.webm", webm_bytes, "audio/webm")},
    )
    assert response.status_code == 415
    assert "UNSUPPORTED_AUDIO_FORMAT" in response.json()["detail"]


def test_voice_chat_unsupported_webm_rejected():
    """Verify that uploading a WebM recording to /chat returns 415 without invoking Prisma."""
    webm_bytes = b"\x1a\x45\xdf\xa3" + b"\x00" * 200
    with patch.object(PrismaService, "transcribe_audio") as mock_stt:
        response = client.post(
            "/api/voice/chat",
            files={"file": ("recording.webm", webm_bytes, "audio/webm")},
            data={"session_id": "test_webm"},
        )
        assert response.status_code == 415
        assert "UNSUPPORTED_AUDIO_FORMAT" in response.json()["detail"]
        mock_stt.assert_not_called()

