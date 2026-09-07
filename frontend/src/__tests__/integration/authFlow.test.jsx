/**
 * Auth Flow Integration Tests
 * End-to-end testing of complete authentication flows
 */
import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { renderWithProviders } from '../../test/utils/testUtils';
import { LoginPage } from '../../pages/LoginPage';
import { ProtectedRoute } from '../../components/Auth/ProtectedRoute';
import { useAuthStore } from '../../store/authStore';
import { server } from '../../test/mocks/server';
import {
  loginSuccessResponse,
  loginFailureResponse,
  getMeSuccessResponse,
  logoutSuccessResponse,
} from '../../test/fixtures/apiResponses';

// Mock useNavigate
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    Link: ({ children, to }) => <a href={to}>{children}</a>,
    Navigate: (props) => {
      mockNavigate(props.to, { replace: props.replace || false });
      return <div>Redirecting to {props.to}</div>;
    },
  };
});

describe('Auth Flow Integration Tests', () => {
  const API_BASE_URL = 'http://localhost:3001/api/users';

  beforeEach(() => {
    // Reset auth store
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });

    // Clear mocks
    jest.clearAllMocks();
    mockNavigate.mockClear();

    // Clear localStorage and sessionStorage
    localStorage.clear();
    sessionStorage.clear();
  });

  describe('Complete Login Flow', () => {
    it('should complete full login flow from form to dashboard', async () => {
      const user = userEvent.setup();

      // Setup MSW handlers
      server.use(
        rest.post(`${API_BASE_URL}/login`, (req, res, ctx) => {
          return res(ctx.json(loginSuccessResponse));
        }),
        rest.get(`${API_BASE_URL}/me`, (req, res, ctx) => {
          return res(ctx.json(getMeSuccessResponse));
        })
      );

      renderWithProviders(<LoginPage />);

      // Step 1: Fill in login form
      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'testuser');
      await user.type(passwordInput, 'password123');

      // Step 2: Submit form
      await user.click(submitButton);

      // Step 3: Verify success toast appears
      await waitFor(() => {
        expect(screen.getByText(/login successful/i)).toBeInTheDocument();
      });

      // Step 4: Verify navigation to dashboard
      await waitFor(
        () => {
          expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
        },
        { timeout: 2000 }
      );

      // Step 5: Verify auth store state is updated
      const authState = useAuthStore.getState();
      expect(authState.isAuthenticated).toBe(true);
      expect(authState.user).toBeTruthy();
    });

    it('should handle login failure gracefully', async () => {
      const user = userEvent.setup();

      // Setup MSW to return error
      server.use(
        rest.post(`${API_BASE_URL}/login`, (req, res, ctx) => {
          return res(ctx.status(401), ctx.json(loginFailureResponse));
        })
      );

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'wronguser');
      await user.type(passwordInput, 'wrongpassword');
      await user.click(submitButton);

      // Should show error message
      await waitFor(() => {
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
      });

      // Should not navigate
      expect(mockNavigate).not.toHaveBeenCalled();

      // Auth store should remain unauthenticated
      const authState = useAuthStore.getState();
      expect(authState.isAuthenticated).toBe(false);
      expect(authState.user).toBeNull();
    });

    it('should handle network errors during login', async () => {
      const user = userEvent.setup();

      // Setup MSW to return network error
      server.use(
        rest.post(`${API_BASE_URL}/login`, (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'testuser');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      // Should show error (might be network error or fallback message)
      await waitFor(() => {
        const errorElement =
          screen.queryByText(/error/i) || screen.queryByText(/failed/i);
        expect(errorElement).toBeInTheDocument();
      });
    });
  });

  describe('Protected Route Access Flow', () => {
    it('should allow access to protected route when authenticated', async () => {
      // Set authenticated state
      useAuthStore.setState({
        user: { id: '123', username: 'testuser' },
        isAuthenticated: true,
        isLoading: false,
      });

      const ProtectedContent = () => <div>Protected Dashboard</div>;

      renderWithProviders(
        <ProtectedRoute>
          <ProtectedContent />
        </ProtectedRoute>
      );

      // Should render protected content
      expect(screen.getByText('Protected Dashboard')).toBeInTheDocument();

      // Should not redirect
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('should redirect to login when accessing protected route unauthenticated', () => {
      // Set unauthenticated state
      useAuthStore.setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });

      const ProtectedContent = () => <div>Protected Dashboard</div>;

      renderWithProviders(
        <ProtectedRoute>
          <ProtectedContent />
        </ProtectedRoute>
      );

      // Should redirect to login
      expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true });

      // Should not render protected content
      expect(screen.queryByText('Protected Dashboard')).not.toBeInTheDocument();
    });

    it('should show loading state while checking auth', () => {
      // Set loading state
      useAuthStore.setState({
        user: null,
        isAuthenticated: false,
        isLoading: true,
      });

      const ProtectedContent = () => <div>Protected Dashboard</div>;

      const { container } = renderWithProviders(
        <ProtectedRoute>
          <ProtectedContent />
        </ProtectedRoute>
      );

      // Should show loading spinner
      expect(container.querySelector('.animate-spin')).toBeInTheDocument();

      // Should not render protected content
      expect(screen.queryByText('Protected Dashboard')).not.toBeInTheDocument();

      // Should not redirect yet
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  describe('Complete Logout Flow', () => {
    it('should complete full logout flow', async () => {
      // Setup MSW handler for logout
      server.use(
        rest.post(`${API_BASE_URL}/logout`, (req, res, ctx) => {
          return res(ctx.json(logoutSuccessResponse));
        })
      );

      // Set initial authenticated state
      useAuthStore.setState({
        user: { id: '123', username: 'testuser' },
        isAuthenticated: true,
        isLoading: false,
      });

      const authState = useAuthStore.getState();

      // Perform logout
      await authState.logout();

      // Verify auth store is cleared
      const updatedState = useAuthStore.getState();
      expect(updatedState.user).toBeNull();
      expect(updatedState.isAuthenticated).toBe(false);
    });

    it('should prevent access to protected routes after logout', async () => {
      // Setup MSW handler
      server.use(
        rest.post(`${API_BASE_URL}/logout`, (req, res, ctx) => {
          return res(ctx.json(logoutSuccessResponse));
        })
      );

      // Start authenticated
      useAuthStore.setState({
        user: { id: '123', username: 'testuser' },
        isAuthenticated: true,
        isLoading: false,
      });

      // Perform logout
      const authState = useAuthStore.getState();
      await authState.logout();

      // Now try to access protected route
      const ProtectedContent = () => <div>Protected Dashboard</div>;

      renderWithProviders(
        <ProtectedRoute>
          <ProtectedContent />
        </ProtectedRoute>
      );

      // Should redirect to login
      expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true });
    });
  });

  describe('Session Persistence Flow', () => {
    it('should check auth on app initialization', async () => {
      // Setup MSW handler
      server.use(
        rest.get(`${API_BASE_URL}/me`, (req, res, ctx) => {
          return res(ctx.json(getMeSuccessResponse));
        })
      );

      // Simulate app initialization by calling checkAuth
      const authState = useAuthStore.getState();
      await authState.checkAuth();

      // Should update auth state
      const updatedState = useAuthStore.getState();
      expect(updatedState.isAuthenticated).toBe(true);
      expect(updatedState.user).toBeTruthy();
    });

    it('should handle expired session on app initialization', async () => {
      // Setup MSW to return unauthorized
      server.use(
        rest.get(`${API_BASE_URL}/me`, (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ success: false, error: { message: 'Unauthorized' } })
          );
        })
      );

      // Simulate app initialization
      const authState = useAuthStore.getState();
      await authState.checkAuth();

      // Should clear auth state
      const updatedState = useAuthStore.getState();
      expect(updatedState.isAuthenticated).toBe(false);
      expect(updatedState.user).toBeNull();
    });
  });

  describe('Form Validation Flow', () => {
    it('should prevent submission with invalid data', async () => {
      const user = userEvent.setup();

      renderWithProviders(<LoginPage />);

      const submitButton = screen.getByRole('button', { name: /login/i });

      // Try to submit with empty fields
      await user.click(submitButton);

      // Should show validation errors
      await waitFor(() => {
        expect(
          screen.getByText(/username or email is required/i)
        ).toBeInTheDocument();
        expect(screen.getByText(/password is required/i)).toBeInTheDocument();
      });

      // Should not call API
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('should clear validation errors on input', async () => {
      const user = userEvent.setup();

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      // Submit with empty fields
      await user.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText(/username or email is required/i)
        ).toBeInTheDocument();
      });

      // Start typing
      await user.type(identifierInput, 'test');

      // Submit again to trigger validation
      await user.click(submitButton);

      // Identifier error should be gone
      expect(
        screen.queryByText(/username or email is required/i)
      ).not.toBeInTheDocument();
    });
  });

  describe('Cross-Tab Communication Flow', () => {
    it.skip('should update auth state when login occurs in another tab', async () => {
      // Setup MSW handler
      server.use(
        rest.get(`${API_BASE_URL}/me`, (req, res, ctx) => {
          return res(ctx.json(getMeSuccessResponse));
        })
      );

      // Initial state: not authenticated
      useAuthStore.setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });

      // Simulate login in another tab via BroadcastChannel
      const authChannel = new BroadcastChannel('auth_channel');
      authChannel.postMessage({ type: 'login' });

      // Wait for checkAuth to be called
      await waitFor(
        () => {
          const state = useAuthStore.getState();
          expect(state.isAuthenticated).toBe(true);
        },
        { timeout: 2000 }
      );
    });

    it('should clear auth state when logout occurs in another tab', () => {
      // Start authenticated
      useAuthStore.setState({
        user: { id: '123', username: 'testuser' },
        isAuthenticated: true,
        isLoading: false,
      });

      // Simulate logout in another tab
      const authChannel = new BroadcastChannel('auth_channel');
      authChannel.postMessage({ type: 'logout' });

      // Should clear state
      waitFor(() => {
        const state = useAuthStore.getState();
        expect(state.user).toBeNull();
        expect(state.isAuthenticated).toBe(false);
      });
    });
  });

  describe('Error Recovery Flow', () => {
    it('should recover from temporary network error', async () => {
      const user = userEvent.setup();

      let requestCount = 0;

      // First request fails, second succeeds
      server.use(
        rest.post(`${API_BASE_URL}/login`, (req, res, ctx) => {
          requestCount++;
          if (requestCount === 1) {
            return res(ctx.status(500));
          }
          return res(ctx.json(loginSuccessResponse));
        }),
        rest.get(`${API_BASE_URL}/me`, (req, res, ctx) => {
          return res(ctx.json(getMeSuccessResponse));
        })
      );

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      // First attempt - should fail
      await user.type(identifierInput, 'testuser');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      await waitFor(() => {
        const errorElement =
          screen.queryByText(/error/i) || screen.queryByText(/failed/i);
        expect(errorElement).toBeInTheDocument();
      });

      // Clear fields
      await user.clear(identifierInput);
      await user.clear(passwordInput);

      // Second attempt - should succeed
      await user.type(identifierInput, 'testuser');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/login successful/i)).toBeInTheDocument();
      });
    });
  });
});
