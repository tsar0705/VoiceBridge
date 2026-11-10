import time
import uuid
import base64
import logging
from typing import Optional, Tuple
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status

from app.config import settings
from app.schemas.voice_schema import (
    HealthResponse,
    TranscribeResponse,
    SynthesizeRequest,
    SynthesizeResponse,
    ChatResponse,
    SessionResetResponse,
)
from app.services.prisma_service import PrismaService
from app.services.timbre_service import TimbreService
from app.services.llm_service import LLMService
from app.services.conversation_service import conversation_service
from app.utils.audio_utils import validate_audio_file, detect_audio_format

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice"])

prisma_service = PrismaService()
timbre_service = TimbreService()
llm_service = LLMService()


def resolve_response_language(preferred: Optional[str], detected_lang: Optional[str]) -> Tuple[str, str]:
    """
    Resolves the LLM target language string and the matching Timbre BCP-47 locale.
    Returns: (llm_target_language, timbre_locale)
    """
    pref = (preferred or "").strip().lower()
    
    # Auto-detection / follow detected mode
    if pref in ("", "auto", "follow", "detected"):
        det = (detected_lang or "").strip().lower()
        if det.startswith("ta"):
            return "Tamil", "ta-IN"
        elif det.startswith("hi"):
            return "Hindi", "hi-IN"
        elif det.startswith("en"):
            return "English", "en-IN"
        elif det in ("hi-en", "hinglish"):
            return "Hinglish", "hi-en"
        elif det in ("ta-en", "tanglish"):
            return "Tanglish", "ta-IN"
        elif det.startswith("te"):
            return "Telugu", "te-IN"
        elif det.startswith("kn"):
            return "Kannada", "kn-IN"
        elif det.startswith("ml"):
            return "Malayalam", "ml-IN"
        return "Tamil", "ta-IN"

    # Explicit user preference
    if pref in ("tamil", "ta", "ta-in"):
        return "Tamil", "ta-IN"
    elif pref in ("english", "en", "en-in"):
        return "English", "en-IN"
    elif pref in ("hindi", "hi", "hi-in"):
        return "Hindi", "hi-IN"
    elif pref in ("tanglish", "ta-en"):
        return "Tanglish", "ta-IN"
    elif pref in ("hinglish", "hi-en"):
        return "Hinglish", "hi-en"
    elif pref in ("telugu", "te"):
        return "Telugu", "te-IN"
    elif pref in ("kannada", "kn"):
        return "Kannada", "kn-IN"
    elif pref in ("malayalam", "ml"):
        return "Malayalam", "ml-IN"
    
    # Default fallback
    return preferred.strip(), "ta-IN"


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint reporting API status and service configuration readiness."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        gnani_configured=prisma_service.is_configured() and timbre_service.is_configured(),
        llm_configured=llm_service.is_configured(),
        models={
            "stt": settings.GNANI_PRISMA_MODEL,
            "tts": settings.GNANI_TIMBRE_MODEL,
            "llm": f"{settings.LLM_PROVIDER}:{settings.LLM_MODEL}",
        },
    )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: Optional[UploadFile] = File(None),
    audio_file: Optional[UploadFile] = File(None),
    language: Optional[str] = Form("indic-auto"),
    code_mix: Optional[bool] = Form(True),
):
    """
    Transcribes uploaded audio file via Gnani Prisma STT v3.
    Accepts audio in either 'audio_file' (Gnani standard) or 'file' multipart field.
    Returns transcript, detected language code, confidence score, and processing time.
    """
    target_file = audio_file or file
    if not target_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file provided or filename is missing.",
        )

    start_time = time.time()
    validate_audio_file(target_file, max_size_mb=settings.MAX_AUDIO_SIZE_MB)

    audio_bytes = await target_file.read()
    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty (0 bytes).",
        )

    if detect_audio_format(audio_bytes) == "webm":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="UNSUPPORTED_AUDIO_FORMAT: WebM audio is not supported by Gnani Prisma. Supported formats: flac, mp3, ogg, m4a, wav, aac. Please send PCM WAV audio.",
        )

    try:
        transcript, detected_lang, confidence = await prisma_service.transcribe_audio(
            audio_bytes=audio_bytes,
            filename=target_file.filename or "recording.wav",
            content_type=target_file.content_type or "audio/wav",
            language_code=language,
            code_mix=code_mix,
        )
        duration_ms = (time.time() - start_time) * 1000
        return TranscribeResponse(
            transcript=transcript,
            detected_language=detected_lang,
            confidence=confidence,
            model=settings.GNANI_PRISMA_MODEL,
            processing_time_ms=round(duration_ms, 2),
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (ConnectionError, TimeoutError) as e:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(e)}",
        )


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_speech(payload: SynthesizeRequest):
    """
    Synthesizes input text to speech using Gnani Timbre TTS v2.5.
    Returns synthesized WAV audio in Base64 encoding along with metadata.
    """
    start_time = time.time()
    try:
        audio_bytes, mime_type, duration = await timbre_service.synthesize_speech(
            text=payload.text,
            language=payload.language,
            voice=payload.voice,
            speed=payload.speed or 1.0,
        )
        duration_ms = (time.time() - start_time) * 1000
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        return SynthesizeResponse(
            audio_base64=audio_b64,
            format=mime_type,
            duration_sec=duration,
            model=settings.GNANI_TIMBRE_MODEL,
            processing_time_ms=round(duration_ms, 2),
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (ConnectionError, TimeoutError) as e:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech synthesis failed: {str(e)}",
        )


