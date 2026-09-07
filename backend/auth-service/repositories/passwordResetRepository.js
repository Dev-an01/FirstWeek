// auth-service/repositories/passwordResetRepository.js
const { getDatabase } = require("../config/database");
const {
  transformError,
  ValidationError,
  // eslint-disable-next-line
} = require('../shared/utils/errors');
const {
  createPasswordResetSchema,
  cuidSchema,
} = require("../models/userSchema");

const {
  createLogger,
  // eslint-disable-next-line
} = require('../shared/utils/logger');

const logger = createLogger("password-reset-repository");

let dbInstance = null;

/**
 * Get database instance (singleton pattern)
 * @returns {Promise<Object>} Database instance
 */
const getDB = async () => {
  if (!dbInstance) {
    dbInstance = await getDatabase();
  }
  return dbInstance;
};

/**
 * Create a new password reset token
 * @param {Object} resetData - Password reset data
 * @returns {Promise<Object>} Created password reset record
 */
const createPasswordReset = async (resetData) => {
  try {
    const db = await getDB();

    // Validate reset data
    const validatedResetData = createPasswordResetSchema.parse(resetData);
    // Delete any existing reset tokens for this user
    await db.passwordReset.deleteMany({
      where: {
        userId: validatedResetData.userId,
      },
    });

    logger.info("Creating password reset token", {
      userId: validatedResetData.userId,
      email: validatedResetData.email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      expiresAt: validatedResetData.expiresAt,
    });

    // Create new password reset record
    const newReset = await db.passwordReset.create({
      data: validatedResetData,
      select: {
        id: true,
        userId: true,
        email: true,
        token: true,
        expiresAt: true,
        isUsed: true,
        createdAt: true,
      },
    });

    logger.info("Password reset token created successfully", {
      resetId: newReset.id,
      userId: newReset.userId,
    });

    return newReset;
  } catch (error) {
    logger.error("Failed to create password reset token", {
      error: error.message,
      stack: error.stack,
      userId: resetData?.userId,
    });
    throw transformError(error, "createPasswordReset");
  }
};

/**
 * Find password reset by token
 * @param {string} token - Reset token
 * @returns {Promise<Object|null>} Password reset record or null
 */
const findPasswordResetByToken = async (token) => {
  try {
    if (!token) {
      throw ValidationError("Reset token is required");
    }

    const db = await getDB();

    const reset = await db.passwordReset.findFirst({
      where: {
        token: token,
        isUsed: false,
        expiresAt: { gt: new Date() },
      },
      select: {
        id: true,
        userId: true,
        email: true,
        token: true,
        expiresAt: true,
        isUsed: true,
        attempts: true,
        createdAt: true,
        user: {
          select: {
            id: true,
            email: true,
            username: true,
            firstName: true,
            lastName: true,
            isActive: true,
          },
        },
      },
    });

    if (!reset) {
      logger.warn("Password reset token not found or expired", {
        token: `${token.substring(0, 8)}...`,
      });
    }

    return reset;
  } catch (error) {
    logger.error("Failed to find password reset by token", {
      error: error.message,
      token: token ? `${token.substring(0, 8)}...` : "missing",
    });
    throw transformError(error, "findPasswordResetByToken");
  }
};

/**
 * Find password reset by user ID
 * @param {string} userId - User ID
 * @returns {Promise<Object|null>} Active password reset record or null
 */
const findActivePasswordResetByUserId = async (userId) => {
  try {
    const validUserId = cuidSchema.parse(userId);
    const db = await getDB();

    const reset = await db.passwordReset.findFirst({
      where: {
        userId: validUserId,
        isUsed: false,
        expiresAt: { gt: new Date() },
      },
      select: {
        id: true,
        userId: true,
        email: true,
        expiresAt: true,
        attempts: true,
        createdAt: true,
      },
      orderBy: { createdAt: "desc" },
    });

    return reset;
  } catch (error) {
    throw transformError(error, "findActivePasswordResetByUserId");
  }
};

/**
 * Mark password reset as used
 * @param {string} resetId - Password reset ID
 * @returns {Promise<Object>} Updated password reset record
 */
const markPasswordResetAsUsed = async (resetId) => {
  try {
    const validResetId = cuidSchema.parse(resetId);
    const db = await getDB();

    const updatedReset = await db.passwordReset.update({
      where: { id: validResetId },
      data: {
        isUsed: true,
        usedAt: new Date(),
      },
      select: {
        id: true,
        userId: true,
        isUsed: true,
        usedAt: true,
      },
    });

    logger.info("Password reset marked as used", {
      resetId: updatedReset.id,
      userId: updatedReset.userId,
    });

    return updatedReset;
  } catch (error) {
    throw transformError(error, "markPasswordResetAsUsed");
  }
};

/**
 * Increment reset attempts
 * @param {string} resetId - Password reset ID
 * @returns {Promise<Object>} Updated password reset record
 */
const incrementResetAttempts = async (resetId) => {
  try {
    const validResetId = cuidSchema.parse(resetId);
    const db = await getDB();

    const updatedReset = await db.passwordReset.update({
      where: { id: validResetId },
      data: {
        attempts: { increment: 1 },
      },
      select: {
        id: true,
        attempts: true,
      },
    });

    return updatedReset;
  } catch (error) {
    throw transformError(error, "incrementResetAttempts");
  }
};

/**
 * Clean up expired password reset tokens
 * @returns {Promise<Object>} Cleanup result
 */
const cleanupExpiredPasswordResets = async () => {
  try {
    const db = await getDB();

    const deletedResets = await db.passwordReset.deleteMany({
      where: {
        OR: [{ expiresAt: { lt: new Date() } }, { isUsed: true }],
      },
    });

    logger.info("Expired password resets cleaned up", {
      deletedCount: deletedResets.count,
    });

    return { deletedCount: deletedResets.count };
  } catch (error) {
    throw transformError(error, "cleanupExpiredPasswordResets");
  }
};

/**
 * Get password reset statistics for a user
 * @param {string} userId - User ID
 * @returns {Promise<Object>} Reset statistics
 */
const getPasswordResetStats = async (userId) => {
  try {
    const validUserId = cuidSchema.parse(userId);
    const db = await getDB();

    const [totalResets, activeResets, lastReset] = await Promise.all([
      // Total reset requests
      db.passwordReset.count({
        where: { userId: validUserId },
      }),

      // Active (unused and not expired) resets
      db.passwordReset.count({
        where: {
          userId: validUserId,
          isUsed: false,
          expiresAt: { gt: new Date() },
        },
      }),

      // Most recent reset request
      db.passwordReset.findFirst({
        where: { userId: validUserId },
        select: {
          createdAt: true,
          isUsed: true,
          expiresAt: true,
        },
        orderBy: { createdAt: "desc" },
      }),
    ]);

    return {
      totalResets,
      activeResets,
      lastReset,
    };
  } catch (error) {
    throw transformError(error, "getPasswordResetStats");
  }
};

module.exports = {
  createPasswordReset,
  findPasswordResetByToken,
  findActivePasswordResetByUserId,
  markPasswordResetAsUsed,
  incrementResetAttempts,
  cleanupExpiredPasswordResets,
  getPasswordResetStats,
};
