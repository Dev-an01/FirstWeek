# API Reference - Auth & Chat Services

Concise reference for all authentication and chat endpoints with RBAC examples.

---

## Authentication Service

**Base URL**: `http://localhost:3001/api/users`

### Default Admin Account

A default administrator account is created when seeding the database:

```
Username: admin
Email: admin@example.invalid
Password: Admin@123456
Role: EXECUTIVE
```

**⚠️ SECURITY WARNING:**
- Change the default admin password immediately in production
- This account has full system access and can manage all users
- Use `PUT /api/users/change-password` to update the password after first login

**To seed the database:**
```bash
docker compose exec auth-service npm run db:seed
```

---

### Register User

**POST** `/register`

Creates a new user account. All new users are assigned the `EMPLOYEE` role by default.

**Request:**
```json
{
  "email": "employee@example.com",
  "password": "SecurePass123!",
  "username": "john_doe",
  "firstName": "John",
  "lastName": "Doe"
}
```

**Required Fields:**
- `email` - Valid email address
- `password` - Min 8 chars, must contain uppercase, lowercase, number, and special character
- `username` - 3-30 chars, letters/numbers/underscores only
- `firstName` - User's first name
- `lastName` - User's last name

**Optional Fields:**
- `profilePic` - URL to profile picture

**Response:**
```json
{
  "success": true,
  "message": "User registered successfully",
  "data": {
    "user": {
      "id": "clx...",
      "email": "employee@example.com",
      "username": "john_doe",
      "firstName": "John",
      "lastName": "Doe",
      "profilePic": null,
      "role": "EMPLOYEE",
      "emailVerified": false,
      "isActive": true,
      "createdAt": "2025-01-15T10:00:00.000Z",
      "updatedAt": "2025-01-15T10:00:00.000Z",
      "lastLoginAt": null
    }
  }
}
```

**Cookies Set**: `firstweek_avatar_access_token`, `firstweek_avatar_refresh_token` (httpOnly)

