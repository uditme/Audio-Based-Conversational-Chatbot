import os
import asyncio
import logging
import json
import vosk

# Fallback/Dummy implementation
class STTAdapter:
    async def transcribe(self, pcm16_bytes: bytes, final: bool=False) -> dict:
        """
        Returns {"text": str, "confidence": float, "is_final": bool}
        """
        raise NotImplementedError

class DummySTTAdapter(STTAdapter):
    def __init__(self):
        self.counter = 0

    async def transcribe(self, pcm16_bytes: bytes, final: bool=False) -> dict:
        # Simulate processing time
        await asyncio.sleep(0.05)
        self.counter += 1
        return {
            "text": f"This is a dummy transcription {self.counter}",
            "confidence": 0.95,
            "is_final": final
        }

class VoskSTTAdapter(STTAdapter):
    def __init__(self):
        model_path = "/opt/vosk-model/model"
        if not os.path.exists(model_path):
             # Fallback for local testing outside docker if needed, or error
             logging.error(f"Vosk model not found at {model_path}")
             raise FileNotFoundError("Vosk model not found")
        
        logging.info(f"Loading Vosk model from {model_path}...")
        self.model = vosk.Model(model_path)
        # We need a recognizer per session ideally, or one global? 
        # Vosk KaldiRecognizer has state. STTAdapter logic usually implies stateless "transcribe this chunk" 
        # BUT for streaming STT, we need context.
        # However, our interface `transcribe(bytes, final)` suggests stateless or managed state.
        # The main.py creates a new Adapter via `get_stt_adapter`? No, it calls it once?
        # Let's check main.py usage. 
        # main.py: `self.stt_adapter = get_stt_adapter()` in SessionContext.
        # So one adapter instance per session. Perfect.
        
        self.rec = vosk.KaldiRecognizer(self.model, 16000)
    
    async def transcribe(self, pcm16_bytes: bytes, final: bool=False) -> dict:
        # Vosk expects small chunks.
        # rec.AcceptWaveform returns True if silence reached (end of utterance)
        
        loop = asyncio.get_running_loop()
        
        # AcceptWaveform runs in C++, blocking. Run in executor.
        def process():
            if len(pcm16_bytes) > 0:
                if self.rec.AcceptWaveform(pcm16_bytes):
                    res = json.loads(self.rec.Result())
                    return res.get("text", ""), True
                else:
                    res = json.loads(self.rec.PartialResult())
                    return res.get("partial", ""), False
            return "", False 

        text, is_utterance_end = await loop.run_in_executor(None, process)
        
        # If 'final' flag from caller is True, we might want to force final result?
        # But caller 'final' usually means "silence detected by VAD".
        # Vosk has its own VAD/end-of-speech logic implicitly in AcceptWaveform.
        # If VAD says "Final", we should get the Result().
        
        if final:
            # Force final result
            # Force final result
            def get_final():
                final_json = self.rec.FinalResult()
                return json.loads(final_json)

            final_res = await loop.run_in_executor(None, get_final)
            final_text = final_res.get("text", "")
            
            # If we already got text from AcceptWaveform, usually it's the same or accumulated.
            # Reset recognizer for next turn? KaldiRecognizer resets after FinalResult? Yes.
            # Re-create recognizer for next turn is safer or stream continues?
            # Usually creates a new one or AcceptWaveform resets.
            # We'll return the final text.
            return {
                "text": final_text,
                "confidence": 1.0, 
                "is_final": True
            }
        
        return {
            "text": text,
            "confidence": 0.8,
            "is_final": is_utterance_end
        }

# Factory
def get_stt_adapter():
    try:
        return VoskSTTAdapter()
    except Exception as e:
        logging.error(f"Failed to load Vosk: {e}. Falling back to Dummy.")
        return DummySTTAdapter()
