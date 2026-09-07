import { BarChart3, User, LogOut, MessageSquare, Building2, Users } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useUIStore } from '../../store/uiStore';
import { useAuthStore } from '../../store/authStore';

/**
 * Sidebar Component
 * Responsive collapsible sidebar - hidden on mobile by default
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Optional children to render after main nav with separator
 */
export function Sidebar({ children }) {
  const location = useLocation();
  const { t } = useTranslation();
  const { sidebarOpen, closeSidebar } = useUIStore();
  const { logout, logoutAllDevices, user } = useAuthStore();

  // Check if user has admin privileges (COMPANY_ADMIN or SUPER_ADMIN)
  const isAdmin = ['COMPANY_ADMIN', 'SUPER_ADMIN'].includes(user?.role);
  const isSuperAdmin = user?.role === 'SUPER_ADMIN';

  // Base navigation items visible to all authenticated users
  const baseNavItems = [
    {
      icon: BarChart3,
      label: t('sidebar.dashboard'),
      href: '/dashboard',
      active: location.pathname === '/dashboard',
    },
    {
      icon: MessageSquare,
      label: t('sidebar.chat'),
      href: '/chat',
      active: location.pathname.startsWith('/chat'),
    },
    {
      icon: User,
      label: t('sidebar.profile'),
      href: '/profile',
      active: location.pathname === '/profile',
    },
  ];

  // Admin-only navigation items (COMPANY_ADMIN + SUPER_ADMIN)
  const adminNavItems = isAdmin
    ? [
      {
        icon: Building2,
        label: t('sidebar.onboarding'),
        href: '/admin/onboarding',
        active: location.pathname.startsWith('/admin/onboarding'),
      },
      {
        icon: Users,
        label: t('sidebar.team', 'Team'),
        href: '/admin/team',
        active: location.pathname.startsWith('/admin/team'),
      },
    ]
    : [];

  // Executive-only navigation
  const executiveNavItems = user?.role === 'EXECUTIVE'
    ? [
      {
        icon: Building2,
        label: t('sidebar.onboarding'),
        href: '/admin/onboarding',
        active: location.pathname.startsWith('/admin/onboarding'),
      },
    ]
    : [];

  // SUPER_ADMIN-only navigation items
  const superAdminNavItems = isSuperAdmin
    ? [
      {
        icon: Building2,
        label: t('sidebar.companies', 'Companies'),
        href: '/admin/companies',
        active: location.pathname.startsWith('/admin/companies'),
      },
      {
        icon: Users,
        label: t('sidebar.users', 'Users'),
        href: '/admin/users',
        active: location.pathname.startsWith('/admin/users'),
      },
    ]
    : [];

  // Company Info link - Visible to COMPANY_ADMIN, EMPLOYEE, EXECUTIVE (Not GUEST, Not SUPER_ADMIN unless they want to see their own "admin" company info?)
  // Request said: "COMPANY_ADMIN has a dedicated page... same for EMPLOYEE and EXECUTIVES... GUEST don't get to see"
  // Super Admin usually manages *other* companies, but might want to see theirs.
  // For now, let's enable for everyone except GUEST.
  const companyInfoItem = user?.role !== 'GUEST'
    ? [{
      icon: Building2,
      label: t('sidebar.companyInfo', 'Company Info'),
      href: '/admin/company-info',
      active: location.pathname === '/admin/company-info',
    }]
    : [];

  // Combine base and admin nav items
  const navItems = [...baseNavItems, ...adminNavItems, ...superAdminNavItems, ...executiveNavItems, ...companyInfoItem];

  return (
    <aside
      className={`${sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } md:translate-x-0 fixed md:static inset-y-0 left-0 z-40 w-72 md:w-64 lg:w-72 bg-white border-r border-gray-200 transition-transform duration-300 ease-in-out flex-shrink-0 overflow-y-auto h-screen md:h-auto`}
      aria-label="Sidebar navigation"
    >
      <div className="h-full flex flex-col p-3 md:p-4 md:min-h-[calc(100vh-4rem)]">
        {/* Navigation Links */}
        <nav className="space-y-1" role="navigation">
          {navItems.map((item) =>
            item.href.startsWith('/') ? (
              <Link
                key={item.label}
                to={item.href}
                onClick={closeSidebar}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary whitespace-nowrap ${item.active
                  ? 'text-primary bg-primary-light'
                  : 'text-gray-600 hover:bg-gray-50'
                  }`}
                aria-current={item.active ? 'page' : undefined}
              >
                <item.icon
                  size={18}
                  aria-hidden="true"
                  className="flex-shrink-0"
                />
                <span className="truncate">{item.label}</span>
              </Link>
            ) : (
              <a
                key={item.label}
                href={item.href}
                onClick={closeSidebar}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary whitespace-nowrap ${item.active
                  ? 'text-primary bg-primary-light'
                  : 'text-gray-600 hover:bg-gray-50'
                  }`}
                aria-current={item.active ? 'page' : undefined}
              >
                <item.icon
                  size={18}
                  aria-hidden="true"
                  className="flex-shrink-0"
                />
                <span className="truncate">{item.label}</span>
              </a>
            )
          )}
        </nav>

        {/* Chat Features Section (if children provided) */}
        {children && (
          <div className="border-t border-gray-200 mt-3 pt-3 flex-1 overflow-hidden flex flex-col">
            {children}
          </div>
        )}

        {/* Session Management Section */}
        <div className="border-t border-gray-200 pt-3 mt-3 space-y-1 flex-shrink-0">
          <p className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            {t('sidebar.session')}
          </p>
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-3 py-2.5 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 whitespace-nowrap"
          >
            <LogOut size={18} aria-hidden="true" className="flex-shrink-0" />
            <span className="truncate">{t('sidebar.logout')}</span>
          </button>
          <button
            onClick={logoutAllDevices}
            className="w-full text-left px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-primary truncate"
          >
            {t('sidebar.logoutAll')}
          </button>
        </div>
      </div>
    </aside>
  );
}