**Notes:**
- **SECURITY**: All new users are automatically assigned the `EMPLOYEE` role
- **Role changes**: Only administrators (EXECUTIVE role) can change user roles via the admin endpoint
- Password must meet complexity requirements (uppercase, lowercase, number, special character)
- See [Update User Role](#update-user-role-admin-only) for role management

---

### Login

**POST** `/login`

Authenticates user and returns JWT tokens with role information.

**Request:**
```json
{
  "identifier": "employee@example.com",
  "password": "SecurePass123!"
}
```

**Note**: `identifier` can be either email or username.

**Response:**
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "user": {
      "id": "clx...",
      "username": "john_doe",
      "email": "employee@example.com",
      "role": "EMPLOYEE",
      "isActive": true,
      "lastLoginAt": "2025-01-15T10:00:00.000Z"
    }
  }
}
```

**Note**: Login returns minimal user fields for performance. Use `/me` endpoint for complete user details.

**JWT Payload** (decoded from cookie):
```json
{
  "id": "clx...",
  "email": "employee@example.com",
  "role": "EMPLOYEE",
  "iat": 1234567890,
  "exp": 1234567890
}
```

---

### Get Profile

**GET** `/me`

Retrieves authenticated user's profile including role.

**Headers:** Cookie with JWT token (automatic)

**Response:**
```json
{
  "success": true,
  "message": "Profile retrieved successfully",
  "data": {
    "user": {
      "id": "clx...",
      "username": "john_doe",
      "email": "employee@example.com",
      "firstName": "John",
      "lastName": "Doe",
      "profilePic": null,
      "role": "EMPLOYEE",
      "emailVerified": false,
      "isActive": true,
      "createdAt": "2025-01-15T10:00:00.000Z",
      "updatedAt": "2025-01-15T10:00:00.000Z",
      "lastLoginAt": "2025-01-15T10:00:00.000Z"
    },
    "session": {
      "id": "session_id",
      "expiresAt": "2025-01-22T10:00:00.000Z",
      "ipAddress": "127.0.0.1",
      "userAgent": "Mozilla/5.0..."
    }
  }
}
```

---

### Refresh Token

**POST** `/refresh`

Refreshes access token using refresh token from cookie.

**Headers:** Cookie with refresh token (automatic)

**Response:**
```json
{
  "success": true,
  "message": "Token refreshed successfully"
}
```

**Cookies Updated**: New `firstweek_avatar_access_token`

---

### Logout

**POST** `/logout`

Clears authentication cookies.

**Response:**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

### Logout from All Devices

**POST** `/logout-all`

Invalidates all active sessions for the authenticated user across all devices.

**Headers:** Cookie with JWT token (automatic)

**Response:**
```json
{
  "success": true,
  "message": "Logged out from all devices successfully"
}
```

**Notes:**
- Clears all sessions in database
- Requires re-authentication on all devices
- Useful when device is lost/stolen or security is compromised

---

### Change Password

**PUT** `/change-password`

Changes the authenticated user's password.

**Headers:** Cookie with JWT token (automatic)

**Request:**
```json
{
  "currentPassword": "OldPass123!",
  "newPassword": "NewSecurePass456!",
  "confirmPassword": "NewSecurePass456!"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Password changed successfully"
}
```

**Error Responses:**

**400 Bad Request** (Password Mismatch):
```json
{
  "success": false,
  "error": {
    "message": "New password and confirmation do not match",
    "code": "VALIDATION_ERROR"
  }
}
```

**401 Unauthorized** (Incorrect Current Password):
```json
{
  "success": false,
  "error": {
    "message": "Current password is incorrect",
    "code": "INVALID_CURRENT_PASSWORD"
  }
}
```

**Notes:**
- Invalidates all sessions after password change (user must re-login)
- New password must meet complexity requirements
- Useful for regular password rotation and security

---

### Update Profile

**PUT** `/me`

Updates the authenticated user's profile information.

**Headers:** Cookie with JWT token (automatic)

**Request:**
```json
{
  "firstName": "Jane",
  "lastName": "Smith",
  "username": "jane_smith",
  "email": "jane.smith@example.com",
  "profilePic": "https://example.com/avatar.jpg"
}
```

**Available Fields** (all optional):
- `username` - New username (must be unique)
- `email` - New email (must be unique, triggers email verification)
- `firstName` - Updated first name
- `lastName` - Updated last name
- `profilePic` - Profile picture URL

**Response:**
```json
{
  "success": true,
  "message": "Profile updated successfully",
  "data": {
    "user": {
      "id": "clx...",
      "username": "jane_smith",
      "email": "jane.smith@example.com",
      "firstName": "Jane",
      "lastName": "Smith",
      "profilePic": "https://example.com/avatar.jpg",
      "role": "EMPLOYEE",
      "emailVerified": true,
      "isActive": true,
      "createdAt": "2025-01-15T10:00:00.000Z",
      "updatedAt": "2025-01-15T14:30:00.000Z",
      "lastLoginAt": "2025-01-15T14:00:00.000Z"
    }
  }
}
```

**Response (Email Changed):**
```json
{
  "success": true,
  "message": "Profile updated successfully. Please check your email and verify the OTP to complete email setup.",
  "data": {
    "user": {
      "id": "clx...",
      "username": "jane_smith",
      "email": "jane.smith@example.com",
      "emailVerified": false,
      "...": "..."
    },
    "emailVerification": {
      "required": true,
      "email": "jane.smith@example.com",
      "success": true,
      "expiresAt": "2025-01-15T15:00:00.000Z"
    }
  }
}
```

**Notes:**
- Email changes trigger OTP verification process
- Username and email must be unique (returns 409 if already taken)
- **Cannot update role** - only admins can change roles

---

### Deactivate Account

**PUT** `/deactivate`

Deactivates the authenticated user's account.

**Headers:** Cookie with JWT token (automatic)

**Response:**
```json
{
  "success": true,
  "message": "Account deactivated successfully"
}
```

**Notes:**
- Sets `isActive` to `false`
- Invalidates all sessions (logs out from all devices)
- User cannot login until reactivated by admin
- Account data is preserved (not deleted)

---

### Validate Token

**GET** `/validate-token`

Validates the current JWT access token and returns user/session info.

**Headers:** Cookie with JWT token (automatic)

**Response:**
```json
{
  "success": true,
  "message": "Token is valid",
  "data": {
    "isValid": true,
    "user": {
      "id": "clx...",
      "username": "john_doe",
      "email": "john@example.com",
      "role": "EMPLOYEE",
      "emailVerified": false,
      "isActive": true
    },
    "session": {
      "id": "session_id",
      "expiresAt": "2025-01-15T15:00:00.000Z",
      "ipAddress": "127.0.0.1",
      "userAgent": "Mozilla/5.0..."
    }
  }
}
```

**Notes:**
- Useful for frontend to check authentication status
- Returns full user and session data
- Used by protected route guards

---

### Check Email Availability

**POST** `/check-email`

Checks if an email address is already registered.

**Request:**
```json
{
  "email": "test@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Email availability checked",
  "data": {
    "exists": false,
    "email": "test@example.com"
  }
}
```

**Notes:**
- Returns `exists: true` if email is taken
- Useful for real-time validation in signup forms
- Public endpoint (no authentication required)

---

### Check Username Availability

**POST** `/check-username`

Checks if a username is already taken.

**Request:**
```json
{
  "username": "john_doe"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Username availability checked",
  "data": {
    "exists": false,
    "username": "john_doe"
  }
}
```

**Notes:**
- Returns `exists: true` if username is taken
- Useful for real-time validation in signup forms
- Public endpoint (no authentication required)

---

### Update User Role (Admin Only)

**PUT** `/:userId/role`

Updates a user's role. **Requires EXECUTIVE role** (administrator privileges).

**Headers:** Cookie with JWT token (automatic)

**Request:**
```json
{
  "role": "EXECUTIVE"
}
```

**Available Roles**: `GUEST`, `EMPLOYEE`, `EXECUTIVE`, `COMPANY_ADMIN`, `SUPER_ADMIN`

**Response:**
```json
{
  "success": true,
  "message": "User role updated successfully",
  "data": {
    "user": {
      "id": "clx...",
      "username": "jane_doe",
      "email": "jane@example.com",
      "firstName": "Jane",
      "lastName": "Doe",
      "role": "EXECUTIVE",
      "emailVerified": true,
      "isActive": true,
      "createdAt": "2025-01-14T10:00:00.000Z",
      "updatedAt": "2025-01-15T12:30:00.000Z",
      "lastLoginAt": "2025-01-15T09:00:00.000Z"
    }
  }
}
```

**Error Responses:**

**403 Forbidden** (Insufficient Permissions):
```json
{
  "success": false,
  "error": {
    "message": "Insufficient permissions. This action requires elevated privileges.",
    "code": "INSUFFICIENT_PERMISSIONS"
  }
}
```

**400 Bad Request** (Self Role Modification):
```json
{
  "success": false,
  "error": {
    "message": "Cannot modify your own role. Contact another administrator.",
    "code": "SELF_ROLE_MODIFICATION_FORBIDDEN"
  }
}
```

**404 Not Found** (User Not Found):
```json
{
  "success": false,
  "error": {
    "message": "User not found",
    "code": "USER_NOT_FOUND"
  }
}
```

**Notes:**
- **Authorization**: Only users with `EXECUTIVE` role can access this endpoint
- **Self-modification prevention**: Administrators cannot change their own role
- **Audit logging**: All role changes are logged with admin ID, timestamp, and IP address
- **Use case**: Promoting employees to executives or demoting users

**Example Usage:**
```bash
# Promote user to EXECUTIVE role
curl -X PUT http://localhost:3001/api/users/clx123/role \
  -H "Content-Type: application/json" \
  --cookie "firstweek_avatar_access_token=<token>" \
  -d '{"role":"EXECUTIVE"}'
