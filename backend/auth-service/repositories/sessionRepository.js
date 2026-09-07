const { getDatabase } = require("../config/database");
const {
  transformError,
  ValidationError,
  NotFoundError,
  // eslint-disable-next-line
} = require('../shared/utils/errors');
const { createSessionSchema, cuidSchema } = require("../models/userSchema");

const {
  SESSION_FIELDS,
  ALLOWED_SESSION_UPDATE_FIELDS,
} = require("../lib/constants");

// eslint-disable-next-line
const { createLogger } = require('../shared/utils/logger');
const logger = createLogger("session-repository");
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
 * Create a new session
 * @param {Object} sessionData - Session data to create
 * @returns {Promise<Object>} Created session object
 */
const createSession = async (sessionData) => {
  try {
    const db = await getDB();

    // Validate session data
    const validatedSessionData = createSessionSchema.parse(sessionData);

    logger.info("Creating session with validated data", {
      userId: validatedSessionData.userId,
      expiresAt: validatedSessionData.expiresAt,
      hasToken: !!validatedSessionData.token,
      hasRefreshToken: !!validatedSessionData.refreshToken,
    });

    // Create session in database
    const newSession = await db.session.create({
      data: validatedSessionData,
      select: SESSION_FIELDS.withUser,
    });

    // Validate that session was created successfully
    if (!newSession) {
      throw new Error("Database returned null/undefined for created session");
    }

    logger.info("Session created successfully", {
      sessionId: newSession.id,
      userId: newSession.userId,
    });

    return newSession;
  } catch (error) {
    logger.error("Failed to create session", {
      error: error.message,
      stack: error.stack,
      sessionData: {
        userId: sessionData?.userId,
        hasToken: !!sessionData?.token,
        hasRefreshToken: !!sessionData?.refreshToken,
        expiresAt: sessionData?.expiresAt,
      },
    });

    // CRITICAL FIX: Throw the error instead of returning it
    throw transformError(error, "createSession");
  }
};
/**
 * Find session by access token
 * @param {string} token - Access token
 * @returns {Promise<Object|null>} Session object or null if not found
 */
const findSessionByAccessToken = async (token) => {
  try {
    if (!token) {
      throw ValidationError("Token is required");
    }
    const db = await getDB();
    const session = await db.session.findUnique({
      where: { token: token },
      select: SESSION_FIELDS.withUser,
    });
    if (!session) {
      throw NotFoundError(`Session with token ${token} not found`);
    }
    return session;
  } catch (error) {
    throw transformError(error, "findSessionByAccessToken");
  }
};
/**
 * Find session by access token
 * @param {string} token - Refresh token
 * @returns {Promise<Object|null>} Session object or null if not found
 */
const findSessionByRefreshToken = async (token) => {
  try {
    if (!token) {
      throw ValidationError("Refresh token is required");
    }
    const db = await getDB();
    const session = await db.session.findUnique({
      where: { refreshToken: token },
      select: SESSION_FIELDS.withUser,
    });
    if (!session) {
      throw NotFoundError(`Session with refresh token ${token} not found`);
    }
    return session;
  } catch (error) {
    throw transformError(error, "findSessionByRefreshToken");
  }
};

/**
 * Find session by ID
 * @param {string} sessionId - Session ID
 * @returns {Promise<Object|null>} Session object or null if not found
 */
const findSessionById = async (sessionId) => {
  try {
    const validatedSessionId = cuidSchema.parse(sessionId);
    const db = await getDB();
    const session = await db.session.findUnique({
      where: { id: validatedSessionId },
      select: SESSION_FIELDS.withUser,
    });
    if (!session) {
      throw NotFoundError(`Session with ID ${sessionId} not found`);
    }
    return session;
  } catch (error) {
    throw transformError(error, "findSessionById");
  }
};
/**
 * Update session data
 * @param {string} sessionId - Session ID
 * @param {Object} updateData - Data to update
 * @returns {Promise<Object>} Updated session object
 */
const updateSession = async (sessionId, updateData) => {
  try {
    const validatedSessionId = cuidSchema.parse(sessionId);
    if (!updateData || Object.keys(updateData).length === 0) {
      throw ValidationError("Update Data cannot be empty");
    }
    const db = await getDB();
    const validatedUpdateData = createSessionSchema.partial().parse(updateData);
    const cleanData = Object.fromEntries(
      Object.entries(validatedUpdateData).filter(
        ([key, value]) =>
          ALLOWED_SESSION_UPDATE_FIELDS.includes(key) &&
          value !== undefined &&
          value !== null,
      ),
    );
    if (Object.keys(cleanData).length === 0) {
      throw ValidationError("No valid fields to update");
    }
    const updatedSession = await db.session.update({
      where: { id: validatedSessionId },
      data: {
        ...cleanData,
        updatedAt: new Date(),
      },
      select: SESSION_FIELDS.withUser,
    });
    return updatedSession;
  } catch (error) {
    throw transformError(error, "updateSession");
  }
};
/**
 * Delete a session
 * @param {string} sessionId - Session ID to delete
 * @returns {Promise<Object>} Deletion result
 */
const deleteSession = async (sessionId) => {
  try {
    const validatedSessionId = cuidSchema.parse(sessionId);
    const db = await getDB();
    await db.session.delete({
      where: {
        id: validatedSessionId,
      },
    });
    return {
      message: `Session with ID ${validatedSessionId} deleted successfully`,
    };
  } catch (error) {
    throw transformError(error, "deleteSession");
  }
};
/**
 * Get all active sessions for a user
 * @param {string} userId - User ID
 * @param {boolean} includeExpired - Whether to include expired sessions
 * @returns {Promise<Object>} Object containing array of session objects
 */
