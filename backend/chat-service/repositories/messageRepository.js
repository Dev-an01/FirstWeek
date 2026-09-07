// backend/chat-service/repositories/messageRepository.js

const { prisma: db } = require("../shared/lib/prisma");
const { createLogger } = require("../shared/utils/logger");

const logger = createLogger("message-repository");

/**
 * Message Repository
 * Handles all database operations for messages
 */

/**
 * Create a new message
 * @param {Object} data - Message data
 * @param {string} data.conversationId - Conversation ID
 * @param {string} data.role - Message role (user, assistant, system)
 * @param {string} data.content - Message content
 * @param {Object} [data.metadata] - Optional metadata
 * @param {number} [data.tokenCount] - Optional token count
 * @param {number} [data.processingTime] - Optional processing time in ms
 * @returns {Promise<Object>} Created message
 */
const createMessage = async ({
  conversationId,
  role,
  content,
  metadata = null,
  tokenCount = null,
  processingTime = null,
}) => {
  try {
    logger.debug("Creating message", {
      conversationId,
      role,
      contentLength: content.length,
    });

    const message = await db.message.create({
      data: {
        conversationId,
        role,
        content,
        metadata,
        tokenCount,
        processingTime,
      },
    });

    logger.info("Message created", {
      messageId: message.id,
      conversationId: message.conversationId,
      role: message.role,
    });

    return message;
  } catch (error) {
    logger.error("Error creating message", {
      error: error.message,
      conversationId,
    });
    throw error;
  }
};

/**
 * Get messages for a conversation
 * @param {Object} params - Query parameters
 * @param {string} params.conversationId - Conversation ID
 * @param {number} [params.limit=50] - Number of messages to return
 * @param {number} [params.offset=0] - Pagination offset
 * @returns {Promise<Array>} List of messages
 */
const getMessagesByConversationId = async ({
  conversationId,
  limit = 50,
  offset = 0,
}) => {
  try {
    logger.debug("Fetching messages", { conversationId, limit, offset });

    const messages = await db.message.findMany({
      where: { conversationId },
      orderBy: { createdAt: "asc" }, // Oldest first for chat display
      take: limit,
      skip: offset,
    });

    logger.debug("Messages fetched", {
      conversationId,
      count: messages.length,
    });

    return messages;
  } catch (error) {
    logger.error("Error fetching messages", {
      error: error.message,
      conversationId,
    });
    throw error;
  }
};

/**
 * Get a specific message by ID
 * @param {string} messageId - Message ID
 * @returns {Promise<Object|null>} Message or null if not found
 */
const getMessageById = async (messageId) => {
  try {
    logger.debug("Fetching message", { messageId });

    const message = await db.message.findUnique({
      where: { id: messageId },
      include: {
        conversation: {
          select: {
            id: true,
            userId: true,
            title: true,
          },
        },
      },
    });

    if (message) {
      logger.debug("Message found", { messageId });
    } else {
      logger.debug("Message not found", { messageId });
    }

    return message;
  } catch (error) {
    logger.error("Error fetching message", {
      error: error.message,
      messageId,
    });
    throw error;
  }
};

/**
 * Count total messages in a conversation
 * @param {string} conversationId - Conversation ID
 * @returns {Promise<number>} Total message count
 */
const countConversationMessages = async (conversationId) => {
  try {
    const count = await db.message.count({
      where: { conversationId },
    });

    return count;
  } catch (error) {
    logger.error("Error counting messages", {
      error: error.message,
      conversationId,
    });
    throw error;
  }
};

/**
 * Delete a message
 * @param {string} messageId - Message ID
 * @returns {Promise<Object>} Delete result
 */
const deleteMessage = async (messageId) => {
  try {
    logger.debug("Deleting message", { messageId });

    const message = await db.message.delete({
      where: { id: messageId },
    });

    logger.info("Message deleted", { messageId });

    return message;
  } catch (error) {
    logger.error("Error deleting message", {
      error: error.message,
      messageId,
    });
    throw error;
  }
};

/**
 * Get recent messages for context (last N messages)
 * @param {Object} params - Query parameters
 * @param {string} params.conversationId - Conversation ID
 * @param {number} [params.count=10] - Number of recent messages
 * @returns {Promise<Array>} Recent messages
 */
const getRecentMessages = async ({ conversationId, count = 10 }) => {
  try {
    logger.debug("Fetching recent messages", { conversationId, count });

    const messages = await db.message.findMany({
      where: { conversationId },
      orderBy: { createdAt: "desc" },
      take: count,
    });

    // Return in chronological order (oldest first)
    const chronological = messages.reverse();

    logger.debug("Recent messages fetched", {
      conversationId,
      count: chronological.length,
    });

    return chronological;
  } catch (error) {
    logger.error("Error fetching recent messages", {
      error: error.message,
      conversationId,
    });
    throw error;
  }
};

/**
 * Delete all messages in a conversation
 * @param {string} conversationId - Conversation ID
 * @returns {Promise<Object>} Delete result with count
 */
const deleteConversationMessages = async (conversationId) => {
  try {
    logger.debug("Deleting conversation messages", { conversationId });

    const result = await db.message.deleteMany({
      where: { conversationId },
    });

    logger.info("Conversation messages deleted", {
      conversationId,
      count: result.count,
    });

    return result;
  } catch (error) {
    logger.error("Error deleting conversation messages", {
      error: error.message,
      conversationId,
    });
    throw error;
  }
};

module.exports = {
  createMessage,
  getMessagesByConversationId,
  getMessageById,
  countConversationMessages,
  deleteMessage,
  getRecentMessages,
  deleteConversationMessages,
};
