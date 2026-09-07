/**
 * Avatar Service
 * Handles communication with the remote AI Avatar API
 */

const API_BASE_URL = '/api/avatar';

class AvatarService {
  /**
   * Check API health
   * @returns {Promise<Object>} Health status
   */
  async checkHealth() {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }
    return await response.json();
  }

  /**
   * Get available avatars
   * @returns {Promise<Array>} List of avatar names
   */
  async getAvatars() {
    const response = await fetch(`${API_BASE_URL}/avatars`);
    if (!response.ok) {
      throw new Error(`Failed to fetch avatars: ${response.statusText}`);
    }
    const data = await response.json();
    return data.avatars;
  }

  /**
   * Create a new session
   * @param {string} avatarName - Name of the avatar to use
   * @param {string} conversationId - Optional conversation ID
   * @returns {Promise<Object>} Session details
   */
  async createSession(avatarName, conversationId) {
    const response = await fetch(`${API_BASE_URL}/connect`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        avatar_name: avatarName,
        conversation_id: conversationId || `conv_${Date.now()}`,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Create session failed:', response.status, errorText);
      throw new Error(
        `Failed to create session: ${response.statusText} (${response.status})`
      );
    }

    return await response.json();
  }

  /**
   * Setup WebRTC connection
   * @param {string} sessionId - Active session ID
   * @param {RTCPeerConnection} peerConnection - Local peer connection instance
   * @returns {Promise<Object>} Remote session description (answer)
   */
  async sendOffer(sessionId, offer) {
    const response = await fetch(`${API_BASE_URL}/offer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        sdp: offer.sdp,
        type: offer.type,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Send offer failed:', response.status, errorText);
      throw new Error(
        `Failed to send offer: ${response.statusText} (${response.status})`
      );
    }

    return await response.json();
  }

  /**
   * Push audio data for lip-sync
   * @param {string} sessionId - Active session ID
   * @param {Int16Array} audioData - PCM audio data
   * @returns {Promise<Object>} Response status
   */
  async pushAudio(sessionId, audioData) {
    // Convert Int16Array to base64
    const base64Audio = btoa(
      String.fromCharCode.apply(null, new Uint8Array(audioData.buffer))
    );

    const response = await fetch(`${API_BASE_URL}/push_audio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        audio_data: base64Audio,
        sample_rate: 24000,
        format: 'pcm',
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to push audio: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * Disconnect session
   * @param {string} sessionId - Active session ID
   */
  async disconnect(sessionId) {
    if (!sessionId) return;

    await fetch(`${API_BASE_URL}/disconnect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
      }),
    });
  }
}

export const avatarService = new AvatarService();
