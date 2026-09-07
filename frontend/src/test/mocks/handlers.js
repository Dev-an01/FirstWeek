/**
 * MSW (Mock Service Worker) Handlers
 * Define mock API endpoints for testing
 */
import { rest } from 'msw';
import {
  loginSuccessResponse,
  loginFailureResponse,
  registerSuccessResponse,
  getMeSuccessResponse,
  getMeUnauthorizedResponse,
  logoutSuccessResponse,
  logoutAllSuccessResponse,
  refreshSuccessResponse,
  checkEmailAvailableResponse,
  checkUsernameAvailableResponse,
  validateTokenSuccessResponse,
  updateProfileSuccessResponse,
  changePasswordSuccessResponse,
  deactivateAccountSuccessResponse,
  getSessionsSuccessResponse,
  revokeSessionSuccessResponse,
  getSessionStatsSuccessResponse,
  sendEmailOTPSuccessResponse,
  verifyEmailOTPSuccessResponse,
  checkVerificationStatusVerifiedResponse,
  forgotPasswordSuccessResponse,
  resetPasswordSuccessResponse,
  validateResetTokenSuccessResponse,
} from '../fixtures/apiResponses';

// Base URL for API - match your actual API configuration
const API_BASE_URL = 'http://localhost:3001/api/users';

// ==================== PUBLIC ENDPOINTS ====================

/**
 * POST /register - User registration
 */
export const registerHandler = rest.post(
  `${API_BASE_URL}/register`,
  async (req, res, ctx) => {
    const body = await req.json();

    // Simulate validation errors
    if (!body.email || !body.password) {
      return res(
        ctx.status(400),
        ctx.json({
          success: false,
          error: { message: 'Email and password are required' },
        })
      );
    }

    return res(ctx.json(registerSuccessResponse));
  }
);

/**
 * POST /login - User login
 */
export const loginHandler = rest.post(
  `${API_BASE_URL}/login`,
  async (req, res, ctx) => {
    const body = await req.json();

    // Simulate invalid credentials
    if (body.identifier === 'wronguser' || body.password === 'wrongpassword') {
      return res(ctx.status(401), ctx.json(loginFailureResponse));
    }

    return res(ctx.json(loginSuccessResponse));
  }
);

/**
 * POST /logout - Logout current session
 */
export const logoutHandler = rest.post(
  `${API_BASE_URL}/logout`,
  (req, res, ctx) => {
    return res(ctx.json(logoutSuccessResponse));
  }
);

/**
 * POST /refresh - Refresh access token
 */
export const refreshHandler = rest.post(
  `${API_BASE_URL}/refresh`,
  (req, res, ctx) => {
    return res(ctx.json(refreshSuccessResponse));
  }
);

/**
 * POST /check-email - Check if email is available
 */
export const checkEmailHandler = rest.post(
  `${API_BASE_URL}/check-email`,
  (req, res, ctx) => {
    return res(ctx.json(checkEmailAvailableResponse));
  }
);

/**
 * POST /check-username - Check if username is available
 */
export const checkUsernameHandler = rest.post(
  `${API_BASE_URL}/check-username`,
  (req, res, ctx) => {
    return res(ctx.json(checkUsernameAvailableResponse));
  }
);

/**
 * GET /validate-token - Validate current token
 */
export const validateTokenHandler = rest.get(
  `${API_BASE_URL}/validate-token`,
  (req, res, ctx) => {
    return res(ctx.json(validateTokenSuccessResponse));
  }
);

// ==================== PROTECTED ENDPOINTS ====================

/**
 * GET /me - Get current user profile
 */
export const getMeHandler = rest.get(`${API_BASE_URL}/me`, (req, res, ctx) => {
  // Check for authorization (simulate)
  const cookies = req.headers.get('cookie') || '';
  const hasAuthCookie =
    cookies.includes('accessToken') || cookies.includes('refreshToken');

  if (!hasAuthCookie) {
    return res(ctx.status(401), ctx.json(getMeUnauthorizedResponse));
  }

  return res(ctx.json(getMeSuccessResponse));
});

/**
 * PUT /me - Update user profile
 */
export const updateProfileHandler = rest.put(
  `${API_BASE_URL}/me`,
  (req, res, ctx) => {
    return res(ctx.json(updateProfileSuccessResponse));
  }
);

/**
 * PUT /change-password - Change password
 */
export const changePasswordHandler = rest.put(
  `${API_BASE_URL}/change-password`,
  (req, res, ctx) => {
    return res(ctx.json(changePasswordSuccessResponse));
  }
);

