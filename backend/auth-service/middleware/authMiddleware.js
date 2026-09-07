// backend/admin-module/middleware/authMiddleware.js
const jwt = require("jsonwebtoken");
const userService = require("../services/userService");
const { COOKIE_NAMES } = require("../lib/constants");
const {
  AuthenticationError,
  AuthorizationError,
  transformError,
  ValidationError,
  // eslint-disable-next-line
} = require('../shared/utils/errors');
const {
  createLogger,
  // eslint-disable-next-line
} = require('../shared/utils/logger');

const logger = createLogger("auth-middleware", {
  service: "admin-module",
  level: process.env.LOG_LEVEL || "info",
});

// Import session repository functions
const {
  findSessionByAccessToken,
  validateSessionIP,
  getUserSessions,
} = require("../repositories/sessionRepository");

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
  const cookieToken = req.cookies?.[COOKIE_NAMES.ACCESS_TOKEN];
  if (cookieToken) {
    return cookieToken;
  }

  return null;
};

/**
 * Extract refresh token from request
 * @param {Object} req - Express request object
 * @returns {string|null} Refresh token if found
 */
const extractRefreshToken = (req) => {
  const cookieToken = req.cookies?.[COOKIE_NAMES.REFRESH_TOKEN];
  if (cookieToken) {
    return cookieToken;
  }

  return null;
};

/**
 * Get cookie options for setting authentication cookies
 * @param {boolean} isRefreshToken - Whether the cookie is for a refresh token
 * @returns {Object} Cookie options
 */
const getCookieOptions = (isRefreshToken = false) => {
  // Helper function to check if a string is an IP address
  const isIPAddress = (str) => {
    if (!str) return false;
    return /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(str);
  };

  const cookieDomain = process.env.COOKIE_DOMAIN;

  const baseOptions = {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: process.env.NODE_ENV === "production" ? "strict" : "lax",
    path: "/", // Explicitly set path to root so cookies are sent for all API routes
    // Don't set domain for IP addresses (browsers reject cookies with IP domains)
    // Only set domain for proper domain names like "localhost" or "example.com"
    domain:
      cookieDomain && !isIPAddress(cookieDomain) ? cookieDomain : undefined,
  };

  if (isRefreshToken) {
    // Refresh token cookies should have longer expiry
    baseOptions.maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days
    baseOptions.path = "/api/users/"; // accessible only on users auth routes
  } else {
    // Access token cookies
    baseOptions.maxAge = 15 * 60 * 1000; // 15 minutes
  }

  return baseOptions;
};

/**
 * Get request metadata for session tracking
 * @param {Object} req - Express request object
 * @returns {Object} Request metadata
 */
const getRequestMetadata = (req) => {
  return {
    ipAddress:
      req.ip || req.connection.remoteAddress || req.socket.remoteAddress,
    userAgent: req.get("User-Agent") || "Unknown",
  };
};

/**
 * Enhanced session validation middleware
 * Validates JWT token and session in database with comprehensive checks
 * @param {Object} options - Middleware options
 * @param {boolean} options.requireIPMatch - Whether to enforce IP matching (default: true)
 * @param {boolean} options.requireActiveSession - Whether to require at least one active session (default: true)
 * @param {boolean} options.optional - Whether authentication is optional (default: false)
 * @returns {Function} Express middleware function
 */
