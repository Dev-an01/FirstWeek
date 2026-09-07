/**
 * Visual Regression Tests (Snapshots)
 * Snapshot tests for key UI components to catch visual regressions
 */
import React from 'react';
import { renderWithProviders } from '../../test/utils/testUtils';
import { LoginPage } from '../../pages/LoginPage';
import { ProtectedRoute } from '../../components/Auth/ProtectedRoute';
import { useAuthStore } from '../../store/authStore';

// Mock the auth store
jest.mock('../../store/authStore');

// Mock useNavigate
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => jest.fn(),
  Link: ({ children, to }) => <a href={to}>{children}</a>,
  Navigate: ({ to }) => <div>Redirecting to {to}</div>,
}));

describe('Component Snapshots', () => {
  describe('LoginPage Snapshots', () => {
    beforeEach(() => {
      useAuthStore.mockReturnValue({
        login: jest.fn(),
        isAuthenticated: false,
        isLoading: false,
      });
    });

    it('should match snapshot for initial render', () => {
      const { container } = renderWithProviders(<LoginPage />);
      expect(container).toMatchSnapshot();
    });

    it('should match snapshot with validation errors', () => {
      const { container } = renderWithProviders(<LoginPage />);

      // Trigger validation by clicking submit
      const form = container.querySelector('form');
      if (form) {
        const event = new Event('submit', { bubbles: true, cancelable: true });
        form.dispatchEvent(event);
      }

      expect(container).toMatchSnapshot();
    });
  });

  describe('ProtectedRoute Snapshots', () => {
    const TestComponent = () => <div>Protected Content</div>;

    it('should match snapshot when loading', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: false,
        isLoading: true,
      });

      const { container } = renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      expect(container).toMatchSnapshot();
    });

    it('should match snapshot when authenticated', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
      });

      const { container } = renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      expect(container).toMatchSnapshot();
    });

    it('should match snapshot when redirecting', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
      });

      const { container } = renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      expect(container).toMatchSnapshot();
    });
  });

  describe('Responsive Layout Snapshots', () => {
    beforeEach(() => {
      useAuthStore.mockReturnValue({
        login: jest.fn(),
        isAuthenticated: false,
        isLoading: false,
      });
    });

    it('should match snapshot for mobile viewport', () => {
      // Simulate mobile viewport
      global.innerWidth = 375;
      global.innerHeight = 667;

      const { container } = renderWithProviders(<LoginPage />);
      expect(container).toMatchSnapshot();
    });

    it('should match snapshot for tablet viewport', () => {
      // Simulate tablet viewport
      global.innerWidth = 768;
      global.innerHeight = 1024;

      const { container } = renderWithProviders(<LoginPage />);
      expect(container).toMatchSnapshot();
    });

    it('should match snapshot for desktop viewport', () => {
      // Simulate desktop viewport
      global.innerWidth = 1920;
      global.innerHeight = 1080;

      const { container } = renderWithProviders(<LoginPage />);
      expect(container).toMatchSnapshot();
    });
  });
});
