/**
 * Zustand Auth Store
 * Manages authentication state and provides auth methods
 * Replaces the old AuthContext/AuthProvider pattern
 */
import { create } from 'zustand';
import * as api from '../services/api';
import { sanitizeInput } from '../utils/sanitizer';

// BroadcastChannel for cross-tab communication
let authChannel = null;

/**
 * Create the auth store
 */
export const useAuthStore = create((set, get) => ({
  // State
  user: null,
  isLoading: true,
  isAuthenticated: false,

  // Actions

  /**
   * Check authentication status
   */
  checkAuth: async () => {
    try {
      const response = await api.getMe();
      // Backend returns: { success: true, data: { user: {...} } }
      const userData = response.data?.user || null;

      // Check if account is active
      if (userData && userData.isActive === false) {
        // Account is deactivated, clear user state
        set({ user: null, isAuthenticated: false, isLoading: false });
      } else {
        set({ user: userData, isAuthenticated: !!userData, isLoading: false });
      }
    } catch (error) {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  /**
   * Login user
   * @param {string} identifier - Username or email
   * @param {string} password - User password
   */
  login: async (identifier, password) => {
    const response = await api.login(sanitizeInput(identifier), password);
    // Backend returns: { success: true, data: { user: {...} } }
    const userData = response.data?.user || null;

    // Check if account is active
    if (userData && userData.isActive === false) {
      throw new Error(
        'Your account has been deactivated. Please contact support to reactivate your account.'
      );
    }

    set({ user: userData, isAuthenticated: true });

    // Fetch complete user profile to ensure all fields are up-to-date
    await get().checkAuth();

    // Notify other tabs about login
    if (authChannel) {
      authChannel.postMessage({ type: 'login' });
    }
  },

  /**
   * Signup new user
   * @param {Object} userData - User registration data
   */
  signup: async (userData) => {
    const response = await api.register({
      ...userData,
      username: sanitizeInput(userData.username),
      email: sanitizeInput(userData.email),
      firstName: sanitizeInput(userData.firstName),
      lastName: sanitizeInput(userData.lastName),
      title: userData.title ? sanitizeInput(userData.title) : undefined,
    });
    // Backend returns: { success: true, data: { user: {...} } }
    const newUser = response.data?.user || null;
    set({ user: newUser, isAuthenticated: true });

    // Fetch complete user profile to ensure all fields are up-to-date
    await get().checkAuth();

    // Notify other tabs about signup
    if (authChannel) {
      authChannel.postMessage({ type: 'signup' });
    }
  },

  /**
   * Logout current session
   */
  logout: async () => {
    await api.logout();
    set({ user: null, isAuthenticated: false });

    // Disconnect socket on logout
    try {
      const { socketManager } = await import('../services/socket');
      socketManager.disconnect();
      console.log('[authStore] Socket disconnected on logout');
    } catch (error) {
      console.warn('[authStore] Failed to disconnect socket:', error);
    }

    // Reset chat store on logout
    try {
      const { useChatStore } = await import('./chatStore');
      useChatStore.getState().reset();
      console.log('[authStore] Chat store reset on logout');
    } catch (error) {
      console.warn('[authStore] Failed to reset chat store:', error);
    }

    // Notify other tabs about logout
    if (authChannel) {
      authChannel.postMessage({ type: 'logout' });
    }
  },

  /**
   * Logout from all devices
   */
  logoutAllDevices: async () => {
    await api.logoutAll();
    set({ user: null, isAuthenticated: false });

    // Disconnect socket on logout
    try {
      const { socketManager } = await import('../services/socket');
      socketManager.disconnect();
      console.log('[authStore] Socket disconnected on logout all devices');
    } catch (error) {
      console.warn('[authStore] Failed to disconnect socket:', error);
    }

    // Reset chat store on logout
    try {
      const { useChatStore } = await import('./chatStore');
      useChatStore.getState().reset();
      console.log('[authStore] Chat store reset on logout all devices');
    } catch (error) {
      console.warn('[authStore] Failed to reset chat store:', error);
    }

    // Notify other tabs about logout
    if (authChannel) {
      authChannel.postMessage({ type: 'logout' });
    }
  },

  /**
   * Refresh access token
   */
  refreshToken: async () => {
    try {
      await api.refresh();
    } catch (error) {
      set({ user: null, isAuthenticated: false });
    }
  },

  /**
   * Refresh user data (alias for checkAuth)
   */
  refreshUser: async () => {
    await get().checkAuth();
  },

  /**
   * Set loading state manually
   */
  setLoading: (isLoading) => {
    set({ isLoading });
  },
}));

// The private app owns this lifecycle. Importing a shared component must not
// issue authenticated requests or subscribe anonymous public visitors.
export function initializePrivateAuth() {
  if (typeof BroadcastChannel !== 'undefined') authChannel = new BroadcastChannel('auth_channel');
  if (authChannel) {
    authChannel.onmessage = (event) => {
      const { checkAuth } = useAuthStore.getState();

      if (event.data.type === 'login' || event.data.type === 'signup') {
        // Another tab logged in, refresh auth state
        checkAuth();
      } else if (event.data.type === 'logout') {
        // Another tab logged out, clear user state
        useAuthStore.setState({ user: null, isAuthenticated: false });
      }
    };
  }
  useAuthStore.getState().checkAuth();
  return () => { if (authChannel) { authChannel.onmessage = null; authChannel.close(); authChannel = null; } };
}
