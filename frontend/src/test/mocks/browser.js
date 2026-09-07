/**
 * MSW Browser Setup
 * Configure Mock Service Worker for browser environment (development/debugging)
 * Note: MSW v1 uses 'msw' import, not 'msw/browser'
 */
import { setupWorker } from 'msw';
import { handlers } from './handlers';

// Setup mock service worker for browser
export const worker = setupWorker(...handlers);

export default worker;
