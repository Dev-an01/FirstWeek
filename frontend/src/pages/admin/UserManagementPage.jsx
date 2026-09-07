/**
 * UserManagementPage
 * 
 * SUPER_ADMIN dashboard for managing all users.
 * Features: View all users, change roles (including assigning SUPER_ADMIN)
 */

import { memo, useState, useEffect, useCallback } from 'react';
import { useAuthStore } from '../../store/authStore';
import { useUIStore } from '../../store/uiStore';
import { Navbar } from '../../components/Navbar/Navbar';
import { Sidebar } from '../../components/Sidebar/Sidebar';
import * as api from '../../services/api';
import {
    Users,
    Shield,
    ShieldCheck,
    Crown,
    User,
    RefreshCw,
    Search,
} from 'lucide-react';

// Role options
const ROLES = [
    { value: 'GUEST', label: 'Guest', icon: User, color: 'gray' },
    { value: 'EMPLOYEE', label: 'Employee', icon: Users, color: 'blue' },
    { value: 'EXECUTIVE', label: 'Executive', icon: Crown, color: 'purple' },
    { value: 'COMPANY_ADMIN', label: 'Company Admin', icon: Shield, color: 'green' },
    { value: 'SUPER_ADMIN', label: 'Super Admin', icon: Crown, color: 'yellow' },
];

