import { Navigate } from 'react-router-dom';
import PropTypes from 'prop-types';
import { useAuthStore } from '../../store/authStore';

/**
 * AdminRoute Component
 * Restricts access to COMPANY_ADMIN and SUPER_ADMIN roles
 * Redirects to dashboard if user doesn't have admin privileges
 */
export function AdminRoute({ children }) {
    const { user, isAuthenticated, isLoading } = useAuthStore();

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent" />
            </div>
        );
    }

    // Not authenticated - redirect to login
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    // Check if user has admin role (COMPANY_ADMIN or SUPER_ADMIN)
    const isAdmin = ['COMPANY_ADMIN', 'SUPER_ADMIN'].includes(user?.role);

    if (!isAdmin) {
        // User is authenticated but doesn't have admin privileges
        return <Navigate to="/dashboard" replace />;
    }

    return children;
}

AdminRoute.propTypes = {
    children: PropTypes.node.isRequired,
};

/**
 * SuperAdminRoute Component
 * Restricts access to SUPER_ADMIN role only
 * Redirects to dashboard if user doesn't have super admin privileges
 */
export function SuperAdminRoute({ children }) {
    const { user, isAuthenticated, isLoading } = useAuthStore();

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent" />
            </div>
        );
    }

    // Not authenticated - redirect to login
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    // Check if user is SUPER_ADMIN
    const isSuperAdmin = user?.role === 'SUPER_ADMIN';

    if (!isSuperAdmin) {
        // User is authenticated but doesn't have super admin privileges
        return <Navigate to="/dashboard" replace />;
    }

    return children;
}

SuperAdminRoute.propTypes = {
    children: PropTypes.node.isRequired,
};
