import { useState, useRef, useCallback, useEffect } from 'react';

/**
 * useVoiceInput Hook
 *
 * Handles voice recording and real-time speech-to-text transcription
 *
 * Features:
 * - Browser microphone access
 * - Real-time audio capture (16kHz, mono, int16)
 * - WebSocket connection to STT service
 * - Language support (EN/JA)
 * - Automatic VAD (Voice Activity Detection) on server
 */
export function useVoiceInput({ onTranscript, language = 'en' }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState(null);

  const audioContext = useRef(null);
  const websocket = useRef(null);
  const stream = useRef(null);

  /**
   * Initialize WebSocket connection to STT service
   */
  const connectWebSocket = useCallback(() => {
    return new Promise((resolve, reject) => {
      try {
        // Connect to STT WebSocket endpoint via the current host (Caddy proxies /api/v1* → rag-api)
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/v1/stt/stream`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log('[VoiceInput] WebSocket connected');

          // Send language configuration
          ws.send(
            JSON.stringify({
              type: 'config',
              language,
            })
          );

          websocket.current = ws;
          resolve(ws);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.type === 'transcript') {
              console.log('[VoiceInput] Transcript received:', data.text);
              onTranscript?.(data.text);
            } else if (data.type === 'error') {
              console.error('[VoiceInput] STT error:', data.message);
              setError(data.message);
            }
          } catch (err) {
            console.error(
              '[VoiceInput] Failed to parse WebSocket message:',
              err
            );
          }
        };

        ws.onerror = (err) => {
          console.error('[VoiceInput] WebSocket error:', err);
          reject(new Error('WebSocket connection failed'));
        };

        ws.onclose = () => {
          console.log('[VoiceInput] WebSocket closed');
          websocket.current = null;
        };
      } catch (err) {
        reject(err);
      }
    });
  }, [language, onTranscript]);

  /**
   * Send language config update when language changes
   */
  useEffect(() => {
    if (websocket.current && websocket.current.readyState === WebSocket.OPEN) {
      console.log(
        `[VoiceInput] Language changed to: ${language}, sending config update`
      );
      websocket.current.send(
        JSON.stringify({
          type: 'config',
          language,
        })
      );
    }
  }, [language]);

  /**
   * Process audio chunk and send to WebSocket
   */
  const processAudioChunk = useCallback((audioData) => {
    if (!websocket.current || websocket.current.readyState !== WebSocket.OPEN) {
      return;
    }

    // Convert Float32Array to Int16Array (required by STT service)
    const int16Array = new Int16Array(audioData.length);
    for (let i = 0; i < audioData.length; i++) {
      const s = Math.max(-1, Math.min(1, audioData[i]));
      int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    // Encode as base64
    const bytes = new Uint8Array(int16Array.buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const base64 = btoa(binary);

    // Send to WebSocket
    websocket.current.send(
      JSON.stringify({
        type: 'audio',
        data: base64,
      })
    );
  }, []);

  /**
   * Start voice recording
   */
  const startRecording = useCallback(async () => {
    try {
      setIsConnecting(true);
      setError(null);

      // Request microphone access (don't specify sampleRate - use browser default)
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1, // Mono
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Connect to WebSocket
      await connectWebSocket();

      // Create AudioContext with 16kHz sample rate to allow browser-native resampling
      // This prevents aliasing artifacts ("random noise") from manual linear interpolation
      const AudioContextClass =
        window.AudioContext || window.webkitAudioContext;
      const contextOptions = { sampleRate: 16000, latencyHint: 'interactive' };

      try {
        audioContext.current = new AudioContextClass(contextOptions);
      } catch (err) {
        console.warn(
          '[VoiceInput] Failed to set sample rate, falling back to default:',
          err
        );
        audioContext.current = new AudioContextClass();
      }

      const source = audioContext.current.createMediaStreamSource(
        stream.current
      );

      // Create processor that will resample to 16kHz
      const processorBufferSize = 4096;
      const processor = audioContext.current.createScriptProcessor(
        processorBufferSize,
        1,
        1
      );

      // Calculate resampling ratio
      const inputSampleRate = audioContext.current.sampleRate;
      const outputSampleRate = 16000;
      const resampleRatio = outputSampleRate / inputSampleRate;

      console.log(
        `[VoiceInput] Audio: ${inputSampleRate}Hz → 16000Hz (ratio: ${resampleRatio.toFixed(3)})`
      );

      // Process audio chunks with resampling
      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);

        // Simple linear interpolation resampling
        const outputLength = Math.floor(inputData.length * resampleRatio);
        const outputData = new Float32Array(outputLength);

        for (let i = 0; i < outputLength; i++) {
          const srcIndex = i / resampleRatio;
          const srcIndexFloor = Math.floor(srcIndex);
          const srcIndexCeil = Math.min(
            srcIndexFloor + 1,
            inputData.length - 1
          );
          const fraction = srcIndex - srcIndexFloor;

          // Linear interpolation
          outputData[i] =
            inputData[srcIndexFloor] * (1 - fraction) +
            inputData[srcIndexCeil] * fraction;
        }

        processAudioChunk(outputData);
      };

      source.connect(processor);
      processor.connect(audioContext.current.destination);

      setIsRecording(true);
      setIsConnecting(false);

      console.log('[VoiceInput] Recording started');
    } catch (err) {
      console.error('[VoiceInput] Failed to start recording:', err);
      setError(err.message || 'Failed to access microphone');
      setIsRecording(false);
      setIsConnecting(false);
    }
  }, [connectWebSocket, processAudioChunk]);

  /**
   * Stop voice recording
   */
  const stopRecording = useCallback(() => {
    console.log('[VoiceInput] Stopping recording');

    // Stop audio context
    if (audioContext.current) {
      audioContext.current.close();
      audioContext.current = null;
    }

    // Stop media stream
    if (stream.current) {
      stream.current.getTracks().forEach((track) => track.stop());
      stream.current = null;
    }

    // Close WebSocket
    if (websocket.current) {
      websocket.current.close();
      websocket.current = null;
    }

    setIsRecording(false);
  }, []);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      if (isRecording) {
        stopRecording();
      }
    };
  }, [isRecording, stopRecording]);

  return {
    isRecording,
    isConnecting,
    error,
    startRecording,
    stopRecording,
  };
}
