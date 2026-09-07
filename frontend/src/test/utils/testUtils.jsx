/**
 * Test Utilities
 * Custom render functions and test helpers for React Testing Library
 */
import React from 'react';
import { render } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import i18n from '../setup/i18nForTests';

/**
 * Custom render function that wraps components with common providers
 * @param {React.Component} ui - Component to render
 * @param {Object} options - Additional options
 * @returns {Object} - Render result from RTL
 */
export function renderWithProviders(ui, options = {}) {
  const { initialRoute = '/', i18nInstance = i18n, ...renderOptions } = options;

  // Set initial route if provided
  if (initialRoute !== '/') {
    window.history.pushState({}, 'Test page', initialRoute);
  }

  function Wrapper({ children }) {
    return (
      <BrowserRouter>
        <I18nextProvider i18n={i18nInstance}>{children}</I18nextProvider>
      </BrowserRouter>
    );
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
  };
}

/**
 * Wait for a condition to be true
 * @param {Function} callback - Function that returns true when condition is met
 * @param {Object} options - Options for timeout and interval
 * @returns {Promise} - Resolves when condition is true
 */
export const waitFor = async (callback, options = {}) => {
  const { timeout = 3000, interval = 50 } = options;
  const startTime = Date.now();

  const checkCondition = () => {
    try {
      const result = callback();
      if (result) return result;
    } catch (error) {
      // Continue waiting
    }

    if (Date.now() - startTime < timeout) {
      return new Promise((resolve) => {
        setTimeout(() => resolve(checkCondition()), interval);
      });
    }

    throw new Error('Timeout waiting for condition');
  };

  return checkCondition();
};

/**
 * Create a mock file for upload testing
 * @param {string} name - File name
 * @param {number} size - File size in bytes
 * @param {string} type - MIME type
 * @returns {File} - Mock file object
 */
export function createMockFile(
  name = 'test.png',
  size = 1024,
  type = 'image/png'
) {
  const file = new File(['test'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

/**
 * Mock localStorage for testing
 */
export const localStorageMock = (() => {
  let store = {};

  return {
    getItem: (key) => store[key] || null,
    setItem: (key, value) => {
      store[key] = value.toString();
    },
    removeItem: (key) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
    get length() {
      return Object.keys(store).length;
    },
    key: (index) => {
      const keys = Object.keys(store);
      return keys[index] || null;
    },
  };
})();

/**
 * Mock sessionStorage for testing
 */
export const sessionStorageMock = (() => {
  let store = {};

  return {
    getItem: (key) => store[key] || null,
    setItem: (key, value) => {
      store[key] = value.toString();
    },
    removeItem: (key) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
    get length() {
      return Object.keys(store).length;
    },
    key: (index) => {
      const keys = Object.keys(store);
      return keys[index] || null;
    },
  };
})();

/**
 * Setup mock storage before each test
 */
export function setupMockStorage() {
  global.localStorage = localStorageMock;
  global.sessionStorage = sessionStorageMock;
}

/**
 * Clear all mocks and storage
 */
export function cleanupTests() {
  localStorageMock.clear();
  sessionStorageMock.clear();
  jest.clearAllMocks();
}

/**
 * Mock BroadcastChannel for cross-tab communication testing
 */
export class MockBroadcastChannel {
  constructor(name) {
    this.name = name;
    this.onmessage = null;
    this.listeners = [];

    // Store instance for testing
    if (!global.broadcastChannels) {
      global.broadcastChannels = {};
    }
    global.broadcastChannels[name] = this;
  }

  postMessage(message) {
    if (this.onmessage) {
      this.onmessage({ data: message });
    }
    this.listeners.forEach((listener) => listener({ data: message }));
  }

  addEventListener(event, listener) {
    if (event === 'message') {
      this.listeners.push(listener);
    }
  }

  removeEventListener(event, listener) {
    if (event === 'message') {
      this.listeners = this.listeners.filter((l) => l !== listener);
    }
  }

  close() {
    this.listeners = [];
  }
}

/**
 * Setup mock BroadcastChannel
 */
export function setupMockBroadcastChannel() {
  global.BroadcastChannel = MockBroadcastChannel;
}

/**
 * Simulate broadcast message from another tab
 */
export function simulateBroadcast(channelName, message) {
  if (global.broadcastChannels && global.broadcastChannels[channelName]) {
    global.broadcastChannels[channelName].postMessage(message);
  }
}

/**
 * Re-export everything from RTL for convenience
 */
export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
