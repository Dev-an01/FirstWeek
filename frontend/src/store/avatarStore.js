/**
 * Zustand Avatar Store
 * Manages avatar state, session, and WebRTC connection
 */
import { create } from 'zustand';
import { avatarService } from '../services/AvatarService';

export const useAvatarStore = create((set, get) => ({
  // State
  avatars: [],
  isLoading: false,
  isConnected: false,
  sessionId: null,
  currentAvatar: null,
  error: null,
  peerConnection: null,
  videoStream: null,

  // Actions

  /**
   * Initialize store and fetch available avatars
   */
  init: async () => {
    set({ isLoading: true, error: null });
    try {
      await avatarService.checkHealth();
      const avatars = await avatarService.getAvatars();
      set({ avatars, isLoading: false });
    } catch (error) {
      set({ error: error.message, isLoading: false });
    }
  },

  /**
   * Connect to an avatar session
   * @param {string} avatarName
   */
  connect: async (avatarName) => {
    set({ isLoading: true, error: null });
    try {
      // 1. Create Session
      const session = await avatarService.createSession(avatarName);

      // 2. Setup WebRTC
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
      });

      // Handle incoming tracks
      pc.ontrack = (event) => {
        if (event.track.kind === 'video') {
          set({ videoStream: event.streams[0] });
        }
      };

      // Create offer and set local description
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      // Wait for ICE gathering to complete (or timeout) to ensure we send a complete SDP
      // This is crucial if the backend doesn't support trickle ICE
      if (pc.iceGatheringState !== 'complete') {
        await new Promise((resolve) => {
          const checkState = () => {
            if (pc.iceGatheringState === 'complete') {
              pc.removeEventListener('icegatheringstatechange', checkState);
              resolve();
            }
          };
          pc.addEventListener('icegatheringstatechange', checkState);
          // Fallback timeout: 2 seconds is usually enough for STUN
          setTimeout(() => {
            pc.removeEventListener('icegatheringstatechange', checkState);
            resolve();
          }, 2000);
        });
      }

      // Get the complete local description with candidates
      const completeOffer = pc.localDescription;

      // Send offer to server
      const answer = await avatarService.sendOffer(
        session.session_id,
        completeOffer
      );
      await pc.setRemoteDescription(new RTCSessionDescription(answer));

      set({
        sessionId: session.session_id,
        currentAvatar: avatarName,
        isConnected: true,
        peerConnection: pc,
        isLoading: false,
      });
    } catch (error) {
      console.error('Connection failed:', error);
      set({ error: error.message, isLoading: false });
      // Cleanup if failed
      get().disconnect();
    }
  },

  /**
   * Disconnect the current session
   */
  disconnect: async () => {
    const { sessionId, peerConnection } = get();

    if (peerConnection) {
      peerConnection.close();
    }

    if (sessionId) {
      try {
        await avatarService.disconnect(sessionId);
      } catch (error) {
        console.warn('Disconnect error:', error);
      }
    }

    set({
      sessionId: null,
      currentAvatar: null,
      isConnected: false,
      peerConnection: null,
      videoStream: null,
      error: null,
    });
  },

  /**
   * Push audio data to the avatar
   * @param {Int16Array} audioData
   */
  pushAudio: async (audioData) => {
    const { sessionId } = get();
    if (!sessionId) return;

    try {
      await avatarService.pushAudio(sessionId, audioData);
    } catch (error) {
      console.error('Failed to push audio:', error);
    }
  },
}));
