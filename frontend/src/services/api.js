/**
 * API Service for FirstWeek Auth Service
 * Handles all HTTP requests to the backend API using axios
 */
import axios from 'axios';

// Configure axios defaults
axios.defaults.withCredentials = true;

/**
 * Determine the API base URL based on environment
 * - Docker: Use relative path (Vite proxy handles routing)
 * - Local: Use absolute localhost URL
 */
const getApiBaseUrl = () => {
  // Get environment variable
  // Uses import.meta.env (Vite will replace this at build time)
  // For Jest tests, this is mocked in jest.config.cjs
  const envApiUrl = import.meta.env.VITE_API_BASE_URL;

  // If it starts with '/', it's a relative path (Docker/proxy mode)
  if (envApiUrl && envApiUrl.startsWith('/')) {
    return envApiUrl;
  }

  // If it's a full URL, use it directly
  if (
    envApiUrl &&
    (envApiUrl.startsWith('http://') || envApiUrl.startsWith('https://'))
  ) {
    return envApiUrl;
  }

  // Fallback to localhost for local development and tests
  return 'http://localhost:3001/api/users';
};

const API_URL = getApiBaseUrl();

// Create axios instance with default config
const axiosInstance = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Flag to prevent multiple refresh attempts
let isRefreshing = false;
let failedQueue = [];
let isRedirecting = false; // Prevent multiple redirects

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Logout and redirect helper
const logoutAndRedirect = () => {
  if (isRedirecting) return; // Prevent multiple redirects

  isRedirecting = true;
  isRefreshing = false;

  // Clear any stored user state
  localStorage.removeItem('user');
  sessionStorage.clear();

  // Redirect to login only if not already there
  if (!window.location.pathname.includes('/login')) {
    window.location.href = '/login';
  }
};

// Request interceptor
axiosInstance.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling and token refresh
axiosInstance.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const originalRequest = error.config;

    // Handle network errors
    if (error.message === 'Network Error') {
      throw new Error(
        'Unable to connect to server. Please check if the backend is running.'
      );
    }

    // Handle 401 Unauthorized errors (only if not on login/register pages)
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't intercept if already on login or public pages
      const publicPaths = ['/login', '/register', '/forgot-password'];
      const isPublicPage = publicPaths.some((path) =>
        window.location.pathname.includes(path)
      );

      // If on public page, just throw the error
      if (
        isPublicPage ||
        originalRequest.url?.includes('/login') ||
        originalRequest.url?.includes('/register')
      ) {
        const errorMessage =
          error.response?.data?.error?.message ||
          error.response?.data?.message ||
          error.message ||
          'Authentication failed';
        throw new Error(errorMessage);
      }

      // Check if this is a refresh token request that failed
      if (originalRequest.url?.includes('/refresh')) {
        // Refresh token is invalid, logout user
        processQueue(error, null);
        logoutAndRedirect();
        throw new Error('Session expired. Please login again.');
      }

      // If already refreshing, queue this request
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => {
            return axiosInstance(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Try to refresh the token
        await axiosInstance.post('/refresh');

        isRefreshing = false;
        processQueue(null, true);

        // Retry the original request
        return axiosInstance(originalRequest);
      } catch (refreshError) {
        // Refresh failed, logout user
        processQueue(refreshError, null);
        logoutAndRedirect();
        throw new Error('Session expired. Please login again.');
      }
    }

    // Handle 403 Forbidden errors
    if (error.response?.status === 403) {
      throw new Error(
        'Access denied. You do not have permission to perform this action.'
      );
    }

    // Extract error message
    const errorMessage =
      error.response?.data?.error?.message ||
      error.response?.data?.message ||
      error.message ||
      'Request failed';

    throw new Error(errorMessage);
  }
);

// ==================== PUBLIC ENDPOINTS ====================

/**
 * User Registration
 * POST /register
 */
export const register = (userData) => {
  const { username, email, firstName, lastName, password, profilePic, inviteCode, title } =
    userData;

  return axiosInstance.post('/register', {
    username,
    email,
    firstName,
    lastName,
    password,
    profilePic: profilePic || undefined,
    inviteCode: inviteCode || undefined,
    title: title || undefined,
  });
};

