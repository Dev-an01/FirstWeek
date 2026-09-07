const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const { JWT_CONFIG } = require("./constants");
// eslint-disable-next-line
const {
  transformError,
  isValidationError,
  isConflictError,
  isNotFoundError,
  isAuthenticationError,
  isAuthorizationError,
  AuthenticationError,
  // eslint-disable-next-line
} = require('../shared/utils/errors');
const SALT_ROUNDS = 12;
/**
 * Generate JWT tokens (access and refresh)
 * @param {Object} payload - Token payload
 * @returns {Object} Object containing access and refresh tokens
 */
const generateTokens = (payload) => {
  try {
    const accessToken = jwt.sign(payload, process.env.JWT_ACCESS_SECRET, {
      expiresIn: JWT_CONFIG.accessTokenExpiry || "15m",
    });
    const refreshToken = jwt.sign(payload, process.env.JWT_REFRESH_SECRET, {
      expiresIn: JWT_CONFIG.refreshTokenExpiry || "7d",
    });
    return { accessToken, refreshToken };
  } catch (error) {
    return transformError(error, "generateTokens");
  }
};

/**
 * Verify JWT token
 * @param {string} token - JWT token to verify
 * @param {string} secret - Secret to verify against
 * @returns {Object} Decoded payload
 */
const verifyToken = (token, secret) => {
  try {
    return jwt.verify(token, secret);
  } catch (error) {
    if (error.name === "TokenExpiredError") {
      throw AuthenticationError("Token has expired");
    }
    if (error.name === "JsonWebTokenError") {
      throw AuthenticationError("Invalid or malformed token");
    }
    throw transformError(error, "verifyToken");
  }
};
/**
 * Hash password using bcrypt
 * @param {string} password - Plain text password
 * @returns {Promise<string>} Hashed password
 */
const hashPassword = async (password) => {
  try {
    return await bcrypt.hash(password, SALT_ROUNDS);
  } catch (error) {
    throw transformError(error, "hashPassword");
  }
};
/**
 * Compare password with hash
 * @param {string} password - Plain text password
 * @param {string} hash - Hashed password
 * @returns {Promise<boolean>} True if password matches
 */
const comparePassword = async (password, hash) => {
  try {
    return await bcrypt.compare(password, hash);
  } catch (error) {
    throw transformError(error, "comparePassword");
  }
};

/**
 * Create standardized success response
 * @param {Object} res - Express response object
 * @param {Object} data - Response data
 * @param {string} message - Success message
 * @param {number} statusCode - HTTP status code
 */
const createSuccessResponse = (
  res,
  data = {},
  message = "Success",
  statusCode = 200,
) => {
  return res.status(statusCode).json({
    success: true,
    message,
    data,
    timestamp: new Date().toISOString(),
  });
};

/**
 * Create standardized error response
 * @param {Object} res - Express response object
 * @param {Error} error - Error object
 * @param {string} context - Error context
 */
const createErrorResponse = (res, error, context = "") => {
  const transformedError = transformError(error, context);

  // Determine appropriate HTTP status code
  let statusCode = 500;
  if (isValidationError(transformedError)) statusCode = 400;
  if (isAuthenticationError(transformedError)) statusCode = 401;
  if (isAuthorizationError(transformedError)) statusCode = 403;
  if (isNotFoundError(transformedError)) statusCode = 404;
  if (isConflictError(transformedError)) statusCode = 409;

  return res.status(statusCode).json({
    success: false,
    error: {
      message: transformedError.message,
      code: transformedError.code,
      ...(transformedError.metadata && { metadata: transformedError.metadata }),
    },
    timestamp: new Date().toISOString(),
  });
};
module.exports = {
  generateTokens,
  verifyToken,
  hashPassword,
  comparePassword,
  SALT_ROUNDS,
  AuthenticationError,
  transformError,
  createSuccessResponse,
  createErrorResponse,
};
