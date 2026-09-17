/**
 * Auth Store Unit Tests
 * Tests for Zustand auth store actions and state management
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { initializePrivateAuth, useAuthStore } from '../authStore';
import * as api from '../../services/api';
import {
  mockUser,
  mockDeactivatedUser,
  mockLoginCredentials,
  mockRegisterData,
} from '../../test/fixtures/users';
import {
  loginSuccessResponse,
  registerSuccessResponse,
  getMeSuccessResponse,
  getMeDeactivatedResponse,
  logoutSuccessResponse,
  logoutAllSuccessResponse,
  refreshSuccessResponse,
} from '../../test/fixtures/apiResponses';
import { simulateBroadcast } from '../../test/utils/testUtils';

// Mock the API module
jest.mock('../../services/api');

describe('authStore', () => {
  let cleanupAuth;
  beforeEach(async () => {
    // Reset store state before each test
    const { setState } = useAuthStore;
    setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });

    // Clear all mocks
    jest.clearAllMocks();
    api.getMe.mockResolvedValueOnce({ data: { user: null } });
    await act(async () => { cleanupAuth = initializePrivateAuth(); });
    jest.clearAllMocks();
  });
  afterEach(() => cleanupAuth());

  describe('Initial State', () => {
    it('should have correct initial state', () => {
      const { result } = renderHook(() => useAuthStore());

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isLoading).toBe(false);
    });

    it('should have all required actions', () => {
      const { result } = renderHook(() => useAuthStore());

      expect(typeof result.current.checkAuth).toBe('function');
      expect(typeof result.current.login).toBe('function');
      expect(typeof result.current.signup).toBe('function');
      expect(typeof result.current.logout).toBe('function');
      expect(typeof result.current.logoutAllDevices).toBe('function');
      expect(typeof result.current.refreshToken).toBe('function');
      expect(typeof result.current.refreshUser).toBe('function');
      expect(typeof result.current.setLoading).toBe('function');
    });
  });

  describe('checkAuth', () => {
    it('should set user and isAuthenticated on successful auth check', async () => {
      api.getMe.mockResolvedValueOnce(getMeSuccessResponse);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.checkAuth();
      });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isAuthenticated).toBe(true);
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.getMe).toHaveBeenCalledTimes(1);
    });

    it('should clear user if account is deactivated', async () => {
      api.getMe.mockResolvedValueOnce(getMeDeactivatedResponse);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.checkAuth();
      });

      await waitFor(() => {
        expect(result.current.user).toBeNull();
        expect(result.current.isAuthenticated).toBe(false);
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('should clear user on failed auth check', async () => {
      api.getMe.mockRejectedValueOnce(new Error('Unauthorized'));

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.checkAuth();
      });

      await waitFor(() => {
        expect(result.current.user).toBeNull();
        expect(result.current.isAuthenticated).toBe(false);
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('should handle network errors gracefully', async () => {
      api.getMe.mockRejectedValueOnce(new Error('Network Error'));

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.checkAuth();
      });

      await waitFor(() => {
        expect(result.current.user).toBeNull();
        expect(result.current.isAuthenticated).toBe(false);
      });
    });
  });

  describe('login', () => {
    it('should login user successfully', async () => {
      api.login.mockResolvedValue(loginSuccessResponse);
      api.getMe.mockResolvedValue(getMeSuccessResponse);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.login(
          mockLoginCredentials.identifier,
          mockLoginCredentials.password
        );
      });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isAuthenticated).toBe(true);
      });

      expect(api.login).toHaveBeenCalledWith(
        mockLoginCredentials.identifier,
        mockLoginCredentials.password
      );
      expect(api.getMe).toHaveBeenCalled();
    });

    it('should throw error for deactivated account', async () => {
      api.login.mockResolvedValueOnce({
        success: true,
        data: { user: mockDeactivatedUser },
      });

      const { result } = renderHook(() => useAuthStore());

      await expect(
        act(async () => {
          await result.current.login('test@example.com', 'password');
        })
      ).rejects.toThrow(
        'Your account has been deactivated. Please contact support to reactivate your account.'
      );

      expect(result.current.isAuthenticated).toBe(false);
    });

    it('should sanitize identifier before login', async () => {
      api.login.mockResolvedValueOnce(loginSuccessResponse);
      api.getMe.mockResolvedValueOnce(getMeSuccessResponse);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.login('<script>alert("xss")</script>', 'password');
      });

      expect(api.login).toHaveBeenCalledWith(
        expect.not.stringContaining('<script>'),
        'password'
      );
    });

    it('should broadcast login event to other tabs', async () => {
      api.login.mockResolvedValueOnce(loginSuccessResponse);
      api.getMe.mockResolvedValueOnce(getMeSuccessResponse);

      const postMessageSpy = jest.spyOn(
        global.BroadcastChannel.prototype,
        'postMessage'
      );

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.login('testuser', 'password');
      });

      await waitFor(() => {
        expect(postMessageSpy).toHaveBeenCalledWith({ type: 'login' });
      });
    });

    it('should handle login errors', async () => {
      const errorMessage = 'Invalid credentials';
      api.login.mockRejectedValueOnce(new Error(errorMessage));

      const { result } = renderHook(() => useAuthStore());

      await expect(
        act(async () => {
          await result.current.login('wronguser', 'wrongpassword');
        })
      ).rejects.toThrow(errorMessage);

      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('signup', () => {
    it('should signup user successfully', async () => {
      api.register.mockResolvedValueOnce(registerSuccessResponse);
      api.getMe.mockResolvedValueOnce(getMeSuccessResponse);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.signup(mockRegisterData);
      });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isAuthenticated).toBe(true);
      });

      expect(api.register).toHaveBeenCalledWith(
        expect.objectContaining({
          username: mockRegisterData.username,
          email: mockRegisterData.email,
          firstName: mockRegisterData.firstName,
          lastName: mockRegisterData.lastName,
        })
      );
      expect(api.getMe).toHaveBeenCalled();
    });

    it('should sanitize user data before signup', async () => {
      api.register.mockResolvedValueOnce(registerSuccessResponse);
      api.getMe.mockResolvedValueOnce(getMeSuccessResponse);

      const { result } = renderHook(() => useAuthStore());

      const maliciousData = {
        username: '<script>xss</script>',
        email: 'test@example.com',
        firstName: '<b>Evil</b>',
        lastName: '<i>User</i>',
        password: 'password',
      };

      await act(async () => {
        await result.current.signup(maliciousData);
      });

      expect(api.register).toHaveBeenCalledWith(
        expect.objectContaining({
          username: expect.not.stringContaining('<script>'),
          firstName: expect.not.stringContaining('<b>'),
          lastName: expect.not.stringContaining('<i>'),
        })
      );
    });

    it('should broadcast signup event to other tabs', async () => {
      api.register.mockResolvedValueOnce(registerSuccessResponse);
      api.getMe.mockResolvedValueOnce(getMeSuccessResponse);

      const postMessageSpy = jest.spyOn(
        global.BroadcastChannel.prototype,
        'postMessage'
      );

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.signup(mockRegisterData);
      });

      await waitFor(() => {
        expect(postMessageSpy).toHaveBeenCalledWith({ type: 'signup' });
      });
    });

    it('should handle signup errors', async () => {
      const errorMessage = 'Email already exists';
      api.register.mockRejectedValueOnce(new Error(errorMessage));

      const { result } = renderHook(() => useAuthStore());

      await expect(
        act(async () => {
          await result.current.signup(mockRegisterData);
        })
      ).rejects.toThrow(errorMessage);

      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('logout', () => {
    it('should logout user successfully', async () => {
      api.logout.mockResolvedValueOnce(logoutSuccessResponse);

      const { result } = renderHook(() => useAuthStore());

      // Set initial authenticated state
      act(() => {
        useAuthStore.setState({
          user: mockUser,
          isAuthenticated: true,
        });
      });

      await act(async () => {
        await result.current.logout();
      });

      await waitFor(() => {
        expect(result.current.user).toBeNull();
        expect(result.current.isAuthenticated).toBe(false);
      });

      expect(api.logout).toHaveBeenCalledTimes(1);
    });

    it('should broadcast logout event to other tabs', async () => {
      api.logout.mockResolvedValueOnce(logoutSuccessResponse);

      const postMessageSpy = jest.spyOn(
        global.BroadcastChannel.prototype,
        'postMessage'
      );

      const { result } = renderHook(() => useAuthStore());

      act(() => {
        useAuthStore.setState({
          user: mockUser,
          isAuthenticated: true,
        });
      });

      await act(async () => {
        await result.current.logout();
      });

      await waitFor(() => {
        expect(postMessageSpy).toHaveBeenCalledWith({ type: 'logout' });
      });
    });

    it('should handle logout errors', async () => {
      const errorMessage = 'Logout failed';
      api.logout.mockRejectedValueOnce(new Error(errorMessage));

      const { result } = renderHook(() => useAuthStore());

      await expect(
        act(async () => {
          await result.current.logout();
        })
      ).rejects.toThrow(errorMessage);
    });
  });

  describe('logoutAllDevices', () => {
    it('should logout from all devices successfully', async () => {
      api.logoutAll.mockResolvedValueOnce(logoutAllSuccessResponse);

      const { result } = renderHook(() => useAuthStore());

      act(() => {
        useAuthStore.setState({
          user: mockUser,
          isAuthenticated: true,
        });
      });

      await act(async () => {
        await result.current.logoutAllDevices();
      });

      await waitFor(() => {
        expect(result.current.user).toBeNull();
        expect(result.current.isAuthenticated).toBe(false);
      });

      expect(api.logoutAll).toHaveBeenCalledTimes(1);
    });

    it('should broadcast logout event after logging out all devices', async () => {
      api.logoutAll.mockResolvedValueOnce(logoutAllSuccessResponse);

      const postMessageSpy = jest.spyOn(
        global.BroadcastChannel.prototype,
        'postMessage'
      );

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.logoutAllDevices();
      });

      await waitFor(() => {
        expect(postMessageSpy).toHaveBeenCalledWith({ type: 'logout' });
      });
    });
  });

  describe('refreshToken', () => {
    it('should refresh token successfully', async () => {
      api.refresh.mockResolvedValueOnce(refreshSuccessResponse);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.refreshToken();
      });

      expect(api.refresh).toHaveBeenCalledTimes(1);
    });

    it('should clear user state on refresh failure', async () => {
      api.refresh.mockRejectedValueOnce(new Error('Invalid refresh token'));

      const { result } = renderHook(() => useAuthStore());

      act(() => {
        useAuthStore.setState({
          user: mockUser,
          isAuthenticated: true,
        });
      });

      await act(async () => {
        await result.current.refreshToken();
      });

      await waitFor(() => {
        expect(result.current.user).toBeNull();
        expect(result.current.isAuthenticated).toBe(false);
      });
    });
  });

  describe('refreshUser', () => {
    it('should refresh user data', async () => {
      api.getMe.mockResolvedValueOnce(getMeSuccessResponse);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.refreshUser();
      });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isAuthenticated).toBe(true);
      });

      expect(api.getMe).toHaveBeenCalledTimes(1);
    });
  });

  describe('setLoading', () => {
    it('should set loading state to true', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setLoading(true);
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('should set loading state to false', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setLoading(true);
      });

      act(() => {
        result.current.setLoading(false);
      });

      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('BroadcastChannel Integration', () => {
    it('should update state when another tab logs in', async () => {
      api.getMe.mockResolvedValueOnce(getMeSuccessResponse);

      renderHook(() => useAuthStore());

      // Simulate login from another tab
      act(() => {
        simulateBroadcast('auth_channel', { type: 'login' });
      });

      // Wait for checkAuth to complete
      await waitFor(() => {
        expect(api.getMe).toHaveBeenCalled();
      });
    });

    it('should clear state when another tab logs out', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        useAuthStore.setState({
          user: mockUser,
          isAuthenticated: true,
        });
      });

      // Simulate logout from another tab
      act(() => {
        simulateBroadcast('auth_channel', { type: 'logout' });
      });

      waitFor(() => {
        expect(result.current.user).toBeNull();
        expect(result.current.isAuthenticated).toBe(false);
      });
    });

    it('should update state when another tab signs up', async () => {
      api.getMe.mockResolvedValueOnce(getMeSuccessResponse);

      renderHook(() => useAuthStore());

      // Simulate signup from another tab
      act(() => {
        simulateBroadcast('auth_channel', { type: 'signup' });
      });

      // Wait for checkAuth to complete
      await waitFor(() => {
        expect(api.getMe).toHaveBeenCalled();
      });
    });
  });
});
