# Testing Guide - FirstWeek Frontend

> **Quick Start**: `npm test` to run all tests | `npm run test:coverage` for coverage report

---

## Table of Contents
1. [Testing Stack](#testing-stack)
2. [Setup Testing Environment](#setup-testing-environment)
3. [Writing Tests for New Pages](#writing-tests-for-new-pages)
4. [Writing Integration Tests](#writing-integration-tests)
5. [Running Tests](#running-tests)
6. [Troubleshooting](#troubleshooting)

---

## Testing Stack

### Core Libraries & Tools

| Library | Version | Purpose |
|---------|---------|---------|
| **Jest** | 29.7.0 | Test runner, assertion library, and mocking framework |
| **React Testing Library** | 16.0.1 | Component testing with user-centric queries |
| **@testing-library/user-event** | 14.5.2 | Realistic user interaction simulation |
| **@testing-library/jest-dom** | 6.5.0 | Custom DOM matchers (`toBeInTheDocument`, etc.) |
| **MSW (Mock Service Worker)** | 1.3.5 | API request mocking at network level |
| **Playwright** | 1.47.0 | End-to-end browser testing |

### Why These Tools?

**Jest**: Industry-standard test runner with built-in:
- Test execution and reporting
- Code coverage analysis
- Mocking utilities
- Snapshot testing

**React Testing Library**: Encourages testing components as users interact with them:
- Query by accessibility roles and labels
- Wait for async operations
- No implementation details testing

**MSW**: Intercepts network requests without touching application code:
- Realistic API mocking
- Works in both tests and browser
- No need to mock axios/fetch directly

---

## Setup Testing Environment

### 1. Installation (Already Done)

The testing environment is already configured in this project. If setting up from scratch:

```bash
npm install --save-dev jest @testing-library/react @testing-library/jest-dom \
  @testing-library/user-event babel-jest @babel/preset-env @babel/preset-react \
  jest-environment-jsdom identity-obj-proxy msw whatwg-fetch
```

### 2. Configuration Files

#### `jest.config.cjs`
```javascript
module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  moduleNameMapper: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    '\\.(jpg|jpeg|png|gif|svg)$': '<rootDir>/src/test/mocks/fileMock.js',
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  transform: {
    '^.+\\.(js|jsx)$': 'babel-jest',
  },
  transformIgnorePatterns: [
    'node_modules/(?!(msw|@bundled-es-modules)/)',
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
```

#### `babel.config.cjs`
```javascript
module.exports = {
  presets: [
    ['@babel/preset-env', { targets: { node: 'current' } }],
    ['@babel/preset-react', { runtime: 'automatic' }],
  ],
};
```

#### `src/setupTests.js`
```javascript
import '@testing-library/jest-dom';
import 'whatwg-fetch';
import { server } from './test/mocks/server';

// Start MSW server before tests
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock browser APIs
global.localStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};

global.BroadcastChannel = class {
  constructor() {}
  postMessage() {}
  close() {}
};
```

### 3. Test Infrastructure Files

```
src/test/
├── fixtures/
│   ├── users.js              # Mock user data
│   └── apiResponses.js       # Mock API responses
├── mocks/
│   ├── handlers.js           # MSW request handlers
│   └── server.js             # MSW server setup
├── setup/
│   └── i18nForTests.js       # i18n configuration
└── utils/
    ├── testUtils.jsx         # Custom render functions
    └── mockStore.js          # Store mocking utilities
```

---

## Writing Tests for New Pages

### Step-by-Step Guide

#### **Step 1: Create Test File**

Place test file next to the component:
```
src/pages/
├── NewPage.jsx
└── __tests__/
    └── NewPage.test.jsx
```

#### **Step 2: Basic Test Structure**

```javascript
/**
 * NewPage Component Tests
 */
import React from 'react';
import { screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NewPage } from '../NewPage';
import { renderWithProviders } from '../../test/utils/testUtils';
import { useAuthStore } from '../../store/authStore';

// Mock the auth store
jest.mock('../../store/authStore');

// Mock useNavigate if needed
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

describe('NewPage', () => {
  const mockAction = jest.fn();

  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();
    mockNavigate.mockReset();
    mockAction.mockReset();

    // Setup auth store mock
    useAuthStore.mockReturnValue({
      user: null,
      isAuthenticated: false,
      someAction: mockAction,
    });
  });

  afterEach(() => {
    cleanup();
  });

  // Your tests go here...
});
```

#### **Step 3: Test Categories**

**A. Rendering Tests**
```javascript
describe('Rendering', () => {
  it('should render the page with all elements', () => {
    renderWithProviders(<NewPage />);

    expect(screen.getByRole('heading', { name: /page title/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/enter text/i)).toBeInTheDocument();
  });

  it('should render loading state', () => {
    useAuthStore.mockReturnValue({
      isLoading: true,
      someAction: mockAction,
    });

    renderWithProviders(<NewPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
```

**B. Form Validation Tests**
```javascript
describe('Form Validation', () => {
  it('should show error when field is empty', async () => {
    const user = userEvent.setup();
    renderWithProviders(<NewPage />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/field is required/i)).toBeInTheDocument();
    });
  });

  it('should validate email format', async () => {
    const user = userEvent.setup();
    renderWithProviders(<NewPage />);

    const emailInput = screen.getByPlaceholderText(/email/i);
    await user.type(emailInput, 'invalid-email');

    const submitButton = screen.getByRole('button', { name: /submit/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
    });
  });
});
```

**C. User Interaction Tests**
```javascript
describe('User Interactions', () => {
  it('should call action when form is submitted', async () => {
    const user = userEvent.setup();
    mockAction.mockResolvedValueOnce({ success: true });

    renderWithProviders(<NewPage />);

    // Fill form
    await user.type(screen.getByPlaceholderText(/name/i), 'John Doe');
    await user.type(screen.getByPlaceholderText(/email/i), 'john@example.com');

    // Submit
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Verify action was called
    await waitFor(() => {
      expect(mockAction).toHaveBeenCalledWith({
        name: 'John Doe',
        email: 'john@example.com',
      });
    });
  });

  it('should show success message on successful submission', async () => {
    const user = userEvent.setup();
    mockAction.mockResolvedValueOnce({ success: true });

    renderWithProviders(<NewPage />);

    await user.type(screen.getByPlaceholderText(/name/i), 'John');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/success/i)).toBeInTheDocument();
    });
  });
});
```

**D. Error Handling Tests**
```javascript
describe('Error Handling', () => {
  it('should display error message on failure', async () => {
    const user = userEvent.setup();
    mockAction.mockRejectedValueOnce(new Error('Something went wrong'));

    renderWithProviders(<NewPage />);

    await user.type(screen.getByPlaceholderText(/name/i), 'John');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    });
  });
});
```

**E. Navigation Tests**
```javascript
describe('Navigation', () => {
  it('should navigate to next page on success', async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ delay: null });
    mockAction.mockResolvedValueOnce({ success: true });

    renderWithProviders(<NewPage />);

    await user.type(screen.getByPlaceholderText(/name/i), 'John');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // If there's a setTimeout, advance timers
    jest.advanceTimersByTime(1000);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/next-page');
    });

    jest.useRealTimers();
  });
});
```

#### **Step 4: Complete Example**

Here's a full test file for a signup page:

```javascript
/**
 * SignupPage Component Tests
 */
import React from 'react';
import { screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SignupPage } from '../SignupPage';
import { renderWithProviders } from '../../test/utils/testUtils';
import { useAuthStore } from '../../store/authStore';

jest.mock('../../store/authStore');

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
  Link: ({ children, to }) => <a href={to}>{children}</a>,
}));

describe('SignupPage', () => {
  const mockSignup = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockNavigate.mockReset();
    mockSignup.mockReset();

    useAuthStore.mockReturnValue({
      signup: mockSignup,
      isAuthenticated: false,
      isLoading: false,
    });
  });

  afterEach(() => {
    cleanup();
  });

  describe('Rendering', () => {
    it('should render signup form', () => {
      renderWithProviders(<SignupPage />);

      expect(screen.getByRole('heading', { name: /sign up/i })).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/email/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sign up/i })).toBeInTheDocument();
    });
  });

  describe('Form Validation', () => {
    it('should show error when username is empty', async () => {
      const user = userEvent.setup();
      renderWithProviders(<SignupPage />);

      await user.click(screen.getByRole('button', { name: /sign up/i }));

      await waitFor(() => {
        expect(screen.getByText(/username is required/i)).toBeInTheDocument();
      });
    });

    it('should validate email format', async () => {
      const user = userEvent.setup();
      renderWithProviders(<SignupPage />);

      await user.type(screen.getByPlaceholderText(/email/i), 'invalid');
      await user.click(screen.getByRole('button', { name: /sign up/i }));

      await waitFor(() => {
        expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
      });
    });
  });

  describe('Successful Signup', () => {
    it('should call signup with correct data', async () => {
      const user = userEvent.setup();
      mockSignup.mockResolvedValueOnce();

      renderWithProviders(<SignupPage />);

      await user.type(screen.getByPlaceholderText(/username/i), 'johndoe');
      await user.type(screen.getByPlaceholderText(/email/i), 'john@example.com');
      await user.type(screen.getByPlaceholderText(/password/i), 'Password123!');
      await user.click(screen.getByRole('button', { name: /sign up/i }));

      await waitFor(() => {
        expect(mockSignup).toHaveBeenCalledWith({
          username: 'johndoe',
          email: 'john@example.com',
          password: 'Password123!',
        });
      });
    });
  });
});
```

---

## Writing Integration Tests

Integration tests verify complete user flows across multiple components and API calls.

### Step-by-Step Guide

#### **Step 1: Create Test File**

```
src/__tests__/
└── integration/
    └── yourFlow.test.jsx
```

#### **Step 2: Setup MSW Handlers**

First, create API response fixtures:

```javascript
// src/test/fixtures/apiResponses.js
export const signupSuccessResponse = {
  success: true,
  message: 'User registered successfully',
  data: {
    user: {
      id: '1',
      username: 'testuser',
      email: 'test@example.com',
    },
  },
};

export const signupErrorResponse = {
  success: false,
  error: {
    message: 'Email already exists',
  },
};
```

Create MSW handlers:

```javascript
// src/test/mocks/handlers.js
import { rest } from 'msw';

const API_BASE_URL = 'http://localhost:3001/api/users';

export const handlers = [
  // Signup
  rest.post(`${API_BASE_URL}/register`, async (req, res, ctx) => {
    const body = await req.json();

    if (body.email === 'existing@example.com') {
      return res(
        ctx.status(400),
        ctx.json(signupErrorResponse)
      );
    }

    return res(ctx.status(200), ctx.json(signupSuccessResponse));
  }),

  // Login
  rest.post(`${API_BASE_URL}/login`, async (req, res, ctx) => {
    const body = await req.json();

    if (body.password === 'wrongpassword') {
      return res(
        ctx.status(401),
        ctx.json({ error: { message: 'Invalid credentials' } })
      );
    }

    return res(ctx.status(200), ctx.json(loginSuccessResponse));
  }),

  // Get user profile
  rest.get(`${API_BASE_URL}/me`, (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(getMeSuccessResponse));
  }),
];
```

Setup MSW server:

```javascript
// src/test/mocks/server.js
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

#### **Step 3: Write Integration Test**

```javascript
/**
 * Complete Signup Flow Integration Test
 */
import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test/utils/testUtils';
import { SignupPage } from '../../pages/SignupPage';
import { server } from '../../test/mocks/server';
import { rest } from 'msw';

describe('Complete Signup Flow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should complete full signup flow from form to verification', async () => {
    const user = userEvent.setup();

    // Render signup page
    renderWithProviders(<SignupPage />);

    // Fill signup form
    await user.type(screen.getByPlaceholderText(/username/i), 'newuser');
    await user.type(screen.getByPlaceholderText(/email/i), 'new@example.com');
    await user.type(screen.getByPlaceholderText(/first name/i), 'John');
    await user.type(screen.getByPlaceholderText(/last name/i), 'Doe');
    await user.type(screen.getByPlaceholderText(/^password/i), 'Password123!');
    await user.type(screen.getByPlaceholderText(/confirm password/i), 'Password123!');

    // Submit form
    await user.click(screen.getByRole('button', { name: /sign up/i }));

    // Wait for success message
    await waitFor(() => {
      expect(screen.getByText(/registration successful/i)).toBeInTheDocument();
    }, { timeout: 3000 });

    // Verify navigation to email verification page
    await waitFor(() => {
      expect(window.location.pathname).toBe('/verify-email');
    });
  });

  it('should handle signup errors gracefully', async () => {
    const user = userEvent.setup();

    // Override handler to return error
    server.use(
      rest.post('http://localhost:3001/api/users/register', (req, res, ctx) => {
        return res(
          ctx.status(400),
          ctx.json({
            success: false,
            error: { message: 'Email already exists' },
          })
        );
      })
    );

    renderWithProviders(<SignupPage />);

    await user.type(screen.getByPlaceholderText(/username/i), 'existinguser');
    await user.type(screen.getByPlaceholderText(/email/i), 'existing@example.com');
    await user.type(screen.getByPlaceholderText(/^password/i), 'Password123!');
    await user.click(screen.getByRole('button', { name: /sign up/i }));

    // Verify error message is displayed
    await waitFor(() => {
      expect(screen.getByText(/email already exists/i)).toBeInTheDocument();
    });

    // Verify user stays on signup page
    expect(window.location.pathname).toBe('/signup');
  });

  it('should validate all fields before submission', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SignupPage />);

    // Submit empty form
    await user.click(screen.getByRole('button', { name: /sign up/i }));

    // Check all error messages appear
    await waitFor(() => {
      expect(screen.getByText(/username is required/i)).toBeInTheDocument();
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });
  });
});
```

#### **Step 4: Advanced Integration Test Examples**

**Testing Protected Route Flow:**

```javascript
describe('Protected Route Access Flow', () => {
  it('should redirect unauthenticated user to login', async () => {
    renderWithProviders(<ProtectedPage />, { initialRoute: '/dashboard' });

    await waitFor(() => {
      expect(window.location.pathname).toBe('/login');
    });
  });

  it('should allow authenticated user to access protected page', async () => {
    // Mock authenticated state
    useAuthStore.mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      isLoading: false,
    });

    renderWithProviders(<ProtectedPage />, { initialRoute: '/dashboard' });

    expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
    expect(window.location.pathname).toBe('/dashboard');
  });
});
```

**Testing Complete Auth Flow:**

```javascript
describe('Complete Authentication Flow', () => {
  it('should handle login → access protected page → logout', async () => {
    const user = userEvent.setup();

    // Start at login page
    const { rerender } = renderWithProviders(<LoginPage />);

    // Perform login
    await user.type(screen.getByPlaceholderText(/email/i), 'test@example.com');
    await user.type(screen.getByPlaceholderText(/password/i), 'password123');
    await user.click(screen.getByRole('button', { name: /login/i }));

    // Wait for successful login
    await waitFor(() => {
      expect(screen.getByText(/login successful/i)).toBeInTheDocument();
    });

    // Mock authenticated state
    useAuthStore.mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      logout: mockLogout,
    });

    // Navigate to protected page
    rerender(renderWithProviders(<DashboardPage />));
    expect(screen.getByText(/welcome/i)).toBeInTheDocument();

    // Perform logout
    await user.click(screen.getByRole('button', { name: /logout/i }));

    // Verify logout was called
    expect(mockLogout).toHaveBeenCalled();

    // Verify redirect to login
    await waitFor(() => {
      expect(window.location.pathname).toBe('/login');
    });
  });
});
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
npm test

