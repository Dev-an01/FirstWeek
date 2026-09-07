/**
 * DashboardCard Component
 * Reusable card component for dashboard sections
 */
export function DashboardCard({ title, children, icon: Icon, className = '' }) {
  return (
    <div
      className={`bg-white rounded-xl p-5 lg:p-6 shadow-sm hover:shadow-md transition-shadow w-full max-w-full ${className}`}
    >
      <div className="flex items-center gap-3 mb-4">
        {Icon && (
          <div className="w-10 h-10 bg-primary-light rounded-full flex items-center justify-center flex-shrink-0">
            <Icon className="text-primary" size={20} aria-hidden="true" />
          </div>
        )}
        <h3 className="text-lg font-semibold text-primary">{title}</h3>
      </div>
      <div className="w-full max-w-full overflow-x-hidden">{children}</div>
    </div>
  );
}
