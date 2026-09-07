import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Lock, CheckCircle, XCircle } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { PasswordInput } from '../components/ui/PasswordInput';
import { Toast } from '../components/ui/Toast';
import * as api from '../services/api';

/**
 * ResetPasswordPage Component
 * Allows users to reset their password using a reset token
 */
export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [validatingToken, setValidatingToken] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [maskedEmail, setMaskedEmail] = useState('');
  const [toast, setToast] = useState(null);
  const [resetSuccess, setResetSuccess] = useState(false);

  /**
   * Validate token on component mount
   */
  useEffect(() => {
    const validateToken = async () => {
      if (!token) {
        setTokenValid(false);
        setValidatingToken(false);
        setToast({
          message: 'Invalid or missing reset token',
          type: 'error',
        });
        return;
      }

      try {
        const response = await api.validateResetToken(token);
        if (response.data?.valid) {
          setTokenValid(true);
          setMaskedEmail(response.data.email || '');
        } else {
          setTokenValid(false);
          setToast({
            message: 'Invalid or expired reset token',
            type: 'error',
          });
        }
      } catch (error) {
        setTokenValid(false);
        setToast({
          message: error.message || 'Invalid or expired reset token',
          type: 'error',
        });
      } finally {
        setValidatingToken(false);
      }
    };

    validateToken();
  }, [token]);

  /**
   * Handle form submission
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setToast(null);

    // Validate passwords match
    if (newPassword !== confirmPassword) {
      setToast({
        message: 'Passwords do not match',
        type: 'error',
      });
      return;
    }

    // Validate password strength
    if (newPassword.length < 8) {
      setToast({
        message: 'Password must be at least 8 characters long',
        type: 'error',
      });
      return;
    }

    setLoading(true);

    try {
      const response = await api.resetPassword(
        token,
        newPassword,
        confirmPassword
      );
      setResetSuccess(true);
      setToast({
        message:
          response.message ||
          'Password reset successfully. You can now login with your new password.',
        type: 'success',
      });

      // Redirect to login page after 3 seconds
      setTimeout(() => {
        navigate('/login');
      }, 3000);
    } catch (error) {
      setToast({
        message: error.message || 'Failed to reset password. Please try again.',
        type: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  /**
   * Render loading state
   */
  if (validatingToken) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-xl shadow-lg text-center">
          <div className="w-16 h-16 bg-primary-light rounded-full flex items-center justify-center mx-auto animate-pulse">
            <Lock className="text-primary" size={32} />
          </div>
          <p className="text-gray-600">Validating reset link...</p>
        </div>
      </div>
    );
  }

  /**
   * Render invalid token state
   */
  if (!tokenValid) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center px-4 sm:px-6 lg:px-8">
        {toast && (
          <Toast
            message={toast.message}
            type={toast.type}
            onClose={() => setToast(null)}
          />
        )}
        <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-xl shadow-lg">
          <div className="text-center">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <XCircle className="text-red-600" size={32} />
            </div>
            <h2 className="text-3xl font-bold text-gray-900">
              Invalid Reset Link
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              This password reset link is invalid or has expired.
            </p>
          </div>

          <div className="space-y-3">
            <Link to="/forgot-password">
              <Button variant="primary" className="w-full">
                Request New Reset Link
              </Button>
            </Link>
            <Link to="/login">
              <Button variant="outline" className="w-full">
                Back to Login
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  /**
   * Render success state
   */
  if (resetSuccess) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center px-4 sm:px-6 lg:px-8">
        {toast && (
          <Toast
            message={toast.message}
            type={toast.type}
            onClose={() => setToast(null)}
          />
        )}
        <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-xl shadow-lg">
          <div className="text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="text-green-600" size={32} />
            </div>
            <h2 className="text-3xl font-bold text-gray-900">
              Password Reset Successful!
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              Your password has been reset successfully. You can now login with
              your new password.
            </p>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm text-blue-800">
              Redirecting to login page in 3 seconds...
            </p>
          </div>

          <Link to="/login">
            <Button className="w-full">Go to Login</Button>
          </Link>
        </div>
      </div>
    );
  }

  /**
   * Render reset password form
   */
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center px-4 sm:px-6 lg:px-8">
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-xl shadow-lg">
        {/* Header */}
        <div className="text-center">
          <div className="w-16 h-16 bg-primary-light rounded-full flex items-center justify-center mx-auto mb-4">
            <Lock className="text-primary" size={32} />
          </div>
          <h2 className="text-3xl font-bold text-primary">Reset Password</h2>
          <p className="mt-2 text-sm text-gray-600">
            {maskedEmail && `For ${maskedEmail}`}
          </p>
          <p className="mt-1 text-sm text-gray-600">
            Enter your new password below
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* New Password */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              New Password
            </label>
            <PasswordInput
              placeholder="Enter new password"
              value={newPassword}
              onChange={setNewPassword}
              required
              disabled={loading}
              autoComplete="new-password"
              showStrength
            />
            <p className="text-xs text-gray-500 mt-1">
              Must be at least 8 characters with uppercase, lowercase, number,
              and special character
            </p>
          </div>

          {/* Confirm Password */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Confirm Password
            </label>
            <PasswordInput
              placeholder="Confirm new password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              required
              disabled={loading}
              autoComplete="new-password"
            />
          </div>

          {/* Password Match Indicator */}
          {newPassword && confirmPassword && (
            <div
              className={`text-sm ${newPassword === confirmPassword ? 'text-green-600' : 'text-red-600'}`}
            >
              {newPassword === confirmPassword
                ? '✓ Passwords match'
                : '✗ Passwords do not match'}
            </div>
          )}

          {/* Submit Button */}
          <Button
            type="submit"
            loading={loading}
            disabled={loading || !newPassword || !confirmPassword}
            className="w-full"
          >
            {loading ? 'Resetting Password...' : 'Reset Password'}
          </Button>

          {/* Back to Login */}
          <div className="text-center">
            <Link to="/login" className="text-sm text-primary hover:underline">
              Remember your password? Login
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
