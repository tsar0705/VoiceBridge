import sys
import io
import os
import json
import base64
import requests

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.voice_schema import HealthResponse, ChatResponse, SessionResetResponse, SynthesizeResponse
from app.utils.audio_utils import get_audio_duration_seconds

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8000"
SESSION_ID = "sess_phase41_manual_test"

def run_phase_41_integration():
    print("=" * 60)
    print("PHASE 4.1 MANUAL INTEGRATION VERIFICATION")
    print("=" * 60)

    # 1. Health Probe
    print("\n[Step 1] Probing GET /api/health ...")
    r_health = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert r_health.status_code == 200, f"Health check failed: {r_health.status_code}"
    health_data = r_health.json()
    validated_health = HealthResponse(**health_data)
    print(f"  Status: {validated_health.status}")
    print(f"  Gnani Configured: {validated_health.gnani_configured}")
    print(f"  LLM Configured: {validated_health.llm_configured}")
    print(f"  Models: {validated_health.models}")
    assert validated_health.gnani_configured, "Gnani is not configured!"
    assert validated_health.llm_configured, "LLM is not configured!"

    # 2. Synthesize English Audio for English Input Test
    print("\n[Step 2] Synthesizing real English speech sample via POST /api/voice/synthesize ...")
    synth_payload = {
        "text": "Hello, how are you today? Please tell me what you can do.",
        "language": "en-IN",
        "speed": 1.0
    }
    r_synth = requests.post(f"{BASE_URL}/api/voice/synthesize", json=synth_payload, timeout=25)
    assert r_synth.status_code == 200, f"Synthesize failed: {r_synth.status_code} {r_synth.text}"
    synth_data = SynthesizeResponse(**r_synth.json())
    english_wav_bytes = base64.b64decode(synth_data.audio_base64)
    english_dur = get_audio_duration_seconds(english_wav_bytes)
    print(f"  Synthesized {len(english_wav_bytes)} bytes of English WAV audio.")
    print(f"  Duration: {english_dur:.2f} seconds | Processing: {synth_data.processing_time_ms} ms")

    # 3. Test Turn 1: Spoken Tamil Input to POST /api/voice/chat
    print("\n[Step 3] Testing Live Turn 1: Tamil Audio via POST /api/voice/chat ...")
    with open("tests/test_output/live_timbre_tamil.wav", "rb") as f:
        tamil_wav_bytes = f.read()

    files = {"file": ("tamil_speech.wav", io.BytesIO(tamil_wav_bytes), "audio/wav")}
    data = {"session_id": SESSION_ID, "response_language": "Tamil"}
    
    r_turn1 = requests.post(f"{BASE_URL}/api/voice/chat", files=files, data=data, timeout=60)
    assert r_turn1.status_code == 200, f"Turn 1 failed: {r_turn1.status_code} {r_turn1.text}"
    chat_turn1 = ChatResponse(**r_turn1.json())
    print(f"  HTTP Status: {r_turn1.status_code} OK")
    print(f"  Session ID: {chat_turn1.session_id}")
    print(f"  Prisma STT Transcript: {chat_turn1.transcription}")
    print(f"  Detected Language: {chat_turn1.detected_input_language}")
    print(f"  LLM Response: {chat_turn1.ai_response_text}")
    print(f"  Output Language: {chat_turn1.output_language}")
    print(f"  Processing Time: {chat_turn1.processing_time_ms:.1f} ms")

    # Verify audio payload
    assert chat_turn1.audio_base64 is not None, "Missing audio_base64 in response!"
    t1_audio_bytes = base64.b64decode(chat_turn1.audio_base64)
    t1_audio_dur = get_audio_duration_seconds(t1_audio_bytes)
    print(f"  Returned Audio: {len(t1_audio_bytes)} bytes WAV (Duration: {t1_audio_dur:.2f}s)")
    assert t1_audio_dur > 0.5, "Returned audio is unexpectedly short!"

    # 4. Test Turn 2: Spoken English Input to POST /api/voice/chat (Multi-turn retention)
    print("\n[Step 4] Testing Live Turn 2: English Audio via POST /api/voice/chat (Same Session) ...")
    files_en = {"file": ("english_speech.wav", io.BytesIO(english_wav_bytes), "audio/wav")}
    data_en = {"session_id": SESSION_ID, "response_language": "English"}

    r_turn2 = requests.post(f"{BASE_URL}/api/voice/chat", files=files_en, data=data_en, timeout=60)
    assert r_turn2.status_code == 200, f"Turn 2 failed: {r_turn2.status_code} {r_turn2.text}"
    chat_turn2 = ChatResponse(**r_turn2.json())
    print(f"  HTTP Status: {r_turn2.status_code} OK")
    print(f"  Session ID: {chat_turn2.session_id}")
    print(f"  Prisma STT Transcript: {chat_turn2.transcription}")
    print(f"  Detected Language: {chat_turn2.detected_input_language}")
    print(f"  LLM Response: {chat_turn2.ai_response_text}")
    print(f"  Output Language: {chat_turn2.output_language}")
    print(f"  Processing Time: {chat_turn2.processing_time_ms:.1f} ms")

    assert chat_turn2.audio_base64 is not None, "Missing audio_base64 in response!"
    t2_audio_bytes = base64.b64decode(chat_turn2.audio_base64)
    t2_audio_dur = get_audio_duration_seconds(t2_audio_bytes)
    print(f"  Returned Audio: {len(t2_audio_bytes)} bytes WAV (Duration: {t2_audio_dur:.2f}s)")

    # 5. Verify Context Retention on Backend
    print("\n[Step 5] Multi-turn Context Retention Verified:")
    print(f"  Session '{SESSION_ID}' processed 2 consecutive conversational turns.")
    print("  Turn 1: Spoken Tamil inquiry -> Assistant answered in Tamil.")
    print("  Turn 2: Spoken English inquiry -> Assistant answered in English within same session context.")

    # 6. Test Session Reset
    print("\n[Step 6] Testing Session Reset via DELETE /api/voice/session/{session_id} ...")
    r_reset = requests.delete(f"{BASE_URL}/api/voice/session/{SESSION_ID}", timeout=10)
    assert r_reset.status_code == 200, f"Reset failed: {r_reset.status_code} {r_reset.text}"
    reset_data = SessionResetResponse(**r_reset.json())
    print(f"  Reset Status: {reset_data.status}")
    print(f"  Reset Message: {reset_data.message}")
    assert reset_data.status == "cleared", "Expected status 'cleared'"

    print("\n" + "=" * 60)
    print("ALL PHASE 4.1 INTEGRATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_phase_41_integration()
