/**
 * VoiceBridge API Service Client
 * Handles communication with the FastAPI backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

/**
 * Checks backend health and configuration status.
 */
export async function checkHealth() {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status: ${response.status}`);
  }
  return response.json();
}

/**
 * Transcribes an audio recording using Gnani Prisma STT.
 */
export async function transcribeAudio(audioBlob, language = 'indic-auto', codeMix = true) {
  const formData = new FormData();
  formData.append('audio_file', audioBlob, 'recording.wav');
  formData.append('file', audioBlob, 'recording.wav');
  formData.append('language', language);
  formData.append('code_mix', codeMix.toString());

  const response = await fetch(`${API_BASE_URL}/voice/transcribe`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Transcription error: ${response.status}`);
  }
  return response.json();
}

/**
 * Synthesizes text into speech using Gnani Timbre TTS.
 */
export async function synthesizeSpeech(text, language = 'ta-IN', voice = null, speed = 1.0) {
  const response = await fetch(`${API_BASE_URL}/voice/synthesize`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      text,
      language,
      voice,
      speed,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Speech synthesis error: ${response.status}`);
  }
  return response.json();
}

/**
 * Complete multi-turn voice chat interaction.
 */
export async function sendVoiceChat(audioBlob, sessionId, responseLanguage = 'auto', voice = null) {
  const formData = new FormData();
  formData.append('audio_file', audioBlob, 'recording.wav');
  formData.append('file', audioBlob, 'recording.wav');
  if (sessionId) formData.append('session_id', sessionId);
  if (responseLanguage) formData.append('response_language', responseLanguage);
  if (voice) formData.append('voice', voice);

  const response = await fetch(`${API_BASE_URL}/voice/chat`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Voice chat error: ${response.status}`);
  }
  return response.json();
}

/**
 * Clears conversation history for the given session ID.
 */
export async function resetSession(sessionId) {
  if (!sessionId) return { status: 'cleared', session_id: '' };
  const response = await fetch(`${API_BASE_URL}/voice/session/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Session reset error: ${response.status}`);
  }
  return response.json();
}