```

---

### Get All Users (Admin Only)

**GET** `/`

Retrieves all users in the system. **Requires EXECUTIVE role** (administrator privileges).

**Headers:** Cookie with JWT token (automatic)

**Response:**
```json
{
  "success": true,
  "message": "Users retrieved successfully",
  "data": {
    "users": [
      {
        "id": "clx1...",
        "username": "admin",
        "email": "admin@example.invalid",
        "firstName": "System",
        "lastName": "Administrator",
        "role": "EXECUTIVE",
        "emailVerified": true,
        "isActive": true,
        "createdAt": "2025-01-01T00:00:00.000Z",
        "updatedAt": "2025-01-01T00:00:00.000Z"
      },
      {
        "id": "clx2...",
        "username": "john_doe",
        "email": "john@example.com",
        "firstName": "John",
        "lastName": "Doe",
        "role": "EMPLOYEE",
        "emailVerified": false,
        "isActive": true,
        "createdAt": "2025-01-15T10:00:00.000Z",
        "updatedAt": "2025-01-15T10:00:00.000Z"
      }
    ]
  }
}
```

**Notes:**
- **Authorization**: Only users with `EXECUTIVE` role can access this endpoint
- Returns all users regardless of status (active/inactive)
- Password hashes are never returned in responses

---

## Session Management

### Get User Sessions

**GET** `/sessions`

Retrieves all active and expired sessions for the authenticated user.

**Headers:** Cookie with JWT token (automatic)

**Response:**
```json
{
  "success": true,
  "message": "Sessions retrieved successfully",
  "data": {
    "sessions": [
      {
        "id": "session_abc123",
        "token": "eyJhbGc...",
        "ipAddress": "192.168.1.100",
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
        "expiresAt": "2025-01-22T10:00:00.000Z",
        "createdAt": "2025-01-15T10:00:00.000Z",
        "updatedAt": "2025-01-15T10:00:00.000Z",
        "isCurrent": true
      },
      {
        "id": "session_def456",
        "token": "eyJhbGc...",
        "ipAddress": "192.168.1.101",
        "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0...)...",
        "expiresAt": "2025-01-22T08:00:00.000Z",
        "createdAt": "2025-01-14T08:00:00.000Z",
        "updatedAt": "2025-01-14T08:00:00.000Z",
        "isCurrent": false
      }
    ],
    "totalSessions": 2,
    "activeSessions": 2
  }
}
```

**Notes:**
- Shows all sessions across all devices
- `isCurrent` flag indicates the current session
- Includes IP address and user agent for security tracking
- Expired sessions are also returned

---

### Revoke Session

**DELETE** `/sessions/:sessionId`

Revokes a specific session by ID, logging out that device.

**Headers:** Cookie with JWT token (automatic)

**URL Parameters:**
- `sessionId` - The session ID to revoke

**Response:**
```json
{
  "success": true,
  "message": "Session revoked successfully"
}
```

**Notes:**
- If revoking current session, will redirect to logout
- Useful for remotely logging out from specific devices
- Session is immediately invalidated

**Example:**
```bash
curl -X DELETE http://localhost:3001/api/users/sessions/session_abc123 \
  -b cookies.txt
```

---

### Get Session Statistics

**GET** `/sessions/stats`

Retrieves session statistics for the authenticated user.

**Headers:** Cookie with JWT token (automatic)

**Response:**
```json
{
  "success": true,
  "message": "Session statistics retrieved successfully",
  "data": {
    "stats": {
      "totalSessions": 5,
      "activeSessions": 2,
      "expiredSessions": 3,
      "lastLoginAt": "2025-01-15T10:00:00.000Z",
      "lastLoginIp": "192.168.1.100",
      "lastLoginUserAgent": "Mozilla/5.0..."
    }
  }
}
```

**Notes:**
- Provides overview of user's session activity
- Useful for security dashboard
- Shows login patterns and device usage

---

## Password Reset

### Request Password Reset

**POST** `/password/forgot`

Initiates password reset process by sending reset link to user's email.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Password reset email sent. Please check your inbox.",
  "data": {
    "email": "user@example.com",
    "expiresAt": "2025-01-15T16:00:00.000Z"
  }
}
```

**Notes:**
- Public endpoint (no authentication required)
- Sends email with reset token (valid for 1 hour)
- Returns success even if email not found (security best practice)
- Rate limited to prevent abuse

---

### Reset Password

**POST** `/password/reset`

Resets user password using the token from reset email.

**Request:**
```json
{
  "token": "reset_token_from_email",
  "newPassword": "NewSecurePass456!",
  "confirmPassword": "NewSecurePass456!"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Password reset successfully. Please login with your new password."
}
```

**Error Responses:**

**400 Bad Request** (Invalid/Expired Token):
```json
{
  "success": false,
  "error": {
    "message": "Invalid or expired reset token",
    "code": "INVALID_RESET_TOKEN"
  }
}
```

**Notes:**
- Public endpoint (no authentication required)
- Token is single-use and expires in 1 hour
- Invalidates all existing sessions (user must re-login)
- New password must meet complexity requirements

---

### Validate Reset Token

**GET** `/password/validate-token/:token`

Validates a password reset token before attempting reset.

**URL Parameters:**
- `token` - The reset token from email

**Response:**
```json
{
  "success": true,
  "message": "Reset token is valid",
  "data": {
    "isValid": true,
    "email": "user@example.com",
    "expiresAt": "2025-01-15T16:00:00.000Z"
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": {
    "message": "Invalid or expired reset token",
    "code": "INVALID_RESET_TOKEN"
  }
}
```

**Notes:**
- Public endpoint (no authentication required)
- Useful for validating token before showing reset form
- Returns associated email address if valid

---

## Email Verification

### Send Email Verification OTP

**POST** `/email/send-otp`

Sends a 6-digit OTP to user's email for verification.

**Headers:** Cookie with JWT token (automatic)

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Verification OTP sent to your email",
  "data": {
    "email": "user@example.com",
    "expiresAt": "2025-01-15T15:00:00.000Z"
  }
}
```

**Notes:**
- Requires authentication
- OTP is valid for 15 minutes
- Maximum 3 verification attempts allowed
- Rate limited to prevent spam

---

### Verify Email OTP

**POST** `/email/verify-otp`

Verifies the email using the OTP code sent to user's email.

**Headers:** Cookie with JWT token (automatic)

**Request:**
```json
{
  "email": "user@example.com",
  "otp": "123456"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Email verified successfully",
  "data": {
    "email": "user@example.com",
    "emailVerified": true
  }
}
```

**Error Responses:**

**400 Bad Request** (Invalid OTP):
```json
{
  "success": false,
  "error": {
    "message": "Invalid OTP code",
    "code": "INVALID_OTP"
  }
}
```

**400 Bad Request** (Expired OTP):
```json
{
  "success": false,
  "error": {
    "message": "OTP has expired. Please request a new one.",
    "code": "OTP_EXPIRED"
  }
}
```

**429 Too Many Requests** (Max Attempts Exceeded):
```json
{
  "success": false,
  "error": {
    "message": "Maximum verification attempts exceeded. Please request a new OTP.",
    "code": "MAX_ATTEMPTS_EXCEEDED"
  }
}
```

**Notes:**
- OTP must be exactly 6 digits
- Maximum 3 attempts before OTP is invalidated
- Updates user's `emailVerified` status to true

---

### Resend Email Verification OTP

**POST** `/email/resend-otp`

Resends a new OTP to user's email.

**Headers:** Cookie with JWT token (automatic)

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "New verification OTP sent to your email",
  "data": {
    "email": "user@example.com",
    "expiresAt": "2025-01-15T15:15:00.000Z"
  }
}
```

