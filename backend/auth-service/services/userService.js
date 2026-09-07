const userRepository = require("../repositories/userRepository");
const sessionRepository = require("../repositories/sessionRepository");
const companyRepository = require("../repositories/companyRepository");
const inviteCodeRepository = require("../repositories/inviteCodeRepository");
const { updateUserRoleSchema } = require("../models/userSchema");
const {
  hashPassword,
  generateTokens,
  comparePassword,
  verifyToken,
} = require("../lib/utils");
const {
  createUserSchema,
  loginUserSchema,
  updateUserSchema,
  passwordSchema,
} = require("../models/userSchema");

const {
  ValidationError,
  AuthenticationError,
  ConflictError,
  NotFoundError,
  transformError,
  // eslint-disable-next-line
} = require('../shared/utils/errors');
const { JWT_CONFIG } = require("../lib/constants");
// eslint-disable-next-line
const { createLogger } = require('../shared/utils/logger');
const logger = createLogger("user-service");

/**
 * Extract email domain from email address
 * @param {string} email - Email address
 * @returns {string} Domain part of email
 */
const extractEmailDomain = (email) => {
  return email.split("@")[1].toLowerCase();
};

/**
 * Register a new user
 * Handles three registration scenarios:
 * 1. With invite code - auto-assigns to company and auto-verifies
 * 2. With matching email domain - auto-assigns to company (pending verification)
 * 3. No company match - registers as standalone user (GUEST role)
 * 
 * @param {Object} userData - User registration data
 * @param {Object} requestMetadata - Request metadata (IP, user agent)
 * @returns {Promise<Object>} Registration result with user data and tokens
 */
const registerUser = async (userData, requestMetadata = {}) => {
  try {
    // Extract inviteCode before Zod validation (it's not in the schema)
    const { inviteCode, ...baseUserData } = userData;

    // Validate input data
    const validatedData = createUserSchema.parse(baseUserData);

    // Check if email already exists
    const emailExists = await userRepository.checkEmailExists(
      validatedData.email,
    );
    if (emailExists) {
      throw ConflictError("Email already registered");
    }

    // Check if username already exists
    const usernameExists = await userRepository.checkUsernameExists(
      validatedData.username,
    );
    if (usernameExists) {
      throw ConflictError("Username already taken");
    }

    // Initialize company assignment data
    let companyId = null;
    let isCompanyVerified = false;
    let role = validatedData.role || "EMPLOYEE";
    let registrationMethod = "standalone";

    // SCENARIO 1: Registration with invite code
    if (inviteCode) {
      logger.info("Registration with invite code", { inviteCode });

      const codeValidation = await inviteCodeRepository.validateCode(inviteCode);

      if (!codeValidation.valid) {
        throw ValidationError(
          codeValidation.message || "Invalid invite code",
          codeValidation.error || "INVALID_INVITE_CODE"
        );
      }

      // Use the invite code (increment usage)
      await inviteCodeRepository.useInviteCode(inviteCode);

      // Assign to company and auto-verify
      companyId = codeValidation.company.id;
      isCompanyVerified = true; // Invite code users are auto-verified
      registrationMethod = "invite_code";

      logger.info("User assigned to company via invite code", {
        companyId,
        companyName: codeValidation.company.name,
      });
    }
    // SCENARIO 2: Check if email domain matches a company
    else {
      const emailDomain = extractEmailDomain(validatedData.email);
      const matchedCompany = await companyRepository.findByDomain(emailDomain);

      if (matchedCompany) {
        companyId = matchedCompany.id;
        isCompanyVerified = false; // Pending admin verification
        registrationMethod = "domain_match";

        logger.info("User auto-assigned to company via email domain", {
          companyId,
          companyName: matchedCompany.name,
          emailDomain,
        });
      } else {
        // SCENARIO 3: No company match - register as GUEST
        role = "GUEST";
        registrationMethod = "standalone";

        logger.info("User registered without company association", {
          email: validatedData.email,
          role,
        });
      }
    }

    // Hash password
    const hashedPassword = await hashPassword(validatedData.password);

    // Create user with company assignment
    const newUser = await userRepository.createUser({
      ...validatedData,
      password: hashedPassword,
      role,
      companyId,
      isCompanyVerified,
      verifiedAt: isCompanyVerified ? new Date() : null,
    });

    // Generate tokens
    const tokenPayload = {
      userId: newUser.id,
      username: newUser.username,
      email: newUser.email,
      role: newUser.role,
      companyId: newUser.companyId,
    };

    const { accessToken, refreshToken } = generateTokens(tokenPayload);

    // Create session
    const sessionData = {
      userId: newUser.id,
      token: accessToken,
      refreshToken: refreshToken,
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 days
      ipAddress: requestMetadata.ipAddress,
      userAgent: requestMetadata.userAgent,
    };

    await sessionRepository.createSession(sessionData);

    // Build response message based on registration method
    let message = "User registered successfully";
    if (registrationMethod === "domain_match") {
      message = "User registered. Pending company admin verification.";
    } else if (registrationMethod === "invite_code") {
      message = "User registered and verified via invite code.";
    }

    return {
      user: newUser,
      tokens: { accessToken, refreshToken },
      message,
      registrationMethod,
    };
  } catch (error) {
    throw transformError(error, "registerUser");
  }
};


