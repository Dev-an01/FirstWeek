/**
 * MSW Server Setup
 * Configure Mock Service Worker for Node environment (Jest tests)
 */
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// Setup mock server with default handlers
export const server = setupServer(...handlers);

// Start server before all tests
export function setupMockServer() {
  beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));

  // Reset handlers after each test
  afterEach(() => server.resetHandlers());

  // Clean up after all tests
  afterAll(() => server.close());
}

export default server;
