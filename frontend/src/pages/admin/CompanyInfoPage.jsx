import { memo, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Navbar } from '../../components/Navbar/Navbar';
import { Sidebar } from '../../components/Sidebar/Sidebar';
import { useAuthStore } from '../../store/authStore';
import { useUIStore } from '../../store/uiStore';
import * as companyApi from '../../services/companyApi';
import {
    Building2,
    Globe,
    Phone,
    MapPin,
    Edit2,
    Save,
    X,
    RefreshCw,
} from 'lucide-react';

function CompanyInfoPageComponent() {
    const { t } = useTranslation();
    const { user } = useAuthStore();
    const showSuccessToast = useUIStore((s) => s.showSuccessToast);
    const showErrorToast = useUIStore((s) => s.showErrorToast);
    const sidebarOpen = useUIStore((s) => s.sidebarOpen);
    const closeSidebar = useUIStore((s) => s.closeSidebar);

    const [company, setCompany] = useState(null);
    const [loading, setLoading] = useState(true);
    const [isEditing, setIsEditing] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        website: '',
        phone: '',
        address: '',
    });

    // Check if user has permission to edit (COMPANY_ADMIN only)
    // SUPER_ADMIN can edit via Management page, but if they land here they can also edit.
    // EMPLOYEE/EXECUTIVE are view-only.
    const canEdit = user?.role === 'COMPANY_ADMIN';

    useEffect(() => {
        if (user?.companyId) {
            fetchCompany(user.companyId);
        }
    }, [user]);

    const fetchCompany = async (companyId) => {
        setLoading(true);
        try {
            const response = await companyApi.getCompany(companyId);
            const data = response.data.company;
            setCompany(data);
            setFormData({
                name: data.name || '',
                description: data.description || '',
                website: data.website || '',
                phone: data.phone || '',
                address: data.address || '',
            });
        } catch (error) {
            console.error('Failed to fetch company:', error);
            showErrorToast('Failed to load company details');
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        try {
            await companyApi.updateCompany(company.id, formData);
            setCompany({ ...company, ...formData });
            setIsEditing(false);
            showSuccessToast('Company information updated successfully');
        } catch (error) {
            console.error('Failed to update company:', error);
            showErrorToast('Failed to update company information');
        } finally {
            setSubmitting(false);
        }
    };

    const handleCancel = () => {
        setIsEditing(false);
        // Reset form data
        if (company) {
            setFormData({
                name: company.name || '',
                description: company.description || '',
                website: company.website || '',
                phone: company.phone || '',
                address: company.address || '',
            });
        }
    };

    if (loading) {
        return (
            <div className="flex flex-col min-h-screen bg-gray-50">
                <Navbar />
                <div className="flex flex-1 overflow-hidden">
                    <Sidebar />
                    <main className="flex-1 flex items-center justify-center">
                        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
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
                    <div className="p-4 sm:p-6 lg:p-8 max-w-4xl mx-auto">
                        {/* Header */}
                        <div className="flex items-center justify-between mb-6">
                            <div>
                                <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                                    <Building2 className="w-7 h-7" />
                                    Company Information
                                </h1>
                                <p className="text-gray-500 mt-1">
                                    View and manage your company details
                                </p>
                            </div>

                            {canEdit && !isEditing && (
                                <button
                                    onClick={() => setIsEditing(true)}
                                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                                >
                                    <Edit2 className="w-4 h-4" />
                                    Edit Details
                                </button>
                            )}
                        </div>

                        {/* Content */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                            {isEditing ? (
                                <form onSubmit={handleSubmit} className="p-6 space-y-6">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="col-span-full">
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Company Name
                                            </label>
                                            <input
                                                type="text"
                                                value={formData.name}
                                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                                required
                                            />
                                        </div>

                                        <div className="col-span-full">
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Description
                                            </label>
                                            <textarea
                                                value={formData.description}
                                                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                                rows={3}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                                placeholder="Tell us about your company..."
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Website
                                            </label>
                                            <div className="relative">
                                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                                    <Globe className="h-5 w-5 text-gray-400" />
                                                </div>
                                                <input
                                                    type="url"
                                                    value={formData.website}
                                                    onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                                                    className="w-full pl-10 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                                    placeholder="https://example.com"
                                                />
                                            </div>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Phone Number
                                            </label>
                                            <div className="relative">
                                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                                    <Phone className="h-5 w-5 text-gray-400" />
                                                </div>
                                                <input
                                                    type="tel"
                                                    value={formData.phone}
                                                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                                    className="w-full pl-10 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                                    placeholder="+1 (555) 000-0000"
                                                />
                                            </div>
                                        </div>

                                        <div className="col-span-full">
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Address
                                            </label>
                                            <div className="relative">
                                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                                    <MapPin className="h-5 w-5 text-gray-400" />
                                                </div>
                                                <input
                                                    type="text"
                                                    value={formData.address}
                                                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                                                    className="w-full pl-10 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                                    placeholder="123 Business Ave, Tech City, TC 90210"
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center justify-end gap-3 pt-4 border-t">
                                        <button
                                            type="button"
                                            onClick={handleCancel}
                                            className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                                            disabled={submitting}
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
                                                <Save className="w-4 h-4" />
                                            )}
                                            Save Changes
                                        </button>
                                    </div>
                                </form>
                            ) : (
                                <div className="p-6">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8">
                                        <div className="col-span-full">
                                            <h2 className="text-xl font-semibold text-gray-900 mb-2">{company?.name}</h2>
                                            <p className="text-gray-600 whitespace-pre-wrap">
                                                {company?.description || 'No description provided.'}
                                            </p>
                                        </div>

                                        <div className="space-y-4">
                                            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">Contact Details</h3>

                                            <div className="flex items-start gap-3">
                                                <Globe className="w-5 h-5 text-gray-400 mt-0.5" />
                                                <div>
                                                    <span className="block text-sm font-medium text-gray-700">Website</span>
                                                    {company?.website ? (
                                                        <a
                                                            href={company.website}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="text-blue-600 hover:underline"
                                                        >
                                                            {company.website}
                                                        </a>
                                                    ) : (
                                                        <span className="text-gray-400 italic">Not set</span>
                                                    )}
                                                </div>
                                            </div>

                                            <div className="flex items-start gap-3">
                                                <Phone className="w-5 h-5 text-gray-400 mt-0.5" />
                                                <div>
                                                    <span className="block text-sm font-medium text-gray-700">Phone</span>
                                                    <span className={company?.phone ? "text-gray-900" : "text-gray-400 italic"}>
                                                        {company?.phone || 'Not set'}
                                                    </span>
                                                </div>
                                            </div>

                                            <div className="flex items-start gap-3">
                                                <MapPin className="w-5 h-5 text-gray-400 mt-0.5" />
                                                <div>
                                                    <span className="block text-sm font-medium text-gray-700">Address</span>
                                                    <span className={company?.address ? "text-gray-900" : "text-gray-400 italic"}>
                                                        {company?.address || 'Not set'}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="space-y-4">
                                            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">Company Status</h3>
                                            <div className="flex items-center gap-2">
                                                <div className={`w-3 h-3 rounded-full ${company?.isActive ? 'bg-green-500' : 'bg-red-500'}`} />
                                                <span className="font-medium text-gray-900">{company?.isActive ? 'Active' : 'Inactive'}</span>
                                            </div>
                                            <div className="text-sm text-gray-500">
                                                Created on {new Date(company?.created_at).toLocaleDateString()}
                                            </div>
                                        </div>

                                    </div>
                                </div>
                            )}
                        </div>

                        {!canEdit && (
                            <p className="mt-4 text-center text-gray-500 text-sm">
                                View-only access. Contact your Company Admin to update these details.
                            </p>
                        )}
                    </div>
                </main>

                {/* Mobile sidebar overlay */}
                {sidebarOpen && (
                    <div
                        className="fixed inset-0 z-20 bg-black bg-opacity-50 md:hidden"
                        onClick={closeSidebar}
                    />
                )}
            </div>
        </div>
    );
}

export const CompanyInfoPage = memo(CompanyInfoPageComponent);
export default CompanyInfoPage;
