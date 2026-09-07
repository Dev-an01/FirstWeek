import { Navigate } from 'react-router-dom';
import PropTypes from 'prop-types';
import { useAuthStore } from '../../store/authStore';

/**
 * OnboardingRoute Component
 * Restricts access to users involved in onboarding:
 * - SUPER_ADMIN
 * - COMPANY_ADMIN
 * - EXECUTIVE
 * 
 * Redirects to dashboard if user doesn't have appropriate privileges
 */
export function OnboardingRoute({ children }) {
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

    // Check if user has allowed role
    const isAllowed = ['COMPANY_ADMIN', 'SUPER_ADMIN', 'EXECUTIVE'].includes(user?.role);

    if (!isAllowed) {
        // User is authenticated but doesn't have onboarding privileges
        return <Navigate to="/dashboard" replace />;
    }

    // EXECUTIVE must have a companyId to access onboarding
    if (user?.role === 'EXECUTIVE' && !user?.companyId) {
        return <Navigate to="/profile" replace />;
    }

    return children;
}

OnboardingRoute.propTypes = {
    children: PropTypes.node.isRequired,
};
