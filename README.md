# Audio-Based Conversational Chatbot

A real-time audio chat system featuring:
- **Frontend**: React SPA (single page) for audio capture and playback.
- **Backend**: FastAPI WebSocket service for VAD, STT, LLM streaming, and TTS.
- **Persistence**: Django DRF service for session management and transcripts.
- **AI**: Gemini (LLM), Whisper (STT), Coqui (TTS) [Swappable adapters].

## Architecture

1. **Frontend** streams audio (blob/chunks) to **FastAPI**.
2. **FastAPI** decodes to PCM16, runs VAD (Voice Activity Detection).
3. On speech: **STT** (Whisper) transcribes partially.
4. On silence: **STT** finalizes, sends to **Django** for storage.
5. **FastAPI** drives **LLM** (Gemini) with the transcript.
6. **LLM** tokens are buffered and sent to **TTS** (Coqui/Dummy).
7. **TTS** audio chunks are streamed back to **Frontend** for playback.

## Prerequisites

- Docker & Docker Compose
- Google Gemini API Key (provided in `.env.example`)

## Setup & Run

1. **Clone & Config**:
   ```bash
   cp .env.example .env
   # Edit .env if needed (GEMINI_API_KEY is pre-filled for this demo)
   ```

2. **Run Services**:
   ```bash
   docker-compose up --build
   ```

3. **Access**:
   - **Frontend**: (Requires running locally for now, see below)
   - **Django Admin**: [http://localhost:8000/admin](http://localhost:8000/admin)
   - **FastAPI**: [http://localhost:8001/docs](http://localhost:8001/docs)

## Running Frontend

(Instructions to be added after Frontend scaffolding)

## Testing

### Integration Test
1. Ensure services are running.
2. Run pytest:
   ```bash
   pytest tests/
   ```

### Manual Play Test
Use the helper script to simulate a client:
```bash
python tests/play_test_audio.py --file tests/sample_16k_mono.wav
```
