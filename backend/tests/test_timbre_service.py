import pytest
import io
import wave
import httpx
from unittest.mock import patch

from app.services.timbre_service import TimbreService


def make_test_wav(duration_sec: float = 1.5, sample_rate: int = 48000) -> bytes:
    """Generates a valid PCM WAV byte stream for testing."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * int(duration_sec * sample_rate))
    return buf.getvalue()


@pytest.fixture
def dummy_wav():
    return make_test_wav(duration_sec=1.5)


def test_timbre_language_normalization():
    """Verify various input formats map cleanly to documented BCP-47 locales."""
    assert TimbreService.normalize_language_code("Tamil") == "ta-IN"
    assert TimbreService.normalize_language_code("ta") == "ta-IN"
    assert TimbreService.normalize_language_code("Hindi") == "hi-IN"
    assert TimbreService.normalize_language_code("hi") == "hi-IN"
    assert TimbreService.normalize_language_code("English") == "en-IN"
    assert TimbreService.normalize_language_code("en") == "en-IN"
    assert TimbreService.normalize_language_code("Hinglish") == "hi-en"
    assert TimbreService.normalize_language_code("Tanglish") == "ta-IN"
    assert TimbreService.normalize_language_code(None) == "ta-IN"


@pytest.mark.anyio
async def test_timbre_not_configured():
    """TimbreService without API key should raise ValueError."""
    service = TimbreService(api_key="")
    assert not service.is_configured()
    with pytest.raises(ValueError, match="Gnani Timbre API key is not configured"):
        await service.synthesize_speech("வணக்கம்")


@pytest.mark.anyio
async def test_timbre_empty_text():
    """Empty or whitespace-only text must raise ValueError."""
    service = TimbreService(api_key="test_key_xyz")
    with pytest.raises(ValueError, match="cannot be empty"):
        await service.synthesize_speech("   ")


@pytest.mark.anyio
async def test_timbre_successful_binary_audio_synthesis(dummy_wav):
    """
    Verify that successful REST response contains raw binary audio data.
    Handle it as binary, validate HTTP status and content type, without parsing JSON.
    """
    service = TimbreService(api_key="test_key_xyz")

    mock_response = httpx.Response(
        status_code=200,
        content=dummy_wav,
        headers={"content-type": "audio/wav"},
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response) as mock_post:
        audio_bytes, mime_type, duration = await service.synthesize_speech(
            text="வணக்கம், VoiceBridge இல் உங்கள் வருகை நல்வரவாகுக!",
            language="Tamil",
            voice="Nalini",
            speed=1.0,
        )

        assert isinstance(audio_bytes, bytes)
        assert len(audio_bytes) == len(dummy_wav)
        assert mime_type == "audio/wav"
        assert duration == 1.5

        # Verify request headers and JSON payload structure
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["X-API-Key-ID"] == "test_key_xyz"
        assert kwargs["headers"]["Content-Type"] == "application/json"
        payload = kwargs["json"]
        assert payload["model"] == "timbre-v2.5"
        assert payload["voice"] == "Nalini"
        assert payload["language"] == "ta-IN"
        assert payload["audio_config"]["container"] == "wav"


@pytest.mark.anyio
async def test_timbre_auth_failure():
    """401/403 should raise PermissionError."""
    service = TimbreService(api_key="invalid_key")
    mock_response = httpx.Response(
        status_code=401,
        text="Invalid X-API-Key-ID",
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(PermissionError, match="Gnani Timbre authentication failed"):
            await service.synthesize_speech("Hello")


@pytest.mark.anyio
async def test_timbre_credits_exhausted():
    """402/429 should raise RuntimeError indicating credits or rate limit."""
    service = TimbreService(api_key="test_key_xyz")
    mock_response = httpx.Response(
        status_code=429,
        text="Quota exceeded",
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="rate limit reached or account credits exhausted"):
            await service.synthesize_speech("Hello")


@pytest.mark.anyio
async def test_timbre_bad_request():
    """400 should raise ValueError."""
    service = TimbreService(api_key="test_key_xyz")
    mock_response = httpx.Response(
        status_code=400,
        text="Unsupported voice for model",
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(ValueError, match="Gnani Timbre rejected the request"):
            await service.synthesize_speech("Hello")


@pytest.mark.anyio
async def test_timbre_server_error():
    """500 should raise RuntimeError."""
    service = TimbreService(api_key="test_key_xyz")
    mock_response = httpx.Response(
        status_code=500,
        text="Internal Server Error",
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="Gnani Timbre upstream service error"):
            await service.synthesize_speech("Hello")


@pytest.mark.anyio
async def test_timbre_empty_audio_response():
    """200 response with 0 content bytes should raise ValueError."""
    service = TimbreService(api_key="test_key_xyz")
    mock_response = httpx.Response(
        status_code=200,
        content=b"",
        headers={"content-type": "audio/wav"},
        request=httpx.Request("POST", service.endpoint),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(ValueError, match="returned 0 bytes of audio data"):
            await service.synthesize_speech("Hello")


@pytest.mark.anyio
async def test_timbre_connection_timeout():
    """ConnectTimeout should raise ConnectionError."""
    service = TimbreService(api_key="test_key_xyz")

    with patch.object(httpx.AsyncClient, "post", side_effect=httpx.ConnectTimeout("Connect timeout")):
        with pytest.raises(ConnectionError, match="Connection timed out"):
            await service.synthesize_speech("Hello")


@pytest.mark.anyio
async def test_timbre_read_timeout():
    """ReadTimeout should raise TimeoutError."""
    service = TimbreService(api_key="test_key_xyz")

    with patch.object(httpx.AsyncClient, "post", side_effect=httpx.ReadTimeout("Read timeout")):
        with pytest.raises(TimeoutError, match="timed out while generating audio"):
            await service.synthesize_speech("Hello")
