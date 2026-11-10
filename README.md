# VoiceBridge – Multilingual AI Voice Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3+-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6.0+-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.4+-38B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![Tests](https://img.shields.io/badge/Pytest-67%20Passed%20(100%25)-brightgreen.svg)](docs/testing.md)

**VoiceBridge** is a production-quality, multilingual, voice-first AI assistant designed for Indian users and built for **The Great Indian AI Internship Challenge organized by Gnani AI**.

It enables Indian users to converse naturally in their native languages and everyday code-mixed speech (**Tamil, English, Hindi, Tanglish, Hinglish**), powered by:
- **Gnani AI Prisma (STT v3)**: Automatic language detection (`indic-auto`) and code-mixed transcription (`codemix`).
- **Modular LLM Reasoning Engine**: Context-aware, conversational multi-turn intelligence (Google Gemini 3.5 Flash Lite, OpenAI, or Gnani Evon) tuned for concise, spoken responses.
- **Gnani AI Timbre (TTS v2.5)**: High-fidelity Indic voice synthesis with verified catalog voices (`Nalini`).
- **Sliding-Window Session Memory**: Maintains conversational context across multi-turn exchanges with strict user isolation.

---

## 1. Key Features

- **Multilingual & Code-Mixed Speech**: First-class support for Tamil, English, Hindi, Tanglish (Tamil + English), and Hinglish (Hindi + English).
- **Voice-First Interaction**: Browser-native microphone recording with real-time animated waveform visualization and 30-second duration guard.
- **Auto Language Detection & Persona Resolution**: Understands the user's spoken language automatically or allows explicit response language preferences.
- **TTS-Optimized Reasoning**: System prompts automatically sanitize markdown, asterisks, URLs, and code blocks to ensure fluid, natural voice playback.
- **Session Isolation & Multi-Turn Retention**: Sliding-window conversation retention with one-click atomic session reset (`DELETE /api/voice/session/{session_id}`).
- **Interactive Audio Player**: Base64-to-Blob audio player with time tracking, scrub bar, and variable playback speeds (`1x`, `1.25x`, `1.5x`, `0.85x`).

---

## 2. End-to-End Multimodal Architecture

```text
User Speech (Microphone)
       │
       ▼
React + Vite Frontend (MediaRecorder Audio Capture)
       │
       ▼
Browser Web Audio API (Decodes WebM/Opus -> Resamples to 16kHz Mono 16-bit PCM WAV)
       │
       │ POST /api/voice/chat (Multipart Form: recording.wav, audio/wav)
       ▼
FastAPI Backend Orchestrator
       │
       ├── 1. Audio Signature Validation (RIFF/WAVE verification, rejects WebM, size <= 10MB, duration <= 30s)
       │
       ├── 2. Gnani Prisma STT (prisma-v3.0 / indic-auto / codemix)
       │      └── Returns transcript + detected language (e.g. ta-IN, hi-IN, en-IN)
       │
       ├── 3. Conversation Session Store (In-memory, session isolation, max 10 turns)
       │      └── Injects previous turns into reasoning context
       │
       ├── 4. Modular LLM Service (Gemini 3.5 Flash Lite / OpenAI / Evon)
       │      └── Synthesizes concise, conversational reply (1-3 sentences)
       │
       ├── 5. Gnani Timbre TTS (timbre-v2.5 / voice: Nalini / 48kHz WAV)
       │      └── Generates natural-sounding spoken audio
       │
       └── 6. Atomic Session Update (Commits turns only upon full pipeline success)
             └── Returns Base64 WAV audio + transcript + timing metadata
       │
       ▼
Frontend AudioPlayer (Auto-play / Replay / Speed Control)
```

---

## 3. Technology Stack

- **Frontend**: React 18, Vite 6, Tailwind CSS, Lucide React icons, Browser MediaRecorder API, Web Audio API (`AudioContext`).
- **Backend**: Python 3.11/3.14, FastAPI, Uvicorn, Pydantic v2, Pydantic Settings, HTTPX, Requests.
- **AI Engines**:
  - Speech-to-Text: **Gnani AI Prisma v3.0** (`https://api.vachana.ai/stt/v3`)
  - Reasoning: **Google Gemini 3.5 Flash Lite** / OpenAI API / Gnani Evon
  - Text-to-Speech: **Gnani AI Timbre v2.5** (`https://api.vachana.ai/api/v1/tts/inference`)
- **Testing & Quality Assurance**: Pytest, Pytest-Asyncio, HTTPX Mocking, 61 automated tests (100% pass rate).

---

## 4. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health probe, model versions, and credentials readiness |
| `POST` | `/api/voice/transcribe` | Standalone speech-to-text via Gnani Prisma STT v3 |
| `POST` | `/api/voice/synthesize` | Standalone text-to-speech via Gnani Timbre TTS v2.5 |
| `POST` | `/api/voice/chat` | Complete end-to-end multimodal voice conversation turn |
| `DELETE` | `/api/voice/session/{session_id}` | Clears conversation context for a session ID |

---

## 5. Local Setup Instructions

### Prerequisites
- Python 3.10+
- Node.js 18.0+ and `npm`

### 1. Backend Setup
```bash
cd backend

# Create virtual environment (optional)
python -m venv venv
# Windows: venv\Scripts\activate | Linux/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

Edit `backend/.env` with your credentials:
```ini
GNANI_API_KEY=your_gnani_api_key_here
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite
LLM_API_KEY=your_google_ai_studio_api_key_here
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173
```

Run test suite:
```bash
python -m pytest -v
# 61 passed, 100% pass rate
```

Start backend:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- Interactive Swagger API Documentation: `http://localhost:8000/docs`
- Health Probe: `http://localhost:8000/api/health`

### 2. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
```
Ensure `frontend/.env` contains:
```ini
VITE_API_BASE_URL=http://localhost:8000/api
```

Start development server:
```bash
npm run dev
```
Open your browser at `http://localhost:5173`.

---

## 6. Production Deployment

VoiceBridge is designed for simple, decoupled cloud deployment:
- **Frontend**: [Vercel](https://vercel.com) (Edge CDN with instant builds)
- **Backend**: [Render](https://render.com) (Python Web Service or Docker container)

Full step-by-step instructions, cost analysis, and cold-start mitigations are documented in [docs/deployment.md](docs/deployment.md).

---

## 7. Known Limitations

1. **Maximum Audio Duration**: Gnani Prisma STT enforces a 30-second recording limit per utterance. The frontend and backend automatically enforce this threshold.
2. **Free-Tier Backend Sleep**: When deployed on free hosting tiers (such as Render Free), the web service spins down after 15 minutes of inactivity. Initial request after idle may incur a ~50s cold start.
3. **Browser Audio Policies**: Web browsers require explicit user interaction (click/tap) before audio can autoplay. The UI includes an inline playback trigger if autoplay is blocked by browser security policy.

---

## 8. Documentation & Submission Resources

- **[Architecture Deep-Dive](docs/architecture.md)**: System design, dataflow diagrams, and module responsibilities.
- **[Testing Strategy & Matrix](docs/testing.md)**: Breakdown of unit, mocked, and live integration tests.
- **[Production Deployment Guide](docs/deployment.md)**: Step-by-step instructions for Vercel and Render.
- **[Submission Materials & Demo Storyboard](docs/submission.md)**: Challenge submission write-up, key highlights, 90-second demo script, and social announcement draft.
