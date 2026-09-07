/**
 * Audio Manager for Kokoro TTS Audio Playback
 * Handles base64 PCM16 audio frames from RAG API
 * Uses Web Worker for decoding and Web Audio API for gapless playback
 */

class AudioManager {
  constructor() {
    this.audioContext = null;
    this.worker = null;
    this.sampleRate = 24000; // Kokoro TTS output is 24kHz
    this.playbackRate = 1.1; // 1.1x speedup
    this.isPlaying = false;
    this.nextPlayTime = 0;
    this.pendingDecodes = new Map();
    this.decodeQueue = [];
    this.isProcessing = false;
    this.onPlayingCallback = null;
    this.onEndedCallback = null;
    this.activeSources = []; // Track active audio sources for proper cleanup

    // Audio-video sync tracking
    this.totalSamplesScheduled = 0; // Total samples scheduled for playback
    this.playbackStartTime = 0; // When playback started (performance.now())
    this.isStopped = false;

    this.schedulingBuffer = []; // Buffer for batching small chunks
    this.SCHEDULING_BATCH_SIZE = 2400; // 100ms at 24kHz (reduced from 200ms for lower latency)
    this.jungle = null;
    this.jungleLatency = 0.1; // Latency introduced by Jungle (bufferTime)
  }

  /**
   * Initialize Audio Context and Web Worker
   */
  async init() {
    try {
      // DON'T create AudioContext here - wait until first audio playback
      // This avoids browser autoplay policy blocking

      // Create Web Worker (this is allowed without user gesture)
      this.worker = new Worker('/js/audioDecoder.worker.js');

      // Handle worker messages
      this.worker.onmessage = (event) => {
        const { type, id, audioData, error } = event.data;

        if (type === 'ready') {
          // Worker ready
        } else if (type === 'decoded') {
          // Resolve pending decode promise
          const resolver = this.pendingDecodes.get(id);
          if (resolver) {
            resolver(audioData);
            this.pendingDecodes.delete(id);
          }
        } else if (type === 'error') {
          console.error('[AudioManager] Worker error:', error);
          const resolver = this.pendingDecodes.get(id);
          if (resolver) {
            resolver(null);
            this.pendingDecodes.delete(id);
          }
        }
      };

      this.worker.onerror = (error) => {
        console.error('[AudioManager] Worker error:', error);
      };

    } catch (error) {
      console.error('[AudioManager] Initialization failed:', error);
      throw error;
    }
  }

