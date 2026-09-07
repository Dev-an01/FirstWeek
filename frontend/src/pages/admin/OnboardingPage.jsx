/**
 * OnboardingPage (Memoized)
 *
 * Admin dashboard for managing companies, executives, and documents.
 * Uses URL params to determine which view to show.
 */

import { memo, useEffect, useCallback, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Navbar } from '../../components/Navbar/Navbar';
import { Sidebar } from '../../components/Sidebar/Sidebar';
import { useOnboardingStore } from '../../store/onboardingStore';
import { useUIStore } from '../../store/uiStore';
import { useAuthStore } from '../../store/authStore';
import * as api from '../../services/onboardingApi';

// Sub-views
import { CompanyListView } from './views/CompanyListView';
import { CompanyDetailView } from './views/CompanyDetailView';
import { ExecutiveDetailView } from './views/ExecutiveDetailView';

function OnboardingPageComponent() {
  const { companyId, executiveId } = useParams();
  const navigate = useNavigate();

  // Selective store subscriptions for performance
  const fetchCompanies = useOnboardingStore((s) => s.fetchCompanies);
  const selectCompany = useOnboardingStore((s) => s.selectCompany);
  const selectExecutive = useOnboardingStore((s) => s.selectExecutive);
  const clearCompanySelection = useOnboardingStore((s) => s.clearCompanySelection);
  const clearExecutiveSelection = useOnboardingStore((s) => s.clearExecutiveSelection);
  const reset = useOnboardingStore((s) => s.reset);

  const showErrorToast = useUIStore((s) => s.showErrorToast);
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const closeSidebar = useUIStore((s) => s.closeSidebar);
  const { user } = useAuthStore(); // Changed user access
  const [executiveNotFound, setExecutiveNotFound] = useState(false);

  // Redirect Executives to their own profile if they hit the root
  useEffect(() => {
    if (!user?.companyId) return;

    if (user.role === 'EXECUTIVE' && !executiveId) {
      setExecutiveNotFound(false);
      // Find the executive profile for this user
      api.getExecutives(user.companyId, { email: user.email })
        .then(response => {
          const executives = response.executives || [];
          if (executives.length > 0) {
            // Found matching executive - redirect to their ID
            navigate(`/admin/onboarding/companies/${user.companyId}/executives/${executives[0].id}`, { replace: true });
          } else {
            console.warn('No executive profile found for email:', user.email);
            setExecutiveNotFound(true);
          }
        })
        .catch(err => {
          console.error('Failed to lookup executive profile:', err);
          setExecutiveNotFound(true);
        });
    }
    // COMPANY_ADMIN handling is done via direct render, no redirect needed for root
  }, [navigate, executiveId, user]);

  useEffect(() => {
    // Only fetch companies if SUPER_ADMIN
    if (user?.role === 'SUPER_ADMIN') {
      fetchCompanies().catch((err) => {
        console.error('Failed to fetch companies:', err);
        showErrorToast(err.message || 'Failed to load companies');
      });
    }

    return () => {
      // Cleanup on unmount
      reset();
    };
  }, [fetchCompanies, reset, showErrorToast, user]);

  // Load company logic
  useEffect(() => {
    const targetCompanyId = user?.role === 'COMPANY_ADMIN' ? user.companyId : companyId;

    if (targetCompanyId) {
      selectCompany(targetCompanyId).catch((err) => {
        console.error('Failed to load company:', err);
        showErrorToast(err.message || 'Failed to load company');
        // Only redirect if not executive or company admin
        if (user?.role === 'SUPER_ADMIN') {
          navigate('/admin/onboarding');
        }
      });
    } else {
      clearCompanySelection();
    }
  }, [companyId, selectCompany, clearCompanySelection, showErrorToast, navigate, user]);

  // Load executive when executiveId changes
  useEffect(() => {
    const targetCompanyId = user?.role === 'COMPANY_ADMIN' ? user.companyId : companyId;

    if (targetCompanyId && executiveId) {
      selectExecutive(targetCompanyId, executiveId).catch((err) => {
        console.error('Failed to load executive:', err);
        showErrorToast(err.message || 'Failed to load executive');
        if (user?.role === 'SUPER_ADMIN') {
          navigate(`/admin/onboarding/companies/${targetCompanyId}`);
        }
      });
    } else if (!executiveId) {
      clearExecutiveSelection();
    }
  }, [companyId, executiveId, selectExecutive, clearExecutiveSelection, showErrorToast, navigate, user]);

  // Navigation callbacks
  const handleNavigateToCompanies = useCallback(() => {
    navigate('/admin/onboarding');
  }, [navigate]);

  const handleNavigateToCompany = useCallback(
    (id) => {
      navigate(`/admin/onboarding/companies/${id}`);
    },
    [navigate]
  );

  const handleNavigateToExecutive = useCallback(
    (execId) => {
      const targetCompanyId = user?.companyId || companyId;
      navigate(`/admin/onboarding/companies/${targetCompanyId}/executives/${execId}`);
    },
    [navigate, companyId, user]
  );

  // Determine which view to render
  const renderContent = () => {
    // EXECUTIVE VIEW: Strict confinement
    if (user?.role === 'EXECUTIVE') {
      if (executiveNotFound) {
        return (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 max-w-md">
              <h2 className="text-lg font-semibold text-gray-900 mb-2">Profile Not Ready</h2>
              <p className="text-gray-600">
                Your executive profile is being set up. Please contact your company administrator or try refreshing the page.
              </p>
            </div>
          </div>
        );
      }
      if (executiveId && companyId) {
        return <ExecutiveDetailView />;
      }
      return null;
    }

    // COMPANY_ADMIN VIEW: Direct access to Company Detail
    if (user?.role === 'COMPANY_ADMIN') {
      if (executiveId) {
        return (
          <ExecutiveDetailView
            onBack={() => navigate(`/admin/onboarding`)} // Back goes to company root (which is effectively this page)
          />
        );
      }
      // Always show company detail, never the list
      return (
        <CompanyDetailView
          onSelectExecutive={handleNavigateToExecutive}
        // No onBack, they can't go to list
        />
      );
    }

    // SUPER_ADMIN VIEWS
    if (executiveId && companyId) {
      return (
        <ExecutiveDetailView
          onBack={() => navigate(`/admin/onboarding/companies/${companyId}`)}
        />
      );
    }

    if (companyId) {
      return (
        <CompanyDetailView
          onBack={handleNavigateToCompanies}
          onSelectExecutive={handleNavigateToExecutive}
        />
      );
    }

    return <CompanyListView onSelectCompany={handleNavigateToCompany} />;
  };

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      <Navbar />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        <main className="flex-1 overflow-y-auto">
          <div className="p-4 sm:p-6 lg:p-8">
            {renderContent()}
          </div>
        </main>
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black bg-opacity-50 md:hidden"
          onClick={closeSidebar}
        />
      )}
    </div>
  );
}

export const OnboardingPage = memo(OnboardingPageComponent);
export default OnboardingPage;
