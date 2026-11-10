from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

    # Gnani AI Prisma (STT) - Official endpoint & model
    GNANI_API_KEY: str = ""
    GNANI_PRISMA_ENDPOINT: str = "https://api.vachana.ai/stt/v3"
    GNANI_PRISMA_MODEL: str = "prisma-v3.0"

    # Gnani AI Timbre (TTS) - Official endpoint, model & voice
    GNANI_TIMBRE_ENDPOINT: str = "https://api.vachana.ai/api/v1/tts/inference"
    GNANI_TIMBRE_MODEL: str = "timbre-v2.5"
    GNANI_DEFAULT_VOICE: str = "Nalini"

    # LLM Service (Modular: gemini | openai | gnani_evon)
    LLM_PROVIDER: str = "gemini"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini-3.5-flash-lite"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    MAX_HISTORY_TURNS: int = 10

    # Audio limits
    MAX_AUDIO_SIZE_MB: int = 10
    MAX_RECORDING_DURATION_SEC: int = 30

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
