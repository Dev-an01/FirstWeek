/**
 * Avatar Video WebSocket Client
 * Connects to Avatar Video Streaming Service (GCP)
 * Handles idle frames and lip-sync video streaming
 * 
 * REFACTORED: Uses Web Worker for WebSocket handling to prevent main thread blocking
 */

class AvatarVideoClient {
  constructor(config) {
    // Build default wsUrl from runtime config
    const defaultWsUrl = (() => {
      const protocol = window.ENV_CONFIG?.AVATAR_VIDEO_PROTOCOL || 'ws';
      const host = window.ENV_CONFIG?.AVATAR_VIDEO_HOST || window.location.hostname;
      const port = window.ENV_CONFIG?.AVATAR_VIDEO_PORT || '';
      const path = window.ENV_CONFIG?.AVATAR_VIDEO_PATH || '';

      // Build URL: protocol://host[:port][/path]
      let url = `${protocol}://${host}`;
      if (port && port !== '443' && port !== '80') {
        url += `:${port}`;
      }
      if (path) {
        url += path;
      }
      return url;
    })();

    this.config = {
      wsUrl: config.wsUrl || defaultWsUrl,
      executiveId: config.executiveId || 'anand_idle_v2',
      reconnectDelay: 3000,
      maxReconnectAttempts: 10,
      ...config
    };

    this.worker = null;
    this.isConnected = false;
    this.videoRenderer = null;

    // Lip-sync mode
    this.isLipSyncMode = false;
    this.lipSyncFrameBuffer = [];
    this.lipSyncFrameCallback = null;

    // Frame tracking
    this._firstFrameShown = false;
    this._idleFrameCount = 0;

    // Callbacks
    this.onConnectedCallback = null;
    this.onDisconnectedCallback = null;
    this.onErrorCallback = null;
    this.onStatusCallback = null;

    this._initWorker();


  }

  /**
   * Initialize Web Worker
   */
  _initWorker() {
    try {
      this.worker = new Worker('js/avatarVideoWorker.js');

      this.worker.onmessage = (event) => {
        this.handleWorkerMessage(event.data);
      };

      this.worker.onerror = (error) => {
        console.error('[AvatarVideoClient] Worker error:', error);
        if (this.onErrorCallback) {
          this.onErrorCallback(error);
        }
      };

      // Send configuration
      this.worker.postMessage({
        type: 'configure',
        payload: this.config
      });

    } catch (error) {
      console.error('[AvatarVideoClient] Failed to initialize worker:', error);
    }
  }

  /**
   * Handle messages from Worker
   */
  handleWorkerMessage(message) {
    const { type, payload } = message;

    switch (type) {
      case 'connected':
        this.isConnected = true;
        if (this.onConnectedCallback) this.onConnectedCallback();
        break;

      case 'disconnected':
        this.isConnected = false;
        if (this.onDisconnectedCallback) this.onDisconnectedCallback();
        if (this.videoRenderer) this.videoRenderer.hide();
        break;

      case 'status':
        this.notifyStatus(payload.status, payload.message);
        break;

      case 'error':
        if (this.onErrorCallback) this.onErrorCallback(new Error(payload.message));
        break;

      case 'frame':
        this.handleFrame(payload);
        break;

      case 'lip_sync_complete':
        this.handleLipSyncComplete(payload);
        break;

      case 'lip_sync_stopped':
        // Handle returned frames if needed
        break;
    }
  }

  /**
   * Handle video frame from Worker
   */
  handleFrame(payload) {
    const { data, isIdle } = payload;

    if (this.videoRenderer && data) {
      // Show canvas on first frame
      if (!this._firstFrameShown) {
        this._firstFrameShown = true;
        this.videoRenderer.show();
        this.notifyStatus('streaming', 'Idle animation streaming');
      }

      if (isIdle) {
        // Render idle frames immediately
        this.videoRenderer.renderFrame(data);

        this._idleFrameCount++;
      } else {
        // Lip-sync frame: Pass to callback if available, otherwise render immediately (fallback)
        if (this.lipSyncFrameCallback) {
          this.lipSyncFrameCallback(data);
        } else {
          this.videoRenderer.renderFrame(data);
        }
      }
    }
  }

