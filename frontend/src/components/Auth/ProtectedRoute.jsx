import { Navigate } from 'react-router-dom';
import PropTypes from 'prop-types';
import { useAuthStore } from '../../store/authStore';

/**
 * ProtectedRoute Component
 * Redirects to login if user is not authenticated
 * Shows loading spinner while checking auth status
 */
export function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

ProtectedRoute.propTypes = {
  children: PropTypes.node.isRequired,
};
