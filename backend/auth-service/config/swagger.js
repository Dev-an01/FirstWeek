// backend/auth-service/config/swagger.js

const swaggerJsdoc = require("swagger-jsdoc");
const path = require("path");

const options = {
  definition: {
    openapi: "3.0.0",
    info: {
      title: "Auth Service API",
      version: "1.0.0",
      description: `
# Authentication & User Management API

Complete authentication service with:
- User registration with role assignment (GUEST, EMPLOYEE, EXECUTIVE, COMPANY_ADMIN, SUPER_ADMIN)
- JWT-based authentication (access + refresh tokens)
- Password reset via email
- Email verification with OTP
- Session management
- User profile management

## Authentication

Most endpoints require JWT authentication via cookies or Authorization header:
- **Cookie**: \`firstweek_avatar_access_token\` (httpOnly, secure)
- **Header**: \`Authorization: Bearer <token>\`

## Getting Started

1. **Register**: POST /api/users/register
2. **Login**: POST /api/users/login → Receives JWT tokens
3. **Access Protected Resources**: Include cookies or Authorization header

## Base URL

\`http://localhost:3001/api/users\`
      `,
      contact: {
        name: "FIRSTWEEK Team",
        email: "support@example.invalid",
      },
      license: {
        name: "ISC",
      },
    },
    servers: [
      {
        url: "http://localhost:3001/api/users",
        description: "Development Server",
      },
      {
        url: "https://api.example.invalid/api/users",
        description: "Production Server",
      },
    ],
    tags: [
      {
        name: "Authentication",
        description: "User registration, login, and session management",
      },
      {
        name: "User Profile",
        description: "User profile and account management",
      },
      {
        name: "Password Management",
        description: "Password reset and change functionality",
      },
      {
        name: "Email Verification",
        description: "Email verification with OTP",
      },
      {
        name: "Sessions",
        description: "Active session management",
      },
      {
        name: "Admin",
        description: "Admin-only endpoints",
      },
    ],
    components: {
      securitySchemes: {
        bearerAuth: {
          type: "http",
          scheme: "bearer",
          bearerFormat: "JWT",
          description: "JWT access token in Authorization header",
        },
        cookieAuth: {
          type: "apiKey",
          in: "cookie",
          name: "firstweek_avatar_access_token",
          description: "JWT access token in httpOnly cookie",
        },
      },
      schemas: {
        User: {
          type: "object",
          properties: {
            id: { type: "string", example: "clx123abc456" },
            email: {
              type: "string",
              format: "email",
              example: "john@example.com",
            },
            username: { type: "string", example: "john_doe" },
            firstName: { type: "string", example: "John" },
            lastName: { type: "string", example: "Doe" },
            profilePic: { type: "string", format: "uri", nullable: true },
            role: {
              type: "string",
              enum: ["GUEST", "EMPLOYEE", "EXECUTIVE", "COMPANY_ADMIN", "SUPER_ADMIN"],
              example: "EMPLOYEE",
            },
            emailVerified: { type: "boolean", example: false },
            isActive: { type: "boolean", example: true },
            createdAt: { type: "string", format: "date-time" },
            updatedAt: { type: "string", format: "date-time" },
            lastLoginAt: {
              type: "string",
              format: "date-time",
              nullable: true,
            },
          },
        },
        Session: {
          type: "object",
          properties: {
            id: { type: "string" },
            userId: { type: "string" },
            deviceInfo: { type: "string" },
            ipAddress: { type: "string" },
            createdAt: { type: "string", format: "date-time" },
            expiresAt: { type: "string", format: "date-time" },
            lastActivityAt: { type: "string", format: "date-time" },
          },
        },
        Error: {
          type: "object",
          properties: {
            success: { type: "boolean", example: false },
            error: {
              type: "object",
              properties: {
                message: { type: "string" },
                code: { type: "string" },
              },
            },
          },
        },
      },
      responses: {
        UnauthorizedError: {
          description: "Authentication required",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/Error" },
              example: {
                success: false,
                error: {
                  message: "Authentication required",
                  code: "UNAUTHORIZED",
                },
              },
            },
          },
        },
        ValidationError: {
          description: "Validation error",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/Error" },
              example: {
                success: false,
                error: {
                  message: "Validation failed",
                  code: "VALIDATION_ERROR",
                },
              },
            },
          },
        },
      },
    },
  },
  apis: [
    path.join(__dirname, "../routes/*.js"),
    path.join(__dirname, "../controllers/*.js"),
  ],
};

const swaggerSpec = swaggerJsdoc(options);

module.exports = swaggerSpec;
