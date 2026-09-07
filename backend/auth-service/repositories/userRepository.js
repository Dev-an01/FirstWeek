const { getDatabase } = require("../config/database");
const {
  transformError,
  ValidationError,
  // eslint-disable-next-line
} = require('../shared/utils/errors');
const {
  createUserSchema,
  updateUserSchema,
  cuidSchema,
  emailSchema,
  usernameSchema,
} = require("../models/userSchema");
const { USER_FIELDS, ALLOWED_UPDATE_FIELDS } = require("../lib/constants");
// eslint-disable-next-line
const { createLogger } = require('../shared/utils/logger');
const logger = createLogger("user-repository");
let dbInstance = null;

/**
 * Get database instance (singleton pattern)
 * @returns {Promise<Object>} Database instance
 */
const getDB = async () => {
  if (!dbInstance) {
    dbInstance = await getDatabase();
  }
  return dbInstance;
};

/**
 * Create a new user in the database
 * @param {Object} userData - User data to create
 * @returns {Promise<Object>} Created user object
 * @throws {DatabaseError} When database operation fails
 */
const createUser = async (userData) => {
  // Extract company-related and role fields before Zod validation (they're not in the schema)
  const { companyId, isCompanyVerified, verifiedAt, role, ...baseUserData } = userData;

  const validatedUserData = createUserSchema.parse(baseUserData);
  const { username, email, firstName, lastName, password, title } =
    validatedUserData;
  try {
    const db = await getDB();
    const newUser = await db.user.create({
      data: {
        username,
        email,
        firstName,
        lastName,
        password,
        ...(title && { title }),
        ...(role && { role }), // Only include role if provided
        ...(companyId && { companyId }), // Company assignment
        ...(isCompanyVerified !== undefined && { isCompanyVerified }),
        ...(verifiedAt && { verifiedAt }),
      },
      select: USER_FIELDS.public,
    });
    return newUser;
  } catch (error) {
    console.log("Error in createUser:", error);
    throw transformError(error, "createUser");
  }
};
/**
 * Find user by various possible identifiers
 * @param {Object|string} identifiers - Identifier(s): email, username, id, or a single string
 * @param {boolean} includePassword - Whether to include password in result
 * @returns {Promise<Object|null>} User object or null if not found
 */
const findUser = async (
  identifiers,
  includePassword = false,
  requireActive = true,
) => {
  try {
    const db = await getDB();
    const orConditions = [];
    if (typeof identifiers === "string") {
      const str = identifiers.trim();
      if (str.includes("@")) {
        const validEmail = emailSchema.parse(str);
        orConditions.push({ email: validEmail });
      } else if (str.length >= 25 && str.match(/^c[a-z0-9]{24,}$/)) {
        // likely a cuid (e.g., "ck9xyz...")
        const validId = cuidSchema.parse(str);
        orConditions.push({ id: validId });
      } else {
        const validUsername = usernameSchema.parse(str);
        orConditions.push({ username: validUsername });
      }
    }
    // Handle object with potential multiple identifiers
    if (typeof identifiers === "object" && identifiers !== null) {
      const { email, username, id } = identifiers;
      if (email && typeof email === "string") {
        orConditions.push({ email: emailSchema.parse(email) });
      }
      if (username && typeof username === "string") {
        orConditions.push({ username: usernameSchema.parse(username) });
      }
      if (id && typeof id === "string") {
        orConditions.push({ id: cuidSchema.parse(id) });
      }
    }
    // Ensure at least one valid identifier is provided
    if (orConditions.length === 0) {
      throw ValidationError(
        "At least one valid identifier (email, username, or id) must be provided",
      );
    }

    const whereClause = { OR: orConditions };
    // Only filter by isActive if requireActive is true
    if (requireActive) {
      whereClause.isActive = true;
    }

    const user = await db.user.findFirst({
      where: whereClause,
      select: includePassword ? USER_FIELDS.withPassword : USER_FIELDS.public,
    });

    return user;
  } catch (error) {
    throw transformError(error, "findUser");
  }
};
/**
 * Update user's last login timestamp
 * @param {string} userId - User ID to update
 * @returns {Promise<Object>} Updated user object with minimal fields
 * @throws {DatabaseError} When database operation fails
 */
const updateLastLogin = async (userId) => {
  try {
    const db = await getDB();
    const validUserId = cuidSchema.parse(userId);
    const updatedUser = await db.user.update({
      where: { id: validUserId },
      data: { lastLoginAt: new Date() },
      select: USER_FIELDS.minimal,
    });
    return updatedUser;
  } catch (error) {
    throw transformError(error, "updateLastLogin");
  }
};
/**
 * Update user details
 * @param {string} userId - User ID to update
 * @param {Object} updateData - Fields to update
 * @returns {Promise<Object>} Updated user object
 * @throws {DatabaseError} When database operation fails
 */
