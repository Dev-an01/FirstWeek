// backend/shared/utils/errors.js

/**
 * Shared error handling utilities for FirstWeek microservices
 * Used by: auth-service, video-processing-service, subtitle-service, etc.
 */
const { ZodError } = require("zod");
const ERROR_CODES = require("../constants/errorCodes");

/**
 * Create a custom error factory function
 */
function createErrorFactory(name, defaultCode) {
  return (message, code = defaultCode, metadata = {}) => {
    const error = new Error(message);
    error.name = name;
    error.code = code;
    error.metadata = metadata;
    error.timestamp = new Date().toISOString();

    // Maintain stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(error, createErrorFactory);
    }

    return error;
  };
}

// Error factories for all FirstWeek services
const ValidationError = createErrorFactory(
  "ValidationError",
  ERROR_CODES.VALIDATION_ERROR,
);
const ConflictError = createErrorFactory(
  "ConflictError",
  ERROR_CODES.CONFLICT_ERROR,
);
const NotFoundError = createErrorFactory(
  "NotFoundError",
  ERROR_CODES.NOT_FOUND,
);
const BusinessLogicError = createErrorFactory(
  "BusinessLogicError",
  ERROR_CODES.BUSINESS_LOGIC_ERROR,
);
const DatabaseError = createErrorFactory(
  "DatabaseError",
  ERROR_CODES.DATABASE_ERROR,
);
const AuthenticationError = createErrorFactory(
  "AuthenticationError",
  ERROR_CODES.AUTHENTICATION_ERROR,
);
const AuthorizationError = createErrorFactory(
  "AuthorizationError",
  ERROR_CODES.AUTHORIZATION_ERROR,
);

/**
 * Error type checking functions
 */
const isValidationError = (error) => error.name === "ValidationError";
const isConflictError = (error) => error.name === "ConflictError";
const isNotFoundError = (error) => error.name === "NotFoundError";
const isAuthenticationError = (error) => error.name === "AuthenticationError";
const isAuthorizationError = (error) => error.name === "AuthorizationError";
/**
 * Type guard to check if an error is a ZodError
 * @param {any} error - The error to check
 * @returns {boolean} - True if the error is a ZodError
 */
const isZodError = (error) => {
  return (
    error instanceof ZodError ||
    (error && error.name === "ZodError") ||
    (error && Array.isArray(error.errors) && error.errors.length > 0)
  );
};
/** Transforms a Zod validation error into a user-friendly format
 * @param {Error|ZodError} zodError - The Zod error to transform
 * @param {string} context - Optional context for the error
 * @returns {ValidationError} - Transformed validation error
 */
const transformZodError = (zodError, context = "") => {
  // Early return if not a Zod error
  if (!isZodError(zodError)) {
    return zodError;
  }

  try {
    // Handle different Zod error formats
    const errors = zodError.errors || zodError.issues || [];

    if (!Array.isArray(errors) || errors.length === 0) {
      return ValidationError(
        context
          ? `${context}: Invalid input provided`
          : "Invalid input provided",
        ERROR_CODES.VALIDATION_ERROR,
        {
          validationErrors: [],
          zodError: true,
          context,
        },
      );
    }

    // Extract and format validation errors
    const validationDetails = errors.map((error) => {
      const field = Array.isArray(error.path)
        ? error.path.join(".")
        : error.path || "root";

      return {
        field,
        message: error.message || "Invalid value",
        code: error.code || "invalid",
        expected: error.expected,
        received: error.received,
        // Include additional context for specific error types
        ...(error.minimum && { minimum: error.minimum }),
        ...(error.maximum && { maximum: error.maximum }),
        ...(error.options && { validOptions: error.options }),
      };
    });

    // Create user-friendly error messages
    const fieldMessages = validationDetails.map((detail) => {
      if (detail.field === "root") {
        return detail.message;
      }
      return `${detail.field}: ${detail.message}`;
    });

    // Create comprehensive error message
    const primaryMessage = fieldMessages.join("; ");
    const fullMessage = context
      ? `${context} - ${primaryMessage}`
      : primaryMessage;

    // Return properly constructed ValidationError
    return ValidationError(fullMessage, ERROR_CODES.VALIDATION_ERROR, {
      validationErrors: validationDetails,
      zodError: true,
      context,
      fieldCount: validationDetails.length,
    });
  } catch (transformError) {
    // Fallback error handling
    console.error("Error transforming Zod error:", transformError);

    const fallbackMessage = context
      ? `${context}: Validation failed - please check your input`
      : "Validation failed - please check your input";

    return ValidationError(fallbackMessage, ERROR_CODES.VALIDATION_ERROR, {
      validationErrors: [],
      zodError: true,
      context,
      transformError: true,
    });
  }
};

/**
 * Service-specific error transformers
 */
const transformPrismaError = (prismaError, operation) => {
  console.error(`Database error in ${operation}:`, prismaError);
  switch (prismaError.code) {
    case "P2002":
      const field = prismaError.meta?.target?.[0] || "field";
      return ConflictError(
        `${field} already exists`,
        ERROR_CODES.UNIQUE_VIOLATION,
      );

    case "P2025":
      return NotFoundError("Resource not found", ERROR_CODES.RECORD_NOT_FOUND);
    case "P2003":
      return BusinessLogicError(
        "Cannot delete resource with existing dependencies",
        ERROR_CODES.BUSINESS_LOGIC_ERROR,
      );
    default:
      return DatabaseError(
        "Database operation failed",
        ERROR_CODES.DB_OPERATION_FAILED,
        {
          operation,
          prismaCode: prismaError.code,
          message: prismaError.message,
        },
      );
  }
};

/**
 * Universal error transformer that handles multiple error types
 * @param {Error} error - Any error object
 * @param {string} context - Context where error occurred
 * @returns {Error} Transformed error
 */
const transformError = (error, context = "") => {
  // Handle Zod validation errors
  if (isZodError(error)) {
    return transformZodError(error, context);
  }

  // Handle Prisma errors
  if (
    error.code &&
    typeof error.code === "string" &&
    error.code.startsWith("P")
  ) {
    return transformPrismaError(error, context);
  }

  // Handle already transformed custom errors
  if (error.name && error.name.endsWith("Error") && error.code) {
    return error; // Already a custom error, don't transform
  }

  // Default to business logic error for unhandled cases
  return BusinessLogicError(
    error.message || "An unexpected error occurred",
    ERROR_CODES.BUSINESS_LOGIC_ERROR,
    { originalError: error.name, context },
  );
};
module.exports = {
  // Error factories
  ValidationError,
  ConflictError,
  NotFoundError,
  BusinessLogicError,
  DatabaseError,
  AuthenticationError,
  AuthorizationError,
  // Type checkers
  isValidationError,
  isConflictError,
  isNotFoundError,
  isAuthenticationError,
  isAuthorizationError,

  // Transformers
  transformPrismaError,
  transformZodError,
  transformError,
};