function UserManagementPageComponent() {
    const user = useAuthStore((state) => state.user);
    const { sidebarOpen, closeSidebar } = useUIStore();
    const showSuccessToast = useUIStore((state) => state.showSuccessToast);
    const showErrorToast = useUIStore((state) => state.showErrorToast);

    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [updatingRole, setUpdatingRole] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [roleFilter, setRoleFilter] = useState('ALL');

    // Fetch all users
    const fetchUsers = useCallback(async () => {
        setLoading(true);
        try {
            const response = await api.getAllUsers();
            setUsers(response.data?.data?.users || response.data?.users || []);
        } catch (error) {
            console.error('Failed to fetch users:', error);
            showErrorToast('Failed to load users');
        } finally {
            setLoading(false);
        }
    }, [showErrorToast]);

    useEffect(() => {
        fetchUsers();
    }, [fetchUsers]);

    // Handle role change
    const handleRoleChange = async (userId, newRole) => {
        setUpdatingRole(userId);
        try {
            await api.updateUserRole(userId, newRole);
            showSuccessToast(`User role updated to ${newRole}`);
            fetchUsers();
        } catch (error) {
            showErrorToast(error.response?.data?.error?.message || 'Failed to update role');
        } finally {
            setUpdatingRole(null);
        }
    };

    // Filter users by search and role
    const filteredUsers = users.filter(u => {
        const matchesSearch =
            u.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            u.username?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            u.firstName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            u.lastName?.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesRole = roleFilter === 'ALL' || u.role === roleFilter;

        return matchesSearch && matchesRole;
    });

    // Get role info
    const getRoleInfo = (role) => {
        return ROLES.find(r => r.value === role) || ROLES[0];
    };

    // Not SUPER_ADMIN
    if (user?.role !== 'SUPER_ADMIN') {
        return (
            <div className="flex flex-col min-h-screen bg-gray-50">
                <Navbar />
                <div className="flex flex-1 overflow-hidden">
                    <Sidebar />
                    <main className="flex-1 flex items-center justify-center">
                        <div className="text-center">
                            <ShieldCheck className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                            <h2 className="text-xl font-semibold text-gray-700">Access Restricted</h2>
                            <p className="text-gray-500 mt-2">Super Admin access required.</p>
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
                <main className="flex-1 overflow-y-auto p-6">
                    <div className="max-w-6xl mx-auto">
                        {/* Header */}
                        <div className="mb-6">
                            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
                                <Users className="w-7 h-7 text-blue-600" />
                                User Management
                            </h1>
                            <p className="text-gray-600 mt-1">
                                Manage user roles across the platform. Assign or revoke admin privileges.
                            </p>
                        </div>

                        {/* Search and Filter */}
                        <div className="mb-6 flex flex-col md:flex-row gap-4">
                            <div className="relative flex-1 max-w-md">
                                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                                <input
                                    type="text"
                                    placeholder="Search users..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                />
                            </div>
                            <div className="w-full md:w-48">
                                <select
                                    value={roleFilter}
                                    onChange={(e) => setRoleFilter(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                                >
                                    <option value="ALL">All Roles</option>
                                    {ROLES.map(role => (
                                        <option key={role.value} value={role.value}>{role.label}</option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        {/* Users Table */}
                        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
                            {loading ? (
                                <div className="flex items-center justify-center py-12">
                                    <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
                                </div>
                            ) : filteredUsers.length === 0 ? (
                                <div className="text-center py-12 text-gray-500">
                                    <Users className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                                    No users found
                                </div>
                            ) : (
                                <table className="w-full">
                                    <thead className="bg-gray-50 border-b">
                                        <tr>
                                            <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider">User</th>
                                            <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider">Email</th>
                                            <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider">Company</th>
                                            <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider">Role</th>
                                            <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100">
                                        {filteredUsers.map((u) => {
                                            const roleInfo = getRoleInfo(u.role);
                                            const RoleIcon = roleInfo.icon;
                                            const isCurrentUser = u.id === user?.id;

                                            return (
                                                <tr key={u.id} className={`hover:bg-gray-50 ${isCurrentUser ? 'bg-blue-50/50' : ''}`}>
                                                    <td className="px-6 py-4">
                                                        <div className="flex items-center gap-3">
                                                            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-medium">
                                                                {u.firstName?.[0] || u.username?.[0] || '?'}
                                                            </div>
                                                            <div>
                                                                <div className="font-medium text-gray-900">
                                                                    {u.firstName} {u.lastName}
                                                                    {isCurrentUser && <span className="ml-2 text-xs text-blue-600">(You)</span>}
                                                                </div>
                                                                <div className="text-sm text-gray-500">@{u.username}</div>
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 text-sm text-gray-600">{u.email}</td>
                                                    <td className="px-6 py-4 text-sm text-gray-600">
                                                        {u.company?.name || <span className="text-gray-400">No company</span>}
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-${roleInfo.color}-100 text-${roleInfo.color}-700`}>
                                                            <RoleIcon className="w-3.5 h-3.5" />
                                                            {roleInfo.label}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        {isCurrentUser ? (
                                                            <span className="text-xs text-gray-400">Cannot change own role</span>
                                                        ) : (
                                                            <select
                                                                value={u.role}
                                                                onChange={(e) => handleRoleChange(u.id, e.target.value)}
                                                                disabled={updatingRole === u.id}
                                                                className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
                                                            >
                                                                {ROLES.map((role) => (
                                                                    <option key={role.value} value={role.value}>
                                                                        {role.label}
                                                                    </option>
                                                                ))}
                                                            </select>
                                                        )}
                                                        {updatingRole === u.id && (
                                                            <RefreshCw className="w-4 h-4 animate-spin text-blue-500 inline ml-2" />
                                                        )}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            )}
                        </div>

                        {/* Stats */}
                        <div className="mt-6 grid grid-cols-4 gap-4">
                            {ROLES.map((role) => {
                                const count = users.filter(u => u.role === role.value).length;
                                const RoleIcon = role.icon;
                                return (
                                    <div key={role.value} className="bg-white rounded-lg p-4 border shadow-sm">
                                        <div className="flex items-center gap-2 text-gray-600 mb-1">
                                            <RoleIcon className="w-4 h-4" />
                                            <span className="text-sm">{role.label}s</span>
                                        </div>
                                        <div className="text-2xl font-bold text-gray-900">{count}</div>
                                    </div>
                                );
                            })}
                        </div>
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
        </div>
    );
}

export const UserManagementPage = memo(UserManagementPageComponent);
export default UserManagementPage;