const validateUserSession = (options = {}) => {
  const {
    requireIPMatch = true,
    requireActiveSession = true,
    optional = false,
  } = options;

  return async (req, res, next) => {
    try {
      const token = extractToken(req);
      const clientIP = getClientIP(req);

      // If optional and no token, continue without auth
      if (optional && !token) {
        req.clientIP = clientIP;
        return next();
      }

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

      // Find session in database
      const session = await findSessionByAccessToken(token);

      if (!session) {
        logger.warn("Session not found for valid JWT", {
          userId: decoded.userId,
        });
        throw AuthenticationError("Session not found", "SESSION_NOT_FOUND");
      }

      // Check if user has any active sessions
      if (requireActiveSession) {
        const sessions = await getUserSessions(decoded.userId);
        const activeSessionsCount = sessions.counts.activeSessions;
        if (activeSessionsCount === 0) {
          logger.warn("User has no active sessions", {
            userId: decoded.userId,
          });
          throw AuthenticationError("No active sessions", "NO_ACTIVE_SESSIONS");
        }

        logger.debug(
          `User ${decoded.userId} has ${activeSessionsCount} active session(s)`,
        );
      }

      // Validate IP address if required
      if (requireIPMatch) {
        const ipValid = await validateSessionIP(session.id, clientIP);

        if (!ipValid) {
          logger.warn("IP mismatch detected", {
            userId: decoded.userId,
            sessionId: session.id,
            storedIP: session.ipAddress,
            currentIP: clientIP,
          });

          throw AuthenticationError("IP address mismatch", "IP_MISMATCH");
        }
      }

      // Add session and user info to request object
      req.session = session;
      req.user = {
        id: decoded.userId,
        username: decoded.username,
        email: decoded.email,
        ...session.user, // Include full user data from session
      };
      req.token = token;
      req.clientIP = clientIP;

      logger.debug(`Session validated successfully for user ${decoded.userId}`);
      next();
    } catch (error) {
      const transformedError = transformError(error, "validateUserSession");

      // Clear cookies if session/token is invalid
      if (
        [
          "INVALID_TOKEN",
          "SESSION_NOT_FOUND",
          "NO_ACTIVE_SESSIONS",
          "IP_MISMATCH",
        ].includes(transformedError.code)
      ) {
        res.clearCookie(COOKIE_NAMES.ACCESS_TOKEN);
        res.clearCookie(COOKIE_NAMES.REFRESH_TOKEN);
      }

      logger.error("Session validation failed", {
        error: transformedError.message,
        code: transformedError.code,
        url: req.url,
        method: req.method,
        clientIP: getClientIP(req),
      });

      // If optional and validation fails, continue without auth
      if (optional) {
        req.clientIP = getClientIP(req);
        return next();
      }

      return res.status(401).json({
        success: false,
        error: {
          message: transformedError.message,
          code: transformedError.code,
        },
      });
    }
  };
};

/**
 * Basic authentication middleware using the legacy method
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Next middleware function
 */
const authenticateUser = async (req, res, next) => {
  try {
    const token = extractToken(req);

    if (!token) {
      throw AuthenticationError("Authentication token required");
    }

    // Validate token and get user data using userService
    const { user, session } = await userService.validateToken(token);

    // Add user and session data to request object
    req.user = user;
    req.session = session;
    req.token = token;
    req.clientIP = getClientIP(req);

    next();
  } catch (error) {
    const transformedError = transformError(error, "authenticateUser");

    // Clear cookies if token is invalid
    if (
      transformedError.code === "INVALID_TOKEN" ||
      transformedError.code === "TOKEN_EXPIRED"
    ) {
      res.clearCookie(COOKIE_NAMES.ACCESS_TOKEN);
      res.clearCookie(COOKIE_NAMES.REFRESH_TOKEN);
    }

    return res.status(401).json({
      success: false,
      error: {
        message: transformedError.message,
        code: transformedError.code,
      },
    });
  }
};

/**
 * Optional authentication middleware - doesn't fail if no token provided
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Next middleware function
 */
const optionalAuth = async (req, res, next) => {
  try {
    const token = extractToken(req);

    if (token) {
      const { user, session } = await userService.validateToken(token);
      req.user = user;
      req.session = session;
      req.token = token;
    }

    req.clientIP = getClientIP(req);
    next();
  } catch (error) {
    // For optional auth, we don't fail on invalid tokens
    // Just clear cookies and continue
    res.clearCookie(COOKIE_NAMES.ACCESS_TOKEN);
    res.clearCookie(COOKIE_NAMES.REFRESH_TOKEN);
    req.clientIP = getClientIP(req);
    next();
  }
};

/**
 * Middleware to check if user account is active
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Next middleware function
 */
