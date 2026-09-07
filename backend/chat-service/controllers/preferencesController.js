// backend/chat-service/controllers/preferencesController.js

const { createLogger } = require("../shared/utils/logger");
const preferencesService = require("../services/preferencesService");
const {
  transformError,
  isValidationError,
  isNotFoundError,
} = require("../shared/utils/errors");

const logger = createLogger(
  "preferencesController",
  process.env.LOG_LEVEL || "info",
);

/**
 * Helper function to get HTTP status code from error type
 * @param {Error} error - Transformed error object
 * @returns {number} HTTP status code
 */
const getErrorStatusCode = (error) => {
  if (isValidationError(error)) return 400;
  if (isNotFoundError(error)) return 404;
  if (error.name === "AuthenticationError") return 401;
  if (error.name === "AuthorizationError") return 403;
  return 500; // Internal server error for all other cases
};

/**
 * Get user preferences
 * GET /api/chat/preferences
 */
const getPreferences = async (req, res) => {
  try {
    const userId = req.user.id;

    logger.info("Get preferences request", { userId });

    const preferences = await preferencesService.getUserPreferences(userId);

    res.json({
      success: true,
      message: "Preferences retrieved successfully",
      data: {
        preferences,
      },
    });
  } catch (error) {
    logger.error("Error getting preferences", {
      error: error.message,
      userId: req.user?.id,
    });

    const transformedError = transformError(error);
    const statusCode = getErrorStatusCode(transformedError);

    res.status(statusCode).json({
      success: false,
      error: {
        message: transformedError.message,
        code: transformedError.code || "PREFERENCES_ERROR",
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Update user preferences
 * PATCH /api/chat/preferences
 * Body: { defaultProfileId?, defaultTopK?, defaultMinScore?, streamingEnabled?, theme?, language? }
 */
const updatePreferences = async (req, res) => {
  try {
    const userId = req.user.id;
    const updates = req.body;

    logger.info("Update preferences request", { userId, updates });

    // Validate that at least one field is provided
    if (Object.keys(updates).length === 0) {
      return res.status(400).json({
        success: false,
        error: {
          message: "No updates provided",
          code: "VALIDATION_ERROR",
        },
        timestamp: new Date().toISOString(),
      });
    }

    const preferences = await preferencesService.updateUserPreferences(
      userId,
      updates,
    );

    res.json({
      success: true,
      message: "Preferences updated successfully",
      data: {
        preferences,
      },
    });
  } catch (error) {
    logger.error("Error updating preferences", {
      error: error.message,
      userId: req.user?.id,
    });

    const transformedError = transformError(error);
    const statusCode = getErrorStatusCode(transformedError);

    res.status(statusCode).json({
      success: false,
      error: {
        message: transformedError.message,
        code: transformedError.code || "PREFERENCES_UPDATE_ERROR",
      },
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * Reset preferences to defaults
 * POST /api/chat/preferences/reset
 */
const resetPreferences = async (req, res) => {
  try {
    const userId = req.user.id;

    logger.info("Reset preferences request", { userId });

    const preferences = await preferencesService.resetUserPreferences(userId);

    res.json({
      success: true,
      message: "Preferences reset to defaults successfully",
      data: {
        preferences,
      },
    });
  } catch (error) {
    logger.error("Error resetting preferences", {
      error: error.message,
      userId: req.user?.id,
    });

    const transformedError = transformError(error);
    const statusCode = getErrorStatusCode(transformedError);

    res.status(statusCode).json({
      success: false,
      error: {
        message: transformedError.message,
        code: transformedError.code || "PREFERENCES_RESET_ERROR",
      },
      timestamp: new Date().toISOString(),
    });
  }
};

module.exports = {
  getPreferences,
  updatePreferences,
  resetPreferences,
};
