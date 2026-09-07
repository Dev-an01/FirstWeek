/**
 * TeamManagementPage
 * 
 * Admin dashboard for managing company team members.
 * - COMPANY_ADMIN: Can view/manage their own company users
 * - SUPER_ADMIN: Can view/manage any company users
 */

import { memo, useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Navbar } from '../../components/Navbar/Navbar';
import { Sidebar } from '../../components/Sidebar/Sidebar';
import { useAuthStore } from '../../store/authStore';
import { useUIStore } from '../../store/uiStore';
import * as companyApi from '../../services/companyApi';
import {
    Users,
    UserCheck,
    UserPlus,
    Shield,
    Clock,
    CheckCircle,
    XCircle,
    Copy,
    Plus,
    Trash2,
    RefreshCw,
    Mail,
    X,
    Edit2,
    Search,
} from 'lucide-react';

// Role badge colors
const ROLE_COLORS = {
    SUPER_ADMIN: 'bg-purple-100 text-purple-800',
    COMPANY_ADMIN: 'bg-blue-100 text-blue-800',
    EXECUTIVE: 'bg-green-100 text-green-800',
    EMPLOYEE: 'bg-gray-100 text-gray-800',
    GUEST: 'bg-yellow-100 text-yellow-800',
};

function TeamManagementPageComponent() {
    const { t } = useTranslation();
    const user = useAuthStore((s) => s.user);
    const showSuccessToast = useUIStore((s) => s.showSuccessToast);
    const showErrorToast = useUIStore((s) => s.showErrorToast);
    const sidebarOpen = useUIStore((s) => s.sidebarOpen);
    const closeSidebar = useUIStore((s) => s.closeSidebar);

    // State
    const [activeTab, setActiveTab] = useState('members');
    const [members, setMembers] = useState([]);
    const [pendingApprovals, setPendingApprovals] = useState([]);
    const [inviteCodes, setInviteCodes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [creating, setCreating] = useState(false);
    const [showAddUserModal, setShowAddUserModal] = useState(false);
    const [newUserIdentifier, setNewUserIdentifier] = useState('');
    const [addingUser, setAddingUser] = useState(false);

    // Member edit state (role + title)
    const [showEditModal, setShowEditModal] = useState(false);
    const [selectedMember, setSelectedMember] = useState(null);
    const [newRole, setNewRole] = useState('');
    const [newTitle, setNewTitle] = useState('');
    const [updatingMember, setUpdatingMember] = useState(false);

    // Search and Filter state
    const [searchQuery, setSearchQuery] = useState('');
    const [roleFilter, setRoleFilter] = useState('ALL');

    // Filtered members
    const filteredMembers = members.filter(member => {
        const matchesSearch =
            member.firstName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            member.lastName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            member.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            member.username?.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesRole = roleFilter === 'ALL' || member.role === roleFilter;

        return matchesSearch && matchesRole;
    });

    // Company ID from user or URL params
    const companyId = user?.companyId;

    // Fetch team members
    const fetchMembers = useCallback(async () => {
        if (!companyId) return;
        try {
            const response = await companyApi.getCompanyUsers(companyId);
            setMembers(response.data?.users || []);
        } catch (error) {
            console.error('Failed to fetch members:', error);
            showErrorToast('Failed to load team members');
        }
    }, [companyId, showErrorToast]);

    // Fetch pending approvals
    const fetchPendingApprovals = useCallback(async () => {
        if (!companyId) return;
        try {
            const response = await companyApi.getPendingApprovals(companyId);
            setPendingApprovals(response.data?.users || []);
        } catch (error) {
            console.error('Failed to fetch pending approvals:', error);
        }
    }, [companyId]);

    // Fetch invite codes
    const fetchInviteCodes = useCallback(async () => {
        if (!companyId) return;
        try {
            const response = await companyApi.listInviteCodes(companyId);
            setInviteCodes(response.data?.inviteCodes || []);
        } catch (error) {
            console.error('Failed to fetch invite codes:', error);
        }
    }, [companyId]);

    // Load data on mount
    useEffect(() => {
        const loadData = async () => {
            setLoading(true);
            await Promise.all([
                fetchMembers(),
                fetchPendingApprovals(),
                fetchInviteCodes(),
            ]);
            setLoading(false);
        };
        loadData();
    }, [fetchMembers, fetchPendingApprovals, fetchInviteCodes]);

    // Approve user
    const handleApproveUser = async (userId) => {
        try {
            await companyApi.verifyUser(companyId, userId);
            showSuccessToast('User approved successfully');
            fetchPendingApprovals();
            fetchMembers();
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Failed to approve user');
        }
    };

    // Create invite code
    const handleCreateInviteCode = async () => {
        setCreating(true);
        try {
            await companyApi.createInviteCode({ companyId, usageLimit: 1 });
            showSuccessToast('Invite code created');
            fetchInviteCodes();
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Failed to create invite code');
        } finally {
            setCreating(false);
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
            fetchInviteCodes();
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Failed to revoke invite code');
        }
    };

    // Add user to company
    const handleAddUser = async () => {
        if (!newUserIdentifier.trim()) {
            showErrorToast('Please enter an email or username');
            return;
        }
        setAddingUser(true);
        try {
            await companyApi.addUserToCompany(companyId, newUserIdentifier.trim());
            showSuccessToast('User added to company successfully!');
            setShowAddUserModal(false);
            setNewUserIdentifier('');
            fetchMembers();
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Failed to add user');
        } finally {
            setAddingUser(false);
        }
    };

    // Open edit modal
    const openEditModal = (member) => {
        setSelectedMember(member);
        setNewRole(member.role);
        setNewTitle(member.title || '');
        setShowEditModal(true);
    };

    // Update user role and/or title
    const handleUpdateMember = async () => {
        if (!selectedMember) return;

        const roleChanged = newRole !== selectedMember.role;
        const titleChanged = newTitle !== (selectedMember.title || '');
        if (!roleChanged && !titleChanged) return;

        setUpdatingMember(true);
        try {
            await companyApi.updateCompanyUserRole(
                companyId,
                selectedMember.id,
                roleChanged ? newRole : undefined,
                titleChanged ? newTitle : undefined
            );
            showSuccessToast('Member updated successfully');
            setShowEditModal(false);
            fetchMembers();
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Failed to update member');
        } finally {
            setUpdatingMember(false);
        }
    };

    // Render member card
    const renderMemberCard = (member) => (
        <div
            key={member.id}
            className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow"
        >
            <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-semibold">
                        {member.firstName?.[0]}{member.lastName?.[0]}
                    </div>
                    <div>
                        <h3 className="font-medium text-gray-900">
                            {member.firstName} {member.lastName}
                        </h3>
                        <p className="text-sm text-gray-500">{member.email}</p>
                        {member.title && (
                            <p className="text-xs text-gray-400">{member.title}</p>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${ROLE_COLORS[member.role] || 'bg-gray-100'}`}>
                        {member.role}
                    </span>
                    {/* Only show edit button for non-admin users and not self */}
                    {(user.role === 'COMPANY_ADMIN' || user.role === 'SUPER_ADMIN') &&
                        member.id !== user.id &&
                        !['COMPANY_ADMIN', 'SUPER_ADMIN'].includes(member.role) && (
                            <button
                                onClick={() => openEditModal(member)}
                                className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                                title="Edit Member"
                            >
                                <Edit2 className="w-4 h-4" />
                            </button>
                        )}
                </div>
            </div>
            <div className="mt-3 flex items-center gap-2 text-sm text-gray-500">
                {member.isCompanyVerified ? (
                    <span className="flex items-center gap-1 text-green-600">
                        <CheckCircle className="w-4 h-4" />
                        Verified
                    </span>
                ) : (
                    <span className="flex items-center gap-1 text-yellow-600">
                        <Clock className="w-4 h-4" />
                        Pending
                    </span>
                )}
            </div>
        </div >
    );

    // Render pending approval card
    const renderPendingCard = (pending) => (
        <div
            key={pending.id}
            className="bg-white rounded-lg border border-yellow-200 p-4"
        >
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center text-yellow-700 font-semibold">
                        {pending.firstName?.[0]}{pending.lastName?.[0]}
                    </div>
                    <div>
                        <h3 className="font-medium text-gray-900">
                            {pending.firstName} {pending.lastName}
                        </h3>
                        <p className="text-sm text-gray-500">{pending.email}</p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => handleApproveUser(pending.id)}
                        className="p-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition-colors"
                        title="Approve"
                    >
                        <CheckCircle className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );

    // Render invite code card
    const renderInviteCodeCard = (code) => (
        <div
            key={code.id}
            className={`bg-white rounded-lg border p-4 ${code.isActive ? 'border-gray-200' : 'border-red-200 opacity-60'}`}
        >
            <div className="flex items-center justify-between">
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
                        Used: {code.usageCount} / {code.usageLimit || '∞'}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {code.isActive ? (
                        <button
                            onClick={() => handleRevokeCode(code.id)}
                            className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                            title="Revoke"
                        >
                            <XCircle className="w-5 h-5" />
                        </button>
                    ) : (
                        <span className="text-sm text-red-500">Revoked</span>
                    )}
                </div>
            </div>
        </div>
    );

    // No company assigned
    if (!companyId) {
        return (
            <div className="flex flex-col min-h-screen bg-gray-50">
                <Navbar />
                <div className="flex flex-1 overflow-hidden">
                    <Sidebar />
                    <main className="flex-1 flex items-center justify-center">
                        <div className="text-center">
                            <Shield className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                            <h2 className="text-xl font-semibold text-gray-700">No Company Assigned</h2>
                            <p className="text-gray-500 mt-2">You are not associated with any company.</p>
                        </div>
                    </main>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col min-h-screen bg-gray-50">
            <Navbar />

            <div className="flex flex-1 overflow-hidden">
                <Sidebar />

                <main className="flex-1 overflow-y-auto">
                    <div className="p-4 sm:p-6 lg:p-8">
                        {/* Header */}
                        <div className="mb-6">
                            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                                <Users className="w-7 h-7" />
                                Team Management
                            </h1>
                            <p className="text-gray-500 mt-1">Manage your company team members and invite codes</p>
                        </div>

                        {/* Tabs */}
                        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg mb-6 w-fit">
                            <button
                                onClick={() => setActiveTab('members')}
                                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${activeTab === 'members'
                                    ? 'bg-white text-blue-600 shadow-sm'
                                    : 'text-gray-600 hover:text-gray-900'
                                    }`}
                            >
                                <Users className="w-4 h-4" />
                                Members ({members.length})
                            </button>
                            <button
                                onClick={() => setActiveTab('pending')}
                                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${activeTab === 'pending'
                                    ? 'bg-white text-blue-600 shadow-sm'
                                    : 'text-gray-600 hover:text-gray-900'
                                    }`}
                            >
                                <Clock className="w-4 h-4" />
                                Pending ({pendingApprovals.length})
                            </button>
                            <button
                                onClick={() => setActiveTab('invites')}
                                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${activeTab === 'invites'
                                    ? 'bg-white text-blue-600 shadow-sm'
                                    : 'text-gray-600 hover:text-gray-900'
                                    }`}
                            >
                                <UserPlus className="w-4 h-4" />
                                Invite Codes ({inviteCodes.length})
                            </button>
                        </div>

                        {/* Loading */}
                        {loading ? (
                            <div className="flex items-center justify-center py-12">
                                <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
                            </div>
                        ) : (
                            <>
                                {activeTab === 'members' && (
                                    <div>
                                        {/* Search and Filter */}
                                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                                            <div className="flex-1 relative max-w-md">
                                                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                                                <input
                                                    type="text"
                                                    placeholder="Search members..."
                                                    value={searchQuery}
                                                    onChange={(e) => setSearchQuery(e.target.value)}
                                                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                                />
                                            </div>

                                            <div className="flex items-center gap-2">
                                                <select
                                                    value={roleFilter}
                                                    onChange={(e) => setRoleFilter(e.target.value)}
                                                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                                                >
                                                    <option value="ALL">All Roles</option>
                                                    <option value="COMPANY_ADMIN">Admins</option>
                                                    <option value="EXECUTIVE">Executives</option>
                                                    <option value="EMPLOYEE">Employees</option>
                                                </select>

                                                <button
                                                    onClick={() => setShowAddUserModal(true)}
                                                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium whitespace-nowrap"
                                                >
                                                    <UserPlus className="w-4 h-4" />
                                                    Add User
                                                </button>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                            {filteredMembers.length === 0 ? (
                                                <div className="col-span-full text-center py-12 text-gray-500">
                                                    No team members found
                                                </div>
                                            ) : (
                                                filteredMembers.map(renderMemberCard)
                                            )}
                                        </div>
                                    </div>
                                )}

                                {/* Pending Tab */}
                                {activeTab === 'pending' && (
                                    <div className="space-y-4">
                                        {pendingApprovals.length === 0 ? (
                                            <div className="text-center py-12 text-gray-500">
                                                <UserCheck className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                                                No pending approvals
                                            </div>
                                        ) : (
                                            pendingApprovals.map(renderPendingCard)
                                        )}
                                    </div>
                                )}

                                {/* Invite Codes Tab */}
                                {activeTab === 'invites' && (
                                    <div className="space-y-4">
                                        <button
                                            onClick={handleCreateInviteCode}
                                            disabled={creating}
                                            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                                        >
                                            {creating ? (
                                                <RefreshCw className="w-4 h-4 animate-spin" />
                                            ) : (
                                                <Plus className="w-4 h-4" />
                                            )}
                                            Create Invite Code
                                        </button>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            {inviteCodes.length === 0 ? (
                                                <div className="col-span-full text-center py-12 text-gray-500">
                                                    <UserPlus className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                                                    No invite codes created yet
                                                </div>
                                            ) : (
                                                inviteCodes.map(renderInviteCodeCard)
                                            )}
                                        </div>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </main>
            </div>

            {/* Mobile sidebar overlay */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 z-20 bg-black bg-opacity-50 md:hidden"
                    onClick={closeSidebar}
                />
            )}

            {/* Add User Modal */}
            {showAddUserModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
                    <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                                <UserPlus className="w-5 h-5 text-blue-600" />
                                Add Existing User
                            </h3>
                            <button
                                onClick={() => {
                                    setShowAddUserModal(false);
                                    setNewUserIdentifier('');
                                }}
                                className="text-gray-400 hover:text-gray-600"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <p className="text-sm text-gray-600 mb-4">
                            Enter the email or username of an existing user to add them to your company.
                        </p>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Email or Username
                                </label>
                                <div className="relative">
                                    <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                                    <input
                                        type="text"
                                        value={newUserIdentifier}
                                        onChange={(e) => setNewUserIdentifier(e.target.value)}
                                        placeholder="user@example.com or username"
                                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                        disabled={addingUser}
                                        onKeyDown={(e) => e.key === 'Enter' && handleAddUser()}
                                    />
                                </div>
                            </div>
                            <div className="flex gap-3 pt-2">
                                <button
                                    onClick={() => {
                                        setShowAddUserModal(false);
                                        setNewUserIdentifier('');
                                    }}
                                    className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                                    disabled={addingUser}
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleAddUser}
                                    disabled={addingUser || !newUserIdentifier.trim()}
                                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                                >
                                    {addingUser ? (
                                        <>
                                            <RefreshCw className="w-4 h-4 animate-spin" />
                                            Adding...
                                        </>
                                    ) : (
                                        <>
                                            <UserPlus className="w-4 h-4" />
                                            Add User
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
            {/* Edit Member Modal */}
            {showEditModal && selectedMember && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
                    <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                                <Edit2 className="w-5 h-5 text-blue-600" />
                                Edit Member
                            </h3>
                            <button
                                onClick={() => setShowEditModal(false)}
                                className="text-gray-400 hover:text-gray-600"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="flex items-center gap-3 mb-6 p-3 bg-gray-50 rounded-lg">
                            <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-semibold">
                                {selectedMember.firstName?.[0]}{selectedMember.lastName?.[0]}
                            </div>
                            <div>
                                <h4 className="font-medium text-gray-900">
                                    {selectedMember.firstName} {selectedMember.lastName}
                                </h4>
                                <p className="text-sm text-gray-500">{selectedMember.email}</p>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Title / Designation
                                </label>
                                <input
                                    type="text"
                                    value={newTitle}
                                    onChange={(e) => setNewTitle(e.target.value)}
                                    placeholder="e.g., CEO, CTO, VP Engineering"
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                    disabled={updatingMember}
                                    maxLength={100}
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    The job title or designation for this team member.
                                </p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Role
                                </label>
                                <select
                                    value={newRole}
                                    onChange={(e) => setNewRole(e.target.value)}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                    disabled={updatingMember}
                                >
                                    <option value="EMPLOYEE">Employee</option>
                                    <option value="EXECUTIVE">Executive</option>
                                    <option value="GUEST">Guest</option>
                                </select>
                                <p className="text-xs text-gray-500 mt-2">
                                    Note: You cannot promote users to Admin roles here. Contact a Super Admin for that.
                                </p>
                            </div>

                            <div className="flex gap-3 pt-2">
                                <button
                                    onClick={() => setShowEditModal(false)}
                                    className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                                    disabled={updatingMember}
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleUpdateMember}
                                    disabled={updatingMember || (newRole === selectedMember.role && newTitle === (selectedMember.title || ''))}
                                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                                >
                                    {updatingMember ? (
                                        <>
                                            <RefreshCw className="w-4 h-4 animate-spin" />
                                            Updating...
                                        </>
                                    ) : (
                                        'Save Changes'
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>

    );
}

export const TeamManagementPage = memo(TeamManagementPageComponent);
export default TeamManagementPage;
