// auth-service/services/emailVerificationService.js
const crypto = require("crypto");
const nodemailer = require("nodemailer");
const emailVerificationRepository = require("../repositories/emailRepository");
const userRepository = require("../repositories/userRepository");
const {
  ValidationError,
  ConflictError,
  // eslint-disable-next-line
} = require('../shared/utils/errors');
const {
  createLogger,
  // eslint-disable-next-line
} = require('../shared/utils/logger');
const { GMAIL_CONFIG } = require("../lib/constants");

const logger = createLogger("email-verification-service");
/**
 * Generate 6-digit OTP
 */
const generateOtp = () => {
  return Math.floor(100000 + Math.random() * 900000).toString();
};

/**
 * Generate verification token
 */
const generateToken = () => {
  return crypto.randomBytes(32).toString("hex");
};
/**
 * Send email with OTP (Enhanced with HTML template)
 */
const sendVerificationEmail = async (email, otp, userName = "User") => {
  try {
    logger.info("📧 Sending verification email", {
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"), // Mask email for security
      otp,
      userName,
    });

    const transporter = nodemailer.createTransport({
      service: "gmail",
      host: "smtp.gmail.com",
      auth: GMAIL_CONFIG.auth,
      secure: true,
    });

    const result = await transporter.sendMail({
      from: `"FirstWeek" <${GMAIL_CONFIG.auth.user}>`,
      to: email,
      subject: "Verify Your Email - FirstWeek",
      html: `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Verify Your Email</title>
          <style>
            * {
              margin: 0;
              padding: 0;
              box-sizing: border-box;
            }
            
            body { 
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
              line-height: 1.6; 
              color: #333; 
              background-color: #f8fafc;
              padding: 20px;
            }
            
            .email-container { 
              max-width: 600px; 
              margin: 0 auto; 
              background: #ffffff;
              border-radius: 12px;
              overflow: hidden;
              box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            }
            
            .header { 
              background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); 
              color: white; 
              padding: 40px 30px; 
              text-align: center; 
            }
            
            .header h1 {
              font-size: 28px;
              font-weight: 700;
              margin-bottom: 8px;
            }
            
            .header p {
              font-size: 16px;
              opacity: 0.9;
            }
            
            .content { 
              padding: 40px 30px;
              text-align: center;
            }
            
            .greeting {
              font-size: 18px;
              color: #374151;
              margin-bottom: 24px;
            }
            
            .message {
              font-size: 16px;
              color: #6b7280;
              margin-bottom: 32px;
              line-height: 1.6;
            }
            
            .otp-container {
              background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
              border: 2px solid #2563eb;
              border-radius: 12px;
              padding: 24px;
              margin: 32px 0;
              text-align: center;
            }
            
            .otp-label {
              font-size: 14px;
              color: #374151;
              font-weight: 600;
              margin-bottom: 8px;
              text-transform: uppercase;
              letter-spacing: 0.5px;
            }
            
            .otp-code {
              font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
              font-size: 32px;
              font-weight: bold;
              color: #2563eb;
              letter-spacing: 4px;
              margin: 12px 0;
              padding: 12px 24px;
              background: white;
              border-radius: 8px;
              border: 1px solid #e5e7eb;
              display: inline-block;
              min-width: 200px;
            }
            
            .otp-note {
              font-size: 14px;
              color: #6b7280;
              margin-top: 12px;
            }
            
            .instructions {
              background: #fef3c7;
              border: 1px solid #f59e0b;
              border-radius: 8px;
              padding: 20px;
              margin: 24px 0;
              text-align: left;
            }
            
            .instructions h3 {
              color: #92400e;
              font-size: 16px;
              margin-bottom: 12px;
              display: flex;
              align-items: center;
            }
            
            .instructions h3::before {
              content: "⚠️";
              margin-right: 8px;
            }
            
            .instructions ul {
              color: #92400e;
              font-size: 14px;
              padding-left: 20px;
            }
            
            .instructions li {
              margin-bottom: 6px;
            }
            
            .security-note {
              background: #f0fdf4;
              border: 1px solid #bbf7d0;
              border-radius: 8px;
              padding: 20px;
              margin: 24px 0;
              text-align: left;
            }
            
            .security-note h3 {
              color: #166534;
              font-size: 16px;
              margin-bottom: 12px;
              display: flex;
              align-items: center;
            }
            
            .security-note h3::before {
              content: "🔒";
              margin-right: 8px;
            }
            
            .security-note p {
              color: #166534;
              font-size: 14px;
              line-height: 1.5;
            }
            
            .footer { 
              background: #f8fafc;
              padding: 30px;
              text-align: center; 
              border-top: 1px solid #e5e7eb;
            }
            
            .footer p {
              font-size: 14px; 
              color: #6b7280;
              margin-bottom: 8px;
            }
            
            .footer a {
              color: #2563eb;
              text-decoration: none;
            }
            
            .footer a:hover {
              text-decoration: underline;
            }
            
            .social-links {
              margin-top: 20px;
            }
            
            .social-links a {
              display: inline-block;
              margin: 0 8px;
              color: #6b7280;
              text-decoration: none;
              font-size: 12px;
            }
            
            @media only screen and (max-width: 600px) {
              .email-container {
                margin: 0;
                border-radius: 0;
              }
              
              .header, .content, .footer {
                padding: 24px 20px;
              }
              
              .otp-code {
                font-size: 24px;
                letter-spacing: 2px;
                min-width: 160px;
              }
            }
          </style>
        </head>
        <body>
          <div class="email-container">
            <div class="header">
              <h1>FirstWeek</h1>
              <p>Email Verification Required</p>
            </div>
            
            <div class="content">
              <div class="greeting">
                Hello ${userName}! 👋
              </div>
              
              <div class="message">
                Thank you for signing up with <strong>FirstWeek</strong>! To complete your registration and secure your account, please verify your email address using the code below.
              </div>
              
              <div class="otp-container">
                <div class="otp-label">Your Verification Code</div>
                <div class="otp-code">${otp}</div>
                <div class="otp-note">This code will expire in 10 minutes</div>
              </div>
              
              <div class="instructions">
                <h3>How to verify:</h3>
                <ul>
                  <li>Copy the verification code above</li>
                  <li>Return to the FirstWeek registration page</li>
                  <li>Paste the code in the verification field</li>
                  <li>Click "Verify Email" to complete your registration</li>
                </ul>
              </div>
              
              <div class="security-note">
                <h3>Security Notice</h3>
                <p>
                  If you didn't create an account with FirstWeek, please ignore this email.
                  Your email address will not be used for anything, and no account will be created.
                  For security concerns, contact our support team immediately.
                </p>
              </div>
              
              <div class="message">
                Welcome to the FirstWeek family! We're excited to have you on board and can't wait for you to explore all the amazing features we have to offer.
              </div>
            </div>
            
            <div class="footer">
              <p><strong>FirstWeek</strong> - Your Creative Video Platform</p>
              <p>This is an automated message, please do not reply to this email.</p>
              <p>
                Need help? Contact us at 
                Contact your workspace administrator for help.
              </p>
              
              <div class="social-links">
                <a href="#">Privacy Policy</a> • 
                <a href="#">Terms of Service</a> • 
                <a href="#">Support</a>
              </div>
              
              <p style="margin-top: 20px; font-size: 12px;">
                &copy; ${new Date().getFullYear()} FirstWeek. All rights reserved.
              </p>
            </div>
          </div>
        </body>
        </html>
      `,
      text: `
        Welcome to FirstWeek!
        
        Hello ${userName},
        
        Thank you for signing up with FirstWeek! To complete your registration and secure your account, please verify your email address.
        
        Your Verification Code: ${otp}
        
        How to verify:
        1. Copy the verification code above
        2. Return to the FirstWeek registration page
        3. Paste the code in the verification field
        4. Click "Verify Email" to complete your registration
        
        Important Notes:
        - This code will expire in 10 minutes for security reasons
        - If you didn't create an account with FirstWeek, please ignore this email
        - For security concerns, contact our support team immediately
        
        Welcome to the FirstWeek family! We're excited to have you on board.
        
        Best regards,
        The FirstWeek Team
        
        ---
        FirstWeek - Your Creative Video Platform
        This is an automated message, please do not reply to this email.
        Need help? Contact your workspace administrator.
        
        © ${new Date().getFullYear()} FirstWeek. All rights reserved.
      `,
    });

    logger.info("✅ Verification email sent successfully", {
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      messageId: result.messageId,
    });

    return {
      success: true,
      message: "Verification email sent successfully",
      messageId: result.messageId,
      email: email,
    };
  } catch (error) {
    logger.error("❌ Failed to send verification email", {
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      error: error.message,
      stack: error.stack,
    });
    throw error;
  }
};
/**
 * Send OTP to email
 */
