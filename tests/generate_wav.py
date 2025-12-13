import wave
import struct
import math

def generate_sine_wave(filename, duration=3.0, sample_rate=16000, frequency=440.0):
    num_samples = int(duration * sample_rate)
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        data = bytearray()
        for i in range(num_samples):
            # Generate speech-like bursts? No, just a tone is fine for signal
            value = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
            data.extend(struct.pack('<h', value))
            
        wav_file.writeframes(data)
    print(f"Generated {filename}")

if __name__ == "__main__":
    generate_sine_wave("tests/sample_16k_mono.wav")