const updateUser = async (userId, updateData) => {
  try {
    const db = await getDB();
    const validUserId = cuidSchema.parse(userId);
    if (!updateData || Object.keys(updateData).length === 0) {
      throw ValidationError("Update Data cannot be empty");
    }
    const validatedUpdateData = updateUserSchema.parse(updateData);
    logger.info("UpdateUser", {
      userId: validUserId,
      updateData: validatedUpdateData,
      initialData: updateData,
    });
    const cleanData = Object.fromEntries(
      Object.entries(validatedUpdateData).filter(
        ([key, value]) =>
          ALLOWED_UPDATE_FIELDS.includes(key) &&
          value !== undefined &&
          value !== null,
      ),
    );
    const updatedUser = await db.user.update({
      where: { id: validUserId },
      data: {
        ...cleanData,
        updatedAt: new Date(),
      },
      select: USER_FIELDS.public,
    });

    return updatedUser;
  } catch (error) {
    throw transformError(error, "updateUser");
  }
};
/**
 * Update user role (admin only - bypasses normal update restrictions)
 * @param {string} userId - User ID to update
 * @param {string} role - New role value
 * @returns {Promise<Object>} Updated user object
 */
const updateUserRole = async (userId, role) => {
  try {
    const db = await getDB();
    const validUserId = cuidSchema.parse(userId);

    const updatedUser = await db.user.update({
      where: { id: validUserId },
      data: {
        role,
        updatedAt: new Date(),
      },
      select: USER_FIELDS.public,
    });

    return updatedUser;
  } catch (error) {
    throw transformError(error, "updateUserRole");
  }
};

/**
 * Update email verification status
 * @param {string} userId - User ID to update
 * @param {boolean} isVerified - Verification status
 * @returns {Promise<Object>} Updated user object with public fields
 * @throws {DatabaseError} When database operation fails
 * */
const updateEmailVerificationStatus = async (userId, isVerified) => {
  try {
    const db = await getDB();
    const validUserId = cuidSchema.parse(userId);
    const updatedUser = await db.user.update({
      where: { id: validUserId },
      data: {
        emailVerified: isVerified,
        emailVerifiedAt: isVerified ? new Date() : null,
      },
      select: USER_FIELDS.public,
    });
    return updatedUser;
  } catch (error) {
    throw transformError(error, "updateEmailVerificationStatus");
  }
};
/**
 * Update user password
 * @param {string} userId - User ID to update
 * @param {string} newPassword - New password to set
 * @returns {Promise<Object>} Updated user object with public fields
 * @throws {DatabaseError} When database operation fails
 * */
const updateUserPassword = async (userId, newPassword) => {
  try {
    const db = await getDB();
    const validUserId = cuidSchema.parse(userId);
    const updatedUser = await db.user.update({
      where: { id: validUserId },
      data: {
        password: newPassword,
        updatedAt: new Date(),
      },
      select: USER_FIELDS.public,
    });
    return updatedUser;
  } catch (error) {
    throw transformError(error, "updateUserPassword");
  }
};
/**
 * Check if email exists
 * @param {string} email - Email to check
 * @returns {Promise<boolean>} True if email exists
 * @throws {DatabaseError} When database operation fails
 */
const checkEmailExists = async (email) => {
  try {
    const db = await getDB();
    const validEmail = emailSchema.parse(email);

    const count = await db.user.count({
      where: { email: validEmail },
    });
    return count > 0;
  } catch (error) {
    throw transformError(error, "checkEmailExists");
  }
};
/**
 * Check if username exists
 * @param {string} username - Username to check
 * @returns {Promise<boolean>} True if username exists
 * @throws {DatabaseError} When database operation fails
 */
const checkUsernameExists = async (username) => {
  try {
    const db = await getDB();
    const validUsername = usernameSchema.parse(username);
    const count = await db.user.count({
      where: { username: validUsername },
    });
    return count > 0;
  } catch (error) {
    throw transformError(error, "checkUsernameExists");
  }
};

const findUsers = async (filters = {}, options = {}) => {
  try {
    const db = await getDB();
    const { limit = 10, offset = 0 } = options;

    const whereConditions = {
      isActive: true,
      ...filters,
    };

    const users = await db.user.findMany({
      where: whereConditions,
      skip: offset,
      take: limit,
      select: {
        ...USER_FIELDS.minimal,
        company: {
          select: {
            id: true,
            name: true,
          },
        },
      },
    });

    return users;
  } catch (error) {
    console.log("Error in findUsers:", error);
    throw transformError(error, "findUsers");
  }
};

/**
 * Assign a user to a company with a new role
 * @param {string} userId - User ID
 * @param {string} companyId - Company ID to assign
 * @param {string} role - New role (e.g., EMPLOYEE)
 * @param {boolean} isCompanyVerified - Whether user is verified for company
 * @returns {Promise<Object>} Updated user object
 */
const assignToCompany = async (userId, companyId, role = "EMPLOYEE", isCompanyVerified = true) => {
  try {
    const db = await getDB();
    const updatedUser = await db.user.update({
      where: { id: userId },
      data: {
        companyId,
        role,
        isCompanyVerified,
        verifiedAt: isCompanyVerified ? new Date() : null,
      },
      select: USER_FIELDS.public,
    });
    return updatedUser;
  } catch (error) {
    console.log("Error in assignToCompany:", error);
    throw transformError(error, "assignToCompany");
  }
};

module.exports = {
  createUser,
  findUser,
  updateLastLogin,
  updateUser,
  updateUserRole,
  updateEmailVerificationStatus,
  updateUserPassword,
  checkEmailExists,
  checkUsernameExists,
  findUsers,
  assignToCompany,
};