# Run tests in watch mode (re-runs on changes)
npm run test:watch

# Run with coverage report
npm run test:coverage

# Run specific test file
npm test -- LoginPage.test.jsx

# Run tests matching pattern
npm test -- --testNamePattern="should validate"

# Run tests for specific directory
npm test -- src/pages/__tests__/
```

### Watch Mode Options

When running `npm run test:watch`:
- Press `a` to run all tests
- Press `f` to run only failed tests
- Press `p` to filter by filename pattern
- Press `t` to filter by test name
- Press `q` to quit

### Coverage Reports

```bash
# Generate coverage report
npm run test:coverage

# View HTML coverage report
open coverage/lcov-report/index.html
```

Coverage thresholds (40% minimum):
- Statements: 40%
- Branches: 40%
- Functions: 40%
- Lines: 40%

---

## Troubleshooting

### Common Issues & Solutions

#### 1. **Tests Timing Out**

**Problem**: Tests fail with timeout errors

**Solution**:
```javascript
await waitFor(() => {
  expect(screen.getByText(/success/i)).toBeInTheDocument();
}, { timeout: 5000 }); // Increase timeout
```

#### 2. **"Cannot find module" Errors**

**Problem**: Jest can't resolve imports

**Solution**: Check `jest.config.cjs` moduleNameMapper:
```javascript
moduleNameMapper: {
  '^@/(.*)$': '<rootDir>/src/$1',
}
```

#### 3. **act() Warnings**

**Problem**: State updates not wrapped in act()

**Solution**: Use `waitFor` for async operations:
```javascript
await waitFor(() => {
  expect(mockFunction).toHaveBeenCalled();
});
```

#### 4. **Mock Not Resetting Between Tests**

**Problem**: Previous test's mock affects current test

**Solution**: Reset mocks in `beforeEach`:
```javascript
beforeEach(() => {
  jest.clearAllMocks();
  mockFunction.mockReset();
});
```

#### 5. **setTimeout Causing Test Interference**

**Problem**: Timers from one test affect another

**Solution**: Use fake timers:
```javascript
it('should handle delayed action', async () => {
  jest.useFakeTimers();
  const user = userEvent.setup({ delay: null });

  // ... your test code ...

  jest.advanceTimersByTime(1000);

  await waitFor(() => {
    expect(mockNavigate).toHaveBeenCalled();
  });

  jest.useRealTimers();
});
```

#### 6. **MSW Handlers Not Working**

**Problem**: API calls not being intercepted

**Solution**: Verify MSW server is setup in `setupTests.js`:
```javascript
import { server } from './test/mocks/server';

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

