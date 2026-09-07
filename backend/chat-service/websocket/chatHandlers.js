// backend/chat-service/websocket/chatHandlers.js

const messageService = require("../services/messageService");
const conversationService = require("../services/conversationService");
const { createLogger } = require("../shared/utils/logger");
const { ValidationError } = require("../shared/utils/errors");
const ragService = require("../services/ragService");
const messageRepository = require("../repositories/messageRepository");
const conversationRepository = require("../repositories/conversationRepository");
const preferencesService = require("../services/preferencesService");

const logger = createLogger("websocket-chat", process.env.LOG_LEVEL || "info");

// =============================================
// Per-socket rate limiting for cost-sensitive WebSocket events (audit H2)
// The Express `generalLimiter` only protects HTTP routes, not Socket.IO
// events, so the expensive LLM/RAG path (`chat:message`) was unthrottled.
// Limits are configurable via env; defaults are generous for human use and
// only catch automated flooding.
// =============================================
const RATE_LIMITS = {
  "chat:message": {
    max: parseInt(process.env.WS_MESSAGE_RATE_MAX || "30", 10),
    windowMs: parseInt(process.env.WS_MESSAGE_RATE_WINDOW_MS || "60000", 10),
  },
  "chat:interrupt": {
    max: parseInt(process.env.WS_INTERRUPT_RATE_MAX || "60", 10),
    windowMs: parseInt(process.env.WS_INTERRUPT_RATE_WINDOW_MS || "60000", 10),
  },
};

/**
 * Register chat event handlers for a socket
 * @param {Object} io - Socket.IO server instance
 * @param {Object} socket - Socket.IO socket instance
 */
