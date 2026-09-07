// backend/chat-service/services/messageService.js

const messageRepository = require("../repositories/messageRepository");
const conversationRepository = require("../repositories/conversationRepository");
const ragService = require("./ragService");
const preferencesService = require("./preferencesService");
const conversationService = require("./conversationService");
const { createLogger } = require("../shared/utils/logger");
const { ValidationError, NotFoundError } = require("../shared/utils/errors");

// Global variable to store Socket.IO instance (set by server.js)
let ioInstance = null;

/**
 * Set Socket.IO instance for emitting events
 * @param {Object} io - Socket.IO server instance
 */
const setSocketIO = (io) => {
  ioInstance = io;
};

const logger = createLogger("message-service");

/**
 * Message Service
 * Business logic for message management and RAG integration
 */

/**
 * Send a message and get AI response
 * @param {Object} params - Message parameters
 * @param {string} params.conversationId - Conversation ID
 * @param {string} params.userId - User ID (for authorization)
 * @param {string} params.content - Message content
 * @param {Object} params.user - User object with role (for RAG)
 * @param {Object} [params.ragOptions] - Optional RAG configuration
 * @param {number} [params.ragOptions.topK=5] - Number of documents to retrieve
 * @param {number} [params.ragOptions.minScore=0.6] - Minimum similarity score
 * @param {string} [params.ragOptions.profileId] - Executive profile ID
 * @returns {Promise<Object>} User message and AI response
 */