/**
 * Login user
 * @param {Object} loginData - Login credentials
 * @param {Object} requestMetadata - Request metadata (IP, user agent)
 * @returns {Promise<Object>} Login result with user data and tokens
 */
const loginUser = async (loginData, requestMetadata = {}) => {
  try {
    // Validate input data
    const validatedData = loginUserSchema.parse(loginData);

    // Find user by email or username (don't filter by isActive so we can provide better error)
    const user = await userRepository.findUser(
      validatedData.identifier,
      true,
      false,
    );
    if (!user) {
      throw AuthenticationError("Invalid credentials");
    }

    // Check if user is active
    if (!user.isActive) {
      throw AuthenticationError(
        "Account is deactivated",
        "ACCOUNT_DEACTIVATED",
      );
    }

    // Verify password
    const passwordMatch = await comparePassword(
      validatedData.password,
      user.password,
    );
    if (!passwordMatch) {
      throw AuthenticationError("Invalid credentials");
    }

    // Generate tokens
    const tokenPayload = {
      userId: user.id,
      username: user.username,
      email: user.email,
      role: user.role,
      companyId: user.companyId,
      isCompanyVerified: user.isCompanyVerified,
    };

    const { accessToken, refreshToken } = generateTokens(tokenPayload);

    // Create new session
    const sessionData = {
      userId: user.id,
      token: accessToken,
      refreshToken: refreshToken,
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 days
      ipAddress: requestMetadata.ipAddress,
      userAgent: requestMetadata.userAgent,
    };

    await sessionRepository.createSession(sessionData);

    // Update last login
    const updatedUser = await userRepository.updateLastLogin(user.id);

    return {
      user: updatedUser,
      tokens: { accessToken, refreshToken },
      message: "Login successful",
    };
  } catch (error) {
    throw transformError(error, "loginUser");
  }
};

/**
 * Refresh access token using refresh token
 * @param {string} refreshToken - Refresh token
 * @param {Object} requestMetadata - Request metadata
 * @returns {Promise<Object>} New tokens
 */
const refreshAccessToken = async (refreshToken, requestMetadata = {}) => {
  try {
    if (!refreshToken) {
      throw AuthenticationError(
        "Refresh token required",
        "REFRESH_TOKEN_REQUIRED",
      );
    }

    // Verify refresh token
    const decoded = verifyToken(refreshToken, JWT_CONFIG.refreshTokenSecret);

    // Check if session exists and is valid
    const session =
      await sessionRepository.findSessionByRefreshToken(refreshToken);
    if (!session || session.expiresAt < new Date()) {
      throw AuthenticationError("Invalid or expired refresh token");
    }

    // Get user data
    const user = await userRepository.findUser({ username: decoded.username });
    if (!user || !user.isActive) {
      throw AuthenticationError("User not found or inactive");
    }

    // Generate new tokens
    const tokenPayload = {
      userId: user.id,
      username: user.username,
      email: user.email,
      role: user.role,
      companyId: user.companyId,
      isCompanyVerified: user.isCompanyVerified,
    };

    const { accessToken, refreshToken: newRefreshToken } =
      generateTokens(tokenPayload);

    // Update session with new tokens
    await sessionRepository.updateSession(session.id, {
      token: accessToken,
      refreshToken: newRefreshToken,
      ipAddress: requestMetadata.ipAddress,
      userAgent: requestMetadata.userAgent,
    });

    return {
      message: "Token refreshed successfully",
      tokens: { accessToken, refreshToken: newRefreshToken },
    };
  } catch (error) {
    throw transformError(error, "refreshAccessToken");
  }
};

