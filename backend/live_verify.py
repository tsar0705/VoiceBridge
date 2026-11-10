import os
import sys
import wave
import json
from pathlib import Path
from dotenv import load_dotenv
import httpx

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Configure UTF-8 encoding for Windows console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Load .env
env_path = backend_dir / ".env"
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv("GNANI_API_KEY", "").strip()
PRISMA_ENDPOINT = os.getenv("GNANI_PRISMA_ENDPOINT", "https://api.vachana.ai/stt/v3").strip()
PRISMA_MODEL = os.getenv("GNANI_PRISMA_MODEL", "prisma-v3.0").strip()
TIMBRE_ENDPOINT = os.getenv("GNANI_TIMBRE_ENDPOINT", "https://api.vachana.ai/api/v1/tts/inference").strip()
TIMBRE_MODEL = os.getenv("GNANI_TIMBRE_MODEL", "timbre-v2.5").strip()
TIMBRE_VOICE = os.getenv("GNANI_DEFAULT_VOICE", "Nalini").strip()

output_dir = backend_dir / "tests" / "test_output"
output_dir.mkdir(parents=True, exist_ok=True)
audio_output_path = output_dir / "live_timbre_tamil.wav"


def check_configuration():
    print("=" * 60)
    print("STEP 1: Checking Gnani AI Configuration")
    print("=" * 60)
    if not API_KEY or API_KEY == "your_gnani_api_key_here":
        print("ERROR: GNANI_API_KEY is missing or contains placeholder.")
        sys.exit(1)
    
    print(f"API Key configured: True (Length: {len(API_KEY)} chars, masked)")
    print(f"Prisma STT Endpoint: {PRISMA_ENDPOINT}")
    print(f"Prisma STT Model: {PRISMA_MODEL}")
    print(f"Timbre TTS Endpoint: {TIMBRE_ENDPOINT}")
    print(f"Timbre TTS Model: {TIMBRE_MODEL}")
    print(f"Timbre TTS Default Voice: {TIMBRE_VOICE}")
    print("Configuration check PASSED.\n")


def test_live_timbre_synthesis():
    print("=" * 60)
    print("STEP 2: Executing Live Timbre TTS Synthesis Request")
    print("=" * 60)
    
    tamil_prompt = "வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்?"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key-ID": API_KEY,
    }
    payload = {
        "text": tamil_prompt,
        "voice": TIMBRE_VOICE,
        "model": TIMBRE_MODEL,
        "language": "ta-IN",
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 48000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }
    
    print(f"Sending POST to {TIMBRE_ENDPOINT}...")
    print(f"Input Text: '{tamil_prompt}'")
    print(f"Requested Language: ta-IN | Voice: {TIMBRE_VOICE} | Model: {TIMBRE_MODEL}")
    
    timeout = httpx.Timeout(connect=15.0, read=45.0, write=15.0, pool=10.0)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(TIMBRE_ENDPOINT, headers=headers, json=payload)
    
    print(f"Response HTTP Status: {response.status_code}")
    print(f"Response Headers Content-Type: {response.headers.get('content-type')}")
    
    if response.status_code != 200:
        print(f"TTS Failed with status {response.status_code}: {response.text}")
        sys.exit(1)
    
    audio_bytes = response.content
    print(f"Received raw binary audio: {len(audio_bytes)} bytes")
    
    # Save to disk
    with open(audio_output_path, "wb") as f:
        f.write(audio_bytes)
    print(f"Saved audio file to: {audio_output_path}")
    
    # Inspect WAV header
    try:
        with wave.open(str(audio_output_path), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            duration = n_frames / float(framerate)
            print("\n--- Audio File Header Verification ---")
            print(f"Container: Valid RIFF WAVE")
            print(f"Channels: {channels} (Mono)" if channels == 1 else f"Channels: {channels}")
            print(f"Sample Rate: {framerate} Hz")
            print(f"Sample Width: {sample_width * 8} bits")
            print(f"Total Frames: {n_frames}")
            print(f"Calculated Duration: {duration:.2f} seconds")
            print("File Validity: PLAYABLE WAV (Verified)")
    except Exception as e:
        print(f"Warning: Failed to parse WAV header: {e}")
        sys.exit(1)

    print("Timbre TTS Live Synthesis PASSED.\n")
    return audio_bytes


def test_live_prisma_transcription(audio_bytes: bytes):
    print("=" * 60)
    print("STEP 3: Executing Live Prisma STT Transcription Request")
    print("=" * 60)
    
    headers = {
        "X-API-Key-ID": API_KEY,
    }
    data = {
        "model": PRISMA_MODEL,
        "language_code": "indic-auto",
        "format": "codemix",
    }
    files = {
        "audio_file": ("live_timbre_tamil.wav", audio_bytes, "audio/wav")
    }
    
    print(f"Sending POST to {PRISMA_ENDPOINT}...")
    print(f"Form parameters: model={PRISMA_MODEL}, language_code=indic-auto, format=codemix")
    print(f"Audio payload size: {len(audio_bytes)} bytes")
    
    timeout = httpx.Timeout(connect=15.0, read=45.0, write=15.0, pool=10.0)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(PRISMA_ENDPOINT, headers=headers, data=data, files=files)
    
    print(f"Response HTTP Status: {response.status_code}")
    print(f"Response Headers Content-Type: {response.headers.get('content-type')}")
    
    if response.status_code != 200:
        print(f"STT Failed with status {response.status_code}: {response.text}")
        sys.exit(1)
        
    try:
        res_json = response.json()
        print("\n--- Prisma STT Live Response Structure ---")
        print(json.dumps(res_json, indent=2, ensure_ascii=False))
        
        transcript = res_json.get("transcript") or res_json.get("transcription") or res_json.get("text")
        detected_lang = res_json.get("detected_language_code") or res_json.get("language_code") or res_json.get("language")
        conf = res_json.get("confidence")
        
        print("\n--- Extracted & Normalized Fields ---")
        print(f"Transcription: '{transcript}'")
        print(f"Detected Language: '{detected_lang}'")
        print(f"Confidence: {conf}")
    except Exception as e:
        print(f"Failed to parse JSON response: {e}, text: {response.text}")
        sys.exit(1)

    print("Prisma STT Live Transcription PASSED.\n")


def main():
    check_configuration()
    audio_bytes = test_live_timbre_synthesis()
    test_live_prisma_transcription(audio_bytes)
    print("=" * 60)
    print("ALL LIVE GNANI AI API INTEGRATION VERIFICATIONS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