const sendMessage = async ({
  conversationId,
  userId,
  content,
  user,
  ragOptions = {},
}) => {
  const startTime = Date.now();

  try {
    logger.info("Sending message", {
      conversationId,
      userId,
      contentLength: content.length,
    });

    // Validate inputs
    if (!conversationId) {
      throw new ValidationError("Conversation ID is required", {
        field: "conversationId",
      });
    }

    if (!userId) {
      throw new ValidationError("User ID is required", {
        field: "userId",
      });
    }

    if (!content || typeof content !== "string") {
      throw new ValidationError("Message content is required", {
        field: "content",
      });
    }

    if (content.trim().length === 0) {
      throw new ValidationError("Message content cannot be empty", {
        field: "content",
      });
    }

    if (content.length > 10000) {
      throw new ValidationError(
        "Message content too long (max 10000 characters)",
        {
          field: "content",
          maxLength: 10000,
        },
      );
    }

    // Verify conversation exists and user owns it
    const conversation = await conversationRepository.getConversationById({
      conversationId,
      userId,
    });

    if (!conversation) {
      throw new NotFoundError("Conversation not found", { conversationId });
    }

    // Step 1: Save user message
    const userMessage = await messageRepository.createMessage({
      conversationId,
      role: "user",
      content: content.trim(),
    });

    logger.debug("User message saved", {
      messageId: userMessage.id,
      conversationId,
    });

    // Step 2: Get recent conversation context (last 10 messages)
    const recentMessages = await messageRepository.getRecentMessages({
      conversationId,
      count: 10,
    });

    // Step 2.5: Auto-update conversation title if this is the first user message
    try {
      // Filter to count only user messages (not assistant responses)
      const userMessagesOnly = recentMessages.filter(
        (msg) => msg.role === "user",
      );

      // If this is the first user message, generate title from it
      if (userMessagesOnly.length === 1) {
        logger.info("First user message detected, auto-generating title", {
          conversationId,
          messageLength: content.length,
        });

        // Generate title from first message (truncate intelligently)
        let autoTitle = content.trim();

        // Remove excessive whitespace
        autoTitle = autoTitle.replace(/\s+/g, " ");

        // Try to get first sentence (up to 60 chars)
        const sentenceEnd = autoTitle.search(/[.!?]\s/);
        if (sentenceEnd > 0 && sentenceEnd <= 60) {
          autoTitle = autoTitle.substring(0, sentenceEnd + 1);
        } else if (autoTitle.length > 60) {
          // Truncate at word boundary
          autoTitle = autoTitle.substring(0, 60);
          const lastSpace = autoTitle.lastIndexOf(" ");
          if (lastSpace > 40) {
            autoTitle = autoTitle.substring(0, lastSpace);
          }
          autoTitle += "...";
        }

        // Update conversation title (this does NOT affect socket connections)
        await conversationService.updateConversation({
          conversationId,
          userId,
          data: { title: autoTitle },
        });

        logger.info("Conversation title auto-updated", {
          conversationId,
          newTitle: autoTitle,
        });

        // Emit socket event to notify frontend of title change
        // This does NOT affect the room connection (still uses conversationId)
        if (ioInstance) {
          ioInstance
            .to(`conversation:${conversationId}`)
            .emit("conversation:title-updated", {
              conversationId,
              title: autoTitle,
              timestamp: new Date().toISOString(),
            });
          logger.debug("Title update event emitted via socket", {
            conversationId,
            newTitle: autoTitle,
          });
        }
      }
    } catch (titleError) {
      // Don't fail the message send if title update fails
      logger.warn("Failed to auto-update conversation title", {
        conversationId,
        error: titleError.message,
      });
    }

    // Build context from recent messages
    // eslint-disable-next-line no-unused-vars
    const conversationContext = recentMessages
      .map((msg) => `${msg.role}: ${msg.content}`)
      .join("\n");

    logger.debug("Retrieved conversation context", {
      conversationId,
      contextMessages: recentMessages.length,
    });

    // Step 3: Query RAG for AI response
    logger.info("Querying RAG API", {
      conversationId,
      userId,
      query: content.substring(0, 100),
    });

    const ragStartTime = Date.now();
    let assistantContent;
    let ragMetadata = null;

    try {
      // Get user preferences for RAG defaults
      let userPreferences;
      try {
        userPreferences = await preferencesService.getUserPreferences(userId);
      } catch (prefError) {
        logger.warn("Failed to get user preferences, using system defaults", {
          userId,
          error: prefError.message,
        });
        // Use system defaults if preferences can't be fetched
        userPreferences = {
          defaultProfileId: "exec_003_test",
          defaultTopK: 5,
          defaultMinScore: 0.15,
        };
      }

      // Use RAG chat for full LLM-generated response
      // Priority: ragOptions > user preferences > system defaults
      const ragResponse = await ragService.chatWithRAG({
        query: content,
        user: user,
        topK: ragOptions.topK || userPreferences.defaultTopK || 5,
        minScore:
          ragOptions.minScore || userPreferences.defaultMinScore || 0.15,
        forcePath: ragOptions.forcePath || null,
        profileId:
          ragOptions.profileId ||
          userPreferences.defaultProfileId ||
          "exec_003_test",
        language: ragOptions.language || "en", // Language preference for AI response
      });

      const ragProcessingTime = Date.now() - ragStartTime;

      logger.debug("RAG chat completed", {
        conversationId,
        answerLength: ragResponse.answer?.length || 0,
        citationsCount: ragResponse.citations?.length || 0,
        processingTime: ragProcessingTime,
      });

      // Use LLM-generated response
      if (ragResponse.success && ragResponse.answer) {
        // Got LLM-generated answer with RAG context
        assistantContent = ragResponse.answer;

        ragMetadata = {
          citationsCount: ragResponse.citations?.length || 0,
          sourcesCount: ragResponse.sources?.length || 0,
          citations: ragResponse.citations || [],
          sources: ragResponse.sources || [],
          llmPath: ragResponse.metadata?.path || "standard",
          processingTime: ragProcessingTime,
        };
      } else {
        // RAG failed - provide helpful fallback
        assistantContent =
          ragResponse.error?.message ||
          "I couldn't find specific information about that in my knowledge base. Could you rephrase your question or ask something else?";

        ragMetadata = {
          error: true,
          errorCode: ragResponse.error?.code,
          processingTime: ragProcessingTime,
        };
      }
    } catch (ragError) {
      logger.error("RAG query failed, using fallback", {
        error: ragError.message,
        conversationId,
      });

      // Fallback response if RAG fails
      assistantContent =
        "I'm having trouble accessing my knowledge base right now. Please try again in a moment.";

      ragMetadata = {
        error: ragError.message,
        fallback: true,
      };
    }

    // Step 4: Save assistant message
    const totalProcessingTime = Date.now() - startTime;

    const assistantMessage = await messageRepository.createMessage({
      conversationId,
      role: "assistant",
      content: assistantContent,
      metadata: ragMetadata,
      processingTime: totalProcessingTime,
    });

    logger.info("Assistant message created", {
      messageId: assistantMessage.id,
      conversationId,
      processingTime: totalProcessingTime,
    });

    // Step 5: Update conversation's lastMessageAt
    await conversationRepository.updateLastMessageAt(conversationId);

    logger.debug("Conversation lastMessageAt updated", { conversationId });

    // Return both messages
    return {
      userMessage: {
        id: userMessage.id,
        role: userMessage.role,
        content: userMessage.content,
        createdAt: userMessage.createdAt,
      },
      assistantMessage: {
        id: assistantMessage.id,
        role: assistantMessage.role,
        content: assistantMessage.content,
        createdAt: assistantMessage.createdAt,
        metadata: assistantMessage.metadata,
        processingTime: assistantMessage.processingTime,
      },
      processingTime: totalProcessingTime,
    };
  } catch (error) {
    logger.error("Error sending message", {
      error: error.message,
      conversationId,
      userId,
    });
    throw error;
  }
};

