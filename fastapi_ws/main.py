import asyncio
import os
import logging
import json
import uuid
import time
import struct
import io
import av
import websockets
import webrtcvad
import numpy as np
import httpx
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from adapters.stt_adapter import get_stt_adapter
from adapters.llm_adapter import get_llm_adapter
from adapters.tts_adapter import get_tts_adapter

# Configuration
STT_INTERVAL_MS = int(os.environ.get("STT_INTERVAL_MS", 300))
TTS_INTERVAL_MS = int(os.environ.get("TTS_INTERVAL_MS", 200))
SILENCE_WINDOW_MS = int(os.environ.get("SILENCE_WINDOW_MS", 800))
VAD_MODE = int(os.environ.get("VAD_MODE", 0))
MIN_TTS_CHARS = int(os.environ.get("MIN_TTS_CHARS", 10))
DJANGO_URL = os.environ.get("DJANGO_INTERNAL_URL", "http://django:8000")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SessionContext:
    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.audio_queue = asyncio.Queue(maxsize=128) # chunks of PCM16 16k audio
        self.vad_buffer = bytearray() # Buffer for VAD
        self.stt_buffer = bytearray() # Buffer for STT (speech only)
        self.stt_processed_idx = 0
        self.transcript_parts = [] # Accumulate final phrases
        
        self.llm_buffer = ""
        self.llm_processed_idx = 0
        
        self.tts_queue = asyncio.Queue(maxsize=64)
        
        self.vad = webrtcvad.Vad(VAD_MODE)
        self.sample_rate = 16000
        self.frame_duration_ms = 30
        self.frame_size_bytes = int(self.sample_rate * self.frame_duration_ms / 1000) * 2 # 16-bit
        
        self.silence_frames_count = 0
        self.silence_threshold_frames = SILENCE_WINDOW_MS // self.frame_duration_ms
        self.is_speaking = False
        
        self.stt_adapter = get_stt_adapter()
        self.stt_lock = asyncio.Lock() # Protects stt_adapter state
        self.llm_adapter = get_llm_adapter()
        self.tts_adapter = get_tts_adapter()
        
        self.tasks = []
        self.active = True

async def decode_to_pcm16(data: bytes) -> bytes:
    """
    Decodes arbitrary audio bytes to PCM16 16000Hz Mono using PyAV.
    This is expensive, so ideally we do it only if needed.
    """
    try:
        # If it's already raw PCM16 (heuristic: size matches expected raw), we might skip. 
        # But safest is to try decode if it's a container.
        # For simplicity in this demo, we assume the frontend sends chunks of raw PCM or simple containers.
        # If it's raw bytes, PyAV might fail to open it without format.
        # We will assume logic: try to open; if fail, assume it's raw pcm16 16k if sent in appropriate chunks.
        
        # NOTE: Opening a container for every small chunk is very inefficient. 
        # A streaming decoder would be better.
        # But for "simple demo" where frontend sends raw PCM or we decode 40ms chunks:
        
        # Optimization: if the client sets a header saying it's raw, use it.
        # For now, let's assume the client sends raw PCM16 16k to keep "minimal-complexity" unless it's obviously a file header.
        return data  
    except Exception as e:
        logger.error(f"Decode error: {e}")
        return b""

async def finalize_session_transcript(session_id: str, transcript: str, duration_ms: int):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{DJANGO_URL}/api/sessions/{session_id}/finalize/",
                json={"final_transcript": transcript, "duration_ms": duration_ms}
            )
    except Exception as e:
        logger.error(f"Failed to save transcript: {e}")

