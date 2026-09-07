// auth-service/controllers/emailVerificationController.js
const emailVerificationService = require("../services/emailService");
const { emailSchema, otpSchema } = require("../models/userSchema");
const { createSuccessResponse, createErrorResponse } = require("../lib/utils");
const {
  createLogger,
  // eslint-disable-next-line
} = require('../shared/utils/logger');

const logger = createLogger("email-verification-controller");
/**
 * Send email verification OTP
 * @route POST /api/users/email/send-otp
 */
const sendEmailVerificationOtp = async (req, res) => {
  try {
    const { email } = req.body;
    const userId = req.user.id;

    // Validate input
    const validatedEmail = emailSchema.parse(email);

    // Send OTP
    const result = await emailVerificationService.sendEmailOtp(
      userId,
      validatedEmail,
    );

    logger.info("📧 Email verification OTP sent", {
      userId,
      email: validatedEmail.replace(/(.{2}).*(@.*)/, "$1***$2"),
    });

    return createSuccessResponse(res, result.data, result.message);
  } catch (error) {
    logger.error("❌ Send email OTP failed", {
      userId: req.user?.id,
      error: error,
    });
    return createErrorResponse(res, error, "sendEmailVerificationOtp");
  }
};

/**
 * Verify email OTP
 * @route POST /api/users/email/verify-otp
 */
const verifyEmailOtp = async (req, res) => {
  try {
    const { email, otp } = req.body;
    const userId = req.user.id;

    // Validate input
    const validatedEmail = emailSchema.parse(email);
    const validatedOtp = otpSchema.parse(otp);

    // Verify OTP
    const result = await emailVerificationService.verifyEmailOtp(
      userId,
      validatedEmail,
      validatedOtp,
    );

    logger.info("✅ Email verification successful", {
      userId,
      email: validatedEmail.replace(/(.{2}).*(@.*)/, "$1***$2"),
    });

    return createSuccessResponse(res, result.data, result.message);
  } catch (error) {
    logger.error("❌ Email verification failed", {
      userId: req.user?.id,
      error: error.message,
    });
    return res.status(error.statusCode || 400).json({
      success: false,
      error: {
        message: error.message,
        code: error.code || "VERIFY_OTP_ERROR",
      },
    });
  }
};

/**
 * Resend email verification OTP
 * @route POST /api/users/email/resend-otp
 */
const resendEmailVerificationOtp = async (req, res) => {
  try {
    const { email } = req.body;
    const userId = req.user.id;

    // Validate input
    const validatedEmail = emailSchema.parse(email);

    // Resend OTP
    const result = await emailVerificationService.resendEmailOtp(
      userId,
      validatedEmail,
    );

    logger.info("🔄 Email verification OTP resent", {
      userId,
      email: validatedEmail.replace(/(.{2}).*(@.*)/, "$1***$2"),
    });

    return createSuccessResponse(res, result.data, result.message);
  } catch (error) {
    logger.error("❌ Resend email OTP failed", {
      userId: req.user?.id,
      error: error.message,
    });
    return res.status(error.statusCode || 500).json({
      success: false,
      error: {
        message: error.message,
        code: error.code || "RESEND_OTP_ERROR",
      },
    });
  }
};

/**
 * Check email verification status
 * @route GET /api/users/email/verification-status
 */
const checkEmailVerificationStatus = async (req, res) => {
  try {
    const { email } = req.query;

    if (!email) {
      return res.status(400).json({
        success: false,
        error: {
          message: "Email query parameter is required",
          code: "EMAIL_REQUIRED",
        },
      });
    }

    // Validate input
    const validatedEmail = emailSchema.parse(email);

    // Check status
    const result =
      await emailVerificationService.checkEmailVerificationStatus(
        validatedEmail,
      );

    return createSuccessResponse(res, result.data, result.message);
  } catch (error) {
    logger.error("❌ Check email verification status failed", {
      userId: req.user?.id,
      error: error.message,
    });
    return res.status(error.statusCode || 500).json({
      success: false,
      error: {
        message: error.message,
        code: error.code || "CHECK_STATUS_ERROR",
      },
    });
  }
};

module.exports = {
  sendEmailVerificationOtp,
  verifyEmailOtp,
  resendEmailVerificationOtp,
  checkEmailVerificationStatus,
};
