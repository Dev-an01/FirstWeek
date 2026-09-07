import { Navigate } from 'react-router-dom';
import PropTypes from 'prop-types';
import { useAuthStore } from '../../store/authStore';

/**
 * CompanyRequiredRoute Component
 * Restricts access to users who:
 * 1. Have verified their email
 * 2. Are assigned to a company
 * Users without email verification or company are redirected to profile page.
 */
export function CompanyRequiredRoute({ children }) {
    const user = useAuthStore((state) => state.user);
    const isLoading = useAuthStore((state) => state.isLoading);

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent" />
            </div>
        );
    }

    // If user hasn't verified email, redirect to profile
    if (!user?.emailVerified) {
        return <Navigate to="/profile" replace />;
    }

    // GUEST users cannot access company pages
    if (user?.role === 'GUEST') {
        return <Navigate to="/dashboard" replace />;
    }

    // SUPER_ADMIN manages all companies — no companyId needed
    // Other users need a company assignment to access protected pages
    if (!user?.companyId && user?.role !== 'SUPER_ADMIN') {
        return <Navigate to="/profile" replace />;
    }

    return children;
}

CompanyRequiredRoute.propTypes = {
    children: PropTypes.node.isRequired,
};
