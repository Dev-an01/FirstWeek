// backend/chat-service/controllers/chatController.js

const {
  createLogger,
  // eslint-disable-next-line
} = require('../shared/utils/logger');
const ragService = require("../services/ragService");
const conversationService = require("../services/conversationService");
const messageService = require("../services/messageService");
const {
  transformError,
  isValidationError,
  isConflictError,
  isNotFoundError,
} = require("../shared/utils/errors");

const logger = createLogger("chatController", process.env.LOG_LEVEL || "info");

/**
 * Helper function to get HTTP status code from error type
 * @param {Error} error - Transformed error object
 * @returns {number} HTTP status code
 */
const getErrorStatusCode = (error) => {
  if (isValidationError(error)) return 400;
  if (isConflictError(error)) return 409;
  if (isNotFoundError(error)) return 404;
  if (error.name === "AuthenticationError") return 401;
  if (error.name === "AuthorizationError") return 403;
  return 500; // Internal server error for all other cases
};

/**
 * Test endpoint to verify chat service is working
 * GET /api/chat/test
 */
const testEndpoint = async (req, res) => {
  try {
    logger.info("Test endpoint called", { ip: req.ip });

    res.json({
      success: true,
      message: "Chat service is working! 🚀",
      service: "chat-service",
      timestamp: new Date().toISOString(),
      data: {
        socketIOAvailable: !!req.app.get("io"),
        environment: process.env.NODE_ENV || "development",
      },
    });
  } catch (error) {
    logger.error("Test endpoint error", {
      error: error.message,
      stack: error.stack,
    });

    res.status(500).json({
      success: false,
      error: {
        message: "Internal server error",
        code: "INTERNAL_ERROR",
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Get all conversations for authenticated user
 * GET /api/chat/conversations
 * Query params: ?limit=20&offset=0
 */
const getConversations = async (req, res) => {
  try {
    const userId = req.user.id;
    const limit = parseInt(req.query.limit) || 20;
    const offset = parseInt(req.query.offset) || 0;

    logger.info("Fetching conversations", { userId, limit, offset });

    const result = await conversationService.getUserConversations({
      userId,
      limit,
      offset,
    });

    res.json({
      success: true,
      message: "Conversations retrieved successfully",
      data: result,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("Get conversations error", {
      error: error.message,
      userId: req.user?.id,
    });

    const transformed = transformError(error);
    const statusCode = getErrorStatusCode(transformed);
    res.status(statusCode).json({
      success: false,
      error: {
        message: transformed.message,
        code: transformed.code,
        ...(transformed.metadata && { metadata: transformed.metadata }),
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Create a new conversation
 * POST /api/chat/conversations
 * Body: { title?: string }
 */
const createConversation = async (req, res) => {
  try {
    const userId = req.user.id;
    const { title } = req.body;

    logger.info("Creating conversation", { userId, title });

    const conversation = await conversationService.createConversation({
      userId,
      title,
    });

    res.status(201).json({
      success: true,
      message: "Conversation created successfully",
      data: conversation,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("Create conversation error", {
      error: error.message,
      userId: req.user?.id,
    });

    const transformed = transformError(error);
    const statusCode = getErrorStatusCode(transformed);
    res.status(statusCode).json({
      success: false,
      error: {
        message: transformed.message,
        code: transformed.code,
        ...(transformed.metadata && { metadata: transformed.metadata }),
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Get a specific conversation
 * GET /api/chat/conversations/:id
 */
const getConversation = async (req, res) => {
  try {
    const userId = req.user.id;
    const conversationId = req.params.id;

    logger.info("Fetching conversation", { userId, conversationId });

    const conversation = await conversationService.getConversation({
      conversationId,
      userId,
    });

    res.json({
      success: true,
      message: "Conversation retrieved successfully",
      data: conversation,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("Get conversation error", {
      error: error.message,
      userId: req.user?.id,
      conversationId: req.params.id,
    });

    const transformed = transformError(error);
    const statusCode = getErrorStatusCode(transformed);
    res.status(statusCode).json({
      success: false,
      error: {
        message: transformed.message,
        code: transformed.code,
        ...(transformed.metadata && { metadata: transformed.metadata }),
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Update a conversation
 * PATCH /api/chat/conversations/:id
 * Body: { title?: string }
 */
const updateConversation = async (req, res) => {
  try {
    const userId = req.user.id;
    const conversationId = req.params.id;
    const updateData = req.body;

    logger.info("Updating conversation", {
      userId,
      conversationId,
      updateData,
    });

    const conversation = await conversationService.updateConversation({
      conversationId,
      userId,
      data: updateData,
    });

    res.json({
      success: true,
      message: "Conversation updated successfully",
      data: conversation,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("Update conversation error", {
      error: error.message,
      userId: req.user?.id,
      conversationId: req.params.id,
    });

    const transformed = transformError(error);
    const statusCode = getErrorStatusCode(transformed);
    res.status(statusCode).json({
      success: false,
      error: {
        message: transformed.message,
        code: transformed.code,
        ...(transformed.metadata && { metadata: transformed.metadata }),
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Delete a conversation
 * DELETE /api/chat/conversations/:id
 */
const deleteConversation = async (req, res) => {
  try {
    const userId = req.user.id;
    const conversationId = req.params.id;

    logger.info("Deleting conversation", { userId, conversationId });

    const result = await conversationService.deleteConversation({
      conversationId,
      userId,
    });

    res.json({
      success: true,
      message: "Conversation deleted successfully",
      data: result,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("Delete conversation error", {
      error: error.message,
      userId: req.user?.id,
      conversationId: req.params.id,
    });

    const transformed = transformError(error);
    const statusCode = getErrorStatusCode(transformed);
    res.status(statusCode).json({
      success: false,
      error: {
        message: transformed.message,
        code: transformed.code,
        ...(transformed.metadata && { metadata: transformed.metadata }),
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Get messages for a conversation
 * GET /api/chat/conversations/:id/messages
 * Query params: ?limit=50&offset=0
 */
const getMessages = async (req, res) => {
  try {
    const userId = req.user.id;
    const conversationId = req.params.id;
    const limit = parseInt(req.query.limit) || 50;
    const offset = parseInt(req.query.offset) || 0;

    logger.info("Fetching messages", { userId, conversationId, limit, offset });

    const result = await messageService.getConversationMessages({
      conversationId,
      userId,
      limit,
      offset,
    });

    res.json({
      success: true,
      message: "Messages retrieved successfully",
      data: result,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("Get messages error", {
      error: error.message,
      userId: req.user?.id,
      conversationId: req.params.id,
    });

    const transformed = transformError(error);
    const statusCode = getErrorStatusCode(transformed);
    res.status(statusCode).json({
      success: false,
      error: {
        message: transformed.message,
        code: transformed.code,
        ...(transformed.metadata && { metadata: transformed.metadata }),
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Send a message (HTTP fallback)
 * POST /api/chat/conversations/:id/messages
 * Body: { content: string, ragOptions?: { topK?, minScore?, profileId? } }
 */
const sendMessage = async (req, res) => {
  try {
    const userId = req.user.id;
    const conversationId = req.params.id;
    const { content, ragOptions } = req.body;

    logger.info("Sending message", {
      userId,
      conversationId,
      contentLength: content?.length,
    });

    const result = await messageService.sendMessage({
      conversationId,
      userId,
      content,
      user: req.user, // Pass full user object for RBAC
      ragOptions,
    });

    res.status(201).json({
      success: true,
      message: "Message sent successfully",
      data: result,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("Send message error", {
      error: error.message,
      userId: req.user?.id,
      conversationId: req.params.id,
    });

    const transformed = transformError(error);
    const statusCode = getErrorStatusCode(transformed);
    res.status(statusCode).json({
      success: false,
      error: {
        message: transformed.message,
        code: transformed.code,
        ...(transformed.metadata && { metadata: transformed.metadata }),
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Test RAG integration - Health check
 * GET /api/chat/rag/health
 */
const testRAGHealth = async (req, res) => {
  try {
    logger.info("Testing RAG API health", { ip: req.ip });

    const healthResult = await ragService.checkHealth();

    res.json({
      success: true,
      message: "RAG API health check completed",
      data: healthResult,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("RAG health check error", {
      error: error.message,
      stack: error.stack,
    });

    res.status(500).json({
      success: false,
      error: {
        message: "Failed to check RAG API health",
        code: "RAG_HEALTH_CHECK_FAILED",
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Test RAG integration - Query documents
 * POST /api/chat/rag/query
 * Body: { query: string, topK?: number, minScore?: number }
 */
const testRAGQuery = async (req, res) => {
  try {
    const { query, topK = 5, minScore = 0.15 } = req.body;

    if (!query) {
      return res.status(400).json({
        success: false,
        error: {
          message: "Query text is required",
          code: "MISSING_QUERY",
        },
        timestamp: new Date().toISOString(),
      });
    }

    logger.info("Testing RAG API query", {
      query: query.substring(0, 50),
      userId: req.user?.id,
      topK,
      minScore,
    });

    const result = await ragService.queryDocuments({
      query,
      user: req.user,
      topK,
      minScore,
    });

    res.json({
      success: result.success,
      message: "RAG query completed",
      data: result,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("RAG query test error", {
      error: error.message,
      stack: error.stack,
    });

    res.status(500).json({
      success: false,
      error: {
        message: "Failed to query RAG API",
        code: "RAG_QUERY_TEST_FAILED",
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Test RAG integration - Chat with LLM
 * POST /api/chat/rag/chat
 * Body: { query: string, profileId?: string, topK?: number, minScore?: number }
 */
const testRAGChat = async (req, res) => {
  try {
    const { query, profileId, topK = 5, minScore = 0.15 } = req.body;

    if (!query) {
      return res.status(400).json({
        success: false,
        error: {
          message: "Query text is required",
          code: "MISSING_QUERY",
        },
        timestamp: new Date().toISOString(),
      });
    }

    logger.info("Testing RAG API chat", {
      query: query.substring(0, 50),
      userId: req.user?.id,
      profileId,
      topK,
      minScore,
    });

    const result = await ragService.chatWithRAG({
      query,
      user: req.user,
      profileId,
      topK,
      minScore,
    });

    res.json({
      success: result.success,
      message: "RAG chat completed",
      data: result,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("RAG chat test error", {
      error: error.message,
      stack: error.stack,
    });

    res.status(500).json({
      success: false,
      error: {
        message: "Failed to chat with RAG API",
        code: "RAG_CHAT_TEST_FAILED",
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Get available RAG profiles
 * GET /api/chat/rag/profiles
 */
const getRAGProfiles = async (req, res) => {
  try {
    logger.info("Fetching RAG profiles", { userId: req.user?.id, companyId: req.user?.companyId, role: req.user?.role });

    const result = await ragService.getProfiles(req.user?.companyId, req.user?.role);

    res.json({
      success: result.success,
      message: "RAG profiles fetched",
      data: result,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("Get RAG profiles error", {
      error: error.message,
      stack: error.stack,
    });

    res.status(500).json({
      success: false,
      error: {
        message: "Failed to fetch RAG profiles",
        code: "RAG_PROFILES_FAILED",
      },
      timestamp: new Date().toISOString(),
    });
  }
};

module.exports = {
  testEndpoint,
  getConversations,
  createConversation,
  getConversation,
  updateConversation,
  deleteConversation,
  getMessages,
  sendMessage,
  testRAGHealth,
  testRAGQuery,
  testRAGChat,
  getRAGProfiles,
};
