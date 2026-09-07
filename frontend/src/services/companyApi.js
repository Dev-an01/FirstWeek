/**
 * Company Management API
 * API services for company and invite code management
 */
import axios from 'axios';

const API_BASE = import.meta.env.VITE_AUTH_API_URL || '/api/users';
const COMPANY_API = API_BASE.replace('/users', '/companies');
const INVITE_API = API_BASE.replace('/users', '/invite-codes');

// Axios instance with credentials
const api = axios.create({
    withCredentials: true,
    headers: {
        'Content-Type': 'application/json',
    },
});

// =============================================
// Company API
// =============================================

/**
 * Create a new company (SUPER_ADMIN only)
 */
export const createCompany = async (data) => {
    const response = await api.post(COMPANY_API, data);
    return response.data;
};

/**
 * List all companies (SUPER_ADMIN only)
 */
export const listCompanies = async (params = {}) => {
    const response = await api.get(COMPANY_API, { params });
    return response.data;
};

/**
 * Get company by ID
 */
export const getCompany = async (companyId) => {
    const response = await api.get(`${COMPANY_API}/${companyId}`);
    return response.data;
};

/**
 * Update company
 */
export const updateCompany = async (companyId, data) => {
    const response = await api.put(`${COMPANY_API}/${companyId}`, data);
    return response.data;
};

/**
 * Delete company (SUPER_ADMIN only)
 */
export const deleteCompany = async (companyId) => {
    const response = await api.delete(`${COMPANY_API}/${companyId}`);
    return response.data;
};

/**
 * Get company users
 */
export const getCompanyUsers = async (companyId, params = {}) => {
    const response = await api.get(`${COMPANY_API}/${companyId}/users`, { params });
    return response.data;
};

/**
 * Get pending user approvals
 */
export const getPendingApprovals = async (companyId) => {
    const response = await api.get(`${COMPANY_API}/${companyId}/pending`);
    return response.data;
};

/**
 * Verify a user's company membership
 */
export const verifyUser = async (companyId, userId) => {
    const response = await api.post(`${COMPANY_API}/${companyId}/users/${userId}/verify`);
    return response.data;
};

/**
 * Assign a user as company admin (SUPER_ADMIN only)
 */
export const assignCompanyAdmin = async (companyId, userId) => {
    const response = await api.post(`${COMPANY_API}/${companyId}/admins/${userId}`);
    return response.data;
};

/**
 * Revoke company admin privileges (SUPER_ADMIN only)
 */
export const revokeCompanyAdmin = async (companyId, userId) => {
    const response = await api.delete(`${COMPANY_API}/${companyId}/admins/${userId}`);
    return response.data;
};

/**
 * Add an existing user to company by email or username
 */
export const addUserToCompany = async (companyId, identifier) => {
    const response = await api.post(`${COMPANY_API}/${companyId}/users`, { identifier });
    return response.data;
};

/**
 * Update user role and/or title (COMPANY_ADMIN only)
 */
export const updateCompanyUserRole = async (companyId, userId, role, title) => {
    const body = {};
    if (role !== undefined) body.role = role;
    if (title !== undefined) body.title = title;
    const response = await api.put(`${COMPANY_API}/${companyId}/users/${userId}/role`, body);
    return response.data;
};

// =============================================
// Invite Code API
// =============================================

/**
 * Create an invite code
 */
export const createInviteCode = async (data) => {
    const response = await api.post(INVITE_API, data);
    return response.data;
};

/**
 * Validate an invite code (public)
 */
export const validateInviteCode = async (code) => {
    const response = await api.get(`${INVITE_API}/validate/${code}`);
    return response.data;
};

/**
 * List invite codes for a company
 */
export const listInviteCodes = async (companyId, params = {}) => {
    const response = await api.get(`${INVITE_API}/company/${companyId}`, { params });
    return response.data;
};

/**
 * Get invite code details
 */
export const getInviteCode = async (inviteCodeId) => {
    const response = await api.get(`${INVITE_API}/${inviteCodeId}`);
    return response.data;
};

/**
 * Revoke an invite code
 */
export const revokeInviteCode = async (inviteCodeId) => {
    const response = await api.post(`${INVITE_API}/${inviteCodeId}/revoke`);
    return response.data;
};

/**
 * Delete an invite code (SUPER_ADMIN only)
 */
export const deleteInviteCode = async (inviteCodeId) => {
    const response = await api.delete(`${INVITE_API}/${inviteCodeId}`);
    return response.data;
};

export default {
    // Company
    createCompany,
    listCompanies,
    getCompany,
    updateCompany,
    deleteCompany,
    getCompanyUsers,
    getPendingApprovals,
    verifyUser,
    assignCompanyAdmin,
    updateCompanyUserRole,
    // Invite Codes
    createInviteCode,
    validateInviteCode,
    listInviteCodes,
    getInviteCode,
    revokeInviteCode,
    deleteInviteCode,
};
