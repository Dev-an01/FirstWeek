import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, ArrowLeft, CheckCircle } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { FormInput } from '../components/ui/FormInput';
import { Toast } from '../components/ui/Toast';
import * as api from '../services/api';

/**
 * ForgotPasswordPage Component
 * Allows users to request a password reset link
 */
export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [emailSent, setEmailSent] = useState(false);

  /**
   * Handle form submission
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setToast(null);

    try {
      const response = await api.forgotPassword(email);
      setEmailSent(true);
      setToast({
        message:
          response.message ||
          'If an account with that email exists, a password reset link has been sent.',
        type: 'success',
      });
    } catch (error) {
      setToast({
        message:
          error.message || 'Failed to send reset email. Please try again.',
        type: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

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
            <Mail className="text-primary" size={32} />
          </div>
          <h2 className="text-3xl font-bold text-primary">Forgot Password?</h2>
          <p className="mt-2 text-sm text-gray-600">
            {emailSent
              ? 'Check your email for reset instructions'
              : "Enter your email and we'll send you a reset link"}
          </p>
        </div>

        {emailSent ? (
          /* Success State */
          <div className="space-y-6">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start space-x-3">
              <CheckCircle
                className="text-green-600 flex-shrink-0 mt-0.5"
                size={20}
              />
              <div className="flex-1">
                <p className="text-sm text-green-800 font-medium">
                  Email sent successfully!
                </p>
                <p className="text-sm text-green-700 mt-1">
                  If an account exists for <strong>{email}</strong>, you will
                  receive a password reset link shortly.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-sm text-gray-600 text-center">
                Didn't receive the email? Check your spam folder or try again.
              </p>
              <Button
                onClick={() => {
                  setEmailSent(false);
                  setEmail('');
                }}
                variant="outline"
                className="w-full"
              >
                Try Another Email
              </Button>
            </div>

            <Link
              to="/login"
              className="flex items-center justify-center text-sm text-primary hover:underline"
            >
              <ArrowLeft size={16} className="mr-1" />
              Back to Login
            </Link>
          </div>
        ) : (
          /* Form State */
          <form onSubmit={handleSubmit} className="space-y-6">
            <FormInput
              type="email"
              placeholder="Email Address"
              value={email}
              onChange={setEmail}
              icon={<Mail size={20} />}
              required
              disabled={loading}
              autoComplete="email"
            />

            <Button
              type="submit"
              loading={loading}
              disabled={loading || !email}
              className="w-full"
            >
              {loading ? 'Sending...' : 'Send Reset Link'}
            </Button>

            <Link
              to="/login"
              className="flex items-center justify-center text-sm text-primary hover:underline"
            >
              <ArrowLeft size={16} className="mr-1" />
              Back to Login
            </Link>
          </form>
        )}
      </div>
    </div>
  );
}
