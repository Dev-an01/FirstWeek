// backend/auth-service/models/schemas/userSchema.js
const { z } = require("zod");

// =============================================
// Base validation schemas (replacing manual validators)
// =============================================

const emailSchema = z
    .string()
    .min(1, "Email is required")
    .max(254, "Email must be less than 254 characters")
    .email("Invalid email format")
    .toLowerCase()
    .trim();

const passwordSchema = z
    .string()
    .min(8, "Password must be at least 8 characters")
    .max(128, "Password must be less than 128 characters")
    .regex(/[A-Z]/, "Password must contain at least one uppercase letter")
    .regex(/[a-z]/, "Password must contain at least one lowercase letter")
    .regex(/\d/, "Password must contain at least one number")
    .regex(
        /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/,
        "Password must contain at least one special character",
    );

const usernameSchema = z
    .string()
    .min(3, "Username must be at least 3 characters")
    .max(30, "Username must be less than 30 characters")
    .regex(
        /^[a-zA-Z0-9_]+$/,
        "Username can only contain letters, numbers, and underscores",
    )
    .toLowerCase()
    .trim();

const nameSchema = z
    .string()
    .min(1, "Name is required")
    .max(50, "Name must be less than 50 characters")
    .regex(
        /^[a-zA-Z\s\-']+$/,
        "Name can only contain letters, spaces, hyphens, and apostrophes",
    )
    .trim();

const titleSchema = z
    .string()
    .max(100, "Title must be less than 100 characters")
    .trim()
    .optional()
    .or(z.literal("").transform(() => undefined));

const urlSchema = z
    .string()
    .url("Invalid URL format")
    .refine(
        (url) => {
            try {
                const urlObj = new URL(url);
                return urlObj.protocol === "http:" || urlObj.protocol === "https:";
            } catch {
                return false;
            }
        },
        { message: "URL must use http or https protocol" },
    )
    .optional()
    .or(z.literal(""));

const phoneNumberSchema = z
    .string()
    .transform((phone) => phone.replace(/\D/g, "")) // Remove non-digits
    .refine((cleanPhone) => cleanPhone.length >= 10 && cleanPhone.length <= 15, {
        message: "Phone number must be between 10 and 15 digits",
    });

const dateSchema = z
    .string()
    .refine(
        (dateString) => {
            const date = new Date(dateString);
            return !Number.isNaN(date.getTime()) && date.toISOString() === dateString;
        },
        { message: "Invalid date format. Use ISO 8601 format" },
    )
    .transform((dateString) => new Date(dateString));

const cuidSchema = z.string().regex(/^c[a-z0-9]{24}$/, "Invalid ID format");

// Role schema - matches Prisma UserRole enum (hierarchical order)
// GUEST < EMPLOYEE < EXECUTIVE < COMPANY_ADMIN < SUPER_ADMIN
const roleSchema = z
    .enum(["GUEST", "EMPLOYEE", "EXECUTIVE", "COMPANY_ADMIN", "SUPER_ADMIN"], {
        errorMap: () => ({
            message: "Role must be one of: GUEST, EMPLOYEE, EXECUTIVE, COMPANY_ADMIN, SUPER_ADMIN",
        }),
    })
    .default("EMPLOYEE");

// Sanitization schema (replaces sanitizeInput function)
const sanitizedStringSchema = z.string().transform((input) => {
    if (!input || typeof input !== "string") {
        return "";
    }

    return input.trim().replace(/[<>\"'&]/g, (match) => {
        const htmlEntities = {
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#x27;",
            "&": "&amp;",
        };
        return htmlEntities[match];
    });
});

// =============================================
// User-specific schemas
// =============================================

// User creation schema (for registration)
// SECURITY: Role is NOT included here - all new users default to EMPLOYEE
// Only admins can change roles via the dedicated admin endpoint
const createUserSchema = z
    .object({
        username: usernameSchema,
        email: emailSchema,
        firstName: nameSchema,
        lastName: nameSchema,
        password: passwordSchema,
        profilePic: urlSchema,
        title: titleSchema,
    })
    .strict();

// User update schema (for profile updates)
// SECURITY: Role is NOT included - only admins can change roles
const updateUserSchema = z
    .object({
        username: usernameSchema.optional(),
        email: emailSchema.optional(),
        firstName: nameSchema.optional(),
        lastName: nameSchema.optional(),
        profilePic: urlSchema.optional(),
        title: titleSchema,
        emailVerified: z.boolean().optional(),
        isActive: z.boolean().optional(),
        emailVerifiedAt: dateSchema.optional(),
        lastLoginAt: dateSchema.optional(),
        updatedAt: dateSchema.optional(),
    })
    .strict()
    .refine((data) => Object.keys(data).length > 0, {
        message: "At least one field must be provided for update",
    });

// Admin-only schema for updating user roles
const updateUserRoleSchema = z
    .object({
        role: roleSchema,
    })
    .strict();

// User login schema
const loginUserSchema = z
    .object({
        identifier: z.union([emailSchema, usernameSchema], {
            errorMap: () => ({ message: "Please provide a valid email or username" }),
        }),
        password: z.string().min(1, "Password is required"),
    })
    .strict();

// Password change schema
const changePasswordSchema = z
    .object({
        currentPassword: z.string().min(1, "Current password is required"),
        newPassword: passwordSchema,
        confirmPassword: z.string(),
    })
    .strict()
    .refine((data) => data.newPassword === data.confirmPassword, {
        message: "New password and confirmation do not match",
        path: ["confirmPassword"],
    });

// User query schema (for filtering/searching)
const userQuerySchema = z
    .object({
        id: cuidSchema.optional(),
        username: z.string().optional(),
        email: z.string().optional(),
        isActive: z.boolean().optional(),
        page: z.coerce.number().int().min(1).default(1),
        limit: z.coerce.number().int().min(1).max(100).default(10),
        sortBy: z
            .enum(["createdAt", "updatedAt", "username", "email"])
            .default("createdAt"),
        sortOrder: z.enum(["asc", "desc"]).default("desc"),
    })
    .strict();

// Session schemas

const createSessionSchema = z.object({
    userId: z.string().cuid("Invalid user ID format"),
    token: z.string().min(1, "Token is required"),
    refreshToken: z.string().min(1, "Refresh token is required").optional(),
    expiresAt: z.date("Invalid expiration date"),
    ipAddress: z.string().optional().nullable(),
    userAgent: z.string().optional().nullable(),
});

// =============================================
// Utility validation functions (Zod-based replacements)
// =============================================

/**
 * Validate email using Zod schema
 * @param {string} email - Email to validate
 * @returns {boolean} True if email is valid
 */
const validateEmail = (email) => {
    try {
        emailSchema.parse(email);
        return true;
    } catch {
        return false;
    }
};

/**
 * Validate password using Zod schema
 * @param {string} password - Password to validate
 * @returns {boolean} True if password is valid
 */
const validatePassword = (password) => {
    try {
        passwordSchema.parse(password);
        return true;
    } catch {
        return false;
    }
};

/**
 * Validate username using Zod schema
 * @param {string} username - Username to validate
 * @returns {boolean} True if username is valid
 */
const validateUsername = (username) => {
    try {
        usernameSchema.parse(username);
        return true;
    } catch {
        return false;
    }
};

/**
 * Validate name using Zod schema
 * @param {string} name - Name to validate
 * @returns {boolean} True if name is valid
 */
const validateName = (name) => {
    try {
        nameSchema.parse(name);
        return true;
    } catch {
        return false;
    }
};

/**
 * Validate URL using Zod schema
 * @param {string} url - URL to validate
 * @returns {boolean} True if URL is valid
 */
const validateUrl = (url) => {
    try {
        urlSchema.parse(url);
        return true;
    } catch {
        return false;
    }
};

/**
 * Validate phone number using Zod schema
 * @param {string} phone - Phone number to validate
 * @returns {boolean} True if phone number is valid
 */
const validatePhoneNumber = (phone) => {
    try {
        phoneNumberSchema.parse(phone);
        return true;
    } catch {
        return false;
    }
};

/**
 * Validate date using Zod schema
 * @param {string} dateString - Date string to validate
 * @returns {boolean} True if date is valid
 */
const validateDate = (dateString) => {
    try {
        dateSchema.parse(dateString);
        return true;
    } catch {
        return false;
    }
};

/**
 * Validate CUID using Zod schema
 * @param {string} id - ID to validate
 * @returns {boolean} True if ID is valid
 */
const validateCuid = (id) => {
    try {
        cuidSchema.parse(id);
        return true;
    } catch {
        return false;
    }
};

/**
 * Sanitize input using Zod schema
 * @param {string} input - Input to sanitize
 * @returns {string} Sanitized string
 */
const sanitizeInput = (input) => {
    try {
        return sanitizedStringSchema.parse(input);
    } catch {
        return "";
    }
};

// Email verification schemas
const otpSchema = z
    .string()
    .length(6, { message: "OTP must be exactly 6 digits" })
    .regex(/^\d{6}$/, { message: "OTP must contain only digits" });

const emailVerificationRequestSchema = z.object({
    email: emailSchema,
});

const emailVerificationSchema = z.object({
    email: emailSchema,
    otp: otpSchema,
});

const emailVerificationRecordSchema = z.object({
    userId: cuidSchema,
    email: emailSchema,
    otp: otpSchema,
    token: z.string().optional(),
    expiresAt: z.date(),
    isVerified: z.boolean().default(false),
    attempts: z.number().int().min(0).default(0),
});

/**
 * Password reset request schema
 */
const passwordResetRequestSchema = z.object({
    email: z
        .string()
        .email("Invalid email format")
        .min(5, "Email must be at least 5 characters")
        .max(255, "Email must not exceed 255 characters")
        .toLowerCase()
        .trim(),
});

/**
 * Password reset schema
 */
const passwordResetSchema = z
    .object({
        token: z
            .string()
            .min(32, "Invalid reset token")
            .max(128, "Invalid reset token"),
        newPassword: z
            .string()
            .min(8, "Password must be at least 8 characters")
            .max(128, "Password must not exceed 128 characters")
            .regex(
                /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/,
                "Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character",
            ),
        confirmPassword: z.string(),
    })
    .refine((data) => data.newPassword === data.confirmPassword, {
        message: "Passwords do not match",
        path: ["confirmPassword"],
    });

/**
 * Password reset token creation schema
 */
const createPasswordResetSchema = z.object({
    userId: z.string().cuid("Invalid user ID format"),
    email: z.string().email("Invalid email format"),
    token: z.string().min(32, "Token must be at least 32 characters"),
    expiresAt: z.date(),
    ipAddress: z.string().optional(),
    userAgent: z.string().optional(),
});

// =============================================
// Default export with all schemas and validators
// =============================================

module.exports = {
    // Schemas
    emailSchema,
    passwordSchema,
    usernameSchema,
    nameSchema,
    titleSchema,
    urlSchema,
    phoneNumberSchema,
    dateSchema,
    cuidSchema,
    roleSchema,
    sanitizedStringSchema,
    createUserSchema,
    updateUserSchema,
    updateUserRoleSchema,
    loginUserSchema,
    changePasswordSchema,
    userQuerySchema,
    createSessionSchema,

    // Utility validators (drop-in replacements)
    validateEmail,
    validatePassword,
    validateUsername,
    validateName,
    validateUrl,
    validatePhoneNumber,
    validateDate,
    validateCuid,
    sanitizeInput,

    // email verification schemas
    otpSchema,
    emailVerificationRequestSchema,
    emailVerificationRecordSchema,
    emailVerificationSchema,

    // password reset schema:
    passwordResetRequestSchema,
    passwordResetSchema,
    createPasswordResetSchema,
};
