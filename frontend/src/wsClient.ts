
export interface TranscriptItem {
    id: string;
    text: string;
    isFinal: boolean;
    isUser: boolean; // true for STT, false for LLM
}

export type LogMessage = {
    timestamp: string;
    type: string;
    payload: any;
};

// PCM16 -> Float32 converter
const convertPCM16ToFloat32 = (buffer: ArrayBuffer): Float32Array => {
    const int16 = new Int16Array(buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768.0;
    }
    return float32;
};

export class WSClient {
    private ws: WebSocket | null = null;
    private audioContext: AudioContext | null = null;
    private nextStartTime: number = 0;
    private mediaRecorder: MediaRecorder | null = null;

    // Callbacks
    onLog: (msg: LogMessage) => void = () => { };
    onSttPartial: (text: string) => void = () => { };
    onSttFinal: (text: string) => void = () => { };
    onLlmPartial: (text: string) => void = () => { };
    onLlmFinal: (text: string) => void = () => { };

    // TTS State
    private ttsHeader: any = null; // Wait for binary after header

    constructor() { }

    connect(url: string) {
        this.log('system', `Connecting to ${url}...`);
        this.ws = new WebSocket(url);
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = () => {
            this.log('system', 'Connected');
            this.initAudioContext();
        };

        this.ws.onclose = () => {
            this.log('system', 'Disconnected');
            this.ws = null;
        };

        this.ws.onerror = (e) => {
            this.log('error', 'WebSocket error');
        };

        this.ws.onmessage = async (event) => {
            if (typeof event.data === 'string') {
                // Control message
                try {
                    const msg = JSON.parse(event.data);
                    this.handleJsonMessage(msg);
                } catch (e) {
                    this.log('error', `Parse error: ${event.data}`);
                }
            } else if (event.data instanceof ArrayBuffer) {
                // Binary audio
                this.handleBinaryMessage(event.data);
            }
        };
    }

    handleJsonMessage(msg: any) {
        if (msg.type !== 'tts_chunk') {
            this.log('server', msg); // Don't log spammy tts headers if you want cleaner logs, but for demo we log all
        }

        switch (msg.type) {
            case 'session_ack':
                this.log('info', `Session ID: ${msg.payload.session_id}`);
                break;
            case 'stt_partial':
                this.onSttPartial(msg.payload.text);
                break;
            case 'stt_final':
                this.onSttFinal(msg.payload.text);
                break;
            case 'llm_partial':
                this.onLlmPartial(msg.payload.text);
                break;
            case 'llm_final':
                this.onLlmFinal(msg.payload.text);
                break;
            case 'tts_chunk':
                this.ttsHeader = msg.payload;
                break;
            case 'error':
            case 'warning':
                this.log(msg.type, JSON.stringify(msg.payload));
                break;
        }
    }

    handleBinaryMessage(buffer: ArrayBuffer) {
        if (this.ttsHeader) {
            // It's the audio for the previous header
            this.playAudioChunk(buffer);
            this.ttsHeader = null;
        } else {
            this.log('warn', 'Received binary without header');
        }
    }

    async playAudioChunk(buffer: ArrayBuffer) {
        if (!this.audioContext) return;

        const float32Data = convertPCM16ToFloat32(buffer);
        const audioBuffer = this.audioContext.createBuffer(1, float32Data.length, 16000);
        audioBuffer.copyToChannel(float32Data, 0);

        const source = this.audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.audioContext.destination);

        // Schedule playback
        if (this.nextStartTime < this.audioContext.currentTime) {
            this.nextStartTime = this.audioContext.currentTime;
        }
        source.start(this.nextStartTime);
        this.nextStartTime += audioBuffer.duration;
    }

    initAudioContext() {
        if (!this.audioContext) {
            // @ts-ignore
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioContext({ sampleRate: 16000 });
        }
    }

    async startMic() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // We need 16kHz PCM16 Mono
            const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
                sampleRate: 16000,
            });

            const source = audioContext.createMediaStreamSource(stream);

            // Use ScriptProcessor for legacy/simplicity (Worklet requires separate file loading)
            // bufferSize 4096 ~ 250ms at 16k. Let's send smaller chunks if possible or accept latency.
            // 2048 ~ 128ms. 
            const processor = audioContext.createScriptProcessor(2048, 1, 1);

            source.connect(processor);

            // Connect to destination via Gain(0) to keep processor alive but silent (prevent feedback)
            const gain = audioContext.createGain();
            gain.gain.value = 0;
            processor.connect(gain);
            gain.connect(audioContext.destination);

            let packetCount = 0;

            processor.onaudioprocess = (e) => {
                if (this.ws?.readyState !== WebSocket.OPEN) return;

                const inputData = e.inputBuffer.getChannelData(0);

                packetCount++;
                if (packetCount % 100 === 0) {
                    this.log('debug', `Sent ${packetCount} chunks`);
                }

                // Convert Float32 to Int16
                const buffer = new ArrayBuffer(inputData.length * 2);
                const view = new DataView(buffer);

                for (let i = 0; i < inputData.length; i++) {
                    let s = Math.max(-1, Math.min(1, inputData[i]));
                    s = s < 0 ? s * 0x8000 : s * 0x7FFF;
                    view.setInt16(i * 2, s, true); // Little endian
                }

                this.ws.send(buffer);
            };

            this.audioContext = audioContext;
            // Store refs
            (this as any).stream = stream;
            (this as any).processor = processor;
            (this as any).source = source;
            (this as any).gain = gain;

            this.log('system', 'Mic started (PCM16 16kHz)');
        } catch (e) {
            this.log('error', `Mic error: ${e}`);
        }
    }

    stopMic() {
        // Stop stream tracks
        if ((this as any).stream) {
            (this as any).stream.getTracks().forEach((track: any) => track.stop());
        }

        // Disconnect nodes
        if ((this as any).source) {
            (this as any).source.disconnect();
        }
        if ((this as any).processor) {
            (this as any).processor.disconnect();
        }
        if ((this as any).gain) {
            (this as any).gain.disconnect();
        }

        // Close context if specific one was created for mic
        if (this.audioContext && this.audioContext.state !== 'closed') {
            this.audioContext.close();
            this.audioContext = null;
        }

        this.log('system', 'Mic stopped');
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'audio_end' }));
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
        this.stopMic();
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
    }

    private log(type: string, payload: any) {
        const msg = {
            timestamp: new Date().toISOString().split('T')[1].slice(0, 8),
            type,
            payload
        };
        this.onLog(msg);
    }
}