const registerChatHandlers = (io, socket) => {
  const userId = socket.user?.id;
  const username = socket.user?.username;

  // Sliding-window rate-limit state scoped to this socket. Kept in the handler
  // closure so it is garbage-collected when the socket disconnects (no global
  // Map to leak). Returns false when the limit for `event` is exceeded.
  const rateLimitHits = new Map(); // event -> number[] (hit timestamps, ms)
  const checkRateLimit = (event) => {
    const limit = RATE_LIMITS[event];
    if (!limit) return true;
    const now = Date.now();
    const recent = (rateLimitHits.get(event) || []).filter(
      (ts) => now - ts < limit.windowMs,
    );
    if (recent.length >= limit.max) {
      rateLimitHits.set(event, recent);
      return false;
    }
    recent.push(now);
    rateLimitHits.set(event, recent);
    return true;
  };

  /**
   * Join a conversation room
   * Event: chat:join
   * Payload: { conversationId: string }
   */
  socket.on("chat:join", async (data, callback) => {
    try {
      const { conversationId } = data;

      if (!conversationId) {
        throw ValidationError("Conversation ID is required", {
          field: "conversationId",
        });
      }

      // Verify user has access to this conversation
      const conversation = await conversationService.getConversation({
        conversationId,
        userId,
      });

      // Join the conversation room
      await socket.join(`conversation:${conversationId}`);

      // Acknowledge successful join
      if (callback) {
        callback({
          success: true,
          message: "Joined conversation successfully",
          data: {
            conversationId,
            conversation: {
              id: conversation.id,
              title: conversation.title,
            },
          },
        });
      }

      // Notify other users in the room
      socket.to(`conversation:${conversationId}`).emit("user:joined", {
        userId,
        username,
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      logger.error("Error joining conversation", {
        error: error.message,
        socketId: socket.id,
        userId,
        data,
      });

      if (callback) {
        callback({
          success: false,
          error: {
            message: error.message,
            code: error.code || "JOIN_FAILED",
          },
        });
      }
    }
  });

  /**
   * Leave a conversation room
   * Event: chat:leave
   * Payload: { conversationId: string }
   */
  socket.on("chat:leave", async (data, callback) => {
    try {
      const { conversationId } = data;

      if (!conversationId) {
        throw ValidationError("Conversation ID is required", {
          field: "conversationId",
        });
      }

      // Leave the conversation room
      await socket.leave(`conversation:${conversationId}`);

      // Acknowledge successful leave
      if (callback) {
        callback({
          success: true,
          message: "Left conversation successfully",
        });
      }

      // Notify other users in the room
      socket.to(`conversation:${conversationId}`).emit("user:left", {
        userId,
        username,
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      logger.error("Error leaving conversation", {
        error: error.message,
        socketId: socket.id,
        userId,
        data,
      });

      if (callback) {
        callback({
          success: false,
          error: {
            message: error.message,
            code: error.code || "LEAVE_FAILED",
          },
        });
      }
    }
  });

  /**
   * Send a message to a conversation
   * Event: chat:message
   * Payload: { conversationId: string, content: string, ragOptions?: object }
   */
  socket.on("chat:message", async (data, callback) => {
    const startTime = Date.now();

    try {
      // Rate limit the expensive LLM/RAG path per socket (audit H2)
      if (!checkRateLimit("chat:message")) {
        logger.warn("chat:message rate limit exceeded", {
          socketId: socket.id,
          userId,
        });
        if (callback) {
          callback({
            success: false,
            error: {
              message:
                "Too many messages. Please slow down and try again shortly.",
              code: "RATE_LIMIT_EXCEEDED",
            },
          });
        }
        return;
      }

      const { conversationId, content, ragOptions } = data;

      // Validate input
      if (!conversationId) {
        throw ValidationError("Conversation ID is required", {
          field: "conversationId",
        });
      }

      if (
        !content ||
        typeof content !== "string" ||
        content.trim().length === 0
      ) {
        throw ValidationError("Message content is required", {
          field: "content",
        });
      }

      // Verify the user owns this conversation BEFORE any write (audit C1 /
      // tenant isolation). Mirrors the check already done in chat:join. Throws
      // NotFoundError for conversations the user does not own, which the catch
      // block below surfaces to the client as a failed callback. Without this,
      // the real-streaming branch wrote messages into arbitrary conversations.
      await conversationService.getConversation({ conversationId, userId });

      // Feature flag for real vs fake streaming
      const useRealStreaming = process.env.ENABLE_REAL_STREAMING === "true";

      if (useRealStreaming) {
        // ==================================================================
        // REAL STREAMING PATH (NEW)
        // ==================================================================
        // Step 1: Save user message immediately
        const userMessage = await messageRepository.createMessage({
          conversationId,
          role: "user",
          content: content.trim(),
        });

        // Step 2: Emit user message immediately (no wait!)
        io.to(`conversation:${conversationId}`).emit("message:user", {
          conversationId,
          message: userMessage,
          timestamp: new Date().toISOString(),
        });

        // Step 3: Acknowledge immediately (don't wait for RAG)
        const sessionId = ragOptions?.sessionId; // Track session ID for interrupts
        if (callback) {
          callback({
            success: true,
            message: "Message received, generating response...",
            data: {
              userMessage,
              sessionId, // Return sessionId to frontend
            },
          });
        }

        // Step 4: Get user preferences
        let userPreferences;
        try {
          userPreferences = await preferencesService.getUserPreferences(userId);
        } catch (err) {
          logger.warn("Failed to get user preferences, using defaults", {
            error: err.message,
          });
          userPreferences = { defaultTopK: 5, defaultMinScore: 0.15 };
        }

        // Step 5: Stream RAG response in real-time
        let accumulatedResponse = "";
        const citations = [];
        let metadata = {};
        const tempMessageId = `temp-${Date.now()}`;
        let audioFrameCount = 0; // Track audio frames for debugging
        let audioBatch = []; // Batch audio frames to reduce WebSocket overhead
        const AUDIO_BATCH_SIZE = 20; // Send 20 frames per WebSocket message

        try {
          // Use streaming RAG service
          for await (const chunk of ragService.chatWithRAGStream({
            query: content.trim(),
            user: socket.user,
            topK: ragOptions.topK || userPreferences.defaultTopK || 5,
            minScore:
              ragOptions.minScore || userPreferences.defaultMinScore || 0.15,
            profileId: ragOptions.profileId || userPreferences.defaultProfileId,
            forcePath: ragOptions.forcePath,
            ttsEnabled: ragOptions.ttsEnabled || false,
            voiceProfileId: ragOptions.voiceProfileId || null,
            language: ragOptions.language || "en",
            sessionId: sessionId || null,
          })) {
            if (chunk.type === "token") {
              accumulatedResponse += chunk.content;

              // Emit immediately (NO artificial delay!)
              io.to(`conversation:${conversationId}`).emit("message:stream", {
                conversationId,
                messageId: tempMessageId,
                chunk: chunk.content,
                accumulated: accumulatedResponse,
                isComplete: false,
                sessionId: sessionId || null, // Include sessionId for interrupt support
                timestamp: new Date().toISOString(),
              });
            } else if (chunk.type === "citations") {
              citations.push(...chunk.citations);
            } else if (chunk.type === "complete") {
              // Complete event contains both citations and metadata
              if (chunk.citations && chunk.citations.length > 0) {
                citations.push(...chunk.citations);
              }
              metadata = chunk.metadata || {};
            } else if (chunk.type === "progress") {
              // Progress events (routing, retrieval, react_step) - emit to frontend
              io.to(`conversation:${conversationId}`).emit("message:progress", {
                conversationId,
                messageId: tempMessageId,
                event: chunk.event,
                data: chunk.data,
                timestamp: new Date().toISOString(),
              });
            } else if (chunk.type === "audio_frame") {
              // Audio frame from TTS - batch and emit
              audioFrameCount++;
              audioBatch.push({
                data: chunk.data,
                index: chunk.index,
                samples: chunk.samples,
                segmentId: chunk.segment_id,
              });

              // Emit batch when full (reduce WebSocket overhead)
              if (audioBatch.length >= AUDIO_BATCH_SIZE) {
                logger.info("Emitting audio batch", {
                  conversationId,
                  frameCount: audioBatch.length,
                  totalFramesSoFar: audioFrameCount,
                });
                io.to(`conversation:${conversationId}`).emit(
                  "message:audio:batch",
                  {
                    conversationId,
                    messageId: tempMessageId,
                    frames: audioBatch,
                    timestamp: new Date().toISOString(),
                  },
                );
                audioBatch = [];
              }
            } else if (chunk.type === "error") {
              logger.error("RAG API returned error event", {
                error: chunk.message,
                details: chunk,
                conversationId,
              });
              throw new Error(chunk.message || "RAG streaming error");
            }
          }
        } catch (ragError) {
          logger.error("RAG streaming failed", {
            error: ragError.message,
            conversationId,
            userId,
          });
          accumulatedResponse =
            "I'm having trouble generating a response. Please try again.";
        }

        // Emit any remaining audio frames
        if (audioBatch.length > 0) {
          io.to(`conversation:${conversationId}`).emit("message:audio:batch", {
            conversationId,
            messageId: tempMessageId,
            frames: audioBatch,
            timestamp: new Date().toISOString(),
          });
          logger.debug("Emitted final audio batch", {
            frameCount: audioBatch.length,
            conversationId,
          });
        }

        // Emit audio completion if any audio was generated
        if (audioFrameCount > 0) {
          io.to(`conversation:${conversationId}`).emit(
            "message:audio:complete",
            {
              conversationId,
              messageId: tempMessageId,
              totalFrames: audioFrameCount,
              timestamp: new Date().toISOString(),
            },
          );
          logger.info("Audio streaming complete", {
            totalFrames: audioFrameCount,
            conversationId,
          });
        }

        // Step 6: Save final assistant message
        const processingTime = Date.now() - startTime;

        const assistantMessage = await messageRepository.createMessage({
          conversationId,
          role: "assistant",
          content: accumulatedResponse,
          metadata: {
            citationsCount: citations.length,
            citations,
            ...metadata,
            processingTime,
          },
          processingTime,
        });

        // Step 7: Emit completion
        io.to(`conversation:${conversationId}`).emit("message:complete", {
          conversationId,
          message: assistantMessage,
          processingTime,
          timestamp: new Date().toISOString(),
        });

        // Backwards compatibility
        io.to(`conversation:${conversationId}`).emit("message:received", {
          conversationId,
          userMessage,
          assistantMessage,
          timestamp: new Date().toISOString(),
        });

        // Update conversation timestamp
        await conversationRepository.updateLastMessageAt(conversationId);
      } else {
        // ==================================================================
        // FAKE STREAMING PATH (OLD - for backwards compatibility)
        // ==================================================================
        const result = await messageService.sendMessage({
          conversationId,
          userId,
          content: content.trim(),
          user: socket.user,
          ragOptions: ragOptions || {},
        });

        const processingTime = Date.now() - startTime;

        // Emit user message
        io.to(`conversation:${conversationId}`).emit("message:user", {
          conversationId,
          message: result.userMessage,
          timestamp: new Date().toISOString(),
        });

        // Fake streaming: split into words
        const assistantContent = result.assistantMessage.content;
        let streamedContent = "";

        const words = assistantContent.split(" ");
        for (let i = 0; i < words.length; i++) {
          const word = words[i] + (i < words.length - 1 ? " " : "");
          streamedContent += word;

          io.to(`conversation:${conversationId}`).emit("message:stream", {
            conversationId,
            messageId: result.assistantMessage.id,
            chunk: word,
            accumulated: streamedContent,
            isComplete: false,
            timestamp: new Date().toISOString(),
          });

          // eslint-disable-next-line no-promise-executor-return
          await new Promise((resolve) => setTimeout(resolve, 30));
        }

        // Emit completion
        io.to(`conversation:${conversationId}`).emit("message:complete", {
          conversationId,
          message: result.assistantMessage,
          processingTime,
          timestamp: new Date().toISOString(),
        });

        // Backwards compatibility
        io.to(`conversation:${conversationId}`).emit("message:received", {
          conversationId,
          userMessage: result.userMessage,
          assistantMessage: result.assistantMessage,
          timestamp: new Date().toISOString(),
        });

        // Acknowledge
        if (callback) {
          callback({
            success: true,
            message: "Message sent successfully",
            data: result,
            processingTime,
          });
        }
      }
    } catch (error) {
      logger.error("Error sending message via WebSocket", {
        error: error.message,
        socketId: socket.id,
        userId,
        data,
        stack: error.stack,
      });

      if (callback) {
        callback({
          success: false,
          error: {
            message: error.message,
            code: error.code || "MESSAGE_SEND_FAILED",
          },
        });
      }
    }
  });

  /**
   * Typing indicator
   * Event: chat:typing
   * Payload: { conversationId: string, isTyping: boolean }
   */
  socket.on("chat:typing", (data) => {
    try {
      const { conversationId, isTyping } = data;

      if (!conversationId) {
        return;
      }

      // Broadcast to other users in the conversation (not to sender)
      socket.to(`conversation:${conversationId}`).emit("user:typing", {
        userId,
        username,
        conversationId,
        isTyping,
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      logger.error("Error handling typing event", {
        error: error.message,
        socketId: socket.id,
        userId,
        data,
      });
    }
  });

  /**
   * Stop streaming response
   * Event: chat:stop-streaming
   * Payload: { conversationId: string, messageId: string }
   */
  socket.on("chat:stop-streaming", (data) => {
    try {
      const { conversationId, messageId } = data;

      // Note: Current implementation streams entire response immediately
      // This event is logged for future implementation where we can
      // actually cancel mid-stream processing
      // Frontend already handles ignoring the complete event

      // Broadcast stop signal to all users in the conversation
      io.to(`conversation:${conversationId}`).emit("streaming:stopped", {
        conversationId,
        messageId,
        stoppedBy: userId,
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      logger.error("Error handling stop-streaming event", {
        error: error.message,
        socketId: socket.id,
        userId,
        data,
      });
    }
  });

  /**
   * Interrupt active streaming session
   * Event: chat:interrupt
   * Payload: { sessionId: string }
   */
  socket.on("chat:interrupt", async (data, callback) => {
    try {
      // Rate limit interrupts per socket (audit H2 — triggers a RAG API call)
      if (!checkRateLimit("chat:interrupt")) {
        logger.warn("chat:interrupt rate limit exceeded", {
          socketId: socket.id,
          userId,
        });
        if (callback) {
          callback({
            success: false,
            error: {
              message: "Too many interrupt requests. Please slow down.",
              code: "RATE_LIMIT_EXCEEDED",
            },
          });
        }
        return;
      }

      const { sessionId } = data;

      if (!sessionId) {
        throw ValidationError("Session ID is required", {
          field: "sessionId",
        });
      }

      logger.info("Interrupting session via WebSocket", {
        sessionId,
        userId,
        socketId: socket.id,
      });

      // Call RAG API to interrupt session
      const result = await ragService.interruptSession(sessionId);

      if (callback) {
        callback({
          success: result.success,
          message: result.message || "Session interrupted",
          data: result,
        });
      }
    } catch (error) {
      logger.error("Error interrupting session", {
        error: error.message,
        socketId: socket.id,
        userId,
        data,
      });

      if (callback) {
        callback({
          success: false,
          error: {
            message: error.message,
            code: error.code || "INTERRUPT_FAILED",
          },
        });
      }
    }
  });

  /**
   * Get online users in a conversation
   * Event: chat:get-online-users
   * Payload: { conversationId: string }
   */
  socket.on("chat:get-online-users", async (data, callback) => {
    try {
      const { conversationId } = data;

      if (!conversationId) {
        throw ValidationError("Conversation ID is required", {
          field: "conversationId",
        });
      }

      const roomName = `conversation:${conversationId}`;
      const room = io.sockets.adapter.rooms.get(roomName);
      const socketIds = room ? Array.from(room) : [];

      // Get user info for each socket in the room
      const onlineUsers = [];
      for (const socketId of socketIds) {
        const roomSocket = io.sockets.sockets.get(socketId);
        if (roomSocket && roomSocket.user) {
          onlineUsers.push({
            userId: roomSocket.user.id,
            username: roomSocket.user.username,
            socketId: roomSocket.id,
          });
        }
      }

      if (callback) {
        callback({
          success: true,
          data: {
            conversationId,
            onlineUsers,
            count: onlineUsers.length,
          },
        });
      }
    } catch (error) {
      logger.error("Error getting online users", {
        error: error.message,
        socketId: socket.id,
        userId,
        data,
      });

      if (callback) {
        callback({
          success: false,
          error: {
            message: error.message,
            code: error.code || "GET_ONLINE_USERS_FAILED",
          },
        });
      }
    }
  });

  /**
   * Handle disconnection
   */
  socket.on("disconnect", (reason) => {
    // Socket.IO automatically removes socket from all rooms on disconnect
    // No manual cleanup needed for rooms
    logger.info("Socket disconnected", {
      socketId: socket.id,
      userId,
      reason,
    });
  });
};

module.exports = {
  registerChatHandlers,
};
