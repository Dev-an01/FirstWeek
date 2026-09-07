// auth-service/services/passwordResetService.js
const crypto = require("crypto");
const bcrypt = require("bcryptjs");
const nodemailer = require("nodemailer");
const passwordResetRepository = require("../repositories/passwordResetRepository");
const userRepository = require("../repositories/userRepository");
const emailVerificationRepository = require("../repositories/emailRepository");
const {
  ValidationError,
  BusinessLogicError,
  // eslint-disable-next-line
} = require('../shared/utils/errors');
const {
  passwordResetRequestSchema,
  passwordResetSchema,
} = require("../models/userSchema");

const {
  createLogger,
  // eslint-disable-next-line
} = require('../shared/utils/logger');

const { GMAIL_CONFIG } = require("../lib/constants");

const logger = createLogger("password-reset-service");

/**
 * Validate password strength
 * @param {string} password - Password to validate
 * @returns {Object} Validation result
 */
const validatePasswordStrength = (password) => {
  const requirements = {
    length: /.{8,}/,
    uppercase: /[A-Z]/,
    lowercase: /[a-z]/,
    number: /[0-9]/,
    special: /[@$!%*?&]/,
  };

  const errors = [];
  const passed = [];

  if (!requirements.length.test(password)) {
    errors.push("Password must be at least 8 characters long");
  } else {
    passed.push("length");
  }

  if (!requirements.uppercase.test(password)) {
    errors.push("Password must contain at least one uppercase letter");
  } else {
    passed.push("uppercase");
  }

  if (!requirements.lowercase.test(password)) {
    errors.push("Password must contain at least one lowercase letter");
  } else {
    passed.push("lowercase");
  }

  if (!requirements.number.test(password)) {
    errors.push("Password must contain at least one number");
  } else {
    passed.push("number");
  }

  if (!requirements.special.test(password)) {
    errors.push(
      "Password must contain at least one special character (@$!%*?&)",
    );
  } else {
    passed.push("special");
  }

  return {
    isValid: errors.length === 0,
    errors,
    passed,
    strength: passed.length,
  };
};

/**
 * Generate a secure reset token
 * @returns {string} Generated token
 */
const generateResetToken = () => {
  return crypto.randomBytes(32).toString("hex");
};

/**
 * Generate password reset link
 * @param {string} token - Reset token
 * @returns {string} Reset link
 */
const generateResetLink = (token) => {
  const baseUrl = process.env.API_BASE_URL || "http://localhost:3001";
  return `${baseUrl}/reset-password?token=${token}`;
};

/**
 * Send password reset email
 * @param {string} email - User email
 * @param {string} resetLink - Password reset link
 * @param {Object} user - User information
 * @returns {Promise<Object>} Email send result
 */
const sendPasswordResetEmail = async (email, resetLink, user) => {
  try {
    const transporter = nodemailer.createTransport({
      service: "gmail",
      host: "smtp.gmail.com",
      auth: GMAIL_CONFIG.auth,
      secure: true,
    });

    const result = await transporter.sendMail({
      from: `"FirstWeek" <${GMAIL_CONFIG.auth.user}>`,
      to: email,
      subject: "Reset Your Password - FirstWeek",
      html: `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Reset Your Password</title>
          <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #2563eb; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
            .content { background: #f8fafc; padding: 30px; border-radius: 0 0 8px 8px; }
            .button { display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }
            .footer { text-align: center; margin-top: 20px; font-size: 14px; color: #666; }
            .warning { background: #fef3c7; border: 1px solid #f59e0b; padding: 15px; border-radius: 6px; margin: 20px 0; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1>Reset Your Password</h1>
            </div>
            <div class="content">
              <p>Hello ${user.firstName || user.username},</p>
              
              <p>We received a request to reset the password for your FirstWeek account associated with <strong>${email}</strong>.</p>
              
              <p>Click the button below to reset your password:</p>
              
              <a href="${resetLink}" class="button">Reset Password</a>
              
              <p>Or copy and paste this link into your browser:</p>
              <p style="word-break: break-all; background: #e5e7eb; padding: 10px; border-radius: 4px;">${resetLink}</p>
              
              <div class="warning">
                <strong>Important:</strong>
                <ul>
                  <li>This link will expire in 1 hour for security reasons</li>
                  <li>If you didn't request this password reset, please ignore this email</li>
                  <li>Your password will remain unchanged until you create a new one</li>
                </ul>
              </div>
              
              <p>If you're having trouble with the button above, copy and paste the URL into your web browser.</p>
              
              <p>For security reasons, if you didn't request this password reset, please contact our support team immediately.</p>
              
              <p>Best regards,<br>The FirstWeek Team</p>
            </div>
            <div class="footer">
              <p>This is an automated message, please do not reply to this email.</p>
              <p>&copy; ${new Date().getFullYear()} FirstWeek. All rights reserved.</p>
            </div>
          </div>
        </body>
        </html>
      `,
      text: `
        Reset Your Password - FirstWeek
        
        Hello ${user.firstName || user.username},
        
        We received a request to reset the password for your FirstWeek account associated with ${email}.
        
        Copy and paste this link into your browser to reset your password:
        ${resetLink}
        
        Important:
        - This link will expire in 1 hour for security reasons
        - If you didn't request this password reset, please ignore this email
        - Your password will remain unchanged until you create a new one
        
        If you didn't request this password reset, please contact our support team immediately.
        
        Best regards,
        The FirstWeek Team
        
        This is an automated message, please do not reply to this email.
      `,
    });

    logger.info("Password reset email sent successfully", {
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      messageId: result.messageId,
    });

    return {
      success: true,
      messageId: result.messageId,
      email: email,
    };
  } catch (error) {
    logger.error("Failed to send password reset email", {
      error: error.message,
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
    });
    throw error;
  }
};