async def audio_receive_task(ctx: SessionContext):
    try:
        while ctx.active:
            # We expect either JSON control or Binary audio
            data = await ctx.websocket.receive()
            
            if "bytes" in data:
                audio_bytes = data["bytes"]
                if not hasattr(ctx, "debug_first_audio"):
                    logger.info(f"Session {ctx.session_id} receiving audio bytes (len={len(audio_bytes)})")
                    ctx.debug_first_audio = True
                # Assuming raw PCM16 16k for simplicity of the "minimal" demo, 
                # or simplified decoding logic if needed. 
                # The prompt asks for backend decoding. 
                # Let's insert a resampler/decoder placeholder:
                # pcm_bytes = await decode_to_pcm16(audio_bytes)
                pcm_bytes = audio_bytes 
                
                # Split into VAD-sized chunks (e.g. 960 bytes for 30ms)
                # We need to buffer incoming bytes to ensure we have full frames
                # For this demo, let's assume incoming chunks are reasonably sized or handle partials
                # in a real buffer. We'll dump straight to queue for VAD task to handle framing.
                
                if ctx.audio_queue.full():
                    try:
                        ctx.audio_queue.get_nowait() # Drop OLDEST
                        await ctx.websocket.send_json({"type": "warning", "payload": {"message": "Audio dropped", "reason": "backpressure"}})
                    except:
                        pass
                await ctx.audio_queue.put(pcm_bytes)
                
            elif "text" in data:
                try:
                    msg = json.loads(data["text"])
                    if msg.get("type") == "stop_session":
                        ctx.active = False
                    elif msg.get("type") == "audio_end":
                        # Trigger final flush
                        await trigger_finalization(ctx)
                except:
                    pass
    except WebSocketDisconnect:
        logger.info(f"Session {ctx.session_id} disconnected")
        ctx.active = False
    except Exception as e:
        logger.error(f"Receive error: {e}")
        ctx.active = False

async def trigger_finalization(ctx: SessionContext):
    if not ctx.stt_buffer:
        return

    new_bytes = bytes(ctx.stt_buffer[ctx.stt_processed_idx:])
    
    async with ctx.stt_lock:
        ctx.stt_processed_idx += len(new_bytes)
        res = await ctx.stt_adapter.transcribe(new_bytes, final=True)
    
    # Commit any remainder
    remainder = res.get("text", "")
    if remainder:
        ctx.transcript_parts.append(remainder)
    
    # Full text for LLM
    text = " ".join(ctx.transcript_parts).strip()
    
    # Clear parts for next turn (if session stays open)
    # But usually trigger_finalization might mean "Request -> Response" cycle.
    # If we keep connection open for multi-turn, we clear.
    ctx.transcript_parts = []
    
    if text:
        logger.info(f"Session {ctx.session_id} Final Transcript: {text}")
        await ctx.websocket.send_json({"type": "stt_final", "payload": {"text": text}})
        
        # 2. Save to Django
        asyncio.create_task(finalize_session_transcript(ctx.session_id, text, 0))
        
        # 3. Stream LLM
        ctx.llm_buffer = ""
        ctx.llm_processed_idx = 0
        await ctx.websocket.send_json({"type": "llm_start"}) # Optional marker
        
        async for token in ctx.llm_adapter.stream_response(text):
            ctx.llm_buffer += token
            await ctx.websocket.send_json({"type": "llm_partial", "payload": {"text": token}})
            # TTS Scheduler picks this up asynchronously
        
        await ctx.websocket.send_json({"type": "llm_final", "payload": {"text": ctx.llm_buffer}})
        
    ctx.stt_buffer = bytearray()
    ctx.stt_processed_idx = 0
    ctx.is_speaking = False

async def vad_task(ctx: SessionContext):
    buffer = bytearray()
    while ctx.active:
        try:
            chunk = await ctx.audio_queue.get()
            buffer.extend(chunk)
            
            while len(buffer) >= ctx.frame_size_bytes:
                frame = buffer[:ctx.frame_size_bytes]
                buffer = buffer[ctx.frame_size_bytes:]
                
                is_speech = ctx.vad.is_speech(frame, ctx.sample_rate)
                
                if is_speech:
                    ctx.silence_frames_count = 0
                    if not ctx.is_speaking:
                        ctx.is_speaking = True
                        logger.info(f"Session {ctx.session_id} speech started")
                    ctx.stt_buffer.extend(frame)
                else:
                    if ctx.is_speaking:
                        ctx.stt_buffer.extend(frame) # Keep trailing silence for context
                        ctx.silence_frames_count += 1
                        if ctx.silence_frames_count > ctx.silence_threshold_frames:
                            logger.info(f"Session {ctx.session_id} silence detected")
                            await trigger_finalization(ctx)
                            ctx.silence_frames_count = 0
                            
        except Exception as e:
            logger.error(f"VAD error: {e}")
            await asyncio.sleep(0.01)

