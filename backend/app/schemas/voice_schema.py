from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    gnani_configured: bool = False
    llm_configured: bool = False
    models: Dict[str, str] = Field(
        default_factory=lambda: {
            "stt": "prisma-v3.0",
            "tts": "timbre-v2.5",
            "llm": "gemini-1.5-flash",
        }
    )


class TranscribeResponse(BaseModel):
    transcript: str
    detected_language: Optional[str] = None
    confidence: Optional[float] = None
    model: str
    processing_time_ms: float


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    language: str = Field(default="ta-IN", description="Target language locale (e.g. ta-IN, en-IN, hi-IN)")
    voice: Optional[str] = Field(default=None, description="Voice ID from catalog (e.g. Nalini)")
    speed: Optional[float] = Field(default=1.0, ge=0.5, le=2.0)


class SynthesizeResponse(BaseModel):
    audio_base64: Optional[str] = None
    audio_url: Optional[str] = None
    format: str = "audio/wav"
    duration_sec: Optional[float] = None
    model: str
    processing_time_ms: float


class ChatTurn(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str
    language: Optional[str] = None
    timestamp: Optional[float] = None


class ChatResponse(BaseModel):
    session_id: str
    transcription: str
    detected_input_language: Optional[str] = None
    ai_response_text: str
    output_language: str
    audio_base64: Optional[str] = None
    audio_url: Optional[str] = None
    audio_format: str = "audio/wav"
    audio_duration_sec: Optional[float] = None
    models: Dict[str, str] = Field(
        default_factory=lambda: {
            "stt": "prisma-v3.0",
            "llm": "gemini-1.5-flash",
            "tts": "timbre-v2.5",
        }
    )
    processing_time_ms: float


class SessionResetResponse(BaseModel):
    status: str = "cleared"
    session_id: str
    message: str = "Conversation history cleared successfully."
