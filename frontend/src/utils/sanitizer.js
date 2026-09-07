/**
 * Sanitizes user input by removing dangerous characters
 * @param {string} input - Input string to sanitize
 * @returns {string} - Sanitized string
 */
export const sanitizeInput = (input) => {
  if (typeof input !== 'string') return '';

  // Remove < and > to prevent HTML injection
  return input.replace(/[<>]/g, '');
};

/**
 * Escapes HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} - Escaped text
 */
export const escapeHtml = (text) => {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return text.replace(/[&<>"']/g, (m) => map[m]);
};

/**
 * Truncates string to maximum length
 * @param {string} str - String to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} - Truncated string
 */
export const truncateString = (str, maxLength = 255) => {
  if (str.length <= maxLength) return str;
  return str.substring(0, maxLength);
};