/**
 * Logout user and invalidate session
 * @param {string} token - Access token or refresh token
 * @returns {Promise<Object>} Logout result
 */
const logoutUser = async (token) => {
  try {
    if (!token) {
      throw ValidationError(
        "User not logged in, Token required for logout",
        "TOKEN_REQUIRED",
      );
    }

    // Try to find session by access token or refresh token
    let session = await sessionRepository.findSessionByAccessToken(token);
    if (!session) {
      session = await sessionRepository.findSessionByRefreshToken(token);
    }

    if (session) {
      await sessionRepository.deleteSession(session.id);
    }

    return { message: "Logout successful" };
  } catch (error) {
    throw transformError(error, "logoutUser");
  }
};

/**
 * Logout from all devices
 * @param {string} userId - User ID
 * @returns {Promise<Object>} Logout result
 */
const logoutAllDevices = async (userId) => {
  try {
    await sessionRepository.invalidateUserSessions(userId);
    return { message: "Logged out from all devices successfully" };
  } catch (error) {
    throw transformError(error, "logoutAllDevices");
  }
};
/**
 * Validate access token and get user data
 * @param {string} token - Access token
 * @returns {Promise<Object>} User data
 */
const validateToken = async (token) => {
  try {
    if (!token) {
      throw AuthenticationError("Token required", "TOKEN_REQUIRED");
    }

    // Verify token
    const decoded = verifyToken(token, JWT_CONFIG.accessTokenSecret);

    // Check if session exists
    const session = await sessionRepository.findSessionByAccessToken(token);
    if (!session || session.expiresAt < new Date()) {
      throw AuthenticationError("Session expired", "SESSION_EXPIRED");
    }

    // Get fresh user data
    const user = await userRepository.findUser({ id: decoded.userId });
    if (!user || !user.isActive) {
      throw AuthenticationError("User not found or inactive", "USER_INACTIVE");
    }

    return {
      user,
      session: {
        id: session.id,
        expiresAt: session.expiresAt,
        ipAddress: session.ipAddress,
        userAgent: session.userAgent,
      },
    };
  } catch (error) {
    throw transformError(error, "validateToken");
  }
};

/**
 * Change user password
 * @param {string} userId - User ID
 * @param {Object} passwordData - Password change data
 * @returns {Promise<Object>} Result
 */
const changePassword = async (userId, passwordData) => {
  try {
    // Validate input data
    const validatedPassword = passwordSchema.parse(passwordData.newPassword);
    const user = await userRepository.findUser({ id: userId }, true);
    if (!user) {
      throw NotFoundError("User not found", "USER_NOT_FOUND");
    }
    // Verify current password
    const passwordMatch = await comparePassword(
      passwordData.currentPassword,
      user.password,
    );
    if (!passwordMatch) {
      throw AuthenticationError(
        "Current password is incorrect",
        "INVALID_CURRENT_PASSWORD",
      );
    }

    // Hash new password
    const newHashedPassword = await hashPassword(validatedPassword);
    // Update password in database
    await userRepository.updateUserPassword(userId, newHashedPassword);

    // Invalidate all sessions except current one (optional)
    await sessionRepository.invalidateUserSessions(userId);

    return { message: "Password changed successfully" };
  } catch (error) {
    throw transformError(error, "changePassword");
  }
};

/**
 * Update user profile
 * @param {string} userId - User ID
 * @param {Object} updateData - Update data
 * @returns {Promise<Object>} Updated user data
 */
