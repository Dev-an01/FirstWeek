import { useState } from 'react';
import { Mail, X, ShieldCheck } from 'lucide-react';
import * as api from '../../services/api';
import { EmailVerificationModal } from './EmailVerificationModal';
import { Toast } from '../ui/Toast';

/**
 * EmailVerificationBanner Component
 * Shows a dismissible banner prompting users to verify their email
 * Appears on dashboard and other pages for unverified users
 */
export function EmailVerificationBanner({ user, onVerificationSuccess }) {
  const [showBanner, setShowBanner] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [isSendingOtp, setIsSendingOtp] = useState(false);
  const [toast, setToast] = useState(null);

  // Don't show banner if email is already verified or banner is dismissed
  if (!user || user.emailVerified || !showBanner) {
    return null;
  }

  const handleSendOtp = async () => {
    setIsSendingOtp(true);
    try {
      await api.sendEmailOTP(user.email);
      setShowModal(true);
      setToast({
        message: 'Verification code sent to your email!',
        type: 'success',
      });
    } catch (error) {
      setToast({
        message: error.message || 'Failed to send verification code',
        type: 'error',
      });
    } finally {
      setIsSendingOtp(false);
    }
  };

  const handleVerificationSuccess = async () => {
    setShowModal(false);
    setShowBanner(false);
    setToast({ message: 'Email verified successfully!', type: 'success' });

    // Call parent callback to refresh user data
    if (onVerificationSuccess) {
      await onVerificationSuccess();
    }
  };

  return (
    <>
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* Email Verification Modal */}
      <EmailVerificationModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        email={user.email}
        onVerificationSuccess={handleVerificationSuccess}
      />

      {/* Verification Banner */}
      <div className="bg-orange-50 border-l-4 border-orange-400 p-4 mb-6 rounded-lg shadow-sm">
        <div className="flex items-start">
          <div className="flex-shrink-0">
            <Mail className="h-5 w-5 text-orange-400" aria-hidden="true" />
          </div>
          <div className="ml-3 flex-1">
            <h3 className="text-sm font-medium text-orange-800">
              Verify your email address
            </h3>
            <div className="mt-2 text-sm text-orange-700">
              <p>
                Please verify your email address <strong>{user.email}</strong>{' '}
                to access all features and secure your account.
              </p>
            </div>
            <div className="mt-4">
              <div className="flex gap-3">
                <button
                  onClick={handleSendOtp}
                  disabled={isSendingOtp}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ShieldCheck size={16} />
                  {isSendingOtp ? 'Sending...' : 'Verify Email'}
                </button>
                <button
                  onClick={() => setShowBanner(false)}
                  className="inline-flex items-center px-4 py-2 border border-orange-300 hover:bg-orange-100 text-orange-700 text-sm font-medium rounded-lg transition-colors"
                >
                  Remind me later
                </button>
              </div>
            </div>
          </div>
          <div className="ml-auto pl-3">
            <button
              onClick={() => setShowBanner(false)}
              className="inline-flex text-orange-400 hover:text-orange-600 transition-colors"
              aria-label="Dismiss"
            >
              <X size={20} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
