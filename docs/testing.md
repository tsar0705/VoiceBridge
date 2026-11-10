# VoiceBridge Comprehensive Testing Strategy & Plan

This document outlines the testing strategy, test matrix, and verification protocols for **VoiceBridge**.

---

## 1. Test Pyramid & Methodology

We distinguish between two strict tiers of testing:
1. **Automated Unit & Mocked Tests**: Fast, deterministic test suite using `pytest`, `httpx`, and `unittest.mock`. Verifies API schema contracts, binary audio synthesis handling, audio duration constraints ($\le 30$ seconds), multi-turn conversation memory, error codes (`400`, `401`, `415`, `429`, `502`, `504`), timeouts, and end-to-end pipeline orchestration without consuming live Gnani AI or LLM credits.
2. **Real API Integration Tests**: Live integration tests that send real audio to Gnani Prisma STT (`https://api.vachana.ai/stt/v3`) and synthesize real speech with Gnani Timbre (`https://api.vachana.ai/api/v1/tts/inference`). Verified in Phase 2.5 with 100% transcription accuracy.

---

## 2. Test Matrix

| Test Suite / Scope | Target Language / Scenario | Mocked or Live | Expected Outcome | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Complete Voice Pipeline** | Full turn: Audio in $\rightarrow$ STT $\rightarrow$ LLM $\rightarrow$ TTS $\rightarrow$ Audio out | Mocked | Returns `ChatResponse`, commits history atomically | **PASSED** (10/10) |
| **Pipeline Partial Failures** | Prisma failure / LLM timeout / Timbre error | Mocked | Returns proper HTTP 401/502/504; history remains clean | **PASSED** |
| **Multi-Turn Retention** | Context preservation across turns in same session | Mocked | Prior user & assistant messages provided to LLM | **PASSED** |
| **Session Isolation** | Concurrent sessions with different session IDs | Mocked | Context is strictly isolated with no cross-talk | **PASSED** |
| **Conversation Reset** | `DELETE /api/voice/session/{session_id}` | Mocked | Session context cleared; next turn starts fresh | **PASSED** |
| **Language Resolution** | Auto mode (follows detected language) & Explicit mode | Mocked | Correct LLM persona and Timbre locale applied | **PASSED** |
| **Modular LLM Service** | Gemini & OpenAI-compatible provider integrations | Mocked | Structured requests, error handling, rate limits | **PASSED** (9/9) |
| **LLM TTS Sanitization** | Strip markdown, asterisks, hashtags, URLs | Unit | Generates natural spoken text for TTS | **PASSED** |
| **Conversation Store** | In-memory sliding window history (max turns) | Unit | Sliding window enforced, strict isolation | **PASSED** (5/5) |
| **Prisma STT** | Auto-Detect & Code-Mix (`indic-auto`, `codemix`) | Mocked | Normalized transcript, language code, confidence | **PASSED** (11/11) |
| **Timbre TTS** | Multilingual Synthesis (`ta-IN`, `en-IN`, `hi-IN`) | Mocked | Raw binary audio payload, WAV duration header | **PASSED** (11/11) |
| **Audio Utils** | WAV duration extraction / Magic bytes / WebM rejection | Unit | Accurate duration & WebM rejected with 415 | **PASSED** (10/10) |
| **Voice Routes** | `/transcribe`, `/synthesize`, `/health`, WebM guard | Mocked | Correct HTTP status codes & Base64 audio | **PASSED** (7/7) |
| **Health Probes** | `/api/health` & `/api/voice/health` | Unit | Operational status & model readiness | **PASSED** (4/4) |

**Total Backend Automated Tests:** **67 passed, 0 failed (100% pass rate)**.

---

## 3. Running Automated Tests

```bash
# Navigate to backend directory
cd backend

# Run all automated tests
python -m pytest -v
```
