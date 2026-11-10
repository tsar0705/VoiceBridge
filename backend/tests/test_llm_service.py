import pytest
import httpx
from unittest.mock import patch

from app.services.llm_service import LLMService, GeminiProvider, OpenAICompatibleProvider


@pytest.mark.anyio
async def test_llm_service_not_configured():
    """Unconfigured service should raise a clear ValueError."""
    service = LLMService(api_key="")
    assert not service.is_configured()
    with pytest.raises(ValueError, match="is not configured"):
        await service.generate_response("Hello", [])


@pytest.mark.anyio
async def test_llm_service_empty_message():
    """Empty user prompt should raise ValueError."""
    service = LLMService(provider_name="gemini", api_key="dummy_key_123")
    assert service.is_configured()
    with pytest.raises(ValueError, match="cannot be empty"):
        await service.generate_response("   ", [])


@pytest.mark.anyio
async def test_gemini_provider_success():
    """Verify Gemini provider successfully formats payload and parses candidate text."""
    provider = GeminiProvider(api_key="test_gemini_key", model="gemini-2.5-flash")

    mock_gemini_response = httpx.Response(
        status_code=200,
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "வணக்கம்! நான் வாய்ஸ்பிரிட்ஜ் உதவியாளர். உங்களுக்கு உதவ மகிழ்ச்சி."}
                        ]
                    }
                }
            ]
        },
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_gemini_response) as mock_post:
        result = await provider.generate_completion(
            system_prompt="You are VoiceBridge.",
            messages=[{"role": "user", "content": "வணக்கம்"}],
        )

        assert "வணக்கம்!" in result
        _, kwargs = mock_post.call_args
        assert kwargs["params"]["key"] == "test_gemini_key"
        assert kwargs["json"]["contents"][0]["parts"][0]["text"] == "வணக்கம்"


@pytest.mark.anyio
async def test_gemini_provider_auth_failure():
    """401/403 should raise PermissionError."""
    provider = GeminiProvider(api_key="bad_key")
    mock_response = httpx.Response(
        status_code=403,
        text="The caller does not have permission",
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(PermissionError, match="Gemini API authentication failed"):
            await provider.generate_completion("system", [{"role": "user", "content": "hi"}])


@pytest.mark.anyio
async def test_gemini_provider_rate_limit():
    """429 should raise RuntimeError."""
    provider = GeminiProvider(api_key="test_key")
    mock_response = httpx.Response(
        status_code=429,
        text="Resource exhausted",
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="quota or rate limit exceeded"):
            await provider.generate_completion("system", [{"role": "user", "content": "hi"}])


@pytest.mark.anyio
async def test_gemini_provider_timeouts():
    """Timeout exceptions must be wrapped in descriptive application errors."""
    provider = GeminiProvider(api_key="test_key")

    with patch.object(httpx.AsyncClient, "post", side_effect=httpx.ConnectTimeout("Connect timeout")):
        with pytest.raises(ConnectionError, match="Connection timed out"):
            await provider.generate_completion("system", [{"role": "user", "content": "hi"}])

    with patch.object(httpx.AsyncClient, "post", side_effect=httpx.ReadTimeout("Read timeout")):
        with pytest.raises(TimeoutError, match="reasoning request timed out"):
            await provider.generate_completion("system", [{"role": "user", "content": "hi"}])


@pytest.mark.anyio
async def test_openai_compatible_provider_success():
    """Verify OpenAI-compatible provider completes and parses message content."""
    provider = OpenAICompatibleProvider(api_key="test_openai_key", model="gpt-4o-mini")

    mock_openai_response = httpx.Response(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {
                        "content": "Hello! I am VoiceBridge. How can I assist you today?"
                    }
                }
            ]
        },
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_openai_response) as mock_post:
        result = await provider.generate_completion(
            system_prompt="You are VoiceBridge.",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert "VoiceBridge" in result
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer test_openai_key"


def test_sanitize_for_tts():
    """Markdown formatting should be stripped cleanly to preserve natural spoken speech."""
    raw = "**Hello!** This is #VoiceBridge with `code` and [link](http://test.com)."
    sanitized = LLMService._sanitize_for_tts(raw)
    assert "**" not in sanitized
    assert "#" not in sanitized
    assert "`" not in sanitized
    assert "http" not in sanitized
    assert sanitized == "Hello! This is VoiceBridge with code and link."


def test_system_prompt_language_rules():
    """Verify appropriate speech prompt tailoring for Indic languages."""
    service = LLMService(api_key="dummy_key")

    prompt_ta = service._build_system_prompt("Tamil")
    assert "Tamil" in prompt_ta
    assert "Tamil script" in prompt_ta

    prompt_hi = service._build_system_prompt("Hindi")
    assert "Hindi" in prompt_hi
    assert "Hindi Devanagari" in prompt_hi

    prompt_tanglish = service._build_system_prompt("Tanglish")
    assert "Tanglish" in prompt_tanglish
    assert "Latin script" in prompt_tanglish

    prompt_hinglish = service._build_system_prompt("Hinglish")
    assert "Hinglish" in prompt_hinglish
    assert "Latin script" in prompt_hinglish