@router.post("/chat", response_model=ChatResponse)
async def voice_chat(
    file: Optional[UploadFile] = File(None),
    audio_file: Optional[UploadFile] = File(None),
    session_id: Optional[str] = Form(None),
    response_language: Optional[str] = Form("auto"),
    voice: Optional[str] = Form(None),
):
    """
    Complete end-to-end multimodal voice conversation pipeline:
    Accepts audio in either 'audio_file' (Gnani standard) or 'file' multipart field.
    1. Validates audio format, size, and duration.
    2. Transcribes spoken speech via Gnani Prisma STT v3 with auto-detect & code-mix.
    3. Resolves preferred response language and target BCP-47 locale.
    4. Retrieves active session history and invokes modular LLM for conversational reasoning.
    5. Synthesizes voice reply using Gnani Timbre TTS v2.5.
    6. Commits conversation turns atomically to session memory upon pipeline success.
    7. Returns transcript, detected language, AI response, Base64 WAV audio, and timing metadata.
    """
    target_file = audio_file or file
    if not target_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file provided or filename is missing.",
        )

    start_time = time.time()
    active_session_id = (session_id or "").strip() or f"sess_{uuid.uuid4().hex[:12]}"

    # 1. Audio validation
    validate_audio_file(target_file, max_size_mb=settings.MAX_AUDIO_SIZE_MB)
    audio_bytes = await target_file.read()
    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty (0 bytes).",
        )

    if detect_audio_format(audio_bytes) == "webm":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="UNSUPPORTED_AUDIO_FORMAT: WebM audio is not supported by Gnani Prisma. Supported formats: flac, mp3, ogg, m4a, wav, aac. Please send PCM WAV audio.",
        )

    # 2. Stage 1: Gnani Prisma STT Transcription
    try:
        transcript, detected_lang, confidence = await prisma_service.transcribe_audio(
            audio_bytes=audio_bytes,
            filename=target_file.filename or "recording.wav",
            content_type=target_file.content_type or "audio/wav",
            language_code="indic-auto",
            code_mix=True,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Prisma Auth Error: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Prisma Validation Error: {str(e)}")
    except (ConnectionError, TimeoutError) as e:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=f"Prisma Gateway Timeout: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Prisma STT Failed: {str(e)}")

    if not transcript or not transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No intelligible speech could be transcribed from the provided audio.",
        )

    # 3. Resolve target spoken language and Timbre locale
    target_lang_name, timbre_locale = resolve_response_language(
        preferred=response_language,
        detected_lang=detected_lang,
    )

    # 4. Stage 2: Modular LLM Reasoning
    history = conversation_service.get_history(active_session_id)
    try:
        ai_response_text = await llm_service.generate_response(
            user_message=transcript,
            conversation_history=history,
            target_language=target_lang_name,
            detected_language=detected_lang,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"LLM Auth Error: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"LLM Configuration/Request Error: {str(e)}")
    except (ConnectionError, TimeoutError) as e:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=f"LLM Gateway Timeout: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM Reasoning Failed: {str(e)}")

    # 5. Stage 3: Gnani Timbre TTS Speech Synthesis
    try:
        audio_out_bytes, mime_type, duration_sec = await timbre_service.synthesize_speech(
            text=ai_response_text,
            language=timbre_locale,
            voice=voice or settings.GNANI_DEFAULT_VOICE,
            speed=1.0,
        )
        audio_b64 = base64.b64encode(audio_out_bytes).decode("utf-8")
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Timbre Auth Error: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Timbre Validation Error: {str(e)}")
    except (ConnectionError, TimeoutError) as e:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=f"Timbre Gateway Timeout: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Timbre Synthesis Failed: {str(e)}")

    # 6. Commit conversation turns to session memory only after full pipeline success
    conversation_service.add_message(
        session_id=active_session_id,
        role="user",
        content=transcript,
        language=detected_lang,
    )
    conversation_service.add_message(
        session_id=active_session_id,
        role="assistant",
        content=ai_response_text,
        language=target_lang_name,
    )

    duration_ms = (time.time() - start_time) * 1000

    return ChatResponse(
        session_id=active_session_id,
        transcription=transcript,
        detected_input_language=detected_lang,
        ai_response_text=ai_response_text,
        output_language=target_lang_name,
        audio_base64=audio_b64,
        audio_format=mime_type,
        audio_duration_sec=duration_sec,
        models={
            "stt": settings.GNANI_PRISMA_MODEL,
            "llm": f"{settings.LLM_PROVIDER}:{settings.LLM_MODEL}",
            "tts": settings.GNANI_TIMBRE_MODEL,
        },
        processing_time_ms=round(duration_ms, 2),
    )


@router.delete("/session/{session_id}", response_model=SessionResetResponse)
def reset_session(session_id: str):
    """
    Clears the conversation context for the specified session ID.
    Enables clean conversation resets from the user interface.
    """
    existed = conversation_service.clear_history(session_id)
    return SessionResetResponse(
        status="cleared",
        session_id=session_id,
        message=f"Session '{session_id}' cleared successfully." if existed else f"Session '{session_id}' was not active or already empty.",
    )
