/**
 * Mock Store Utilities
 * Helper functions for creating and managing mock Zustand stores
 */
import { create } from 'zustand';

/**
 * Create a mock auth store for testing
 * @param {Object} initialState - Initial state for the store
 * @returns {Function} - Mock store hook
 */
export function createMockAuthStore(initialState = {}) {
  const defaultState = {
    user: null,
    isAuthenticated: false,
    isLoading: false,
    checkAuth: jest.fn(),
    login: jest.fn(),
    signup: jest.fn(),
    logout: jest.fn(),
    logoutAllDevices: jest.fn(),
    refreshToken: jest.fn(),
    refreshUser: jest.fn(),
    setLoading: jest.fn(),
  };

  return create(() => ({
    ...defaultState,
    ...initialState,
  }));
}

/**
 * Create a mock UI store for testing
 * @param {Object} initialState - Initial state for the store
 * @returns {Function} - Mock store hook
 */
export function createMockUiStore(initialState = {}) {
  const defaultState = {
    sidebarOpen: false,
    toast: null,
    modal: null,
    isLoading: false,
    openSidebar: jest.fn(),
    closeSidebar: jest.fn(),
    toggleSidebar: jest.fn(),
    showToast: jest.fn(),
    hideToast: jest.fn(),
    showModal: jest.fn(),
    hideModal: jest.fn(),
    setLoading: jest.fn(),
  };

  return create(() => ({
    ...defaultState,
    ...initialState,
  }));
}

/**
 * Reset all store mocks
 */
export function resetStoreMocks(store) {
  const state = store.getState();
  Object.keys(state).forEach((key) => {
    if (typeof state[key] === 'function' && state[key].mockClear) {
      state[key].mockClear();
    }
  });
}

/**
 * Get mock implementation that simulates successful auth
 */
export const mockSuccessfulAuth = {
  checkAuth: jest.fn(async () => {
    return Promise.resolve();
  }),
  login: jest.fn(async () => {
    return Promise.resolve();
  }),
  signup: jest.fn(async () => {
    return Promise.resolve();
  }),
  logout: jest.fn(async () => {
    return Promise.resolve();
  }),
  logoutAllDevices: jest.fn(async () => {
    return Promise.resolve();
  }),
  refreshToken: jest.fn(async () => {
    return Promise.resolve();
  }),
};

/**
 * Get mock implementation that simulates failed auth
 */
export const mockFailedAuth = {
  checkAuth: jest.fn(async () => {
    throw new Error('Unauthorized');
  }),
  login: jest.fn(async () => {
    throw new Error('Invalid credentials');
  }),
  signup: jest.fn(async () => {
    throw new Error('Registration failed');
  }),
  logout: jest.fn(async () => {
    throw new Error('Logout failed');
  }),
  logoutAllDevices: jest.fn(async () => {
    throw new Error('Logout all devices failed');
  }),
  refreshToken: jest.fn(async () => {
    throw new Error('Token refresh failed');
  }),
};
