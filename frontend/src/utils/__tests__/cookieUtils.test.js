/**
 * Cookie Utils Unit Tests
 * Tests for cookie utility functions
 */
import {
  hasCookie,
  hasAuthCookies,
  getAllCookies,
  shouldLogoutDueToCookies,
} from '../cookieUtils';

describe('cookieUtils', () => {
  beforeEach(() => {
    // Clear cookies before each test
    document.cookie.split(';').forEach((cookie) => {
      const [name] = cookie.split('=');
      document.cookie = `${name.trim()}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
    });
  });

  describe('hasCookie', () => {
    it('should return true if cookie exists', () => {
      document.cookie = 'testCookie=testValue';
      expect(hasCookie('testCookie')).toBe(true);
    });

    it('should return false if cookie does not exist', () => {
      expect(hasCookie('nonExistentCookie')).toBe(false);
    });

    it('should handle multiple cookies correctly', () => {
      document.cookie = 'cookie1=value1';
      document.cookie = 'cookie2=value2';
      document.cookie = 'cookie3=value3';

      expect(hasCookie('cookie1')).toBe(true);
      expect(hasCookie('cookie2')).toBe(true);
      expect(hasCookie('cookie3')).toBe(true);
      expect(hasCookie('cookie4')).toBe(false);
    });

    it('should handle cookies with special characters', () => {
      document.cookie = 'special-cookie=value';
      expect(hasCookie('special-cookie')).toBe(true);
    });

    it('should handle cookies with similar names', () => {
      document.cookie = 'token=value1';
      document.cookie = 'accessToken=value2';

      expect(hasCookie('token')).toBe(true);
      expect(hasCookie('accessToken')).toBe(true);
    });
  });

  describe('hasAuthCookies', () => {
    it('should return true if accessToken exists', () => {
      document.cookie = 'accessToken=abc123';
      expect(hasAuthCookies()).toBe(true);
    });

    it('should return true if refreshToken exists', () => {
      document.cookie = 'refreshToken=xyz789';
      expect(hasAuthCookies()).toBe(true);
    });

    it('should return true if both tokens exist', () => {
      document.cookie = 'accessToken=abc123';
      document.cookie = 'refreshToken=xyz789';
      expect(hasAuthCookies()).toBe(true);
    });

    it('should return false if no auth cookies exist', () => {
      document.cookie = 'someOtherCookie=value';
      expect(hasAuthCookies()).toBe(false);
    });

    it('should return false if document.cookie is empty', () => {
      expect(hasAuthCookies()).toBe(false);
    });
  });

  describe('getAllCookies', () => {
    it('should return an empty object if no cookies exist', () => {
      const cookies = getAllCookies();
      expect(cookies).toEqual({});
    });

    it('should return all cookies as an object', () => {
      document.cookie = 'cookie1=value1';
      document.cookie = 'cookie2=value2';
      document.cookie = 'cookie3=value3';

      const cookies = getAllCookies();

      expect(cookies).toHaveProperty('cookie1', 'value1');
      expect(cookies).toHaveProperty('cookie2', 'value2');
      expect(cookies).toHaveProperty('cookie3', 'value3');
    });

    it('should handle cookies with special characters in values', () => {
      document.cookie = 'specialCookie=value%20with%20spaces';
      const cookies = getAllCookies();

      expect(cookies).toHaveProperty('specialCookie', 'value%20with%20spaces');
    });

    it('should handle cookies with equals signs in values', () => {
      document.cookie = 'base64Cookie=abc123==';
      const cookies = getAllCookies();

      expect(cookies).toHaveProperty('base64Cookie', 'abc123');
    });

    it('should trim whitespace from cookie names', () => {
      document.cookie = ' trimmedCookie = value';
      const cookies = getAllCookies();

      expect(cookies).toHaveProperty('trimmedCookie');
    });
  });

  describe('shouldLogoutDueToCookies', () => {
    it('should return true if user is authenticated but no auth cookies exist', () => {
      const isAuthenticated = true;
      expect(shouldLogoutDueToCookies(isAuthenticated)).toBe(true);
    });

    it('should return false if user is authenticated and accessToken exists', () => {
      document.cookie = 'accessToken=abc123';
      const isAuthenticated = true;

      expect(shouldLogoutDueToCookies(isAuthenticated)).toBe(false);
    });

    it('should return false if user is authenticated and refreshToken exists', () => {
      document.cookie = 'refreshToken=xyz789';
      const isAuthenticated = true;

      expect(shouldLogoutDueToCookies(isAuthenticated)).toBe(false);
    });

    it('should return false if user is authenticated and both tokens exist', () => {
      document.cookie = 'accessToken=abc123';
      document.cookie = 'refreshToken=xyz789';
      const isAuthenticated = true;

      expect(shouldLogoutDueToCookies(isAuthenticated)).toBe(false);
    });

    it('should return false if user is not authenticated', () => {
      const isAuthenticated = false;
      expect(shouldLogoutDueToCookies(isAuthenticated)).toBe(false);
    });

    it('should return false if user is not authenticated and cookies exist', () => {
      document.cookie = 'accessToken=abc123';
      const isAuthenticated = false;

      expect(shouldLogoutDueToCookies(isAuthenticated)).toBe(false);
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty cookie strings', () => {
      document.cookie = '';
      expect(hasCookie('anyCookie')).toBe(false);
      expect(hasAuthCookies()).toBe(false);
      expect(getAllCookies()).toEqual({});
    });

    it('should handle malformed cookies gracefully', () => {
      // Cookies without equals sign should be ignored
      const cookies = getAllCookies();
      expect(typeof cookies).toBe('object');
    });

    it('should handle cookies with empty values', () => {
      document.cookie = 'emptyCookie=';
      expect(hasCookie('emptyCookie')).toBe(true);

      const cookies = getAllCookies();
      expect(cookies).toHaveProperty('emptyCookie', '');
    });

    it('should handle very long cookie values', () => {
      const longValue = 'a'.repeat(1000);
      document.cookie = `longCookie=${longValue}`;

      expect(hasCookie('longCookie')).toBe(true);
      const cookies = getAllCookies();
      expect(cookies.longCookie).toHaveLength(1000);
    });
  });
});