const requireActiveAccount = (req, res, next) => {
  try {
    if (!req.user) {
      throw AuthenticationError(
        "Authentication required",
        "AUTHENTICATION_REQUIRED",
      );
    }

    next();
  } catch (error) {
    const transformedError = transformError(error, "requireActiveAccount");
    return res.status(403).json({
      success: false,
      error: {
        message: transformedError.message,
        code: transformedError.code,
      },
    });
  }
};

/**
 * Middleware to check if user email is verified
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Next middleware function
 */
const requireEmailVerification = (req, res, next) => {
  try {
    if (!req.user) {
      throw AuthenticationError(
        "Authentication required",
        "AUTHENTICATION_REQUIRED",
      );
    }

    if (!req.user.emailVerified) {
      throw AuthorizationError(
        "Email verification required",
        "EMAIL_VERIFICATION_REQUIRED",
      );
    }

    next();
  } catch (error) {
    const transformedError = transformError(error, "requireEmailVerification");
    return res.status(403).json({
      success: false,
      error: {
        message: transformedError.message,
        code: transformedError.code,
      },
    });
  }
};

/**
 * Middleware to require specific role(s)
 * @param {string|string[]} allowedRoles - Role(s) that are allowed
 * @returns {Function} Express middleware function
 */
const requireRole = (allowedRoles) => {
  // Ensure allowedRoles is an array
  const rolesArray = Array.isArray(allowedRoles)
    ? allowedRoles
    : [allowedRoles];

  return (req, res, next) => {
    try {
      if (!req.user) {
        throw AuthenticationError(
          "Authentication required",
          "AUTHENTICATION_REQUIRED",
        );
      }

      if (!req.user.role) {
        throw AuthorizationError("User role not found", "ROLE_NOT_FOUND");
      }

      if (!rolesArray.includes(req.user.role)) {
        logger.warn("Unauthorized role access attempt", {
          userId: req.user.id,
          userRole: req.user.role,
          requiredRoles: rolesArray,
          endpoint: req.originalUrl,
        });

        throw AuthorizationError(
          "Insufficient permissions. This action requires elevated privileges.",
          "INSUFFICIENT_PERMISSIONS",
        );
      }

      next();
    } catch (error) {
      const transformedError = transformError(error, "requireRole");
      return res.status(403).json({
        success: false,
        error: {
          message: transformedError.message,
          code: transformedError.code,
        },
      });
    }
  };
};

/**
 * Middleware to require SUPER_ADMIN role (highest privilege)
 * Used for: managing companies, creating COMPANY_ADMINs, system-wide settings
 */
const requireSuperAdmin = requireRole("SUPER_ADMIN");

/**
 * Middleware to require company admin privileges (COMPANY_ADMIN or SUPER_ADMIN)
 * Used for: managing company users, onboarding page access, invite codes
 */
const requireCompanyAdmin = requireRole(["COMPANY_ADMIN", "SUPER_ADMIN"]);

/**
 * Middleware to require user's company membership to be verified
 * Used for: accessing company resources, chatting with executives
 */
const requireCompanyVerified = (req, res, next) => {
  try {
    if (!req.user) {
      throw AuthenticationError(
        "Authentication required",
        "AUTHENTICATION_REQUIRED",
      );
    }

    // SUPER_ADMIN bypasses company verification (they manage all companies)
    if (req.user.role === "SUPER_ADMIN") {
      return next();
    }

    if (!req.user.isCompanyVerified) {
      throw AuthorizationError(
        "Company membership verification required. Please wait for your company admin to verify your account.",
        "COMPANY_VERIFICATION_REQUIRED",
      );
    }

    next();
  } catch (error) {
    const transformedError = transformError(error, "requireCompanyVerified");
    return res.status(403).json({
      success: false,
      error: {
        message: transformedError.message,
        code: transformedError.code,
      },
    });
  }
};

/**
 * Middleware to require user belongs to a specific company
 * @param {string} companyIdParam - Parameter name containing company ID (default: 'companyId')
 * @returns {Function} Express middleware function
 */
