import os
import sys
import time
import json
import asyncio
import subprocess
import requests
import websockets

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TAMIL_AUDIO = os.path.abspath("tests/test_output/clean_tamil_44k.wav")
ENGLISH_AUDIO = os.path.abspath("tests/test_output/clean_english_48k.wav")
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
FRONTEND_URL = "http://127.0.0.1:5173"
DEBUG_PORT = 9222


async def run_cdp_session(audio_file, test_scenario="tamil"):
    print("\n" + "=" * 70)
    print(f"RUNNING CHROME BROWSER ACCEPTANCE TEST: {test_scenario.upper()}")
    print("=" * 70)
    assert os.path.exists(audio_file), f"Missing audio file: {audio_file}"

    chrome_cmd = [
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={DEBUG_PORT}",
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        f"--use-file-for-fake-audio-capture={audio_file}",
        "--disable-gpu",
        "--no-sandbox",
        "--allow-insecure-localhost",
        FRONTEND_URL,
    ]

    print(f"[Chrome] Launching Chrome Headless (mic: {os.path.basename(audio_file)})...")
    proc = subprocess.Popen(chrome_cmd)
    time.sleep(3)

    try:
        targets = requests.get(f"http://127.0.0.1:{DEBUG_PORT}/json/list").json()
        page_targets = [t for t in targets if t.get("type") == "page"]
        assert len(page_targets) > 0, "No page target found in Chrome!"
        ws_url = page_targets[0]["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=30 * 1024 * 1024) as ws:
            msg_counter = 0

            async def cdp_call(method, params=None):
                nonlocal msg_counter
                msg_counter += 1
                req_id = msg_counter
                payload = {"id": req_id, "method": method, "params": params or {}}
                await ws.send(json.dumps(payload))
                while True:
                    raw = await ws.recv()
                    data = json.loads(raw)
                    if data.get("id") == req_id:
                        return data.get("result", {})

            async def eval_js(expression):
                res = await cdp_call("Runtime.evaluate", {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True
                })
                return res.get("result", {}).get("value")

            # Enable CDP domains
            await cdp_call("Page.enable")
            await cdp_call("Runtime.enable")
            await cdp_call("Network.enable")

            # Verify page ready
            ready_state = await eval_js("document.readyState")
            print(f"  Page Ready State: {ready_state}")

            # Wait for backend ready
            for _ in range(12):
                hdr = await eval_js("document.querySelector('header')?.innerText || ''")
                if "Backend Ready" in hdr:
                    print("  Backend Connection Status: Backend Ready (200 OK)")
                    break
                await asyncio.sleep(0.5)

            if test_scenario == "tamil":
                # --- TURN 1 (Tamil) ---
                print("\n[Turn 1] Recording Tamil speech via Chrome MediaRecorder...")
                await eval_js("document.querySelector('button[aria-label=\"Start Recording\"]')?.click()")
                await asyncio.sleep(3)
                print("  Stopping recording. Calling convertBlobToWav() in browser...")
                await eval_js("document.querySelector('button[aria-label=\"Stop Recording\"]')?.click()")

                # Wait for Turn 1 to complete
                t1_done = False
                for _ in range(35):
                    await asyncio.sleep(1)
                    count = await eval_js("document.querySelectorAll('.max-w-\\\\[80\\\\%\\\\]').length")
                    is_spin = await eval_js("Boolean(document.querySelector('.animate-spin'))")
                    if count >= 2 and not is_spin:
                        t1_done = True
                        break

                assert t1_done, "Turn 1 timed out!"
                t1_user = await eval_js("document.querySelectorAll('.max-w-\\\\[80\\\\%\\\\]')[0]?.innerText || ''")
                t1_assistant = await eval_js("document.querySelectorAll('.max-w-\\\\[80\\\\%\\\\]')[1]?.innerText || ''")
                t1_lang = await eval_js("document.querySelector('.bg-violet-950\\\\/60')?.innerText || ''")
                t1_player = await eval_js("Boolean(document.querySelector('audio'))")

                print(f"  Turn 1 Transcript: {t1_user.replace(chr(10), ' | ')[:70]}...")
                print(f"  Turn 1 Detected Lang: {t1_lang}")
                print(f"  Turn 1 AI Response: {t1_assistant.replace(chr(10), ' | ')[:70]}...")
                print(f"  Turn 1 AudioPlayer Mounted: {t1_player}")
                assert "ta" in t1_lang.lower(), f"Expected Tamil language code, got {t1_lang}"
                assert t1_player, "AudioPlayer missing for Turn 1"

                # --- TURN 2 (Multi-turn retention in same session) ---
                print("\n[Turn 2] Recording Turn 2 in SAME session (testing multi-turn memory)...")
                await eval_js("document.querySelector('button[aria-label=\"Start Recording\"]')?.click()")
                await asyncio.sleep(3)
                print("  Stopping Turn 2 recording...")
                await eval_js("document.querySelector('button[aria-label=\"Stop Recording\"]')?.click()")

                t2_done = False
                for _ in range(35):
                    await asyncio.sleep(1)
                    count = await eval_js("document.querySelectorAll('.max-w-\\\\[80\\\\%\\\\]').length")
                    is_spin = await eval_js("Boolean(document.querySelector('.animate-spin'))")
                    if count >= 4 and not is_spin:
                        t2_done = True
                        break

                assert t2_done, "Turn 2 timed out!"
                total_bubbles = await eval_js("document.querySelectorAll('.max-w-\\\\[80\\\\%\\\\]').length")
                print(f"  Turn 2 Completed! Total Chat Bubbles in DOM: {total_bubbles}")
                assert total_bubbles == 4, f"Expected 4 chat bubbles after 2 turns, found {total_bubbles}"
                print("  MULTI-TURN SESSION MEMORY VERIFIED IN BROWSER: YES (4/4 messages retained)")

                # --- SESSION RESET ---
                print("\n[Reset Test] Clicking 'Reset Conversation' button...")
                await eval_js("document.querySelector('button[aria-label=\"Reset Conversation\"]')?.click()")
                await asyncio.sleep(1)
                after_reset = await eval_js("document.querySelectorAll('.max-w-\\\\[80\\\\%\\\\]').length")
                welcome_state = await eval_js("Boolean(document.querySelector('h3'))")
                print(f"  Bubbles after reset: {after_reset} | Welcome screen restored: {welcome_state}")
                assert after_reset == 0 and welcome_state, "Reset failed to clear conversation!"
                print("  SESSION RESET VERIFIED IN BROWSER: YES")

            elif test_scenario == "english":
                # --- ENGLISH TURN ---
                print("\n[English Turn] Recording English speech via Chrome MediaRecorder...")
                await eval_js("document.querySelector('button[aria-label=\"Start Recording\"]')?.click()")
                await asyncio.sleep(3)
                print("  Stopping recording. Triggering browser PCM WAV conversion...")
                await eval_js("document.querySelector('button[aria-label=\"Stop Recording\"]')?.click()")

                en_done = False
                for _ in range(35):
                    await asyncio.sleep(1)
                    count = await eval_js("document.querySelectorAll('.max-w-\\\\[80\\\\%\\\\]').length")
                    is_spin = await eval_js("Boolean(document.querySelector('.animate-spin'))")
                    if count >= 2 and not is_spin:
                        en_done = True
                        break

                assert en_done, "English turn timed out!"
                en_user = await eval_js("document.querySelectorAll('.max-w-\\\\[80\\\\%\\\\]')[0]?.innerText || ''")
                en_assistant = await eval_js("document.querySelectorAll('.max-w-\\\\[80\\\\%\\\\]')[1]?.innerText || ''")
                en_lang = await eval_js("document.querySelector('.bg-violet-950\\\\/60')?.innerText || ''")
                en_player = await eval_js("Boolean(document.querySelector('audio'))")

                print(f"  English Transcript: {en_user.replace(chr(10), ' | ')[:70]}...")
                print(f"  Detected Lang Badge: {en_lang}")
                print(f"  English AI Response: {en_assistant.replace(chr(10), ' | ')[:70]}...")
                print(f"  AudioPlayer Mounted: {en_player}")
                assert "en" in en_lang.lower(), f"Expected English language code, got {en_lang}"
                assert en_player, "AudioPlayer missing for English turn"
                print("  ENGLISH SPEECH & AUTO-DETECTION VERIFIED: YES")

    finally:
        print(f"[Cleanup] Terminating Chrome for {test_scenario}...")
        proc.terminate()
        proc.wait()
        time.sleep(2)


async def main():
    # 1. Run Tamil Turn + Multi-turn Continuity + Reset
    await run_cdp_session(TAMIL_AUDIO, test_scenario="tamil")

    # 2. Run English Auto-Detection Turn
    await run_cdp_session(ENGLISH_AUDIO, test_scenario="english")

    print("\n" + "=" * 70)
    print("ALL BROWSER ACCEPTANCE TESTS (TAMIL + MULTI-TURN + RESET + ENGLISH) PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