  /**
   * Handle lip sync completion
   */
  handleLipSyncComplete(payload) {
    // Signal completion
    // Signal completion to main app via callback
    if (this.onLipSyncCompleteCallback) {
      this.onLipSyncCompleteCallback(payload);
    }

    // Legacy support (optional, can remove if not used elsewhere)
    if (window.state) {
      window.state.lipSyncComplete = true;
    }
  }

  /**
   * Set video renderer
   * @param {VideoRenderer} renderer
   */
  setRenderer(renderer) {
    this.videoRenderer = renderer;
  }

  /**
   * Connect to Avatar Video Service
   */
  async connect() {
    if (this.worker) {
      this.worker.postMessage({ type: 'connect' });
    }
  }

  /**
   * Send TTS audio to Avatar Service for lip-sync
   * NOTE: Currently disabled - backend handles audio push directly
   * @param {Int16Array} audioData - PCM16 audio data
   * @param {number} sampleRate - Sample rate (typically 24000)
   */
  async sendTTSAudio(audioData, sampleRate = 24000) {
    // Audio push is handled by backend directly for lower latency
    // Frontend audio push is disabled to avoid duplicate streams
  }

  /**
   * Send transcript for lip-sync (alternative to audio)
   * @param {string} text - The text to lip-sync
   */
  sendTranscript(text) {
    if (!this.isConnected || !this.worker) return;
    this.worker.postMessage({
      type: 'send_transcript',
      payload: { text }
    });
  }

  /**
   * Request idle animation
   */
  requestIdle() {
    if (!this.isConnected || !this.worker) return;
    this.isLipSyncMode = false;
    this.worker.postMessage({ type: 'start_idle' });
  }

  /**
   * Start lip-sync mode
   */
  startLipSyncMode() {
    this.isLipSyncMode = true;
    if (this.worker) {
      this.worker.postMessage({ type: 'start_lip_sync' });
    }
  }

  /**
   * Stop lip-sync mode
   */
  stopLipSyncMode() {
    this.isLipSyncMode = false;
    if (this.worker) {
      this.worker.postMessage({ type: 'stop_lip_sync' });
    }
    // Note: The worker will return buffered frames via 'lip_sync_stopped' message if needed,
    // but currently the main app handles clearing buffers itself in interruptAIResponse()
    return []; // Return empty array as we can't synchronously get frames from worker
  }

  /**
   * Set callback for lip-sync frame received
   */
  onLipSyncFrame(callback) {
    this.lipSyncFrameCallback = callback;
  }

  /**
   * Set callback for lip-sync completion
   */
  onLipSyncComplete(callback) {
    this.onLipSyncCompleteCallback = callback;
  }

  /**
   * Stop speaking and return to idle animation
   * Sends stop_speaking message to server via worker
   */
  stopSpeaking() {
    if (!this.worker) {
      return;
    }
    this.worker.postMessage({ type: 'stop_speaking' });
    this.isLipSyncMode = false;
    this.lipSyncFrameBuffer = [];
    this.lipSyncFrameCallback = null;
  }

  /**
   * Disconnect from avatar service
   */
  disconnect() {
    if (this.worker) {
      this.worker.postMessage({ type: 'disconnect' });
    }
    this.isConnected = false;
  }

  /**
   * Notify status change
   */
  notifyStatus(status, message) {
    if (this.onStatusCallback) {
      this.onStatusCallback(status, message);
    }
  }

  /**
   * Set callback for connection established
   */
  onConnected(callback) {
    this.onConnectedCallback = callback;
  }

  /**
   * Set callback for disconnection
   */
  onDisconnected(callback) {
    this.onDisconnectedCallback = callback;
  }

  /**
   * Set callback for errors
   */
  onError(callback) {
    this.onErrorCallback = callback;
  }

  /**
   * Set callback for status updates
   */
  onStatus(callback) {
    this.onStatusCallback = callback;
  }

  /**
   * Get connection status
   */
  getStatus() {
    return {
      isConnected: this.isConnected,
      reconnectAttempts: 0, // Managed by worker now
      rendererStats: this.videoRenderer ? this.videoRenderer.getStats() : null
    };
  }

  /**
   * Cleanup resources
   */
  destroy() {
    console.log('[AvatarVideoClient] Destroying...');
    this.disconnect();
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
    }
    this.onConnectedCallback = null;
    this.onDisconnectedCallback = null;
    this.onErrorCallback = null;
    this.onStatusCallback = null;
  }
}

// Export for use in avatar.js
window.AvatarVideoClient = AvatarVideoClient;
