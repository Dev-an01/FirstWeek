const logger = require("../utils/logger");

/**
 * Global error handling middleware
 */
// eslint-disable-next-line no-unused-vars
function errorHandler(err, req, res, next) {
  logger.error("[ErrorHandler] Unhandled error:", err);

  const statusCode = err.statusCode || 500;
  const message = err.message || "Internal server error";

  res.status(statusCode).json({
    error: message,
    ...(process.env.NODE_ENV === "development" && { stack: err.stack }),
  });
}

module.exports = errorHandler;