#### 7. **Snapshot Mismatch**

**Problem**: Snapshot tests failing after UI changes

**Solution**: Update snapshots if changes are intentional:
```bash
npm test -- -u
```

---

## Best Practices Checklist

### ✅ Do's
- ✅ Use `userEvent` for user interactions (not `fireEvent`)
- ✅ Query by accessibility roles and labels (`getByRole`, `getByLabelText`)
- ✅ Wait for async operations with `waitFor`
- ✅ Clean up mocks in `beforeEach` and `afterEach`
- ✅ Test user behavior, not implementation details
- ✅ Use descriptive test names that explain the scenario
- ✅ Group related tests with `describe` blocks

### ❌ Don'ts
- ❌ Don't use `getByTestId` unless necessary
- ❌ Don't test implementation details (state, props)
- ❌ Don't mock too much (test real behavior when possible)
- ❌ Don't forget to reset mocks between tests
- ❌ Don't use brittle selectors (class names, IDs)
- ❌ Don't ignore accessibility in tests

---

## Quick Reference

### Common Queries

```javascript
// Preferred (accessible)
screen.getByRole('button', { name: /submit/i })
screen.getByLabelText(/email/i)
screen.getByPlaceholderText(/enter email/i)

// By text content
screen.getByText(/welcome/i)

// Last resort
screen.getByTestId('submit-button')
```

### User Interactions

```javascript
const user = userEvent.setup();

await user.type(input, 'hello');
await user.click(button);
await user.clear(input);
await user.selectOptions(select, 'option1');
await user.upload(fileInput, file);
```

### Assertions

```javascript
expect(element).toBeInTheDocument();
expect(element).toHaveTextContent('text');
expect(element).toBeVisible();
expect(element).toBeDisabled();
expect(element).toHaveAttribute('href', '/path');
expect(mockFn).toHaveBeenCalledWith(expectedArgs);
```

---

## Resources

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [Testing Library Queries](https://testing-library.com/docs/queries/about)
- [MSW Documentation](https://mswjs.io/docs/)
- [Common Mistakes with RTL](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

---

**Last Updated**: October 2025
**Maintained By**: FirstWeek Development Team
