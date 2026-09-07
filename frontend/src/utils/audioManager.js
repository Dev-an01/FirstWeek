/**
 * Audio Manager for Real-Time TTS Streaming
 *
 * Concatenates small PCM chunks into larger buffers for smooth playback.
 * Prevents gaps by immediately scheduling accumulated audio.
 */

class AudioManager {
  constructor() {
    this.audioContext = null;
    this.worker = null;
    this.workerReady = false;
    this.workerCallbacks = new Map();
    this.nextWorkerId = 0;

    this.sampleRate = 24000; // Must match Kokoro output
    this.nextPlayTime = 0;
    this.isPlaying = false;
    this.activeSources = new Set();

    // Real-time streaming: schedule chunks as they arrive
    this.schedulingLock = false;
    this.playbackStarted = false;

    this._initWorker();
  }

  /**
   * Initialize Web Worker for audio decoding
   */
  _initWorker() {
    try {
      this.worker = new Worker(
        new URL('../workers/audioDecoder.worker.js', import.meta.url),
        { type: 'module' }
      );

      this.worker.onmessage = (event) => {
        const { type, id, audioData, error } = event.data;

        if (type === 'ready') {
          this.workerReady = true;
          return;
        }

        if (type === 'error') {
          const callback = this.workerCallbacks.get(id);
          if (callback) {
            callback.reject(new Error(error));
            this.workerCallbacks.delete(id);
          }
          return;
        }

        if (type === 'decoded') {
          const callback = this.workerCallbacks.get(id);
          if (callback) {
            callback.resolve(audioData);
            this.workerCallbacks.delete(id);
          }
        }
      };

      this.worker.onerror = (error) => {
        console.error('[AudioManager] Worker initialization error:', error);
      };
    } catch (error) {
      console.error('[AudioManager] Failed to initialize worker:', error);
    }
  }

  /**
   * Initialize AudioContext
   */
  async initialize() {
    if (!this.audioContext) {
      try {
        this.audioContext = new (window.AudioContext ||
          window.webkitAudioContext)({
          sampleRate: this.sampleRate,
        });
      } catch (e) {
        this.audioContext = new (window.AudioContext ||
          window.webkitAudioContext)();
      }
    }

    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }
  }

  /**
   * Resume audio context
   */
  async resume() {
    await this.initialize();
  }

  /**
   * Wait for worker to be ready
   */
  async _waitForWorker() {
    if (this.workerReady) return;

    const startTime = Date.now();
    while (!this.workerReady && Date.now() - startTime < 5000) {
      // eslint-disable-next-line no-promise-executor-return
      await new Promise((resolve) => setTimeout(resolve, 50));
    }

    if (!this.workerReady) {
      throw new Error('Worker failed to initialize');
    }
  }

  /**
   * Add audio chunk (base64 PCM16) and schedule for immediate playback
   * Real-time streaming: plays audio as chunks arrive
   */
  async addChunk(base64Chunk) {
    if (!base64Chunk) return;

    // Wait for worker to be ready (don't drop chunks!)
    await this._waitForWorker();
    await this.initialize();

    // Decode using worker
    const workerId = this.nextWorkerId++;
    const decodePromise = new Promise((resolve, reject) => {
      this.workerCallbacks.set(workerId, { resolve, reject });

      setTimeout(() => {
        if (this.workerCallbacks.has(workerId)) {
          this.workerCallbacks.delete(workerId);
          reject(new Error('Worker decode timeout'));
        }
      }, 5000);
    });

    this.worker.postMessage({
      id: workerId,
      base64Chunk,
    });

    const float32Data = await decodePromise;

    // Schedule audio for immediate playback (real-time streaming!)
    await this._scheduleChunk(float32Data);
  }

  /**
   * Add multiple audio chunks (batch)
   * Processes frames sequentially to maintain correct playback order
   */
  async addBatch(frames) {
    // Process frames sequentially to maintain order
    for (const frame of frames) {
      await this.addChunk(frame.data);
    }
  }

  /**
   * Schedule a single audio chunk for immediate playback
   * Uses audio scheduling to chain chunks seamlessly without gaps
   */
  async _scheduleChunk(float32Data) {
    if (!float32Data || float32Data.length === 0) return;

    // Ensure audio context is running
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }

    // Wait for any ongoing scheduling to complete (prevent race conditions)
    while (this.schedulingLock) {
      // eslint-disable-next-line no-promise-executor-return
      await new Promise((resolve) => setTimeout(resolve, 10));
    }

    this.schedulingLock = true;

    try {
      // Create audio buffer for this chunk
      const audioBuffer = this.audioContext.createBuffer(
        1,
        float32Data.length,
        this.sampleRate
      );
      audioBuffer.getChannelData(0).set(float32Data);

      // Calculate start time
      const { currentTime } = this.audioContext;

      if (!this.playbackStarted) {
        // First chunk: start immediately with small buffer (50ms for safety)
        this.nextPlayTime = currentTime + 0.05;
        this.playbackStarted = true;
      } else {
        // Subsequent chunks: schedule at nextPlayTime (or immediately if we're behind)
        this.nextPlayTime = Math.max(this.nextPlayTime, currentTime);
      }

      // Create and schedule source
      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.playbackRate.value = 1.0;
      source.connect(this.audioContext.destination);

      // Track active source
      this.activeSources.add(source);
      this.isPlaying = true;

      // Setup ended handler
      source.onended = () => {
        this.activeSources.delete(source);
        if (this.activeSources.size === 0) {
          this.isPlaying = false;
        }
      };

      // Start playback at scheduled time
      source.start(this.nextPlayTime);

      // Update nextPlayTime for next chunk (duration = samples / sampleRate)
      const { duration } = audioBuffer;
      this.nextPlayTime += duration;
    } catch (error) {
      console.error('[AudioManager] Failed to schedule audio chunk:', error);
      throw error;
    } finally {
      this.schedulingLock = false;
    }
  }

  /**
   * Wait for all pending audio to finish playing
   * (Replaces old flushRemaining behavior for compatibility)
   */
  async flushRemaining() {
    // Just wait for playback to complete
    while (this.isPlaying || this.activeSources.size > 0) {
      // eslint-disable-next-line no-promise-executor-return
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }

  /**
   * Stop playback and reset state
   */
  stop() {
    // Stop all active sources

    for (const source of this.activeSources) {
      try {
        source.stop();
        source.disconnect();
      } catch (e) {
        // Already stopped
      }
    }

    this.activeSources.clear();
    this.playbackStarted = false;
    this.schedulingLock = false;

    if (this.audioContext) {
      this.nextPlayTime = this.audioContext.currentTime;
    }

    this.isPlaying = false;
  }

  /**
   * Cleanup
   */
  destroy() {
    this.stop();
    if (this.worker) {
      this.worker.terminate();
    }
    if (this.audioContext) {
      this.audioContext.close();
    }
  }
}

// Export singleton
export const audioManager = new AudioManager();
