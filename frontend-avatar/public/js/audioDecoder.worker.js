/**
 * Audio Decoder Web Worker
 * Decodes base64 PCM16 audio chunks to Float32Array for Web Audio API
 */

self.addEventListener('message', (event) => {
  const { id, base64Chunk } = event.data;

  try {
    // OPTIMIZED: Decode base64 to binary with batched processing
    const binaryString = atob(base64Chunk);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);

    // Process 4 bytes at a time for better performance
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

    // Convert to Int16Array (PCM 16-bit, little-endian)
    const int16Array = new Int16Array(bytes.buffer);
    const sampleCount = int16Array.length;

    // OPTIMIZED: Convert to Float32Array with loop unrolling
    const float32Array = new Float32Array(sampleCount);
    const scale = 1 / 32768.0;
    const len4Samples = sampleCount - (sampleCount % 4);

    for (let i = 0; i < len4Samples; i += 4) {
      float32Array[i] = int16Array[i] * scale;
      float32Array[i + 1] = int16Array[i + 1] * scale;
      float32Array[i + 2] = int16Array[i + 2] * scale;
      float32Array[i + 3] = int16Array[i + 3] * scale;
    }
    for (let i = len4Samples; i < sampleCount; i++) {
      float32Array[i] = int16Array[i] * scale;
    }

    // Send back to main thread (transfer buffer for zero-copy)
    self.postMessage(
      {
        type: 'decoded',
        id,
        audioData: float32Array,
        sampleCount: sampleCount,
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
