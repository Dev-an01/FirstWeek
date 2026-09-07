// backend/chat-service/routes/chatRoutes.js
const express = require("express");
const chatController = require("../controllers/chatController");
const preferencesController = require("../controllers/preferencesController");
const {
  authenticateUser,
  optionalAuth,
} = require("../middleware/authMiddleware");

const router = express.Router();

// =============================================
// Public Routes (for testing)
// =============================================

/**
 * @swagger
 * /test:
 *   get:
 *     tags: [Health]
 *     summary: Test endpoint
 *     description: Simple test endpoint to verify service is running
 *     responses:
 *       200:
 *         description: Service is operational
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                   example: true
 *                 message:
 *                   type: string
 *                   example: Chat Service is running
 */
router.get("/test", chatController.testEndpoint);

// =============================================
// RAG Integration Test Routes (public for testing)
// =============================================

/**
 * @swagger
 * /rag/health:
 *   get:
 *     tags: [RAG Integration]
 *     summary: Check RAG API health
 *     description: Verify that the RAG API service is accessible and responding
 *     responses:
 *       200:
 *         description: RAG API is healthy
 *       500:
 *         description: RAG API is unreachable
 */
router.get("/rag/health", chatController.testRAGHealth);

/**
 * @swagger
 * /rag/profiles:
 *   get:
 *     tags: [RAG Integration]
 *     summary: Get executive profiles
 *     description: Retrieve list of available executive profiles from RAG API
 *     responses:
 *       200:
 *         description: List of executive profiles
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 data:
 *                   type: array
 *                   items:
 *                     type: object
 *                     properties:
 *                       profile_id:
 *                         type: string
 *                       name:
 *                         type: string
 *                       title:
 *                         type: string
 */
router.get("/rag/profiles", optionalAuth, chatController.getRAGProfiles);

/**
 * @swagger
 * /rag/query:
 *   post:
 *     tags: [RAG Integration]
 *     summary: Test RAG document query
 *     description: Retrieve relevant documents without LLM generation (vector search only)
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [query]
 *             properties:
 *               query:
 *                 type: string
 *                 example: What is our discount policy?
 *               profile_id:
 *                 type: string
 *                 example: exec_003_test
 *               top_k:
 *                 type: integer
 *                 default: 5
 *               min_score:
 *                 type: number
 *                 format: float
 *                 default: 0.6
 *     responses:
 *       200:
 *         description: Documents retrieved successfully
 *       400:
 *         description: Invalid query parameters
 */
router.post("/rag/query", authenticateUser, chatController.testRAGQuery);

/**
 * @swagger
 * /rag/chat:
 *   post:
 *     tags: [RAG Integration]
 *     summary: Test RAG chat with LLM
 *     description: Get AI-generated response using RAG document retrieval + LLM
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [query]
 *             properties:
 *               query:
 *                 type: string
 *                 example: Can you explain our warranty terms?
 *               profile_id:
 *                 type: string
 *                 example: exec_003_test
 *               top_k:
 *                 type: integer
 *                 default: 5
 *               min_score:
 *                 type: number
 *                 format: float
 *                 default: 0.6
 *     responses:
 *       200:
 *         description: AI response generated successfully
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 data:
 *                   type: object
 *                   properties:
 *                     response:
 *                       type: string
 *                     documents:
 *                       type: array
 *                     metadata:
 *                       type: object
 *       400:
 *         description: Invalid request
 */
router.post("/rag/chat", authenticateUser, chatController.testRAGChat);

// =============================================
// User Preferences Routes (require authentication)
// =============================================

