// backend/services/auth-service/routes/userRoutes.js
const express = require("express");
const userController = require("../controllers/userController");
const emailController = require("../controllers/emailController");
const passwordResetController = require("../controllers/passwordResetController");
const {
  authenticateUser,
  validateRefreshToken,
  requireAuth,
  strictSessionValidation,
  requireAdmin,
} = require("../middleware/authMiddleware");

const router = express.Router();
const createGroup = (middlewares = []) => {
  const group = express.Router();
  if (middlewares.length > 0) {
    group.use(...middlewares);
  }
  return group;
};

const publicRoutes = express.Router();
const adminRoutes = createGroup([requireAuth, requireAdmin]);
const authRoutes = createGroup([requireAuth]);
const strictRoutes = createGroup([strictSessionValidation]);
// =============================================
// Admin Routes (EXECUTIVE role required)
// =============================================
/**
 * @swagger
 * /:
 *   get:
 *     tags: [Admin]
 *     summary: Get all users (Admin only)
 *     description: Retrieve list of all registered users
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: Users retrieved successfully
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 *       403:
 *         description: Forbidden - Admin access required
 */
adminRoutes.get("/", userController.getAllUsers);

/**
 * @swagger
 * /:{userId}/role:
 *   get:
 *     tags: [Admin]
 *     summary: Update user roles (Admin only)
 *     description: Update a user's role using their userId
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *         description: User Id
 *     responses:
 *       200:
 *         description: Role Updated Successfully
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 *       403:
 *         description: Forbidden - Admin access required
 */
adminRoutes.put("/:userId/role", userController.updateUserRole);

/**
 * @swagger
 * /register:
 *   post:
 *     tags: [Authentication]
 *     summary: Register new user
 *     description: Create a new user account with email and password
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [email, password, username, firstName, lastName]
 *             properties:
 *               email:
 *                 type: string
 *                 format: email
 *                 example: john@example.com
 *               password:
 *                 type: string
 *                 format: password
 *                 minLength: 8
 *                 example: SecurePass123!
 *               username:
 *                 type: string
 *                 example: john_doe
 *               firstName:
 *                 type: string
 *                 example: John
 *               lastName:
 *                 type: string
 *                 example: Doe
 *               role:
 *                 type: string
 *                 enum: [GUEST, EMPLOYEE, EXECUTIVE, COMPANY_ADMIN, SUPER_ADMIN]
 *                 default: EMPLOYEE
 *     responses:
 *       201:
 *         description: User registered successfully
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/User'
 *       400:
 *         $ref: '#/components/responses/ValidationError'
 */
publicRoutes.post("/register", userController.registerUser);

/**
 * @swagger
 * /login:
 *   post:
 *     tags: [Authentication]
 *     summary: Login user
 *     description: Authenticate user with email/username and password
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [identifier, password]
 *             properties:
 *               identifier:
 *                 type: string
 *                 example: john@example.com
 *                 description: Email or username
 *               password:
 *                 type: string
 *                 format: password
 *                 example: SecurePass123!
 *     responses:
 *       200:
 *         description: Login successful
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 user:
 *                   $ref: '#/components/schemas/User'
 *                 tokens:
 *                   type: object
 *                   properties:
 *                     accessToken:
 *                       type: string
 *                     refreshToken:
 *                       type: string
 *       401:
 *         description: Invalid credentials
 */
publicRoutes.post("/login", userController.loginUser);

/**
 * @swagger
 * /check-email:
 *   post:
 *     tags: [Authentication]
 *     summary: Check email availability
 *     description: Check if an email address is already registered
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [email]
 *             properties:
 *               email:
 *                 type: string
 *                 format: email
 *                 example: john@example.com
 *     responses:
 *       200:
 *         description: Email availability status
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 exists:
 *                   type: boolean
 */
publicRoutes.post("/check-email", userController.checkEmailExists);

