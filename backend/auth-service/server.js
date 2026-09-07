const express = require("express");
const path = require("path");
const cors = require("cors");
const compression = require("compression");
const cookieParser = require("cookie-parser");
const helmet = require("helmet");
const rateLimit = require("express-rate-limit");
const swaggerUi = require("swagger-ui-express");
const passwordResetController = require("./controllers/passwordResetController");
// Global Logger Setup
const {
  createLogger,
  createMorganMiddleware,
  errorLoggingMiddleware,
  requestTimingMiddleware,
  // eslint-disable-next-line
} = require('./shared/utils/logger');

// Initialize logger for auth-service
const logger = createLogger("auth-service", process.env.LOG_LEVEL || "info");

// Database configuration
const {
  disconnectDatabase,
  healthCheck,
  initializeDatabase,
} = require("./config/database");

// Routes
const userRoutes = require("./routes/userRoutes");
const companyRoutes = require("./routes/companyRoutes");
const inviteCodeRoutes = require("./routes/inviteCodeRoutes");

// Load environment variables
require("dotenv").config({
  path: path.resolve(__dirname, "../../.env"),
});

const app = express();
app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "templates"));
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
const allowedOrigins = [
  process.env.FRONTEND_URL || "http://localhost:5173",
  "http://localhost:5173", // Always allow localhost
];

// Add server IP origin if HOST env variable is set
if (process.env.HOST) {
  allowedOrigins.push(`http://${process.env.HOST}:5173`);
}

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
    credentials: true, // Important for cookies
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

// Stricter rate limiting for auth endpoints
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 20, // Limit each IP to 20 auth requests per windowMs
  message: {
    success: false,
    error: {
      message: "Too many authentication attempts, please try again later.",
      code: "AUTH_RATE_LIMIT_EXCEEDED",
    },
  },
  standardHeaders: true,
  legacyHeaders: false,
  onLimitReached: (req) => {
    logger.security("AUTH_RATE_LIMIT_HIT", "Auth rate limit exceeded", {
      ip: req.ip,
      userAgent: req.get("User-Agent"),
      endpoint: req.originalUrl,
    });
  },
});

// Apply rate limiting (skip in test mode)
if (process.env.TEST_MODE !== "true") {
  app.use(generalLimiter);
  app.use("/api/users/login", authLimiter);
  app.use("/api/users/register", authLimiter);
  app.use("/api/users/refresh", authLimiter);
  logger.info("Rate limiting enabled");
} else {
  logger.warn("Rate limiting DISABLED - TEST_MODE active");
}

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

// Cookie parser for JWT tokens
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
    customSiteTitle: "Auth Service API Docs",
  }),
);

app.get("/api-docs.json", (req, res) => {
  res.setHeader("Content-Type", "application/json");
  res.send(swaggerSpec);
});

logger.info("📚 Swagger UI available at http://localhost:3001/api-docs");

// =============================================
// Routes
// =============================================
app.get("/reset-password", passwordResetController.renderResetPasswordPage);
// Welcome route
app.get("/", (req, res) => {
  logger.info("Welcome page accessed", { ip: req.ip });

  res.json({
    success: true,
    message: "Welcome to the FirstWeek Auth-Service API",
    service: "auth-service",
    version: "1.0.0",
    environment: process.env.NODE_ENV || "development",
    documentation: {
      health: "/health",
      apiBase: "/api/users",
      endpoints: {
        auth: [
          "POST /api/users/register",
          "POST /api/users/login",
          "POST /api/users/logout",
          "POST /api/users/refresh",
        ],
        profile: [
          "GET /api/users/me",
          "PUT /api/users/me",
          "POST /api/users/change-password",
        ],
        sessions: ["GET /api/users/sessions", "DELETE /api/users/sessions/:id"],
        utility: [
          "POST /api/users/check-email",
          "POST /api/users/check-username",
          "GET /api/users/health",
        ],
      },
    },
    timestamp: new Date().toISOString(),
  });
});

// Health check endpoint (enhanced version)
app.get("/health", async (req, res) => {
  try {
    logger.debug("Health check requested", { ip: req.ip });
    const dbHealth = await healthCheck();

    const healthData = {
      success: true,
      status: "OK",
      service: "auth-service",
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
      environment: process.env.NODE_ENV || "development",
      timestamp: new Date().toISOString(),
    };

    logger.info("Health check successful", {
      status: healthData.status,
      uptime: healthData.uptime,
      memoryUsed: healthData.memory.used,
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
      service: "auth-service",
      error: error.message,
      timestamp: new Date().toISOString(),
    });
  }
});

// User API routes
app.use("/api/users", userRoutes);

// Company management routes
app.use("/api/companies", companyRoutes);
app.use("/api/firstweek", require("./routes/firstweekRoutes"));

// Invite code routes
app.use("/api/invite-codes", inviteCodeRoutes);

// Error logging middleware
app.use(errorLoggingMiddleware(logger));

// =============================================
// Server Startup Function
// =============================================

const startServer = async () => {
  const port = process.env.AUTH_SERVICE_PORT || 3001;

  try {
    // Initialize database connection
    logger.info("Initializing database connection...");
    await initializeDatabase();
    logger.info("Database connection established successfully");

    // Start server
    const server = app.listen(port, () => {
      logger.info("FirstWeek Auth Service started successfully", {
        port: port,
        environment: process.env.NODE_ENV || "development",
        apiBase: `http://localhost:${port}/api/users`,
        health: `http://localhost:${port}/health`,
      });

      // Sync executives to onboarding service after server is listening (fire-and-forget)
      setTimeout(() => {
        const onboardingService = require("./services/onboardingService");
        onboardingService.syncAllExecutives().then((result) => {
          logger.info("Startup executive sync completed", result);
        }).catch((err) => {
          logger.error("Startup executive sync failed (non-fatal)", { error: err.message });
        });
      }, 5000); // 5s delay to let onboarding service be ready

      // Log available routes in development
      if (process.env.NODE_ENV !== "production") {
        logger.debug("Available API Routes:", {
          auth: [
            "POST /api/users/register",
            "POST /api/users/login",
            "POST /api/users/logout",
            "POST /api/users/logout-all",
            "POST /api/users/refresh",
          ],
          profile: [
            "GET /api/users/me",
            "PUT /api/users/me",
            "POST /api/users/change-password",
          ],
          sessions: [
            "GET /api/users/sessions",
            "DELETE /api/users/sessions/:id",
          ],
          utility: [
            "POST /api/users/check-email",
            "POST /api/users/check-username",
            "GET /api/users/health",
          ],
        });
      }
    });

    // Store server reference for graceful shutdown
    app.server = server;
  } catch (error) {
    logger.error("Failed to start server", {
      error: error.message,
      stack: error.stack,
    });
    await disconnectDatabase();
    process.exit(1);
  }
};

// =============================================
// Graceful Shutdown Handlers
// =============================================

const gracefulShutdown = async (signal) => {
  logger.info(`Received ${signal}. Shutting down gracefully...`);

  try {
    // Close server
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

// Export logger for use in other modules
module.exports = { app, logger };

// Start the server
startServer();
