/**
 * FirstWeek Interface JavaScript
 * Integrates with Recall.ai for meeting bots
 *
 * Flow:
 * 1. Capture meeting audio (Recall.ai provides MediaStream)
 * 2. Stream audio to STT service via WebSocket
 * 3. Receive transcripts from STT
 * 4. Send transcripts to Recall Service
 * 5. Play TTS audio responses
 * 6. Recall.ai captures and streams to meeting
 */

// Configuration
const CONFIG = {
  // Get bot ID from URL parameter (passed by Recall Service)
  botId: new URLSearchParams(window.location.search).get('bot_id') || 'default',

  // Language setting (en or ja)
  language: new URLSearchParams(window.location.search).get('lang') || 'en',

  // Service URLs
  // IMPORTANT: When Avatar Interface is loaded by Recall.ai, it runs in their browser
  // So we need to use publicly accessible URLs, not Docker internal hostnames
  sttWsUrl: (() => {
    // Use same origin for STT WebSocket (proxied by avatar-interface server)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/api/v1/stt/stream`;
  })(),

  recallServiceUrl: window.location.hostname === 'localhost'
    ? 'http://localhost:3003'
    : `http://${window.location.hostname}:3003`,

  // RAG API is proxied through avatar-interface server
  ragApiUrl: `${window.location.protocol}//${window.location.host}`,

  // Avatar Video Service (GCP) - Use runtime config
  avatarVideoUrl: (() => {
    const protocol = window.ENV_CONFIG?.AVATAR_VIDEO_PROTOCOL || 'ws';
    const host = window.ENV_CONFIG?.AVATAR_VIDEO_HOST || window.location.hostname;
    const port = window.ENV_CONFIG?.AVATAR_VIDEO_PORT;
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
  })(),
  avatarExecutiveId: 'anand_idle_v2',

  // Audio settings
  sampleRate: 16000,  // STT expects 16kHz
  chunkDurationMs: 100,  // 100ms chunks for VAD

  // WebRTC ICE Servers (STUN/TURN)
  // If connection fails (ICE failed), you MUST provide a valid TURN server here.
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    // {
    //   urls: 'turn:your-turn-server.com:3478',
    //   username: 'username',
    //   credential: 'password'
    // }
  ],

  // VAD (Voice Activity Detection) settings for auto-interrupt
  vad: {
    enabled: true,  // Enable auto-interrupt when user speaks
    rmsThreshold: 0.05,  // RMS threshold (Increased to 0.05 to avoid false positives)
    consecutiveChunksRequired: 6,  // Require 6 consecutive chunks (~600ms) to avoid false positives
    cooldownMs: 1500,  // 1.5s cooldown after interrupt to avoid re-triggering
  },

  // Debug
  enableDebug: window.location.search.includes('debug=true'),
  autoPlayDelay: 100
};

// OPTIMIZATION: Conditional logging to reduce overhead in production
const DEBUG = CONFIG.enableDebug;
function log(...args) {
  if (DEBUG) console.log('[Avatar]', ...args);
}

// DOM Elements
const elements = {
  avatar: document.getElementById('avatar-img'),
  status: document.getElementById('avatar-status'),
  speakingIndicator: document.getElementById('speaking-indicator'),
  connectionStatus: document.getElementById('connection-status'),
  statusText: document.getElementById('status-text'),
  audio: document.getElementById('tts-audio'),
  debugPanel: document.getElementById('debug-panel'),
  debugConnection: document.getElementById('debug-connection'),
  debugLastAudio: document.getElementById('debug-last-audio'),
  debugAudioPlaying: document.getElementById('debug-audio-playing')
};

// State
const state = {
  isConnected: false,
  isSpeaking: false,
  isListening: false,
  currentAudioUrl: null,
  audioQueue: [],
  sttWs: null,
  audioContext: null,
  audioStream: null,
  mediaRecorder: null,
  audioManager: null, // Kokoro TTS audio manager

  // Avatar Video components
  videoRenderer: null,
  avatarVideoClient: null,

  // TTS Audio buffering for lip-sync
  audioBuffer: [],

  // Lip-sync video buffering and streaming
  lipSyncVideoBuffer: [],
  isReceivingLipSync: false,
  lipSyncComplete: false,
  lipSyncPlaybackStarted: false,
  videoStreamInterval: null,
  audioStartTime: null, // Track when audio playback started
  videoFrameRate: 20, // FPS of lip-sync video
  videoAnimationFrame: null, // For requestAnimationFrame

  // Stream control
  currentGenerationId: null, // To track valid streams and prevent zombie playback
  aiSpeechStartTime: 0, // Timestamp when AI started speaking (to prevent immediate self-interrupt)

  // VAD state for auto-interrupt
  // VAD state for auto-interrupt
  vad: {
    consecutiveSpeechChunks: 0,  // Track consecutive chunks with speech
    lastInterruptTime: 0,  // Timestamp of last interrupt (for cooldown)
    isUserSpeaking: false,  // Currently detecting user speech
  },

  // Session
  sessionId: null // Stores the session ID for video multiplexing
};

// Expose state to window for avatarVideoClient to access
window.state = state;

// Initialize
async function init() {
  log('Initializing FirstWeek Interface...');
  log('Bot ID:', CONFIG.botId);

  // Show debug panel if enabled
  if (CONFIG.enableDebug && elements.debugPanel) {
    elements.debugPanel.classList.remove('hidden');
  }

  // Set up audio event listeners
  setupAudioListeners();

  // Initialize Audio Manager for Kokoro TTS
  await initAudioManager();

  // NOTE: initAvatarVideo() is now called AFTER we receive session_id from STT
  // This ensures we can pass session_id to the WebRTC connection for multiplexing

  // Listen for messages from parent (if embedded)
  window.addEventListener('message', handleParentMessage);

  // Add click handler to resume audio context (browser autoplay policy workaround)
  document.addEventListener('click', async () => {
    if (state.audioManager && state.audioManager.audioContext) {
      if (state.audioManager.audioContext.state === 'suspended') {
        log('Resuming AudioContext after user click...');
        await state.audioManager.audioContext.resume();
      }
    }
  }, { once: true });

  // Initialize STT WebSocket connection
  await connectToSTT();

  // Start capturing meeting audio (Recall.ai provides this)
  await captureMeetingAudio();

  log('Avatar Interface ready');
  updateStatus('Ready to assist', 'connected');
}

/**
 * Initialize Audio Manager for Kokoro TTS playback
 */
async function initAudioManager() {
  try {
    log('Initializing Audio Manager for Kokoro TTS...');

    state.audioManager = new AudioManager();
    await state.audioManager.init();

    // Set callbacks
    state.audioManager.onPlaying(() => {
      state.isSpeaking = true;
      state.aiSpeechStartTime = Date.now(); // Mark start time for interrupt protection
      console.log('[AUDIO] state.isSpeaking = true');
      showSpeakingIndicator();
      updateDebug('audio-playing', 'Yes');

      // CRITICAL: Set audio start time when audio actually starts playing
      // This is needed for audio-video synchronization
      if (!state.audioStartTime) {
        state.audioStartTime = performance.now();
        log(`🎵 Audio playback started at ${state.audioStartTime.toFixed(2)}ms`);
      }

      // Show video canvas when speaking
      if (state.videoRenderer) {
        state.videoRenderer.show();
        elements.avatar.classList.add('hidden');
      }
    });

    state.audioManager.onEnded(() => {
      // Ignore premature onEnded events during streaming
      if (!state.isAudioStreamComplete) {
        log('⚠️ Audio buffer empty but stream not complete - waiting for more chunks');
        return;
      }

      // Audio stream is complete and playback ended
      log('🔊 Audio playback ended');

      state.isSpeaking = false;
      hideSpeakingIndicator();
      updateDebug('audio-playing', 'No');
      updateStatus('Listening...');

      // Reset audio start time for next playback
      state.audioStartTime = null;

      // NOTE: Video loop will detect audio ended and handle idle transition
      // We don't do cleanup here to avoid race conditions
    });

    log('Audio Manager initialized successfully');
  } catch (error) {
    log('Failed to initialize Audio Manager:', error);
    updateStatus('Audio initialization failed');
  }
}

