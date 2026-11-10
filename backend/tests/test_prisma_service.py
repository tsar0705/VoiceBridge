import pytest
import io
import wave
import httpx
from unittest.mock import patch, MagicMock

from app.services.prisma_service import PrismaService


def make_test_wav(duration_sec: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Generates a valid test WAV file."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * int(duration_sec * sample_rate))
    return buf.getvalue()


@pytest.fixture
def dummy_wav():
    return make_test_wav(duration_sec=2.0)


@pytest.mark.anyio
async def test_prisma_not_configured(dummy_wav):
    """PrismaService without API key should raise ValueError."""
    service = PrismaService(api_key="")
    assert not service.is_configured()
    with pytest.raises(ValueError, match="Gnani Prisma API key is not configured"):
        await service.transcribe_audio(dummy_wav)


@pytest.mark.anyio
async def test_prisma_empty_audio_buffer():
    """Empty audio should fail validation before any network call."""
    service = PrismaService(api_key="test_key_xyz")
    with pytest.raises(ValueError, match="Audio buffer is empty"):
        await service.transcribe_audio(b"")


@pytest.mark.anyio
async def test_prisma_audio_duration_exceeds_30s():
    """Audio longer than 30 seconds must be rejected per Gnani API spec."""
    long_wav = make_test_wav(duration_sec=32.0)
    service = PrismaService(api_key="test_key_xyz")
    with pytest.raises(ValueError, match="exceeds the maximum allowed limit of 30.0s"):
        await service.transcribe_audio(long_wav)


@pytest.mark.anyio
async def test_prisma_successful_transcription(dummy_wav):
    """Test successful transcription parsing and normalization."""
    service = PrismaService(api_key="test_key_xyz")

    mock_response = httpx.Response(
        status_code=200,
        json={
            "transcript": "வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்?",
            "detected_language_code": "ta",
            "confidence": 0.96,
            "model": "prisma-v3.0",
            "processing_time": 0.45,
        },
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response) as mock_post:
        transcript, lang, conf = await service.transcribe_audio(
            audio_bytes=dummy_wav,
            language_code="indic-auto",
            code_mix=True,
        )

        assert transcript == "வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்?"
        assert lang == "ta"
        assert conf == 0.96

        # Check call arguments (auth header present, never logging key)
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["X-API-Key-ID"] == "test_key_xyz"
        assert kwargs["data"]["model"] == "prisma-v3.0"
        assert kwargs["data"]["language_code"] == "indic-auto"
        assert kwargs["data"]["format"] == "codemix"


@pytest.mark.anyio
async def test_prisma_auth_failure(dummy_wav):
    """401/403 should raise PermissionError with clear advice."""
    service = PrismaService(api_key="invalid_key")
    mock_response = httpx.Response(
        status_code=401,
        text="Unauthorized - Invalid API Key",
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(PermissionError, match="Gnani Prisma authentication failed"):
            await service.transcribe_audio(dummy_wav)


@pytest.mark.anyio
async def test_prisma_credits_exhausted(dummy_wav):
    """402/429 should raise RuntimeError indicating credits or rate limit."""
    service = PrismaService(api_key="test_key_xyz")
    mock_response = httpx.Response(
        status_code=429,
        text="Rate limit exceeded",
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="rate limit reached or account credits exhausted"):
            await service.transcribe_audio(dummy_wav)


@pytest.mark.anyio
async def test_prisma_bad_request(dummy_wav):
    """400 should raise ValueError."""
    service = PrismaService(api_key="test_key_xyz")
    mock_response = httpx.Response(
        status_code=400,
        text="Invalid audio encoding",
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(ValueError, match="Gnani Prisma rejected the audio request"):
            await service.transcribe_audio(dummy_wav)


@pytest.mark.anyio
async def test_prisma_server_error(dummy_wav):
    """500 should raise RuntimeError."""
    service = PrismaService(api_key="test_key_xyz")
    mock_response = httpx.Response(
        status_code=500,
        text="Internal Server Error",
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="Gnani Prisma upstream service error"):
            await service.transcribe_audio(dummy_wav)


@pytest.mark.anyio
async def test_prisma_malformed_response(dummy_wav):
    """Non-JSON response should raise ValueError."""
    service = PrismaService(api_key="test_key_xyz")
    mock_response = httpx.Response(
        status_code=200,
        content=b"<!DOCTYPE html><html>Gateway timeout</html>",
        headers={"content-type": "text/html"},
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(ValueError, match="Gnani Prisma returned a non-JSON response"):
            await service.transcribe_audio(dummy_wav)


@pytest.mark.anyio
async def test_prisma_connection_timeout(dummy_wav):
    """ConnectTimeout should raise ConnectionError."""
    service = PrismaService(api_key="test_key_xyz")

    with patch.object(httpx.AsyncClient, "post", side_effect=httpx.ConnectTimeout("Connect timeout")):
        with pytest.raises(ConnectionError, match="Connection timed out"):
            await service.transcribe_audio(dummy_wav)


@pytest.mark.anyio
async def test_prisma_read_timeout(dummy_wav):
    """ReadTimeout should raise TimeoutError."""
    service = PrismaService(api_key="test_key_xyz")

    with patch.object(httpx.AsyncClient, "post", side_effect=httpx.ReadTimeout("Read timeout")):
        with pytest.raises(TimeoutError, match="timed out while processing audio"):
            await service.transcribe_audio(dummy_wav)