/**
 * @swagger
 * /preferences:
 *   get:
 *     tags: [Preferences]
 *     summary: Get user preferences
 *     description: Retrieve current user's RAG preferences
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: Preferences retrieved successfully
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/UserPreferences'
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
router.get(
  "/preferences",
  authenticateUser,
  preferencesController.getPreferences,
);

/**
 * @swagger
 * /preferences:
 *   patch:
 *     tags: [Preferences]
 *     summary: Update user preferences
 *     description: Update RAG preferences for the current user
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               defaultProfileId:
 *                 type: string
 *                 example: exec_003_test
 *               defaultTopK:
 *                 type: integer
 *                 example: 5
 *               defaultMinScore:
 *                 type: number
 *                 format: float
 *                 example: 0.15
 *               language:
 *                 type: string
 *                 example: en
 *               theme:
 *                 type: string
 *                 example: dark
 *     responses:
 *       200:
 *         description: Preferences updated successfully
 *       400:
 *         description: Invalid preferences data
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
router.patch(
  "/preferences",
  authenticateUser,
  preferencesController.updatePreferences,
);

/**
 * @swagger
 * /preferences/reset:
 *   post:
 *     tags: [Preferences]
 *     summary: Reset preferences to defaults
 *     description: Reset all user preferences to default values
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: Preferences reset successfully
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
router.post(
  "/preferences/reset",
  authenticateUser,
  preferencesController.resetPreferences,
);

// =============================================
// Conversation Routes (require authentication)
// =============================================

/**
 * @swagger
 * /conversations:
 *   get:
 *     tags: [Conversations]
 *     summary: Get user conversations
 *     description: Retrieve all conversations for the authenticated user with pagination
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: query
 *         name: limit
 *         schema:
 *           type: integer
 *           default: 20
 *         description: Number of conversations to return
 *       - in: query
 *         name: offset
 *         schema:
 *           type: integer
 *           default: 0
 *         description: Number of conversations to skip
 *     responses:
 *       200:
 *         description: Conversations retrieved successfully
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 data:
 *                   type: array
 *                   items:
 *                     $ref: '#/components/schemas/Conversation'
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
router.get("/conversations", authenticateUser, chatController.getConversations);

/**
 * @swagger
 * /conversations:
 *   post:
 *     tags: [Conversations]
 *     summary: Create new conversation
 *     description: Create a new chat conversation for the authenticated user
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     requestBody:
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               title:
 *                 type: string
 *                 example: New Chat
 *     responses:
 *       201:
 *         description: Conversation created successfully
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Conversation'
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
router.post(
  "/conversations",
  authenticateUser,
  chatController.createConversation,
);

/**
 * @swagger
 * /conversations/{id}:
 *   get:
 *     tags: [Conversations]
 *     summary: Get conversation by ID
 *     description: Retrieve a specific conversation by its ID
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *         description: Conversation ID
 *     responses:
 *       200:
 *         description: Conversation retrieved successfully
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Conversation'
 *       404:
 *         description: Conversation not found
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
router.get(
  "/conversations/:id",
  authenticateUser,
  chatController.getConversation,
);

/**
 * @swagger
 * /conversations/{id}:
 *   patch:
 *     tags: [Conversations]
 *     summary: Update conversation
 *     description: Update conversation details (e.g., title)
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *         description: Conversation ID
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               title:
 *                 type: string
 *                 example: Updated Chat Title
 *     responses:
 *       200:
 *         description: Conversation updated successfully
 *       404:
 *         description: Conversation not found
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
router.patch(
  "/conversations/:id",
  authenticateUser,
  chatController.updateConversation,
);

/**
 * @swagger
 * /conversations/{id}:
 *   delete:
 *     tags: [Conversations]
 *     summary: Delete conversation
 *     description: Delete a conversation and all its messages
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *         description: Conversation ID
 *     responses:
 *       200:
 *         description: Conversation deleted successfully
 *       404:
 *         description: Conversation not found
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
router.delete(
  "/conversations/:id",
  authenticateUser,
  chatController.deleteConversation,
);

// =============================================
// Message Routes (require authentication)
// =============================================

/**
 * @swagger
 * /conversations/{id}/messages:
 *   get:
 *     tags: [Messages]
 *     summary: Get conversation messages
 *     description: Retrieve all messages for a specific conversation with pagination
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *         description: Conversation ID
 *       - in: query
 *         name: limit
 *         schema:
 *           type: integer
 *           default: 50
 *         description: Number of messages to return
 *       - in: query
 *         name: offset
 *         schema:
 *           type: integer
 *           default: 0
 *         description: Number of messages to skip
 *     responses:
 *       200:
 *         description: Messages retrieved successfully
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 data:
 *                   type: array
 *                   items:
 *                     $ref: '#/components/schemas/Message'
 *       404:
 *         description: Conversation not found
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
router.get(
  "/conversations/:id/messages",
  authenticateUser,
  chatController.getMessages,
);

/**
 * @swagger
 * /conversations/{id}/messages:
 *   post:
 *     tags: [Messages]
 *     summary: Send message (HTTP fallback)
 *     description: Send a message in a conversation (HTTP fallback - prefer WebSocket for real-time)
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *         description: Conversation ID
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [content]
 *             properties:
 *               content:
 *                 type: string
 *                 example: What is your return policy?
 *               ragOptions:
 *                 type: object
 *                 properties:
 *                   profileId:
 *                     type: string
 *                     example: exec_003_test
 *                   topK:
 *                     type: integer
 *                     default: 5
 *                   minScore:
 *                     type: number
 *                     format: float
 *                     default: 0.6
 *     responses:
 *       201:
 *         description: Message sent and response generated
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 data:
 *                   type: object
 *                   properties:
 *                     userMessage:
 *                       $ref: '#/components/schemas/Message'
 *                     assistantMessage:
 *                       $ref: '#/components/schemas/Message'
 *       400:
 *         description: Invalid message content
 *       404:
 *         description: Conversation not found
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
router.post(
  "/conversations/:id/messages",
  authenticateUser,
  chatController.sendMessage,
);

module.exports = router;
