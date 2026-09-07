/**
 * Cookie Utility Functions
 * Handles cookie detection and validation for authentication
 */

/**
 * Check if a specific cookie exists
 * @param {string} name - Cookie name
 * @returns {boolean} - True if cookie exists
 */
export const hasCookie = (name) => {
  const cookies = document.cookie.split(';');
  return cookies.some((cookie) => {
    const [cookieName] = cookie.trim().split('=');
    return cookieName === name;
  });
};

/**
 * Check if authentication cookies exist
 * Checks for either accessToken or refreshToken
 * @returns {boolean} - True if any auth cookie exists
 */
export const hasAuthCookies = () => {
  return hasCookie('accessToken') || hasCookie('refreshToken');
};

/**
 * Get all cookies as an object
 * @returns {Object} - Object with cookie names as keys
 */
export const getAllCookies = () => {
  const cookies = {};
  document.cookie.split(';').forEach((cookie) => {
    const [name, value] = cookie.trim().split('=');
    if (name) {
      cookies[name] = value;
    }
  });
  return cookies;
};

/**
 * Check if user should be logged out based on cookie state
 * @param {boolean} isAuthenticated - Current auth state
 * @returns {boolean} - True if logout is needed
 */
export const shouldLogoutDueToCookies = (isAuthenticated) => {
  // If user is authenticated but cookies are missing, they should be logged out
  return isAuthenticated && !hasAuthCookies();
};