  /**
   * Decode base64 audio chunk via Web Worker
   * @param {string} base64Chunk - Base64-encoded PCM16 audio
   * @returns {Promise<Float32Array>} Decoded audio data
   */
  async decodeViaWorker(base64Chunk) {
    const id = `decode_${Date.now()}_${Math.random()}`;

    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        this.pendingDecodes.delete(id);
        reject(new Error('Decode timeout'));
      }, 5000); // 5 second timeout

      this.pendingDecodes.set(id, (data) => {
        clearTimeout(timeoutId);
        resolve(data);
      });
      this.worker.postMessage({ id, base64Chunk });
    });
  }

  /**
   * Add a single audio chunk and play it
   * @param {string} base64Chunk - Base64-encoded PCM16 audio
   */
  async addChunk(base64Chunk) {
    // Reset stop flag since we are adding new content
    this.isStopped = false;

    // Add to queue
    this.decodeQueue.push(base64Chunk);

    // Process queue if not already processing
    if (!this.isProcessing) {
      this.isProcessing = true;
      await this._processQueue();
      this.isProcessing = false;
    }
  }

  /**
   * Add a batch of audio frames (legacy support)
   * @param {Array} frames - Array of {data: base64} objects
   */
  async addBatch(frames) {
    const chunks = frames.map(f => f.data).filter(d => d);
    await this.addChunks(chunks);
  }

  /**
   * Add multiple audio chunks to the queue atomically
   * This prevents race conditions where chunks from different batches get interleaved
   * @param {Array<string>} chunks - Array of Base64-encoded PCM16 audio strings
   */
  async addChunks(chunks) {
    if (!chunks || chunks.length === 0) return;

    // Reset stop flag
    this.isStopped = false;

    // Add all chunks to queue AT ONCE
    this.decodeQueue.push(...chunks);

    // Process queue if not already processing
    if (!this.isProcessing) {
      this.isProcessing = true;
      await this._processQueue();
      this.isProcessing = false;
    }
  }

  /**
   * Process decode queue sequentially
   */
  async _processQueue() {
    try {
      while (this.decodeQueue.length > 0) {
        const base64Chunk = this.decodeQueue.shift();

        try {
          // Decode via worker
          const float32Data = await this.decodeViaWorker(base64Chunk);

          if (float32Data && float32Data.length > 0) {
            // Check if stopped while decoding
            if (this.isStopped) {
              console.log('[AudioManager] Dropping chunk because stopped');
              continue;
            }

            // BATCHING: Add to scheduling buffer instead of scheduling immediately
            // This reduces the number of AudioBufferSourceNodes created
            for (let i = 0; i < float32Data.length; i++) {
              this.schedulingBuffer.push(float32Data[i]);
            }

            // If buffer is large enough OR queue is empty, flush it
            if (this.schedulingBuffer.length >= this.SCHEDULING_BATCH_SIZE || this.decodeQueue.length === 0) {
              const batchData = new Float32Array(this.schedulingBuffer);
              this.schedulingBuffer = []; // Clear buffer
              await this._scheduleChunk(batchData);
            }
          }
        } catch (error) {
          console.error('[AudioManager] Error processing chunk:', error);
        }
      }
    } finally {
      // Ensure we flush any remaining data if loop exits
      if (this.schedulingBuffer.length > 0 && !this.isStopped) {
        const batchData = new Float32Array(this.schedulingBuffer);
        this.schedulingBuffer = [];
        await this._scheduleChunk(batchData);
      }
    }
  }

  /**
   * Schedule audio chunk for gapless playback
   * @param {Float32Array} float32Data - Decoded audio data
   */
  async _scheduleChunk(float32Data) {
    try {
      // Create AudioContext on first use (lazy initialization)
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
          sampleRate: this.sampleRate,
        });
      }

      // Resume context if suspended (browser autoplay policy)
      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      // Initialize Jungle if needed
      if (!this.jungle) {
        this.jungle = new Jungle(this.audioContext);
        // Compensate for 1.1x pitch up (-1.65 semitones approx -0.1375 mult)
        this.jungle.setPitchOffset(-0.1375);
        this.jungle.output.connect(this.audioContext.destination);
      }

      // Create audio buffer
      const audioBuffer = this.audioContext.createBuffer(
        1, // mono
        float32Data.length,
        this.sampleRate
      );

      // Copy data to buffer
      audioBuffer.getChannelData(0).set(float32Data);

      // Create buffer source
      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      // source.connect(this.audioContext.destination); // OLD
      source.connect(this.jungle.input); // NEW: Connect to Jungle

      // Track active source for cleanup
      this.activeSources.push(source);

      // Calculate play time (gapless scheduling)
      const currentTime = this.audioContext.currentTime;
      if (this.nextPlayTime < currentTime) {
        this.nextPlayTime = currentTime;
      }

      // Start playback
      source.playbackRate.value = this.playbackRate;
      source.start(this.nextPlayTime);

      // Update next play time
      this.nextPlayTime += audioBuffer.duration / this.playbackRate;

      // Handle first chunk - only set start time on FIRST play, not on resume
      if (!this.isPlaying) {
        this.isPlaying = true;
        // Only set playbackStartTime on the true first chunk, not on resume after buffer underrun
        if (!this.playbackStartTime) {
          this.playbackStartTime = performance.now();
          // Also track audioContext start time for better sync
          this.audioContextStartTime = this.audioContext.currentTime;
        }
        if (this.onPlayingCallback) {
          this.onPlayingCallback();
        }
      }

      // Track total samples scheduled for audio-video sync
      this.totalSamplesScheduled += float32Data.length;

      // Handle end of buffer
      source.onended = () => {
        // Remove from active sources
        const index = this.activeSources.indexOf(source);
        if (index > -1) {
          this.activeSources.splice(index, 1);
        }

        // Check if this was the last chunk
        // Note: checking schedulingBuffer too
        if (this.decodeQueue.length === 0 && this.schedulingBuffer.length === 0 && this.nextPlayTime <= this.audioContext.currentTime + 0.1) {
          this.isPlaying = false;
          if (this.onEndedCallback) {
            this.onEndedCallback();
          }
        }
      };
    } catch (error) {
      console.error('[AudioManager] Error scheduling chunk:', error);
    }
  }

  /**
   * Get current playback position in samples (for audio-video sync)
   * IMPORTANT: Continues tracking even during buffer underruns
   * @returns {number} Number of samples that have been played
   */
  getCurrentPlaybackSamples() {
    // If we haven't started playing yet, return 0
    if (!this.playbackStartTime || !this.audioContext) {
      return 0;
    }

    // IMPROVED SYNC: Use AudioContext time if available
    // This is more accurate than performance.now() and handles clock drift
    let elapsedSeconds;
    if (this.audioContext.state === 'running') {
      // Calculate based on AudioContext time relative to when we started
      // Compensate for Jungle latency
      elapsedSeconds = Math.max(0, this.audioContext.currentTime - this.audioContextStartTime - this.jungleLatency);
      // Handle negative time (if audioContextStartTime was set slightly in future or clock weirdness)
      if (elapsedSeconds < 0) elapsedSeconds = 0;
    } else {
      // Fallback to performance.now() if context is suspended/closed
      const elapsedMs = performance.now() - this.playbackStartTime;
      elapsedSeconds = elapsedMs / 1000;
    }

    // Cap at totalSamplesScheduled to prevent video running ahead of available audio
    const samplesFromTime = Math.floor(elapsedSeconds * this.sampleRate * this.playbackRate);
    return Math.min(samplesFromTime, this.totalSamplesScheduled);
  }

  /**
   * Stop all audio playback immediately
   * Critical for preventing overlapping audio
   */
  stop() {
    // Stop all currently playing audio sources
    for (const source of this.activeSources) {
      try {
        source.stop(); // Stop immediately
        source.disconnect(); // Disconnect from audio graph
      } catch (e) {
        // Ignore errors (source may have already ended)
      }
    }

    // Clear all queues and reset state
    this.activeSources = [];
    this.decodeQueue = [];
    this.isPlaying = false;
    this.nextPlayTime = 0;
    this.totalSamplesScheduled = 0;
    this.playbackStartTime = 0;
    this.isStopped = true; // Flag to prevent pending decodes from playing

    console.log('[AudioManager] Stopped - all audio cleared');
  }

  /**
   * Reset stop flag (call before starting new playback)
   */
  reset() {
    this.isStopped = false;
  }

  /**
   * Set callback for when audio starts playing
   * @param {Function} callback
   */
  onPlaying(callback) {
    this.onPlayingCallback = callback;
  }

  /**
   * Set callback for when audio ends
   * @param {Function} callback
   */
  onEnded(callback) {
    this.onEndedCallback = callback;
  }

  /**
   * Get current playing status
   * @returns {boolean}
   */
  getIsPlaying() {
    return this.isPlaying;
  }

  /**
   * Cleanup resources
   */
  destroy() {
    this.stop();
    if (this.jungle) {
      this.jungle.destroy();
      this.jungle = null;
    }
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    console.log('[AudioManager] Destroyed');
  }
}

// Export for use in avatar.js
window.AudioManager = AudioManager;