/**
 * User Login
 * POST /login
 */
export const login = (identifier, password) => {
  return axiosInstance.post('/login', { identifier, password });
};

/**
 * Logout current session
 * POST /logout
 */
export const logout = () => {
  return axiosInstance.post('/logout');
};

/**
 * Refresh access token
 * POST /refresh
 */
export const refresh = () => {
  return axiosInstance.post('/refresh');
};

/**
 * Check if email is available
 * POST /check-email
 */
export const checkEmail = (email) => {
  return axiosInstance.post('/check-email', { email });
};

/**
 * Check if username is available
 * POST /check-username
 */
export const checkUsername = (username) => {
  return axiosInstance.post('/check-username', { username });
};

/**
 * Validate current token
 * GET /validate-token
 */
export const validateToken = () => {
  return axiosInstance.get('/validate-token');
};

// ==================== PROTECTED ENDPOINTS ====================

/**
 * Get current user profile
 * GET /me
 */
export const getMe = () => {
  return axiosInstance.get('/me');
};

/**
 * Update user profile
 * PUT /me
 */
export const updateProfile = (profileData) => {
  return axiosInstance.put('/me', profileData);
};

/**
 * Change password
 * PUT /change-password
 */
export const changePassword = (
  currentPassword,
  newPassword,
  confirmPassword
) => {
  return axiosInstance.put('/change-password', {
    currentPassword,
    newPassword,
    confirmPassword,
  });
};

/**
 * Deactivate account
 * PUT /deactivate
 */
export const deactivateAccount = () => {
  return axiosInstance.put('/deactivate');
};

/**
 * Logout from all devices
 * POST /logout-all
 */
export const logoutAll = () => {
  return axiosInstance.post('/logout-all');
};

// ==================== SESSION MANAGEMENT ====================

/**
 * Get all user sessions
 * GET /sessions
 */
export const getSessions = () => {
  return axiosInstance.get('/sessions');
};

/**
 * Revoke a specific session
 * DELETE /sessions/:sessionId
 */
export const revokeSession = (sessionId) => {
  return axiosInstance.delete(`/sessions/${sessionId}`);
};

/**
 * Get session statistics
 * GET /sessions/stats
 */
export const getSessionStats = () => {
  return axiosInstance.get('/sessions/stats');
};

// ==================== EMAIL VERIFICATION ====================

/**
 * Send email verification OTP
 * POST /email/send-otp
 */
export const sendEmailOTP = (email) => {
  return axiosInstance.post('/email/send-otp', { email });
};

/**
 * Verify email with OTP
 * POST /email/verify-otp
 */
export const verifyEmailOTP = (email, otp) => {
  return axiosInstance.post('/email/verify-otp', { email, otp });
};

/**
 * Resend email OTP
 * POST /email/resend-otp
 */
export const resendEmailOTP = (email) => {
  return axiosInstance.post('/email/resend-otp', { email });
};

/**
 * Check email verification status
 * GET /email/verification-status
 */
export const checkVerificationStatus = (email = null) => {
  const query = email ? `?email=${encodeURIComponent(email)}` : '';
  return axiosInstance.get(`/email/verification-status${query}`);
};

// ==================== PASSWORD RESET ====================

/**
 * Request password reset
 * POST /password/forgot
 */
export const forgotPassword = (email) => {
  return axiosInstance.post('/password/forgot', { email });
};

/**
 * Reset password with token
 * POST /password/reset
 */
export const resetPassword = (token, newPassword, confirmPassword) => {
  return axiosInstance.post('/password/reset', {
    token,
    newPassword,
    confirmPassword,
  });
};

/**
 * Validate password reset token
 * GET /password/validate-token/:token
 */
export const validateResetToken = (token) => {
  return axiosInstance.get(`/password/validate-token/${token}`);
};

// ==================== INVITE CODE REDEMPTION ====================

/**
 * Redeem an invite code to join a company
 * POST /api/invite-codes/redeem
 */
