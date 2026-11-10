import subprocess
import time
import requests
import asyncio
import websockets
import json

cmd = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    '--headless=new',
    '--remote-debugging-port=9222',
    '--disable-gpu',
    'http://127.0.0.1:5173'
]
proc = subprocess.Popen(cmd)
time.sleep(2)

async def test():
    try:
        targets = requests.get('http://127.0.0.1:9222/json/list').json()
        page = [t for t in targets if t.get('type') == 'page'][0]
        async with websockets.connect(page['webSocketDebuggerUrl']) as ws:
            # Check console logs
            await ws.send(json.dumps({'id': 1, 'method': 'Console.enable'}))
            await ws.send(json.dumps({
                'id': 2,
                'method': 'Runtime.evaluate',
                'params': {
                    'expression': 'fetch("http://127.0.0.1:8000/api/health").then(r => r.json()).then(d => JSON.stringify(d)).catch(e => "FETCH_ERR: " + e)',
                    'awaitPromise': True,
                    'returnByValue': True
                }
            }))
            while True:
                raw = await ws.recv()
                data = json.loads(raw)
                if data.get('id') == 2:
                    print('DIRECT FETCH IN CHROME:', data.get('result', {}).get('result', {}).get('value'))
                    break
    finally:
        proc.terminate()

asyncio.run(test())