/**
 * PUT /deactivate - Deactivate account
 */
export const deactivateAccountHandler = rest.put(
  `${API_BASE_URL}/deactivate`,
  (req, res, ctx) => {
    return res(ctx.json(deactivateAccountSuccessResponse));
  }
);

/**
 * POST /logout-all - Logout from all devices
 */
export const logoutAllHandler = rest.post(
  `${API_BASE_URL}/logout-all`,
  (req, res, ctx) => {
    return res(ctx.json(logoutAllSuccessResponse));
  }
);

// ==================== SESSION MANAGEMENT ====================

/**
 * GET /sessions - Get all user sessions
 */
export const getSessionsHandler = rest.get(
  `${API_BASE_URL}/sessions`,
  (req, res, ctx) => {
    return res(ctx.json(getSessionsSuccessResponse));
  }
);

/**
 * DELETE /sessions/:sessionId - Revoke a specific session
 */
export const revokeSessionHandler = rest.delete(
  `${API_BASE_URL}/sessions/:sessionId`,
  (req, res, ctx) => {
    return res(ctx.json(revokeSessionSuccessResponse));
  }
);

/**
 * GET /sessions/stats - Get session statistics
 */
export const getSessionStatsHandler = rest.get(
  `${API_BASE_URL}/sessions/stats`,
  (req, res, ctx) => {
    return res(ctx.json(getSessionStatsSuccessResponse));
  }
);

// ==================== EMAIL VERIFICATION ====================

/**
 * POST /email/send-otp - Send email verification OTP
 */
export const sendEmailOTPHandler = rest.post(
  `${API_BASE_URL}/email/send-otp`,
  (req, res, ctx) => {
    return res(ctx.json(sendEmailOTPSuccessResponse));
  }
);

/**
 * POST /email/verify-otp - Verify email with OTP
 */
export const verifyEmailOTPHandler = rest.post(
  `${API_BASE_URL}/email/verify-otp`,
  (req, res, ctx) => {
    return res(ctx.json(verifyEmailOTPSuccessResponse));
  }
);

/**
 * POST /email/resend-otp - Resend email OTP
 */
export const resendEmailOTPHandler = rest.post(
  `${API_BASE_URL}/email/resend-otp`,
  (req, res, ctx) => {
    return res(ctx.json(sendEmailOTPSuccessResponse));
  }
);

/**
 * GET /email/verification-status - Check email verification status
 */
export const checkVerificationStatusHandler = rest.get(
  `${API_BASE_URL}/email/verification-status`,
  (req, res, ctx) => {
    return res(ctx.json(checkVerificationStatusVerifiedResponse));
  }
);

// ==================== PASSWORD RESET ====================

/**
 * POST /password/forgot - Request password reset
 */
export const forgotPasswordHandler = rest.post(
  `${API_BASE_URL}/password/forgot`,
  (req, res, ctx) => {
    return res(ctx.json(forgotPasswordSuccessResponse));
  }
);

/**
 * POST /password/reset - Reset password with token
 */
export const resetPasswordHandler = rest.post(
  `${API_BASE_URL}/password/reset`,
  (req, res, ctx) => {
    return res(ctx.json(resetPasswordSuccessResponse));
  }
);

/**
 * GET /password/validate-token/:token - Validate password reset token
 */
export const validateResetTokenHandler = rest.get(
  `${API_BASE_URL}/password/validate-token/:token`,
  (req, res, ctx) => {
    return res(ctx.json(validateResetTokenSuccessResponse));
  }
);

// ==================== DEFAULT HANDLERS ====================

/**
 * Export all handlers as default array
 */
export const handlers = [
  // Public endpoints
  registerHandler,
  loginHandler,
  logoutHandler,
  refreshHandler,
  checkEmailHandler,
  checkUsernameHandler,
  validateTokenHandler,

  // Protected endpoints
  getMeHandler,
  updateProfileHandler,
  changePasswordHandler,
  deactivateAccountHandler,
  logoutAllHandler,

  // Session management
  getSessionsHandler,
  revokeSessionHandler,
  getSessionStatsHandler,

  // Email verification
  sendEmailOTPHandler,
  verifyEmailOTPHandler,
  resendEmailOTPHandler,
  checkVerificationStatusHandler,

  // Password reset
  forgotPasswordHandler,
  resetPasswordHandler,
  validateResetTokenHandler,
];

export default handlers;