export const redeemInviteCode = async (code) => {
  // Use absolute path since invite-codes is a separate API path from users
  const response = await axios.post('/api/invite-codes/redeem', { code }, {
    withCredentials: true,
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data;
};

// ==================== ADMIN ENDPOINTS ====================

/**
 * Get all users (admin only)
 * GET /
 */
export const getAllUsers = () => {
  return axiosInstance.get('/');
};

/**
 * Update user role (SUPER_ADMIN only)
 * PUT /:userId/role
 */
export const updateUserRole = (userId, role) => {
  return axiosInstance.put(`/${userId}/role`, { role });
};

// ==================== CHAT SERVICE API ====================
// Chat Service runs on port 3002 with base URL: http://localhost:3002/api/chat

/**
 * Determine the Chat API base URL based on environment
 * - Development with Vite proxy: Use relative path /api/chat (proxied to port 3002)
 * - Production: Use absolute URL from environment variable
 */
const getChatApiBaseUrl = () => {
  const envChatUrl = import.meta.env.VITE_CHAT_API_URL;

  // If it starts with '/', it's a relative path (Vite proxy mode)
  if (envChatUrl && envChatUrl.startsWith('/')) {
    return envChatUrl;
  }

  // If it's a full URL, use it directly
  if (
    envChatUrl &&
    (envChatUrl.startsWith('http://') || envChatUrl.startsWith('https://'))
  ) {
    return envChatUrl;
  }

  // Fallback: Use relative path for development (Vite proxy), absolute for production
  // In development, Vite proxy will route /api/chat to http://localhost:3002/api/chat
  return '/api/chat';
};

const CHAT_API_URL = getChatApiBaseUrl();

// Create a separate axios instance for chat service
const chatAxiosInstance = axios.create({
  baseURL: CHAT_API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Apply the same interceptors to chat instance
chatAxiosInstance.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    // Use the same error handling as main axios instance
    if (error.message === 'Network Error') {
      throw new Error(
        'Unable to connect to chat service. Please check if the chat service is running.'
      );
    }

    // Log the full error for debugging
    console.error('[Chat API Error]', {
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      url: error.config?.url,
      method: error.config?.method,
    });

    const errorMessage =
      error.response?.data?.error?.message ||
      error.response?.data?.message ||
      error.message ||
      'Request failed';

    const enhancedError = new Error(errorMessage);
    enhancedError.response = error.response;
    enhancedError.status = error.response?.status;
    throw enhancedError;
  }
);

// ---------- Test Endpoints ----------

/**
 * Test chat service health
 * GET /test
 */
export const testChatService = () => {
  return chatAxiosInstance.get('/test');
};

// ---------- RAG Endpoints ----------

/**
 * Check RAG API health
 * GET /rag/health
 */
export const ragHealthCheck = () => {
  return chatAxiosInstance.get('/rag/health');
};

/**
 * Query RAG for document retrieval
 * POST /rag/query
 */
export const ragQuery = (query, topK = 5, minScore = 0.15) => {
  return chatAxiosInstance.post('/rag/query', { query, topK, minScore });
};

/**
 * Query RAG with LLM response
 * POST /rag/chat
 */
export const ragChat = (query, profileId, topK = 5, minScore = 0.15) => {
  return chatAxiosInstance.post('/rag/chat', {
    query,
    profileId,
    topK,
    minScore,
  });
};

/**
 * Get available RAG profiles
 * GET /api/rag/profiles (proxies to RAG API /api/v1/profiles)
 */
export const getRagProfiles = (companyId = null) => {
  // FastAPI returns 307 redirect from /profiles/ to /profiles
  // Proxy rewrites the Location header, so following redirects is safe
  const params = {};
  if (companyId) {
    params.company_id = companyId;
  }
  return axios.get('/api/rag/profiles/', {
    params,
    withCredentials: true,
    maxRedirects: 5,
    validateStatus: (status) => status >= 200 && status < 400,
  });
};

// ---------- Conversation Endpoints ----------

/**
 * Get user's conversations with pagination
 * GET /conversations
 */
export const getConversations = (limit = 20, offset = 0) => {
  return chatAxiosInstance.get('/conversations', { params: { limit, offset } });
};

/**
 * Create a new conversation
 * POST /conversations
 */
export const createConversation = (title = 'New Chat') => {
  return chatAxiosInstance.post('/conversations', { title });
};

/**
 * Get a specific conversation
 * GET /conversations/:id
 */
export const getConversation = (id) => {
  return chatAxiosInstance.get(`/conversations/${id}`);
};

/**
 * Update conversation title
 * PATCH /conversations/:id
 */
export const updateConversation = (id, title) => {
  return chatAxiosInstance.patch(`/conversations/${id}`, { title });
};

/**
 * Delete a conversation
 * DELETE /conversations/:id
 */
export const deleteConversation = (id) => {
  return chatAxiosInstance.delete(`/conversations/${id}`);
};

// ---------- Message Endpoints ----------

/**
 * Get messages for a conversation
 * GET /conversations/:id/messages
 */
export const getMessages = (conversationId, limit = 50, offset = 0) => {
  return chatAxiosInstance.get(`/conversations/${conversationId}/messages`, {
    params: { limit, offset },
  });
};

/**
 * Send a message in a conversation
 * POST /conversations/:id/messages
 */
export const sendMessage = (conversationId, content, ragOptions = {}) => {
  return chatAxiosInstance.post(`/conversations/${conversationId}/messages`, {
    content,
    ...ragOptions,
  });
};

// ==================== CHAT & MEETING ENDPOINTS (Placeholder) ====================
// TODO: Implement these endpoints when backend is ready

/**
 * Get chat by ID
 * GET /chats/:id
 */
export const getChat = (id) => {
  // Placeholder - replace with actual endpoint when backend is ready
  return axiosInstance.get(`/chats/${id}`);
};

/**
 * Get executives list
 * GET /executives
 */
export const getExecutives = () => {
  // Placeholder - replace with actual endpoint when backend is ready
  return axiosInstance.get('/executives');
};

/**
 * Create a meeting
 * POST /api/rag/meetings (proxies to RAG API /api/v1/meetings)
 */
export const createMeeting = (meetingData) => {
  // Note: trailing slash required to prevent FastAPI 307 redirect
  return axios.post(
    '/api/rag/meetings/',
    {
      executive: meetingData.executive,
      platform: meetingData.platform,
      language: meetingData.language,
      link: meetingData.link,
      date: meetingData.date,
      time: meetingData.time,
    },
    {
      withCredentials: true,
      maxRedirects: 0,
      validateStatus: (status) => status >= 200 && status < 400,
    }
  );
};

/**
 * Get scheduled meetings
 * GET /api/rag/meetings (proxies to RAG API /api/v1/meetings)
 */
export const getMeetings = (status = null) => {
  const params = status ? { status } : {};
  // Note: trailing slash required to prevent FastAPI 307 redirect
  return axios.get('/api/rag/meetings/', {
    params,
    withCredentials: true,
    maxRedirects: 0,
    validateStatus: (x) => x >= 200 && x < 400,
  });
};

/**
 * Cancel a scheduled meeting
 * DELETE /api/rag/meetings/:id (proxies to RAG API /api/v1/meetings/:id)
 */
export const cancelMeeting = (meetingId) => {
  // Note: trailing slash required to prevent FastAPI 307 redirect
  return axios.delete(`/api/rag/meetings/${meetingId}/`, {
    withCredentials: true,
    maxRedirects: 0,
    validateStatus: (status) => status >= 200 && status < 400,
  });
};

// Reset interceptor state (call on logout)
export const resetInterceptorState = () => {
  isRefreshing = false;
  isRedirecting = false;
  failedQueue = [];
};

// Export axios instance for direct use if needed
export { axiosInstance };

/**
 * Create an instant meeting (bot joins immediately)
 * POST /api/rag/meetings/instant
 */
export const createInstantMeeting = (meetingData) => {
  return axios.post(
    '/api/rag/meetings/instant/',
    {
      executive: meetingData.executive,
      platform: meetingData.platform,
      language: meetingData.language,
      link: meetingData.link,
    },
    {
      withCredentials: true,
      maxRedirects: 0,
      validateStatus: (status) => status >= 200 && status < 400,
    }
  );
};
