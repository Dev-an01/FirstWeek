// backend/auth-service/controllers/userController.js
const userService = require("../services/userService");
const userRepository = require("../repositories/userRepository");
const sessionRepository = require("../repositories/sessionRepository");
const {
  getRequestMetadata,
  setAuthCookies,
  clearAuthCookies,
} = require("../middleware/authMiddleware");

const { SUCCESS_MESSAGES } = require("../lib/constants");
const { createSuccessResponse, createErrorResponse } = require("../lib/utils");
const emailVerificationService = require("../services/emailService");
// Import global logger
const {
  createLogger,
  // eslint-disable-next-line
} = require('../shared/utils/logger');
const { updateUserSchema } = require("../models/userSchema");
const onboardingService = require("../services/onboardingService");

const logger = createLogger("user-controller");

/**
 * Register a new user
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const registerUser = async (req, res) => {
  try {
    logger.info("User registration attempt started", {
      email: req.body.email,
      username: req.body.username,
      ip: req.ip,
      userAgent: req.get("User-Agent"),
    });

    const metadata = getRequestMetadata(req);
    const result = await userService.registerUser(req.body, metadata);

    // Set secure authentication cookies
    setAuthCookies(res, result.tokens);

    logger.auth("REGISTER_SUCCESS", "User registered successfully", {
      userId: result.user.id,
      username: result.user.username,
      email: result.user.email,
      ip: req.ip,
    });

    return createSuccessResponse(
      res,
      { user: result.user },
      result.message || SUCCESS_MESSAGES.USER.REGISTERED,
      201,
    );
  } catch (error) {
    logger.error("User registration failed", {
      error: error.message,
      email: req.body.email,
      username: req.body.username,
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "registerUser");
  }
};

/**
 * Login user
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const loginUser = async (req, res) => {
  try {
    logger.info("User login attempt started", {
      identifier: req.body.identifier,
      ip: req.ip,
      userAgent: req.get("User-Agent"),
    });

    const metadata = getRequestMetadata(req);
    const result = await userService.loginUser(req.body, metadata);

    // Set secure authentication cookies
    setAuthCookies(res, result.tokens);

    logger.auth("LOGIN_SUCCESS", "User logged in successfully", {
      userId: result.user.id,
      username: result.user.username,
      ip: req.ip,
    });

    return createSuccessResponse(
      res,
      { user: result.user },
      result.message || SUCCESS_MESSAGES.USER.LOGIN,
    );
  } catch (error) {
    logger.error("User login failed", {
      error: error.message,
      identifier: req.body.identifier,
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "loginUser");
  }
};

/**
 * Get all users
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const getAllUsers = async (req, res) => {
  try {
    logger.info("Fetching all users", {
      requestedBy: req.user?.id || "anonymous",
      ip: req.ip,
    });

    const result = await userService.getUsers();

    logger.info("Users retrieved successfully", {
      count: result.users.length,
      requestedBy: req.user?.id || "anonymous",
    });

    return createSuccessResponse(
      res,
      { users: result.users },
      "Users retrieved successfully",
    );
  } catch (error) {
    logger.error("Failed to retrieve users", {
      error: error.message,
      requestedBy: req.user?.id || "anonymous",
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "getAllUsers");
  }
};

/**
 * Refresh access token
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const refreshToken = async (req, res) => {
  try {
    logger.info("Token refresh attempt", {
      ip: req.ip,
      userAgent: req.get("User-Agent"),
    });

    const metadata = getRequestMetadata(req);
    const result = await userService.refreshAccessToken(
      req.refreshToken,
      metadata,
    );

    // Set new authentication cookies
    setAuthCookies(res, result.tokens);

    logger.auth(
      "TOKEN_REFRESH_SUCCESS",
      "Access token refreshed successfully",
      {
        userId: result.tokens.userId || "unknown",
        ip: req.ip,
      },
    );

    return createSuccessResponse(
      res,
      {},
      result.message || SUCCESS_MESSAGES.SESSION.REFRESHED,
    );
  } catch (error) {
    logger.error("Token refresh failed", {
      error: error.message,
      ip: req.ip,
      stack: error.stack,
    });
    // Clear cookies on refresh failure
    clearAuthCookies(res);
    return createErrorResponse(res, error, "refreshToken");
  }
};

/**
 * Logout user from current device
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const logoutUser = async (req, res) => {
  try {
    logger.info("User logout attempt", {
      userId: req.user?.id,
      sessionId: req.session?.id,
      ip: req.ip,
    });

    const result = await userService.logoutUser(req.token);

    // Clear authentication cookies
    clearAuthCookies(res);

    logger.auth("LOGOUT_SUCCESS", "User logged out successfully", {
      userId: req.user?.id,
      sessionId: req.session?.id,
      ip: req.ip,
    });

    return createSuccessResponse(
      res,
      {},
      result.message || SUCCESS_MESSAGES.USER.LOGOUT,
    );
  } catch (error) {
    logger.error("User logout failed", {
      error: error.message,
      userId: req.user?.id,
      ip: req.ip,
      stack: error.stack,
    });
    // Clear cookies even on error
    clearAuthCookies(res);
    return createErrorResponse(res, error, "logoutUser");
  }
};

/**
 * Logout user from all devices
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const logoutAllDevices = async (req, res) => {
  try {
    logger.info("Logout all devices attempt", {
      userId: req.user.id,
      ip: req.ip,
    });

    const result = await userService.logoutAllDevices(req.user.id);

    // Clear authentication cookies
    clearAuthCookies(res);

    logger.auth(
      "LOGOUT_ALL_SUCCESS",
      "Logged out from all devices successfully",
      {
        userId: req.user.id,
        ip: req.ip,
      },
    );

    return createSuccessResponse(
      res,
      {},
      result.message || "Logged out from all devices successfully",
    );
  } catch (error) {
    logger.error("Logout all devices failed", {
      error: error.message,
      userId: req.user?.id,
      ip: req.ip,
      stack: error.stack,
    });
    // Clear cookies even on error
    clearAuthCookies(res);
    return createErrorResponse(res, error, "logoutAllDevices");
  }
};

/**
 * Get current user profile
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const getCurrentUserProfile = async (req, res) => {
  try {
    logger.info("Current user profile requested", {
      userId: req.user.id,
      username: req.user.username,
    });

    // User data is already available from authentication middleware
    logger.debug("Profile retrieved successfully from middleware", {
      userId: req.user.id,
    });

    return createSuccessResponse(
      res,
      {
        user: req.user,
        session: req.session,
      },
      "Profile retrieved successfully",
    );
  } catch (error) {
    logger.error("Failed to get current user profile", {
      error: error.message,
      userId: req.user?.id,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "getCurrentUserProfile");
  }
};

/**
 * Get user profile by ID
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const getUserProfile = async (req, res) => {
  try {
    const { userId } = req.params;

    logger.info("User profile requested", {
      targetUserId: userId,
      requestedBy: req.user?.id,
      ip: req.ip,
    });

    const result = await userService.getUserProfile(userId);

    logger.debug("User profile retrieved successfully", {
      targetUserId: userId,
      username: result.user.username,
    });

    return createSuccessResponse(
      res,
      { user: result.user },
      "Profile retrieved successfully",
    );
  } catch (error) {
    logger.error("Failed to get user profile", {
      error: error.message,
      targetUserId: req.params.userId,
      requestedBy: req.user?.id,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "getUserProfile");
  }
};

/**
 * Update user profile
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const updateUserProfile = async (req, res) => {
  try {
    const userId = req.params.userId || req.user.id;
    const updateData = req.body;

    // Validate input
    const validatedData = updateUserSchema.parse(updateData);

    // Check if email is being updated
    const emailChanged =
      validatedData.email && validatedData.email !== req.user.email;
    let emailVerificationResult = null;

    if (emailChanged) {
      // If email is being changed, don't update it directly
      // Instead, trigger email verification process
      const emailToVerify = validatedData.email;
      delete validatedData.email; // Remove from update data

      try {
        // Send verification OTP to new email
        emailVerificationResult = await emailVerificationService.sendEmailOtp(
          userId,
          emailToVerify,
        );

        logger.info("📧 Email verification triggered for profile update", {
          userId,
          newEmail: emailToVerify.replace(/(.{2}).*(@.*)/, "$1***$2"),
        });
      } catch (emailError) {
        logger.error(
          "❌ Failed to send verification email during profile update",
          {
            userId,
            error: emailError.message,
          },
        );
        // Continue with other profile updates even if email verification fails
      }
    }

    // Update user profile (excluding email if it's being verified)
    const result = await userService.updateUserProfile(userId, validatedData);

    // Prepare response
    const responseData = {
      user: result.user,
    };

    // Include email verification info if email was changed
    if (emailChanged && emailVerificationResult) {
      responseData.emailVerification = {
        required: true,
        email: validatedData.email || updateData.email,
        success: emailVerificationResult.success,
        expiresAt: emailVerificationResult.data?.expiresAt,
      };
    }

    const message = emailChanged
      ? "Profile updated successfully. Please check your email and verify the OTP to complete email setup."
      : result.message || "Profile updated successfully";

    // Sync to Onboarding Service if EXECUTIVE's name or title changed
    const nameOrTitleChanged = validatedData.firstName !== undefined
      || validatedData.lastName !== undefined
      || validatedData.title !== undefined;

    if (
      req.user.role === "EXECUTIVE"
      && req.user.companyId
      && nameOrTitleChanged
    ) {
      onboardingService.syncUpdateExecutive(result.user, req.user.companyId).catch(err => {
        logger.error("Async executive profile sync failed", {
          error: err.message,
          userId,
        });
      });
    }

    logger.info("✅ User profile updated", {
      userId,
      fieldsUpdated: Object.keys(validatedData),
      emailVerificationTriggered: emailChanged,
    });

    return createSuccessResponse(res, responseData, message);
  } catch (error) {
    logger.error("❌ Update user profile failed", {
      userId: req.params.userId || req.user?.id,
      error: error.message,
    });
    return createErrorResponse(res, error, "updateUserProfile");
  }
};
/**
 * Change user password
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const changePassword = async (req, res) => {
  try {
    logger.info("Password change attempt", {
      userId: req.user.id,
      username: req.user.username,
      ip: req.ip,
    });

    const result = await userService.changePassword(req.user.id, req.body);

    logger.auth("PASSWORD_CHANGE_SUCCESS", "Password changed successfully", {
      userId: req.user.id,
      username: req.user.username,
      ip: req.ip,
    });

    return createSuccessResponse(
      res,
      {},
      result.message || SUCCESS_MESSAGES.USER.PASSWORD_CHANGED,
    );
  } catch (error) {
    logger.error("Password change failed", {
      error: error.message,
      userId: req.user?.id,
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "changePassword");
  }
};
/**
 * Get user's active sessions
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const getUserSessions = async (req, res) => {
  try {
    const userId = req.user.id;
    if (!userId) {
      return createErrorResponse(
        res,
        new Error("User ID is required"),
        "getUserSessions",
      );
    }
    logger.info("User sessions requested", {
      targetUserId: userId,
      requestedBy: req.user.id,
    });
    const result = await userService.getUserSessions(userId);
    if (!result || !Array.isArray(result.sessions)) {
      logger.error("Invalid sessions data from service", {
        targetUserId: userId,
        resultType: typeof result,
        sessionsType: typeof result?.sessions,
      });

      return createErrorResponse(
        res,
        new Error("Failed to retrieve sessions"),
        "getUserSessions",
      );
    }
    const sessionsWithCurrent = result.sessions.map((session) => ({
      ...session,
      isCurrent: session.id === req.session?.id,
    }));
    const currentTime = new Date();
    const activeSessions = sessionsWithCurrent.filter((session) => {
      if (!session.expiresAt) return false;
      const expiresAt = new Date(session.expiresAt);
      return expiresAt > currentTime;
    });

    logger.debug("User sessions retrieved successfully", {
      targetUserId: userId,
      totalSessions: sessionsWithCurrent.length,
      activeSessions: activeSessions.length,
    });
    return createSuccessResponse(
      res,
      {
        sessions: sessionsWithCurrent,
        totalSessions: sessionsWithCurrent.length,
        activeSessions: activeSessions.length,
      },
      "Sessions retrieved successfully",
    );
  } catch (error) {
    logger.error("Failed to get user sessions", {
      error: error.message,
      targetUserId: req.params.userId || req.user?.id,
      requestedBy: req.user?.id,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "getUserSessions");
  }
};
/**
 * Revoke a specific session
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const revokeSession = async (req, res) => {
  try {
    const { sessionId } = req.params;

    logger.info("Session revocation attempt", {
      sessionId: sessionId,
      requestedBy: req.user.id,
      currentSessionId: req.session.id,
      ip: req.ip,
    });

    // Check if user is trying to revoke their own session
    if (sessionId === req.session.id) {
      logger.info(
        "User attempting to revoke current session, redirecting to logout",
      );
      // Use logout instead for current session
      return logoutUser(req, res);
    }

    await sessionRepository.deleteSession(sessionId);

    logger.auth("SESSION_REVOKED", "Session revoked successfully", {
      sessionId: sessionId,
      revokedBy: req.user.id,
      ip: req.ip,
    });

    return createSuccessResponse(res, {}, "Session revoked successfully");
  } catch (error) {
    logger.error("Session revocation failed", {
      error: error.message,
      sessionId: req.params.sessionId,
      requestedBy: req.user?.id,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "revokeSession");
  }
};

/**
 * Validate token endpoint (useful for frontend token validation)
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const validateToken = async (req, res) => {
  try {
    logger.debug("Token validation requested", {
      userId: req.user.id,
      sessionId: req.session.id,
      ip: req.ip,
    });

    // Token validation is already done by authentication middleware
    logger.debug("Token validation successful", {
      userId: req.user.id,
      sessionId: req.session.id,
    });

    return createSuccessResponse(
      res,
      {
        user: req.user,
        session: req.session,
        isValid: true,
      },
      "Token is valid",
    );
  } catch (error) {
    logger.error("Token validation failed", {
      error: error.message,
      userId: req.user?.id,
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "validateToken");
  }
};

/**
 * Check if email exists
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const checkEmailExists = async (req, res) => {
  try {
    const { email } = req.body;

    logger.debug("Email availability check", {
      email: email,
      ip: req.ip,
    });

    const exists = await userRepository.checkEmailExists(email);

    logger.debug("Email availability checked", {
      email: email,
      exists: exists,
    });

    return createSuccessResponse(
      res,
      { exists, email },
      "Email availability checked",
    );
  } catch (error) {
    logger.error("Email availability check failed", {
      error: error.message,
      email: req.body?.email,
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "checkEmailExists");
  }
};

/**
 * Check if username exists
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const checkUsernameExists = async (req, res) => {
  try {
    const { username } = req.body;

    logger.debug("Username availability check", {
      username: username,
      ip: req.ip,
    });

    const exists = await userRepository.checkUsernameExists(username);

    logger.debug("Username availability checked", {
      username: username,
      exists: exists,
    });

    return createSuccessResponse(
      res,
      { exists, username },
      "Username availability checked",
    );
  } catch (error) {
    logger.error("Username availability check failed", {
      error: error.message,
      username: req.body?.username,
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "checkUsernameExists");
  }
};

/**
 * Get user session statistics
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const getUserSessionStats = async (req, res) => {
  try {
    const userId = req.user.id;

    logger.info("Session statistics requested", {
      targetUserId: userId,
      requestedBy: req.user.id,
    });

    const stats = await sessionRepository.getUserSessionStats(userId);

    logger.debug("Session statistics retrieved", {
      targetUserId: userId,
      statsKeys: Object.keys(stats),
    });

    return createSuccessResponse(
      res,
      { stats },
      "Session statistics retrieved successfully",
    );
  } catch (error) {
    logger.error("Failed to get session statistics", {
      error: error.message,
      targetUserId: req.params.userId || req.user?.id,
      requestedBy: req.user?.id,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "getUserSessionStats");
  }
};

/**
 * Deactivate user account
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const deactivateAccount = async (req, res) => {
  try {
    const userId = req.user.id;

    logger.warn("Account deactivation attempt", {
      userId: userId,
      username: req.user.username,
      ip: req.ip,
      userAgent: req.get("User-Agent"),
    });

    // Update user to inactive
    await userService.updateUserProfile(userId, { isActive: false });

    // Logout from all devices
    await userService.logoutAllDevices(userId);

    // Clear cookies
    clearAuthCookies(res);

    logger.warn("Account deactivated successfully", {
      userId: userId,
      username: req.user.username,
      ip: req.ip,
    });

    return createSuccessResponse(res, {}, "Account deactivated successfully");
  } catch (error) {
    logger.error("Account deactivation failed", {
      error: error.message,
      userId: req.user?.id,
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "deactivateAccount");
  }
};

/**
 * Update user role (Admin only)
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
const updateUserRole = async (req, res) => {
  try {
    const { userId } = req.params;
    const { role } = req.body;

    logger.info("User role update attempt", {
      targetUserId: userId,
      newRole: role,
      adminUserId: req.user.id,
      adminUsername: req.user.username,
      ip: req.ip,
    });

    const result = await userService.updateUserRole(userId, role, req.user.id);

    // Sync to Onboarding Service when promoting to EXECUTIVE
    if (role === "EXECUTIVE" && result.user.companyId) {
      onboardingService.syncCreateExecutive(result.user, result.user.companyId).catch(err => {
        logger.error("Async executive create sync failed on role update", {
          error: err.message,
          userId: result.user.id,
        });
      });
    }

    logger.auth("ROLE_UPDATE_SUCCESS", "User role updated successfully", {
      targetUserId: userId,
      newRole: role,
      adminUserId: req.user.id,
      ip: req.ip,
    });

    return createSuccessResponse(
      res,
      { user: result.user },
      result.message || "User role updated successfully",
    );
  } catch (error) {
    logger.error("User role update failed", {
      error: error.message,
      targetUserId: req.params.userId,
      adminUserId: req.user?.id,
      ip: req.ip,
      stack: error.stack,
    });
    return createErrorResponse(res, error, "updateUserRole");
  }
};

// Export all controller functions wrapped with async handler
module.exports = {
  // Authentication
  registerUser,
  loginUser,
  getAllUsers,
  refreshToken,
  logoutUser,
  logoutAllDevices,
  validateToken,

  // Profile management
  getCurrentUserProfile,
  getUserProfile,
  updateUserProfile,
  changePassword,
  deactivateAccount,

  // Admin management
  updateUserRole,

  // Session management
  getUserSessions,
  revokeSession,
  getUserSessionStats,

  // Utility endpoints
  checkEmailExists,
  checkUsernameExists,
};
