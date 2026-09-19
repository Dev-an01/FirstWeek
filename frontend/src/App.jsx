import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { ProtectedRoute } from './components/Auth/ProtectedRoute';
import { CompanyRequiredRoute } from './components/Auth/CompanyRequiredRoute';
import { OnboardingRoute } from './components/Auth/OnboardingRoute';
import { AdminRoute, SuperAdminRoute } from './components/Auth/AdminRoute';
import { PageLoader } from './components/PageLoader';
import './i18n/config';
import { publicApi } from './firstweek/publicApi';
import { initializePrivateAuth } from './store/authStore';

function PrivateAuthLifecycle() {
  const { pathname } = useLocation();
  const publicRoute = pathname === '/showcase' || pathname.startsWith('/showcase/');
  useEffect(() => {
    if (!publicRoute) return initializePrivateAuth();
    return undefined;
  }, [publicRoute]);
  return null;
}

// Keep auth pages as normal imports - they're needed immediately
import { SignupPage } from './pages/SignupPage';
import { LoginPage } from './firstweek/Login';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';

const FirstWeekWorkspace = lazy(() => import('./firstweek/Workspace'));
const FirstWeekPreview = import.meta.env.DEV
  ? lazy(() => import('./firstweek/Preview'))
  : null;

// Lazy load protected pages - loaded on-demand for better performance
const ProfilePage = lazy(() =>
  import('./pages/ProfilePage').then((module) => ({
    default: module.ProfilePage,
  }))
);
const ChatPage = lazy(() =>
  import('./pages/ChatPage').then((module) => ({
    default: module.ChatPage,
  }))
);

// Admin pages - lazy loaded
const OnboardingPage = lazy(() =>
  import('./pages/admin/OnboardingPage').then((module) => ({
    default: module.OnboardingPage,
  }))
);

const TeamManagementPage = lazy(() =>
  import('./pages/admin/TeamManagementPage').then((module) => ({
    default: module.TeamManagementPage,
  }))
);

const CompanyManagementPage = lazy(() =>
  import('./pages/admin/CompanyManagementPage').then((module) => ({
    default: module.CompanyManagementPage,
  }))
);

const UserManagementPage = lazy(() =>
  import('./pages/admin/UserManagementPage').then((module) => ({
    default: module.UserManagementPage,
  }))
);

const CompanyInfoPage = lazy(() =>
  import('./pages/admin/CompanyInfoPage').then((module) => ({
    default: module.CompanyInfoPage,
  }))
);

/**
 * Main App Component
 * Sets up routing with zustand auth store (no provider needed)
 * Uses React.lazy() and Suspense for code splitting and optimized bundle sizes
 */
function App() {
  return (
    <BrowserRouter>
      <PrivateAuthLifecycle />
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/showcase/:projectId?/:view?" element={<FirstWeekWorkspace client={publicApi} publicAccess />} />
          {import.meta.env.DEV && (
            <Route
              path="/preview/:projectId?/:view?"
              element={<FirstWeekPreview />}
            />
          )}
          <Route
            path="/projects/:projectId?/:view?"
            element={
              <ProtectedRoute>
                <FirstWeekWorkspace />
              </ProtectedRoute>
            }
          />
          {/* Public Routes - Not lazy loaded (needed immediately) */}
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />

          {/* Protected Routes - Lazy loaded for better performance */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <CompanyRequiredRoute>
                  <Navigate to="/projects" replace />
                </CompanyRequiredRoute>
              </ProtectedRoute>
            }
          />

          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/chat/:conversationId?"
            element={
              <ProtectedRoute>
                <CompanyRequiredRoute>
                  <ChatPage />
                </CompanyRequiredRoute>
              </ProtectedRoute>
            }
          />

          {/* Admin Routes - Onboarding Dashboard (COMPANY_ADMIN + SUPER_ADMIN + EXECUTIVE) */}
          <Route
            path="/admin/onboarding"
            element={
              <OnboardingRoute>
                <OnboardingPage />
              </OnboardingRoute>
            }
          />
          <Route
            path="/admin/onboarding/companies/:companyId"
            element={
              <OnboardingRoute>
                <OnboardingPage />
              </OnboardingRoute>
            }
          />
          <Route
            path="/admin/onboarding/companies/:companyId/executives/:executiveId"
            element={
              <OnboardingRoute>
                <OnboardingPage />
              </OnboardingRoute>
            }
          />

          {/* Admin Routes - Team Management (COMPANY_ADMIN + SUPER_ADMIN only) */}
          <Route
            path="/admin/team"
            element={
              <AdminRoute>
                <TeamManagementPage />
              </AdminRoute>
            }
          />

          {/* Admin Routes - Company Management (SUPER_ADMIN only) */}
          <Route
            path="/admin/companies"
            element={
              <SuperAdminRoute>
                <CompanyManagementPage />
              </SuperAdminRoute>
            }
          />

          <Route
            path="/admin/users"
            element={
              <SuperAdminRoute>
                <UserManagementPage />
              </SuperAdminRoute>
            }
          />

          {/* Company Info Page - Accessible to all company members except GUEST */}
          <Route
            path="/admin/company-info"
            element={
              <ProtectedRoute>
                <CompanyRequiredRoute>
                  <CompanyInfoPage />
                </CompanyRequiredRoute>
              </ProtectedRoute>
            }
          />

          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/projects" replace />} />

          {/* 404 Not Found */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
