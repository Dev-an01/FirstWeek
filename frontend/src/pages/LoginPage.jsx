import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../store/authStore';
import { FormInput } from '../components/ui/FormInput';
import { PasswordInput } from '../components/ui/PasswordInput';
import { Button } from '../components/ui/Button';
import { Toast } from '../components/ui/Toast';
import { LanguageToggle } from '../components/LanguageToggle/LanguageToggle';

/**
 * LoginPage Component
 * Fully responsive login page - fits all screen sizes
 */
export function LoginPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { login, isAuthenticated, isLoading } = useAuthStore();

  const [identifier, setIdentifier] = useState(''); // Can be username or email
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  /**
   * Redirect to dashboard if user is already authenticated
   */
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate]);

  /**
   * Handle form submission
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({});

    // Client-side validation
    const newErrors = {};
    if (!identifier.trim()) {
      newErrors.identifier = 'Username or email is required';
    }
    if (!password) {
      newErrors.password = 'Password is required';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setIsSubmitting(true);
    try {
      await login(identifier, password);
      setToast({ message: 'Login successful!', type: 'success' });
      setTimeout(() => navigate('/dashboard'), 1000);
    } catch (error) {
      setToast({
        message: error.message || 'Invalid credentials. Please try again.',
        type: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full overflow-x-hidden bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4">
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* Language Toggle - Top Right */}
      <div className="fixed top-4 right-4 z-50">
        <LanguageToggle />
      </div>

      <div className="w-full max-w-[90%] sm:max-w-md md:max-w-lg lg:max-w-xl bg-white rounded-2xl shadow-lg p-6 sm:p-8 md:p-10">
        <div className="flex flex-col items-center mb-6">
          <img
            src="/logo/header_logo.svg"
            alt="AI Avatar Logo"
            className="h-12 sm:h-16 mb-4"
          />
          <h1 className="text-xl sm:text-2xl font-bold text-primary text-center">
            {t('login.title')}
          </h1>
          <p className="text-sm text-gray-600 mt-2">{t('login.subtitle')}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 w-full" noValidate>
          <FormInput
            type="text"
            placeholder={t('login.emailOrUsername')}
            value={identifier}
            onChange={setIdentifier}
            icon={<Mail size={20} />}
            error={errors.identifier}
            required
            autoComplete="username"
          />

          <PasswordInput
            placeholder={t('login.password')}
            value={password}
            onChange={setPassword}
            error={errors.password}
            required
            autoComplete="current-password"
          />

          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-sm">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="remember"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="w-4 h-4 accent-primary cursor-pointer focus:ring-2 focus:ring-primary rounded flex-shrink-0"
              />
              <label
                htmlFor="remember"
                className="text-primary cursor-pointer select-none"
              >
                Remember me
              </label>
            </div>
            <Link
              to="/forgot-password"
              className="text-primary font-medium hover:underline focus:outline-none focus:ring-2 focus:ring-primary rounded px-1 text-left sm:text-right"
            >
              {t('login.forgotPassword')}
            </Link>
          </div>

          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? t('login.loggingIn') : t('login.loginButton')}
          </Button>
        </form>

        <p className="text-center mt-5 text-gray-600 text-sm">
          {t('login.noAccount')}{' '}
          <Link
            to="/signup"
            className="text-primary font-semibold underline hover:text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary rounded"
          >
            {t('login.signUp')}
          </Link>
        </p>
      </div>
    </div>
  );
}
