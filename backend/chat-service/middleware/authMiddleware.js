// backend/chat-service/middleware/authMiddleware.js
const jwt = require("jsonwebtoken");
const axios = require("axios");
const {
  AuthenticationError,
  transformError,
  // eslint-disable-next-line
} = require('../shared/utils/errors');
const {
  createLogger,
  // eslint-disable-next-line
} = require('../shared/utils/logger');

const logger = createLogger("auth-middleware", process.env.LOG_LEVEL || "info");

/**
 * Get client IP address from request
 * @param {Object} req - Express request object
 * @returns {string} Client IP address
 */
const getClientIP = (req) => {
  return req.ip || req.connection.remoteAddress || req.socket.remoteAddress;
};

/**
 * Extract token from request (header or cookie)
 * @param {Object} req - Express request object
 * @returns {string|null} Token if found
 */
const extractToken = (req) => {
  // Check Authorization header first
  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith("Bearer ")) {
    return authHeader.substring(7);
  }

  // Check cookies (use the actual cookie name set by auth-service)
  const cookieToken = req.cookies?.firstweek_avatar_access_token;
  if (cookieToken) {
    return cookieToken;
  }

  return null;
};

/**
 * Authenticate user middleware
 * Validates JWT token and adds user info to request
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next function
 */
const authenticateUser = async (req, res, next) => {
  try {
    const token = extractToken(req);
    const clientIP = getClientIP(req);

    if (!token) {
      throw AuthenticationError("Authentication token required", "NO_TOKEN");
    }

    // Verify JWT token
    let decoded;
    try {
      decoded = jwt.verify(token, process.env.JWT_ACCESS_SECRET);
    } catch (jwtError) {
      logger.error("JWT verification failed:", jwtError.message);
      throw AuthenticationError("Invalid or expired token", "INVALID_TOKEN");
    }

    // Add user info to request object
    req.user = {
      id: decoded.userId,
      username: decoded.username,
      email: decoded.email,
      role: decoded.role, // Include role for RBAC
      companyId: decoded.companyId, // Include companyId for tenant isolation
    };
    req.token = token;
    req.clientIP = clientIP;

    logger.debug(`User authenticated successfully: ${decoded.userId} (company: ${decoded.companyId})`);
    next();
  } catch (error) {
    const transformedError = transformError(error);
    logger.error("Authentication failed:", transformedError);

    return res.status(transformedError.statusCode || 401).json({
      success: false,
      error: {
        message: transformedError.message,
        code: transformedError.code,
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Optional authentication middleware
 * Validates JWT token if present, but doesn't fail if missing
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next function
 */
const optionalAuth = async (req, res, next) => {
  try {
    const token = extractToken(req);
    const clientIP = getClientIP(req);

    req.clientIP = clientIP;

    if (!token) {
      // No token, continue without authentication
      return next();
    }

    // Try to verify token, but don't fail if invalid
    try {
      const decoded = jwt.verify(token, process.env.JWT_ACCESS_SECRET);
      req.user = {
        id: decoded.userId,
        username: decoded.username,
        email: decoded.email,
        role: decoded.role, // Include role for RBAC
        companyId: decoded.companyId, // Include companyId for tenant isolation
      };
      req.token = token;
    } catch (jwtError) {
      // Token invalid, but that's okay for optional auth
      logger.debug("Optional auth: invalid token, continuing without auth");
    }

    next();
  } catch (error) {
    // For optional auth, errors should not block the request
    logger.error("Optional auth error:", error);
    next();
  }
};

/**
 * Validate token with auth service (HTTP call)
 * This can be used as a fallback or for extra validation
 * @param {string} token - JWT token to validate
 * @returns {Promise<Object>} User info if valid
 */
const validateTokenWithAuthService = async (token) => {
  try {
    const authServiceUrl =
      process.env.AUTH_SERVICE_URL || "http://auth-service:3001";
    const response = await axios.post(
      `${authServiceUrl}/api/users/validate-token`,
      {},
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    return response.data.data;
  } catch (error) {
    throw AuthenticationError(
      "Token validation with auth service failed",
      "AUTH_SERVICE_ERROR",
    );
  }
};

module.exports = {
  authenticateUser,
  optionalAuth,
  extractToken,
  getClientIP,
  validateTokenWithAuthService,
};
