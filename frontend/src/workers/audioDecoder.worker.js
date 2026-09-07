/**
 * Audio Decoder Web Worker
 * Decodes base64 PCM16 audio chunks to Float32Array for Web Audio API
 */

self.addEventListener('message', (event) => {
  const { id, base64Chunk } = event.data;

  try {
    // Decode base64 to binary
    const binaryString = atob(base64Chunk);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    // Convert to Int16Array (PCM 16-bit, little-endian)
    const int16Array = new Int16Array(bytes.buffer);

    // Convert to Float32Array for Web Audio API (-1.0 to 1.0 range)
    const float32Array = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
      float32Array[i] = int16Array[i] / 32768.0;
    }

    // Send back to main thread (transfer buffer for zero-copy)
    self.postMessage(
      {
        type: 'decoded',
        id,
        audioData: float32Array,
        sampleCount: float32Array.length,
      },
      [float32Array.buffer]
    );
  } catch (error) {
    self.postMessage({
      type: 'error',
      id,
      error: error.message,
    });
  }
});

// Signal ready
self.postMessage({ type: 'ready' });