/**
 * Request password reset
 * @param {Object} requestData - Request data containing email
 * @param {Object} metadata - Request metadata (IP, user agent)
 * @returns {Promise<Object>} Password reset request result
 */
const requestPasswordReset = async (requestData, metadata = {}) => {
  try {
    // Validate input
    const { email } = passwordResetRequestSchema.parse(requestData);
    logger.info("Password reset requested", {
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      ip: metadata.ipAddress,
    });

    // Find user by email
    const user = await userRepository.findUser({ email });

    if (!user) {
      logger.warn("Password reset requested for non-existent email", {
        email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
        ip: metadata.ipAddress,
      });

      return {
        success: false,
        message: "No user exists with this email",
        email: email,
      };
    }

    if (!user.isActive) {
      throw BusinessLogicError(
        "Account is deactivated. Please contact support.",
        "ACCOUNT_DEACTIVATED",
      );
    }

    const status =
      await emailVerificationRepository.getVerificationStatus(email);
    if (!status.isVerified) {
      throw ValidationError("Email is not verified");
    }

    // Check if there's already an active reset request
    const existingReset =
      await passwordResetRepository.findActivePasswordResetByUserId(user.id);

    if (existingReset) {
      const timeRemaining = Math.ceil(
        (existingReset.expiresAt - new Date()) / (1000 * 60),
      );

      if (timeRemaining > 50) {
        // Allow new request only if less than 10 minutes remain
        throw BusinessLogicError(
          `A password reset link was already sent. Please check your email or wait ${timeRemaining} minutes before requesting again.`,
          "RESET_ALREADY_REQUESTED",
        );
      }
    }

    // Generate reset token and expiry
    const resetToken = generateResetToken();
    const expiresAt = new Date(Date.now() + 60 * 60 * 1000); // 1 hour

    // Create password reset record
    const resetRecord = await passwordResetRepository.createPasswordReset({
      userId: user.id,
      email: user.email,
      token: resetToken,
      expiresAt,
      ipAddress: metadata.ipAddress,
      userAgent: metadata.userAgent,
    });

    // Generate reset link
    const resetLink = generateResetLink(resetToken);

    // Send password reset email
    try {
      await sendPasswordResetEmail(user.email, resetLink, user);
    } catch (emailError) {
      // Log email error but don't fail the request
      logger.error(
        "Failed to send password reset email, but reset token created",
        {
          userId: user.id,
          resetId: resetRecord.id,
          emailError: emailError.message,
        },
      );
    }

    logger.info("Password reset request processed successfully", {
      userId: user.id,
      resetId: resetRecord.id,
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
    });

    return {
      success: true,
      message:
        "If an account with that email exists, a password reset link has been sent.",
      email: email,
      expiresAt: expiresAt,
    };
  } catch (error) {
    logger.error("Password reset request failed", {
      error: error.message,
      email: requestData?.email?.replace(/(.{2}).*(@.*)/, "$1***$2"),
      ip: metadata.ipAddress,
    });
    throw error;
  }
};

/**
 * Reset password using token
 * @param {Object} resetData - Reset data containing token and new password
 * @param {Object} metadata - Request metadata
 * @returns {Promise<Object>} Password reset result
 */
