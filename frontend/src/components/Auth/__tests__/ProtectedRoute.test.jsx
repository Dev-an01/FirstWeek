/**
 * ProtectedRoute Component Tests
 * Tests for route protection and authentication checks
 */
import React from 'react';
import { screen } from '@testing-library/react';
import { ProtectedRoute } from '../ProtectedRoute';
import { renderWithProviders } from '../../../test/utils/testUtils';
import { useAuthStore } from '../../../store/authStore';

// Mock the auth store
jest.mock('../../../store/authStore');

// Mock Navigate component
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    Navigate: (props) => {
      mockNavigate(props.to, { replace: props.replace || false });
      return <div data-testid="navigate-mock">Redirecting to {props.to}</div>;
    },
  };
});

describe('ProtectedRoute', () => {
  const TestComponent = () => (
    <div data-testid="protected-content">Protected Content</div>
  );

  beforeEach(() => {
    jest.clearAllMocks();
    mockNavigate.mockClear();
  });

  describe('Rendering States', () => {
    it('should show loading spinner while checking auth', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: false,
        isLoading: true,
      });

      const { container } = renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      // Should show loading spinner
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
      expect(spinner).toHaveClass('animate-spin');

      // Should not show protected content
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();

      // Should not redirect
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('should render children when authenticated', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
      });

      renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      // Should show protected content
      expect(screen.getByTestId('protected-content')).toBeInTheDocument();
      expect(screen.getByText('Protected Content')).toBeInTheDocument();

      // Should not redirect
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('should redirect to login when not authenticated', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
      });

      renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      // Should redirect to login
      expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true });

      // Should show redirect message (from mocked Navigate)
      expect(screen.getByTestId('navigate-mock')).toBeInTheDocument();
      expect(screen.getByText('Redirecting to /login')).toBeInTheDocument();

      // Should not show protected content
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('should have correct loading spinner styles', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: false,
        isLoading: true,
      });

      const { container } = renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      const spinner = container.querySelector('.animate-spin');

      // Check for all loading spinner classes
      expect(spinner).toHaveClass('animate-spin');
      expect(spinner).toHaveClass('rounded-full');
      expect(spinner).toHaveClass('h-12');
      expect(spinner).toHaveClass('w-12');
      expect(spinner).toHaveClass('border-4');
      expect(spinner).toHaveClass('border-primary');
      expect(spinner).toHaveClass('border-t-transparent');
    });

    it('should center loading spinner on screen', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: false,
        isLoading: true,
      });

      const { container } = renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      const loadingContainer = container.querySelector('.min-h-screen');

      expect(loadingContainer).toHaveClass('flex');
      expect(loadingContainer).toHaveClass('items-center');
      expect(loadingContainer).toHaveClass('justify-center');
      expect(loadingContainer).toHaveClass('bg-gray-50');
    });
  });

  describe('Authentication State Changes', () => {
    it('should update when auth state changes from loading to authenticated', () => {
      const { rerender, container } = renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      // Initially loading
      useAuthStore.mockReturnValue({
        isAuthenticated: false,
        isLoading: true,
      });

      rerender(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      expect(container.querySelector('.animate-spin')).toBeInTheDocument();

      // Then authenticated
      useAuthStore.mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
      });

      rerender(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      expect(screen.getByTestId('protected-content')).toBeInTheDocument();
      expect(container.querySelector('.animate-spin')).not.toBeInTheDocument();
    });

    it('should update when auth state changes from loading to unauthenticated', () => {
      const { rerender, container } = renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      // Initially loading
      useAuthStore.mockReturnValue({
        isAuthenticated: false,
        isLoading: true,
      });

      rerender(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      expect(container.querySelector('.animate-spin')).toBeInTheDocument();

      // Then unauthenticated
      useAuthStore.mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
      });

      rerender(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true });
    });

    it('should handle logout (authenticated to unauthenticated)', () => {
      const { rerender } = renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      // Initially authenticated
      useAuthStore.mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
      });

      rerender(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      expect(screen.getByTestId('protected-content')).toBeInTheDocument();

      // User logs out
      useAuthStore.mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
      });

      rerender(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true });
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    });
  });

  describe('Children Rendering', () => {
    it('should render multiple children when authenticated', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
      });

      renderWithProviders(
        <ProtectedRoute>
          <div data-testid="child-1">Child 1</div>
          <div data-testid="child-2">Child 2</div>
          <div data-testid="child-3">Child 3</div>
        </ProtectedRoute>
      );

      expect(screen.getByTestId('child-1')).toBeInTheDocument();
      expect(screen.getByTestId('child-2')).toBeInTheDocument();
      expect(screen.getByTestId('child-3')).toBeInTheDocument();
    });

    it('should render complex component tree when authenticated', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
      });

      const ComplexComponent = () => (
        <div>
          <header>Header</header>
          <main>
            <section>Content</section>
          </main>
          <footer>Footer</footer>
        </div>
      );

      renderWithProviders(
        <ProtectedRoute>
          <ComplexComponent />
        </ProtectedRoute>
      );

      expect(screen.getByText('Header')).toBeInTheDocument();
      expect(screen.getByText('Content')).toBeInTheDocument();
      expect(screen.getByText('Footer')).toBeInTheDocument();
    });

    it('should pass through props to children', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
      });

      const ChildWithProps = ({ title, count }) => (
        <div>
          <h1>{title}</h1>
          <p>Count: {count}</p>
        </div>
      );

      renderWithProviders(
        <ProtectedRoute>
          <ChildWithProps title="Test Title" count={42} />
        </ProtectedRoute>
      );

      expect(screen.getByText('Test Title')).toBeInTheDocument();
      expect(screen.getByText('Count: 42')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle undefined isAuthenticated', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: undefined,
        isLoading: false,
      });

      renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      // Should treat undefined as falsy and redirect
      expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true });
    });

    it('should handle null isAuthenticated', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: null,
        isLoading: false,
      });

      renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      // Should treat null as falsy and redirect
      expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true });
    });

    it('should prioritize loading state over authentication state', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: true, // Even though authenticated
        isLoading: true, // Should still show loading
      });

      const { container } = renderWithProviders(
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      );

      // Should show loading, not content
      expect(container.querySelector('.animate-spin')).toBeInTheDocument();
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    });

    it('should handle empty children gracefully when authenticated', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
      });

      const { container } = renderWithProviders(
        <ProtectedRoute>{null}</ProtectedRoute>
      );

      // Should not crash, container should exist
      expect(container).toBeInTheDocument();
    });
  });

  describe('PropTypes Validation', () => {
    it('should accept valid children prop', () => {
      useAuthStore.mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
      });

      // Should not throw with valid children
      expect(() => {
        renderWithProviders(
          <ProtectedRoute>
            <TestComponent />
          </ProtectedRoute>
        );
      }).not.toThrow();
    });
  });

  describe('Snapshot Tests', () => {
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

      expect(container.firstChild).toMatchSnapshot();
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

      expect(container.firstChild).toMatchSnapshot();
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

      expect(container.firstChild).toMatchSnapshot();
    });
  });
});
