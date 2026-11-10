import pytest
import io
import wave
import base64
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.prisma_service import PrismaService
from app.services.llm_service import LLMService
from app.services.timbre_service import TimbreService
from app.api.voice_routes import conversation_service

client = TestClient(app)


def make_test_wav(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generates a valid test WAV byte buffer."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * int(duration_sec * sample_rate))
    return buf.getvalue()


@pytest.fixture(autouse=True)
def clean_sessions():
    """Ensure clean conversation session memory before each test."""
    conversation_service._sessions.clear()
    yield
    conversation_service._sessions.clear()


def test_complete_voice_chat_pipeline_success():
    """
    Verify complete voice conversation pipeline:
    Audio in -> Prisma STT -> LLM reasoning -> Timbre TTS -> Audio out + metadata.
    """
    wav_bytes = make_test_wav(1.5)
    mock_stt_result = ("வணக்கம், இன்றைய செய்தி என்ன?", "ta-IN", 0.97)
    mock_llm_result = "வணக்கம்! இன்றைய முக்கிய செய்திகள் இதோ."
    mock_tts_result = (wav_bytes, "audio/wav", 1.8)

    with patch.object(PrismaService, "transcribe_audio", AsyncMock(return_value=mock_stt_result)), \
         patch.object(LLMService, "generate_response", AsyncMock(return_value=mock_llm_result)), \
         patch.object(TimbreService, "synthesize_speech", AsyncMock(return_value=mock_tts_result)):

        response = client.post(
            "/api/voice/chat",
            files={"file": ("speech.wav", wav_bytes, "audio/wav")},
            data={"session_id": "sess_e2e_1", "response_language": "Tamil"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == "sess_e2e_1"
        assert data["transcription"] == "வணக்கம், இன்றைய செய்தி என்ன?"
        assert data["detected_input_language"] == "ta-IN"
        assert data["ai_response_text"] == "வணக்கம்! இன்றைய முக்கிய செய்திகள் இதோ."
        assert data["output_language"] == "Tamil"
        assert data["audio_format"] == "audio/wav"
        assert data["audio_duration_sec"] == 1.8
        assert "models" in data
        assert "processing_time_ms" in data

        # Verify binary audio is returned as valid Base64
        decoded = base64.b64decode(data["audio_base64"])
        assert decoded == wav_bytes

        # Verify conversation history was updated with both turns
        history = conversation_service.get_history("sess_e2e_1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "வணக்கம், இன்றைய செய்தி என்ன?"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "வணக்கம்! இன்றைய முக்கிய செய்திகள் இதோ."


def test_voice_chat_partial_failure_prisma():
    """When Prisma STT fails, pipeline returns 502 and session history is NOT updated."""
    wav_bytes = make_test_wav(1.0)

    with patch.object(
        PrismaService,
        "transcribe_audio",
        AsyncMock(side_effect=RuntimeError("Prisma service temporarily unavailable")),
    ):
        response = client.post(
            "/api/voice/chat",
            files={"file": ("speech.wav", wav_bytes, "audio/wav")},
            data={"session_id": "sess_fail_stt"},
        )

        assert response.status_code == 502
        assert "Prisma STT Failed" in response.json()["detail"]
        assert conversation_service.get_history("sess_fail_stt") == []


def test_voice_chat_partial_failure_llm_auth():
    """When LLM authentication fails, pipeline returns 401 and history is NOT updated."""
    wav_bytes = make_test_wav(1.0)
    mock_stt = ("Hello VoiceBridge", "en-IN", 0.95)

    with patch.object(PrismaService, "transcribe_audio", AsyncMock(return_value=mock_stt)), \
         patch.object(LLMService, "generate_response", AsyncMock(side_effect=PermissionError("Invalid LLM API Key"))):

        response = client.post(
            "/api/voice/chat",
            files={"file": ("speech.wav", wav_bytes, "audio/wav")},
            data={"session_id": "sess_fail_llm"},
        )

        assert response.status_code == 401
        assert "LLM Auth Error" in response.json()["detail"]
        assert conversation_service.get_history("sess_fail_llm") == []


def test_voice_chat_partial_failure_llm_timeout():
    """When LLM times out, pipeline returns 504 Gateway Timeout."""
    wav_bytes = make_test_wav(1.0)
    mock_stt = ("Hello VoiceBridge", "en-IN", 0.95)

    with patch.object(PrismaService, "transcribe_audio", AsyncMock(return_value=mock_stt)), \
         patch.object(LLMService, "generate_response", AsyncMock(side_effect=TimeoutError("LLM response timeout"))):

        response = client.post(
            "/api/voice/chat",
            files={"file": ("speech.wav", wav_bytes, "audio/wav")},
            data={"session_id": "sess_fail_timeout"},
        )

        assert response.status_code == 504
        assert "LLM Gateway Timeout" in response.json()["detail"]
        assert conversation_service.get_history("sess_fail_timeout") == []


def test_voice_chat_partial_failure_timbre_tts():
    """When Timbre synthesis fails, pipeline returns 502 and history is NOT updated."""
    wav_bytes = make_test_wav(1.0)
    mock_stt = ("Hello VoiceBridge", "en-IN", 0.95)
    mock_llm = "Hello! How can I help you?"

    with patch.object(PrismaService, "transcribe_audio", AsyncMock(return_value=mock_stt)), \
         patch.object(LLMService, "generate_response", AsyncMock(return_value=mock_llm)), \
         patch.object(TimbreService, "synthesize_speech", AsyncMock(side_effect=RuntimeError("Timbre error"))):

        response = client.post(
            "/api/voice/chat",
            files={"file": ("speech.wav", wav_bytes, "audio/wav")},
            data={"session_id": "sess_fail_tts"},
        )

        assert response.status_code == 502
        assert "Timbre Synthesis Failed" in response.json()["detail"]
        assert conversation_service.get_history("sess_fail_tts") == []


def test_multi_turn_history_retention():
    """Verify that multiple turns in the same session pass previous context to the LLM."""
    wav_bytes = make_test_wav(1.0)
    llm_history_captured = []

    async def mock_llm_side_effect(user_message, conversation_history, target_language, detected_language):
        # Record the history passed to LLM on each call
        llm_history_captured.append(list(conversation_history))
        return f"Response to: {user_message}"

    with patch.object(PrismaService, "transcribe_audio", AsyncMock(side_effect=[
        ("My name is Karthik.", "en-IN", 0.98),
        ("What is my name?", "en-IN", 0.99),
    ])), \
         patch.object(LLMService, "generate_response", AsyncMock(side_effect=mock_llm_side_effect)), \
         patch.object(TimbreService, "synthesize_speech", AsyncMock(return_value=(wav_bytes, "audio/wav", 1.0))):

        # Turn 1
        res1 = client.post(
            "/api/voice/chat",
            files={"file": ("turn1.wav", wav_bytes, "audio/wav")},
            data={"session_id": "sess_multiturn", "response_language": "English"},
        )
        assert res1.status_code == 200

        # Turn 2
        res2 = client.post(
            "/api/voice/chat",
            files={"file": ("turn2.wav", wav_bytes, "audio/wav")},
            data={"session_id": "sess_multiturn", "response_language": "English"},
        )
        assert res2.status_code == 200

        # Verify LLM received empty history on Turn 1 and 2 turns on Turn 2
        assert len(llm_history_captured[0]) == 0
        assert len(llm_history_captured[1]) == 2
        assert llm_history_captured[1][0]["content"] == "My name is Karthik."
        assert llm_history_captured[1][1]["content"] == "Response to: My name is Karthik."


def test_session_isolation_in_chat():
    """Verify that separate sessions do not share chat history."""
    wav_bytes = make_test_wav(1.0)
    session_histories = {}

    async def mock_llm(user_message, conversation_history, target_language, detected_language):
        session_histories[user_message] = len(conversation_history)
        return "Acknowledged"

    with patch.object(PrismaService, "transcribe_audio", AsyncMock(side_effect=[
        ("User A message 1", "en-IN", 0.95),
        ("User B message 1", "en-IN", 0.95),
    ])), \
         patch.object(LLMService, "generate_response", AsyncMock(side_effect=mock_llm)), \
         patch.object(TimbreService, "synthesize_speech", AsyncMock(return_value=(wav_bytes, "audio/wav", 1.0))):

        client.post(
            "/api/voice/chat",
            files={"file": ("a.wav", wav_bytes, "audio/wav")},
            data={"session_id": "session_user_A"},
        )
        client.post(
            "/api/voice/chat",
            files={"file": ("b.wav", wav_bytes, "audio/wav")},
            data={"session_id": "session_user_B"},
        )

        # Both turn 1s had 0 previous history
        assert session_histories["User A message 1"] == 0
        assert session_histories["User B message 1"] == 0


def test_session_reset_endpoint():
    """Verify DELETE /api/voice/session/{session_id} clears history cleanly."""
    conversation_service.add_message("sess_to_clear", "user", "Hello")
    conversation_service.add_message("sess_to_clear", "assistant", "Hi there")
    assert conversation_service.session_exists("sess_to_clear") is True

    response = client.delete("/api/voice/session/sess_to_clear")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cleared"
    assert data["session_id"] == "sess_to_clear"
    assert conversation_service.session_exists("sess_to_clear") is False


def test_language_resolution_auto_and_explicit():
    """Verify language selection rules (Auto following detected language vs explicit)."""
    wav_bytes = make_test_wav(1.0)

    with patch.object(PrismaService, "transcribe_audio", AsyncMock(return_value=("வணக்கம்", "ta-IN", 0.96))), \
         patch.object(LLMService, "generate_response", AsyncMock(return_value="நன்றி")), \
         patch.object(TimbreService, "synthesize_speech", AsyncMock(return_value=(wav_bytes, "audio/wav", 1.0))):

        # Auto mode: follows detected 'ta-IN' -> output 'Tamil'
        res_auto = client.post(
            "/api/voice/chat",
            files={"file": ("s.wav", wav_bytes, "audio/wav")},
            data={"response_language": "auto"},
        )
        assert res_auto.status_code == 200
        assert res_auto.json()["output_language"] == "Tamil"

        # Explicit mode: user requests English -> output 'English'
        res_explicit = client.post(
            "/api/voice/chat",
            files={"file": ("s.wav", wav_bytes, "audio/wav")},
            data={"response_language": "English"},
        )
        assert res_explicit.status_code == 200
        assert res_explicit.json()["output_language"] == "English"


def test_voice_chat_invalid_audio():
    """Empty audio payload should be rejected with 400 Bad Request."""
    response = client.post(
        "/api/voice/chat",
        files={"file": ("empty.wav", b"", "audio/wav")},
        data={"session_id": "sess_err"},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
