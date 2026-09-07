/**
 * Jest Environment Setup
 * This file runs before setupTests.js and defines global variables needed for tests
 */

// Mock import.meta for Jest (Vite provides this in the browser)
// We need to mock it at the Babel transform level since import.meta is syntax
// This is handled by babel-plugin-transform-import-meta which should transform
// import.meta.env.VARIABLE into process.env.VARIABLE

// As a backup, also define it on global (though import is a reserved word)
try {
  Object.defineProperty(global, 'import', {
    value: {
      meta: {
        env: {
          VITE_API_BASE_URL: process.env.VITE_API_BASE_URL || '/api',
          VITE_AUTH_TOKEN: process.env.VITE_AUTH_TOKEN || '',
          MODE: 'test',
          DEV: false,
          PROD: false,
          SSR: false,
        },
      },
    },
    writable: false,
    configurable: true,
  });
} catch (e) {
  // import is a reserved word, so this might fail
  // The babel plugin should handle the transformation anyway
}
