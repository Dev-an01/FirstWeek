// backend/auth-service/controllers/companyController.js
const companyRepository = require("../repositories/companyRepository");
const onboardingService = require("../services/onboardingService");
const { createSuccessResponse, createErrorResponse } = require("../lib/utils");
const { createLogger } = require("../shared/utils/logger");
const { AuthorizationError, NotFoundError, ValidationError } = require("../shared/utils/errors");

const logger = createLogger("company-controller");

/**
 * Create a new company
 * SUPER_ADMIN only
 */
const createCompany = async (req, res) => {
    try {
        const { name, allowedDomains, description, website, phone, address } = req.body;

        logger.info("Creating new company", {
            name,
            allowedDomains,
            createdBy: req.user.id,
        });

        const company = await companyRepository.createCompany({
            name,
            allowedDomains: allowedDomains || [],
            description,
            website,
            phone,
            address,
        });

        logger.info("Company created successfully", {
            companyId: company.id,
            name: company.name,
            createdBy: req.user.id,
        });

        // Sync with Onboarding Service (Fire and forget)
        onboardingService.syncCreateCompany(company).catch(err => {
            logger.error("Async sync failed", { error: err.message });
        });

        return createSuccessResponse(
            res,
            { company },
            "Company created successfully",
            201
        );
    } catch (error) {
        logger.error("Failed to create company", {
            error: error.message,
            name: req.body.name,
            createdBy: req.user?.id,
        });
        return createErrorResponse(res, error, "createCompany");
    }
};

/**
 * Get company by ID
 * COMPANY_ADMIN (own company) or SUPER_ADMIN
 */
