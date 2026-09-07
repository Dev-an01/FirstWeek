// backend/auth-service/repositories/companyRepository.js
const { getDatabase } = require("../config/database");

let dbInstance = null;

const getDB = async () => {
    if (!dbInstance) {
        dbInstance = await getDatabase();
    }
    return dbInstance;
};

/**
 * Company Repository
 * Handles database operations for Company model
 */

/**
 * Create a new company
 * @param {Object} data - Company data
 * @returns {Promise<Object>} Created company
 */
const createCompany = async (data) => {
    const db = await getDB();
    return db.company.create({
        data: {
            name: data.name,
            allowedDomains: data.allowedDomains || [],
            isActive: data.isActive !== undefined ? data.isActive : true,
            description: data.description,
            website: data.website,
            phone: data.phone,
            address: data.address,
        },
    });
};

/**
 * Find company by ID
 * @param {string} id - Company ID
 * @returns {Promise<Object|null>} Company or null
 */
const findById = async (id) => {
    const db = await getDB();
    return db.company.findUnique({
        where: { id },
        include: {
            _count: {
                select: { users: true, inviteCodes: true },
            },
        },
    });
};

/**
 * Find company by allowed domain
 * @param {string} domain - Email domain (e.g., "company.com")
 * @returns {Promise<Object|null>} Company or null
 */
const findByDomain = async (domain) => {
    const db = await getDB();
    return db.company.findFirst({
        where: {
            allowedDomains: { has: domain },
            isActive: true,
        },
    });
};

/**
 * List all companies with optional filters
 * @param {Object} options - Query options
 * @returns {Promise<Object[]>} List of companies
 */
const listCompanies = async (options = {}) => {
    const { isActive, page = 1, limit = 20 } = options;
    const db = await getDB();

    const where = {};
    if (isActive !== undefined) {
        where.isActive = isActive;
    }

    const [companies, total] = await Promise.all([
        db.company.findMany({
            where,
            skip: (page - 1) * limit,
            take: limit,
            orderBy: { createdAt: "desc" },
            include: {
                _count: {
                    select: { users: true, inviteCodes: true },
                },
            },
        }),
        db.company.count({ where }),
    ]);

    return {
        companies,
        pagination: {
            page,
            limit,
            total,
            pages: Math.ceil(total / limit),
        },
    };
};

/**
 * Update company by ID
 * @param {string} id - Company ID
 * @param {Object} data - Update data
 * @returns {Promise<Object>} Updated company
 */
const updateCompany = async (id, data) => {
    const db = await getDB();
    return db.company.update({
        where: { id },
        data,
    });
};

/**
 * Delete company by ID (soft delete by setting isActive = false)
 * @param {string} id - Company ID
 * @returns {Promise<Object>} Updated company
 */
const deleteCompany = async (id) => {
    const db = await getDB();
    return db.company.update({
        where: { id },
        data: { isActive: false },
    });
};

/**
 * Get company users with filters
 * @param {string} companyId - Company ID
 * @param {Object} options - Query options
 * @returns {Promise<Object>} Users list with pagination
 */
const getCompanyUsers = async (companyId, options = {}) => {
    const { isCompanyVerified, role, page = 1, limit = 20 } = options;
    const db = await getDB();

    const where = { companyId };
    if (isCompanyVerified !== undefined) {
        where.isCompanyVerified = isCompanyVerified;
    }
    if (role) {
        where.role = role;
    }

    const [users, total] = await Promise.all([
        db.user.findMany({
            where,
            skip: (page - 1) * limit,
            take: limit,
            orderBy: { createdAt: "desc" },
            select: {
                id: true,
                username: true,
                email: true,
                firstName: true,
                lastName: true,
                title: true,
                role: true,
                isCompanyVerified: true,
                verifiedAt: true,
                isActive: true,
                createdAt: true,
            },
        }),
        db.user.count({ where }),
    ]);

    return {
        users,
        pagination: {
            page,
            limit,
            total,
            pages: Math.ceil(total / limit),
        },
    };
};

/**
 * Get pending approval users for a company
 * @param {string} companyId - Company ID
 * @returns {Promise<Object[]>} Pending users
 */
const getPendingApprovals = async (companyId) => {
    const db = await getDB();
    return db.user.findMany({
        where: {
            companyId,
            isCompanyVerified: false,
            isActive: true,
        },
        orderBy: { createdAt: "asc" },
        select: {
            id: true,
            username: true,
            email: true,
            firstName: true,
            lastName: true,
            title: true,
            role: true,
            createdAt: true,
        },
    });
};

/**
 * Verify user's company membership
 * @param {string} userId - User ID to verify
 * @param {string} verifiedById - Admin user ID performing verification
 * @returns {Promise<Object>} Updated user
 */
const verifyUser = async (userId, verifiedById) => {
    const db = await getDB();
    return db.user.update({
        where: { id: userId },
        data: {
            isCompanyVerified: true,
            verifiedAt: new Date(),
            verifiedBy: verifiedById,
        },
    });
};

/**
 * Assign user to company
 * @param {string} userId - User ID
 * @param {string} companyId - Company ID
 * @param {boolean} isVerified - Whether to auto-verify
 * @returns {Promise<Object>} Updated user
 */
const assignUserToCompany = async (userId, companyId, isVerified = false) => {
    const db = await getDB();
    const data = {
        companyId,
        isCompanyVerified: isVerified,
    };

    if (isVerified) {
        data.verifiedAt = new Date();
    }

    return db.user.update({
        where: { id: userId },
        data,
    });
};

module.exports = {
    createCompany,
    findById,
    findByDomain,
    listCompanies,
    updateCompany,
    deleteCompany,
    getCompanyUsers,
    getPendingApprovals,
    verifyUser,
    assignUserToCompany,
};
