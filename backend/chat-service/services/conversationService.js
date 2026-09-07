// backend/chat-service/services/conversationService.js

const conversationRepository = require("../repositories/conversationRepository");
const { createLogger } = require("../shared/utils/logger");
const { ValidationError, NotFoundError } = require("../shared/utils/errors");

const logger = createLogger("conversation-service");

/**
 * Conversation Service
 * Business logic for conversation management
 */

/**
 * Create a new conversation
 * @param {Object} params - Conversation parameters
 * @param {string} params.userId - User ID
 * @param {string} [params.title] - Optional conversation title
 * @returns {Promise<Object>} Created conversation
 */
const createConversation = async ({ userId, title }) => {
  try {
    logger.debug("Creating conversation", { userId, title });

    // Validate userId
    if (!userId) {
      throw new ValidationError("User ID is required", {
        field: "userId",
      });
    }

    // Validate title if provided
    if (title && typeof title !== "string") {
      throw new ValidationError("Title must be a string", {
        field: "title",
      });
    }

    if (title && title.length > 200) {
      throw new ValidationError("Title must be less than 200 characters", {
        field: "title",
        maxLength: 200,
      });
    }

    // Create conversation
    const conversation = await conversationRepository.createConversation({
      userId,
      title: title || "New Chat",
    });

    logger.info("Conversation created successfully", {
      conversationId: conversation.id,
      userId,
    });

    return {
      id: conversation.id,
      userId: conversation.userId,
      title: conversation.title,
      createdAt: conversation.createdAt,
      updatedAt: conversation.updatedAt,
      lastMessageAt: conversation.lastMessageAt,
      messageCount: conversation._count?.messages || 0,
      lastMessage: conversation.messages?.[0] || null,
    };
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
 * @returns {Promise<Object>} Conversations with metadata
 */
const getUserConversations = async ({ userId, limit = 20, offset = 0 }) => {
  try {
    logger.debug("Fetching user conversations", { userId, limit, offset });

    // Validate userId
    if (!userId) {
      throw new ValidationError("User ID is required", {
        field: "userId",
      });
    }

    // Validate pagination parameters
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

    // Fetch conversations and total count
    const [conversations, totalCount] = await Promise.all([
      conversationRepository.getConversationsByUserId({
        userId,
        limit,
        offset,
      }),
      conversationRepository.countUserConversations(userId),
    ]);

    logger.debug("Conversations fetched", {
      userId,
      count: conversations.length,
      totalCount,
    });

    // Format conversations for response
    const formattedConversations = conversations.map((conv) => ({
      id: conv.id,
      userId: conv.userId,
      title: conv.title,
      createdAt: conv.createdAt,
      updatedAt: conv.updatedAt,
      lastMessageAt: conv.lastMessageAt,
      messageCount: conv._count?.messages || 0,
      lastMessage: conv.messages?.[0] || null,
    }));

    return {
      conversations: formattedConversations,
      pagination: {
        total: totalCount,
        limit,
        offset,
        hasMore: offset + limit < totalCount,
      },
    };
  } catch (error) {
    logger.error("Error fetching user conversations", {
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
 * @returns {Promise<Object>} Conversation details
 */
const getConversation = async ({ conversationId, userId }) => {
  try {
    logger.debug("Fetching conversation", { conversationId, userId });

    // Validate parameters
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

    // Fetch conversation
    const conversation = await conversationRepository.getConversationById({
      conversationId,
      userId,
    });

    if (!conversation) {
      throw new NotFoundError("Conversation not found", {
        conversationId,
      });
    }

    logger.debug("Conversation fetched", {
      conversationId: conversation.id,
      messageCount: conversation._count?.messages || 0,
    });

    return {
      id: conversation.id,
      userId: conversation.userId,
      title: conversation.title,
      createdAt: conversation.createdAt,
      updatedAt: conversation.updatedAt,
      lastMessageAt: conversation.lastMessageAt,
      messageCount: conversation._count?.messages || 0,
      messages: conversation.messages || [],
    };
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
 * @returns {Promise<Object>} Updated conversation
 */
const updateConversation = async ({ conversationId, userId, data }) => {
  try {
    logger.debug("Updating conversation", { conversationId, userId, data });

    // Validate parameters
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

    if (!data || Object.keys(data).length === 0) {
      throw new ValidationError("Update data is required", {
        field: "data",
      });
    }

    // Validate title if provided
    if (data.title !== undefined) {
      if (typeof data.title !== "string") {
        throw new ValidationError("Title must be a string", {
          field: "title",
        });
      }

      if (data.title.length === 0) {
        throw new ValidationError("Title cannot be empty", {
          field: "title",
        });
      }

      if (data.title.length > 200) {
        throw new ValidationError("Title must be less than 200 characters", {
          field: "title",
          maxLength: 200,
        });
      }
    }

    // Only allow updating certain fields
    const allowedFields = ["title"];
    const updateData = {};

    for (const field of allowedFields) {
      if (data[field] !== undefined) {
        updateData[field] = data[field];
      }
    }

    if (Object.keys(updateData).length === 0) {
      throw new ValidationError("No valid fields to update", {
        allowedFields,
      });
    }

    // Update conversation
    const conversation = await conversationRepository.updateConversation({
      conversationId,
      userId,
      data: updateData,
    });

    logger.info("Conversation updated successfully", {
      conversationId,
      userId,
    });

    return {
      id: conversation.id,
      userId: conversation.userId,
      title: conversation.title,
      createdAt: conversation.createdAt,
      updatedAt: conversation.updatedAt,
      lastMessageAt: conversation.lastMessageAt,
      messageCount: conversation._count?.messages || 0,
    };
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

    // Validate parameters
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

    // Delete conversation (messages will be cascade deleted)
    // eslint-disable-next-line no-unused-vars
    const result = await conversationRepository.deleteConversation({
      conversationId,
      userId,
    });

    logger.info("Conversation deleted successfully", {
      conversationId,
      userId,
    });

    return {
      deleted: true,
      conversationId,
    };
  } catch (error) {
    logger.error("Error deleting conversation", {
      error: error.message,
      conversationId,
      userId,
    });
    throw error;
  }
};

module.exports = {
  createConversation,
  getUserConversations,
  getConversation,
  updateConversation,
  deleteConversation,
};
