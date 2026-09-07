const LOG_LEVELS = {
  error: 0,
  warn: 1,
  info: 2,
  debug: 3,
};

const currentLevel = LOG_LEVELS[process.env.LOG_LEVEL || "info"];

const logger = {
  error: (...args) => {
    if (currentLevel >= LOG_LEVELS.error) {
      console.error("[ERROR]", new Date().toISOString(), ...args);
    }
  },
  warn: (...args) => {
    if (currentLevel >= LOG_LEVELS.warn) {
      console.warn("[WARN]", new Date().toISOString(), ...args);
    }
  },
  info: (...args) => {
    if (currentLevel >= LOG_LEVELS.info) {
      console.info("[INFO]", new Date().toISOString(), ...args);
    }
  },
  debug: (...args) => {
    if (currentLevel >= LOG_LEVELS.debug) {
      console.debug("[DEBUG]", new Date().toISOString(), ...args);
    }
  },
};

module.exports = logger;
