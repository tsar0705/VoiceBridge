import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.main import app
from app.schemas.voice_schema import HealthResponse, TranscribeResponse, SynthesizeResponse, ChatResponse
from app.services.prisma_service import PrismaService
from app.services.timbre_service import TimbreService
from app.services.llm_service import LLMService
from app.services.conversation_service import ConversationService
from app.utils.audio_utils import validate_audio_file, validate_audio_payload, get_audio_duration_seconds

def main():
    print(f"=== VoiceBridge Backend Scaffolding & Gnani Services Verification ===")
    print(f"Python Version: {sys.version.split()[0]}")
    print(f"FastAPI Application: {app.title} (v{app.version})")
    print(f"CORS Allowed Origins: {settings.cors_origin_list}")
    print(f"Gnani Prisma Endpoint: {settings.GNANI_PRISMA_ENDPOINT}")
    print(f"Gnani Prisma Model: {settings.GNANI_PRISMA_MODEL}")
    print(f"Gnani Timbre Endpoint: {settings.GNANI_TIMBRE_ENDPOINT}")
    print(f"Gnani Timbre Model: {settings.GNANI_TIMBRE_MODEL}")
    print(f"Gnani Default Voice: {settings.GNANI_DEFAULT_VOICE}")
    
    # Verify services initialization
    prisma = PrismaService()
    timbre = TimbreService()
    llm = LLMService()
    conv = ConversationService()
    
    assert timbre.normalize_language_code("Tamil") == "ta-IN"
    assert timbre.normalize_language_code("Hindi") == "hi-IN"
    assert timbre.normalize_language_code("English") == "en-IN"
    print("Timbre Language Locale Normalization: OK")
    
    conv.add_message("test-session", "user", "Vanakkam", "ta")
    history = conv.get_history("test-session")
    assert len(history) == 1, "Conversation service failed to store turn"
    print(f"Conversation Service Test: OK ({len(history)} turn stored)")
    
    # Verify routes registered
    route_paths = [route.path for route in app.routes]
    expected_paths = [
        "/api/health",
        "/api/voice/health",
        "/api/voice/transcribe",
        "/api/voice/synthesize",
        "/api/voice/chat",
        "/api/voice/session/{session_id}",
    ]
    for path in expected_paths:
        assert path in route_paths, f"Missing route {path}"
    print(f"Registered Endpoints: {expected_paths} - ALL PRESENT")
    print("=== Verification Successful! ===")

if __name__ == "__main__":
    main()