const updateUserProfile = async (userId, updateData) => {
  try {
    // Validate input data
    const validatedData = updateUserSchema.parse(updateData);

    // Check for email/username conflicts if being updated
    if (validatedData.email) {
      const emailExists = await userRepository.checkEmailExists(
        validatedData.email,
      );
      if (emailExists) {
        const existingUser = await userRepository.findUser({
          email: validatedData.email,
        });
        if (existingUser && existingUser.id !== userId) {
          throw ConflictError("Email already in use", "EMAIL_EXISTS");
        }
      }
    }

    if (validatedData.username) {
      const usernameExists = await userRepository.checkUsernameExists(
        validatedData.username,
      );
      if (usernameExists) {
        const existingUser = await userRepository.findUser({
          username: validatedData.username,
        });
        if (existingUser && existingUser.id !== userId) {
          throw ConflictError("Username already taken", "USERNAME_EXISTS");
        }
      }
    }

    // Update user
    const updatedUser = await userRepository.updateUser(userId, validatedData);

    return {
      user: updatedUser,
      message: "Profile updated successfully",
    };
  } catch (error) {
    throw transformError(error, "updateUserProfile");
  }
};

/**
 * Get user profile by ID
 * @param {string} userId - User ID
 * @returns {Promise<Object>} User data
 */
const getUserProfile = async (userId) => {
  try {
    const user = await userRepository.findUser({ id: userId }, true);
    if (!user) {
      throw NotFoundError("User not found", "USER_NOT_FOUND");
    }

    return { user };
  } catch (error) {
    throw transformError(error, "getUserProfile");
  }
};
/**
 * Get user's active sessions
 * @param {string} userId - User ID
 * @returns {Promise<Object>} Active sessions
 */
const getUserSessions = async (userId) => {
  try {
    // Validate userId
    if (!userId) {
      throw new Error("User ID is required");
    }

    logger.info("Getting user sessions from service", { userId });

    // Get sessions from repository - this returns { sessions: [...] }
    const result = await sessionRepository.getUserSessions(userId);

    // Validate the result structure
    if (!result || !Array.isArray(result.sessions)) {
      logger.error("Invalid sessions data from repository", {
        userId,
        resultType: typeof result,
        sessionsType: typeof result?.sessions,
        result,
      });

      // Return empty sessions structure if repository returns invalid data
      return {
        sessions: [],
      };
    }

    logger.info("User sessions retrieved successfully from service", {
      userId,
      sessionCount: result.sessions.length,
    });

    // Return the result as-is since it already has the correct structure
    return result;
  } catch (error) {
    logger.error("Failed to get user sessions in service", {
      error: error.message,
      userId,
      stack: error.stack,
    });
    throw transformError(error, "getUserSessions");
  }
};

const getUsers = async () => {
  try {
    const users = await userRepository.findUsers();
    return { users };
  } catch (error) {
    throw transformError(error, "getUsers");
  }
};

/**
 * Update user role (admin only)
 * @param {string} targetUserId - ID of user whose role to update
 * @param {string} newRole - New role to assign
 * @param {string} adminUserId - ID of admin making the change
 * @returns {Promise<Object>} Updated user data
 */
const updateUserRole = async (targetUserId, newRole, adminUserId) => {
  try {
    // Validate the new role
    const validatedData = updateUserRoleSchema.parse({ role: newRole });

    // Check if target user exists
    const targetUser = await userRepository.findUser({ id: targetUserId });
    if (!targetUser) {
      throw NotFoundError("User not found", "USER_NOT_FOUND");
    }

    // Prevent self-demotion (admins shouldn't be able to change their own role)
    if (targetUserId === adminUserId) {
      throw ValidationError(
        "Cannot modify your own role. Contact another administrator.",
        "SELF_ROLE_MODIFICATION_FORBIDDEN",
      );
    }

    // Update user role using dedicated repository method
    const updatedUser = await userRepository.updateUserRole(
      targetUserId,
      validatedData.role,
    );

    logger.info("User role updated", {
      targetUserId: targetUserId,
      targetUsername: targetUser.username,
      oldRole: targetUser.role,
      newRole: validatedData.role,
      adminUserId: adminUserId,
    });

    return {
      user: updatedUser,
      message: "User role updated successfully",
    };
  } catch (error) {
    throw transformError(error, "updateUserRole");
  }
};

module.exports = {
  registerUser,
  loginUser,
  refreshAccessToken,
  logoutUser,
  logoutAllDevices,
  validateToken,
  changePassword,
  updateUserProfile,
  getUserProfile,
  getUserSessions,
  getUsers,
  updateUserRole,
};
