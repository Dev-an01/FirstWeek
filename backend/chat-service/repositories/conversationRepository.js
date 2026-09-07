// backend/chat-service/repositories/conversationRepository.js

const { prisma: db } = require("../shared/lib/prisma");
const { createLogger } = require("../shared/utils/logger");

const logger = createLogger("conversation-repository");

/**
 * Conversation Repository
 * Handles all database operations for conversations
 */

/**
 * Create a new conversation
 * @param {Object} data - Conversation data
 * @param {string} data.userId - User ID who owns the conversation
 * @param {string} [data.title] - Optional conversation title
 * @returns {Promise<Object>} Created conversation
 */
const createConversation = async ({ userId, title = "New Chat" }) => {
  try {
    logger.debug("Creating conversation", { userId, title });

    const conversation = await db.conversation.create({
      data: {
        userId,
        title,
      },
      include: {
        messages: {
          orderBy: { createdAt: "desc" },
          take: 1, // Include last message for preview
        },
      },
    });

    logger.info("Conversation created", {
      conversationId: conversation.id,
      userId: conversation.userId,
    });

    return conversation;
  } catch (error) {
    logger.error("Error creating conversation", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

/**
 * Get all conversations for a user
 * @param {Object} params - Query parameters
 * @param {string} params.userId - User ID
 * @param {number} [params.limit=20] - Number of conversations to return
 * @param {number} [params.offset=0] - Pagination offset
 * @returns {Promise<Array>} List of conversations
 */
const getConversationsByUserId = async ({ userId, limit = 20, offset = 0 }) => {
  try {
    logger.debug("Fetching conversations", { userId, limit, offset });

    const conversations = await db.conversation.findMany({
      where: { userId },
      include: {
        messages: {
          orderBy: { createdAt: "desc" },
          take: 1, // Include last message for preview
        },
        _count: {
          select: { messages: true },
        },
      },
      orderBy: [{ lastMessageAt: "desc" }, { updatedAt: "desc" }],
      take: limit,
      skip: offset,
    });

    logger.debug("Conversations fetched", {
      userId,
      count: conversations.length,
    });

    return conversations;
  } catch (error) {
    logger.error("Error fetching conversations", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

/**
 * Get a specific conversation by ID
 * @param {Object} params - Query parameters
 * @param {string} params.conversationId - Conversation ID
 * @param {string} params.userId - User ID (for authorization)
 * @returns {Promise<Object|null>} Conversation or null if not found
 */
const getConversationById = async ({ conversationId, userId }) => {
  try {
    logger.debug("Fetching conversation", { conversationId, userId });

    const conversation = await db.conversation.findFirst({
      where: {
        id: conversationId,
        userId, // Ensure user owns this conversation
      },
      include: {
        messages: {
          orderBy: { createdAt: "asc" },
          select: {
            id: true,
            role: true,
            content: true,
            createdAt: true,
            metadata: true,
            tokenCount: true,
            processingTime: true,
          },
        },
        _count: {
          select: { messages: true },
        },
      },
    });

    if (conversation) {
      logger.debug("Conversation found", {
        conversationId: conversation.id,
        messageCount: conversation._count.messages,
      });
    } else {
      logger.debug("Conversation not found", { conversationId, userId });
    }

    return conversation;
  } catch (error) {
    logger.error("Error fetching conversation", {
      error: error.message,
      conversationId,
      userId,
    });
    throw error;
  }
};

/**
 * Update a conversation
 * @param {Object} params - Update parameters
 * @param {string} params.conversationId - Conversation ID
 * @param {string} params.userId - User ID (for authorization)
 * @param {Object} params.data - Fields to update
 * @param {string} [params.data.title] - New title
 * @param {Date} [params.data.lastMessageAt] - Last message timestamp
 * @returns {Promise<Object>} Updated conversation
 */
const updateConversation = async ({ conversationId, userId, data }) => {
  try {
    logger.debug("Updating conversation", { conversationId, userId, data });

    const conversation = await db.conversation.updateMany({
      where: {
        id: conversationId,
        userId, // Ensure user owns this conversation
      },
      data,
    });

    if (conversation.count === 0) {
      const error = new Error("Conversation not found or unauthorized");
      error.code = "NOT_FOUND";
      throw error;
    }

    logger.info("Conversation updated", { conversationId, userId });

    // Fetch and return updated conversation
    return await getConversationById({ conversationId, userId });
  } catch (error) {
    logger.error("Error updating conversation", {
      error: error.message,
      conversationId,
      userId,
    });
    throw error;
  }
};

/**
 * Delete a conversation
 * @param {Object} params - Delete parameters
 * @param {string} params.conversationId - Conversation ID
 * @param {string} params.userId - User ID (for authorization)
 * @returns {Promise<Object>} Delete result
 */
const deleteConversation = async ({ conversationId, userId }) => {
  try {
    logger.debug("Deleting conversation", { conversationId, userId });

    const result = await db.conversation.deleteMany({
      where: {
        id: conversationId,
        userId, // Ensure user owns this conversation
      },
    });

    if (result.count === 0) {
      const error = new Error("Conversation not found or unauthorized");
      error.code = "NOT_FOUND";
      throw error;
    }

    logger.info("Conversation deleted", { conversationId, userId });

    return { deleted: true, count: result.count };
  } catch (error) {
    logger.error("Error deleting conversation", {
      error: error.message,
      conversationId,
      userId,
    });
    throw error;
  }
};

/**
 * Count total conversations for a user
 * @param {string} userId - User ID
 * @returns {Promise<number>} Total conversation count
 */
const countUserConversations = async (userId) => {
  try {
    const count = await db.conversation.count({
      where: { userId },
    });

    return count;
  } catch (error) {
    logger.error("Error counting conversations", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

/**
 * Update conversation's lastMessageAt timestamp
 * @param {string} conversationId - Conversation ID
 * @returns {Promise<Object>} Updated conversation
 */
const updateLastMessageAt = async (conversationId) => {
  try {
    logger.debug("Updating lastMessageAt", { conversationId });

    const conversation = await db.conversation.update({
      where: { id: conversationId },
      data: { lastMessageAt: new Date() },
    });

    return conversation;
  } catch (error) {
    logger.error("Error updating lastMessageAt", {
      error: error.message,
      conversationId,
    });
    throw error;
  }
};

module.exports = {
  createConversation,
  getConversationsByUserId,
  getConversationById,
  updateConversation,
  deleteConversation,
  countUserConversations,
  updateLastMessageAt,
};
