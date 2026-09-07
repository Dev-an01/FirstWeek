/**
 * Avatar Video Worker
 * Handles WebSocket connection and message processing off the main thread
 * to prevent video lag during heavy main thread activity.
 */

// Configuration - These defaults are overridden by 'configure' message from main thread
// Main thread passes runtime config from window.ENV_CONFIG
let config = {
    wsUrl: 'ws://localhost:8085',  // Default fallback, overridden by avatarVideoClient
    executiveId: 'anand_idle_v2',
    reconnectDelay: 3000,
    maxReconnectAttempts: 10
};

// State
let ws = null;
let isConnected = false;
let reconnectAttempts = 0;
let reconnectTimer = null;
let isLipSyncMode = false;
let lipSyncFrameBuffer = []; // Stores Uint8Array (compressed JPEG)

// Logger helper - disabled for performance
function log(message, ...args) {
    // Logging disabled for performance
}

function error(message, ...args) {
    console.error(`[AvatarWorker] ${message}`, ...args);
}

// Handle messages from main thread
self.onmessage = async (event) => {
    const { type, payload } = event.data;

    switch (type) {
        case 'configure':
            config = { ...config, ...payload };
            log('Configured:', config);
            break;

        case 'connect':
            await connect();
            break;

        case 'disconnect':
            disconnect();
            break;

        case 'send_audio':
            await sendTTSAudio(payload.audioData, payload.sampleRate);
            break;

        case 'send_transcript':
            sendTranscript(payload.text);
            break;

        case 'start_idle':
            requestIdle();
            break;

        case 'start_lip_sync':
            isLipSyncMode = true;
            lipSyncFrameBuffer = [];
            log('Starting lip-sync mode');
            break;

        case 'stop_lip_sync':
            stopLipSyncMode();
            break;

        case 'stop_speaking':
            stopSpeaking();
            break;
    }
};

/**
 * Wait for avatar service to be ready by polling health endpoint
 */
async function waitForServiceReady(maxAttempts = 20, delayMs = 1000) {
    const healthUrl = `${config.wsUrl.replace('ws://', 'http://').replace('wss://', 'https://')}/health`;
    log(`⏳ Waiting for service to be ready: ${healthUrl}`);

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            const response = await fetch(healthUrl, {
                method: 'GET',
                signal: AbortSignal.timeout(3000)
            });

            if (response.ok) {
                const data = await response.json();
                if (data.status === 'healthy') {
                    log(`✅ Service is healthy (attempt ${attempt}/${maxAttempts})`);
                    return true;
                }
            }
        } catch (err) {
            log(`⏳ Service not ready yet (attempt ${attempt}/${maxAttempts}):`, err.message);
        }

        if (attempt < maxAttempts) {
            await new Promise(resolve => setTimeout(resolve, delayMs));
        }
    }

    error(`❌ Service did not become ready after ${maxAttempts} attempts`);
    return false;
}

/**
 * Connect to Avatar Video Service
 */
async function connect() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        log('Already connected');
        return;
    }

    // Wait for service to be ready
    const isReady = await waitForServiceReady();
    if (!isReady) {
        postMessage({ type: 'status', payload: { status: 'failed', message: 'Service not ready' } });
        scheduleReconnect();
        return;
    }

    // Close existing
    if (ws) {
        try { ws.close(); } catch (e) { }
        ws = null;
    }

    try {
        const wsEndpoint = `${config.wsUrl}/ws/avatar/${config.executiveId}`;
        log('🔌 Connecting to:', wsEndpoint);

        postMessage({ type: 'status', payload: { status: 'connecting', message: 'Connecting...' } });

        ws = new WebSocket(wsEndpoint);

        // Connection timeout
        const connectionTimeout = setTimeout(() => {
            if (ws && ws.readyState === WebSocket.CONNECTING) {
                error('⏱️ Connection timeout');
                ws.close();
                scheduleReconnect();
            }
        }, 10000);

        ws.onopen = () => {
            clearTimeout(connectionTimeout);
            log('✅ Connected');
            isConnected = true;
            reconnectAttempts = 0;

            postMessage({ type: 'connected' });
            postMessage({ type: 'status', payload: { status: 'connected', message: 'Connected' } });
        };

        ws.onmessage = (event) => {
            handleMessage(event.data);
        };

        ws.onerror = (err) => {
            error('❌ WebSocket error');
            postMessage({ type: 'error', payload: { message: 'WebSocket error' } });
        };

        ws.onclose = (event) => {
            log('❌ Disconnected', event.code);
            isConnected = false;
            postMessage({ type: 'disconnected' });
            postMessage({ type: 'status', payload: { status: 'disconnected', message: 'Disconnected' } });
            scheduleReconnect();
        };

    } catch (err) {
        error('Failed to connect:', err);
        scheduleReconnect();
    }
}

/**
 * Handle incoming WebSocket message
 */
