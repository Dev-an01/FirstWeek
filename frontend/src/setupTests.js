// jest-dom adds custom jest matchers for asserting on DOM nodes.
import '@testing-library/jest-dom';
import 'whatwg-fetch';
import { setupMockServer } from './test/mocks/server';
import {
  setupMockStorage,
  setupMockBroadcastChannel,
} from './test/utils/testUtils';

// Setup MSW server for all tests
setupMockServer();

// Setup mock storage
setupMockStorage();

// Setup mock BroadcastChannel
setupMockBroadcastChannel();

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  // eslint-disable-next-line no-useless-constructor, no-empty-function
  constructor() {}

  disconnect() {}

  observe() {}

  takeRecords() {
    return [];
  }

  unobserve() {}
};

// Suppress console errors in tests (optional - comment out if you want to see them)
global.console = {
  ...console,
  error: jest.fn(),
  warn: jest.fn(),
};