/**
 * Initialize Avatar Video components
 */
/**
 * Initialize Avatar Video components (WebRTC)
 */
async function initAvatarVideo() {
  try {
    log('Initializing Avatar Video components (WebRTC)...');

    // [NEW] WebRTC Migration: Create <video> element if not exists
    let videoEl = document.getElementById('avatar-webrtc-video');
    if (!videoEl) {
      videoEl = document.createElement('video');
      videoEl.id = 'avatar-webrtc-video';
      videoEl.autoplay = true;
      videoEl.playsInline = true;
      videoEl.muted = false; // Keep audio enabled for A/V sync
      videoEl.controls = false; // No native controls
      videoEl.disablePictureInPicture = true; // Prevent PiP latency
      videoEl.preload = 'none'; // Don't buffer ahead - lower latency

      // iOS-specific attributes for inline play
      videoEl.setAttribute('playsinline', ''); // iOS inline play
      videoEl.setAttribute('webkit-playsinline', ''); // Older iOS

      // Styling
      videoEl.style.width = '100%';
      videoEl.style.height = '100%';
      videoEl.style.objectFit = 'cover';
      videoEl.style.position = 'absolute';
      videoEl.style.top = '0';
      videoEl.style.left = '0';
      videoEl.style.zIndex = '10'; // Above static image

      // Find avatar container
      const container = document.querySelector('.avatar-container') || document.body;
      container.appendChild(videoEl);
      log('✅ Created WebRTC <video> element');
    }

    // Create WebRTC Client
    // Note: Use WebRTCClient instead of AvatarVideoClient
    state.avatarVideoClient = new WebRTCClient({
      wsUrl: CONFIG.avatarVideoUrl,
      avatarId: CONFIG.avatarExecutiveId, // 'anand_idle_v2'
      sessionId: state.sessionId, // [NEW] Pass session ID for multiplexing
      iceServers: CONFIG.iceServers
    });

    // Handle incoming tracks
    state.avatarVideoClient.onTrack((mediaStream) => {
      log('🎥 WebRTC Track received. Attaching to video element.');

      videoEl.srcObject = mediaStream;
      videoEl.play().catch(e => log('Autoplay failed:', e));

      // Hide static image
      elements.avatar.classList.add('hidden');
      if (elements.status) elements.status.style.opacity = '0';
    });

    // Set up status callbacks
    state.avatarVideoClient.onConnected(() => {
      log('✅ WebRTC Connected');
      updatePipelineStatus('avatar', 'ok');
    });

    state.avatarVideoClient.onDisconnected(() => {
      log('❌ WebRTC Disconnected');
      updatePipelineStatus('avatar', 'error');
    });

    state.avatarVideoClient.onError((error) => {
      log('❌ WebRTC Error:', error);
      updatePipelineStatus('avatar', 'error');
    });

    // Connect immediately (removed 1-second delay for lower latency)
    log('⏰ Connecting WebRTC...');
    await state.avatarVideoClient.connect();

  } catch (error) {
    log('Failed to initialize WebRTC:', error);
    updatePipelineStatus('avatar', 'error');
  }
}

/**
 * Connect to STT WebSocket service
 */
async function connectToSTT() {
  try {
    log('📞 Connecting to STT service:', CONFIG.sttWsUrl);
    log('Window location:', {
      protocol: window.location.protocol,
      host: window.location.host,
      href: window.location.href
    });
    updateStatus('Connecting to STT...', 'connecting');

    state.sttWs = new WebSocket(CONFIG.sttWsUrl);
    log('WebSocket object created, readyState:', state.sttWs.readyState, '(0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED)');

    state.sttWs.onopen = () => {
      log('✅ STT WebSocket OPENED! ReadyState:', state.sttWs.readyState);
      updateStatus('Connected', 'connected');
      updateDebug('connection', 'STT Connected');
      updatePipelineStatus('stt', 'ok');  // Show STT connected

      // Configure language
      log('Sending language config to STT...');
      state.sttWs.send(JSON.stringify({
        type: 'config',
        language: CONFIG.language
      }));
      log('Language config sent');
    };

    state.sttWs.onmessage = async (event) => {
      const data = JSON.parse(event.data);
      log('📨 STT message received, type:', data.type);

      if (data.type === 'transcript') {
        log('📝 Received transcript:', data.text);
        await handleTranscript(data.text);
      } else if (data.type === 'error') {
        log('❌ STT error:', data.message);
      } else if (data.type === 'session_init') {
        // [NEW] Capture Session ID and Initialize Video
        log('🆔 Received Session ID:', data.session_id);
        state.sessionId = data.session_id;

        // Now safe to initialize Video (WebRTC) with multiplexing capability
        if (!state.avatarVideoClient) {
          initAvatarVideo();
        }

      } else {
        log('Unknown STT message type:', data);
      }
    };

    state.sttWs.onerror = (error) => {
      log('❌ STT WebSocket ERROR:', error);
      log('Error details:', {
        type: error.type,
        target: error.target ? error.target.url : 'unknown'
      });
      updateStatus('STT connection error', 'disconnected');
    };

    state.sttWs.onclose = (event) => {
      log('❌ STT WebSocket CLOSED');
      log('Close details:', {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean
      });
      updateStatus('STT disconnected', 'disconnected');
      updateDebug('connection', 'Disconnected');

      // Reconnect after 3 seconds
      setTimeout(() => {
        log('🔄 Attempting to reconnect to STT...');
        connectToSTT();
      }, 3000);
    };

  } catch (error) {
    log('Failed to connect to STT:', error);
    updateStatus('STT connection failed', 'disconnected');
  }
}

/**
 * Capture meeting audio from Recall.ai MediaStream
 * Recall.ai automatically provides meeting audio to the webpage
 * 
 * IMPORTANT: Recall.ai injects meeting audio AFTER page load
 * We need to retry getUserMedia() with delays to wait for audio injection
 */
