
import React, { useEffect, useRef, useState } from 'react';
import { WSClient, LogMessage } from './wsClient';

const HOST = import.meta.env.VITE_WS_HOST || 'localhost:8001';
const PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL = `${PROTOCOL}//${HOST}/ws/audio`;

function App() {
    const [client] = useState(() => new WSClient());
    const [isConnected, setIsConnected] = useState(false);
    const [isRecording, setIsRecording] = useState(false);
    const [logs, setLogs] = useState<LogMessage[]>([]);

    const [transcript, setTranscript] = useState<{ user: string, llm: string }>({ user: '', llm: '' });

    useEffect(() => {
        // Setup callbacks
        client.onLog = (msg) => {
            setLogs(prev => [msg, ...prev].slice(0, 50));
        };

        client.onSttPartial = (text) => {
            setTranscript(prev => ({ ...prev, user: text + '...' }));
        };

        client.onSttFinal = (text) => {
            setTranscript(prev => ({ ...prev, user: text }));
        };

        client.onLlmPartial = (text) => {
            setTranscript(prev => ({ ...prev, llm: prev.llm + text }));
        };

        client.onLlmFinal = (text) => {
            // Could reset streaming state
        };

        return () => {
            client.disconnect();
        };
    }, [client]);

    const handleConnect = () => {
        if (isConnected) {
            client.disconnect();
            setIsConnected(false);
            setIsRecording(false);
        } else {
            client.connect(WS_URL);
            setIsConnected(true);
            setTranscript({ user: '', llm: '' }); // clear
        }
    };

    const handleMic = async () => {
        if (isRecording) {
            client.stopMic();
            setIsRecording(false);
        } else {
            await client.startMic();
            setIsRecording(true);
            // Reset LLM part for new turn
            setTranscript(prev => ({ ...prev, llm: '' }));
        }
    };

    return (
        <div style={{ padding: '20px', fontFamily: 'sans-serif', maxWidth: '800px', margin: '0 auto' }}>
            <h1>Audio Conversational Bot</h1>

            <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #ccc', borderRadius: '8px' }}>
                <button onClick={handleConnect} style={{ marginRight: '10px', padding: '8px 16px' }}>
                    {isConnected ? 'Disconnect' : 'Connect'}
                </button>

                <button onClick={handleMic} disabled={!isConnected} style={{
                    padding: '8px 16px',
                    backgroundColor: isRecording ? '#ff4444' : '#44aa44',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: isConnected ? 'pointer' : 'not-allowed'
                }}>
                    {isRecording ? 'Stop Mic' : 'Start Mic'}
                </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                <div style={{ border: '1px solid #eee', padding: '15px', borderRadius: '8px', minHeight: '200px' }}>
                    <h3>User (STT)</h3>
                    <p style={{ fontSize: '1.2em', color: '#333' }}>{transcript.user}</p>
                </div>

                <div style={{ border: '1px solid #eee', padding: '15px', borderRadius: '8px', minHeight: '200px', backgroundColor: '#f9f9f9' }}>
                    <h3>Bot (LLM)</h3>
                    <p style={{ fontSize: '1.2em', color: '#0066cc', whiteSpace: 'pre-wrap' }}>{transcript.llm}</p>
                </div>
            </div>

            <div style={{ marginTop: '30px', borderTop: '1px solid #ddd', paddingTop: '10px' }}>
                <h3>Logs</h3>
                <div style={{ height: '300px', overflowY: 'auto', backgroundColor: '#333', color: '#0f0', padding: '10px', fontFamily: 'monospace', fontSize: '12px' }}>
                    {logs.map((log, i) => (
                        <div key={i}>
                            <span style={{ color: '#888' }}>[{log.timestamp}]</span>{' '}
                            <span style={{ color: '#fff' }}>{log.type.toUpperCase()}</span>:{' '}
                            {typeof log.payload === 'object' ? JSON.stringify(log.payload) : log.payload}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

export default App;
