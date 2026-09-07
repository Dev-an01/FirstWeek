// backend/auth-service/controllers/inviteCodeController.js
const inviteCodeRepository = require("../repositories/inviteCodeRepository");
const companyRepository = require("../repositories/companyRepository");
const { createSuccessResponse, createErrorResponse } = require("../lib/utils");
const { createLogger } = require("../shared/utils/logger");
const { AuthorizationError, NotFoundError, ValidationError } = require("../shared/utils/errors");

const logger = createLogger("invite-code-controller");

/**
 * Create a new invite code
 * COMPANY_ADMIN (own company) or SUPER_ADMIN
 */
const createInviteCode = async (req, res) => {
    try {
        const { companyId, usageLimit, expiresAt } = req.body;

        // Determine which company to create code for
        const targetCompanyId = req.user.role === "SUPER_ADMIN"
            ? companyId
            : req.user.companyId;

        if (!targetCompanyId) {
            throw ValidationError("Company ID is required", "COMPANY_ID_REQUIRED");
        }

        // Verify company exists
        const company = await companyRepository.findById(targetCompanyId);
        if (!company) {
            throw NotFoundError("Company not found", "COMPANY_NOT_FOUND");
        }

        // Access control: COMPANY_ADMIN can only create codes for their company
        if (
            req.user.role !== "SUPER_ADMIN" &&
            req.user.companyId !== targetCompanyId
        ) {
            throw AuthorizationError(
                "Access denied: you can only create invite codes for your own company",
                "CROSS_COMPANY_ACCESS_DENIED"
            );
        }

        logger.info("Creating invite code", {
            companyId: targetCompanyId,
            usageLimit,
            expiresAt,
            createdBy: req.user.id,
        });

        const inviteCode = await inviteCodeRepository.createInviteCode({
            companyId: targetCompanyId,
            createdBy: req.user.id,
            usageLimit: usageLimit || 1,
            expiresAt: expiresAt ? new Date(expiresAt) : null,
        });

        logger.info("Invite code created successfully", {
            inviteCodeId: inviteCode.id,
            code: inviteCode.code,
            companyId: targetCompanyId,
            createdBy: req.user.id,
        });

        return createSuccessResponse(
            res,
            { inviteCode },
            "Invite code created successfully",
            201
        );
    } catch (error) {
        logger.error("Failed to create invite code", {
            error: error.message,
            companyId: req.body.companyId,
            createdBy: req.user?.id,
        });
        return createErrorResponse(res, error, "createInviteCode");
    }
};

/**
 * Validate an invite code (public - used during registration)
 */
const validateInviteCode = async (req, res) => {
    try {
        const { code } = req.params;

        logger.debug("Validating invite code", { code });

        const result = await inviteCodeRepository.validateCode(code);

        if (!result.valid) {
            return createSuccessResponse(
                res,
                { valid: false, error: result.error },
                result.message
            );
        }

        // Return company info but not full invite code details
        return createSuccessResponse(
            res,
            {
                valid: true,
                company: {
                    id: result.company.id,
                    name: result.company.name,
                },
            },
            "Invite code is valid"
        );
    } catch (error) {
        logger.error("Failed to validate invite code", {
            error: error.message,
            code: req.params.code,
        });
        return createErrorResponse(res, error, "validateInviteCode");
    }
};

/**
 * List invite codes for a company
 * COMPANY_ADMIN (own company) or SUPER_ADMIN
 */
