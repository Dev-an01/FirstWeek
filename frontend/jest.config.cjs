module.exports = {
  testEnvironment: 'jsdom',
  setupFiles: ['<rootDir>/src/test/setup/jestEnv.js'], // Setup import.meta before tests
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  testMatch: ['**/__tests__/**/*.test.[jt]s?(x)'],
  testEnvironmentOptions: {
    customExportConditions: ['node', 'node-addons'],
  },
  transform: {
    '^.+\\.(js|jsx)$': ['babel-jest', { configFile: './babel.config.cjs' }],
  },
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
  transformIgnorePatterns: [
    'node_modules/(?!(' +
    'msw|' +
    '@bundled-es-modules|' +
    '@mswjs|' +
    'headers-polyfill|' +
    'outvariant|' +
    'strict-event-emitter|' +
    'statuses' +
    ')/)',
  ],
  moduleFileExtensions: ['js', 'jsx', 'json', 'node', 'mjs'],
  collectCoverageFrom: [
    'src/**/*.{js,jsx}',
    '!src/**/*.test.{js,jsx}',
    '!src/test/**',
    '!src/**/__tests__/**',
    '!src/main.jsx',
    '!src/i18n/**',
  ],
  coverageThreshold: {
    global: {
      branches: 40,
      functions: 40,
      lines: 40,
      statements: 40,
    },
  },
};
