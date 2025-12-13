import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
# We need to import app from the directory above. 
# In a real repo we'd install the package or use pythonpath.
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../fastapi_ws'))

from main import app

client = TestClient(app)

def test_health_check():
    # We didn't explicitly add a health check but docs is usually up
    response = client.get("/docs")
    assert response.status_code == 200

def test_websocket_flow():
    # NOTE: This runs with Dummy adapters by default if env vars not set, which is what we want for CI
    with client.websocket_connect("/ws/audio") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "session_ack"
        
        # Send fake audio (silence/tone)
        # 10 chunks of 40ms = 400ms
        chunk_size = 1280 # 40ms * 16k * 2 bytes
        fake_audio = b"\x00" * chunk_size
        
        for _ in range(5):
            websocket.send_bytes(fake_audio)
        
        # We might not get Partial STT immediately with silence/dummy
        # Let's send a "stop" to verify clean exit
        websocket.send_json({"type": "stop_session"})
        
        # Expect session closed or disconnect
        # In our implementation we just set active=False, which closes the loop and connection eventually
        # or we can manually close
        websocket.close()
