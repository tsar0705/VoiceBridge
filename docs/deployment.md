# VoiceBridge Production Deployment Guide

This guide details the recommended production architecture, step-by-step deployment instructions, operational trade-offs, and cost analysis for **VoiceBridge**.

---

## 1. Recommended Production Architecture

```text
[ User Browser / Mobile ]
           │
           │ HTTPS
           ▼
[ Vercel Edge CDN (Frontend) ]
  • React + Vite Single Page Application
  • MediaRecorder audio capture
  • AudioPlayer Base64 playback
           │
           │ HTTPS / REST (CORS enabled)
           ▼
[ Render Web Service (Backend Orchestrator) ]
  • FastAPI on Python 3.11/3.12 (uvicorn --workers 2)
  • In-memory session context isolation
  • Audio validation (<= 10MB, <= 30s)
           │
           ├── (1) POST /stt/v3 ────────────────────────► [ Gnani AI Prisma STT ]
           │   (indic-auto, codemix)
           │
           ├── (2) POST /models/{model}:generateContent ─► [ Google Gemini 3.5 Flash Lite ]
           │   (Contextual reasoning)
           │
           └── (3) POST /api/v1/tts/inference ──────────► [ Gnani AI Timbre TTS ]
               (voice: Nalini, 48kHz WAV)
```

---

## 2. Platform Trade-offs, Free-Tier Limits & Cost Analysis

| Component | Platform | Free-Tier Limits & Considerations | Cold Start & Latency | Estimated API Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend** | **Vercel** | 100 GB bandwidth/month, unlimited builds for personal hobby tier. Global Edge CDN. | **Zero cold start** (~5-20ms edge delivery). | **Free** |
| **Backend** | **Render** | 512 MB RAM, 0.1 CPU on Free tier. Spins down after 15 minutes of inactivity. | **~50s cold start** on initial request after idle. *(Upgrade to \$7/mo Starter tier keeps it alive 24/7).* | **Free** (or \$7/mo for always-on) |
| **STT Engine** | **Gnani Prisma** | Prisma v3.0, 30s max duration per utterance. | ~0.8s – 1.8s per transcription. | Consumes Gnani AI challenge credits. |
| **LLM Engine** | **Gemini 3.5 Flash Lite** | Free tier allows up to 15 Requests/Min, 1M Tokens/Min. | **~1.7s – 2.0s** generation time. | **Free** (within rate limits). |
| **TTS Engine** | **Gnani Timbre** | Timbre v2.5, 48kHz mono WAV. | ~0.9s – 1.6s per synthesis. | Consumes Gnani AI challenge credits. |

---

## 3. Backend Deployment Instructions (Render)

### Step 1: Connect Git Repository to Render
1. Sign in to your [Render Dashboard](https://dashboard.render.com).
2. Click **New +** and select **Web Service**.
3. Connect your Git repository containing the VoiceBridge codebase.

### Step 2: Configure Service Settings
- **Name**: `voicebridge-backend`
- **Root Directory**: `backend`
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`
- **Health Check Path**: `/api/health`
- **Instance Type**: `Free` (or `Starter` for 24/7 always-on without spin-down)

### Step 3: Add Backend Environment Variables
In the Render **Environment** tab, add the following variables (refer to `backend/.env.production.example`):

| Variable Name | Example / Production Value | Notes |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.11.9` | Ensures consistent Python runtime. |
| `GNANI_API_KEY` | *(Paste your actual Gnani API Key)* | Kept secure in Render; never in Git. |
| `GNANI_PRISMA_ENDPOINT`| `https://api.vachana.ai/stt/v3` | Official Prisma STT endpoint. |
| `GNANI_PRISMA_MODEL` | `prisma-v3.0` | Production Indic STT model. |
| `GNANI_TIMBRE_ENDPOINT`| `https://api.vachana.ai/api/v1/tts/inference` | Official Timbre TTS endpoint. |
| `GNANI_TIMBRE_MODEL` | `timbre-v2.5` | Production Indic TTS model. |
| `GNANI_DEFAULT_VOICE` | `Nalini` | Verified natural voice persona. |
| `LLM_PROVIDER` | `gemini` | Modular LLM provider. |
| `LLM_MODEL` | `gemini-3.5-flash-lite` | Stable, low-latency reasoning model. |
| `LLM_API_KEY` | *(Paste your actual Google AI Studio Key)*| Kept secure in Render. |
| `CORS_ORIGINS` | `https://voicebridge.vercel.app,http://localhost:5173` | Add your Vercel URL once generated. |
| `MAX_AUDIO_SIZE_MB` | `10` | Enforces audio upload limit. |
| `MAX_RECORDING_DURATION_SEC`| `30` | Matches Gnani STT limit. |

4. Click **Deploy Web Service**.
5. Once deployment finishes, note down your backend URL:
   `https://voicebridge-backend.onrender.com`
6. Test health: `curl https://voicebridge-backend.onrender.com/api/health`

---

## 4. Frontend Deployment Instructions (Vercel)

### Step 1: Connect Git Repository to Vercel
1. Sign in to your [Vercel Dashboard](https://vercel.com).
2. Click **Add New...** $\rightarrow$ **Project**.
3. Import your VoiceBridge repository.

### Step 2: Configure Project Settings
- **Framework Preset**: `Vite`
- **Root Directory**: `frontend`
- **Build Command**: `npm run build`
- **Output Directory**: `dist`

### Step 3: Add Frontend Environment Variable
In the **Environment Variables** section:

| Key | Value |
| :--- | :--- |
| `VITE_API_BASE_URL` | `https://voicebridge-backend.onrender.com/api` |

*(Replace with your actual Render backend URL followed by `/api`)*

### Step 4: Deploy & Close CORS Loop
1. Click **Deploy**.
2. Once deployed, Vercel will provide your live URL (e.g., `https://voicebridge-xxx.vercel.app`).
3. Return to your Render backend dashboard and ensure `CORS_ORIGINS` contains this exact Vercel URL.
4. Open the Vercel URL in your browser and verify end-to-end voice chat.
