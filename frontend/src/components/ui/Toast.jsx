import { useEffect } from 'react';
import { X, CheckCircle, AlertCircle } from 'lucide-react';

/**
 * Toast Component
 * Notification component with auto-dismiss
 */
export function Toast({ message, type = 'success', onClose, duration = 4000 }) {
  useEffect(() => {
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [onClose, duration]);

  const styles = {
    success: 'bg-green-500',
    error: 'bg-red-500',
    info: 'bg-blue-500',
    warning: 'bg-yellow-500',
  };

  const icons = {
    success: <CheckCircle size={20} />,
    error: <AlertCircle size={20} />,
    info: <AlertCircle size={20} />,
    warning: <AlertCircle size={20} />,
  };

  return (
    <div
      className={`fixed top-20 right-4 px-6 py-3 rounded-lg shadow-lg text-white ${styles[type]} animate-slide-in z-50 flex items-center gap-3 max-w-md`}
      role="alert"
      aria-live="assertive"
    >
      <span aria-hidden="true">{icons[type]}</span>
      <span className="flex-1">{message}</span>
      <button
        onClick={onClose}
        className="hover:bg-white hover:bg-opacity-20 p-1 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-white"
        aria-label="Close notification"
      >
        <X size={18} />
      </button>
    </div>
  );
}
