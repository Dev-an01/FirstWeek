const express = require("express");
const { createServer } = require("http");
const { Server } = require("socket.io");
const path = require("path");
const cors = require("cors");
const compression = require("compression");
const cookieParser = require("cookie-parser");
const helmet = require("helmet");
const rateLimit = require("express-rate-limit");

// Global Logger Setup
const swaggerUi = require("swagger-ui-express");
const {
  createLogger,
  createMorganMiddleware,
  errorLoggingMiddleware,
  requestTimingMiddleware,
  // eslint-disable-next-line
} = require('./shared/utils/logger');

// Initialize logger for chat-service
const logger = createLogger("chat-service", process.env.LOG_LEVEL || "info");

// Database configuration
const {
  disconnectDatabase,
  healthCheck,
  initializeDatabase,
} = require("./config/database");

// Routes
const chatRoutes = require("./routes/chatRoutes");

// Load environment variables
require("dotenv").config({
  path: path.resolve(__dirname, "../../.env"),
});

const app = express();
const httpServer = createServer(app);

// =============================================
// Socket.IO Configuration
// =============================================

// Build allowed origins for CORS
const allowedOrigins = [
  process.env.FRONTEND_URL || "http://localhost:5173",
  "http://localhost:5173",
];

if (process.env.HOST) {
  allowedOrigins.push(`http://${process.env.HOST}:5173`);
}

const io = new Server(httpServer, {
  cors: {
    origin: allowedOrigins,
    credentials: true,
    methods: ["GET", "POST"],
    allowedHeaders: ["Content-Type", "Authorization", "Cookie"],
  },
  pingTimeout: 60000,
  pingInterval: 25000,
  transports: ["websocket", "polling"], // Support both transports
});

// Make io accessible to routes/controllers
app.set("io", io);

// Make io accessible to message service for emitting events
const messageService = require("./services/messageService");

messageService.setSocketIO(io);

// =============================================
// Logging Middleware (Must be first!)
// =============================================

// Request timing middleware
app.use(requestTimingMiddleware(logger));

// Morgan HTTP request logging
app.use(createMorganMiddleware(logger));

// =============================================
// Security Middleware
// =============================================

// Helmet for security headers
app.use(
  helmet({
    crossOriginResourcePolicy: { policy: "cross-origin" },
  }),
);

// CORS configuration - support multiple origins for remote access
app.use(
  cors({
    // eslint-disable-next-line
    origin: function (origin, callback) {
      // Allow requests with no origin (like mobile apps or curl requests)
      if (!origin) return callback(null, true);

      if (allowedOrigins.indexOf(origin) !== -1) {
        callback(null, true);
      } else {
        logger.warn(`CORS blocked origin: ${origin}`, { allowedOrigins });
        callback(new Error("Not allowed by CORS"));
      }
    },
    credentials: true,
    methods: ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization", "Cookie"],
  }),
);

// Compression middleware
app.use(compression());

// =============================================
// Rate Limiting
// =============================================

// General rate limiting
const generalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Limit each IP to 100 requests per windowMs
  message: {
    success: false,
    error: {
      message: "Too many requests, please try again later.",
      code: "RATE_LIMIT_EXCEEDED",
    },
  },
  standardHeaders: true,
  legacyHeaders: false,
  onLimitReached: (req) => {
    logger.security("RATE_LIMIT_HIT", "General rate limit exceeded", {
      ip: req.ip,
      userAgent: req.get("User-Agent"),
    });
  },
});

// Apply general rate limiting
app.use(generalLimiter);

// =============================================
// Body Parsing Middleware
// =============================================

app.use(
  express.json({
    limit: "10mb",
    strict: true,
  }),
);

app.use(
  express.urlencoded({
    extended: true,
    limit: "10mb",
  }),
);

// Cookie parser
app.use(cookieParser());

// =============================================
// Swagger Documentation
// =============================================
const swaggerSpec = require("./config/swagger");

app.use(
  "/api-docs",
  swaggerUi.serve,
  swaggerUi.setup(swaggerSpec, {
    customCss: ".swagger-ui .topbar { display: none }",
    customSiteTitle: "Chat Service API Docs",
  }),
);

app.get("/api-docs.json", (req, res) => {
  res.setHeader("Content-Type", "application/json");
  res.send(swaggerSpec);
});

logger.info("📚 Swagger UI available at http://localhost:3002/api-docs");

// =============================================
// Routes
// =============================================

// Welcome route
app.get("/", (req, res) => {
  logger.info("Welcome page accessed", { ip: req.ip });

  res.json({
    success: true,
    message: "Welcome to the FirstWeek Chat-Service API",
    service: "chat-service",
    version: "1.0.0",
    environment: process.env.NODE_ENV || "development",
    documentation: {
      health: "/health",
      apiBase: "/api/chat",
      endpoints: {
        conversations: [
          "GET /api/chat/conversations",
          "POST /api/chat/conversations",
          "GET /api/chat/conversations/:id",
          "DELETE /api/chat/conversations/:id",
        ],
        messages: [
          "GET /api/chat/conversations/:id/messages",
          "POST /api/chat/conversations/:id/messages",
        ],
        websocket: [
          "Socket.IO connection at /socket.io",
          "Events: chat:join, chat:message, chat:typing",
        ],
      },
    },
    timestamp: new Date().toISOString(),
  });
});