const getUserSessions = async (userId, includeExpired = false) => {
  try {
    const validatedUserId = cuidSchema.parse(userId);
    const db = await getDB();
    const whereClause = {
      userId: validatedUserId,
    };
    if (!includeExpired) {
      whereClause.expiresAt = { gt: new Date() };
    }
    logger.info("Fetching user sessions", {
      userId: validatedUserId,
      includeExpired,
      whereClause,
    });
    const sessions = await db.session?.findMany({
      where: whereClause,
      select: SESSION_FIELDS.withUser,
      orderBy: {
        createdAt: "desc",
      },
    });
    logger.info("Sessions retrieved from database", {
      userId: validatedUserId,
      sessionCount: sessions.length,
    });
    const currentTime = new Date();
    const activeSessions = sessions.filter(
      (session) =>
        session.expiresAt && new Date(session.expiresAt) > currentTime,
    );
    const expiredSessions = sessions.filter(
      (session) =>
        session.expiresAt && new Date(session.expiresAt) <= currentTime,
    );
    return {
      sessions: sessions,
      counts: {
        total: sessions.length,
        activeSessions: activeSessions.length,
        expiredSessions: expiredSessions.length,
      },
    };
  } catch (error) {
    logger.error("Failed to get user sessions from repository", {
      error: error.message,
      userId,
      stack: error.stack,
    });
    throw transformError(error, "getUserSessions");
  }
};
/**
 * Clean up expired sessions (utility function for cron jobs)
 * @returns {Promise<Object>} Cleanup result with count
 */
const invalidateUserSessions = async (userId) => {
  try {
    const validatedUserId = cuidSchema.parse(userId);
    const db = await getDB();
    const deletedSessions = await db.session.deleteMany({
      where: { userId: validatedUserId },
    });
    return {
      deletedCount: deletedSessions.count,
    };
  } catch (error) {
    throw transformError(error, "invalidateUserSessions");
  }
};
/**
 * Get session statistics for a user
 * @param {string} userId - User ID
 * @returns {Promise<Object>} Session statistics
 */
const getUserSessionStats = async (userId) => {
  try {
    const validUserId = cuidSchema.parse(userId);
    const db = await getDB();

    const [activeSessions, totalSessions, lastSession] = await Promise.all([
      // Active sessions count
      db.session.count({
        where: {
          userId: validUserId,
          expiresAt: { gt: new Date() },
        },
      }),

      // Total sessions count
      db.session.count({
        where: { userId: validUserId },
      }),

      // Most recent session
      db.session.findFirst({
        where: { userId: validUserId },
        select: {
          createdAt: true,
          ipAddress: true,
          userAgent: true,
        },
        orderBy: { createdAt: "desc" },
      }),
    ]);

    return {
      activeSessions,
      totalSessions,
      lastSession,
    };
  } catch (error) {
    throw transformError(error, "getUserSessionStats");
  }
};

/**
 * Check if a session is valid (not expired)
 * @param {string} sessionId - Session ID
 * @returns {Promise<boolean>} True if session is valid
 */
const isSessionValid = async (sessionId) => {
  try {
    const session = await findSessionById(sessionId);

    if (!session) {
      return false;
    }

    return session.expiresAt > new Date();
  } catch (error) {
    throw transformError(error, "isSessionValid");
  }
};

/**
 * Extend session expiry time
 * @param {string} sessionId - Session ID
 * @param {number} extensionHours - Hours to extend (default: 24)
 * @returns {Promise<Object>} Updated session
 */
const extendSession = async (sessionId, extensionHours = 24) => {
  try {
    const validSessionId = cuidSchema.parse(sessionId);
    const db = await getDB();

    const newExpiryTime = new Date(
      Date.now() + extensionHours * 60 * 60 * 1000,
    );

    const updatedSession = await db.session.update({
      where: { id: validSessionId },
      data: {
        expiresAt: newExpiryTime,
        updatedAt: new Date(),
      },
      select: SESSION_FIELDS.public,
    });

    return updatedSession;
  } catch (error) {
    throw transformError(error, "extendSession");
  }
};

/**
 * Validate session by IP address
 * @param {string} sessionId - Session ID
 * @param {string} currentIP - Current request IP
 * @returns {Promise<boolean>} Whether IP matches
 */
const validateSessionIP = async (sessionId, currentIP) => {
  try {
    const db = await getDB();
    const session = await db.session.findUnique({
      where: { id: sessionId },
      select: { ipAddress: true, id: true },
    });
    if (!session) {
      logger.warn("Session not found for IP validation", { sessionId });
      return false;
    }
    if (!session.ipAddress) {
      logger.debug("No IP stored for session, allowing access", { sessionId });
      return true;
    }
    const ipMatches = session.ipAddress === currentIP;
    logger.debug("Session IP validation", {
      sessionId,
      storedIP: session.ipAddress,
      currentIP,
      matches: ipMatches,
    });
    return ipMatches;
  } catch (error) {
    logger.error("Failed to validate session IP", {
      error: error.message,
      sessionId,
      currentIP,
      stack: error.stack,
    });
    return false;
  }
};
module.exports = {
  // Core session management
  createSession,
  findSessionByAccessToken,
  findSessionByRefreshToken,
  findSessionById,
  updateSession,
  deleteSession,
  // User session management
  getUserSessions,
  invalidateUserSessions,
  getUserSessionStats,
  // session utilities
  isSessionValid,
  extendSession,
  validateSessionIP,
};