const listInviteCodes = async (req, res) => {
    try {
        const { companyId } = req.params;
        const { isActive, page, limit } = req.query;

        // Access control
        if (
            req.user.role !== "SUPER_ADMIN" &&
            req.user.companyId !== companyId
        ) {
            throw AuthorizationError(
                "Access denied: you can only view your own company's invite codes",
                "CROSS_COMPANY_ACCESS_DENIED"
            );
        }

        const result = await inviteCodeRepository.listByCompany(companyId, {
            isActive: isActive === "true" ? true : isActive === "false" ? false : undefined,
            page: parseInt(page) || 1,
            limit: parseInt(limit) || 20,
        });

        return createSuccessResponse(
            res,
            result,
            "Invite codes retrieved successfully"
        );
    } catch (error) {
        logger.error("Failed to list invite codes", {
            error: error.message,
            companyId: req.params.companyId,
            requestedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "listInviteCodes");
    }
};

/**
 * Get invite code by ID
 * COMPANY_ADMIN (own company) or SUPER_ADMIN
 */
const getInviteCode = async (req, res) => {
    try {
        const { inviteCodeId } = req.params;

        const inviteCode = await inviteCodeRepository.findById(inviteCodeId);

        if (!inviteCode) {
            throw NotFoundError("Invite code not found", "INVITE_CODE_NOT_FOUND");
        }

        // Access control
        if (
            req.user.role !== "SUPER_ADMIN" &&
            req.user.companyId !== inviteCode.companyId
        ) {
            throw AuthorizationError(
                "Access denied: you can only view your own company's invite codes",
                "CROSS_COMPANY_ACCESS_DENIED"
            );
        }

        return createSuccessResponse(
            res,
            { inviteCode },
            "Invite code retrieved successfully"
        );
    } catch (error) {
        logger.error("Failed to get invite code", {
            error: error.message,
            inviteCodeId: req.params.inviteCodeId,
            requestedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "getInviteCode");
    }
};

/**
 * Revoke an invite code
 * COMPANY_ADMIN (own company) or SUPER_ADMIN
 */
const revokeInviteCode = async (req, res) => {
    try {
        const { inviteCodeId } = req.params;

        const inviteCode = await inviteCodeRepository.findById(inviteCodeId);

        if (!inviteCode) {
            throw NotFoundError("Invite code not found", "INVITE_CODE_NOT_FOUND");
        }

        // Access control
        if (
            req.user.role !== "SUPER_ADMIN" &&
            req.user.companyId !== inviteCode.companyId
        ) {
            throw AuthorizationError(
                "Access denied: you can only revoke your own company's invite codes",
                "CROSS_COMPANY_ACCESS_DENIED"
            );
        }

        logger.info("Revoking invite code", {
            inviteCodeId,
            code: inviteCode.code,
            revokedBy: req.user.id,
        });

        const updatedCode = await inviteCodeRepository.revokeInviteCode(inviteCodeId);

        logger.info("Invite code revoked successfully", {
            inviteCodeId,
            revokedBy: req.user.id,
        });

        return createSuccessResponse(
            res,
            { inviteCode: updatedCode },
            "Invite code revoked successfully"
        );
    } catch (error) {
        logger.error("Failed to revoke invite code", {
            error: error.message,
            inviteCodeId: req.params.inviteCodeId,
            revokedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "revokeInviteCode");
    }
};

/**
 * Delete an invite code
 * SUPER_ADMIN only
 */
const deleteInviteCode = async (req, res) => {
    try {
        const { inviteCodeId } = req.params;

        const inviteCode = await inviteCodeRepository.findById(inviteCodeId);

        if (!inviteCode) {
            throw NotFoundError("Invite code not found", "INVITE_CODE_NOT_FOUND");
        }

        logger.warn("Deleting invite code", {
            inviteCodeId,
            code: inviteCode.code,
            deletedBy: req.user.id,
        });

        await inviteCodeRepository.deleteInviteCode(inviteCodeId);

        logger.info("Invite code deleted successfully", {
            inviteCodeId,
            deletedBy: req.user.id,
        });

        return createSuccessResponse(res, {}, "Invite code deleted successfully");
    } catch (error) {
        logger.error("Failed to delete invite code", {
            error: error.message,
            inviteCodeId: req.params.inviteCodeId,
            deletedBy: req.user?.id,
        });
        return createErrorResponse(res, error, "deleteInviteCode");
    }
};

/**
 * Redeem an invite code (authenticated users only)
 * Allows GUEST users to join a company and become EMPLOYEE
 * POST /api/invite-codes/redeem
 */
const redeemInviteCode = async (req, res) => {
    try {
        const { code } = req.body;
        const userId = req.user?.id;
        const currentRole = req.user?.role;

        if (!code) {
            throw ValidationError("Invite code is required");
        }

        if (!userId) {
            throw AuthorizationError("Authentication required");
        }

        // Check if user already belongs to a company
        if (req.user?.companyId) {
            throw ValidationError("You are already assigned to a company");
        }

        // Validate the invite code
        const validation = await inviteCodeRepository.validateCode(code);
        if (!validation.valid) {
            throw ValidationError(validation.message || "Invalid invite code");
        }

        const { company } = validation;

        // Import userRepository here to avoid circular dependencies
        const userRepository = require("../repositories/userRepository");

        // Assign user to company with EMPLOYEE role
        const updatedUser = await userRepository.assignToCompany(
            userId,
            company.id,
            "EMPLOYEE",
            true
        );

        // Increment invite code usage
        await inviteCodeRepository.useInviteCode(code);

        logger.info("User redeemed invite code", {
            userId,
            previousRole: currentRole,
            newRole: "EMPLOYEE",
            companyId: company.id,
            companyName: company.name,
            inviteCode: code,
        });

        return createSuccessResponse(
            res,
            {
                user: updatedUser,
                company: {
                    id: company.id,
                    name: company.name,
                },
            },
            "Successfully joined company"
        );
    } catch (error) {
        logger.error("Failed to redeem invite code", {
            error: error.message,
            userId: req.user?.id,
        });
        return createErrorResponse(res, error, "redeemInviteCode");
    }
};

module.exports = {
    createInviteCode,
    validateInviteCode,
    listInviteCodes,
    getInviteCode,
    revokeInviteCode,
    deleteInviteCode,
    redeemInviteCode,
};
