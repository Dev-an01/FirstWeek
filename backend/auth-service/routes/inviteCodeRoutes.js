// backend/auth-service/routes/inviteCodeRoutes.js
const express = require("express");
const inviteCodeController = require("../controllers/inviteCodeController");
const {
    requireAuth,
    requireCompanyAdmin,
    requireSuperAdmin,
} = require("../middleware/authMiddleware");

const router = express.Router();

// Helper to create route groups with middleware
const createGroup = (middlewares = []) => {
    const group = express.Router();
    if (middlewares.length > 0) {
        group.use(...middlewares);
    }
    return group;
};

// Route groups by access level
const publicRoutes = express.Router();
const superAdminRoutes = createGroup([requireAuth, requireSuperAdmin]);
const companyAdminRoutes = createGroup([requireAuth, requireCompanyAdmin]);

// =============================================
// Public Routes (for registration validation)
// =============================================

/**
 * @swagger
 * /invite-codes/validate/{code}:
 *   get:
 *     tags: [Invite Codes]
 *     summary: Validate an invite code (public)
 *     parameters:
 *       - in: path
 *         name: code
 *         required: true
 *         schema:
 *           type: string
 *         description: The invite code to validate
 *     responses:
 *       200:
 *         description: Validation result with company info if valid
 */
publicRoutes.get("/validate/:code", inviteCodeController.validateInviteCode);

/**
 * @swagger
 * /invite-codes/redeem:
 *   post:
 *     tags: [Invite Codes]
 *     summary: Redeem an invite code to join a company (authenticated users)
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required:
 *               - code
 *             properties:
 *               code:
 *                 type: string
 *                 description: The invite code to redeem
 *     responses:
 *       200:
 *         description: Successfully joined company
 *       400:
 *         description: Invalid code or already assigned to company
 */
publicRoutes.post("/redeem", requireAuth, inviteCodeController.redeemInviteCode);


// =============================================
// COMPANY_ADMIN + SUPER_ADMIN routes
// =============================================

/**
 * @swagger
 * /invite-codes:
 *   post:
 *     tags: [Invite Codes]
 *     summary: Create an invite code
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
 *               companyId:
 *                 type: string
 *                 description: Required for SUPER_ADMIN, optional for COMPANY_ADMIN (defaults to their company)
 *               usageLimit:
 *                 type: integer
 *                 default: 1
 *                 example: 10
 *               expiresAt:
 *                 type: string
 *                 format: date-time
 *     responses:
 *       201:
 *         description: Invite code created successfully
 */
companyAdminRoutes.post("/", inviteCodeController.createInviteCode);

/**
 * @swagger
 * /invite-codes/company/{companyId}:
 *   get:
 *     tags: [Invite Codes]
 *     summary: List invite codes for a company
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: companyId
 *         required: true
 *         schema:
 *           type: string
 *       - in: query
 *         name: isActive
 *         schema:
 *           type: boolean
 *       - in: query
 *         name: page
 *         schema:
 *           type: integer
 *       - in: query
 *         name: limit
 *         schema:
 *           type: integer
 *     responses:
 *       200:
 *         description: Invite codes retrieved successfully
 */
companyAdminRoutes.get(
    "/company/:companyId",
    inviteCodeController.listInviteCodes
);

/**
 * @swagger
 * /invite-codes/{inviteCodeId}:
 *   get:
 *     tags: [Invite Codes]
 *     summary: Get invite code details
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: inviteCodeId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Invite code retrieved successfully
 */
companyAdminRoutes.get("/:inviteCodeId", inviteCodeController.getInviteCode);

/**
 * @swagger
 * /invite-codes/{inviteCodeId}/revoke:
 *   post:
 *     tags: [Invite Codes]
 *     summary: Revoke an invite code
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: inviteCodeId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Invite code revoked successfully
 */
companyAdminRoutes.post(
    "/:inviteCodeId/revoke",
    inviteCodeController.revokeInviteCode
);

// =============================================
// SUPER_ADMIN only routes
// =============================================

/**
 * @swagger
 * /invite-codes/{inviteCodeId}:
 *   delete:
 *     tags: [Invite Codes]
 *     summary: Delete an invite code (SUPER_ADMIN only)
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: inviteCodeId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Invite code deleted successfully
 */
superAdminRoutes.delete("/:inviteCodeId", inviteCodeController.deleteInviteCode);

// Mount route groups
router.use("/", publicRoutes);
router.use("/", companyAdminRoutes);
router.use("/", superAdminRoutes);

module.exports = router;
