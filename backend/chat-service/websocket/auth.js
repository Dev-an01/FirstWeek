// backend/chat-service/websocket/auth.js

const jwt = require("jsonwebtoken");
const { createLogger } = require("../shared/utils/logger");

const logger = createLogger("websocket-auth", process.env.LOG_LEVEL || "info");

/**
 * Extract token from Socket.IO handshake
 * Supports: cookies, auth.token, and query.token
 * @param {Object} socket - Socket.IO socket instance
 * @returns {string|null} Token if found
 */
const extractSocketToken = (socket) => {
  // Method 1: Check auth.token (most common for Socket.IO client)
  if (socket.handshake.auth && socket.handshake.auth.token) {
    return socket.handshake.auth.token;
  }

  // Method 2: Check query parameters
  if (socket.handshake.query && socket.handshake.query.token) {
    return socket.handshake.query.token;
  }

  // Method 3: Check cookies (if cookie-parser is used)
  const cookies = socket.handshake.headers.cookie;
  if (cookies) {
    const cookieArray = cookies.split(";");
    for (const cookie of cookieArray) {
      const [name, value] = cookie.trim().split("=");
      if (name === "firstweek_avatar_access_token") {
        return value;
      }
    }
  }

  return null;
};

/**
 * Socket.IO authentication middleware
 * Validates JWT token and attaches user data to socket
 * @param {Object} socket - Socket.IO socket instance
 * @param {Function} next - Next middleware function
 */
const socketAuthMiddleware = (socket, next) => {
  try {
    // Debug logging
    logger.debug("WebSocket handshake received", {
      auth: socket.handshake.auth,
      query: socket.handshake.query,
      cookies: socket.handshake.headers.cookie,
      headers: Object.keys(socket.handshake.headers),
    });

    const token = extractSocketToken(socket);

    if (!token) {
      logger.warn("WebSocket connection attempt without token", {
        socketId: socket.id,
        ip: socket.handshake.address,
        auth: socket.handshake.auth,
        query: socket.handshake.query,
        hasCookies: !!socket.handshake.headers.cookie,
      });
      return next(new Error("Authentication token required"));
    }

    // Verify JWT token
    let decoded;
    try {
      decoded = jwt.verify(token, process.env.JWT_ACCESS_SECRET);
    } catch (jwtError) {
      logger.error("WebSocket JWT verification failed", {
        error: jwtError.message,
        socketId: socket.id,
      });
      return next(new Error("Invalid or expired token"));
    }

    // Attach user data to socket
    socket.user = {
      id: decoded.userId,
      username: decoded.username,
      email: decoded.email,
      role: decoded.role, // For RBAC
      companyId: decoded.companyId, // For tenant isolation
    };

    logger.info("WebSocket user authenticated", {
      socketId: socket.id,
      userId: socket.user.id,
      username: socket.user.username,
      role: socket.user.role,
    });

    next();
  } catch (error) {
    logger.error("WebSocket authentication error", {
      error: error.message,
      socketId: socket.id,
    });
    next(new Error("Authentication failed"));
  }
};

/**
 * Optional authentication for public namespaces
 * Attaches user if token is valid, but allows connection without token
 * @param {Object} socket - Socket.IO socket instance
 * @param {Function} next - Next middleware function
 */
const optionalSocketAuth = (socket, next) => {
  try {
    const token = extractSocketToken(socket);

    if (!token) {
      // No token - proceed as guest
      socket.user = null;
      logger.debug("WebSocket connection without authentication (guest)", {
        socketId: socket.id,
      });
      return next();
    }

    // Token present - try to verify
    try {
      const decoded = jwt.verify(token, process.env.JWT_ACCESS_SECRET);
      socket.user = {
        id: decoded.userId,
        username: decoded.username,
        email: decoded.email,
        role: decoded.role,
        companyId: decoded.companyId, // For tenant isolation
      };

      logger.info("WebSocket optional auth successful", {
        socketId: socket.id,
        userId: socket.user.id,
      });
    } catch (jwtError) {
      // Invalid token - proceed as guest but log warning
      logger.warn("WebSocket invalid token, proceeding as guest", {
        error: jwtError.message,
        socketId: socket.id,
      });
      socket.user = null;
    }

    next();
  } catch (error) {
    logger.error("WebSocket optional auth error", {
      error: error.message,
      socketId: socket.id,
    });
    // Even on error, allow connection for optional auth
    socket.user = null;
    next();
  }
};

module.exports = {
  socketAuthMiddleware,
  optionalSocketAuth,
  extractSocketToken,
};