async function captureMeetingAudio(retryCount = 0) {
  const MAX_RETRIES = 5;
  const RETRY_DELAY = 2000; // 2 seconds

  try {
    log(`Requesting microphone access (attempt ${retryCount + 1}/${MAX_RETRIES + 1})...`);
    log('Note: Recall.ai injects meeting audio into getUserMedia() stream');
    updateStatus('Accessing meeting audio...');

    // Detect if we're running inside Recall.ai bot
    const isRecallBot = window.location.href.includes('bot_id=') ||
      navigator.userAgent.includes('Chrome') &&
      window.location.protocol === 'https:';

    log('Environment detection:', {
      isRecallBot: isRecallBot,
      url: window.location.href,
      userAgent: navigator.userAgent.substring(0, 100)
    });

    // Request audio access - Recall.ai auto-grants and injects meeting audio
    // For Recall.ai bots: This returns meeting audio, not user's microphone
    // For direct browser access: This returns user's microphone
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,  // Disable - Recall already processes
        noiseSuppression: false,  // Disable - Recall already processes  
        autoGainControl: false    // Disable - Recall already processes
      }
    });

    log('✅ getUserMedia() succeeded! Stream info:', {
      id: stream.id,
      active: stream.active,
      audioTracks: stream.getAudioTracks().length
    });

    const audioTracks = stream.getAudioTracks();
    if (audioTracks.length === 0) {
      throw new Error('No audio tracks in stream!');
    }

    const track = audioTracks[0];
    log('Audio track details:', {
      id: track.id,
      kind: track.kind,
      label: track.label,
      enabled: track.enabled,
      muted: track.muted,
      readyState: track.readyState,
      settings: track.getSettings()
    });

    // CRITICAL: Check if audio is actually flowing
    // For Recall bots, the label should indicate it's meeting audio
    const isLikelyMeetingAudio = track.label.toLowerCase().includes('meeting') ||
      track.label.toLowerCase().includes('recall') ||
      track.label === '' ||  // Recall might use empty label
      isRecallBot;

    log('Audio source analysis:', {
      trackLabel: track.label,
      isLikelyMeetingAudio: isLikelyMeetingAudio,
      shouldRetry: !isLikelyMeetingAudio && isRecallBot && retryCount < MAX_RETRIES
    });

    // If we're in Recall bot but got wrong audio source, retry
    if (!isLikelyMeetingAudio && isRecallBot && retryCount < MAX_RETRIES) {
      log(`⚠️ Audio source doesn't look like meeting audio, retrying in ${RETRY_DELAY}ms...`);

      // Stop current stream
      stream.getTracks().forEach(track => track.stop());

      // Wait and retry
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
      return captureMeetingAudio(retryCount + 1);
    }

    state.audioStream = stream;
    updatePipelineStatus('audio', 'ok');  // Show audio captured

    // Set up audio processing
    await setupAudioProcessing(stream);

    state.isListening = true;
    updateStatus('Listening to meeting...', 'connected');

    log('✅ Meeting audio capture successful!');

  } catch (error) {
    log('❌ Failed to capture meeting audio:', error.message);
    log('Error details:', {
      name: error.name,
      message: error.message,
      stack: error.stack ? error.stack.substring(0, 200) : 'none'
    });

    // Retry if not max retries
    if (retryCount < MAX_RETRIES) {
      log(`Retrying in ${RETRY_DELAY}ms (attempt ${retryCount + 2}/${MAX_RETRIES + 1})...`);
      updateStatus(`Retrying audio access (${retryCount + 2}/${MAX_RETRIES + 1})...`);

      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
      return captureMeetingAudio(retryCount + 1);
    }

    // Max retries exceeded
    updateStatus('Microphone access failed after retries', 'disconnected');
    log('⚠️ IMPORTANT: If this is a Recall.ai bot, ensure:');
    log('  1. Bot created with in_meeting_audio.enabled = true');
    log('  2. Recall.ai has time to inject audio (takes ~2-5 seconds)');
    log('  3. Check Recall.ai bot logs for audio injection errors');
  }
}

/**
 * Set up audio processing pipeline using MediaStreamTrackProcessor
 * Required by Recall.ai for 4-core bots - DO NOT CHANGE
 * https://docs.recall.ai/docs/stream-media
 */
async function setupAudioProcessing(stream) {
  const targetSampleRate = CONFIG.sampleRate; // 16000 Hz for STT

  log('Audio processing setup with MediaStreamTrackProcessor (Required by Recall.ai)');

  // Get the audio track from the stream
  const meetingAudioTrack = stream.getAudioTracks()[0];

  if (!meetingAudioTrack) {
    log('Error: No audio track found in stream');
    return;
  }

  // Check if MediaStreamTrackProcessor is supported
  if (typeof MediaStreamTrackProcessor === 'undefined') {
    log('MediaStreamTrackProcessor not supported, falling back to ScriptProcessor');
    await setupAudioProcessingLegacy(stream);
    return;
  }

  // ENHANCED RESAMPLING:
  // If source audio is not 16kHz, use Web Audio API to resample content natively.
  // This avoids the low-quality linear interpolation in processAudioData().
  let trackToProcess = meetingAudioTrack;

  // Check settings - if sampleRate matches target, we're good
  const settings = meetingAudioTrack.getSettings();
  const sourceRate = settings.sampleRate;

  // DETECT FIREFOX: Firefox has known issues with MediaStreamDestination or strict autoplay policies
  // independent of getUserMedia. Since Firefox worked fine with manual resampling (Step 0), 
  // we skip this robust pipeline for Firefox to restore the working state.
  const isFirefox = navigator.userAgent.toLowerCase().includes('firefox');

  if (!isFirefox && (!sourceRate || sourceRate !== targetSampleRate)) {
    log(`⚠️ Source audio is ${sourceRate || 'unknown'}Hz, resampling to ${targetSampleRate}Hz via Web Audio API`);

    try {
      // 1. Create AudioContext at target rate (16kHz)
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioContextClass({
        sampleRate: targetSampleRate,
        latencyHint: 'interactive'
      });

      // Ensure context is running (fixes Chrome autoplay policy issues)
      if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
      }

      // 2. Create source from original stream
      const source = audioCtx.createMediaStreamSource(stream);

      // 3. Create destination stream
      const dest = audioCtx.createMediaStreamDestination();
      dest.channelCount = 1; // Force mono mixdown

      // 4. Connect graph: Source -> Destination
      source.connect(dest);

      // 5. Use the new resampled track
      trackToProcess = dest.stream.getAudioTracks()[0];

      // Keep context alive in state to prevent garbage collection
      state.resamplingAudioContext = audioCtx;

      log('✅ Native resampling pipeline established');
    } catch (err) {
      log('❌ Failed to set up native resampling, falling back to manual:', err);
      // Fall through to use original track (manual resampling in processAudioData will trigger)
    }
  }

  // Create track processor for the audio track
  const trackProcessor = new MediaStreamTrackProcessor({ track: trackToProcess });
  const trackReader = trackProcessor.readable.getReader();

  log('MediaStreamTrackProcessor initialized');

  // Process audio frames in a loop
  let frameCount = 0;
  (async () => {
    try {
      while (true) {
        const { value, done } = await trackReader.read();

        if (done) {
          log('Audio track ended');
          break;
        }

        // value is an AudioData object
        const audioData = value;
        frameCount++;

        // Log every 50 frames (roughly every 1 second)
        if (frameCount % 50 === 0) {
          log(`Audio frames received: ${frameCount}, current frame:`, {
            sampleRate: audioData.sampleRate,
            numberOfFrames: audioData.numberOfFrames,
            numberOfChannels: audioData.numberOfChannels,
            duration: audioData.duration
          });
        }

        if (!state.sttWs || state.sttWs.readyState !== WebSocket.OPEN) {
          if (frameCount % 50 === 0) {
            log('⚠️ STT WebSocket not ready, frame dropped. State:', state.sttWs ? state.sttWs.readyState : 'null', '(0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED)');
          }
          audioData.close(); // Important: close AudioData to free resources
          continue;
        }

        // Extract audio samples from AudioData
        await processAudioData(audioData, targetSampleRate);

        // Close the AudioData object to free resources
        audioData.close();
      }
    } catch (error) {
      log('Error in audio processing loop:', error);
      log('Error stack:', error.stack);
    }
  })();

  log('Audio processing pipeline established');
}

// Counter for periodic logging
let audioChunkCount = 0;
let firstAudioMessageLogged = false;