/**
 * @swagger
 * /check-username:
 *   post:
 *     tags: [Authentication]
 *     summary: Check username availability
 *     description: Check if a username is already taken
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [username]
 *             properties:
 *               username:
 *                 type: string
 *                 example: john_doe
 *     responses:
 *       200:
 *         description: Username availability status
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 exists:
 *                   type: boolean
 */
publicRoutes.post("/check-username", userController.checkUsernameExists);

/**
 * @swagger
 * /password/forgot:
 *   post:
 *     tags: [Password Management]
 *     summary: Request password reset
 *     description: Send password reset email with token
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [email]
 *             properties:
 *               email:
 *                 type: string
 *                 format: email
 *                 example: john@example.com
 *     responses:
 *       200:
 *         description: Password reset email sent
 *       404:
 *         description: User not found
 */
publicRoutes.post(
  "/password/forgot",
  passwordResetController.requestPasswordReset,
);

/**
 * @swagger
 * /password/reset:
 *   post:
 *     tags: [Password Management]
 *     summary: Reset password
 *     description: Reset password using token from email
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [token, newPassword]
 *             properties:
 *               token:
 *                 type: string
 *                 example: abc123def456
 *               newPassword:
 *                 type: string
 *                 format: password
 *                 minLength: 8
 *                 example: NewSecurePass123!
 *     responses:
 *       200:
 *         description: Password reset successfully
 *       400:
 *         description: Invalid or expired token
 */
publicRoutes.post("/password/reset", passwordResetController.resetPassword);

/**
 * @swagger
 * /password/validate-token/{token}:
 *   get:
 *     tags: [Password Management]
 *     summary: Validate reset token
 *     description: Check if password reset token is valid
 *     parameters:
 *       - in: path
 *         name: token
 *         required: true
 *         schema:
 *           type: string
 *         description: Reset token from email
 *     responses:
 *       200:
 *         description: Token is valid
 *       400:
 *         description: Invalid or expired token
 */
publicRoutes.get(
  "/password/validate-token/:token",
  passwordResetController.validateResetToken,
);

// =============================================
// Protected Routes (Authentication Required)
// =============================================

/**
 * @swagger
 * /logout-all:
 *   post:
 *     tags: [Authentication]
 *     summary: Logout from all devices
 *     description: Revoke all active sessions for the current user
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: All sessions revoked successfully
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.post("/logout-all", userController.logoutAllDevices);

/**
 * @swagger
 * /me:
 *   get:
 *     tags: [User Profile]
 *     summary: Get current user profile
 *     description: Retrieve authenticated user's profile information
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: User profile retrieved
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/User'
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.get("/me", userController.getCurrentUserProfile);

/**
 * @swagger
 * /me:
 *   put:
 *     tags: [User Profile]
 *     summary: Update user profile
 *     description: Update authenticated user's profile information
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               firstName:
 *                 type: string
 *                 example: John
 *               lastName:
 *                 type: string
 *                 example: Doe
 *               username:
 *                 type: string
 *                 example: john_doe_updated
 *               profilePic:
 *                 type: string
 *                 format: uri
 *     responses:
 *       200:
 *         description: Profile updated successfully
 *       400:
 *         $ref: '#/components/responses/ValidationError'
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.put("/me", userController.updateUserProfile);

/**
 * @swagger
 * /change-password:
 *   put:
 *     tags: [Password Management]
 *     summary: Change password
 *     description: Change password for authenticated user
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [currentPassword, newPassword]
 *             properties:
 *               currentPassword:
 *                 type: string
 *                 format: password
 *                 example: OldPass123!
 *               newPassword:
 *                 type: string
 *                 format: password
 *                 minLength: 8
 *                 example: NewSecurePass123!
 *     responses:
 *       200:
 *         description: Password changed successfully
 *       400:
 *         description: Invalid current password
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.put("/change-password", userController.changePassword);

/**
 * @swagger
 * /validate-token:
 *   get:
 *     tags: [Authentication]
 *     summary: Validate JWT token
 *     description: Check if current JWT token is valid
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: Token is valid
 *       401:
 *         description: Token is invalid or expired
 */