const requireSameCompany = (companyIdParam = "companyId") => {
  return (req, res, next) => {
    try {
      if (!req.user) {
        throw AuthenticationError(
          "Authentication required",
          "AUTHENTICATION_REQUIRED",
        );
      }

      // SUPER_ADMIN can access any company
      if (req.user.role === "SUPER_ADMIN") {
        return next();
      }

      const targetCompanyId = req.params[companyIdParam];

      if (!targetCompanyId) {
        throw AuthorizationError(
          "Company ID parameter required",
          "COMPANY_ID_REQUIRED",
        );
      }

      if (req.user.companyId !== targetCompanyId) {
        logger.warn("Cross-company access attempt", {
          userId: req.user.id,
          userCompanyId: req.user.companyId,
          targetCompanyId,
          endpoint: req.originalUrl,
        });

        throw AuthorizationError(
          "Access denied: you can only access resources in your own company",
          "CROSS_COMPANY_ACCESS_DENIED",
        );
      }

      next();
    } catch (error) {
      const transformedError = transformError(error, "requireSameCompany");
      return res.status(403).json({
        success: false,
        error: {
          message: transformedError.message,
          code: transformedError.code,
        },
      });
    }
  };
};

// Legacy aliases for backward compatibility (will be deprecated)
const requireAdmin = requireSuperAdmin;
const requireManager = requireCompanyAdmin;

/**
 * Middleware to validate refresh token
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Next middleware function
 */
const validateRefreshToken = async (req, res, next) => {
  try {
    const refreshToken = extractRefreshToken(req);

    if (!refreshToken) {
      throw AuthenticationError(
        "Refresh token required",
        "REFRESH_TOKEN_REQUIRED",
      );
    }

    // Add refresh token to request
    req.refreshToken = refreshToken;

    next();
  } catch (error) {
    const transformedError = transformError(error, "validateRefreshToken");

    // Clear refresh token cookie if invalid
    res.clearCookie(COOKIE_NAMES.REFRESH_TOKEN);

    return res.status(401).json({
      success: false,
      error: {
        message: transformedError.message,
        code: transformedError.code,
      },
    });
  }
};

/**
 * Middleware to check if user owns the resource
 * @param {string} userIdParam - Parameter name containing user ID (default: 'userId')
 * @returns {Function} Express middleware function
 */
const requireResourceOwnership = (userIdParam = "userId") => {
  return (req, res, next) => {
    try {
      if (!req.user) {
        throw AuthenticationError(
          "Authentication required",
          "AUTHENTICATION_REQUIRED",
        );
      }

      const resourceUserId = req.params[userIdParam] || req.body[userIdParam];

      if (!resourceUserId) {
        throw AuthorizationError(
          "User ID parameter required",
          "USER_ID_REQUIRED",
        );
      }

      if (req.user.id !== resourceUserId) {
        throw AuthorizationError(
          "Access denied: resource ownership required",
          "OWNERSHIP_REQUIRED",
        );
      }

      next();
    } catch (error) {
      const transformedError = transformError(
        error,
        "requireResourceOwnership",
      );
      return res.status(403).json({
        success: false,
        error: {
          message: transformedError.message,
          code: transformedError.code,
        },
      });
    }
  };
};

/**
 * Set authentication cookies on response object with proper error handling
 * @param {Object} res - Express response object
 * @param {Object} tokens - Tokens object
 * @param {string} tokens.accessToken - JWT access token
 * @param {string} tokens.refreshToken - JWT refresh token
 * @throws {ValidationError} When tokens are invalid
 */