// OPTIMIZED: Ring buffer for accumulating audio chunks
// Uses pre-allocated TypedArray instead of Array.push() for O(1) performance
// VAD requires minimum 30ms (480 samples at 16kHz) to work
const TARGET_CHUNK_SIZE = 480;  // 30ms at 16kHz (minimum for VAD)
const AUDIO_BUFFER_SIZE = TARGET_CHUNK_SIZE * 4; // 4x buffer for safety
const audioRingBuffer = new Int16Array(AUDIO_BUFFER_SIZE);
let audioBufferWriteIndex = 0;
let audioBufferReadIndex = 0;
let audioBufferCount = 0; // Number of samples in buffer

/**
 * Handle Voice Activity Detection (VAD) for auto-interrupt
 * Detects when user speaks while AI is speaking and interrupts AI
 */
function handleVoiceActivityDetection(rms) {
  if (!CONFIG.vad.enabled) return;

  const now = Date.now();
  const cooldownElapsed = now - state.vad.lastInterruptTime > CONFIG.vad.cooldownMs;

  // Check if user is speaking (RMS above threshold)
  const isUserSpeakingNow = rms > CONFIG.vad.rmsThreshold;



  if (isUserSpeakingNow) {
    state.vad.consecutiveSpeechChunks++;
  } else {
    // Reset counter if silence detected
    state.vad.consecutiveSpeechChunks = 0;
    state.vad.isUserSpeaking = false;
  }

  // If we detect consecutive speech chunks, user is speaking
  if (state.vad.consecutiveSpeechChunks >= CONFIG.vad.consecutiveChunksRequired) {
    state.vad.isUserSpeaking = true;
    state.vad.lastSpeechTime = now; // Track when speech was last detected

    // If AI is speaking AND user starts speaking AND cooldown elapsed → INTERRUPT!
    // GRACE PERIOD: Also apply 1.5s grace period here to prevent echo from triggering VAD
    const isGracePeriod = Date.now() - (state.aiSpeechStartTime || 0) < 1500;

    if (state.isSpeaking && cooldownElapsed && !isGracePeriod) {
      interruptAIResponse();
      state.vad.lastInterruptTime = now;
      state.vad.consecutiveSpeechChunks = 0; // Reset after interrupt
    }
  }
}

/**
 * Interrupt AI audio response immediately
 * Called when user starts speaking during AI's response
 */
function interruptAIResponse() {
  log('⏹️ Interrupting AI response...');

  // Set force stop flag - this will be checked in the video loop
  state.forceStopVideo = true;

  // Invalidate current stream generation to stop zombie chunks
  state.currentGenerationId = Date.now();

  // Stop audio playback immediately
  if (state.audioManager) {
    state.audioManager.stop();
  }

  // Stop video streaming
  if (state.videoStreamInterval) {
    clearInterval(state.videoStreamInterval);
    state.videoStreamInterval = null;
  }

  // Cancel animation frame
  if (state.videoAnimationFrame) {
    cancelAnimationFrame(state.videoAnimationFrame);
    state.videoAnimationFrame = null;
  }

  // Clear all buffers
  state.audioQueue = [];
  state.audioBuffer = [];
  state.lipSyncVideoBuffer = [];
  state.isReceivingLipSync = false;
  state.lipSyncComplete = false;
  state.lipSyncPlaybackStarted = false;
  state.audioStartTime = null;
  state.isAudioStreamComplete = false;

  // Stop lip-sync mode and return to idle via stopSpeaking
  if (state.avatarVideoClient && state.avatarVideoClient.isConnected) {
    state.avatarVideoClient.stopSpeaking();
  }

  // Update state
  state.isSpeaking = false;
  hideSpeakingIndicator();

  // Update UI
  updateStatus('Listening...');
}

/**
 * Process AudioData object and send to STT
 */