// Health check endpoint
app.get("/health", async (req, res) => {
  try {
    logger.debug("Health check requested", { ip: req.ip });

    // Check database health
    const dbHealth = await healthCheck();

    const healthData = {
      success: true,
      status: "OK",
      service: "chat-service",
      database: dbHealth,
      uptime: process.uptime(),
      memory: {
        used:
          Math.round((process.memoryUsage().heapUsed / 1024 / 1024) * 100) /
          100,
        total:
          Math.round((process.memoryUsage().heapTotal / 1024 / 1024) * 100) /
          100,
      },
      websocket: {
        connected: io.engine.clientsCount,
      },
      environment: process.env.NODE_ENV || "development",
      timestamp: new Date().toISOString(),
    };

    logger.info("Health check successful", {
      status: healthData.status,
      uptime: healthData.uptime,
      memoryUsed: healthData.memory.used,
      websocketClients: healthData.websocket.connected,
    });

    res.json(healthData);
  } catch (error) {
    logger.error("Health check failed", {
      error: error.message,
      stack: error.stack,
    });

    res.status(500).json({
      success: false,
      status: "ERROR",
      service: "chat-service",
      error: error.message,
      timestamp: new Date().toISOString(),
    });
  }
});

// Chat API routes
app.use("/api/chat", chatRoutes);

// Error logging middleware
app.use(errorLoggingMiddleware(logger));

// =============================================
// Socket.IO Connection Handling
// =============================================

const { socketAuthMiddleware } = require("./websocket/auth");
const { registerChatHandlers } = require("./websocket/chatHandlers");

// Apply authentication middleware to Socket.IO
io.use(socketAuthMiddleware);

// Handle authenticated connections
io.on("connection", (socket) => {
  logger.info("Socket.IO client connected (authenticated)", {
    socketId: socket.id,
    userId: socket.user.id,
    username: socket.user.username,
    role: socket.user.role,
    transport: socket.conn.transport.name,
  });

  // Send welcome message with user info
  socket.emit("connected", {
    success: true,
    message: "Connected to chat service",
    data: {
      socketId: socket.id,
      user: {
        id: socket.user.id,
        username: socket.user.username,
        role: socket.user.role,
      },
    },
    timestamp: new Date().toISOString(),
  });

  // Register chat event handlers
  registerChatHandlers(io, socket);

  // Basic ping-pong for connection testing
  socket.on("ping", () => {
    logger.debug("Received ping from client", {
      socketId: socket.id,
      userId: socket.user.id,
    });
    socket.emit("pong", {
      timestamp: Date.now(),
      userId: socket.user.id,
    });
  });
});

// =============================================
// Server Startup Function
// =============================================

const startServer = async () => {
  const port = process.env.CHAT_SERVICE_PORT || 3002;

  try {
    // Initialize database connection
    logger.info("Initializing database connection...");
    await initializeDatabase();
    logger.info("Database connection established successfully");

    // Start server
    httpServer.listen(port, () => {
      logger.info("FirstWeek Chat Service started successfully", {
        port: port,
        environment: process.env.NODE_ENV || "development",
        apiBase: `http://localhost:${port}/api/chat`,
        health: `http://localhost:${port}/health`,
        socketIO: `ws://localhost:${port}`,
      });

      // Log available routes in development
      if (process.env.NODE_ENV !== "production") {
        logger.debug("Available API Routes:", {
          health: "GET /health",
          welcome: "GET /",
          conversations: [
            "GET /api/chat/conversations",
            "POST /api/chat/conversations",
            "GET /api/chat/conversations/:id",
            "DELETE /api/chat/conversations/:id",
          ],
          messages: [
            "GET /api/chat/conversations/:id/messages",
            "POST /api/chat/conversations/:id/messages",
          ],
          websocket: "Socket.IO at /socket.io",
        });
      }
    });

    // Store server reference for graceful shutdown
    app.server = httpServer;
  } catch (error) {
    logger.error("Failed to start server", {
      error: error.message,
      stack: error.stack,
    });
    process.exit(1);
  }
};

// =============================================
// Graceful Shutdown Handlers
// =============================================

const gracefulShutdown = async (signal) => {
  logger.info(`Received ${signal}. Shutting down gracefully...`);

  try {
    // Close WebSocket connections
    logger.info("Closing WebSocket connections...");
    io.close(() => {
      logger.info("WebSocket server closed successfully");
    });

    // Close HTTP server
    if (app.server) {
      logger.info("Closing HTTP server...");
      app.server.close(() => {
        logger.info("HTTP server closed successfully");
      });
    }

    // Close database connection
    logger.info("Closing database connection...");
    await disconnectDatabase();
    logger.info("Database connection closed successfully");

    logger.info("Graceful shutdown completed");
    process.exit(0);
  } catch (error) {
    logger.error("Error during shutdown", {
      error: error.message,
      stack: error.stack,
    });
    process.exit(1);
  }
};

// Handle shutdown signals
process.on("SIGTERM", () => gracefulShutdown("SIGTERM"));
process.on("SIGINT", () => gracefulShutdown("SIGINT"));

// Handle uncaught exceptions
process.on("uncaughtException", (error) => {
  logger.error("Uncaught Exception", {
    error: error.message,
    stack: error.stack,
  });
  gracefulShutdown("UNCAUGHT_EXCEPTION");
});

// Handle unhandled promise rejections
process.on("unhandledRejection", (reason, promise) => {
  logger.error("Unhandled Rejection", {
    reason: reason,
    promise: promise,
  });
  gracefulShutdown("UNHANDLED_REJECTION");
});

// Export for testing
module.exports = { app, httpServer, io, logger };

// Start the server
startServer();