const getCompany = async (req, res) => {
    try {
        const { companyId } = req.params;

        // Access control: COMPANY_ADMIN can only view their own company
        if (
            req.user.role !== "SUPER_ADMIN" &&
            req.user.companyId !== companyId
        ) {
            throw AuthorizationError(
                "Access denied: you can only view your own company",
                "CROSS_COMPANY_ACCESS_DENIED"
            );
        }

        const company = await companyRepository.findById(companyId);

        if (!company) {
            throw NotFoundError("Company not found", "COMPANY_NOT_FOUND");
        }

        return createSuccessResponse(
            res,
            { company },
            "Company retrieved successfully"
        );
    } catch (error) {
        logger.error("Failed to get company", {
            error: error.message,
            companyId: req.params.companyId,
            requestedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "getCompany");
    }
};

/**
 * List all companies
 * SUPER_ADMIN only
 */
const listCompanies = async (req, res) => {
    try {
        const { isActive, page, limit } = req.query;

        logger.info("Listing companies", {
            isActive,
            page,
            limit,
            requestedBy: req.user.id,
        });

        const result = await companyRepository.listCompanies({
            isActive: isActive === "true" ? true : isActive === "false" ? false : undefined,
            page: parseInt(page) || 1,
            limit: parseInt(limit) || 20,
        });

        return createSuccessResponse(
            res,
            result,
            "Companies retrieved successfully"
        );
    } catch (error) {
        logger.error("Failed to list companies", {
            error: error.message,
            requestedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "listCompanies");
    }
};

/**
 * Update company
 * COMPANY_ADMIN (own company) or SUPER_ADMIN
 */
const updateCompany = async (req, res) => {
    try {
        const { companyId } = req.params;
        const { name, allowedDomains, isActive, description, website, phone, address } = req.body;

        // Access control: COMPANY_ADMIN can only update their own company
        if (
            req.user.role !== "SUPER_ADMIN" &&
            req.user.companyId !== companyId
        ) {
            throw AuthorizationError(
                "Access denied: you can only update your own company",
                "CROSS_COMPANY_ACCESS_DENIED"
            );
        }

        // COMPANY_ADMIN cannot change isActive (only SUPER_ADMIN can)
        const updateData = { name, allowedDomains, description, website, phone, address };
        if (req.user.role === "SUPER_ADMIN" && isActive !== undefined) {
            updateData.isActive = isActive;
        }

        // Filter out undefined values
        Object.keys(updateData).forEach(
            (key) => updateData[key] === undefined && delete updateData[key]
        );

        const company = await companyRepository.updateCompany(companyId, updateData);

        logger.info("Company updated successfully", {
            companyId,
            updatedFields: Object.keys(updateData),
            updatedBy: req.user.id,
        });

        return createSuccessResponse(
            res,
            { company },
            "Company updated successfully"
        );
    } catch (error) {
        logger.error("Failed to update company", {
            error: error.message,
            companyId: req.params.companyId,
            updatedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "updateCompany");
    }
};

/**
 * Delete company (soft delete)
 * SUPER_ADMIN only
 */
const deleteCompany = async (req, res) => {
    try {
        const { companyId } = req.params;

        logger.warn("Deleting company (soft delete)", {
            companyId,
            deletedBy: req.user.id,
        });

        const company = await companyRepository.deleteCompany(companyId);

        logger.info("Company deleted successfully", {
            companyId,
            deletedBy: req.user.id,
        });

        return createSuccessResponse(res, { company }, "Company deleted successfully");
    } catch (error) {
        logger.error("Failed to delete company", {
            error: error.message,
            companyId: req.params.companyId,
            deletedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "deleteCompany");
    }
};

/**
 * Get company users
 * COMPANY_ADMIN (own company) or SUPER_ADMIN
 */
const getCompanyUsers = async (req, res) => {
    try {
        const { companyId } = req.params;
        const { isCompanyVerified, role, page, limit } = req.query;

        // Access control: COMPANY_ADMIN can only view their own company's users
        if (
            req.user.role !== "SUPER_ADMIN" &&
            req.user.companyId !== companyId
        ) {
            throw AuthorizationError(
                "Access denied: you can only view your own company's users",
                "CROSS_COMPANY_ACCESS_DENIED"
            );
        }

        const result = await companyRepository.getCompanyUsers(companyId, {
            isCompanyVerified:
                isCompanyVerified === "true"
                    ? true
                    : isCompanyVerified === "false"
                        ? false
                        : undefined,
            role,
            page: parseInt(page) || 1,
            limit: parseInt(limit) || 20,
        });

        return createSuccessResponse(
            res,
            result,
            "Company users retrieved successfully"
        );
    } catch (error) {
        logger.error("Failed to get company users", {
            error: error.message,
            companyId: req.params.companyId,
            requestedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "getCompanyUsers");
    }
};

/**
 * Get pending approvals for a company
 * COMPANY_ADMIN (own company) or SUPER_ADMIN
 */
const getPendingApprovals = async (req, res) => {
    try {
        const { companyId } = req.params;

        // Access control
        if (
            req.user.role !== "SUPER_ADMIN" &&
            req.user.companyId !== companyId
        ) {
            throw AuthorizationError(
                "Access denied: you can only view your own company's pending approvals",
                "CROSS_COMPANY_ACCESS_DENIED"
            );
        }

        const pendingUsers = await companyRepository.getPendingApprovals(companyId);

        logger.info("Found pending users", {
            companyId,
            count: pendingUsers.length,
            users: pendingUsers.map(u => u.email),
        });

        return createSuccessResponse(
            res,
            { users: pendingUsers, count: pendingUsers.length },
            "Pending approvals retrieved successfully"
        );
    } catch (error) {
        logger.error("Failed to get pending approvals", {
            error: error.message,
            companyId: req.params.companyId,
            requestedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "getPendingApprovals");
    }
};

/**
 * Verify a user's company membership
 * COMPANY_ADMIN (own company) or SUPER_ADMIN
 */
const verifyUser = async (req, res) => {
    try {
        const { companyId, userId } = req.params;

        // Access control
        if (
            req.user.role !== "SUPER_ADMIN" &&
            req.user.companyId !== companyId
        ) {
            throw AuthorizationError(
                "Access denied: you can only verify users in your own company",
                "CROSS_COMPANY_ACCESS_DENIED"
            );
        }

        logger.info("Verifying user's company membership", {
            targetUserId: userId,
            companyId,
            verifiedBy: req.user.id,
        });

        const user = await companyRepository.verifyUser(userId, req.user.id);

        logger.auth("USER_VERIFIED", "User company membership verified", {
            targetUserId: userId,
            companyId,
            verifiedBy: req.user.id,
        });

        return createSuccessResponse(
            res,
            { user },
            "User verified successfully"
        );
    } catch (error) {
        logger.error("Failed to verify user", {
            error: error.message,
            targetUserId: req.params.userId,
            companyId: req.params.companyId,
            verifiedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "verifyUser");
    }
};

/**
 * Assign a user as COMPANY_ADMIN
 * SUPER_ADMIN only
 */
const assignCompanyAdmin = async (req, res) => {
    try {
        const { companyId, userId } = req.params;

        logger.info("Assigning user as COMPANY_ADMIN", {
            targetUserId: userId,
            companyId,
            assignedBy: req.user.id,
        });

        // First assign user to company and verify them
        await companyRepository.assignUserToCompany(userId, companyId, true);

        // Then update their role to COMPANY_ADMIN
        const { getDatabase } = require("../config/database");
        const db = await getDatabase();
        const user = await db.user.update({
            where: { id: userId },
            data: { role: "COMPANY_ADMIN" },
        });

        logger.auth("COMPANY_ADMIN_ASSIGNED", "User assigned as COMPANY_ADMIN", {
            targetUserId: userId,
            companyId,
            assignedBy: req.user.id,
        });

        return createSuccessResponse(
            res,
            { user },
            "User assigned as company admin successfully"
        );
    } catch (error) {
        logger.error("Failed to assign company admin", {
            error: error.message,
            targetUserId: req.params.userId,
            companyId: req.params.companyId,
            assignedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "assignCompanyAdmin");
    }
};

/**
 * Add an existing user to a company
 * COMPANY_ADMIN (own company) or SUPER_ADMIN
 * POST /companies/:companyId/users
 */
const addUserToCompany = async (req, res) => {
    try {
        const { companyId } = req.params;
        const { identifier } = req.body; // email or username
        const userRole = req.user?.role;
        const userCompanyId = req.user?.companyId;

        if (!identifier) {
            throw new Error("Email or username is required");
        }

        // Authorization check
        if (userRole === "COMPANY_ADMIN" && userCompanyId !== companyId) {
            throw AuthorizationError("You can only add users to your own company");
        }

        // Import userRepository
        const userRepository = require("../repositories/userRepository");

        // Find the target user
        const targetUser = await userRepository.findUser(identifier, false, true);
        if (!targetUser) {
            throw NotFoundError("User not found with email or username: " + identifier);
        }

        // Check if user is already assigned to a company
        if (targetUser.companyId) {
            throw new Error("User is already assigned to a company");
        }

        // Verify company exists
        const company = await companyRepository.findById(companyId);
        if (!company) {
            throw NotFoundError("Company not found");
        }

        // Assign user to company with EMPLOYEE role
        const updatedUser = await userRepository.assignToCompany(
            targetUser.id,
            companyId,
            "EMPLOYEE",
            true
        );

        logger.info("User added to company", {
            targetUserId: targetUser.id,
            targetEmail: targetUser.email,
            companyId,
            companyName: company.name,
            addedBy: req.user?.id,
        });

        return createSuccessResponse(
            res,
            { user: updatedUser },
            "User added to company successfully"
        );
    } catch (error) {
        logger.error("Failed to add user to company", {
            error: error.message,
            identifier: req.body?.identifier,
            companyId: req.params.companyId,
            addedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "addUserToCompany");
    }
};

/**
 * Revoke COMPANY_ADMIN privileges from a user
 * SUPER_ADMIN only - demotes user back to EMPLOYEE
 * DELETE /companies/:companyId/admins/:userId
 */
const revokeCompanyAdmin = async (req, res) => {
    try {
        const { companyId, userId } = req.params;

        logger.info("Revoking COMPANY_ADMIN privileges", {
            targetUserId: userId,
            companyId,
            revokedBy: req.user.id,
        });

        // Verify user exists and is a COMPANY_ADMIN of this company
        const { getDatabase } = require("../config/database");
        const db = await getDatabase();

        const targetUser = await db.user.findUnique({
            where: { id: userId },
            select: { id: true, role: true, companyId: true, email: true },
        });

        if (!targetUser) {
            throw NotFoundError("User not found");
        }

        if (targetUser.companyId !== companyId) {
            throw new Error("User does not belong to this company");
        }

        if (targetUser.role !== "COMPANY_ADMIN") {
            throw new Error("User is not a COMPANY_ADMIN");
        }

        // Demote user to EMPLOYEE
        const updatedUser = await db.user.update({
            where: { id: userId },
            data: { role: "EMPLOYEE" },
        });

        logger.auth("COMPANY_ADMIN_REVOKED", "COMPANY_ADMIN privileges revoked", {
            targetUserId: userId,
            targetEmail: targetUser.email,
            companyId,
            revokedBy: req.user.id,
        });

        return createSuccessResponse(
            res,
            { user: updatedUser },
            "Admin privileges revoked successfully. User is now an EMPLOYEE."
        );
    } catch (error) {
        logger.error("Failed to revoke company admin", {
            error: error.message,
            targetUserId: req.params.userId,
            companyId: req.params.companyId,
            revokedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "revokeCompanyAdmin");
    }
};


/**
 * Update a user's role within the company
 * COMPANY_ADMIN can only promote/demote between EMPLOYEE, EXECUTIVE, GUEST
 * PUT /companies/:companyId/users/:userId/role
 */
const updateCompanyUserRole = async (req, res) => {
    try {
        const { companyId, userId } = req.params;
        const { role, title } = req.body;

        // At least one field must be provided
        if (!role && title === undefined) {
            throw ValidationError(
                "At least role or title must be provided",
                "MISSING_UPDATE_DATA"
            );
        }

        // Validate role if provided
        if (role) {
            const ALLOWED_ROLES = ["EMPLOYEE", "EXECUTIVE", "GUEST"];
            if (!ALLOWED_ROLES.includes(role)) {
                throw ValidationError(
                    `Invalid role. Allowed roles: ${ALLOWED_ROLES.join(", ")}`,
                    "INVALID_ROLE"
                );
            }
        }

        const userRepository = require("../repositories/userRepository");
        const targetUser = await userRepository.findUser({ id: userId });

        if (!targetUser) {
            throw NotFoundError("User not found", "USER_NOT_FOUND");
        }

        if (targetUser.companyId !== companyId) {
            throw AuthorizationError(
                "User does not belong to this company",
                "USER_NOT_IN_COMPANY"
            );
        }

        // Prevent modifying admins
        if (["COMPANY_ADMIN", "SUPER_ADMIN"].includes(targetUser.role)) {
            throw AuthorizationError(
                "Cannot modify administrative roles. Contact Super Admin.",
                "ADMIN_ROLE_MODIFICATION_FORBIDDEN"
            );
        }

        let updatedUser;

        // Update role if provided
        if (role) {
            updatedUser = await userRepository.updateUserRole(userId, role);
        }

        // Update title if provided
        if (title !== undefined) {
            updatedUser = await userRepository.updateUser(userId, { title: title || null });
        }

        const previousRole = targetUser.role;
        const effectiveRole = role || previousRole;

        logger.info("Company user updated", {
            companyId,
            targetUserId: userId,
            newRole: role,
            newTitle: title,
            updatedBy: req.user.id,
        });

        // Sync to Onboarding Service based on role transition
        if (role && previousRole !== "EXECUTIVE" && role === "EXECUTIVE") {
            // Newly promoted to EXECUTIVE — create executive record
            onboardingService.syncCreateExecutive(updatedUser, companyId).catch(err => {
                logger.error("Async executive create sync failed", { error: err.message, userId: updatedUser.id });
            });
        } else if (effectiveRole === "EXECUTIVE" && title !== undefined) {
            // Already an EXECUTIVE and title changed — update existing record
            onboardingService.syncUpdateExecutive(updatedUser, companyId).catch(err => {
                logger.error("Async executive update sync failed", { error: err.message, userId: updatedUser.id });
            });
        }

        return createSuccessResponse(
            res,
            { user: updatedUser },
            "User updated successfully"
        );
    } catch (error) {
        logger.error("Failed to update company user", {
            error: error.message,
            companyId: req.params.companyId,
            targetUserId: req.params.userId,
            updatedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "updateCompanyUserRole");
    }
};

module.exports = {
    createCompany,
    getCompany,
    listCompanies,
    updateCompany,
    deleteCompany,
    getCompanyUsers,
    getPendingApprovals,
    verifyUser,
    assignCompanyAdmin,
    addUserToCompany,
    revokeCompanyAdmin,
    updateCompanyUserRole,
};
