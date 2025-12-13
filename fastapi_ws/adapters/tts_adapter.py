import asyncio
import logging
import io
import av
from gtts import gTTS

class TTSAdapter:
    async def synthesize(self, text: str) -> bytes:
        """
        Returns PCM16 16k mono bytes
        """
        raise NotImplementedError

class DummyTTSAdapter(TTSAdapter):
    async def synthesize(self, text: str) -> bytes:
        # Generate silence or simple tone? 
        # For dummy, we just return empty or 1 sec of silence to not crash
        # or maybe a sine wave if numpy is available
        import numpy as np
        sample_rate = 16000
        duration = 1.0 # 1 sec per chunk
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Generate a 440 Hz sine wave
        audio = (np.sin(t * 2 * np.pi * 440) * 32767).astype(np.int16)
        return audio.tobytes()

class GoogleTTSAdapter(TTSAdapter):
    def __init__(self):
        logging.info("Initialized GoogleTTSAdapter (gTTS)")

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""
            
        loop = asyncio.get_running_loop()
        
        def _generate():
            try:
                # 1. Generate MP3 with gTTS
                mp3_fp = io.BytesIO()
                tts = gTTS(text=text, lang='en')
                tts.write_to_fp(mp3_fp)
                mp3_fp.seek(0)
                
                # 2. Convert MP3 -> PCM16 16000Hz Mono using PyAV
                input_container = av.open(mp3_fp)
                input_stream = input_container.streams.audio[0]
                
                resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
                
                pcm_data = bytearray()
                for frame in input_container.decode(input_stream):
                    for packet in resampler.resample(frame):
                        pcm_data.extend(packet.to_ndarray().tobytes())
                        
                return bytes(pcm_data)
            except Exception as e:
                logging.error(f"TTS Error: {e}")
                return b""

        return await loop.run_in_executor(None, _generate)

def get_tts_adapter():
    try:
        return GoogleTTSAdapter()
    except:
        return DummyTTSAdapter()
