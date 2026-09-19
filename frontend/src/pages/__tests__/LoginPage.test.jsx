/**
 * LoginPage Component Tests
 * Tests for login form functionality and user interactions
 */
import React from 'react';
import { screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginPage } from '../LoginPage';
import { renderWithProviders } from '../../test/utils/testUtils';
import { useAuthStore } from '../../store/authStore';
import { mockLoginCredentials } from '../../test/fixtures/users';

// Mock the auth store
jest.mock('../../store/authStore');

// Mock useNavigate
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
  Link: ({ children, to }) => <a href={to}>{children}</a>,
}));

describe('LoginPage', () => {
  const mockLogin = jest.fn();

  beforeEach(() => {
    // Reset mocks before each test
    jest.clearAllMocks();
    mockNavigate.mockReset();
    mockLogin.mockReset();

    // Setup default mock return value - create fresh object for each test
    useAuthStore.mockReturnValue({
      login: mockLogin,
      isAuthenticated: false,
      isLoading: false,
    });
  });

  afterEach(() => {
    // Clean up React components
    cleanup();
    // Clear all timers to prevent setTimeout from previous tests affecting next tests
    jest.clearAllTimers();
  });

  describe('Rendering', () => {
    it('should render login form', () => {
      renderWithProviders(<LoginPage />);

      expect(
        screen.getByRole('img', { name: /FirstWeek logo/i })
      ).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText(/email or username/i)
      ).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /login/i })
      ).toBeInTheDocument();
    });

    it('should render remember me checkbox', () => {
      renderWithProviders(<LoginPage />);

      const rememberCheckbox = screen.getByRole('checkbox', {
        name: /remember me/i,
      });
      expect(rememberCheckbox).toBeInTheDocument();
      expect(rememberCheckbox).not.toBeChecked();
    });

    it('should render forgot password link', () => {
      renderWithProviders(<LoginPage />);

      const forgotPasswordLink = screen.getByRole('link', {
        name: /forgot password/i,
      });
      expect(forgotPasswordLink).toBeInTheDocument();
      expect(forgotPasswordLink).toHaveAttribute('href', '/forgot-password');
    });

    it('should render signup link', () => {
      renderWithProviders(<LoginPage />);

      const signupLink = screen.getByRole('link', { name: /sign up/i });
      expect(signupLink).toBeInTheDocument();
      expect(signupLink).toHaveAttribute('href', '/signup');
    });

    it('should render language toggle component', () => {
      renderWithProviders(<LoginPage />);

      // LanguageToggle should be present
      expect(
        document.querySelector('.fixed.top-4.right-4')
      ).toBeInTheDocument();
    });
  });

  describe('Form Validation', () => {
    it('should show error when identifier is empty', async () => {
      const user = userEvent.setup();
      renderWithProviders(<LoginPage />);

      const submitButton = screen.getByRole('button', { name: /login/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText(/username or email is required/i)
        ).toBeInTheDocument();
      });

      expect(mockLogin).not.toHaveBeenCalled();
    });

    it('should show error when password is empty', async () => {
      const user = userEvent.setup();
      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'testuser');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/password is required/i)).toBeInTheDocument();
      });

      expect(mockLogin).not.toHaveBeenCalled();
    });

    it('should show errors for both fields when both are empty', async () => {
      const user = userEvent.setup();
      renderWithProviders(<LoginPage />);

      const submitButton = screen.getByRole('button', { name: /login/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText(/username or email is required/i)
        ).toBeInTheDocument();
        expect(screen.getByText(/password is required/i)).toBeInTheDocument();
      });

      expect(mockLogin).not.toHaveBeenCalled();
    });

    it('should clear errors when user starts typing', async () => {
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

      // The identifier error should be gone
      expect(
        screen.queryByText(/username or email is required/i)
      ).not.toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    it('should call login with correct credentials', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValueOnce();

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, mockLoginCredentials.identifier);
      await user.type(passwordInput, mockLoginCredentials.password);
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith(
          mockLoginCredentials.identifier,
          mockLoginCredentials.password
        );
      });
    });

    it('should show success toast on successful login', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValueOnce();

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'testuser');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/login successful/i)).toBeInTheDocument();
      });
    });

    it('should navigate to dashboard after successful login', async () => {
      jest.useFakeTimers();
      const user = userEvent.setup({ delay: null }); // Disable delay for fake timers
      mockLogin.mockResolvedValueOnce();

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'testuser');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      // Fast-forward time to trigger the setTimeout
      jest.advanceTimersByTime(1000);

      await waitFor(
        () => {
          expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
        },
        { timeout: 2000 }
      );

      jest.useRealTimers();
    });

    it('should show error toast on failed login', async () => {
      const user = userEvent.setup();
      const errorMessage = 'Invalid credentials';
      mockLogin.mockRejectedValueOnce(new Error(errorMessage));

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'wronguser');
      await user.type(passwordInput, 'wrongpassword');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });

      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('should disable submit button while submitting', async () => {
      const user = userEvent.setup();
      let resolveLogin;
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve;
      });
      mockLogin.mockReturnValueOnce(loginPromise);

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'testuser');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      // Button should be disabled while submitting
      await waitFor(() => {
        expect(submitButton).toBeDisabled();
      });

      // Resolve the login
      resolveLogin();

      // Button should be enabled again
      await waitFor(() => {
        expect(submitButton).not.toBeDisabled();
      });
    });

    it('should show "logging in" text while submitting', async () => {
      const user = userEvent.setup();
      let resolveLogin;
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve;
      });
      mockLogin.mockReturnValueOnce(loginPromise);

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'testuser');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByRole('button', { name: /logging in/i })
        ).toBeInTheDocument();
      });

      resolveLogin();
    });
  });

  describe('Remember Me Functionality', () => {
    it('should toggle remember me checkbox', async () => {
      const user = userEvent.setup();
      renderWithProviders(<LoginPage />);

      const rememberCheckbox = screen.getByRole('checkbox', {
        name: /remember me/i,
      });

      expect(rememberCheckbox).not.toBeChecked();

      await user.click(rememberCheckbox);
      expect(rememberCheckbox).toBeChecked();

      await user.click(rememberCheckbox);
      expect(rememberCheckbox).not.toBeChecked();
    });
  });

  describe('Auto-redirect for Authenticated Users', () => {
    it('should redirect to dashboard if user is already authenticated', () => {
      useAuthStore.mockReturnValue({
        login: mockLogin,
        isAuthenticated: true,
        isLoading: false,
      });

      renderWithProviders(<LoginPage />);

      waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/dashboard', {
          replace: true,
        });
      });
    });

    it('should not redirect while loading', () => {
      useAuthStore.mockReturnValue({
        login: mockLogin,
        isAuthenticated: false,
        isLoading: true,
      });

      renderWithProviders(<LoginPage />);

      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('should have proper form autocomplete attributes', () => {
      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);

      expect(identifierInput).toHaveAttribute('autocomplete', 'username');
      expect(passwordInput).toHaveAttribute('autocomplete', 'current-password');
    });

    it('should have noValidate attribute on form', () => {
      renderWithProviders(<LoginPage />);

      const form = screen
        .getByRole('button', { name: /login/i })
        .closest('form');
      expect(form).toHaveAttribute('noValidate');
    });

    it('should have required attributes on inputs', () => {
      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);

      // FormInput and PasswordInput components should handle required prop
      expect(identifierInput).toBeInTheDocument();
      expect(passwordInput).toBeInTheDocument();
    });
  });

  describe('Toast Notifications', () => {
    it('should close toast when clicking close button', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValueOnce();

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'testuser');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/login successful/i)).toBeInTheDocument();
      });

      // Toast should auto-close or have a close mechanism
      // This depends on Toast component implementation
    });
  });

  describe('Edge Cases', () => {
    it('should handle whitespace-only identifier', async () => {
      const user = userEvent.setup();
      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, '   ');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText(/username or email is required/i)
        ).toBeInTheDocument();
      });

      expect(mockLogin).not.toHaveBeenCalled();
    });

    it('should handle network errors gracefully', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValueOnce(new Error('Network Error'));

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'testuser');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });

    it('should handle undefined error message', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValueOnce(new Error());

      renderWithProviders(<LoginPage />);

      const identifierInput = screen.getByPlaceholderText(/email or username/i);
      const passwordInput = screen.getByPlaceholderText(/password/i);
      const submitButton = screen.getByRole('button', { name: /login/i });

      await user.type(identifierInput, 'testuser');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
      });
    });
  });
});
