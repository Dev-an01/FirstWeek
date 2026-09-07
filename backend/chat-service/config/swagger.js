// backend/chat-service/config/swagger.js

const swaggerJsdoc = require("swagger-jsdoc");
const path = require("path");

const options = {
  definition: {
    openapi: "3.0.0",
    info: {
      title: "Chat Service API",
      version: "1.0.0",
      description: `
# Chat Service API

Real-time messaging service with RAG (Retrieval Augmented Generation) integration.

## Features

- **Conversations**: Create and manage chat conversations
- **Messages**: Send messages and receive AI-powered responses
- **Real-time**: WebSocket support via Socket.IO (see WebSocket section)
- **RAG Integration**: Intelligent document retrieval and LLM responses
- **Preferences**: Customize RAG behavior per user

## WebSocket Events

For real-time messaging, use Socket.IO:

### Client → Server
\`\`\`javascript
socket.emit('chat:join', { conversationId })
socket.emit('chat:message', { conversationId, content, ragOptions })
socket.emit('chat:typing', { conversationId, isTyping })
\`\`\`

### Server → Client
\`\`\`javascript
socket.on('message:created', (data) => {})
socket.on('user:typing', (data) => {})
socket.on('user:joined', (data) => {})
\`\`\`

## Authentication

All endpoints require JWT authentication:
- **Cookie**: \`firstweek_avatar_access_token\`
- **Header**: \`Authorization: Bearer <token>\`

Obtain tokens from Auth Service (\`POST /api/users/login\`)

## Base URL

\`http://localhost:3002/api/chat\`
      `,
      contact: {
        name: "FIRSTWEEK Team",
        email: "support@example.invalid",
      },
      license: {
        name: "ISC",
      },
    },
    servers: [
      {
        url: "http://localhost:3002/api/chat",
        description: "Development Server",
      },
      {
        url: "https://api.example.invalid/api/chat",
        description: "Production Server",
      },
    ],
    tags: [
      {
        name: "Conversations",
        description: "Chat conversation CRUD operations",
      },
      {
        name: "Messages",
        description: "Message sending and retrieval",
      },
      {
        name: "Preferences",
        description: "User preference management",
      },
      {
        name: "RAG Integration",
        description: "RAG API testing endpoints",
      },
      {
        name: "Health",
        description: "Service health checks",
      },
    ],
    components: {
      securitySchemes: {
        bearerAuth: {
          type: "http",
          scheme: "bearer",
          bearerFormat: "JWT",
        },
        cookieAuth: {
          type: "apiKey",
          in: "cookie",
          name: "firstweek_avatar_access_token",
        },
      },
      schemas: {
        Conversation: {
          type: "object",
          properties: {
            id: { type: "string", example: "conv_123abc" },
            userId: { type: "string" },
            title: { type: "string", example: "New Chat" },
            createdAt: { type: "string", format: "date-time" },
            updatedAt: { type: "string", format: "date-time" },
            lastMessageAt: {
              type: "string",
              format: "date-time",
              nullable: true,
            },
            messageCount: { type: "integer", example: 5 },
          },
        },
        Message: {
          type: "object",
          properties: {
            id: { type: "string" },
            conversationId: { type: "string" },
            role: { type: "string", enum: ["user", "assistant"] },
            content: { type: "string" },
            metadata: { type: "object", nullable: true },
            createdAt: { type: "string", format: "date-time" },
          },
        },
        UserPreferences: {
          type: "object",
          properties: {
            defaultProfileId: { type: "string", example: "exec_003_test" },
            defaultTopK: { type: "integer", default: 5 },
            defaultMinScore: { type: "number", format: "float", default: 0.15 },
            language: { type: "string", default: "en" },
            theme: { type: "string", default: "light" },
          },
        },
        Error: {
          type: "object",
          properties: {
            success: { type: "boolean", example: false },
            error: {
              type: "object",
              properties: {
                message: { type: "string" },
                code: { type: "string" },
              },
            },
          },
        },
      },
      responses: {
        UnauthorizedError: {
          description: "Authentication required",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/Error" },
              example: {
                success: false,
                error: {
                  message: "Authentication required",
                  code: "UNAUTHORIZED",
                },
              },
            },
          },
        },
      },
    },
  },
  apis: [
    path.join(__dirname, "../routes/*.js"),
    path.join(__dirname, "../controllers/*.js"),
  ],
};

const swaggerSpec = swaggerJsdoc(options);

module.exports = swaggerSpec;
