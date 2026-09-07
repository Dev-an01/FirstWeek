// backend/chat-service/services/preferencesService.js

const preferencesRepository = require("../repositories/preferencesRepository");
const { createLogger } = require("../shared/utils/logger");

const logger = createLogger("preferences-service");

/**
 * Preferences Service
 * Business logic for user preferences management
 */

/**
 * Get user preferences
 * Creates default preferences if they don't exist
 * @param {string} userId - User ID
 * @returns {Promise<Object>} User preferences
 */
const getUserPreferences = async (userId) => {
  try {
    logger.debug("Getting preferences for user", { userId });

    const preferences =
      await preferencesRepository.getOrCreatePreferences(userId);

    return preferences;
  } catch (error) {
    logger.error("Error getting user preferences", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

/**
 * Update user preferences
 * Validates and sanitizes input before updating
 * @param {string} userId - User ID
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated preferences
 */
const updateUserPreferences = async (userId, updates) => {
  try {
    logger.info("Updating preferences for user", { userId, updates });

    // Validate updates
    const validatedUpdates = validatePreferencesUpdate(updates);

    const preferences = await preferencesRepository.updatePreferences(
      userId,
      validatedUpdates,
    );

    return preferences;
  } catch (error) {
    logger.error("Error updating user preferences", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

/**
 * Reset user preferences to defaults
 * @param {string} userId - User ID
 * @returns {Promise<Object>} Reset preferences
 */
const resetUserPreferences = async (userId) => {
  try {
    logger.info("Resetting preferences to defaults", { userId });

    const preferences = await preferencesRepository.resetToDefaults(userId);

    return preferences;
  } catch (error) {
    logger.error("Error resetting preferences", {
      error: error.message,
      userId,
    });
    throw error;
  }
};

/**
 * Get specific preference field
 * @param {string} userId - User ID
 * @param {string} field - Field name to retrieve
 * @returns {Promise<any>} Field value
 */
const getPreferenceField = async (userId, field) => {
  try {
    logger.debug("Getting preference field", { userId, field });

    const preferences = await getUserPreferences(userId);

    if (!preferences || !(field in preferences)) {
      throw new Error(`Preference field '${field}' not found`);
    }

    return preferences[field];
  } catch (error) {
    logger.error("Error getting preference field", {
      error: error.message,
      userId,
      field,
    });
    throw error;
  }
};

/**
 * Validate preferences update data
 * @param {Object} updates - Update data to validate
 * @returns {Object} Validated and sanitized updates
 * @throws {Error} If validation fails
 */
const validatePreferencesUpdate = (updates) => {
  const validatedUpdates = {};

  // Validate defaultProfileId
  if (updates.defaultProfileId !== undefined) {
    if (
      typeof updates.defaultProfileId === "string" ||
      updates.defaultProfileId === null
    ) {
      validatedUpdates.defaultProfileId = updates.defaultProfileId;
    } else {
      throw new Error("defaultProfileId must be a string or null");
    }
  }

  // Validate defaultTopK
  if (updates.defaultTopK !== undefined) {
    const topK = parseInt(updates.defaultTopK, 10);
    if (isNaN(topK) || topK < 1 || topK > 20) {
      throw new Error("defaultTopK must be a number between 1 and 20");
    }
    validatedUpdates.defaultTopK = topK;
  }

  // Validate defaultMinScore
  if (updates.defaultMinScore !== undefined) {
    const minScore = parseFloat(updates.defaultMinScore);
    if (isNaN(minScore) || minScore < 0 || minScore > 1) {
      throw new Error("defaultMinScore must be a number between 0 and 1");
    }
    validatedUpdates.defaultMinScore = minScore;
  }

  // Validate streamingEnabled
  if (updates.streamingEnabled !== undefined) {
    if (typeof updates.streamingEnabled !== "boolean") {
      throw new Error("streamingEnabled must be a boolean");
    }
    validatedUpdates.streamingEnabled = updates.streamingEnabled;
  }

  // Validate theme
  if (updates.theme !== undefined) {
    const validThemes = ["light", "dark", "auto"];
    if (!validThemes.includes(updates.theme) && updates.theme !== null) {
      throw new Error(`theme must be one of: ${validThemes.join(", ")}`);
    }
    validatedUpdates.theme = updates.theme;
  }

  // Validate language
  if (updates.language !== undefined) {
    if (typeof updates.language === "string" || updates.language === null) {
      validatedUpdates.language = updates.language;
    } else {
      throw new Error("language must be a string or null");
    }
  }

  if (Object.keys(validatedUpdates).length === 0) {
    throw new Error("No valid updates provided");
  }

  return validatedUpdates;
};

module.exports = {
  getUserPreferences,
  updateUserPreferences,
  resetUserPreferences,
  getPreferenceField,
};
