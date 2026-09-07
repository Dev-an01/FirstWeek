/**
 * CompanyManagementPage
 * 
 * SUPER_ADMIN dashboard for managing all companies.
 * Features: Create, view, edit, delete companies, assign admins, create invite codes
 */

import { memo, useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Navbar } from '../../components/Navbar/Navbar';
import { Sidebar } from '../../components/Sidebar/Sidebar';
import { useUIStore } from '../../store/uiStore';
import * as companyApi from '../../services/companyApi';
import {
    Building2,
    Plus,
    Edit2,
    Trash2,
    Users,
    RefreshCw,
    X,
    Check,
    Globe,
    UserCog,
    Crown,
    Ticket,
    Copy,
    XCircle,
} from 'lucide-react';

function CompanyManagementPageComponent() {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const showSuccessToast = useUIStore((s) => s.showSuccessToast);
    const showErrorToast = useUIStore((s) => s.showErrorToast);
    const sidebarOpen = useUIStore((s) => s.sidebarOpen);
    const closeSidebar = useUIStore((s) => s.closeSidebar);

    // State
    const [companies, setCompanies] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingCompany, setEditingCompany] = useState(null);
    const [formData, setFormData] = useState({
        name: '',
        allowedDomains: '',
        description: '',
        website: '',
        phone: '',
        address: ''
    });
    const [submitting, setSubmitting] = useState(false);

    // Admin assignment state
    const [showAdminModal, setShowAdminModal] = useState(false);
    const [selectedCompany, setSelectedCompany] = useState(null);
    const [companyUsers, setCompanyUsers] = useState([]);
    const [loadingUsers, setLoadingUsers] = useState(false);
    const [assigningAdmin, setAssigningAdmin] = useState(null);

    // Invite code state
    const [showInviteModal, setShowInviteModal] = useState(false);
    const [inviteCodes, setInviteCodes] = useState([]);
    const [loadingCodes, setLoadingCodes] = useState(false);
    const [creatingCode, setCreatingCode] = useState(false);

    // Fetch companies
    const fetchCompanies = useCallback(async () => {
        setLoading(true);
        try {
            const response = await companyApi.listCompanies();
            setCompanies(response.data?.companies || []);
        } catch (error) {
            console.error('Failed to fetch companies:', error);
            showErrorToast('Failed to load companies');
        } finally {
            setLoading(false);
        }
    }, [showErrorToast]);

    useEffect(() => {
        fetchCompanies();
    }, [fetchCompanies]);

    // Fetch company users for admin assignment
    const fetchCompanyUsers = useCallback(async (companyId) => {
        setLoadingUsers(true);
        try {
            const response = await companyApi.getCompanyUsers(companyId, { limit: 100 });
            setCompanyUsers(response.data?.users || []);
        } catch (error) {
            console.error('Failed to fetch company users:', error);
            showErrorToast('Failed to load company users');
            setCompanyUsers([]);
        } finally {
            setLoadingUsers(false);
        }
    }, [showErrorToast]);

    // Fetch invite codes for a company
    const fetchInviteCodes = useCallback(async (companyId) => {
        setLoadingCodes(true);
        try {
            const response = await companyApi.listInviteCodes(companyId);
            setInviteCodes(response.data?.inviteCodes || []);
        } catch (error) {
            console.error('Failed to fetch invite codes:', error);
            showErrorToast('Failed to load invite codes');
            setInviteCodes([]);
        } finally {
            setLoadingCodes(false);
        }
    }, [showErrorToast]);

    // Handle form submit
    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!formData.name.trim()) {
            showErrorToast('Company name is required');
            return;
        }

        setSubmitting(true);
        try {
            const domains = formData.allowedDomains
                .split(',')
                .map((d) => d.trim().toLowerCase())
                .filter((d) => d);

            const companyData = {
                name: formData.name,
                allowedDomains: domains,
                description: formData.description,
                website: formData.website,
                phone: formData.phone,
                address: formData.address,
            };

            if (editingCompany) {
                await companyApi.updateCompany(editingCompany.id, companyData);
                showSuccessToast('Company updated successfully');
            } else {
                await companyApi.createCompany(companyData);
                showSuccessToast('Company created successfully');
            }

            setShowModal(false);
            setEditingCompany(null);
            setFormData({
                name: '',
                allowedDomains: '',
                description: '',
                website: '',
                phone: '',
                address: ''
            });
            fetchCompanies();
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Operation failed');
        } finally {
            setSubmitting(false);
        }
    };

    // Open edit modal
    const handleEdit = (company) => {
        setEditingCompany(company);
        setFormData({
            name: company.name,
            allowedDomains: company.allowedDomains?.join(', ') || '',
            description: company.description || '',
            website: company.website || '',
            phone: company.phone || '',
            address: company.address || '',
        });
        setShowModal(true);
    };

    // Delete company
    const handleDelete = async (companyId) => {
        if (!confirm('Are you sure you want to delete this company? This action cannot be undone.')) {
            return;
        }

        try {
            await companyApi.deleteCompany(companyId);
            showSuccessToast('Company deleted successfully');
            fetchCompanies();
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Failed to delete company');
        }
    };

    // Open admin assignment modal
    const handleManageAdmins = (company) => {
        setSelectedCompany(company);
        setShowAdminModal(true);
        fetchCompanyUsers(company.id);
    };

    // Assign user as company admin
    const handleAssignAdmin = async (userId) => {
        if (!selectedCompany) return;

        setAssigningAdmin(userId);
        try {
            await companyApi.assignCompanyAdmin(selectedCompany.id, userId);
            showSuccessToast('User assigned as Company Admin successfully');
            fetchCompanyUsers(selectedCompany.id);
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Failed to assign admin');
        } finally {
            setAssigningAdmin(null);
        }
    };

    // Revoke user's company admin privileges
    const handleRevokeAdmin = async (userId) => {
        if (!selectedCompany) return;

        setAssigningAdmin(userId); // Reuse same loading state
        try {
            await companyApi.revokeCompanyAdmin(selectedCompany.id, userId);
            showSuccessToast('Admin privileges revoked successfully');
            fetchCompanyUsers(selectedCompany.id);
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Failed to revoke admin');
        } finally {
            setAssigningAdmin(null);
        }
    };

    // Open invite codes modal
    const handleManageInviteCodes = (company) => {
        setSelectedCompany(company);
        setShowInviteModal(true);
        fetchInviteCodes(company.id);
    };

    // Create invite code
    const handleCreateInviteCode = async () => {
        if (!selectedCompany) return;

        setCreatingCode(true);
        try {
            await companyApi.createInviteCode({
                companyId: selectedCompany.id,
                usageLimit: 10  // Allow 10 uses by default
            });
            showSuccessToast('Invite code created successfully');
            fetchInviteCodes(selectedCompany.id);
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Failed to create invite code');
        } finally {
            setCreatingCode(false);
        }
    };

    // Copy invite code
    const handleCopyCode = (code) => {
        navigator.clipboard.writeText(code);
        showSuccessToast('Invite code copied to clipboard');
    };

    // Revoke invite code
    const handleRevokeCode = async (inviteCodeId) => {
        try {
            await companyApi.revokeInviteCode(inviteCodeId);
            showSuccessToast('Invite code revoked');
            if (selectedCompany) {
                fetchInviteCodes(selectedCompany.id);
            }
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Failed to revoke invite code');
        }
    };

    return (
        <div className="flex flex-col min-h-screen bg-gray-50">
            <Navbar />

            <div className="flex flex-1 overflow-hidden">
                <Sidebar />

                <main className="flex-1 overflow-y-auto">
                    <div className="p-4 sm:p-6 lg:p-8">
                        {/* Header */}
                        <div className="flex items-center justify-between mb-6">
                            <div>
                                <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                                    <Building2 className="w-7 h-7" />
                                    Company Management
                                </h1>
                                <p className="text-gray-500 mt-1">Manage all companies in the system</p>
                            </div>

                            <button
                                onClick={() => {
                                    setEditingCompany(null);
                                    setFormData({
                                        name: '',
                                        allowedDomains: '',
                                        description: '',
                                        website: '',
                                        phone: '',
                                        address: ''
                                    });
                                    setShowModal(true);
                                }}
                                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                            >
                                <Plus className="w-4 h-4" />
                                Add Company
                            </button>
                        </div>

                        {/* Info Box */}
                        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                            <p className="text-sm text-blue-800">
                                <strong>Note:</strong> These companies are for user access control (RBAC).
                                The onboarding page uses a separate company database for managing executive avatars and knowledge bases.
                            </p>
                        </div>

                        {/* Loading */}
                        {loading ? (
                            <div className="flex items-center justify-center py-12">
                                <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
                            </div>
                        ) : (
                            /* Companies Grid */
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {companies.length === 0 ? (
                                    <div className="col-span-full text-center py-12 text-gray-500">
                                        <Building2 className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                                        No companies yet. Create your first company.
                                    </div>
                                ) : (
                                    companies.map((company) => (
                                        <div
                                            key={company.id}
                                            className="bg-white rounded-lg border border-gray-200 p-5 hover:shadow-md transition-shadow"
                                        >
                                            <div className="flex items-start justify-between mb-3">
                                                <div>
                                                    <h3 className="font-semibold text-gray-900 text-lg">
                                                        {company.name}
                                                    </h3>
                                                    <span
                                                        className={`inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium ${company.isActive
                                                            ? 'bg-green-100 text-green-700'
                                                            : 'bg-red-100 text-red-700'
                                                            }`}
                                                    >
                                                        {company.isActive ? 'Active' : 'Inactive'}
                                                    </span>
                                                </div>
                                                <div className="flex gap-1">
                                                    <button
                                                        onClick={() => handleManageInviteCodes(company)}
                                                        className="p-2 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                                                        title="Invite Codes"
                                                    >
                                                        <Ticket className="w-4 h-4" />
                                                    </button>
                                                    <button
                                                        onClick={() => handleManageAdmins(company)}
                                                        className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                                                        title="Manage Admins"
                                                    >
                                                        <UserCog className="w-4 h-4" />
                                                    </button>
                                                    <button
                                                        onClick={() => handleEdit(company)}
                                                        className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                                                        title="Edit"
                                                    >
                                                        <Edit2 className="w-4 h-4" />
                                                    </button>
                                                    <button
                                                        onClick={() => handleDelete(company.id)}
                                                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                                        title="Delete"
                                                    >
                                                        <Trash2 className="w-4 h-4" />
                                                    </button>
                                                </div>
                                            </div>

                                            {/* Allowed Domains */}
                                            {company.allowedDomains?.length > 0 && (
                                                <div className="flex items-center gap-1 text-sm text-gray-500 mb-3">
                                                    <Globe className="w-4 h-4" />
                                                    {company.allowedDomains.join(', ')}
                                                </div>
                                            )}

                                            {/* Stats */}
                                            <div className="flex items-center gap-4 text-sm text-gray-500 pt-3 border-t">
                                                <span className="flex items-center gap-1">
                                                    <Users className="w-4 h-4" />
                                                    {company._count?.users || 0} users
                                                </span>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        )}
                    </div>
                </main>
            </div>

            {/* Create/Edit Company Modal */}
            {showModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                    <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4">
                        <div className="flex items-center justify-between p-4 border-b">
                            <h2 className="text-lg font-semibold">
                                {editingCompany ? 'Edit Company' : 'Create Company'}
                            </h2>
                            <button
                                onClick={() => setShowModal(false)}
                                className="p-1 text-gray-400 hover:text-gray-600"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <form onSubmit={handleSubmit} className="p-4 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Company Name *
                                </label>
                                <input
                                    type="text"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                    placeholder="Acme Corporation"
                                    required
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Allowed Domains
                                </label>
                                <input
                                    type="text"
                                    value={formData.allowedDomains}
                                    onChange={(e) => setFormData({ ...formData, allowedDomains: e.target.value })}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                    placeholder="acme.com, acme.co.jp"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    Comma-separated list of email domains for auto-assignment
                                </p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Description
                                </label>
                                <textarea
                                    value={formData.description}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    rows={2}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                    placeholder="Company description..."
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Website
                                    </label>
                                    <input
                                        type="url"
                                        value={formData.website}
                                        onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                        placeholder="https://..."
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Phone
                                    </label>
                                    <input
                                        type="tel"
                                        value={formData.phone}
                                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                        placeholder="+1..."
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Address
                                </label>
                                <input
                                    type="text"
                                    value={formData.address}
                                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                    placeholder="Street address..."
                                />
                            </div>

                            <div className="flex justify-end gap-2 pt-2">
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={submitting}
                                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                                >
                                    {submitting ? (
                                        <RefreshCw className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Check className="w-4 h-4" />
                                    )}
                                    {editingCompany ? 'Update' : 'Create'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Assign Admin Modal */}
            {showAdminModal && selectedCompany && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                    <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4">
                        <div className="flex items-center justify-between p-4 border-b">
                            <div>
                                <h2 className="text-lg font-semibold flex items-center gap-2">
                                    <UserCog className="w-5 h-5" />
                                    Assign Company Admin
                                </h2>
                                <p className="text-sm text-gray-500">{selectedCompany.name}</p>
                            </div>
                            <button
                                onClick={() => {
                                    setShowAdminModal(false);
                                    setSelectedCompany(null);
                                    setCompanyUsers([]);
                                }}
                                className="p-1 text-gray-400 hover:text-gray-600"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="p-4">
                            {loadingUsers ? (
                                <div className="flex items-center justify-center py-8">
                                    <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
                                </div>
                            ) : companyUsers.length === 0 ? (
                                <div className="text-center py-8 text-gray-500">
                                    <Users className="w-10 h-10 mx-auto mb-2 text-gray-300" />
                                    <p>No users in this company yet.</p>
                                    <p className="text-sm mt-1">
                                        Create an invite code first, then users can register.
                                    </p>
                                    <button
                                        onClick={() => {
                                            setShowAdminModal(false);
                                            handleManageInviteCodes(selectedCompany);
                                        }}
                                        className="mt-3 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
                                    >
                                        <Ticket className="w-4 h-4 inline mr-1" />
                                        Create Invite Code
                                    </button>
                                </div>
                            ) : (
                                <div className="max-h-80 overflow-y-auto space-y-2">
                                    {companyUsers.map((user) => (
                                        <div
                                            key={user.id}
                                            className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center text-gray-600 font-medium">
                                                    {user.firstName?.[0] || user.username?.[0] || '?'}
                                                </div>
                                                <div>
                                                    <div className="font-medium text-gray-900 flex items-center gap-2">
                                                        {user.firstName} {user.lastName}
                                                        {user.role === 'COMPANY_ADMIN' && (
                                                            <Crown className="w-4 h-4 text-yellow-500" title="Company Admin" />
                                                        )}
                                                    </div>
                                                    <div className="text-sm text-gray-500">{user.email}</div>
                                                </div>
                                            </div>

                                            {user.role === 'COMPANY_ADMIN' ? (
                                                <button
                                                    onClick={() => handleRevokeAdmin(user.id)}
                                                    disabled={assigningAdmin === user.id}
                                                    className="flex items-center gap-1 px-3 py-1.5 text-sm bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors disabled:opacity-50"
                                                    title="Revoke admin privileges"
                                                >
                                                    {assigningAdmin === user.id ? (
                                                        <RefreshCw className="w-3 h-3 animate-spin" />
                                                    ) : (
                                                        <XCircle className="w-3 h-3" />
                                                    )}
                                                    Revoke Admin
                                                </button>
                                            ) : (
                                                <button
                                                    onClick={() => handleAssignAdmin(user.id)}
                                                    disabled={assigningAdmin === user.id}
                                                    className="flex items-center gap-1 px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
                                                >
                                                    {assigningAdmin === user.id ? (
                                                        <RefreshCw className="w-3 h-3 animate-spin" />
                                                    ) : (
                                                        <Crown className="w-3 h-3" />
                                                    )}
                                                    Make Admin
                                                </button>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="p-4 border-t bg-gray-50 rounded-b-xl">
                            <p className="text-xs text-gray-500">
                                Company Admins can manage team members, approve pending users, and create invite codes.
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Invite Codes Modal */}
            {showInviteModal && selectedCompany && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                    <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4">
                        <div className="flex items-center justify-between p-4 border-b">
                            <div>
                                <h2 className="text-lg font-semibold flex items-center gap-2">
                                    <Ticket className="w-5 h-5" />
                                    Invite Codes
                                </h2>
                                <p className="text-sm text-gray-500">{selectedCompany.name}</p>
                            </div>
                            <button
                                onClick={() => {
                                    setShowInviteModal(false);
                                    setSelectedCompany(null);
                                    setInviteCodes([]);
                                }}
                                className="p-1 text-gray-400 hover:text-gray-600"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="p-4">
                            {/* Create Button */}
                            <button
                                onClick={handleCreateInviteCode}
                                disabled={creatingCode}
                                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 mb-4"
                            >
                                {creatingCode ? (
                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                    <Plus className="w-4 h-4" />
                                )}
                                Generate New Invite Code
                            </button>

                            {loadingCodes ? (
                                <div className="flex items-center justify-center py-8">
                                    <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
                                </div>
                            ) : inviteCodes.length === 0 ? (
                                <div className="text-center py-8 text-gray-500">
                                    <Ticket className="w-10 h-10 mx-auto mb-2 text-gray-300" />
                                    <p>No invite codes yet.</p>
                                    <p className="text-sm mt-1">
                                        Create one above to allow users to join this company.
                                    </p>
                                </div>
                            ) : (
                                <div className="max-h-60 overflow-y-auto space-y-2">
                                    {inviteCodes.map((code) => (
                                        <div
                                            key={code.id}
                                            className={`flex items-center justify-between p-3 rounded-lg border ${code.isActive
                                                ? 'bg-white border-gray-200'
                                                : 'bg-gray-50 border-gray-100 opacity-60'
                                                }`}
                                        >
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <code className="text-lg font-mono font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded">
                                                        {code.code}
                                                    </code>
                                                    <button
                                                        onClick={() => handleCopyCode(code.code)}
                                                        className="p-1 text-gray-400 hover:text-gray-600"
                                                        title="Copy code"
                                                    >
                                                        <Copy className="w-4 h-4" />
                                                    </button>
                                                </div>
                                                <p className="text-sm text-gray-500 mt-1">
                                                    Used: {code.usageCount || 0} / {code.usageLimit || '∞'}
                                                    {!code.isActive && <span className="ml-2 text-red-500">(Revoked)</span>}
                                                </p>
                                            </div>
                                            {code.isActive && (
                                                <button
                                                    onClick={() => handleRevokeCode(code.id)}
                                                    className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                                                    title="Revoke"
                                                >
                                                    <XCircle className="w-5 h-5" />
                                                </button>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="p-4 border-t bg-gray-50 rounded-b-xl">
                            <p className="text-xs text-gray-500">
                                Share invite codes with users to let them register and join this company.
                                Codes with remaining uses can be used during registration.
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Mobile sidebar overlay */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 z-20 bg-black bg-opacity-50 md:hidden"
                    onClick={closeSidebar}
                />
            )}
        </div>
    );
}

export const CompanyManagementPage = memo(CompanyManagementPageComponent);
export default CompanyManagementPage;