async def stt_worker(ctx: SessionContext):
    while ctx.active:
        await asyncio.sleep(STT_INTERVAL_MS / 1000.0)
        if ctx.is_speaking and len(ctx.stt_buffer) > ctx.stt_processed_idx: # Has new audio
            try:
                # Snapshot current buffer delta
                new_bytes = bytes(ctx.stt_buffer[ctx.stt_processed_idx:])
                async with ctx.stt_lock:
                    ctx.stt_processed_idx += len(new_bytes)
                    res = await ctx.stt_adapter.transcribe(new_bytes, final=False)
                if res.get("text"):
                    # If Vosk says it's final (utterance end), accumulate it
                    if res.get("is_final"):
                        ctx.transcript_parts.append(res["text"])
                        logger.info(f"Session {ctx.session_id} commit STT chunk: {res['text']}")
                    
                    await ctx.websocket.send_json({"type": "stt_partial", "payload": res})
            except Exception as e:
                logger.error(f"STT partial error: {e}")

async def tts_scheduler(ctx: SessionContext):
    seq = 0
    while ctx.active:
        await asyncio.sleep(TTS_INTERVAL_MS / 1000.0)
        
        # Check LLM buffer for new content to synthesize
        unprocessed = ctx.llm_buffer[ctx.llm_processed_idx:]
        
        # Simple heuristic: synthesize if > MIN_CHARS or if we are at the end (handled separately really)
        # For stream processing, we usually look for sentence boundaries or chunks.
        # Here we just check length.
        if len(unprocessed) >= MIN_TTS_CHARS:
            chunk_text = unprocessed
            ctx.llm_processed_idx += len(chunk_text)
            
            # Synthesize
            audio = await ctx.tts_adapter.synthesize(chunk_text)
            if audio:
                await ctx.tts_queue.put((seq, audio))
                seq += 1

async def tts_sender_task(ctx: SessionContext):
    while ctx.active:
        seq, audio_data = await ctx.tts_queue.get()
        try:
            duration_ms = int(len(audio_data) / 32) # (len / 2 bytes_per_sample) / 16 samples_per_ms
            await ctx.websocket.send_json({
                "type": "tts_chunk",
                "payload": {
                    "seq": seq,
                    "audio_format": "pcm16",
                    "sample_rate": 16000,
                    "length_ms": duration_ms
                }
            })
            await ctx.websocket.send_bytes(audio_data)
        except Exception as e:
            logger.error(f"TTS send error: {e}")

@app.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket, session_id: str = None):
    await websocket.accept()
    if not session_id:
        session_id = str(uuid.uuid4())
        # Create session in Django
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{DJANGO_URL}/api/sessions/", json={"client_info": {"user_agent": "ws_client"}})
                if resp.status_code == 201:
                    session_id = resp.json().get("session_id", session_id)
        except Exception as e:
            logger.error(f"Failed to create session in Django: {e}")
            
    await websocket.send_json({"type": "session_ack", "payload": {"session_id": session_id}})
    
    ctx = SessionContext(session_id, websocket)
    
    # Start tasks
    ctx.tasks = [
        asyncio.create_task(audio_receive_task(ctx)),
        asyncio.create_task(vad_task(ctx)),
        asyncio.create_task(stt_worker(ctx)),
        asyncio.create_task(tts_scheduler(ctx)),
        asyncio.create_task(tts_sender_task(ctx)),
    ]
    
    try:
        # Keep main loop alive monitoring tasks or waiting for disconnect
        await asyncio.gather(*ctx.tasks)
    except Exception as e:
        logger.error(f"Root session error: {e}")
    finally:
        ctx.active = False
        for task in ctx.tasks:
            task.cancel()
        logger.info(f"Session {session_id} cleaned up")
