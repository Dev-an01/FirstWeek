/**
 * Logger Utility
 *
 * Conditional logging that only outputs in development mode.
 * In production, only errors are logged to avoid performance penalties
 * and potential security issues from leaking internal state.
 *
 * Usage:
 *   import logger from '../utils/logger';
 *   logger.log('[Component]', 'Debug message', data);
 *   logger.error('[Component]', 'Error message', error);
 */

const isDevelopment = import.meta.env.DEV;

const logger = {
  /**
   * Log debug information (only in development)
   */
  log: (...args) => {
    if (isDevelopment) {
      console.log(...args);
    }
  },

  /**
   * Log debug information (alias for log)
   */
  debug: (...args) => {
    if (isDevelopment) {
      console.log(...args);
    }
  },

  /**
   * Log informational messages (only in development)
   */
  info: (...args) => {
    if (isDevelopment) {
      console.info(...args);
    }
  },

  /**
   * Log warnings (only in development)
   */
  warn: (...args) => {
    if (isDevelopment) {
      console.warn(...args);
    }
  },

  /**
   * Log errors (always logged, even in production)
   */
  error: (...args) => {
    console.error(...args);
  },
};

export default logger;
