# VoiceBridge Architecture Document

## 1. Executive Summary

**VoiceBridge** is a production-grade, multilingual AI voice assistant tailored for Indian languages and code-mixed speech (**Tamil, English, Hindi, Tanglish, Hinglish**). Developed for **The Great Indian AI Internship Challenge organized by Gnani AI**, VoiceBridge coordinates:
1. **Gnani AI Prisma (STT v3)** for automatic language detection (`indic-auto`) and code-mixed transcription (`codemix`).
2. **Modular LLM Reasoning Service** (supporting Google Gemini and OpenAI-compatible endpoints including Gnani Evon) optimized for concise spoken conversational turns.
3. **Gnani AI Timbre (TTS v2.5)** for natural-sounding Indic voice synthesis with verified catalog voices (`Nalini`).
4. **Stateful Session Store** for multi-turn context retention with strict session isolation.

---

## 2. End-to-End Multimodal Architecture

VoiceBridge follows a clean **modular monolithic architecture** that decouples frontend client interaction, backend orchestration, and AI model providers.

```mermaid
flowchart TD
    subgraph Client["Frontend (React + Vite + Tailwind CSS)"]
        UI["VoiceBridge UI"]
        MR["MediaRecorder API\n(Microphone Audio Capture)"]
        AP["AudioPlayer Component\n(Play / Pause / Speed)"]
        CL["API Client Service"]
    end

    subgraph Server["Backend Orchestrator (FastAPI)"]
        API["FastAPI API Router\n(/api/voice/* & /api/health)"]
        AV["Audio Validator\n(MIME, size <= 10MB, duration <= 30s)"]
        CS["Conversation Context Service\n(In-memory Session Store, max 10 turns)"]
    end

    subgraph AIProviders["AI Model Layer"]
        Prisma["Gnani AI Prisma (STT v3)\n(prisma-v3.0 / indic-auto / codemix)"]
        LLM["Modular LLM Service\n(Gemini 2.5 Flash / OpenAI / Evon)"]
        Timbre["Gnani AI Timbre (TTS v2.5)\n(timbre-v2.5 / voice: Nalini / 48kHz WAV)"]
    end

    MR -->|Audio Blob (webm/wav)| CL
    CL -->|POST /api/voice/chat| API
    API --> AV
    AV -->|Validated Audio Buffer| Prisma
    Prisma -->|Transcript & Detected Language (e.g. ta-IN)| API
    API --> CS
    CS -->|History Turns + New Prompt| LLM
    LLM -->|Concise Conversational Text (1-3 sentences)| API
    API --> Timbre
    Timbre -->|Binary WAV Audio Stream (48kHz Mono)| API
    API -->|Atomic Update on Pipeline Success| CS
    API -->|JSON + Base64 WAV Audio Payload| CL
    CL --> UI
    CL --> AP
```

---

## 3. End-to-End Voice Chat Pipeline Specification

When a user submits voice speech to `POST /api/voice/chat`:

1. **Audio Validation**:
   - Supported containers: `.wav`, `.webm`, `.ogg`, `.mp3`, `.flac`.
   - File size enforced $\le 10$MB.
   - Max recording duration enforced $\le 30$ seconds (per official Gnani STT API limits).
2. **Speech-to-Text (Gnani Prisma STT v3)**:
   - Endpoint: `https://api.vachana.ai/stt/v3`
   - Headers: `X-API-Key-ID: <GNANI_API_KEY>`
   - Form parameters: `model="prisma-v3.0"`, `language_code="indic-auto"`, `format="codemix"`.
   - Returns normalized `(transcript, detected_language_code, confidence)`.
3. **Language Resolution**:
   - If user requested `"auto"`: dynamically adopts the detected spoken language (e.g., `ta-IN` $\rightarrow$ Tamil, `hi-IN` $\rightarrow$ Hindi, `en-IN` $\rightarrow$ English).
   - If user explicitly requested a language (`Tamil`, `English`, `Hindi`, `Tanglish`, `Hinglish`): routes prompt generation and TTS synthesis to that specific language.
4. **Context Retrieval & LLM Reasoning**:
   - Retrieves active turn history for `session_id` from `ConversationService` (up to 10 previous turns).
   - The modular LLM prompt strictly enforces:
     - 1 to 3 short conversational sentences ($< 40$ words).
     - Natural spoken persona without Markdown bullet points, asterisks, or code formatting.
     - Natural code-mixed phrasing for Tanglish/Hinglish requests.
   - Text sanitizer strips any markdown artifacts before speech synthesis.
