/**
 * PageLoader Component
 * Loading fallback for lazy-loaded pages
 */
export function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-purple-50 to-blue-50">
      <div className="text-center">
        <div className="relative">
          {/* Spinner */}
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-gray-200 border-t-primary mx-auto" />

          {/* Optional: Inner pulse effect */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-8 w-8 bg-primary rounded-full opacity-20 animate-pulse" />
          </div>
        </div>

        {/* Loading text */}
        <p className="mt-4 text-gray-600 text-sm font-medium">Loading...</p>
      </div>
    </div>
  );
}
