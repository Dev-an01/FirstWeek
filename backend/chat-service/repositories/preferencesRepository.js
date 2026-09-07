// backend/chat-service/repositories/preferencesRepository.js

const userDb = require("./userDbClient"); // Use userDb for auth database access
const { createLogger } = require("../shared/utils/logger");

const logger = createLogger("preferences-repository");

/**
 * Preferences Repository
 * Handles all database operations for user preferences
 */

/**
 * Get user preferences by userId
 * @param {string} userId - User ID
 * @returns {Promise<Object|null>} User preferences or null if not found
 */
const getPreferencesByUserId = async (userId) => {
  try {
    logger.debug("Getting preferences for user", { userId });

    const preferences = await userDb.userPreferences.findUnique({
      where: { userId },
    });

    if (preferences) {
      logger.debug("Preferences found", {
        userId,
        preferencesId: preferences.id,
      });
    } else {
      logger.debug("No preferences found for user", { userId });
    }

    return preferences;
  } catch (error) {
    logger.error("Error getting preferences", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

/**
 * Create default preferences for a new user
 * @param {string} userId - User ID
 * @returns {Promise<Object>} Created preferences
 */
const createDefaultPreferences = async (userId) => {
  try {
    logger.debug("Creating default preferences for user", { userId });

    const preferences = await userDb.userPreferences.create({
      data: {
        userId,
        // Defaults are set in Prisma schema
      },
    });

    logger.info("Default preferences created", {
      userId,
      preferencesId: preferences.id,
    });

    return preferences;
  } catch (error) {
    logger.error("Error creating default preferences", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

/**
 * Update user preferences
 * @param {string} userId - User ID
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated preferences
 */
const updatePreferences = async (userId, updates) => {
  try {
    logger.debug("Updating preferences for user", { userId, updates });

    const preferences = await userDb.userPreferences.upsert({
      where: { userId },
      update: updates,
      create: {
        userId,
        ...updates,
      },
    });

    logger.info("Preferences updated", {
      userId,
      preferencesId: preferences.id,
    });

    return preferences;
  } catch (error) {
    logger.error("Error updating preferences", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

/**
 * Get or create preferences for a user
 * If preferences don't exist, creates them with defaults
 * @param {string} userId - User ID
 * @returns {Promise<Object>} User preferences
 */
const getOrCreatePreferences = async (userId) => {
  try {
    logger.debug("Getting or creating preferences for user", { userId });

    let preferences = await getPreferencesByUserId(userId);

    if (!preferences) {
      logger.debug("Preferences not found, creating defaults", { userId });
      preferences = await createDefaultPreferences(userId);
    }

    return preferences;
  } catch (error) {
    logger.error("Error in getOrCreatePreferences", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

/**
 * Delete user preferences
 * @param {string} userId - User ID
 * @returns {Promise<Object>} Deleted preferences
 */
const deletePreferences = async (userId) => {
  try {
    logger.debug("Deleting preferences for user", { userId });

    const preferences = await userDb.userPreferences.delete({
      where: { userId },
    });

    logger.info("Preferences deleted", { userId });

    return preferences;
  } catch (error) {
    logger.error("Error deleting preferences", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

/**
 * Reset preferences to defaults
 * @param {string} userId - User ID
 * @returns {Promise<Object>} Reset preferences
 */
const resetToDefaults = async (userId) => {
  try {
    logger.debug("Resetting preferences to defaults", { userId });

    const preferences = await userDb.userPreferences.update({
      where: { userId },
      data: {
        defaultProfileId: "exec_003_test",
        defaultTopK: 5,
        defaultMinScore: 0.15,
        streamingEnabled: true,
        theme: "light",
        language: "en",
      },
    });

    logger.info("Preferences reset to defaults", { userId });

    return preferences;
  } catch (error) {
    logger.error("Error resetting preferences", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

module.exports = {
  getPreferencesByUserId,
  createDefaultPreferences,
  updatePreferences,
  getOrCreatePreferences,
  deletePreferences,
  resetToDefaults,
};
