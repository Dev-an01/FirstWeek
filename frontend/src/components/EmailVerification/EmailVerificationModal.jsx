import { useState, useEffect } from 'react';
import { Mail, X, Clock, CheckCircle } from 'lucide-react';
import * as api from '../../services/api';
import { Button } from '../ui/Button';
import { Toast } from '../ui/Toast';

/**
 * EmailVerificationModal Component
 * Modal for entering OTP to verify email address
 * Includes 30-second resend timer
 */
export function EmailVerificationModal({
  isOpen,
  onClose,
  email,
  onVerificationSuccess,
}) {
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  const [resendTimer, setResendTimer] = useState(0);
  const [isResending, setIsResending] = useState(false);

  // Start 30-second timer on mount
  useEffect(() => {
    if (isOpen) {
      setResendTimer(30);
    }
  }, [isOpen]);

  // Countdown timer
  useEffect(() => {
    if (resendTimer > 0) {
      const timer = setTimeout(() => {
        setResendTimer(resendTimer - 1);
      }, 1000);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [resendTimer]);

  // Handle OTP input change
  const handleOtpChange = (index, value) => {
    // Only allow numbers
    if (value && !/^\d$/.test(value)) return;

    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);

    // Auto-focus next input
    if (value && index < 5) {
      const nextInput = document.getElementById(`otp-${index + 1}`);
      if (nextInput) nextInput.focus();
    }
  };

  // Handle backspace
  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      const prevInput = document.getElementById(`otp-${index - 1}`);
      if (prevInput) prevInput.focus();
    }
  };

  // Handle paste
  const handlePaste = (e) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').trim();

    // Only process if it's 6 digits
    if (/^\d{6}$/.test(pastedData)) {
      const newOtp = pastedData.split('');
      setOtp(newOtp);

      // Focus last input
      const lastInput = document.getElementById('otp-5');
      if (lastInput) lastInput.focus();
    }
  };

  // Verify OTP
  const handleVerifyOtp = async (e) => {
    e.preventDefault();

    const otpString = otp.join('');
    if (otpString.length !== 6) {
      setToast({
        message: 'Please enter the complete 6-digit OTP',
        type: 'error',
      });
      return;
    }

    setIsSubmitting(true);
    try {
      await api.verifyEmailOTP(email, otpString);
      setToast({ message: 'Email verified successfully!', type: 'success' });

      // Call success callback after short delay
      setTimeout(() => {
        if (onVerificationSuccess) {
          onVerificationSuccess();
        }
        onClose();
      }, 1500);
    } catch (error) {
      setToast({
        message: error.message || 'Invalid OTP. Please try again.',
        type: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Resend OTP
  const handleResendOtp = async () => {
    if (resendTimer > 0) return;

    setIsResending(true);
    try {
      await api.resendEmailOTP(email);
      setToast({ message: 'OTP sent successfully!', type: 'success' });
      setResendTimer(30); // Reset timer
      setOtp(['', '', '', '', '', '']); // Clear OTP inputs

      // Focus first input
      const firstInput = document.getElementById('otp-0');
      if (firstInput) firstInput.focus();
    } catch (error) {
      setToast({
        message: error.message || 'Failed to resend OTP',
        type: 'error',
      });
    } finally {
      setIsResending(false);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* Modal */}
        <div
          className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 sm:p-8 relative"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Close"
          >
            <X size={24} />
          </button>

          {/* Header */}
          <div className="text-center mb-6">
            <div className="w-16 h-16 bg-primary-light rounded-full flex items-center justify-center mx-auto mb-4">
              <Mail className="text-primary" size={32} />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Verify Your Email
            </h2>
            <p className="text-gray-600 text-sm">
              We've sent a 6-digit verification code to
            </p>
            <p className="text-primary font-medium mt-1">{email}</p>
          </div>

          {/* OTP Input Form */}
          <form onSubmit={handleVerifyOtp} className="space-y-6">
            {/* OTP Inputs */}
            <div className="flex justify-center gap-2 sm:gap-3">
              {otp.map((digit, index) => (
                <input
                  key={index}
                  id={`otp-${index}`}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleOtpChange(index, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(index, e)}
                  onPaste={handlePaste}
                  className="w-12 h-12 sm:w-14 sm:h-14 text-center text-xl font-bold border-2 border-gray-300 rounded-lg focus:border-primary focus:ring-2 focus:ring-primary-light outline-none transition-all"
                  aria-label={`OTP digit ${index + 1}`}
                />
              ))}
            </div>

            {/* Verify Button */}
            <Button
              type="submit"
              disabled={isSubmitting || otp.join('').length !== 6}
              className="w-full"
            >
              {isSubmitting ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2" />
                  Verifying...
                </>
              ) : (
                <>
                  <CheckCircle size={20} className="mr-2" />
                  Verify Email
                </>
              )}
            </Button>

            {/* Resend OTP */}
            <div className="text-center">
              <p className="text-sm text-gray-600 mb-2">
                Didn't receive the code?
              </p>
              {resendTimer > 0 ? (
                <div className="flex items-center justify-center gap-2 text-gray-500">
                  <Clock size={16} />
                  <span className="text-sm">
                    Resend in{' '}
                    <span className="font-bold text-primary">
                      {resendTimer}s
                    </span>
                  </span>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={isResending}
                  className="text-primary hover:text-primary-dark font-medium text-sm underline disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isResending ? 'Sending...' : 'Resend OTP'}
                </button>
              )}
            </div>
          </form>

          {/* Help text */}
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-600 text-center">
              💡 <strong>Tip:</strong> Check your spam folder if you don't see
              the email. The code expires in 10 minutes.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
