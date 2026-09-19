import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { User, Mail, Ticket, Briefcase } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../store/authStore';
import { FormInput } from '../components/ui/FormInput';
import { PasswordInput } from '../components/ui/PasswordInput';
import { Button } from '../components/ui/Button';
import { Toast } from '../components/ui/Toast';
import { LanguageToggle } from '../components/LanguageToggle/LanguageToggle';
import { validateEmail, validatePassword } from '../utils/validators';

/**
 * SignupPage Component
 * Fully responsive signup page - fits all screen sizes
 */
export function SignupPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { signup, isAuthenticated, isLoading } = useAuthStore();

  const [username, setUsername] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [title, setTitle] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [agreedToTerms, setAgreedToTerms] = useState(false);
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
    if (!username.trim()) {
      newErrors.username = 'Username is required';
    } else if (username.length < 3 || username.length > 30) {
      newErrors.username = 'Username must be 3-30 characters';
    } else if (!/^[a-z0-9_]+$/.test(username)) {
      newErrors.username =
        'Username must be lowercase alphanumeric and underscores only';
    }
    if (!firstName.trim()) {
      newErrors.firstName = 'First name is required';
    }
    if (!lastName.trim()) {
      newErrors.lastName = 'Last name is required';
    }
    if (!validateEmail(email)) {
      newErrors.email = 'Invalid email address';
    }
    const passwordValidation = validatePassword(password);
    if (!passwordValidation.valid) {
      newErrors.password = passwordValidation.message;
    }
    if (!agreedToTerms) {
      newErrors.terms = 'You must agree to the terms';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setIsSubmitting(true);
    try {
      await signup({
        username,
        firstName,
        lastName,
        email,
        password,
        title: title.trim() || undefined,
        inviteCode: inviteCode.trim() || undefined,
      });

      setToast({
        message: 'Account created successfully! Please login to continue.',
        type: 'success',
      });

      // Redirect to login page after successful signup
      setTimeout(() => navigate('/login'), 1500);
    } catch (error) {
      setToast({
        message: error.message || 'Signup failed. Please try again.',
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
            alt="FirstWeek logo"
            className="h-12 sm:h-16 mb-4"
          />
          <h1 className="text-xl sm:text-2xl font-bold text-primary text-center">
            {t('signup.title')}
          </h1>
          <p className="text-sm text-gray-600 mt-2">{t('signup.subtitle')}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 w-full" noValidate>
          <FormInput
            type="text"
            placeholder={t('signup.username')}
            value={username}
            onChange={setUsername}
            icon={<User size={20} />}
            error={errors.username}
            required
            maxLength={30}
            autoComplete="username"
          />

          <FormInput
            type="text"
            placeholder={t('signup.firstName')}
            value={firstName}
            onChange={setFirstName}
            icon={<User size={20} />}
            error={errors.firstName}
            required
            maxLength={50}
            autoComplete="given-name"
          />

          <FormInput
            type="text"
            placeholder={t('signup.lastName')}
            value={lastName}
            onChange={setLastName}
            icon={<User size={20} />}
            error={errors.lastName}
            required
            maxLength={50}
            autoComplete="family-name"
          />

          <FormInput
            type="text"
            placeholder="Title / Designation (optional, e.g., CEO)"
            value={title}
            onChange={setTitle}
            icon={<Briefcase size={20} />}
            maxLength={100}
            autoComplete="organization-title"
          />

          <FormInput
            type="email"
            placeholder={t('signup.email')}
            value={email}
            onChange={setEmail}
            icon={<Mail size={20} />}
            error={errors.email}
            required
            autoComplete="email"
          />

          <PasswordInput
            placeholder={t('signup.password')}
            value={password}
            onChange={setPassword}
            error={errors.password}
            showStrength
            required
            autoComplete="new-password"
          />

          <div>
            <FormInput
              type="text"
              placeholder="Invite Code (optional)"
              value={inviteCode}
              onChange={setInviteCode}
              icon={<Ticket size={20} />}
              maxLength={20}
              autoComplete="off"
            />
            <p className="text-xs text-gray-500 mt-1 ml-2">
              Have an invite code? Enter it to join a company.
            </p>
          </div>

          <div>
            <div className="flex items-start gap-3 px-4 py-2.5 border-2 border-gray-200 rounded-xl focus-within:border-primary transition-colors">
              <input
                type="checkbox"
                id="terms"
                checked={agreedToTerms}
                onChange={(e) => setAgreedToTerms(e.target.checked)}
                className="w-4 h-4 mt-0.5 accent-primary cursor-pointer focus:ring-2 focus:ring-primary rounded flex-shrink-0"
                aria-describedby={errors.terms ? 'terms-error' : undefined}
              />
              <label
                htmlFor="terms"
                className="text-primary text-sm cursor-pointer select-none leading-relaxed"
              >
                I agree to the Terms & Conditions
              </label>
            </div>
            {errors.terms && (
              <p
                id="terms-error"
                className="text-red-500 text-sm mt-1 ml-2"
                role="alert"
              >
                {errors.terms}
              </p>
            )}
          </div>

          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? t('signup.signingUp') : t('signup.signupButton')}
          </Button>
        </form>

        <p className="text-center mt-5 text-gray-600 text-sm">
          {t('signup.haveAccount')}{' '}
          <Link
            to="/login"
            className="text-primary font-semibold underline hover:text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary rounded"
          >
            {t('signup.login')}
          </Link>
        </p>
      </div>
    </div>
  );
}
