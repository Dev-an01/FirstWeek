const USER_FIELDS = {
  public: {
    id: true,
    username: true,
    email: true,
    firstName: true,
    lastName: true,
    profilePic: true,
    title: true,
    role: true, // RBAC - Include role for authorization
    emailVerified: true,
    isActive: true,
    createdAt: true,
    updatedAt: true,
    lastLoginAt: true,
    sessions: true,
    companyId: true, // RBAC - Company association
    isCompanyVerified: true, // RBAC - Company verification status
    company: { // RBAC - Include company details
      select: {
        id: true,
        name: true,
      },
    },
  },
  withPassword: {
    id: true,
    username: true,
    email: true,
    firstName: true,
    lastName: true,
    profilePic: true,
    title: true,
    role: true, // RBAC - Include role for authorization
    password: true,
    emailVerified: true,
    isActive: true,
    createdAt: true,
    updatedAt: true,
    lastLoginAt: true,
    companyId: true, // RBAC - Company association
    isCompanyVerified: true, // RBAC - Company verification status
  },
  minimal: {
    id: true,
    username: true,
    email: true,
    role: true, // RBAC - Include role for authorization
    isActive: true,
    lastLoginAt: true,
    companyId: true, // RBAC - Company association
    isCompanyVerified: true, // RBAC - Company verification status
  },
};
// Session field selections
const SESSION_FIELDS = {
  // Public session fields (safe for client)
  public: {
    id: true,
    userId: true,
    expiresAt: true,
    ipAddress: true,
    userAgent: true,
    createdAt: true,
    updatedAt: true,
  },

  // Session fields with user data
  withUser: {
    id: true,
    userId: true,
    token: true,
    refreshToken: true,
    expiresAt: true,
    ipAddress: true,
    userAgent: true,
    createdAt: true,
    updatedAt: true,
  },

  // Minimal session fields
  minimal: {
    id: true,
    userId: true,
    expiresAt: true,
    createdAt: true,
  },

  // Session fields including tokens (for internal use only)
  withTokens: {
    id: true,
    userId: true,
    token: true,
    refreshToken: true,
    expiresAt: true,
    ipAddress: true,
    userAgent: true,
    createdAt: true,
    updatedAt: true,
  },
};
const ALLOWED_UPDATE_FIELDS = [
  "username",
  "email",
  "firstName",
  "lastName",
  "profilePic",
  "title",
  "emailVerified",
  "emailVerifiedAt",
  "password",
  "isActive",
];
const ALLOWED_SESSION_UPDATE_FIELDS = [
  "token",
  "refreshToken",
  "expiresAt",
  "ipAddress",
  "userAgent",
];
// JWT token configurations
const TOKEN_TYPES = {
  ACCESS: "access",
  REFRESH: "refresh",
  EMAIL_VERIFICATION: "email_verification",
  PASSWORD_RESET: "password_reset",
};

// Cookie names for different token types
const COOKIE_NAMES = {
  ACCESS_TOKEN: "firstweek_avatar_access_token",
  REFRESH_TOKEN: "firstweek_avatar_refresh_token",
};

// Session configuration
const SESSION_CONFIG = {
  MAX_SESSIONS_PER_USER: 5, // Maximum concurrent sessions
  SESSION_CLEANUP_INTERVAL: 24 * 60 * 60 * 1000, // 24 hours in milliseconds
  SESSION_EXTEND_THRESHOLD: 2 * 60 * 60 * 1000, // 2 hours before expiry
};
// Email verification configuration
const EMAIL_VERIFICATION = {
  TOKEN_EXPIRY: 24 * 60 * 60 * 1000, // 24 hours
  MAX_RESEND_ATTEMPTS: 3,
  RESEND_COOLDOWN: 5 * 60 * 1000, // 5 minutes
};
// Rate limiting configurations
const RATE_LIMITS = {
  LOGIN_ATTEMPTS: {
    max: 5,
    windowMs: 15 * 60 * 1000, // 15 minutes
    skipSuccessfulRequests: true,
  },
  REGISTRATION: {
    max: 3,
    windowMs: 60 * 60 * 1000, // 1 hour
  },
  PASSWORD_RESET: {
    max: 3,
    windowMs: 60 * 60 * 1000, // 1 hour
  },
  TOKEN_REFRESH: {
    max: 10,
    windowMs: 60 * 1000, // 1 minute
  },
};

// Error message templates
const ERROR_MESSAGES = {
  VALIDATION: {
    REQUIRED_FIELD: (field) => `${field} is required`,
    INVALID_FORMAT: (field) => `${field} has invalid format`,
    TOO_SHORT: (field, min) => `${field} must be at least ${min} characters`,
    TOO_LONG: (field, max) => `${field} must be less than ${max} characters`,
  },
  AUTHENTICATION: {
    INVALID_CREDENTIALS: "Invalid email/username or password",
    ACCOUNT_DEACTIVATED: "Account has been deactivated",
    TOKEN_EXPIRED: "Token has expired",
    INVALID_TOKEN: "Invalid or malformed token",
    SESSION_EXPIRED: "Session has expired",
  },
  AUTHORIZATION: {
    INSUFFICIENT_PERMISSIONS: "Insufficient permissions for this action",
  },
  CONFLICT: {
    EMAIL_EXISTS: "Email is already registered",
    USERNAME_EXISTS: "Username is already taken",
  },
};

// Success message templates
const SUCCESS_MESSAGES = {
  USER: {
    REGISTERED: "User registered successfully",
    LOGIN: "Login successful",
    LOGOUT: "Logout successful",
    PROFILE_UPDATED: "Profile updated successfully",
    PASSWORD_CHANGED: "Password changed successfully",
    EMAIL_VERIFIED: "Email verified successfully",
  },
  SESSION: {
    CREATED: "Session created successfully",
    REFRESHED: "Token refreshed successfully",
    INVALIDATED: "Session invalidated successfully",
  },
};
const JWT_CONFIG = {
  accessTokenSecret:
    process.env.JWT_ACCESS_SECRET || "your-access-token-secret",
  refreshTokenSecret:
    process.env.JWT_REFRESH_SECRET || "your-refresh-token-secret",
  accessTokenExpiry: process.env.JWT_ACCESS_EXPIRY || "15m",
  refreshTokenExpiry: process.env.JWT_REFRESH_EXPIRY || "7d",
  cookieOptions: {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: process.env.NODE_ENV === "production" ? "strict" : "lax",
    // Don't set domain for IP addresses (browsers reject cookies with IP domains)
    // Only set domain for proper domain names like "localhost" or "example.com"
    domain: (() => {
      const cookieDomain = process.env.COOKIE_DOMAIN;
      if (!cookieDomain) return undefined;
      // Check if it's an IP address (simple regex for IPv4)
      const isIP = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(cookieDomain);
      return isIP ? undefined : cookieDomain;
    })(),
  },
};
const GMAIL_CONFIG = {
  auth: {
    user: process.env.GMAIL_ADDRESS,
    pass: process.env.GMAIL_PASSWORD,
  },
};
module.exports = {
  // Field selections
  USER_FIELDS,
  SESSION_FIELDS,
  // Allowed fields for updates
  ALLOWED_UPDATE_FIELDS,
  ALLOWED_SESSION_UPDATE_FIELDS,
  // Token and session configurations
  TOKEN_TYPES,
  COOKIE_NAMES,
  SESSION_CONFIG,
  EMAIL_VERIFICATION,
  RATE_LIMITS,
  // Error and success messages
  ERROR_MESSAGES,
  SUCCESS_MESSAGES,
  JWT_CONFIG,
  GMAIL_CONFIG,
};