**Notes:**
- Invalidates previous OTP
- Generates new 6-digit code
- Rate limited to prevent abuse (max 3 requests per 15 minutes)

---

### Check Email Verification Status

**GET** `/email/verification-status`

Checks the verification status of user's email.

**Headers:** Cookie with JWT token (automatic)

**Response:**
```json
{
  "success": true,
  "message": "Email verification status retrieved",
  "data": {
    "email": "user@example.com",
    "emailVerified": true,
    "verifiedAt": "2025-01-15T10:30:00.000Z"
  }
}
```

**Response (Not Verified):**
```json
{
  "success": true,
  "message": "Email verification status retrieved",
  "data": {
    "email": "user@example.com",
    "emailVerified": false,
    "verifiedAt": null
  }
}
```

**Notes:**
- Returns current verification status
- Shows when email was verified (if applicable)
- Useful for conditional UI rendering

---

## Chat Service

**Base URL**: `http://localhost:3002/api/chat`

All conversation and message endpoints require authentication (JWT cookie).

---

## Test Endpoints

### Service Health Check

**GET** `/test`

Verifies chat service is running.

**Response:**
```json
{
  "success": true,
  "message": "Chat service is working! 🚀",
  "data": {
    "socketIOAvailable": true,
    "environment": "development"
  }
}
```

---

## RAG Integration Test Endpoints

### RAG Health Check

**GET** `/rag/health`

Checks RAG API connectivity.

**Response:**
```json
{
  "success": true,
  "message": "RAG API health check completed",
  "data": {
    "status": "healthy",
    "postgresConnected": true,
    "neo4jConnected": true
  }
}
```

---

### RAG Query (Document Retrieval)

**POST** `/rag/query`

Retrieves documents using vector search with RBAC filtering.

**Auth**: Optional (uses `optionalAuth` middleware)
- **Without auth**: Returns public documents (guest scope)
- **With auth**: Returns documents based on user role

**Request:**
```json
{
  "query": "What is the vacation policy?",
  "topK": 5,
  "minScore": 0.6
}
```

**Response (Authenticated as EMPLOYEE):**
```json
{
  "success": true,
  "message": "RAG query completed",
  "data": {
    "results": [
      {
        "id": "doc_001",
        "content": "Vacation policy content...",
        "score": 0.87,
        "doc_type": "policy",
        "metadata": {
          "title": "Vacation Policy",
          "scope": "employee"
        }
      }
    ],
    "count": 3,
    "query_time": 0.214
  }
}
```

**RBAC Behavior:**
- `GUEST` → sees public documents only
- `EMPLOYEE` → sees public + employee documents
- `EXECUTIVE` → sees all documents
- `COMPANY_ADMIN` → sees all documents (company scope)
- `SUPER_ADMIN` → sees all documents (global scope)

---

### RAG Chat (with LLM)

**POST** `/rag/chat`

Queries documents and generates AI response using LLM.

**Auth**: Optional

**Request:**
```json
{
  "query": "How many vacation days do I get?",
  "profileId": "executive-001",
  "topK": 5,
  "minScore": 0.6
}
```

**Response:**
```json
{
  "success": true,
  "message": "RAG chat completed",
  "data": {
    "response": "Based on company policy, employees receive 15 vacation days...",
    "sources": [
      {
        "id": "doc_001",
        "score": 0.89
      }
    ]
  }
}
```

---

### RAG Profiles

**GET** `/rag/profiles`

Lists available executive AI profiles.

**Response:**
```json
{
  "success": true,
  "data": {
    "profiles": [
      {
        "id": "executive-001",
        "name": "CEO Profile",
        "description": "Strategic decision-making persona"
      }
    ]
  }
}
```

---

## User Preferences Management

### Get User Preferences

**GET** `/preferences`

Retrieves user's chat preferences including default AI profile and RAG settings.

**Auth**: Required

**Response:**
```json
{
  "success": true,
  "message": "Preferences retrieved successfully",
  "data": {
    "preferences": {
      "id": "pref_abc123",
      "userId": "user_xyz789",
      "defaultProfileId": "exec_003_test",
      "defaultTopK": 5,
      "defaultMinScore": 0.6,
      "streamingEnabled": true,
      "theme": "light",
      "language": "en",
      "createdAt": "2025-01-15T10:00:00.000Z",
      "updatedAt": "2025-01-15T10:00:00.000Z"
    }
  }
}
```

**Note**: Preferences are created automatically with defaults if they don't exist.

---

### Update User Preferences

**PATCH** `/preferences`

Updates one or more user preference fields.

**Auth**: Required

**Request:**
```json
{
  "defaultProfileId": "exec_001_test",
  "defaultTopK": 10,
  "defaultMinScore": 0.7,
  "streamingEnabled": false,
  "theme": "dark",
  "language": "es"
}
```

**Available Fields** (all optional):
- `defaultProfileId` (string|null): Default executive AI profile
  - Available: `exec_001_test`, `exec_002_test`, `exec_003_test`, `exec_004_test`
  - Use `GET /api/chat/rag/profiles` to see full list
- `defaultTopK` (integer 1-20): Default number of documents to retrieve
- `defaultMinScore` (float 0-1): Default similarity threshold
- `streamingEnabled` (boolean): Enable word-by-word streaming
- `theme` (string|null): UI theme - "light", "dark", or "auto"
- `language` (string|null): Interface language code (e.g., "en", "es")

**Response:**
```json
{
  "success": true,
  "message": "Preferences updated successfully",
  "data": {
    "preferences": {
      "id": "pref_abc123",
      "userId": "user_xyz789",
      "defaultProfileId": "exec_001_test",
      "defaultTopK": 10,
      "defaultMinScore": 0.7,
      "streamingEnabled": false,
      "theme": "dark",
      "language": "es",
      "createdAt": "2025-01-15T10:00:00.000Z",
      "updatedAt": "2025-01-15T15:30:00.000Z"
    }
  }
}
```

**Validation Errors:**
- `defaultTopK` must be between 1-20
- `defaultMinScore` must be between 0-1
- `theme` must be "light", "dark", or "auto"

---

### Reset Preferences to Defaults

**POST** `/preferences/reset`

Resets all user preferences to system defaults.

**Auth**: Required