async function handleMessage(data) {
    try {
        const message = JSON.parse(data);

        switch (message.type) {
            case 'ready':
                log('✅ Avatar ready');
                // Auto-request idle
                try {
                    ws.send(JSON.stringify({ type: 'start_idle' }));
                } catch (e) { }
                break;

            case 'idle_frame':
                if (!isLipSyncMode && message.data) {
                    // OPTIMIZATION: Decode idle frame to ImageBitmap in worker
                    // This removes image decoding overhead from main thread
                    try {
                        const bytes = base64ToUint8Array(message.data);
                        const blob = new Blob([bytes], { type: 'image/jpeg' });
                        const bitmap = await createImageBitmap(blob);

                        // Transfer bitmap to main thread (zero-copy)
                        postMessage({
                            type: 'frame',
                            payload: {
                                data: bitmap,
                                isIdle: true,
                                isBitmap: true
                            }
                        }, [bitmap]);
                    } catch (err) {
                        error('Failed to decode idle frame:', err);
                    }
                }
                break;

            case 'video':
                if (message.data) {


                    // Convert base64 to Uint8Array immediately to save space and CPU later
                    const bytes = base64ToUint8Array(message.data);

                    if (isLipSyncMode) {
                        // Buffer for "complete" event (optional, but good for consistency)
                        lipSyncFrameBuffer.push(bytes);

                        // STREAMING: Send frame to main thread immediately!
                        postMessage({
                            type: 'frame',
                            payload: {
                                data: bytes,
                                isIdle: message.is_idle || false // Use server flag or default to false
                            }
                        });


                    } else {
                        // Treat as idle frame if not in lip-sync mode
                        try {
                            const blob = new Blob([bytes], { type: 'image/jpeg' });
                            const bitmap = await createImageBitmap(blob);

                            postMessage({
                                type: 'frame',
                                payload: {
                                    data: bitmap,
                                    isIdle: true,
                                    isBitmap: true
                                }
                            }, [bitmap]);
                        } catch (err) {
                            error('Failed to decode video frame:', err);
                        }
                    }
                }
                break;

            case 'video_complete':
                log('✅ Lip-sync video generation complete');
                // Send buffer of Uint8Arrays
                // Note: We don't decode these to bitmaps here to avoid massive memory usage
                // Main thread will decode them "just in time" using createImageBitmap
                postMessage({
                    type: 'lip_sync_complete',
                    payload: {
                        buffer: lipSyncFrameBuffer
                    }
                });
                break;

            case 'status':
                postMessage({ type: 'status', payload: { status: 'status', message: message.message || message.status } });
                break;

            case 'error':
                postMessage({ type: 'error', payload: { message: message.message } });
                break;
        }
    } catch (err) {
        error('Failed to parse message:', err);
    }
}

/**
 * Send TTS audio
 */
async function sendTTSAudio(audioData, sampleRate) {
    if (!isConnected || !ws) return;

    const CHUNK_SIZE = 4096;

    // Convert Object/Array back to Int16Array if needed
    const data = audioData instanceof Int16Array ? audioData : new Int16Array(Object.values(audioData));

    log(`🎵 Sending audio: ${data.length} samples`);

    for (let i = 0; i < data.length; i += CHUNK_SIZE) {
        const chunk = data.slice(i, Math.min(i + CHUNK_SIZE, data.length));
        const audioBase64 = arrayToBase64(chunk);

        try {
            ws.send(JSON.stringify({
                type: 'audio',
                data: audioBase64,
                sampleRate: sampleRate,
                format: 'int16',
                timestamp: performance.now()
            }));

            await new Promise(resolve => setTimeout(resolve, 10));
        } catch (err) {
            error('Failed to send audio chunk');
        }
    }
}

function sendTranscript(text) {
    if (!isConnected || !ws) return;
    try {
        ws.send(JSON.stringify({ type: 'transcript', text: text }));
    } catch (err) { }
}

function requestIdle() {
    if (!isConnected || !ws) return;
    try {
        isLipSyncMode = false;
        ws.send(JSON.stringify({ type: 'idle' }));
    } catch (err) { }
}

function stopLipSyncMode() {
    log('Stopping lip-sync mode');
    isLipSyncMode = false;
    const frames = lipSyncFrameBuffer;
    lipSyncFrameBuffer = [];

    postMessage({
        type: 'lip_sync_stopped',
        payload: { frames }
    });
}

/**
 * Stop speaking and return to idle animation
 * Sends stop_speaking message to server
 */
function stopSpeaking() {
    if (!isConnected || !ws) {
        return;
    }

    isLipSyncMode = false;
    lipSyncFrameBuffer = [];

    try {
        ws.send(JSON.stringify({ type: 'stop_speaking' }));
    } catch (err) {
        error('Failed to send stop_speaking:', err);
    }
}

function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);

    if (reconnectAttempts >= config.maxReconnectAttempts) {
        postMessage({ type: 'status', payload: { status: 'failed', message: 'Max retries reached' } });
        return;
    }

    reconnectAttempts++;
    postMessage({ type: 'status', payload: { status: 'reconnecting', message: `Reconnecting (${reconnectAttempts})...` } });

    reconnectTimer = setTimeout(() => {
        connect();
    }, config.reconnectDelay);
}

function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) {
        ws.close();
        ws = null;
    }
    isConnected = false;
}

function arrayToBase64(array) {
    const bytes = new Uint8Array(array.buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

function base64ToUint8Array(base64) {
    const binaryString = atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);

    // OPTIMIZED: Process 4 bytes at a time for better performance
    const len4 = len - (len % 4);
    for (let i = 0; i < len4; i += 4) {
        bytes[i] = binaryString.charCodeAt(i);
        bytes[i + 1] = binaryString.charCodeAt(i + 1);
        bytes[i + 2] = binaryString.charCodeAt(i + 2);
        bytes[i + 3] = binaryString.charCodeAt(i + 3);
    }
    // Handle remaining bytes
    for (let i = len4; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes;
}
