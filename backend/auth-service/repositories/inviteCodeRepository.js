// backend/auth-service/repositories/inviteCodeRepository.js
const { getDatabase } = require("../config/database");
const crypto = require("crypto");

let dbInstance = null;

const getDB = async () => {
    if (!dbInstance) {
        dbInstance = await getDatabase();
    }
    return dbInstance;
};

/**
 * Invite Code Repository
 * Handles database operations for InviteCode model
 */

/**
 * Generate a random invite code
 * @returns {string} 8-character alphanumeric code
 */
const generateCode = () => {
    return crypto.randomBytes(4).toString("hex").toUpperCase();
};

/**
 * Create a new invite code
 * @param {Object} data - Invite code data
 * @returns {Promise<Object>} Created invite code
 */
const createInviteCode = async (data) => {
    const db = await getDB();
    const code = data.code || generateCode();

    return db.inviteCode.create({
        data: {
            code,
            companyId: data.companyId,
            createdById: data.createdBy,
            usageLimit: data.usageLimit || 1,
            expiresAt: data.expiresAt || null,
        },
        include: {
            company: {
                select: { id: true, name: true },
            },
        },
    });
};

/**
 * Find invite code by code string
 * @param {string} code - The invite code
 * @returns {Promise<Object|null>} Invite code or null
 */
const findByCode = async (code) => {
    const db = await getDB();
    return db.inviteCode.findUnique({
        where: { code },
        include: {
            company: {
                select: { id: true, name: true, isActive: true },
            },
        },
    });
};

/**
 * Find invite code by ID
 * @param {string} id - Invite code ID
 * @returns {Promise<Object|null>} Invite code or null
 */
const findById = async (id) => {
    const db = await getDB();
    return db.inviteCode.findUnique({
        where: { id },
        include: {
            company: {
                select: { id: true, name: true },
            },
        },
    });
};

/**
 * Validate an invite code (check if valid and usable)
 * @param {string} code - The invite code
 * @returns {Promise<Object>} Validation result with company info
 */
const validateCode = async (code) => {
    const inviteCode = await findByCode(code);

    if (!inviteCode) {
        return { valid: false, error: "INVALID_CODE", message: "Invalid invite code" };
    }

    if (!inviteCode.isActive) {
        return { valid: false, error: "CODE_INACTIVE", message: "Invite code is no longer active" };
    }

    if (!inviteCode.company.isActive) {
        return { valid: false, error: "COMPANY_INACTIVE", message: "Company is no longer active" };
    }

    if (inviteCode.expiresAt && new Date(inviteCode.expiresAt) < new Date()) {
        return { valid: false, error: "CODE_EXPIRED", message: "Invite code has expired" };
    }

    if (inviteCode.usageLimit > 0 && inviteCode.usageCount >= inviteCode.usageLimit) {
        return { valid: false, error: "CODE_EXHAUSTED", message: "Invite code has reached its usage limit" };
    }

    return {
        valid: true,
        inviteCode,
        company: inviteCode.company,
    };
};

/**
 * Use an invite code (increment usage count)
 * @param {string} code - The invite code
 * @returns {Promise<Object>} Updated invite code
 */
const useInviteCode = async (code) => {
    const db = await getDB();
    return db.inviteCode.update({
        where: { code },
        data: {
            usageCount: { increment: 1 },
        },
    });
};

/**
 * List invite codes for a company
 * @param {string} companyId - Company ID
 * @param {Object} options - Query options
 * @returns {Promise<Object>} Invite codes with pagination
 */
const listByCompany = async (companyId, options = {}) => {
    const { isActive, page = 1, limit = 20 } = options;
    const db = await getDB();

    const where = { companyId };
    if (isActive !== undefined) {
        where.isActive = isActive;
    }

    const [inviteCodes, total] = await Promise.all([
        db.inviteCode.findMany({
            where,
            skip: (page - 1) * limit,
            take: limit,
            orderBy: { createdAt: "desc" },
        }),
        db.inviteCode.count({ where }),
    ]);

    return {
        inviteCodes,
        pagination: {
            page,
            limit,
            total,
            pages: Math.ceil(total / limit),
        },
    };
};

/**
 * Revoke an invite code
 * @param {string} id - Invite code ID
 * @returns {Promise<Object>} Updated invite code
 */
const revokeInviteCode = async (id) => {
    const db = await getDB();
    return db.inviteCode.update({
        where: { id },
        data: { isActive: false },
    });
};

/**
 * Delete an invite code
 * @param {string} id - Invite code ID
 * @returns {Promise<Object>} Deleted invite code
 */
const deleteInviteCode = async (id) => {
    const db = await getDB();
    return db.inviteCode.delete({
        where: { id },
    });
};

module.exports = {
    generateCode,
    createInviteCode,
    findByCode,
    findById,
    validateCode,
    useInviteCode,
    listByCompany,
    revokeInviteCode,
    deleteInviteCode,
};