**Response:**
```json
{
  "success": true,
  "message": "Preferences reset to defaults successfully",
  "data": {
    "preferences": {
      "id": "pref_abc123",
      "userId": "user_xyz789",
      "defaultProfileId": "exec_003_test",
      "defaultTopK": 5,
      "defaultMinScore": 0.6,
      "streamingEnabled": true,
      "theme": "light",
      "language": "en",
      "createdAt": "2025-01-15T10:00:00.000Z",
      "updatedAt": "2025-01-15T16:00:00.000Z"
    }
  }
}
```

**Default Values:**
- `defaultProfileId`: "exec_003_test" (Yuki Nakamura - CTO)
- `defaultTopK`: 5
- `defaultMinScore`: 0.6
- `streamingEnabled`: true
- `theme`: "light"
- `language`: "en"

---

## Conversation Management

### List Conversations

**GET** `/conversations?limit=20&offset=0`

Retrieves user's conversations with pagination.

**Auth**: Required

**Query Parameters:**
- `limit` (optional): 1-100, default 20
- `offset` (optional): default 0

**Response:**
```json
{
  "success": true,
  "message": "Conversations retrieved successfully",
  "data": {
    "conversations": [
      {
        "id": "conv_abc123",
        "title": "Vacation Policy Discussion",
        "messageCount": 12,
        "lastMessagePreview": "Thank you for the information...",
        "lastMessageAt": "2025-01-15T14:30:00.000Z",
        "createdAt": "2025-01-15T10:00:00.000Z"
      }
    ],
    "pagination": {
      "total": 45,
      "limit": 20,
      "offset": 0,
      "hasMore": true
    }
  }
}
```

---

### Create Conversation

**POST** `/conversations`

Creates a new conversation.

**Auth**: Required

**Request:**
```json
{
  "title": "Benefits Questions"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Conversation created successfully",
  "data": {
    "id": "conv_xyz789",
    "title": "Benefits Questions",
    "messageCount": 0,
    "createdAt": "2025-01-15T15:00:00.000Z"
  }
}
```

**Note**: Title is optional, defaults to "New Chat"

---

### Get Conversation

**GET** `/conversations/:id`

Retrieves a specific conversation.

**Auth**: Required (must own conversation)

**Response:**
```json
{
  "success": true,
  "message": "Conversation retrieved successfully",
  "data": {
    "id": "conv_abc123",
    "title": "Vacation Policy Discussion",
    "messageCount": 12,
    "lastMessageAt": "2025-01-15T14:30:00.000Z",
    "createdAt": "2025-01-15T10:00:00.000Z",
    "updatedAt": "2025-01-15T14:30:00.000Z"
  }
}
```

---

### Update Conversation

**PATCH** `/conversations/:id`

Updates conversation details (currently title only).

**Auth**: Required (must own conversation)

**Request:**
```json
{
  "title": "Updated Title - Vacation & Benefits"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Conversation updated successfully",
  "data": {
    "id": "conv_abc123",
    "title": "Updated Title - Vacation & Benefits",
    "updatedAt": "2025-01-15T15:30:00.000Z"
  }
}
```

---

### Delete Conversation

**DELETE** `/conversations/:id`

Deletes conversation and all associated messages (cascade).

**Auth**: Required (must own conversation)

**Response:**
```json
{
  "success": true,
  "message": "Conversation deleted successfully",
  "data": {
    "deleted": true,
    "conversationId": "conv_abc123"
  }
}
```

---

## Message Management

### Get Messages

**GET** `/conversations/:id/messages?limit=50&offset=0`

Retrieves messages for a conversation with pagination.

**Auth**: Required (must own conversation)

**Query Parameters:**
- `limit` (optional): 1-100, default 50
- `offset` (optional): default 0

**Response:**
```json
{
  "success": true,
  "message": "Messages retrieved successfully",
  "data": {
    "messages": [
      {
        "id": "msg_001",
        "role": "user",
        "content": "What is the vacation policy?",
        "createdAt": "2025-01-15T14:00:00.000Z"
      },
      {
        "id": "msg_002",
        "role": "assistant",
        "content": "Based on the information I found:\n\nEmployees receive 15 vacation days...",
        "createdAt": "2025-01-15T14:00:05.000Z",
        "metadata": {
          "resultsCount": 3,
          "topScore": 0.87,
          "sources": [{"id": "doc_001", "type": "policy", "score": 0.87}]
        },
        "processingTime": 258
      }
    ],
    "pagination": {
      "total": 12,
      "limit": 50,
      "offset": 0,
      "hasMore": false
    }
  }
}
```

**Message Roles**: `user`, `assistant`, `system`

---

### Send Message

**POST** `/conversations/:id/messages`

Sends a message and receives AI response via RAG integration.

**Auth**: Required (must own conversation)

**Request:**
```json
{
  "content": "How many vacation days do managers get?",
  "ragOptions": {
    "topK": 5,
    "minScore": 0.6,
    "profileId": "exec_003_test",
    "forcePath": "standard"
  }
}
```

**ragOptions Fields** (all optional):
- `topK` (number, default: 5): Number of documents to retrieve from RAG
- `minScore` (number, default: 0.6): Minimum similarity score (0-1)
- `profileId` (string, default: "exec_003_test"): Executive profile for AI persona
  - Available profiles: `exec_001_test`, `exec_002_test`, `exec_003_test`, `exec_004_test`
  - Get full list via `GET /api/chat/rag/profiles`
- `forcePath` (string, optional): Force specific LLM path
  - Options: "fast", "standard", "agentic"
  - If not specified, auto-routes based on query complexity

**Response:**
```json
{
  "success": true,
  "message": "Message sent successfully",
  "data": {
    "userMessage": {
      "id": "msg_003",
      "role": "user",
      "content": "How many vacation days do managers get?",
      "createdAt": "2025-01-15T14:30:00.000Z"
    },
    "assistantMessage": {
      "id": "msg_004",
      "role": "assistant",
      "content": "Based on the information I found:\n\nManagers receive 20 vacation days...",
      "createdAt": "2025-01-15T14:30:05.000Z",
      "metadata": {
        "resultsCount": 2,
        "topScore": 0.91,
        "sources": [{"id": "doc_005", "type": "policy", "score": 0.91}],
        "processingTime": 214
      },
      "processingTime": 258
    },
    "processingTime": 258
  }
}
```

