// shared/utils/logger.js
const winston = require("winston");
const morgan = require("morgan");
const path = require("path");
require("colors");

// Custom log levels
const logLevels = {
  error: 0,
  warn: 1,
  info: 2,
  http: 3,
  debug: 4,
};

// Custom colors for each log level
const logColors = {
  error: "red",
  warn: "yellow",
  info: "green",
  http: "magenta",
  debug: "white",
};

// Tell winston that you want to link the colors
winston.addColors(logColors);

/**
 * Custom format for console output with colors and emojis
 */
const consoleFormat = winston.format.combine(
  winston.format.timestamp({ format: "YYYY-MM-DD HH:mm:ss:ms" }),
  winston.format.colorize({ all: true }),
  winston.format.printf((info) => {
    const { timestamp, level, message, service, ...meta } = info;

    // Add emoji based on log level
    let emoji = "";
    switch (
      // eslint-disable-next-line
      info.level.replace(/\x1b\[[0-9;]*m/g, '')
    ) {
      case "error":
        emoji = "❌";
        break;
      case "warn":
        emoji = "⚠️ ";
        break;
      case "info":
        emoji = "📝";
        break;
      case "http":
        emoji = "🌐";
        break;
      case "debug":
        emoji = "🔍";
        break;
      default:
        emoji = "📄";
        break;
    }

    let logMessage = `${emoji} [${timestamp}] [${level}]`;

    if (service) {
      logMessage += ` [${service}]`;
    }

    logMessage += `: ${message}`;

    // Add metadata if present
    if (Object.keys(meta).length > 0) {
      logMessage += ` ${JSON.stringify(meta, null, 2)}`;
    }

    return logMessage;
  }),
);

/**
 * JSON format for file output
 */
const fileFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.json(),
);

/**
 * Create logger instance
 * @param {string} serviceName - Name of the service using the logger
 * @param {string} logLevel - Log level (default: info)
 * @returns {Object} Winston logger instance
 */
const createLogger = (serviceName = "app", logLevel = "info") => {
  // Determine log level from environment or parameter
  const level = process.env.LOG_LEVEL || logLevel;

  // Create logs directory path
  const logsDir = process.env.LOGS_DIR || path.join(process.cwd(), "logs");

  // Create transports array
  const transports = [
    // Console transport (always enabled in development)
    new winston.transports.Console({
      level: level,
      format: consoleFormat,
    }),
  ];

  // Add file transports only if not in test environment
  if (process.env.NODE_ENV !== "test") {
    transports.push(
      // All logs file
      new winston.transports.File({
        filename: path.join(logsDir, `${serviceName}-combined.log`),
        level: level,
        format: fileFormat,
        maxsize: 5242880, // 5MB
        maxFiles: 5,
        tailable: true,
      }),

      // Error logs file
      new winston.transports.File({
        filename: path.join(logsDir, `${serviceName}-error.log`),
        level: "error",
        format: fileFormat,
        maxsize: 5242880, // 5MB
        maxFiles: 5,
        tailable: true,
      }),
    );
  }

  const logger = winston.createLogger({
    level: level,
    levels: logLevels,
    format: winston.format.combine(
      winston.format.timestamp(),
      winston.format.errors({ stack: true }),
      winston.format.json(),
    ),
    defaultMeta: { service: serviceName },
    transports: transports,
  });

  // Handle uncaught exceptions and unhandled rejections
  logger.exceptions.handle(
    new winston.transports.File({
      filename: path.join(logsDir, `${serviceName}-exceptions.log`),
      format: fileFormat,
    }),
  );

  logger.rejections.handle(
    new winston.transports.File({
      filename: path.join(logsDir, `${serviceName}-rejections.log`),
      format: fileFormat,
    }),
  );

  // Add custom methods for better developer experience
  logger.request = (req, message = "", meta = {}) => {
    logger.http(message || "Request received", {
      method: req.method,
      url: req.originalUrl || req.url,
      ip: req.ip || req.connection?.remoteAddress,
      userAgent: req.get("User-Agent"),
      ...meta,
    });
  };

  logger.response = (req, res, message = "", meta = {}) => {
    logger.http(message || "Response sent", {
      method: req.method,
      url: req.originalUrl || req.url,
      statusCode: res.statusCode,
      responseTime: res.responseTime,
      ...meta,
    });
  };

  logger.database = (operation, message, meta = {}) => {
    logger.debug(`DB ${operation}: ${message}`, meta);
  };

  logger.auth = (action, message, meta = {}) => {
    logger.info(`AUTH ${action}: ${message}`, meta);
  };

  logger.security = (event, message, meta = {}) => {
    logger.warn(`SECURITY ${event}: ${message}`, meta);
  };

  return logger;
};

