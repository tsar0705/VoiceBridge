import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.voice_routes import router as voice_router
from app.schemas.voice_schema import HealthResponse

# Configure structured logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
)
logger = logging.getLogger("voicebridge")

app = FastAPI(
    title="VoiceBridge API",
    description="Multilingual AI Voice Assistant backend powered by Gnani AI Prisma & Timbre.",
    version="0.1.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Voice Routes
app.include_router(voice_router, prefix="/api")


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def root_health():
    """Top-level health check endpoint."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        gnani_configured=bool(settings.GNANI_API_KEY and settings.GNANI_API_KEY != "your_gnani_api_key_here"),
        llm_configured=bool(settings.LLM_API_KEY and settings.LLM_API_KEY != "your_llm_api_key_here"),
        models={
            "stt": settings.GNANI_PRISMA_MODEL,
            "tts": settings.GNANI_TIMBRE_MODEL,
            "llm": f"{settings.LLM_PROVIDER}:{settings.LLM_MODEL}",
        },
    )


@app.get("/", tags=["Health"])
def root():
    return {"message": "VoiceBridge API is operational. Visit /docs for OpenAPI specs."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