**RAG Integration Flow:**
1. User message saved to database
2. **User preferences fetched** (default profile, topK, minScore)
3. Last 10 messages retrieved for context
4. RAG API queried with:
   - User's role (RBAC filtering)
   - Profile from: `ragOptions.profileId` > user preferences > "exec_003_test"
   - TopK from: `ragOptions.topK` > user preferences > 5
   - MinScore from: `ragOptions.minScore` > user preferences > 0.6
5. AI response generated from retrieved documents
6. Assistant message saved with metadata
7. Conversation `lastMessageAt` updated
8. Both messages returned

**Priority Order for RAG Parameters:**
1. **ragOptions** (if provided in request) - highest priority
2. **User Preferences** (from `/api/chat/preferences`)
3. **System Defaults** - fallback if preferences unavailable

**Fallback Responses:**
- **No documents found**: "I couldn't find specific information about that in my knowledge base. Could you rephrase your question or ask something else?"
- **RAG API error**: "I'm having trouble accessing my knowledge base right now. Please try again in a moment."

---

## WebSocket Real-time Chat

**WebSocket URL**: `ws://localhost:3002` or `http://localhost:3002`

**Protocol**: Socket.IO

### Connection

WebSocket connections require authentication via JWT token.

**Authentication Methods** (in order of preference):

1. **Auth object** (recommended):
```javascript
const socket = io("http://localhost:3002", {
  auth: {
    token: "your_jwt_token_here"
  }
});
```

2. **Query parameter**:
```javascript
const socket = io("http://localhost:3002?token=your_jwt_token_here");
```

3. **Cookie** (automatic if logged in via browser):
```javascript
const socket = io("http://localhost:3002", {
  withCredentials: true
});
```

### Connection Events

#### `connected`
Emitted when successfully connected and authenticated.

**Server → Client:**
```javascript
{
  "success": true,
  "message": "Connected to chat service",
  "data": {
    "socketId": "abc123",
    "user": {
      "id": "user_id",
      "username": "john_doe",
      "role": "EMPLOYEE"
    }
  },
  "timestamp": "2025-01-15T10:00:00.000Z"
}
```

#### `connect_error`
Emitted when connection fails (usually authentication error).

**Server → Client:**
```javascript
Error: "Authentication token required"
// or
Error: "Invalid or expired token"
```

---

### Chat Events

#### `chat:join` - Join Conversation Room
Join a conversation to receive real-time messages.

**Client → Server:**
```javascript
socket.emit("chat:join", {
  conversationId: "conv_abc123"
}, (response) => {
  console.log(response);
});
```

**Callback Response:**
```javascript
{
  "success": true,
  "message": "Joined conversation successfully",
  "data": {
    "conversationId": "conv_abc123",
    "conversation": {
      "id": "conv_abc123",
      "title": "Project Discussion"
    }
  }
}
```

**Broadcast to Room (except sender):**
```javascript
// Event: user:joined
{
  "userId": "user_id",
  "username": "john_doe",
  "timestamp": "2025-01-15T10:00:00.000Z"
}
```

---

#### `chat:leave` - Leave Conversation Room
Leave a conversation room.

**Client → Server:**
```javascript
socket.emit("chat:leave", {
  conversationId: "conv_abc123"
}, (response) => {
  console.log(response);
});
```

**Callback Response:**
```javascript
{
  "success": true,
  "message": "Left conversation successfully"
}
```

**Broadcast to Room (except sender):**
```javascript
// Event: user:left
{
  "userId": "user_id",
  "username": "john_doe",
  "timestamp": "2025-01-15T10:00:00.000Z"
}
```

---

#### `chat:message` - Send Message
Send a message in a conversation (includes RAG integration).

**Client → Server:**
```javascript
socket.emit("chat:message", {
  conversationId: "conv_abc123",
  content: "What is the vacation policy?",
  ragOptions: {
    topK: 5,
    minScore: 0.6,
    profileId: "exec_003_test",  // Optional: AI persona
    forcePath: "standard"  // Optional: fast|standard|agentic
  }
}, (response) => {
  console.log(response);
});
```

**ragOptions** (all fields optional):
- All fields same as HTTP endpoint (see Send Message section lines 728-737 for details)
- **Priority order**: ragOptions > user preferences > system defaults
- If omitted, uses user preferences from `/api/chat/preferences`
- Allows per-message customization while respecting user defaults

**Callback Response:**
```javascript
{
  "success": true,
  "message": "Message sent successfully",
  "data": {
    "userMessage": {
      "id": "msg_001",
      "role": "user",
      "content": "What is the vacation policy?",
      "createdAt": "2025-01-15T10:00:00.000Z"
    },
    "assistantMessage": {
      "id": "msg_002",
      "role": "assistant",
      "content": "Based on the information I found...",
      "createdAt": "2025-01-15T10:00:05.000Z",
      "metadata": {
        "resultsCount": 3,
        "topScore": 0.87,
        "sources": [...]
      },
      "processingTime": 258
    },
    "processingTime": 258
  }
}
```

**Broadcast Events:**

The server emits **three separate events** for real-time message delivery:

##### Event: `message:user`
Emitted immediately when user message is saved.

```javascript
{
  "conversationId": "conv_abc123",
  "message": {
    "id": "msg_001",
    "role": "user",
    "content": "What is the vacation policy?",
    "createdAt": "2025-01-15T10:00:00.000Z"
  },
  "timestamp": "2025-01-15T10:00:00.000Z"
}
```

##### Event: `message:stream`
Emitted multiple times during AI response generation (word-by-word streaming).

```javascript
{
  "conversationId": "conv_abc123",
  "messageId": "msg_002",
  "chunk": "Based ",  // Current word/chunk
  "accumulated": "Based ",  // All content so far
  "isComplete": false,
  "timestamp": "2025-01-15T10:00:01.000Z"
}
```

**Streaming Characteristics:**
- ~30ms delay between chunks (word-by-word)
- `accumulated` contains full text built up over time
- Allows real-time typewriter effect in UI

##### Event: `message:complete`
Emitted once when AI response is fully generated.

```javascript
{
  "conversationId": "conv_abc123",
  "message": {
    "id": "msg_002",
    "role": "assistant",
    "content": "Based on the information I found...",  // Complete response
    "createdAt": "2025-01-15T10:00:05.000Z",
    "metadata": {
      "citationsCount": 3,
      "sourcesCount": 2,
      "citations": [...],
      "sources": [...],
      "llmPath": "standard",
      "processingTime": 4520
    }
  },
  "processingTime": 4520,
  "timestamp": "2025-01-15T10:00:05.000Z"
}
```