const setAuthCookies = (res, tokens) => {
  try {
    // Input validation with detailed error messages
    if (!res) {
      throw ValidationError(
        "Response object is required",
        "MISSING_RESPONSE_OBJECT",
      );
    }

    if (!tokens) {
      throw ValidationError(
        "Tokens object is required for setting auth cookies",
        "MISSING_TOKENS_OBJECT",
        {
          expected: { accessToken: "string", refreshToken: "string" },
          received: tokens,
        },
      );
    }

    if (typeof tokens !== "object") {
      throw ValidationError("Tokens must be an object", "INVALID_TOKENS_TYPE", {
        expected: "object",
        received: typeof tokens,
        value: tokens,
      });
    }

    const { accessToken, refreshToken } = tokens;

    // Validate individual tokens
    if (!accessToken || typeof accessToken !== "string") {
      throw ValidationError(
        "Valid access token is required",
        "INVALID_ACCESS_TOKEN",
        {
          provided: accessToken,
          type: typeof accessToken,
        },
      );
    }

    if (!refreshToken || typeof refreshToken !== "string") {
      throw ValidationError(
        "Valid refresh token is required",
        "INVALID_REFRESH_TOKEN",
        {
          provided: refreshToken,
          type: typeof refreshToken,
        },
      );
    }

    // Set cookies with proper options
    res.cookie(COOKIE_NAMES.ACCESS_TOKEN, accessToken, getCookieOptions(false));
    res.cookie(
      COOKIE_NAMES.REFRESH_TOKEN,
      refreshToken,
      getCookieOptions(true),
    );

    logger.debug("Auth cookies set successfully", {
      accessTokenLength: accessToken.length,
      refreshTokenLength: refreshToken.length,
      service: "auth",
    });
  } catch (error) {
    logger.error("Failed to set auth cookies", {
      error: error.message,
      tokens: tokens ? "provided" : "missing",
      service: "auth",
    });

    // Re-throw the error to be handled by the calling function
    throw error;
  }
};

/**
 * Clear authentication cookies
 * @param {Object} res - Express response object
 */
const clearAuthCookies = (res) => {
  res.clearCookie(COOKIE_NAMES.ACCESS_TOKEN, getCookieOptions(false));
  res.clearCookie(COOKIE_NAMES.REFRESH_TOKEN, getCookieOptions(true));
};

/**
 * Combine multiple middleware functions
 * @param {...Function} middlewares - Middleware functions to combine
 * @returns {Function} Combined middleware function
 */
const combineMiddleware = (...middlewares) => {
  return (req, res, next) => {
    let index = 0;

    const runNext = (error) => {
      if (error) {
        return next(error);
      }

      if (index >= middlewares.length) {
        return next();
      }

      const middleware = middlewares[index++];
      middleware(req, res, runNext);
    };

    runNext();
  };
};

// Pre-configured session validation middleware
const strictSessionValidation = validateUserSession({
  requireIPMatch: true,
  requireActiveSession: true,
});

const relaxedSessionValidation = validateUserSession({
  requireIPMatch: false,
  requireActiveSession: true,
});

const basicSessionValidation = validateUserSession({
  requireIPMatch: false,
  requireActiveSession: false,
});

const optionalSessionValidation = validateUserSession({
  requireIPMatch: false,
  requireActiveSession: false,
  optional: true,
});

module.exports = {
  // Core authentication
  authenticateUser,
  optionalAuth,
  validateRefreshToken,

  // Session validation (new)
  validateUserSession,
  strictSessionValidation,
  relaxedSessionValidation,
  basicSessionValidation,
  optionalSessionValidation,

  // Authorization checks
  requireActiveAccount,
  requireEmailVerification,
  requireResourceOwnership,
  requireRole,

  // RBAC role-based middleware (new)
  requireSuperAdmin,        // SUPER_ADMIN only
  requireCompanyAdmin,      // COMPANY_ADMIN or SUPER_ADMIN
  requireCompanyVerified,   // User's company membership is verified
  requireSameCompany,       // User belongs to same company as target resource

  // Legacy aliases (kept for backward compatibility)
  requireAdmin,
  requireManager,

  // Utility functions
  extractToken,
  extractRefreshToken,
  getRequestMetadata,
  getClientIP,
  setAuthCookies,
  clearAuthCookies,
  combineMiddleware,

  // Pre-configured middleware combinations
  requireAuth: combineMiddleware(authenticateUser, requireActiveAccount),
  requireVerifiedAuth: combineMiddleware(
    authenticateUser,
    requireActiveAccount,
    requireEmailVerification,
  ),
  // New: require authenticated user with verified company membership
  requireCompanyAuth: combineMiddleware(
    authenticateUser,
    requireActiveAccount,
    requireCompanyVerified,
  ),
};