/**
 * Create Morgan middleware for HTTP request logging
 * @param {Object} logger - Winston logger instance
 * @returns {Function} Morgan middleware
 */
const createMorganMiddleware = (logger) => {
  // Define custom Morgan format
  const morganFormat =
    process.env.NODE_ENV === "production"
      ? "combined"
      : ":remote-addr :method :url :status :res[content-length] - :response-time ms";

  // Create custom stream that writes to our logger
  const stream = {
    write: (message) => {
      // Remove trailing newline and log as http level
      logger.http(message.trim());
    },
  };

  return morgan(morganFormat, {
    stream,
    // Skip logging for health checks in production
    // eslint-disable-next-line no-unused-vars
    skip: (req, res) => {
      if (process.env.NODE_ENV === "production") {
        return req.originalUrl === "/health" || req.originalUrl === "/";
      }
      return false;
    },
  });
};

/**
 * Express error logging middleware
 * @param {Object} logger - Winston logger instance
 * @returns {Function} Express error middleware
 */
const errorLoggingMiddleware = (logger) => {
  return (error, req, res, next) => {
    // Log the error
    logger.error("Express error occurred", {
      error: error.message,
      stack: error.stack,
      url: req.originalUrl,
      method: req.method,
      ip: req.ip,
      userAgent: req.get("User-Agent"),
      body: req.body,
      params: req.params,
      query: req.query,
    });

    next(error);
  };
};

/**
 * Request timing middleware
 * @param {Object} logger - Winston logger instance
 * @returns {Function} Express middleware
 */
const requestTimingMiddleware = (logger) => {
  return (req, res, next) => {
    const start = Date.now();

    // Add response time to res object
    res.on("finish", () => {
      const duration = Date.now() - start;
      res.responseTime = duration;

      // Log slow requests
      if (duration > 1000) {
        logger.warn("Slow request detected", {
          method: req.method,
          url: req.originalUrl,
          duration: `${duration}ms`,
          ip: req.ip,
        });
      }
    });

    next();
  };
};

/**
 * Sanitize sensitive data from logs
 * @param {Object} data - Data to sanitize
 * @returns {Object} Sanitized data
 */
const sanitizeLogData = (data) => {
  const sensitive = ["password", "token", "secret", "key", "authorization"];
  const sanitized = { ...data };

  const sanitizeObject = (obj) => {
    Object.keys(obj).forEach((key) => sanitizeValue(obj, key));
  };
  const sanitizeValue = (obj, key) => {
    if (sensitive.some((s) => key.toLowerCase().includes(s))) {
      obj[key] = "[REDACTED]";
    } else if (typeof obj[key] === "object" && obj[key] !== null) {
      sanitizeObject(obj[key]);
    }
  };

  if (typeof sanitized === "object" && sanitized !== null) {
    sanitizeObject(sanitized);
  }

  return sanitized;
};

module.exports = {
  createLogger,
  createMorganMiddleware,
  errorLoggingMiddleware,
  requestTimingMiddleware,
  sanitizeLogData,
  logLevels,
  logColors,
};
