import { Menu, X, UserCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { LanguageToggle } from '../LanguageToggle/LanguageToggle';
import { useUIStore } from '../../store/uiStore';

/**
 * Navbar Component
 * Top navigation bar with menu toggle and user actions
 */
export function Navbar() {
  const navigate = useNavigate();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <nav
      className="bg-white shadow-sm border-b border-gray-200"
      role="navigation"
      aria-label="Main navigation"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Left section */}
          <div className="flex items-center gap-4">
            <button
              onClick={toggleSidebar}
              className="lg:hidden text-primary hover:bg-gray-100 p-2 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="Toggle sidebar"
              aria-expanded={sidebarOpen}
            >
              {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
            <div className="flex items-center gap-3">
              <img
                src="/logo/header_logo.svg"
                alt="FirstWeek logo"
                className="h-8"
              />
              <span className="font-semibold text-primary text-lg">
                FirstWeek
              </span>
            </div>
          </div>

          {/* Center section - Japanese Lesson */}
          <div className="hidden md:flex items-center justify-center flex-1 px-4">
            <p className="text-sm text-gray-700 italic">
              今日の一言: 「継続は力なり」 - Consistency is power
            </p>
          </div>

          {/* Right section */}
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <button
              onClick={() => navigate('/profile')}
              className="text-primary hover:bg-gray-100 p-2 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="My profile"
              title="My Profile"
            >
              <UserCircle size={24} />
            </button>
            <button
              onClick={toggleSidebar}
              className="text-primary hover:bg-gray-100 p-2 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="Toggle menu"
              aria-expanded={sidebarOpen}
            >
              <Menu size={24} />
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