publicRoutes.get(
  "/validate-token",
  authenticateUser,
  userController.validateToken,
);

/**
 * @swagger
 * /deactivate:
 *   put:
 *     tags: [User Profile]
 *     summary: Deactivate account
 *     description: Deactivate the current user's account
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: Account deactivated successfully
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.put("/deactivate", userController.deactivateAccount);

// =============================================
// Session Management Routes
// =============================================

/**
 * @swagger
 * /sessions:
 *   get:
 *     tags: [Sessions]
 *     summary: Get active sessions
 *     description: Retrieve all active sessions for the current user
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: Sessions retrieved successfully
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 data:
 *                   type: array
 *                   items:
 *                     $ref: '#/components/schemas/Session'
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.get("/sessions", userController.getUserSessions);

/**
 * @swagger
 * /sessions/{sessionId}:
 *   delete:
 *     tags: [Sessions]
 *     summary: Revoke session
 *     description: Revoke a specific session by ID
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: sessionId
 *         required: true
 *         schema:
 *           type: string
 *         description: Session ID to revoke
 *     responses:
 *       200:
 *         description: Session revoked successfully
 *       404:
 *         description: Session not found
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.delete("/sessions/:sessionId", userController.revokeSession);

/**
 * @swagger
 * /sessions/stats:
 *   get:
 *     tags: [Sessions]
 *     summary: Get session statistics
 *     description: Retrieve session statistics for the current user
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: Session stats retrieved successfully
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.get("/sessions/stats", userController.getUserSessionStats);

// =============================================
// Email Verification Routes
// =============================================

/**
 * @swagger
 * /email/send-otp:
 *   post:
 *     tags: [Email Verification]
 *     summary: Send email verification OTP
 *     description: Send OTP code to user's email for verification
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: OTP sent successfully
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.post("/email/send-otp", emailController.sendEmailVerificationOtp);

/**
 * @swagger
 * /email/verify-otp:
 *   post:
 *     tags: [Email Verification]
 *     summary: Verify email with OTP
 *     description: Verify user's email address using OTP code
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [otp]
 *             properties:
 *               otp:
 *                 type: string
 *                 example: "123456"
 *     responses:
 *       200:
 *         description: Email verified successfully
 *       400:
 *         description: Invalid or expired OTP
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.post("/email/verify-otp", emailController.verifyEmailOtp);

/**
 * @swagger
 * /email/resend-otp:
 *   post:
 *     tags: [Email Verification]
 *     summary: Resend verification OTP
 *     description: Resend OTP code if previous one expired
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: OTP resent successfully
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.post(
  "/email/resend-otp",
  emailController.resendEmailVerificationOtp,
);

/**
 * @swagger
 * /email/verification-status:
 *   get:
 *     tags: [Email Verification]
 *     summary: Check verification status
 *     description: Check if user's email is verified
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: Verification status retrieved
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 verified:
 *                   type: boolean
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
authRoutes.get(
  "/email/verification-status",
  emailController.checkEmailVerificationStatus,
);

/**
 * @swagger
 * /refresh:
 *   post:
 *     tags: [Authentication]
 *     summary: Refresh access token
 *     description: Get new access token using refresh token
 *     requestBody:
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               refreshToken:
 *                 type: string
 *                 description: Refresh token (also accepts from cookie)
 *     responses:
 *       200:
 *         description: New access token generated
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 accessToken:
 *                   type: string
 *       401:
 *         description: Invalid or expired refresh token
 */
publicRoutes.post(
  "/refresh",
  validateRefreshToken,
  userController.refreshToken,
);

/**
 * @swagger
 * /logout:
 *   post:
 *     tags: [Authentication]
 *     summary: Logout user
 *     description: End current session and clear cookies
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: Logout successful
 *       401:
 *         $ref: '#/components/responses/UnauthorizedError'
 */
publicRoutes.post("/logout", authenticateUser, userController.logoutUser);
router.use("/", publicRoutes);
router.use("/", authRoutes);
router.use("/", strictRoutes);
router.use("/", adminRoutes);
module.exports = router;