##### Event: `message:received` (Legacy)
Emitted for backwards compatibility after message is complete.

```javascript
{
  "conversationId": "conv_abc123",
  "userMessage": { ... },
  "assistantMessage": { ... },
  "timestamp": "2025-01-15T10:00:05.000Z"
}
```

**Note**: Modern clients should use `message:user` + `message:stream` + `message:complete` for the best UX.

---

#### `chat:typing` - Typing Indicator
Notify others when user is typing.

**Client → Server:**
```javascript
socket.emit("chat:typing", {
  conversationId: "conv_abc123",
  isTyping: true
});
```

**Broadcast to Room (except sender):**
```javascript
// Event: user:typing
{
  "userId": "user_id",
  "username": "john_doe",
  "conversationId": "conv_abc123",
  "isTyping": true,
  "timestamp": "2025-01-15T10:00:00.000Z"
}
```

**No callback** - Fire and forget event for performance.

---

#### `chat:get-online-users` - Get Online Users
Get list of users currently in a conversation room.

**Client → Server:**
```javascript
socket.emit("chat:get-online-users", {
  conversationId: "conv_abc123"
}, (response) => {
  console.log(response);
});
```

**Callback Response:**
```javascript
{
  "success": true,
  "data": {
    "conversationId": "conv_abc123",
    "onlineUsers": [
      {
        "userId": "user1",
        "username": "john_doe",
        "socketId": "socket123"
      },
      {
        "userId": "user2",
        "username": "jane_smith",
        "socketId": "socket456"
      }
    ],
    "count": 2
  }
}
```

---

#### `ping` / `pong` - Connection Health Check
Test connection health.

**Client → Server:**
```javascript
socket.emit("ping");
```

**Server → Client:**
```javascript
// Event: pong
{
  "timestamp": 1234567890,
  "userId": "user_id"
}
```

---

### Complete WebSocket Example

```javascript
const io = require("socket.io-client");

// Connect with authentication
const socket = io("http://localhost:3002", {
  auth: {
    token: accessToken
  }
});

// Connection events
socket.on("connect", () => {
  console.log("Connected:", socket.id);
});

socket.on("connected", (data) => {
  console.log("Welcome:", data.data.user.username);

  // Join a conversation
  socket.emit("chat:join", { conversationId: "conv_123" }, (res) => {
    if (res.success) {
      console.log("Joined conversation");

      // Send a message
      socket.emit("chat:message", {
        conversationId: "conv_123",
        content: "Hello everyone!"
      }, (msgRes) => {
        console.log("Message sent:", msgRes.data.userMessage.id);
      });
    }
  });
});

// Listen for user messages
socket.on("message:user", (data) => {
  console.log("User message:", data.message.content);
});

// Listen for streaming AI response (real-time)
let streamBuffer = "";
socket.on("message:stream", (data) => {
  streamBuffer = data.accumulated;
  process.stdout.write(data.chunk);  // Display word-by-word
});

// Listen for complete AI message
socket.on("message:complete", (data) => {
  console.log("\n\nComplete message:", data.message.id);
  console.log("Processing time:", data.processingTime + "ms");
  console.log("Citations:", data.message.metadata?.citationsCount);
});

// Legacy event (backwards compatibility)
socket.on("message:received", (data) => {
  console.log("Message exchange complete");
});

// Listen for typing indicators
socket.on("user:typing", (data) => {
  console.log(`${data.username} is ${data.isTyping ? "typing" : "stopped typing"}`);
});

// Handle errors
socket.on("connect_error", (error) => {
  console.error("Connection failed:", error.message);
});
```

---

## Error Responses

All endpoints return consistent error format:

```json
{
  "success": false,
  "error": {
    "message": "Conversation not found",
    "code": "NOT_FOUND"
  },
  "timestamp": "2025-01-15T14:30:00.000Z"
}
```

**Common HTTP Status Codes:**
- `400` - Validation error (missing fields, invalid format)
- `401` - Authentication required or invalid token
- `403` - Forbidden (lack of permissions)
- `404` - Resource not found
- `500` - Internal server error

**Common Error Codes:**
- `VALIDATION_ERROR` - Input validation failed
- `AUTHENTICATION_ERROR` - Invalid or missing JWT token
- `NOT_FOUND` - Resource doesn't exist
- `UNAUTHORIZED` - User doesn't own the resource
- `INTERNAL_ERROR` - Server error

---

## RBAC Summary

**Role Hierarchy** (access levels):
1. **GUEST** → Public documents only
2. **EMPLOYEE** → Public + employee-level documents
3. **EXECUTIVE** → All documents
4. **COMPANY_ADMIN** → All documents (company scope)
5. **SUPER_ADMIN** → All documents (global scope, highest access)

