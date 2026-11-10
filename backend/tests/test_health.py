import pytest
from app.main import app, root_health, root
from app.api.voice_routes import health_check
from app.schemas.voice_schema import HealthResponse


def test_api_routes_registered():
    """Verify all required API endpoints are properly mounted."""
    route_paths = [route.path for route in app.routes]
    assert "/api/health" in route_paths
    assert "/api/voice/health" in route_paths
    assert "/api/voice/transcribe" in route_paths
    assert "/api/voice/synthesize" in route_paths
    assert "/api/voice/chat" in route_paths


def test_voice_health_check():
    """Verify voice route health check returns valid HealthResponse schema."""
    result = health_check()
    assert isinstance(result, HealthResponse)
    assert result.status == "ok"
    assert result.version == "0.1.0"


def test_root_health_check():
    """Verify top-level API health returns valid schema."""
    result = root_health()
    assert isinstance(result, HealthResponse)
    assert result.status == "ok"


def test_root_welcome_message():
    """Verify root endpoint message."""
    result = root()
    assert "VoiceBridge API is operational" in result["message"]
