/**
 * User Test Fixtures
 * Mock user data for testing
 */

/**
 * Mock authenticated user
 */
export const mockUser = {
  id: 'user-123',
  username: 'testuser',
  email: 'test@example.com',
  firstName: 'Test',
  lastName: 'User',
  profilePic: 'https://example.com/avatar.jpg',
  isActive: true,
  isEmailVerified: true,
  role: 'user',
  createdAt: '2024-01-01T00:00:00.000Z',
  updatedAt: '2024-01-01T00:00:00.000Z',
};

/**
 * Mock user with unverified email
 */
export const mockUnverifiedUser = {
  ...mockUser,
  id: 'user-456',
  email: 'unverified@example.com',
  isEmailVerified: false,
};

/**
 * Mock admin user
 */
export const mockAdminUser = {
  ...mockUser,
  id: 'admin-123',
  username: 'adminuser',
  email: 'admin@example.com',
  role: 'admin',
};

/**
 * Mock deactivated user
 */
export const mockDeactivatedUser = {
  ...mockUser,
  id: 'user-789',
  email: 'deactivated@example.com',
  isActive: false,
};

/**
 * Mock registration data
 */
export const mockRegisterData = {
  username: 'newuser',
  email: 'newuser@example.com',
  firstName: 'New',
  lastName: 'User',
  password: 'SecurePassword123!',
};

/**
 * Mock login credentials
 */
export const mockLoginCredentials = {
  identifier: 'testuser',
  password: 'SecurePassword123!',
};

/**
 * Mock login with email
 */
export const mockLoginWithEmail = {
  identifier: 'test@example.com',
  password: 'SecurePassword123!',
};

/**
 * Mock invalid credentials
 */
export const mockInvalidCredentials = {
  identifier: 'wronguser',
  password: 'wrongpassword',
};

/**
 * Mock update profile data
 */
export const mockUpdateProfileData = {
  firstName: 'Updated',
  lastName: 'Name',
  profilePic: 'https://example.com/new-avatar.jpg',
};

/**
 * Mock change password data
 */
export const mockChangePasswordData = {
  currentPassword: 'OldPassword123!',
  newPassword: 'NewPassword123!',
  confirmPassword: 'NewPassword123!',
};

/**
 * Mock session data
 */
export const mockSession = {
  id: 'session-123',
  userId: 'user-123',
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0',
  ipAddress: '192.168.1.1',
  createdAt: '2024-01-01T00:00:00.000Z',
  expiresAt: '2024-01-02T00:00:00.000Z',
  isCurrent: true,
};

/**
 * Mock multiple sessions
 */
export const mockSessions = [
  mockSession,
  {
    ...mockSession,
    id: 'session-456',
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0) Safari/14.0',
    ipAddress: '192.168.1.2',
    isCurrent: false,
  },
  {
    ...mockSession,
    id: 'session-789',
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Firefox/89.0',
    ipAddress: '192.168.1.3',
    isCurrent: false,
  },
];

/**
 * Mock session stats
 */
export const mockSessionStats = {
  total: 3,
  active: 3,
  expired: 0,
};