const resetPassword = async (resetData, metadata = {}) => {
  try {
    // Validate input
    const { token, newPassword, confirmPassword } =
      passwordResetSchema.parse(resetData);

    logger.info("Password reset attempt", {
      token: `${token?.substring(0, 8)}...`,
      ip: metadata.ipAddress,
    });

    // Validate password confirmation
    if (newPassword !== confirmPassword) {
      throw ValidationError(
        "Passwords do not match. Please ensure both password fields are identical.",
        "PASSWORD_MISMATCH",
      );
    }

    // Validate password strength
    const passwordValidation = validatePasswordStrength(newPassword);
    if (!passwordValidation.isValid) {
      throw ValidationError(
        `Password does not meet requirements: ${passwordValidation.errors.join(", ")}`,
        "WEAK_PASSWORD",
      );
    }

    // Find reset record by token
    const resetRecord =
      await passwordResetRepository.findPasswordResetByToken(token);

    if (!resetRecord) {
      throw ValidationError(
        "Invalid or expired reset token. Please request a new password reset.",
        "INVALID_RESET_TOKEN",
      );
    }

    // Check if too many attempts
    if (resetRecord.attempts >= 3) {
      throw ValidationError(
        "Too many reset attempts. Please request a new password reset.",
        "TOO_MANY_ATTEMPTS",
      );
    }

    // Verify user is still active
    if (!resetRecord.user.isActive) {
      throw BusinessLogicError(
        "Account is deactivated. Please contact support.",
        "ACCOUNT_DEACTIVATED",
      );
    }

    // Check if the new password is the same as the current password
    const currentPasswordValid = await bcrypt.compare(
      newPassword,
      resetRecord.user.password || "",
    );
    if (currentPasswordValid) {
      throw ValidationError(
        "New password cannot be the same as your current password. Please choose a different password.",
        "SAME_PASSWORD",
      );
    }

    // Hash the new password
    const saltRounds = 12;
    const hashedPassword = await bcrypt.hash(newPassword, saltRounds);

    // Update user password
    await userRepository.updateUserPassword(resetRecord.userId, hashedPassword);

    // Mark reset token as used
    await passwordResetRepository.markPasswordResetAsUsed(resetRecord.id);

    logger.info("Password reset completed successfully", {
      userId: resetRecord.userId,
      resetId: resetRecord.id,
      email: resetRecord.email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      ip: metadata.ipAddress,
    });

    return {
      success: true,
      message:
        "Password reset successfully! You can now log in with your new password.",
      userId: resetRecord.userId,
    };
  } catch (error) {
    // Increment attempts for validation errors (except for password mismatch which is client-side)
    if (error.code && error.code !== "PASSWORD_MISMATCH" && resetData?.token) {
      try {
        const resetRecord =
          await passwordResetRepository.findPasswordResetByToken(
            resetData.token,
          );
        if (resetRecord && resetRecord.attempts < 3) {
          await passwordResetRepository.incrementResetAttempts(resetRecord.id);
        }
      } catch (incrementError) {
        logger.error("Failed to increment reset attempts", {
          error: incrementError.message,
        });
      }
    }

    logger.error("Password reset failed", {
      error: error.message,
      errorCode: error.code,
      token: `${resetData?.token?.substring(0, 8)}...`,
      ip: metadata.ipAddress,
    });
    throw error;
  }
};

/**
 * Validate reset token
 * @param {string} token - Reset token
 * @returns {Promise<Object>} Token validation result
 */
const validateResetToken = async (token) => {
  try {
    if (!token) {
      throw ValidationError("Reset token is required");
    }

    const resetRecord =
      await passwordResetRepository.findPasswordResetByToken(token);

    if (!resetRecord) {
      return {
        valid: false,
        message: "Invalid or expired reset token",
      };
    }

    if (resetRecord.attempts >= 3) {
      return {
        valid: false,
        message: "Too many attempts. Please request a new password reset.",
      };
    }

    if (!resetRecord.user.isActive) {
      return {
        valid: false,
        message: "Account is deactivated. Please contact support.",
      };
    }

    const timeRemaining = Math.ceil(
      (resetRecord.expiresAt - new Date()) / (1000 * 60),
    );

    if (timeRemaining <= 0) {
      return {
        valid: false,
        message:
          "Reset token has expired. Please request a new password reset.",
      };
    }

    return {
      valid: true,
      message: "Valid reset token",
      expiresAt: resetRecord.expiresAt,
      timeRemaining: timeRemaining,
      user: {
        email: resetRecord.email,
        username: resetRecord.user.username,
        firstName: resetRecord.user.firstName,
        lastName: resetRecord.user.lastName,
      },
    };
  } catch (error) {
    logger.error("Reset token validation failed", {
      error: error.message,
      token: `${token?.substring(0, 8)}...`,
    });
    throw error;
  }
};

module.exports = {
  requestPasswordReset,
  resetPassword,
  validateResetToken,
  validatePasswordStrength,
  generateResetToken,
  generateResetLink,
  sendPasswordResetEmail,
};
