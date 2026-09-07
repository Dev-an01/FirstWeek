// backend/auth-service/routes/companyRoutes.js
const express = require("express");
const companyController = require("../controllers/companyController");
const {
    requireAuth,
    requireCompanyAdmin,
    requireSuperAdmin,
    requireCompanyVerified,
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
const superAdminRoutes = createGroup([requireAuth, requireSuperAdmin]);
const companyAdminRoutes = createGroup([requireAuth, requireCompanyAdmin]);
const companyMemberRoutes = createGroup([requireAuth, requireCompanyVerified]);

// =============================================
// SUPER_ADMIN only routes
// =============================================

/**
 * @swagger
 * /companies:
 *   post:
 *     tags: [Companies]
 *     summary: Create a new company (SUPER_ADMIN only)
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [name]
 *             properties:
 *               name:
 *                 type: string
 *                 example: "Acme Corporation"
 *               allowedDomains:
 *                 type: array
 *                 items:
 *                   type: string
 *                 example: ["acme.com", "acme.co.jp"]
 *     responses:
 *       201:
 *         description: Company created successfully
 *       403:
 *         description: Forbidden - SUPER_ADMIN access required
 */
superAdminRoutes.post("/", companyController.createCompany);

/**
 * @swagger
 * /companies:
 *   get:
 *     tags: [Companies]
 *     summary: List all companies (SUPER_ADMIN only)
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
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
 *         description: Companies retrieved successfully
 */
superAdminRoutes.get("/", companyController.listCompanies);

/**
 * @swagger
 * /companies/{companyId}:
 *   delete:
 *     tags: [Companies]
 *     summary: Delete company (SUPER_ADMIN only)
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: companyId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Company deleted successfully
 */
superAdminRoutes.delete("/:companyId", companyController.deleteCompany);

/**
 * @swagger
 * /companies/{companyId}/admins/{userId}:
 *   post:
 *     tags: [Companies]
 *     summary: Assign user as COMPANY_ADMIN (SUPER_ADMIN only)
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: companyId
 *         required: true
 *         schema:
 *           type: string
 *       - in: path
 *         name: userId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: User assigned as company admin
 */
superAdminRoutes.post(
    "/:companyId/admins/:userId",
    companyController.assignCompanyAdmin
);

/**
 * @swagger
 * /companies/{companyId}/admins/{userId}:
 *   delete:
 *     tags: [Companies]
 *     summary: Revoke COMPANY_ADMIN privileges (SUPER_ADMIN only)
 *     description: Demotes a COMPANY_ADMIN back to EMPLOYEE role
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: companyId
 *         required: true
 *         schema:
 *           type: string
 *       - in: path
 *         name: userId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Admin privileges revoked successfully
 */
superAdminRoutes.delete(
    "/:companyId/admins/:userId",
    companyController.revokeCompanyAdmin
);

// =============================================
// COMPANY_MEMBER routes (All employees + executives + admins)
// =============================================

/**
 * @swagger
 * /companies/{companyId}:
 *   get:
 *     tags: [Companies]
 *     summary: Get company details
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: companyId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Company retrieved successfully
 */
companyMemberRoutes.get("/:companyId", companyController.getCompany);

// =============================================
// COMPANY_ADMIN + SUPER_ADMIN routes
// =============================================

/**
 * @swagger
 * /companies/{companyId}:
 *   put:
 *     tags: [Companies]
 *     summary: Update company
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: companyId
 *         required: true
 *         schema:
 *           type: string
 *     requestBody:
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               name:
 *                 type: string
 *               allowedDomains:
 *                 type: array
 *                 items:
 *                   type: string
 *     responses:
 *       200:
 *         description: Company updated successfully
 */
companyAdminRoutes.put("/:companyId", companyController.updateCompany);

/**
 * @swagger
 * /companies/{companyId}/users:
 *   get:
 *     tags: [Companies]
 *     summary: Get company users
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
 *         name: isCompanyVerified
 *         schema:
 *           type: boolean
 *       - in: query
 *         name: role
 *         schema:
 *           type: string
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
 *         description: Company users retrieved successfully
 */
companyAdminRoutes.get("/:companyId/users", companyController.getCompanyUsers);

/**
 * @swagger
 * /companies/{companyId}/users:
 *   post:
 *     tags: [Companies]
 *     summary: Add an existing user to company
 *     description: COMPANY_ADMIN can add users without a company to their company
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: companyId
 *         required: true
 *         schema:
 *           type: string
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [identifier]
 *             properties:
 *               identifier:
 *                 type: string
 *                 description: Email or username of the user to add
 *     responses:
 *       200:
 *         description: User added to company successfully
 *       400:
 *         description: User is already assigned to a company
 *       404:
 *         description: User not found
 */
companyAdminRoutes.post("/:companyId/users", companyController.addUserToCompany);

/**
 * @swagger
 * /companies/{companyId}/users/{userId}/role:
 *   put:
 *     tags: [Companies]
 *     summary: Update user role in company
 *     description: COMPANY_ADMIN can update roles of their employees (EMPLOYEE, EXECUTIVE, GUEST)
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: companyId
 *         required: true
 *         schema:
 *           type: string
 *       - in: path
 *         name: userId
 *         required: true
 *         schema:
 *           type: string
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [role]
 *             properties:
 *               role:
 *                 type: string
 *                 enum: [EMPLOYEE, EXECUTIVE, GUEST]
 *     responses:
 *       200:
 *         description: User role updated successfully
 *       403:
 *         description: Forbidden - Cannot modify admin roles
 */
companyAdminRoutes.put(
    "/:companyId/users/:userId/role",
    companyController.updateCompanyUserRole
);


/**
 * @swagger
 * /companies/{companyId}/pending:
 *   get:
 *     tags: [Companies]
 *     summary: Get pending user approvals
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: companyId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Pending approvals retrieved
 */
companyAdminRoutes.get(
    "/:companyId/pending",
    companyController.getPendingApprovals
);

/**
 * @swagger
 * /companies/{companyId}/users/{userId}/verify:
 *   post:
 *     tags: [Companies]
 *     summary: Verify user's company membership
 *     security:
 *       - bearerAuth: []
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: companyId
 *         required: true
 *         schema:
 *           type: string
 *       - in: path
 *         name: userId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: User verified successfully
 */
companyAdminRoutes.post(
    "/:companyId/users/:userId/verify",
    companyController.verifyUser
);

// Mount route groups - more specific routes first
// companyAdminRoutes allows both COMPANY_ADMIN and SUPER_ADMIN
// superAdminRoutes is for SUPER_ADMIN-only operations
router.use("/", companyMemberRoutes);
router.use("/", companyAdminRoutes);
router.use("/", superAdminRoutes);

module.exports = router;
