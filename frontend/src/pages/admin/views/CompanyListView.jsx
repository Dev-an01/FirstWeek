/**
 * CompanyListView
 *
 * Displays the grid of companies with search and create functionality.
 */

import { useState, useCallback, useMemo } from 'react';
import { Plus, Search, Building2, RefreshCw } from 'lucide-react';
import { useOnboardingStore } from '../../../store/onboardingStore';
import { useUIStore } from '../../../store/uiStore';
import { useDebounce } from '../../../hooks/useDebounce';
import { CompanyCard } from '../../../components/onboarding/CompanyCard';
import { Button } from '../../../components/ui/Button';
import Modal from '../../../components/ui/Modal';
import { FormInput } from '../../../components/ui/FormInput';

export function CompanyListView({ onSelectCompany }) {
  // Store subscriptions (selective for performance)
  const companies = useOnboardingStore((s) => s.companies);
  const companiesLoading = useOnboardingStore((s) => s.companiesLoading);
  const fetchCompanies = useOnboardingStore((s) => s.fetchCompanies);
  const createCompany = useOnboardingStore((s) => s.createCompany);

  const showSuccessToast = useUIStore((s) => s.showSuccessToast);
  const showErrorToast = useUIStore((s) => s.showErrorToast);

  // Local state
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newCompany, setNewCompany] = useState({
    id: '',
    name: '',
    industry: '',
  });

  // Debounced search
  const debouncedSearch = useDebounce(searchQuery, 300);

  // Filtered companies
  const filteredCompanies = useMemo(() => {
    if (!debouncedSearch) return companies;
    const query = debouncedSearch.toLowerCase();
    return companies.filter(
      (c) =>
        c.name?.toLowerCase().includes(query) ||
        c.industry?.toLowerCase().includes(query) ||
        c.id?.toLowerCase().includes(query)
    );
  }, [companies, debouncedSearch]);

  // Handlers
  const handleRefresh = useCallback(() => {
    fetchCompanies().catch((err) => showErrorToast(err.message));
  }, [fetchCompanies, showErrorToast]);

  const handleOpenCreateModal = useCallback(() => {
    setNewCompany({ id: '', name: '', industry: '' });
    setIsCreateModalOpen(true);
  }, []);

  const handleCloseCreateModal = useCallback(() => {
    setIsCreateModalOpen(false);
    setNewCompany({ id: '', name: '', industry: '' });
  }, []);

  const handleCreateCompany = useCallback(async () => {
    if (!newCompany.id.trim() || !newCompany.name.trim()) {
      showErrorToast('Company ID and Name are required');
      return;
    }

    // Validate ID format (alphanumeric + underscore)
    if (!/^[a-zA-Z0-9_]+$/.test(newCompany.id)) {
      showErrorToast('Company ID must be alphanumeric with underscores only');
      return;
    }

    setIsCreating(true);
    try {
      const created = await createCompany({
        id: newCompany.id.trim().toLowerCase(),
        name: newCompany.name.trim(),
        industry: newCompany.industry.trim() || undefined,
      });
      showSuccessToast(`Company "${created.name}" created successfully`);
      handleCloseCreateModal();
      // Navigate to the new company
      onSelectCompany(created.id);
    } catch (error) {
      showErrorToast(error.message || 'Failed to create company');
    } finally {
      setIsCreating(false);
    }
  }, [newCompany, createCompany, showSuccessToast, showErrorToast, handleCloseCreateModal, onSelectCompany]);

  // Generate ID from name
  const handleNameChange = useCallback((value) => {
    setNewCompany((prev) => ({
      ...prev,
      name: value,
      // Auto-generate ID if ID is empty or was auto-generated
      id: prev.id === '' || prev.id === prev.name.toLowerCase().replace(/[^a-z0-9]+/g, '_')
        ? value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
        : prev.id,
    }));
  }, []);

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Onboarding</h1>
        <p className="text-gray-500">Manage companies and executive profiles</p>
      </div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search companies..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          />
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={handleRefresh}
            disabled={companiesLoading}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-5 h-5 ${companiesLoading ? 'animate-spin' : ''}`} />
          </button>
          <Button onClick={handleOpenCreateModal}>
            <Plus className="w-4 h-4 mr-2" />
            New Company
          </Button>
        </div>
      </div>

      {/* Companies Grid */}
      {companiesLoading && companies.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-6 h-6 text-primary animate-spin" />
        </div>
      ) : filteredCompanies.length === 0 ? (
        <div className="text-center py-12">
          <Building2 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-1">
            {searchQuery ? 'No companies found' : 'No companies yet'}
          </h3>
          <p className="text-gray-500 mb-4">
            {searchQuery
              ? 'Try a different search term'
              : 'Create your first company to get started'}
          </p>
          {!searchQuery && (
            <Button onClick={handleOpenCreateModal}>
              <Plus className="w-4 h-4 mr-2" />
              Create Company
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCompanies.map((company) => (
            <CompanyCard
              key={company.id}
              company={company}
              onClick={onSelectCompany}
            />
          ))}
        </div>
      )}

      {/* Create Company Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={handleCloseCreateModal}
        title="Create New Company"
      >
        <div className="space-y-4">
          <FormInput
            type="text"
            placeholder="Company Name"
            value={newCompany.name}
            onChange={handleNameChange}
            required
            maxLength={255}
          />

          <FormInput
            type="text"
            placeholder="Company ID (auto-generated)"
            value={newCompany.id}
            onChange={(value) => setNewCompany((prev) => ({ ...prev, id: value.toLowerCase().replace(/[^a-z0-9_]/g, '') }))}
            required
            maxLength={50}
          />
          <p className="text-xs text-gray-400 -mt-2">
            Unique identifier (lowercase, alphanumeric, underscores)
          </p>

          <FormInput
            type="text"
            placeholder="Industry (optional)"
            value={newCompany.industry}
            onChange={(value) => setNewCompany((prev) => ({ ...prev, industry: value }))}
            maxLength={100}
          />

          <div className="flex gap-3 pt-2">
            <Button
              variant="outline"
              onClick={handleCloseCreateModal}
              disabled={isCreating}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateCompany}
              disabled={isCreating || !newCompany.id.trim() || !newCompany.name.trim()}
              className="flex-1"
            >
              {isCreating ? 'Creating...' : 'Create Company'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default CompanyListView;
