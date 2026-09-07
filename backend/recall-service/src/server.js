require("dotenv").config();
const express = require("express");
const bodyParser = require("body-parser");
const cors = require("cors");
const morgan = require("morgan");
const helmet = require("helmet");
const logger = require("./utils/logger");
const errorHandler = require("./middleware/error-handler");

// Routes
const botRoutes = require("./routes/bot.routes");
const webhookRoutes = require("./routes/webhook.routes");

// Initialize Express app
const app = express();
const PORT = process.env.PORT || 3003;

// Middleware
app.use(helmet()); // Security headers
app.use(cors()); // Enable CORS
app.use(bodyParser.json()); // Parse JSON bodies
app.use(bodyParser.urlencoded({ extended: true }));
app.use(morgan("combined")); // HTTP request logging

// Health check endpoint
app.get("/health", (req, res) => {
  res.json({
    status: "healthy",
    service: "recall-service",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
  });
});

// API routes
app.use("/api/bot", botRoutes);
app.use("/api/webhook", webhookRoutes);

// Root endpoint
app.get("/", (req, res) => {
  res.json({
    service: "FirstWeek Recall Service",
    version: "1.0.0",
    endpoints: {
      health: "/health",
      createBot: "POST /api/bot/create",
      getBot: "GET /api/bot/:botId",
      deleteBot: "DELETE /api/bot/:botId",
      listBots: "GET /api/bot",
      processTranscript: "POST /api/bot/:botId/process-transcript",
      webhook: "POST /api/webhook/recall",
    },
  });
});

// Error handling middleware (must be last)
app.use(errorHandler);

// Start server
const server = app.listen(PORT, () => {
  logger.info("=".repeat(60));
  logger.info("🤖 FirstWeek Recall Service");
  logger.info("=".repeat(60));
  logger.info(`✅ Server running on port ${PORT}`);
  logger.info(`📍 Environment: ${process.env.NODE_ENV || "development"}`);
  logger.info(
    `🌐 Avatar Interface URL: ${process.env.AVATAR_INTERFACE_URL || "Not configured"}`,
  );
  logger.info(
    `🎯 RAG API URL: ${process.env.RAG_API_URL || "http://rag-api:8000"}`,
  );
  logger.info("=".repeat(60));
});

// Graceful shutdown
process.on("SIGTERM", () => {
  logger.info("SIGTERM signal received: closing HTTP server");
  server.close(() => {
    logger.info("HTTP server closed");
  });
});
