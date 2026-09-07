/**
 * Validates email format
 * @param {string} email - Email address to validate
 * @returns {boolean} - True if valid, false otherwise
 */
export const validateEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

/**
 * Validates password strength
 * @param {string} password - Password to validate
 * @returns {Object} - { valid: boolean, message: string }
 */
export const validatePassword = (password) => {
  if (password.length < 8) {
    return { valid: false, message: 'Password must be at least 8 characters' };
  }
  if (!/[A-Z]/.test(password)) {
    return {
      valid: false,
      message: 'Password must contain an uppercase letter',
    };
  }
  if (!/[a-z]/.test(password)) {
    return {
      valid: false,
      message: 'Password must contain a lowercase letter',
    };
  }
  if (!/[0-9]/.test(password)) {
    return { valid: false, message: 'Password must contain a number' };
  }
  return { valid: true, message: 'Strong password' };
};

/**
 * Validates required field
 * @param {string} value - Value to validate
 * @returns {boolean} - True if valid, false otherwise
 */
export const validateRequired = (value) => {
  return value && value.trim().length > 0;
};
