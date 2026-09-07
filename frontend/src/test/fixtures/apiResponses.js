/**
 * API Response Fixtures
 * Mock API responses for testing
 */
import {
  mockUser,
  mockDeactivatedUser,
  mockSessions,
  mockSessionStats,
} from './users';

/**
 * Successful response wrapper
 */
const successResponse = (data) => ({
  success: true,
  data,
});

/**
 * Error response wrapper
 */
const errorResponse = (message, code = 'ERROR') => ({
  success: false,
  error: {
    message,
    code,
  },
});

// ==================== AUTH RESPONSES ====================

export const loginSuccessResponse = successResponse({
  user: mockUser,
  message: 'Login successful',
});

export const loginFailureResponse = errorResponse(
  'Invalid credentials',
  'INVALID_CREDENTIALS'
);

export const registerSuccessResponse = successResponse({
  user: mockUser,
  message: 'Registration successful',
});

export const registerFailureResponse = errorResponse(
  'Email already exists',
  'EMAIL_EXISTS'
);

export const logoutSuccessResponse = successResponse({
  message: 'Logout successful',
});

export const logoutAllSuccessResponse = successResponse({
  message: 'Logged out from all devices',
});

export const refreshSuccessResponse = successResponse({
  message: 'Token refreshed successfully',
});

export const refreshFailureResponse = errorResponse(
  'Invalid refresh token',
  'INVALID_REFRESH_TOKEN'
);

// ==================== USER RESPONSES ====================

export const getMeSuccessResponse = successResponse({
  user: mockUser,
});

export const getMeUnauthorizedResponse = errorResponse(
  'Unauthorized',
  'UNAUTHORIZED'
);

export const getMeDeactivatedResponse = successResponse({
  user: mockDeactivatedUser,
});

export const updateProfileSuccessResponse = successResponse({
  user: {
    ...mockUser,
    firstName: 'Updated',
    lastName: 'Name',
  },
  message: 'Profile updated successfully',
});

export const changePasswordSuccessResponse = successResponse({
  message: 'Password changed successfully',
});

export const changePasswordFailureResponse = errorResponse(
  'Current password is incorrect',
  'INCORRECT_PASSWORD'
);

export const deactivateAccountSuccessResponse = successResponse({
  message: 'Account deactivated successfully',
});

// ==================== VALIDATION RESPONSES ====================

export const checkEmailAvailableResponse = successResponse({
  available: true,
  message: 'Email is available',
});

export const checkEmailTakenResponse = successResponse({
  available: false,
  message: 'Email is already taken',
});

export const checkUsernameAvailableResponse = successResponse({
  available: true,
  message: 'Username is available',
});

export const checkUsernameTakenResponse = successResponse({
  available: false,
  message: 'Username is already taken',
});

export const validateTokenSuccessResponse = successResponse({
  valid: true,
  message: 'Token is valid',
});

export const validateTokenFailureResponse = errorResponse(
  'Invalid token',
  'INVALID_TOKEN'
);

// ==================== SESSION RESPONSES ====================

export const getSessionsSuccessResponse = successResponse({
  sessions: mockSessions,
});

export const revokeSessionSuccessResponse = successResponse({
  message: 'Session revoked successfully',
});

export const getSessionStatsSuccessResponse = successResponse({
  stats: mockSessionStats,
});

// ==================== EMAIL VERIFICATION RESPONSES ====================

export const sendEmailOTPSuccessResponse = successResponse({
  message: 'OTP sent successfully',
});

export const verifyEmailOTPSuccessResponse = successResponse({
  message: 'Email verified successfully',
  user: {
    ...mockUser,
    isEmailVerified: true,
  },
});

export const verifyEmailOTPFailureResponse = errorResponse(
  'Invalid OTP',
  'INVALID_OTP'
);

export const checkVerificationStatusVerifiedResponse = successResponse({
  isVerified: true,
});

export const checkVerificationStatusUnverifiedResponse = successResponse({
  isVerified: false,
});

// ==================== PASSWORD RESET RESPONSES ====================

export const forgotPasswordSuccessResponse = successResponse({
  message: 'Password reset email sent',
});

export const resetPasswordSuccessResponse = successResponse({
  message: 'Password reset successful',
});

export const resetPasswordFailureResponse = errorResponse(
  'Invalid or expired reset token',
  'INVALID_RESET_TOKEN'
);

export const validateResetTokenSuccessResponse = successResponse({
  valid: true,
});

export const validateResetTokenFailureResponse = errorResponse(
  'Invalid or expired token',
  'INVALID_TOKEN'
);

// ==================== ERROR RESPONSES ====================

export const networkErrorResponse = {
  message: 'Network Error',
};

export const serverErrorResponse = errorResponse(
  'Internal server error',
  'INTERNAL_ERROR'
);

export const forbiddenResponse = errorResponse('Access denied', 'FORBIDDEN');

export const notFoundResponse = errorResponse(
  'Resource not found',
  'NOT_FOUND'
);