async function processAudioData(audioData, targetSampleRate) {
  try {
    audioChunkCount++;
    const sourceSampleRate = audioData.sampleRate;
    const numberOfChannels = audioData.numberOfChannels;
    const numberOfFrames = audioData.numberOfFrames;

    // Allocate buffer for audio samples
    const bufferSize = numberOfFrames * numberOfChannels;
    const float32Buffer = new Float32Array(bufferSize);

    // Copy audio data to buffer
    audioData.copyTo(float32Buffer, {
      planeIndex: 0,  // First channel (mono or left channel)
      format: 'f32-planar'
    });

    // OPTIMIZED: Only calculate RMS when VAD is enabled OR for periodic logging
    // This saves ~0.2ms per audio frame when not needed
    const shouldCalculateRMS = CONFIG.vad.enabled || (audioChunkCount % 100 === 0);
    let rms = 0;

    if (shouldCalculateRMS) {
      // Calculate audio level (RMS) with loop unrolling for performance
      let sum = 0;
      const len = float32Buffer.length;
      const len4 = len - (len % 4);

      // Process 4 samples at a time
      for (let i = 0; i < len4; i += 4) {
        sum += float32Buffer[i] * float32Buffer[i];
        sum += float32Buffer[i + 1] * float32Buffer[i + 1];
        sum += float32Buffer[i + 2] * float32Buffer[i + 2];
        sum += float32Buffer[i + 3] * float32Buffer[i + 3];
      }
      // Handle remaining samples
      for (let i = len4; i < len; i++) {
        sum += float32Buffer[i] * float32Buffer[i];
      }
      rms = Math.sqrt(sum / len);

      // VAD: Auto-interrupt if user speaks while AI is speaking
      if (CONFIG.vad.enabled) {
        handleVoiceActivityDetection(rms);
      }
    }

    // Only log every 100th chunk to avoid spam
    if (audioChunkCount % 100 === 0 && shouldCalculateRMS) {
      const dbLevel = 20 * Math.log10(rms || 0.0001); // Avoid log(0)
      log('📊 Audio #' + audioChunkCount + ' - RMS: ' + rms.toFixed(4) + ', dB: ' + dbLevel.toFixed(1) + ', Active: ' + (rms > 0.001));
      updatePipelineStatus('level', 'value', dbLevel.toFixed(0) + 'dB');
    }

    // OPTIMIZED: Stereo to mono conversion with loop unrolling
    let monoBuffer = float32Buffer;
    if (numberOfChannels === 2) {
      monoBuffer = new Float32Array(numberOfFrames);
      const len4 = numberOfFrames - (numberOfFrames % 4);
      // Process 4 samples at a time
      for (let i = 0; i < len4; i += 4) {
        monoBuffer[i] = (float32Buffer[i * 2] + float32Buffer[i * 2 + 1]) * 0.5;
        monoBuffer[i + 1] = (float32Buffer[(i + 1) * 2] + float32Buffer[(i + 1) * 2 + 1]) * 0.5;
        monoBuffer[i + 2] = (float32Buffer[(i + 2) * 2] + float32Buffer[(i + 2) * 2 + 1]) * 0.5;
        monoBuffer[i + 3] = (float32Buffer[(i + 3) * 2] + float32Buffer[(i + 3) * 2 + 1]) * 0.5;
      }
      for (let i = len4; i < numberOfFrames; i++) {
        monoBuffer[i] = (float32Buffer[i * 2] + float32Buffer[i * 2 + 1]) * 0.5;
      }
    } else if (numberOfChannels === 1) {
      // Mono: just use first 'numberOfFrames' samples
      monoBuffer = float32Buffer.subarray(0, numberOfFrames); // subarray is O(1) vs slice O(n)
    }

    // Resample to 16kHz if needed
    let resampledData = monoBuffer;
    if (sourceSampleRate !== targetSampleRate) {
      resampledData = resampleAudio(monoBuffer, sourceSampleRate, targetSampleRate);
    }

    // OPTIMIZED: Convert to int16 with loop unrolling (STT expects int16 PCM)
    const resampledLen = resampledData.length;
    const int16Data = new Int16Array(resampledLen);
    const len4 = resampledLen - (resampledLen % 4);

    for (let i = 0; i < len4; i += 4) {
      let s0 = resampledData[i], s1 = resampledData[i + 1], s2 = resampledData[i + 2], s3 = resampledData[i + 3];
      s0 = s0 < -1 ? -1 : (s0 > 1 ? 1 : s0);
      s1 = s1 < -1 ? -1 : (s1 > 1 ? 1 : s1);
      s2 = s2 < -1 ? -1 : (s2 > 1 ? 1 : s2);
      s3 = s3 < -1 ? -1 : (s3 > 1 ? 1 : s3);
      int16Data[i] = s0 < 0 ? s0 * 0x8000 : s0 * 0x7FFF;
      int16Data[i + 1] = s1 < 0 ? s1 * 0x8000 : s1 * 0x7FFF;
      int16Data[i + 2] = s2 < 0 ? s2 * 0x8000 : s2 * 0x7FFF;
      int16Data[i + 3] = s3 < 0 ? s3 * 0x8000 : s3 * 0x7FFF;
    }
    for (let i = len4; i < resampledLen; i++) {
      const s = Math.max(-1, Math.min(1, resampledData[i]));
      int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    // OPTIMIZED: Ring buffer for audio accumulation (O(1) instead of O(n) with push/splice)
    // Write samples to ring buffer
    for (let i = 0; i < int16Data.length; i++) {
      audioRingBuffer[audioBufferWriteIndex] = int16Data[i];
      audioBufferWriteIndex = (audioBufferWriteIndex + 1) % AUDIO_BUFFER_SIZE;
      audioBufferCount++;
    }

    // Only send when we have enough samples for VAD
    if (audioBufferCount >= TARGET_CHUNK_SIZE) {
      // Extract exactly TARGET_CHUNK_SIZE samples from ring buffer
      const chunkToSend = new Int16Array(TARGET_CHUNK_SIZE);
      for (let i = 0; i < TARGET_CHUNK_SIZE; i++) {
        chunkToSend[i] = audioRingBuffer[audioBufferReadIndex];
        audioBufferReadIndex = (audioBufferReadIndex + 1) % AUDIO_BUFFER_SIZE;
      }
      audioBufferCount -= TARGET_CHUNK_SIZE;

      // Encode to base64 and send to STT
      const base64Audio = arrayBufferToBase64(chunkToSend.buffer);

      // Check WebSocket state before sending
      if (state.sttWs.readyState !== WebSocket.OPEN) {
        if (audioChunkCount % 50 === 0) {
          log('❌ WebSocket not OPEN, state:', state.sttWs.readyState);
        }
        return;
      }

      try {
        const message = JSON.stringify({
          type: 'audio',
          data: base64Audio
        });

        audioChunkCount++;

        // ONE-TIME: Log the first audio message details
        if (!firstAudioMessageLogged) {
          log('🔍 FIRST BUFFERED AUDIO MESSAGE:', {
            messageLength: message.length,
            base64Length: base64Audio.length,
            int16Samples: chunkToSend.length,
            targetSamples: TARGET_CHUNK_SIZE,
            wsReadyState: state.sttWs.readyState
          });
          firstAudioMessageLogged = true;
        }

        state.sttWs.send(message);

        // Log every 50th send
        if (audioChunkCount % 50 === 0) {
          log('✅ Sent #' + audioChunkCount + ': ' + chunkToSend.length + ' samples (buffered)');
        }

        // DIAGNOSTIC: Log first successful send  
        if (audioChunkCount === 1) {
          log('🎯 FIRST 480-SAMPLE CHUNK SENT! VAD should now work.');
        }
      } catch (error) {
        log('❌ Error sending buffered audio:', error.message);
      }
    }
  } catch (error) {
    log('Error processing audio data:', error);
    log('Error stack:', error.stack);
  }
}

/**
 * ScriptProcessor audio processing (SAME as working main frontend)
 * Matches useVoiceInput.js lines 150-183 exactly
 */
let legacyChunkCount = 0;
let legacyFirstAudioLogged = false;

async function setupAudioProcessingLegacy(stream) {
  // Explicitly request 16kHz context to handle resampling natively
  state.audioContext = new (window.AudioContext || window.webkitAudioContext)();

  const sourceSampleRate = state.audioContext.sampleRate;
  const targetSampleRate = CONFIG.sampleRate;  // 16000 Hz

  log(`🎙️  Audio: ${sourceSampleRate}Hz → ${targetSampleRate}Hz (ratio: ${(targetSampleRate / sourceSampleRate).toFixed(3)})`);

  const source = state.audioContext.createMediaStreamSource(stream);
  const bufferSize = 4096;  // Match working frontend

  const processor = state.audioContext.createScriptProcessor(bufferSize, 1, 1);

  processor.onaudioprocess = (e) => {
    if (!state.sttWs || state.sttWs.readyState !== WebSocket.OPEN) {
      return;
    }

    legacyChunkCount++;
    const inputData = e.inputBuffer.getChannelData(0);

    // Resample using same method as working frontend (linear interpolation)
    let resampledData = inputData;
    if (sourceSampleRate !== targetSampleRate) {
      const outputLength = Math.floor(inputData.length * (targetSampleRate / sourceSampleRate));
      resampledData = new Float32Array(outputLength);

      for (let i = 0; i < outputLength; i++) {
        const srcIndex = i / (targetSampleRate / sourceSampleRate);
        const srcIndexFloor = Math.floor(srcIndex);
        const srcIndexCeil = Math.min(srcIndexFloor + 1, inputData.length - 1);
        const fraction = srcIndex - srcIndexFloor;

        // Linear interpolation (same as useVoiceInput.js lines 169-176)
        resampledData[i] = inputData[srcIndexFloor] * (1 - fraction) +
          inputData[srcIndexCeil] * fraction;
      }
    }

    // Convert to Int16 (same as useVoiceInput.js lines 102-106)
    const int16Data = new Int16Array(resampledData.length);
    for (let i = 0; i < resampledData.length; i++) {
      const s = Math.max(-1, Math.min(1, resampledData[i]));
      int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    // Encode to base64 (same as useVoiceInput.js lines 109-114)
    const base64Audio = arrayBufferToBase64(int16Data.buffer);

    // ONE-TIME: Log first audio message
    if (!legacyFirstAudioLogged) {
      log('🔍 FIRST AUDIO (ScriptProcessor):', {
        chunk: legacyChunkCount,
        inputSamples: inputData.length,
        resampledSamples: resampledData.length,
        int16Samples: int16Data.length,
        base64Length: base64Audio.length,
        wsState: state.sttWs.readyState
      });
      legacyFirstAudioLogged = true;
    }

    try {
      state.sttWs.send(JSON.stringify({
        type: 'audio',
        data: base64Audio
      }));

      // Log every 100th chunk
      if (legacyChunkCount % 100 === 0) {
        log(`✅  Sent chunk #${legacyChunkCount} (${int16Data.length} samples)`);
      }
    } catch (error) {
      log('❌ Error sending audio to STT:', error);
    }
  };

  source.connect(processor);
  processor.connect(state.audioContext.destination);

  log('✅ ScriptProcessor audio pipeline established (MATCHES working frontend)');
}

/**
 * Handle transcript from STT service
 * Calls RAG API streaming endpoint directly for text + audio
 */
async function handleTranscript(transcript) {
  if (!transcript || transcript.trim().length === 0) {
    return;
  }

  log('Processing transcript:', transcript);

  // 1. Check if this transcript is likely the cause of a recent interrupt (VAD triggered first)
  const timeSinceInterrupt = Date.now() - state.vad.lastInterruptTime;
  if (timeSinceInterrupt < 3000) { // 3 seconds window
    if (transcript.length < 20) {
      log(`Ignoring short transcript "${transcript}" immediately after VAD interrupt`);
      return;
    }
  }

  // 2. Check if we are currently speaking (STT triggered before VAD or VAD disabled)
  if (state.isSpeaking || (state.audioManager && state.audioManager.isPlaying)) {

    // GRACE PERIOD: Ignore interrupts for the first 1.5 seconds of AI speech
    // This prevents trailing STT from the user's query from triggering a self-interrupt
    if (Date.now() - state.aiSpeechStartTime < 1500) {
      log(`Ignoring transcript "${transcript}" - inside AI speech grace period`);
      return;
    }

    // If it's a short command (likely just "stop", "wait", etc.), treat as pure interrupt
    if (transcript.length < 20) {
      // NOISE FILTER: Only interrupt if VAD also detected speech recently
      // This prevents STT hallucinations from background noise triggering interrupts
      const timeSinceSpeech = Date.now() - (state.vad.lastSpeechTime || 0);
      if (CONFIG.vad.enabled && timeSinceSpeech > 1000) {
        log(`Ignoring short transcript "${transcript}" (noise) - VAD silent`);
        return;
      }

      log(`Short command "${transcript}" received while speaking - INTERRUPTING and IGNORING`);
      interruptAIResponse();
      return; // CRITICAL: Return here to prevent processing "stop" as a new query
    }

    // If it's a long query, user probably said "Stop and tell me X", so we interrupt and process
    log('New query received while speaking - INTERRUPTING and PROCESSING');
    interruptAIResponse();
  }

  updateStatus('Processing: "' + transcript.substring(0, 50) + '..."');

  try {
    // Call RAG API streaming endpoint with TTS enabled
    const response = await fetch(
      `${CONFIG.ragApiUrl}/api/v1/langgraph/chat/stream-audio`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify({
          query: transcript,
          profile_id: 'sample_profile', // TODO: Make configurable
          user_id: `meeting_bot_${CONFIG.botId}`,
          user_role: 'executive',
          top_k: 10,
          min_score: 0.2,
          language: CONFIG.language, // Use configured language
          enable_video_push: true, // Enable backend-to-backend audio push for lip-sync
          session_id: state.sessionId // [NEW] Link frontend session to backend processing
        })
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    log('RAG streaming started');
    updateStatus('Generating response...');

    // Initialize streaming session
    initLipSyncSession();

    // Set new generation ID for this stream
    const streamGenerationId = Date.now();
    state.currentGenerationId = streamGenerationId;

    // Read SSE stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let currentEventType = null;
    let fullResponse = '';
    let audioFrameBatch = [];
    const BATCH_SIZE = 5; // Smaller batch size for lower latency

    while (true) {
      // CHECK FOR INTERRUPT: If generation ID changed, stop processing
      if (state.currentGenerationId !== streamGenerationId) {
        log('Stream interrupted - aborting processing');
        await reader.cancel();
        break;
      }

      const { done, value } = await reader.read();

      if (done) {
        log('RAG streaming complete');
        break;
      }

      // Decode chunk and add to buffer
      const decodedChunk = decoder.decode(value, { stream: true });
      buffer += decodedChunk;

      // Process complete lines from buffer
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          // Track current event type
          currentEventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();

          if (data === '[DONE]') {
            log('Stream end marker received');
            break;
          }

          if (data) {
            try {
              const parsed = JSON.parse(data);

              // Handle different event types
              if (currentEventType === 'token') {
                // Text token from LLM
                fullResponse += parsed.token || '';
                // Could display text here if needed
              } else if (currentEventType === 'audio_frame') {
                // Audio frame from Kokoro TTS
                audioFrameBatch.push(parsed);

                // Process batch
                if (audioFrameBatch.length >= BATCH_SIZE) {
                  // Extra check: stop if interrupted during batch accumulation
                  if (state.currentGenerationId !== streamGenerationId) break;

                  await streamAudioToAvatar(audioFrameBatch);
                  audioFrameBatch = [];
                }
              } else if (currentEventType === 'complete') {
                log('Response generation complete');
                log('Full response:', fullResponse);
              } else if (currentEventType === 'error') {
                log('Stream error:', parsed);
                updateStatus('Error generating response');
              }
            } catch (parseError) {
              log('Failed to parse SSE data:', parseError);
            }
          }
        }
      }
    }

    // Process any remaining audio frames
    if (audioFrameBatch.length > 0) {
      await streamAudioToAvatar(audioFrameBatch);
    }

    log('Transcript processing complete');

    // Signal that all audio chunks have been received
    state.isAudioStreamComplete = true;

    // REMOVED: Do NOT set isReceivingLipSync = false here.
    // We must wait for the Avatar Service to finish sending video frames.
    // state.isReceivingLipSync = false; 

  } catch (error) {
    log('Error processing transcript:', error);
    updateStatus('Error: ' + error.message);
  }
}

/**
 * Initialize a new lip-sync streaming session
 */
function initLipSyncSession() {
  log('🎬 Initializing lip-sync streaming session');

  // Reset state
  state.lipSyncVideoBuffer = [];
  state.isReceivingLipSync = true;
  state.lipSyncComplete = false;
  state.lipSyncPlaybackStarted = false;
  state.pendingAudioChunks = []; // Buffer for audio before video starts
  state.isAudioStreamComplete = false; // Reset stream completion flag

  // Set up callback for when lip-sync frames arrive
  if (state.avatarVideoClient) {
    state.avatarVideoClient.onLipSyncFrame(async (frameData) => {
      // Add frame to buffer immediately
      state.lipSyncVideoBuffer.push(frameData);

      // BUFFERING STRATEGY:
      // Wait for a minimum number of video frames before starting playback.
      // This compensates for video generation latency (inference time).
      // Audio is buffered in state.pendingAudioChunks until this threshold is met.
      const MIN_BUFFER_FRAMES = 10; // ~333ms buffer at 30fps

      if (!state.lipSyncPlaybackStarted && state.lipSyncVideoBuffer.length >= MIN_BUFFER_FRAMES) {
        state.lipSyncPlaybackStarted = true;
        log(`🎬 Buffered ${state.lipSyncVideoBuffer.length} frames - starting synchronized playback!`);
        updateStatus('Speaking...');

        // Start video streaming loop immediately
        startVideoStreaming();

        // Flush pending audio chunks to audio manager (non-blocking)
        if (state.pendingAudioChunks.length > 0) {
          log(`🔊 Flushing ${state.pendingAudioChunks.length} pending audio chunks`);
          state.audioManager.addChunks([...state.pendingAudioChunks]);
          state.pendingAudioChunks = [];
        }
      }
    });

    // Set up callback for when lip-sync generation is complete
    state.avatarVideoClient.onLipSyncComplete(() => {
      log('✅ Avatar Service finished generating video frames');
      state.isReceivingLipSync = false;

      // Fallback: If playback hasn't started yet (e.g. short response < buffer threshold), start it now
      if (!state.lipSyncPlaybackStarted && state.lipSyncVideoBuffer.length > 0) {
        log('⚠️ Stream complete but buffer threshold not met - starting playback anyway');
        state.lipSyncPlaybackStarted = true;
        updateStatus('Speaking...');
        startVideoStreaming();

        if (state.pendingAudioChunks.length > 0) {
          state.audioManager.addChunks([...state.pendingAudioChunks]);
          state.pendingAudioChunks = [];
        }
      }
    });

    // Notify avatar client to start lip-sync mode
    state.avatarVideoClient.startLipSyncMode();
  }
}

/**
 * Stream audio batch to avatar service and audio manager
 * @param {Array} frames - Array of audio frame objects
 */
async function streamAudioToAvatar(frames) {
  if (!frames || frames.length === 0) return;

  // Extract base64 chunks
  const base64Chunks = frames.map(f => f.data).filter(d => d);
  if (base64Chunks.length === 0) return;

  // 1. Send to Avatar Service for lip-sync generation
  if (state.avatarVideoClient && state.avatarVideoClient.isConnected) {
    // Decode to Int16Array for avatar service
    const audioArrays = [];
    for (const base64Chunk of base64Chunks) {
      const binaryString = atob(base64Chunk);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      audioArrays.push(new Int16Array(bytes.buffer));
    }

    // Concatenate
    const totalLength = audioArrays.reduce((sum, arr) => sum + arr.length, 0);
    const combinedAudio = new Int16Array(totalLength);
    let offset = 0;
    for (const arr of audioArrays) {
      combinedAudio.set(arr, offset);
      offset += arr.length;
    }

    // Send to worker
    state.avatarVideoClient.sendTTSAudio(combinedAudio, 24000);
  }

  // 2. Handle Audio Playback
  if (state.audioManager) {
    if (state.lipSyncPlaybackStarted) {
      // If playback already started, add to audio manager immediately
      await state.audioManager.addChunks(base64Chunks);
    } else {
      // Otherwise, buffer until first video frame arrives
      if (!state.pendingAudioChunks) state.pendingAudioChunks = [];
      state.pendingAudioChunks.push(...base64Chunks);
    }
  }
}

/**
 * Play audio without video (fallback)
 */
async function playBufferedAudio() {
  if (!state.audioBuffer || state.audioBuffer.length === 0) {
    return;
  }

  log('🔊 Playing audio without lip-sync video');

  for (const chunk of state.audioBuffer) {
    await state.audioManager.addChunk(chunk);
  }

  state.audioBuffer = [];
}

/**
 * Start audio playback immediately
 * @param {Array} audioChunks - Base64 audio chunks
 */
async function startAudioPlayback(audioChunks) {
  log(`🔊 Starting audio playback: ${audioChunks.length} chunks`);

  // Play all audio chunks
  for (const chunk of audioChunks) {
    await state.audioManager.addChunk(chunk);
  }

  log('✅ Audio playback scheduled');

  // REMOVED: cleanupAfterPlayback()
  // We rely on state.audioManager.onEnded() to trigger cleanup
}

/**
 * Start streaming video frames at natural pace
 * SIMPLE APPROACH: Video runs at ~30fps independently of audio
 * Audio and video start together but run at their own rates
 */
function startVideoStreaming() {
  // Prevent multiple loops
  if (state.videoAnimationFrame) {
    cancelAnimationFrame(state.videoAnimationFrame);
    state.videoAnimationFrame = null;
  }

  const FRAME_INTERVAL_MS = 1000 / state.videoFrameRate; // ~50ms per frame (20 FPS)
  let lastRenderedFrame = -1;
  let lastRenderTime = 0;
  let frameCounter = 0; // For periodic logging only
  let waitCounter = 0; // Track how long we wait for audio

  function renderVideoFrame(timestamp) {
    // FORCE STOP: Check if interrupted
    if (state.forceStopVideo) {
      state.videoAnimationFrame = null;
      state.forceStopVideo = false; // Reset flag
      return;
    }

    // Quick check - stop if audio ended
    // CRITICAL FIX: Check if audioManager is processing or has pending decodes before stopping
    // This prevents stopping during buffering gaps (decoding delay)
    const isAudioProcessing = state.audioManager && (state.audioManager.isProcessing || state.audioManager.decodeQueue.length > 0 || state.audioManager.pendingDecodes.size > 0);

    if (state.isAudioStreamComplete && state.audioManager && !state.audioManager.isPlaying && !isAudioProcessing) {
      // Stop the lip-sync video loop
      state.videoAnimationFrame = null;
      state.lipSyncVideoBuffer = [];
      state.isReceivingLipSync = false;
      state.lipSyncPlaybackStarted = false;

      // Send stop_speaking to server - this will stop video and return to idle
      if (state.avatarVideoClient && state.avatarVideoClient.isConnected) {
        state.avatarVideoClient.stopSpeaking();
      }
      return;
    }

    // Wait for audio to start
    if (!state.audioManager || !state.audioManager.playbackStartTime) {
      // CRITICAL FIX: If we are no longer in lip-sync mode (e.g. interrupted), STOP waiting!
      if (!state.isReceivingLipSync && !state.lipSyncPlaybackStarted) {
        state.videoAnimationFrame = null;
        return;
      }

      state.videoAnimationFrame = requestAnimationFrame(renderVideoFrame);
      return;
    }

    // Render next frame if enough time passed
    if (timestamp - lastRenderTime >= FRAME_INTERVAL_MS || lastRenderTime === 0) {
      const nextFrame = lastRenderedFrame + 1;

      if (nextFrame < state.lipSyncVideoBuffer.length) {
        const frame = state.lipSyncVideoBuffer[nextFrame];

        if (state.videoRenderer && frame) {
          state.videoRenderer.renderFrame(frame);
          lastRenderedFrame = nextFrame;
          lastRenderTime = timestamp;

          // Original frameCounter logging removed as it's replaced by the new periodic logging above
        }
      } else {
        // Buffer underrun or waiting for more frames
        // console.log('[VIDEO] Waiting for more frames...');
      }
    }

    // Continue loop
    state.videoAnimationFrame = requestAnimationFrame(renderVideoFrame);
  }

  state.videoAnimationFrame = requestAnimationFrame(renderVideoFrame);
}

/**
 * Cleanup after playback completes
 */
async function cleanupAfterPlayback() {
  log('🧹 Cleaning up after playback...');

  // Wait a bit for video to finish
  await new Promise(resolve => setTimeout(resolve, 500));

  // Stop video streaming if still running
  if (state.videoStreamInterval) {
    clearInterval(state.videoStreamInterval);
    state.videoStreamInterval = null;
  }

  // Cancel animation frame if running
  if (state.videoAnimationFrame) {
    cancelAnimationFrame(state.videoAnimationFrame);
    state.videoAnimationFrame = null;
  }

  // Clear buffers and reset state
  state.audioBuffer = [];
  state.lipSyncVideoBuffer = [];
  state.isReceivingLipSync = false;
  state.lipSyncComplete = false;
  state.lipSyncPlaybackStarted = false;
  state.audioStartTime = null;

  // Stop lip-sync mode in avatar client
  if (state.avatarVideoClient) {
    state.avatarVideoClient.stopLipSyncMode();
  }

  log('✅ Playback complete - returning to idle');
  updateStatus('Listening...');

  // Return to idle animation
  if (state.avatarVideoClient) {
    state.avatarVideoClient.requestIdle();
    log('🔄 Requested return to idle animation');
  }
}

/**
 * Set up audio element event listeners
 */
function setupAudioListeners() {
  if (!elements.audio) return;

  elements.audio.addEventListener('play', () => {
    log('Audio started playing');
    state.isSpeaking = true;
    showSpeakingIndicator();
    updateDebug('audio-playing', 'Yes');
  });

  elements.audio.addEventListener('ended', () => {
    log('Audio finished playing');
    state.isSpeaking = false;
    hideSpeakingIndicator();
    updateDebug('audio-playing', 'No');
    updateStatus('Listening...');

    // Play next in queue if available
    playNextInQueue();
  });

  elements.audio.addEventListener('error', (e) => {
    log('Audio error:', e);
    state.isSpeaking = false;
    hideSpeakingIndicator();
    updateDebug('audio-playing', 'Error');
    updateStatus('Audio error');
  });

  elements.audio.addEventListener('canplay', () => {
    log('Audio can play');
  });
}

/**
 * Handle messages from parent window (for iframe embedding)
 */
function handleParentMessage(event) {
  const { type, data } = event.data;

  switch (type) {
    case 'PLAY_AUDIO':
      playAudio(data.audioUrl);
      break;

    case 'UPDATE_STATUS':
      updateStatus(data.status);
      break;

    case 'SET_AVATAR':
      setAvatarImage(data.imageUrl);
      break;
  }
}

/**
 * Play audio from URL
 */
function playAudio(audioUrl) {
  if (!audioUrl) {
    log('No audio URL provided');
    return;
  }

  log('Playing audio:', audioUrl);

  state.currentAudioUrl = audioUrl;
  updateDebug('last-audio', new Date().toLocaleTimeString());

  if (!elements.audio) return;

  // Set audio source
  elements.audio.src = audioUrl;

  // Auto-play with small delay to ensure loading
  setTimeout(() => {
    elements.audio.play()
      .then(() => {
        log('Audio playback started successfully');
      })
      .catch(error => {
        log('Audio playback failed:', error);
        // Browser autoplay policy - try again after user interaction
        document.addEventListener('click', () => {
          elements.audio.play();
        }, { once: true });
      });
  }, CONFIG.autoPlayDelay);
}

/**
 * Add audio to queue and play if not currently playing
 */
function queueAudio(audioUrl) {
  state.audioQueue.push(audioUrl);

  if (!state.isSpeaking) {
    playNextInQueue();
  }
}

/**
 * Play next audio in queue
 */
function playNextInQueue() {
  if (state.audioQueue.length === 0) {
    return;
  }

  const nextAudioUrl = state.audioQueue.shift();
  playAudio(nextAudioUrl);
}

/**
 * Update status text
 */
function updateStatus(status, connectionState = null) {
  if (elements.status) {
    elements.status.textContent = status;
  }

  if (connectionState) {
    state.isConnected = connectionState === 'connected';
    if (elements.connectionStatus) {
      elements.connectionStatus.className = `status-${connectionState}`;
    }
    if (elements.statusText) {
      elements.statusText.textContent = connectionState.charAt(0).toUpperCase() + connectionState.slice(1);
    }
    updateDebug('connection', connectionState);
  }
}

/**
 * Set avatar image
 */
function setAvatarImage(imageUrl) {
  elements.avatar.src = imageUrl;
  log('Avatar image updated:', imageUrl);
}

/**
 * Show speaking indicator animation
 */
function showSpeakingIndicator() {
  if (elements.speakingIndicator) {
    elements.speakingIndicator.classList.remove('hidden');
  }
  updateStatus('Speaking...');
}

/**
 * Hide speaking indicator
 */
function hideSpeakingIndicator() {
  if (elements.speakingIndicator) {
    elements.speakingIndicator.classList.add('hidden');
  }
  if (state.isListening) {
    updateStatus('Listening...');
  } else {
    updateStatus('Ready');
  }
}

/**
 * Update pipeline status indicator (compact visual diagnostic)
 */
function updatePipelineStatus(stage, status, value = '') {
  const elements = {
    'audio': document.getElementById('pipe-audio'),
    'level': document.getElementById('pipe-level'),
    'stt': document.getElementById('pipe-stt')
  };

  const el = elements[stage];
  if (!el) return;

  if (status === 'ok') {
    el.style.color = '#0f0';
    el.textContent = '✓';
  } else if (status === 'error') {
    el.style.color = '#f00';
    el.textContent = '✗';
  } else if (status === 'waiting') {
    el.style.color = '#888';
    el.textContent = '⏳';
  } else if (status === 'value') {
    el.style.color = '#0ff';
    el.textContent = value;
  }
}

/**
 * Update debug panel
 */
function updateDebug(field, value) {
  if (!CONFIG.enableDebug) return;

  const debugElement = document.getElementById(`debug-${field}`);
  if (debugElement) {
    debugElement.textContent = value;
  }
}

/**
 * Speak text using Web Speech API (browser TTS)
 * DEPRECATED: Now using Kokoro TTS streaming via RAG API
 * Kept as fallback for error scenarios
 */
function speakText(text) {
  if (!text || text.trim().length === 0) {
    return;
  }

  log('Fallback to Web Speech API:', text.substring(0, 50) + '...');

  // Cancel any ongoing speech
  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);

  // Configure voice
  utterance.lang = 'en-US';
  utterance.rate = 1.0;  // Normal speed
  utterance.pitch = 1.0;
  utterance.volume = 1.0;

  // Select a natural-sounding voice if available
  const voices = window.speechSynthesis.getVoices();
  const preferredVoice = voices.find(v =>
    v.lang.startsWith('en') && (v.name.includes('Google') || v.name.includes('Natural'))
  );
  if (preferredVoice) {
    utterance.voice = preferredVoice;
  }

  // Event handlers
  utterance.onstart = () => {
    state.isSpeaking = true;
    showSpeakingIndicator();
    log('Speech started');
  };

  utterance.onend = () => {
    state.isSpeaking = false;
    hideSpeakingIndicator();
    log('Speech ended');

    // Play next in queue
    playNextInQueue();
  };

  utterance.onerror = (error) => {
    log('Speech error:', error);
    state.isSpeaking = false;
    hideSpeakingIndicator();
  };

  // Speak
  window.speechSynthesis.speak(utterance);
  updateStatus('Speaking...');
}

