/**
 * Socket.IO Service for Real-time Chat
 *
 * Handles WebSocket connections to the chat service for real-time messaging
 */
import { io } from 'socket.io-client';

/**
 * Determine the Socket.IO server URL based on environment
 */
const getSocketUrl = () => {
  const envSocketUrl = import.meta.env.VITE_SOCKET_URL;

  // If provided, use it directly
  if (envSocketUrl) {
    return envSocketUrl;
  }

  // Use current hostname with port 3002 for both dev and production
  // This works whether accessing via localhost, server IP, or domain name
  return `${window.location.protocol}//${window.location.hostname}:3002`;
};

const SOCKET_URL = getSocketUrl();

/**
 * Socket Manager Class
 * Manages socket connection lifecycle and event handling
 */
class SocketManager {
  constructor() {
    this.socket = null;
    this.isConnected = false;
    this.listeners = new Map();
    this.resolved = false;
    this.connectionTimeout = null; // Store timeout ID for cleanup
  }

  /**
   * Connect to the socket server
   * Uses cookie-based authentication (httpOnly cookies)
   * @param {string} token - Optional JWT token (will use cookies if not provided)
   * @returns {Promise<Socket>} Connected socket instance
   */
  connect(token = null) {
    return new Promise((resolve, reject) => {
      if (this.socket && this.isConnected) {
        resolve(this.socket);
        return;
      }

      // Reset resolved flag for new connection
      this.resolved = false;

      // Socket.IO configuration
      const socketConfig = {
        withCredentials: true, // Send cookies with requests
        transports: ['polling', 'websocket'], // Try polling first, then upgrade to websocket
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
        upgrade: true, // Allow transport upgrade
        rememberUpgrade: true,
      };

      // Add token to auth if provided (optional, cookies are primary auth method)
      if (token) {
        socketConfig.auth = { token };
      }

      this.socket = io(SOCKET_URL, socketConfig);

      // Timeout for connection - store it so we can clear it on disconnect
      this.connectionTimeout = setTimeout(() => {
        if (!this.isConnected && !this.resolved) {
          console.error('[Socket] Connection timeout after 10 seconds');
          this.connectionTimeout = null;
          this.socket?.disconnect();
          reject(
            new Error(
              'Socket connection timeout - please check if chat service is running'
            )
          );
        }
      }, 10000); // 10 second timeout

      // Connection success
      this.socket.on('connect', () => {
        this.isConnected = true;
      });

      // Authentication success
      this.socket.on('connected', () => {
        if (!this.resolved) {
          this.resolved = true;
          if (this.connectionTimeout) {
            clearTimeout(this.connectionTimeout);
            this.connectionTimeout = null;
          }
          resolve(this.socket);
        }
      });

      // Connection errors
      this.socket.on('connect_error', (error) => {
        console.error('[Socket] Connection error:', error.message);
        this.isConnected = false;

        // Don't reject immediately on first error (allow reconnection attempts)
        if (
          !this.socket.connected &&
          this.socket.io.engine.transport.name === 'polling'
        ) {
          // Retrying with different transport
        } else {
          reject(new Error(`Socket connection failed: ${error.message}`));
        }
      });

      // Disconnection
      this.socket.on('disconnect', (reason) => {
        this.isConnected = false;

        // Auto-reconnect on unexpected disconnections
        if (reason === 'io server disconnect') {
          // Server disconnected, manual reconnection needed
          console.log(
            '[Socket] Server disconnected, attempting manual reconnect...'
          );
          this.socket.connect();
        }
      });

      // Reconnection attempts
      this.socket.on('reconnect_attempt', (attemptNumber) => {
        console.log(`[Socket] Reconnection attempt ${attemptNumber}`);
      });

      this.socket.on('reconnect', (attemptNumber) => {
        console.log(`[Socket] Reconnected after ${attemptNumber} attempts`);
        this.isConnected = true;
      });

      this.socket.on('reconnect_failed', () => {
        console.error('[Socket] Reconnection failed');
        this.isConnected = false;
      });

      // Also resolve on connect event if no 'connected' event comes
      this.socket.once('connect', () => {
        setTimeout(() => {
          if (this.isConnected && !this.resolved) {
            console.log(
              '[Socket] No "connected" event received, resolving anyway'
            );
            this.resolved = true;
            if (this.connectionTimeout) {
              clearTimeout(this.connectionTimeout);
              this.connectionTimeout = null;
            }
            resolve(this.socket);
          }
        }, 2000); // Wait 2 seconds for 'connected' event
      });
    });
  }

