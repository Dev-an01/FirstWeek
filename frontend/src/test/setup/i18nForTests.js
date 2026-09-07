/**
 * i18n Configuration for Tests
 * Simplified i18n setup for testing environment
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

i18n.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  ns: ['translation'],
  defaultNS: 'translation',
  interpolation: {
    escapeValue: false,
  },
  resources: {
    en: {
      translation: {
        login: {
          title: 'Welcome Back',
          subtitle: 'Login to access your account',
          emailOrUsername: 'Email or Username',
          password: 'Password',
          forgotPassword: 'Forgot Password?',
          loginButton: 'Login',
          loggingIn: 'Logging in...',
          noAccount: "Don't have an account?",
          signUp: 'Sign Up',
        },
        signup: {
          title: 'Create Account',
          subtitle: 'Join us today',
          email: 'Email',
          username: 'Username',
          password: 'Password',
          firstName: 'First Name',
          lastName: 'Last Name',
          signupButton: 'Sign Up',
          signingUp: 'Signing up...',
          haveAccount: 'Already have an account?',
          login: 'Login',
        },
      },
    },
  },
});

export default i18n;