/**
 * Get messages for a conversation
 * @param {Object} params - Query parameters
 * @param {string} params.conversationId - Conversation ID
 * @param {string} params.userId - User ID (for authorization)
 * @param {number} [params.limit=50] - Number of messages to return
 * @param {number} [params.offset=0] - Pagination offset
 * @returns {Promise<Object>} Messages with metadata
 */
const getConversationMessages = async ({
  conversationId,
  userId,
  limit = 50,
  offset = 0,
}) => {
  try {
    logger.debug("Fetching conversation messages", {
      conversationId,
      userId,
      limit,
      offset,
    });

    // Validate inputs
    if (!conversationId) {
      throw new ValidationError("Conversation ID is required", {
        field: "conversationId",
      });
    }

    if (!userId) {
      throw new ValidationError("User ID is required", {
        field: "userId",
      });
    }

    // Validate pagination
    if (limit < 1 || limit > 100) {
      throw new ValidationError("Limit must be between 1 and 100", {
        field: "limit",
        min: 1,
        max: 100,
      });
    }

    if (offset < 0) {
      throw new ValidationError("Offset must be non-negative", {
        field: "offset",
      });
    }

    // Verify conversation exists and user owns it
    const conversation = await conversationRepository.getConversationById({
      conversationId,
      userId,
    });

    if (!conversation) {
      throw new NotFoundError("Conversation not found", { conversationId });
    }

    // Fetch messages and count
    const [messages, totalCount] = await Promise.all([
      messageRepository.getMessagesByConversationId({
        conversationId,
        limit,
        offset,
      }),
      messageRepository.countConversationMessages(conversationId),
    ]);

    logger.debug("Messages fetched", {
      conversationId,
      count: messages.length,
      totalCount,
    });

    return {
      messages: messages.map((msg) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        createdAt: msg.createdAt,
        metadata: msg.metadata,
        tokenCount: msg.tokenCount,
        processingTime: msg.processingTime,
      })),
      pagination: {
        total: totalCount,
        limit,
        offset,
        hasMore: offset + limit < totalCount,
      },
    };
  } catch (error) {
    logger.error("Error fetching conversation messages", {
      error: error.message,
      conversationId,
      userId,
    });
    throw error;
  }
};

/**
 * Delete a message
 * @param {Object} params - Delete parameters
 * @param {string} params.messageId - Message ID
 * @param {string} params.userId - User ID (for authorization)
 * @returns {Promise<Object>} Delete result
 */
const deleteMessage = async ({ messageId, userId }) => {
  try {
    logger.debug("Deleting message", { messageId, userId });

    // Validate inputs
    if (!messageId) {
      throw new ValidationError("Message ID is required", {
        field: "messageId",
      });
    }

    if (!userId) {
      throw new ValidationError("User ID is required", {
        field: "userId",
      });
    }

    // Get message to verify ownership
    const message = await messageRepository.getMessageById(messageId);

    if (!message) {
      throw new NotFoundError("Message not found", { messageId });
    }

    // Verify user owns the conversation
    if (message.conversation.userId !== userId) {
      throw new ValidationError("Unauthorized to delete this message", {
        messageId,
      });
    }

    // Delete message
    await messageRepository.deleteMessage(messageId);

    logger.info("Message deleted successfully", { messageId, userId });

    return {
      deleted: true,
      messageId,
    };
  } catch (error) {
    logger.error("Error deleting message", {
      error: error.message,
      messageId,
      userId,
    });
    throw error;
  }
};

module.exports = {
  sendMessage,
  getConversationMessages,
  deleteMessage,
  setSocketIO,
};