const sendEmailOtp = async (userId, email) => {
  try {
    // Check rate limiting
    const status =
      await emailVerificationRepository.getVerificationStatus(email);

    if (!status.canRetry) {
      if (status.isVerified) {
        throw ConflictError("Email is already verified");
      }
      throw ValidationError(
        "Too many attempts or verification expired. Please try again later.",
      );
    }

    // Generate OTP and token
    const otp = generateOtp();
    const token = "TMKC";
    const expiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes

    // Get user info for personalized email
    const user = await userRepository.findUser(userId);
    const userName = user ? `${user.firstName} ${user.lastName}` : "User";

    // Create verification record
    const verificationData = {
      userId,
      email,
      otp,
      token,
      expiresAt,
      isVerified: false,
      attempts: 0,
    };

    const verificationRecord =
      await emailVerificationRepository.createOrUpdateVerification(
        verificationData,
      );

    // Send email
    await sendVerificationEmail(email, otp, userName);

    logger.info("🚀 Email verification OTP sent", {
      userId,
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      expiresAt,
    });

    return {
      success: true,
      data: {
        expiresAt: verificationRecord.expiresAt,
        canRetry: true,
        attemptsRemaining: 5,
      },
      message: "Verification OTP sent successfully",
    };
  } catch (error) {
    logger.error("❌ Failed to send email OTP", {
      userId,
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      error: error.message,
    });
    throw error;
  }
};

