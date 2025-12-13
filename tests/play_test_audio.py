import asyncio
import websockets
import json
import wave
import sys
import time

async def run_test(uri, filename):
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {uri}")
        
        # Wait for Ack
        ack = await websocket.recv()
        print(f"Received: {ack}")
        
        # Stream audio
        with wave.open(filename, 'rb') as wf:
            chunk_ms = 40
            sample_rate = 16000
            chunk_size = int(sample_rate * chunk_ms / 1000) * 2 # 1280 bytes
            
            data = wf.readframes(chunk_size // 2)
            while len(data) > 0:
                await websocket.send(data)
                # print(".", end="", flush=True)
                await asyncio.sleep(chunk_ms / 1000.0) # Real-time simulation
                data = wf.readframes(chunk_size // 2)
                
                # Check for incoming messages
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=0.001)
                    print(f"\nReceived during stream: {msg[:100]}...")
                except (asyncio.TimeoutError):
                    pass
        
        print("\nAudio finished. Sending end signal.")
        await websocket.send(json.dumps({"type": "audio_end"}))
        
        # Listen for results until closed
        while True:
            try:
                msg = await websocket.recv()
                if isinstance(msg, str):
                    print(f"Server: {msg}")
                    j = json.loads(msg)
                    if j['type'] == 'tts_chunk':
                        # Expect binary next
                        audio = await websocket.recv()
                        print(f"Received audio bytes: {len(audio)}")
                else:
                    print(f"Received unexpected binary: {len(msg)}")
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break

if __name__ == "__main__":
    uri = "ws://localhost:8001/ws/audio"
    file = "tests/sample_16k_mono.wav"
    if len(sys.argv) > 1:
        file = sys.argv[1]
    
    # Generate file if not exists
    import os
    if not os.path.exists(file):
        print(f"Generatign {file}...")
        # Dirty import from sibling for convenience in one script if needed, 
        # but we'll assume the user ran generate_wav.py or we use dummy data
        pass

    try:
        asyncio.run(run_test(uri, file))
    except KeyboardInterrupt:
        pass