  /**
   * Disconnect from the socket server
   */
  disconnect() {
    // Clear connection timeout if it's still running
    if (this.connectionTimeout) {
      clearTimeout(this.connectionTimeout);
      this.connectionTimeout = null;
    }

    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
      this.isConnected = false;
      this.listeners.clear();
      this.resolved = false; // Reset resolved flag
    }
  }

  /**
   * Join a conversation room
   * @param {string} conversationId - ID of the conversation to join
   * @returns {Promise<Object>} Response from server
   */
  joinConversation(conversationId) {
    return new Promise((resolve, reject) => {
      if (!this.socket || !this.isConnected) {
        reject(new Error('Socket not connected'));
        return;
      }

      this.socket.emit('chat:join', { conversationId }, (response) => {
        if (response.success) {
          resolve(response);
        } else {
          console.error(
            '[Socket] Failed to join conversation:',
            response.error
          );
          reject(new Error(response.error || 'Failed to join conversation'));
        }
      });
    });
  }

  /**
   * Leave a conversation room
   * @param {string} conversationId - ID of the conversation to leave
   * @returns {Promise<Object>} Response from server
   */
  leaveConversation(conversationId) {
    return new Promise((resolve, reject) => {
      if (!this.socket || !this.isConnected) {
        reject(new Error('Socket not connected'));
        return;
      }

      this.socket.emit('chat:leave', { conversationId }, (response) => {
        if (response.success) {
          resolve(response);
        } else {
          console.error(
            '[Socket] Failed to leave conversation:',
            response.error
          );
          reject(new Error(response.error || 'Failed to leave conversation'));
        }
      });
    });
  }

  /**
   * Send a message in a conversation
   * @param {string} conversationId - ID of the conversation
   * @param {string} content - Message content
   * @param {Object} ragOptions - RAG configuration options
   * @returns {Promise<Object>} Response from server with message data
   */
  sendMessage(conversationId, content, ragOptions = {}) {
    return new Promise((resolve, reject) => {
      if (!this.socket || !this.isConnected) {
        reject(new Error('Socket not connected'));
        return;
      }

      // Generate session ID for interrupt support
      // Use crypto.randomUUID() if available (Postgres requires valid UUID)
      let sessionId;
      try {
        sessionId = ragOptions.sessionId || crypto.randomUUID();
      } catch (e) {
        // Fallback for older browsers or non-secure contexts (though unlikely for this app)
        // This generates a UUID v4 compatible string
        sessionId =
          ragOptions.sessionId ||
          '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, (c) =>
            (
              c ^
              (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))
            ).toString(16)
          );
      }

      const optionsWithSession = {
        ...ragOptions,
        sessionId,
      };

      this.socket.emit(
        'chat:message',
        {
          conversationId,
          content,
          ragOptions: optionsWithSession,
        },
        (response) => {
          if (response.success) {
            resolve(response.data);
          } else {
            console.error('[Socket] Failed to send message:', response.error);
            reject(new Error(response.error || 'Failed to send message'));
          }
        }
      );
    });
  }

  /**
   * Send typing indicator
   * @param {string} conversationId - ID of the conversation
   * @param {boolean} isTyping - Whether user is typing
   */
  sendTypingIndicator(conversationId, isTyping) {
    if (!this.socket || !this.isConnected) {
      return;
    }

    // Fire and forget (no callback)
    this.socket.emit('chat:typing', {
      conversationId,
      isTyping,
    });
  }

  /**
   * Stop streaming response
   * @param {string} conversationId - ID of the conversation
   * @param {string} messageId - ID of the message being streamed
   */
  stopStreaming(conversationId, messageId) {
    if (!this.socket || !this.isConnected) {
      return;
    }

    // Fire and forget (no callback needed)
    this.socket.emit('chat:stop-streaming', {
      conversationId,
      messageId,
    });
  }

  /**
   * Interrupt active streaming session
   * @param {string} sessionId - Session ID to interrupt
   * @returns {Promise<Object>} Response from server
   */
  interruptSession(sessionId) {
    return new Promise((resolve, reject) => {
      if (!this.socket || !this.isConnected) {
        reject(new Error('Socket not connected'));
        return;
      }

      this.socket.emit('chat:interrupt', { sessionId }, (response) => {
        if (response.success) {
          resolve(response);
        } else {
          console.error(
            '[Socket] Failed to interrupt session:',
            response.error
          );
          reject(
            new Error(response.error?.message || 'Failed to interrupt session')
          );
        }
      });
    });
  }

  /**
   * Get online users in a conversation
   * @param {string} conversationId - ID of the conversation
   * @returns {Promise<Array>} List of online users
   */
  getOnlineUsers(conversationId) {
    return new Promise((resolve, reject) => {
      if (!this.socket || !this.isConnected) {
        reject(new Error('Socket not connected'));
        return;
      }

      this.socket.emit(
        'chat:get-online-users',
        { conversationId },
        (response) => {
          if (response.success) {
            resolve(response.data.onlineUsers);
          } else {
            reject(new Error(response.error || 'Failed to get online users'));
          }
        }
      );
    });
  }

  /**
   * Register an event listener
   * @param {string} event - Event name
   * @param {Function} callback - Callback function
   */
  on(event, callback) {
    if (!this.socket) {
      console.warn('[Socket] Cannot add listener, socket not initialized');
      return;
    }

    // Store listener for cleanup
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);

    this.socket.on(event, callback);
  }

  /**
   * Remove an event listener
   * @param {string} event - Event name
   * @param {Function} callback - Callback function (optional, removes all if not provided)
   */
  off(event, callback) {
    if (!this.socket) {
      return;
    }

    if (callback) {
      this.socket.off(event, callback);

      // Remove from stored listeners
      if (this.listeners.has(event)) {
        const callbacks = this.listeners.get(event);
        const index = callbacks.indexOf(callback);
        if (index > -1) {
          callbacks.splice(index, 1);
        }
      }
    } else {
      // Remove all listeners for this event
      this.socket.off(event);
      this.listeners.delete(event);
    }
  }

  /**
   * Send ping to check connection
   */
  ping() {
    if (!this.socket || !this.isConnected) {
      return;
    }

    this.socket.emit('ping');
  }

  /**
   * Get connection status
   * @returns {boolean} Whether socket is connected
   */
  getConnectionStatus() {
    return this.isConnected && this.socket?.connected;
  }

  /**
   * Get socket instance
   * @returns {Socket|null} Socket instance or null if not connected
   */
  getSocket() {
    return this.socket;
  }
}

// Export singleton instance
export const socketManager = new SocketManager();

// Export class for testing
export { SocketManager };

// Export default
export default socketManager;