/**
 * Verify email with OTP
 */
const verifyEmailOtp = async (userId, email, otp) => {
  try {
    // Verify OTP
    const verifiedRecord = await emailVerificationRepository.verifyOtp(
      email,
      otp,
    );

    if (verifiedRecord.userId !== userId) {
      throw ValidationError("OTP verification failed - user mismatch");
    }

    // Update user's email and verification status
    const result = await userRepository.updateEmailVerificationStatus(
      userId,
      true,
    );

    // If user has a company assigned (domain-matched), auto-verify company membership
    // since they've proven they own the email address
    const user = await userRepository.findUser(userId);
    if (user && user.companyId && !user.isCompanyVerified) {
      const { getDatabase } = require("../config/database");
      const db = await getDatabase();
      await db.user.update({
        where: { id: userId },
        data: {
          isCompanyVerified: true,
          verifiedAt: new Date(),
        },
      });
      logger.info("✅ Company membership auto-verified via email verification", {
        userId,
        companyId: user.companyId,
      });
    }

    logger.info("✅ User email updated", {
      userId,
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      updatedFields: Object.keys(result),
    });
    logger.info("✅ Email verified successfully", {
      userId,
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
    });

    return {
      success: true,
      data: {
        email: email,
        verifiedAt: new Date(),
      },
      message: "Email verified successfully",
    };
  } catch (error) {
    logger.error("❌ Email verification failed", {
      userId,
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      error: error.message,
    });
    throw error;
  }
};

/**
 * Resend verification OTP
 */
const resendEmailOtp = async (userId, email) => {
  try {
    return await sendEmailOtp(userId, email);
  } catch (error) {
    logger.error("❌ Failed to resend email OTP", {
      userId,
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      error: error.message,
    });
    throw error;
  }
};

/**
 * Check email verification status
 */
const checkEmailVerificationStatus = async (email) => {
  try {
    const status =
      await emailVerificationRepository.getVerificationStatus(email);

    return {
      success: true,
      data: {
        email: email,
        isVerified: status.isVerified,
        canRetry: status.canRetry,
        attemptsRemaining: Math.max(0, 5 - status.attempts),
        expiresAt: status.expiresAt,
      },
      message: "Email verification status retrieved successfully",
    };
  } catch (error) {
    logger.error("❌ Failed to check email verification status", {
      email: email.replace(/(.{2}).*(@.*)/, "$1***$2"),
      error: error.message,
    });
    throw error;
  }
};

module.exports = {
  sendEmailOtp,
  verifyEmailOtp,
  resendEmailOtp,
  checkEmailVerificationStatus,
  // Utility functions
  generateOtp,
  generateToken,
};