5. **Speech Synthesis (Gnani Timbre TTS v2.5)**:
   - Endpoint: `https://api.vachana.ai/api/v1/tts/inference`
   - Headers: `X-API-Key-ID: <GNANI_API_KEY>`, `Content-Type: application/json`
   - Payload:
     ```json
     {
       "text": "<LLM response text>",
       "voice": "Nalini",
       "model": "timbre-v2.5",
       "language": "ta-IN",
       "speed": 1.0,
       "audio_config": {
         "sample_rate": 48000,
         "num_channels": 1,
         "sample_width": 2,
         "encoding": "linear_pcm",
         "container": "wav"
       }
     }
     ```
   - Receives raw binary WAV audio stream.
   - Extracts playback duration from the WAV header (handling streaming placeholder chunks).
   - Encodes audio into Base64 for instant frontend playback without server-side disk storage.
6. **Atomic Session Update**:
   - User turn and Assistant turn are committed to session storage **only after** all three stages succeed.
   - If any stage fails (e.g. STT timeout, LLM auth error, TTS quota exceeded), history remains clean.

---

## 4. API Endpoint Contracts

### `GET /api/health`
- **Description**: Top-level system health and configuration status.
- **Response**:
  ```json
  {
    "status": "ok",
    "version": "0.1.0",
    "gnani_configured": true,
    "llm_configured": true,
    "models": {
      "stt": "prisma-v3.0",
      "tts": "timbre-v2.5",
      "llm": "gemini:gemini-1.5-flash"
    }
  }
  ```

### `POST /api/voice/transcribe`
- **Description**: Standalone audio transcription via Gnani Prisma.
- **Form Data**:
  - `file`: Audio file (`UploadFile`)
  - `language`: `indic-auto` (default) or specific language code
  - `code_mix`: `true` (default)
- **Response**:
  ```json
  {
    "transcript": "வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்",
    "detected_language": "ta-IN",
    "confidence": 0.98,
    "model": "prisma-v3.0",
    "processing_time_ms": 152.4
  }
  ```

### `POST /api/voice/synthesize`
- **Description**: Standalone speech synthesis via Gnani Timbre.
- **JSON Body**:
  ```json
  {
    "text": "வணக்கம், VoiceBridge இல் உங்கள் வருகை நல்வரவாகுக!",
    "language": "ta-IN",
    "voice": "Nalini",
    "speed": 1.0
  }
  ```
- **Response**:
  ```json
  {
    "audio_base64": "UklGRu...",
    "format": "audio/wav",
    "duration_sec": 2.24,
    "model": "timbre-v2.5",
    "processing_time_ms": 520.1
  }
  ```

### `POST /api/voice/chat`
- **Description**: Complete end-to-end voice conversation turn.
- **Form Data**:
  - `file`: Audio file (`UploadFile`)
  - `session_id`: Session ID (`sess_xxx`, optional)
  - `response_language`: `"auto"` (default), `"Tamil"`, `"English"`, `"Hindi"`, `"Tanglish"`, or `"Hinglish"`
  - `voice`: Optional catalog voice name (defaults to `"Nalini"`)
- **Response**:
  ```json
  {
    "session_id": "sess_8f9a2b",
    "transcription": "வணக்கம், இன்றைய செய்தி என்ன?",
    "detected_input_language": "ta-IN",
    "ai_response_text": "வணக்கம்! இன்றைய முக்கிய செய்திகள் இதோ.",
    "output_language": "Tamil",
    "audio_base64": "UklGRu...",
    "audio_format": "audio/wav",
    "audio_duration_sec": 2.1,
    "models": {
      "stt": "prisma-v3.0",
      "llm": "gemini:gemini-1.5-flash",
      "tts": "timbre-v2.5"
    },
    "processing_time_ms": 1140.5
  }
  ```

### `DELETE /api/voice/session/{session_id}`
- **Description**: Resets/clears conversation history for a specific session ID.
- **Response**:
  ```json
  {
    "status": "cleared",
    "session_id": "sess_8f9a2b",
    "message": "Session 'sess_8f9a2b' cleared successfully."
  }
  ```

---

## 5. Security & Reliability Architecture

- **Zero Client Credential Leakage**: All Gnani AI keys and LLM tokens remain exclusively on the server in `.env`.
- **Ephemeral Audio Processing**: Binary audio streams are processed in-memory and converted into Base64 responses without permanent disk storage.
- **Atomic State Consistency**: Failed conversation turns do not pollute the session history.
- **Standardized Error Handling**: Structured HTTP status codes (`400`, `401`, `415`, `502`, `504`) with actionable messages, completely masking internal tracebacks.