**Where RBAC Applies:**
- RAG query endpoints (`/rag/query`, `/rag/chat`)
- Message send endpoint (uses RAG with user's role)
- Document retrieval filtered at RAG vector search layer

**How to Test RBAC:**
1. **Login as admin** (username: `admin`, password: `Admin@123456`)
2. **Create test users** by registering (all will be EMPLOYEE by default)
3. **Promote users** to different roles using the admin endpoint: `PUT /api/users/:userId/role`
4. **Login with each user** to get their JWT tokens
5. **Query the same question** via `/rag/query` or send messages
6. **Compare the documents returned** (higher roles see more documents)

---

## Authentication Flow

1. **Register**: `POST /api/users/register` → JWT tokens in cookies (role: EMPLOYEE)
2. **Login**: `POST /api/users/login` → JWT tokens in cookies
3. **Access Protected Routes**: Cookies automatically sent with requests
4. **Token Expiry**: Access token expires in 15m, refresh token in 7d
5. **Refresh**: `POST /api/users/refresh` → New access token
6. **Logout**: `POST /api/users/logout` → Cookies cleared
7. **Role Management** (Admin Only): `PUT /api/users/:userId/role` → Update user role

**Cookie Names:**
- `firstweek_avatar_access_token` - Short-lived (15 minutes)
- `firstweek_avatar_refresh_token` - Long-lived (7 days)

**Attributes**: httpOnly, secure (production), sameSite=Lax

---

## Testing Tips

### Test RBAC with curl:

```bash
# Step 1: Register a new user (automatically assigned EMPLOYEE role)
curl -X POST http://localhost:3001/api/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "email":"emp@test.com",
    "password":"TestPass123!",
    "username":"emp_user",
    "firstName":"Employee",
    "lastName":"User"
  }' \
  -c employee_cookies.txt

# Step 2: Login as admin to promote user
curl -X POST http://localhost:3001/api/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "identifier":"admin",
    "password":"Admin@123456"
  }' \
  -c admin_cookies.txt

# Step 3: Get user ID from registration response or /me endpoint
curl -X GET http://localhost:3001/api/users/ \
  -H "Content-Type: application/json" \
  -b admin_cookies.txt

# Step 4: Promote user to EXECUTIVE role
curl -X PUT http://localhost:3001/api/users/clx_user_id/role \
  -H "Content-Type: application/json" \
  -b admin_cookies.txt \
  -d '{"role":"EXECUTIVE"}'

# Step 5: Login as the promoted user
curl -X POST http://localhost:3001/api/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "identifier":"emp@test.com",
    "password":"TestPass123!"
  }' \
  -c executive_cookies.txt

# Step 6: Query RAG with different role levels
curl -X POST http://localhost:3002/api/chat/rag/query \
  -H "Content-Type: application/json" \
  -b executive_cookies.txt \
  -d '{"query":"vacation policy"}'

# Send message (full RAG integration)
curl -X POST http://localhost:3002/api/chat/conversations/conv_id/messages \
  -H "Content-Type: application/json" \
  -b executive_cookies.txt \
  -d '{"content":"How many vacation days?"}'
```

### Test Anonymous Access:

```bash
# Query RAG without authentication (guest access)
curl -X POST http://localhost:3002/api/chat/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query":"public information"}'
```

### Test Role-Based Access (Complete Flow):

```bash
#!/bin/bash
# Script to create users with different roles for RBAC testing

# Step 1: Login as admin
echo "=== Logging in as admin ==="
curl -X POST http://localhost:3001/api/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "identifier":"admin",
    "password":"Admin@123456"
  }' \
  -c admin_cookies.txt

# Step 2: Create test users (all start as EMPLOYEE)
echo -e "\n=== Creating test users ==="
for role in guest employee manager executive; do
  echo "Creating ${role} user..."
  curl -X POST http://localhost:3001/api/users/register \
    -H "Content-Type: application/json" \
    -d "{
      \"email\":\"${role}@test.com\",
      \"password\":\"TestPass123!\",
      \"username\":\"${role}_user\",
      \"firstName\":\"${role^}\",
      \"lastName\":\"User\"
    }" > ${role}_response.json
done

# Step 3: Get all users to find their IDs
echo -e "\n=== Getting user IDs ==="
curl -X GET http://localhost:3001/api/users/ \
  -H "Content-Type: application/json" \
  -b admin_cookies.txt \
  | jq '.data.users[] | {id: .id, username: .username, role: .role}'

# Step 4: Manually update roles using the user IDs from above
# Replace <USER_ID> with actual IDs from the previous step
echo -e "\n=== Update roles manually using the IDs from above ==="
echo "Example:"
echo "curl -X PUT http://localhost:3001/api/users/<GUEST_USER_ID>/role \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -b admin_cookies.txt \\"
echo "  -d '{\"role\":\"GUEST\"}'"
```

**Note**: After creating users, you must manually update their roles using the admin endpoint with the actual user IDs retrieved from the response.

---

## Security Best Practices

### Role-Based Access Control (RBAC)

**Security Improvements (2025-11-01):**

1. **Registration Security**
   - ✅ Users can no longer self-assign roles during registration
   - ✅ All new accounts automatically receive `EMPLOYEE` role
   - ✅ Only admins (EXECUTIVE role) can modify user roles
   - ✅ Prevents privilege escalation vulnerabilities

2. **Admin Role Management**
   - ✅ Role updates require EXECUTIVE privileges
   - ✅ Admins cannot modify their own role (prevents self-demotion)
   - ✅ All role changes are audit-logged with:
     - Admin user ID and username
     - Target user ID and username
     - Old role → New role
     - Timestamp and IP address

3. **Default Admin Account**
   - ⚠️ Change default password immediately: `Admin@123456`
   - ⚠️ Use strong, unique passwords (min 8 chars, uppercase, lowercase, number, special char)
   - ⚠️ Enable email verification for admin account
   - ⚠️ Never commit credentials to version control

### Authentication Security

**Cookie Security:**
- `httpOnly`: Prevents JavaScript access (XSS protection)
- `secure`: HTTPS-only in production
- `sameSite`: CSRF protection (Lax mode)
- Domain-specific: Scoped to application domain

**Token Lifecycle:**
- Access token: 15 minutes (short-lived)
- Refresh token: 7 days (long-lived)
- Automatic rotation on refresh
- Session invalidation on logout

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character
- Hashed with bcrypt (salt rounds: 10)

### API Security Checklist

**Before Production:**
- [ ] Change default admin password
- [ ] Enable HTTPS/TLS for all endpoints
- [ ] Configure CORS for production domains
- [ ] Enable rate limiting (default: 60 req/min per user)
- [ ] Set secure cookie attributes (`secure: true`)
- [ ] Review and update JWT secret keys
- [ ] Enable email verification for new accounts
- [ ] Configure proper logging and monitoring
- [ ] Set up IP-based session validation if needed
- [ ] Review and test all admin endpoints

**Role Assignment Workflow:**
```
New User Registration
        ↓
   EMPLOYEE role
   (automatic)
        ↓
Admin Review Required
        ↓
Admin Login (EXECUTIVE)
        ↓
PUT /users/:userId/role
        ↓
Role Updated + Audit Log
        ↓
User Re-login (new token with new role)
```

---

## Performance Metrics

### HTTP Endpoints
- **Login/Register**: ~200-300ms
- **Conversation CRUD**: ~50-150ms
- **Message Retrieval**: ~100-200ms
- **Message Send (with RAG)**: ~200-400ms
  - RAG query: ~150-250ms
  - Database ops: ~50-150ms
- **RAG Query**: ~150-300ms (with cache hit: ~50-100ms)

### WebSocket
- **Connection Time**: ~50-100ms
- **Join Room**: ~20-50ms
- **Message Send (with RAG)**: ~180-350ms
- **Typing Indicator**: <10ms (fire and forget)
- **Broadcast Latency**: <20ms (within same server)

---

## Related Documentation

- **Directory Structure**: See `DIRECTORY_STRUCTURE.md`
- **RBAC Testing**: See `TESTING_RBAC.md`
- **Chat API Testing**: See `TESTING_CHAT_API.md`
