/**
 * WebRTC Client for Avatar Video
 * Handles connection to Avatar Streaming Service
 * 
 * Signaling: Socket.io (http://34.80.175.36:3001)
 * Media: WebRTC Video track (Receiver)
 */
class WebRTCClient {
    constructor(config) {
        this.config = {
            // New Signaling Endpoint
            signalingUrl: config.signalingUrl || 'https://example.invalid',
            sessionId: config.sessionId || null, // CRITICAL: Required for GPU allocation
            ...config
        };

        this.socket = null;
        this.pc = null;
        this.isConnected = false;
        this.mediaStream = new MediaStream();

        // Callbacks
        this.onConnectedCallback = null;
        this.onDisconnectedCallback = null;
        this.onErrorCallback = null;
        this.onTrackCallback = null;

        // Debug
        this.audioMonitoringContext = null;
    }

    /**
     * Connect to the Signaling Server
     */
    async connect() {
        if (!this.config.sessionId) {
            this._notifyError('Session ID is required for connection');
            return;
        }

        console.log('[WebRTCClient] Connecting to Signaling Server:', this.config.signalingUrl);
        console.log('[WebRTCClient] Session ID:', this.config.sessionId);

        // FREEZE: Close existing connections
        this.disconnect();

        // 1. Connect via Socket.io
        this.socket = io(this.config.signalingUrl, {
            path: '/wrtc/socket.io',
            query: { session_id: this.config.sessionId },
            transports: ['websocket'] // Force WebSocket for better performance
        });

        this._setupSocketListeners();
    }

    _setupSocketListeners() {
        this.socket.on('connect', () => {
            console.log('[WebRTCClient] Socket.io Connected');
        });

        this.socket.on('disconnect', (reason) => {
            console.log('[WebRTCClient] Socket.io Disconnected:', reason);
            this.disconnect();
        });

        this.socket.on('connect_error', (error) => {
            console.error('[WebRTCClient] Socket.io Connection Error:', error);
            this._notifyError(`Signaling connection failed: ${error.message}`);
        });

        // 2. Listen for 'offer' (Server initiates)
        this.socket.on('offer', async (data) => {
            console.log('[WebRTCClient] Received Offer');
            await this._handleOffer(data);
        });

        // Exchange candidates
        this.socket.on('candidate', async (data) => {
            await this._handleRemoteCandidate(data);
        });
    }

    async _handleOffer(offerData) {
        try {
            this._createPeerConnection();

            // Set Remote Description (Offer)
            // Handle both raw SDP string or object formats if necessary, 
            // but standard is usually { type: 'offer', sdp: ... }
            const sdp = offerData.sdp || offerData;
            await this.pc.setRemoteDescription(new RTCSessionDescription({
                type: 'offer',
                sdp: sdp
            }));

            // 3. Send Answer
            const answer = await this.pc.createAnswer();
            await this.pc.setLocalDescription(answer);

            this.socket.emit('answer', {
                type: 'answer',
                sdp: answer.sdp,
                session_id: this.config.sessionId
            });

            this.isConnected = true;
            if (this.onConnectedCallback) this.onConnectedCallback();

        } catch (e) {
            console.error('[WebRTCClient] Error handling offer:', e);
            this._notifyError(e);
        }
    }

    _createPeerConnection() {
        if (this.pc) {
            this.pc.close();
        }

        const iceServers = this.config.iceServers || [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' }
        ];

        this.pc = new RTCPeerConnection({
            iceServers: iceServers,
            bundlePolicy: 'max-bundle',
            rtcpMuxPolicy: 'require'
        });

        // Debug ICE State
        this.pc.oniceconnectionstatechange = () => {
            console.log('[WebRTCClient] ICE State:', this.pc.iceConnectionState);
            if (this.pc.iceConnectionState === 'failed') {
                this._notifyError('ICE Connection Failed');
            }
        };

        // Handle Incoming Video/Audio
        this.pc.ontrack = (event) => {
            console.log('[WebRTCClient] Received Track:', event.track.kind);
            this.mediaStream.addTrack(event.track);

            if (event.track.kind === 'audio') {
                // Optional: Monitor audio levels if needed
                this._startAudioMonitoring(event.track);
            }

            if (this.onTrackCallback) {
                this.onTrackCallback(this.mediaStream);
            }
        };

        // 4. Exchange Candidates
        this.pc.onicecandidate = (event) => {
            if (event.candidate) {
                this.socket.emit('candidate', {
                    candidate: event.candidate.candidate,
                    sdpMid: event.candidate.sdpMid,
                    sdpMLineIndex: event.candidate.sdpMLineIndex,
                    session_id: this.config.sessionId
                });
            }
        };
    }

    async _handleRemoteCandidate(data) {
        if (!this.pc) return;
        try {
            await this.pc.addIceCandidate(new RTCIceCandidate({
                candidate: data.candidate,
                sdpMid: data.sdpMid,
                sdpMLineIndex: data.sdpMLineIndex
            }));
            console.log('[WebRTCClient] Added Remote Candidate');
        } catch (e) {
            console.error('[WebRTCClient] Error adding candidate:', e);
        }
    }

    _startAudioMonitoring(track) {
        // Kept for debug visualizer in console
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            this.audioMonitoringContext = audioCtx;
            const source = audioCtx.createMediaStreamSource(new MediaStream([track]));
            const analyser = audioCtx.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);

            const dataArray = new Uint8Array(analyser.frequencyBinCount);
            const checkVolume = () => {
                if (!this.isConnected || audioCtx.state === 'closed') return;
                analyser.getByteFrequencyData(dataArray);
                let sum = 0;
                for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
                const avg = sum / dataArray.length;
                if (avg > 10) {
                    // console.log(`Audio Level: ${avg}`); 
                }
                requestAnimationFrame(checkVolume);
            };
            checkVolume();
        } catch (e) {
            console.warn('[WebRTCClient] Audio monitoring failed', e);
        }
    }

    disconnect() {
        console.log('[WebRTCClient] Disconnecting...');

        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }

        if (this.pc) {
            this.pc.close();
            this.pc = null;
        }

        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(t => t.stop());
            this.mediaStream = new MediaStream();
        }

        if (this.audioMonitoringContext) {
            this.audioMonitoringContext.close();
            this.audioMonitoringContext = null;
        }

        this.isConnected = false;
        if (this.onDisconnectedCallback) this.onDisconnectedCallback();
    }

    // --- Compatible Event Hooks
    onConnected(cb) { this.onConnectedCallback = cb; }
    onDisconnected(cb) { this.onDisconnectedCallback = cb; }
    onError(cb) { this.onErrorCallback = cb; }
    onTrack(cb) { this.onTrackCallback = cb; }

    // Dummy methods for API compatibility
    setRenderer(r) { }
    stopSpeaking() {
        // Audio control is now strictly backend (REST/WS), but if we needed 
        // to signal via frontend socket we could do it here. 
        // For now, per docs, we do nothing or emit event if server supports it.
    }
    _notifyError(msg) {
        if (this.onErrorCallback) this.onErrorCallback(new Error(msg));
    }
}

window.WebRTCClient = WebRTCClient;