/**
 * Resample audio from source sample rate to target sample rate
 * Simple linear interpolation resampling
 * @param {Float32Array} audioData - Input audio data
 * @param {number} sourceSampleRate - Source sample rate (Hz)
 * @param {number} targetSampleRate - Target sample rate (Hz)
 * @returns {Float32Array} Resampled audio data
 */
function resampleAudio(audioData, sourceSampleRate, targetSampleRate) {
  if (sourceSampleRate === targetSampleRate) {
    return audioData;
  }

  const ratio = sourceSampleRate / targetSampleRate;
  const outputLength = Math.ceil(audioData.length / ratio);
  const output = new Float32Array(outputLength);

  for (let i = 0; i < outputLength; i++) {
    const sourceIndex = i * ratio;
    const index = Math.floor(sourceIndex);
    const fraction = sourceIndex - index;

    if (index + 1 < audioData.length) {
      // Linear interpolation
      output[i] = audioData[index] * (1 - fraction) + audioData[index + 1] * fraction;
    } else {
      output[i] = audioData[index];
    }
  }

  return output;
}

/**
 * Convert ArrayBuffer to base64
 */
function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Log message - DISABLED FOR PERFORMANCE
 * To re-enable: uncomment the function body
 */
function log(...args) {
  // Logging disabled for performance
  // Uncomment below to re-enable:
  // const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
  // console.log('[AvatarInterface]', timestamp, ...args);
}

// Expose global API for external control
window.FIRSTWEEKAvatar = {
  playAudio,
  queueAudio,
  updateStatus,
  setAvatarImage,
  getState: () => ({ ...state })
};

// Initialize on load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { playAudio, updateStatus, setAvatarImage };
}
