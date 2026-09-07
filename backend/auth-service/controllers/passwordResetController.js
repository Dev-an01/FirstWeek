// auth-service/controllers/passwordResetController.js
const passwordResetService = require("../services/passwordResetService");
const { getRequestMetadata } = require("../middleware/authMiddleware");
const { createSuccessResponse, createErrorResponse } = require("../lib/utils");
const {
  createLogger,
  // eslint-disable-next-line
} = require('../shared/utils/logger');

const logger = createLogger("password-reset-controller");

/**
 * Request password reset
 * @route POST /api/users/password/forgot
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const requestPasswordReset = async (req, res) => {
  try {
    const { email } = req.body;

    logger.info("Password reset request received", {
      email: email?.replace(/(.{2}).*(@.*)/, "$1***$2"),
      ip: req.ip,
      userAgent: req.get("User-Agent"),
    });

    const metadata = getRequestMetadata(req);
    const result = await passwordResetService.requestPasswordReset(
      { email },
      metadata,
    );

    logger.info("Password reset request processed", {
      email: email?.replace(/(.{2}).*(@.*)/, "$1***$2"),
      success: result.success,
      ip: req.ip,
    });

    return createSuccessResponse(
      res,
      {
        email: result.email,
        expiresAt: result.expiresAt,
      },
      result.message,
      200,
    );
  } catch (error) {
    logger.error("Password reset request failed", {
      error: error.message,
      email: req.body?.email?.replace(/(.{2}).*(@.*)/, "$1***$2"),
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "requestPasswordReset");
  }
};

/**
 * Reset password using token
 * @route POST /api/users/password/reset
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const resetPassword = async (req, res) => {
  try {
    const { token, newPassword, confirmPassword } = req.body;

    logger.info("Password reset attempt", {
      token: `${token?.substring(0, 8)}...`,
      ip: req.ip,
      userAgent: req.get("User-Agent"),
    });

    const metadata = getRequestMetadata(req);
    const result = await passwordResetService.resetPassword(
      { token, newPassword, confirmPassword },
      metadata,
    );

    logger.info("Password reset completed successfully", {
      userId: result.userId,
      ip: req.ip,
    });

    return createSuccessResponse(
      res,
      { userId: result.userId },
      result.message,
      200,
    );
  } catch (error) {
    logger.error("Password reset failed", {
      error: error.message,
      token: `${req.body?.token?.substring(0, 8)}...`,
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "resetPassword");
  }
};

/**
 * Validate reset token
 * @route GET /api/users/password/validate-token/:token
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const validateResetToken = async (req, res) => {
  try {
    const { token } = req.params;

    logger.info("Reset token validation request", {
      token: `${token?.substring(0, 8)}...`,
      ip: req.ip,
    });

    const result = await passwordResetService.validateResetToken(token);

    logger.info("Reset token validation completed", {
      token: `${token?.substring(0, 8)}...`,
      valid: result.valid,
      ip: req.ip,
    });

    return createSuccessResponse(
      res,
      {
        valid: result.valid,
        expiresAt: result.expiresAt,
        timeRemaining: result.timeRemaining,
        user: result.user,
      },
      result.message,
      200,
    );
  } catch (error) {
    logger.error("Reset token validation failed", {
      error: error.message,
      token: `${req.params?.token?.substring(0, 8)}...`,
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "validateResetToken");
  }
};

/**
 * Render password reset page
 * @route GET /reset-password
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const renderResetPasswordPage = async (req, res) => {
  try {
    const { token } = req.query;

    // Check if token is provided
    if (!token) {
      return res.render("password-reset/invalid-token", {
        title: "Invalid Reset Link - FirstWeek",
        error: "The password reset link is missing or invalid.",
        frontendUrl: process.env.FRONTEND_URL || "http://localhost:3000",
      });
    }

    // Validate the token
    const validation = await passwordResetService.validateResetToken(token);

    if (!validation.valid) {
      return res.render("password-reset/invalid-token", {
        title: "Invalid or Expired Reset Link - FirstWeek",
        error: validation.message,
        frontendUrl: process.env.FRONTEND_URL || "http://localhost:3000",
      });
    }

    // Render the password reset form
    return res.render("password-reset/reset-form", {
      title: "Reset Password - FirstWeek",
      token: token,
      timeRemaining: validation.timeRemaining,
      user: validation.user,
      frontendUrl: process.env.FRONTEND_URL || "http://localhost:3000",
      apiBaseUrl: process.env.API_BASE_URL || "http://localhost:3001",
    });
  } catch (error) {
    logger.error("Failed to render reset password page", {
      error: error.message,
      token: `${req.query?.token?.substring(0, 8)}...`,
      ip: req.ip,
    });

    return res.render("password-reset/error", {
      title: "Error - FirstWeek",
      error:
        "We are having trouble processing your request. Please try again later.",
      frontendUrl: process.env.FRONTEND_URL || "http://localhost:3000",
    });
  }
};

module.exports = {
  requestPasswordReset,
  resetPassword,
  validateResetToken,
  renderResetPasswordPage,
};
