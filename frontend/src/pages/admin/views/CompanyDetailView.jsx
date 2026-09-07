/**
 * CompanyDetailView
 *
 * Shows company details, knowledgebase documents, and executives list.
 */

import { useState, useCallback, useMemo } from 'react';
import {
  ArrowLeft,
  Building2,
  Plus,
  Settings,
  Users,
  FileText,
  RefreshCw,
} from 'lucide-react';
import { useOnboardingStore } from '../../../store/onboardingStore';
import { useUIStore } from '../../../store/uiStore';
import { useAuthStore } from '../../../store/authStore';
import { ExecutiveRow } from '../../../components/onboarding/ExecutiveRow';
import { DocumentRow } from '../../../components/onboarding/DocumentRow';
import { FileUploader } from '../../../components/onboarding/FileUploader';
import { Button } from '../../../components/ui/Button';
import Modal from '../../../components/ui/Modal';
import { FormInput } from '../../../components/ui/FormInput';

export function CompanyDetailView({ onBack, onSelectExecutive }) {
  // Store subscriptions (selective for performance)
  const selectedCompany = useOnboardingStore((s) => s.selectedCompany);
  const selectedCompanyLoading = useOnboardingStore((s) => s.selectedCompanyLoading);
  const executives = useOnboardingStore((s) => s.executives);
  const executivesLoading = useOnboardingStore((s) => s.executivesLoading);
  const knowledgebaseDocuments = useOnboardingStore((s) => s.knowledgebaseDocuments);
  const knowledgebaseLoading = useOnboardingStore((s) => s.knowledgebaseLoading);

  const createExecutive = useOnboardingStore((s) => s.createExecutive);
  const uploadKnowledgebase = useOnboardingStore((s) => s.uploadKnowledgebase);
  const deleteKnowledgebaseDocument = useOnboardingStore((s) => s.deleteKnowledgebaseDocument);
  const selectCompany = useOnboardingStore((s) => s.selectCompany);

  const showSuccessToast = useUIStore((s) => s.showSuccessToast);
  const showErrorToast = useUIStore((s) => s.showErrorToast);

  const { user } = useAuthStore();
  const isAdmin = user?.role === 'COMPANY_ADMIN' || user?.role === 'SUPER_ADMIN';

  // Local state
  const [isExecModalOpen, setIsExecModalOpen] = useState(false);
  const [isCreatingExec, setIsCreatingExec] = useState(false);
  const [isUploadingKB, setIsUploadingKB] = useState(false);
  const [showKBUploader, setShowKBUploader] = useState(false);
  const [newExec, setNewExec] = useState({
    id: '',
    name: '',
    title: '',
    reports_to: '',
  });

  // Build hierarchy tree for executives
  const executiveTree = useMemo(() => {
    if (!executives.length) return [];

    // Group by reports_to
    const byManager = {};
    const roots = [];

    executives.forEach((exec) => {
      if (!exec.reports_to) {
        roots.push({ ...exec, indentLevel: 0 });
      } else {
        if (!byManager[exec.reports_to]) byManager[exec.reports_to] = [];
        byManager[exec.reports_to].push(exec);
      }
    });

    // Recursively build tree
    const buildTree = (items, level = 0) => {
      const result = [];
      items.forEach((item) => {
        result.push({ ...item, indentLevel: level });
        const children = byManager[item.id] || [];
        if (children.length > 0) {
          result.push(...buildTree(children, level + 1));
        }
      });
      return result;
    };

    return buildTree(roots);
  }, [executives]);

  // Handlers
  const handleRefresh = useCallback(() => {
    if (selectedCompany?.id) {
      selectCompany(selectedCompany.id).catch((err) => showErrorToast(err.message));
    }
  }, [selectedCompany?.id, selectCompany, showErrorToast]);

  const handleOpenExecModal = useCallback(() => {
    setNewExec({ id: '', name: '', title: '', reports_to: '' });
    setIsExecModalOpen(true);
  }, []);

  const handleCloseExecModal = useCallback(() => {
    setIsExecModalOpen(false);
    setNewExec({ id: '', name: '', title: '', reports_to: '' });
    setIsExecModalOpen(false);
  }, []);

  const handleCreateExecutive = useCallback(async () => {
    if (!newExec.id.trim() || !newExec.name.trim()) {
      showErrorToast('Executive ID and Name are required');
      return;
    }

    if (!/^[a-zA-Z0-9_]+$/.test(newExec.id)) {
      showErrorToast('Executive ID must be alphanumeric with underscores only');
      return;
    }

    setIsCreatingExec(true);
    try {
      const created = await createExecutive(selectedCompany.id, {
        id: newExec.id.trim().toLowerCase(),
        name: newExec.name.trim(),
        title: newExec.title.trim() || undefined,
        reports_to: newExec.reports_to || undefined,
      });
      showSuccessToast(`Executive "${created.name}" created`);
      handleCloseExecModal();
      // Navigate to the new executive
      onSelectExecutive(created.id);
    } catch (error) {
      showErrorToast(error.message || 'Failed to create executive');
    } finally {
      setIsCreatingExec(false);
    }
  }, [newExec, selectedCompany?.id, createExecutive, showSuccessToast, showErrorToast, handleCloseExecModal, onSelectExecutive]);

  const handleNameChange = useCallback((value) => {
    setNewExec((prev) => ({
      ...prev,
      name: value,
      id: prev.id === '' || prev.id === prev.name.toLowerCase().replace(/[^a-z0-9]+/g, '_')
        ? value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
        : prev.id,
    }));
  }, []);

  const handleUploadKnowledgebase = useCallback(
    async (files, options = {}) => {
      setIsUploadingKB(true);
      try {
        await uploadKnowledgebase(selectedCompany.id, files, options);
        showSuccessToast(`${files.length} document(s) uploaded to knowledgebase`);
        setShowKBUploader(false);
      } catch (error) {
        showErrorToast(error.message || 'Failed to upload documents');
      } finally {
        setIsUploadingKB(false);
      }
    },
    [selectedCompany?.id, uploadKnowledgebase, showSuccessToast, showErrorToast]
  );

  const handleDeleteKBDocument = useCallback(
    async (docId) => {
      try {
        await deleteKnowledgebaseDocument(selectedCompany.id, docId);
        showSuccessToast('Document deleted');
      } catch (error) {
        showErrorToast(error.message || 'Failed to delete document');
      }
    },
    [selectedCompany?.id, deleteKnowledgebaseDocument, showSuccessToast, showErrorToast]
  );

  // Loading state
  if (selectedCompanyLoading && !selectedCompany) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-6 h-6 text-primary animate-spin" />
      </div>
    );
  }

  if (!selectedCompany) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Company not found</p>
        <Button onClick={onBack} className="mt-4">
          Back to Companies
        </Button>
      </div>
    );
  }

  return (
    <div>
      {/* Back Button */}
      {onBack && (
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-gray-500 hover:text-gray-700 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back to Companies</span>
        </button>
      )}

      {/* Company Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-primary-light rounded-xl">
              <Building2 className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">{selectedCompany.name}</h1>
              <p className="text-sm text-gray-500">
                {selectedCompany.industry || 'No industry'} • Created{' '}
                {new Date(selectedCompany.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>

          {user?.role === 'SUPER_ADMIN' && (
            <button
              onClick={handleRefresh}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              title="Refresh"
            >
              <Settings className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Knowledgebase Section */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-primary" />
              <h2 className="font-semibold text-gray-900">Company Knowledgebase</h2>
              <span className="text-sm text-gray-400">({knowledgebaseDocuments.length})</span>
            </div>
            <Button
              variant="outline"
              fullWidth={false}
              className="h-9 px-5 text-sm font-medium rounded-full flex items-center gap-1 !py-0"
              onClick={() => setShowKBUploader(!showKBUploader)}
            >
              <Plus className="w-4 h-4" />
              Upload
            </Button>
          </div>

          {showKBUploader && (
            <div className="mb-4">
              <FileUploader
                onUpload={handleUploadKnowledgebase}
                uploading={isUploadingKB}
                showAccessLevel
              />
            </div>
          )}

          {knowledgebaseLoading && knowledgebaseDocuments.length === 0 ? (
            <div className="py-8 text-center">
              <RefreshCw className="w-5 h-5 text-gray-400 animate-spin mx-auto" />
            </div>
          ) : knowledgebaseDocuments.length === 0 ? (
            <div className="py-8 text-center text-gray-500">
              <FileText className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-sm">No knowledgebase documents</p>
              <p className="text-xs text-gray-400">Upload company policies, procedures, etc.</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {knowledgebaseDocuments.map((doc) => (
                <DocumentRow
                  key={doc.id}
                  document={doc}
                  onDelete={handleDeleteKBDocument}
                />
              ))}
            </div>
          )}
        </div>

        {/* Executives Section */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-primary" />
              <h2 className="font-semibold text-gray-900">Executives</h2>
              <span className="text-sm text-gray-400">({executives.length})</span>
            </div>
            <Button
              onClick={handleOpenExecModal}
              fullWidth={false}
              className="h-9 px-5 text-sm font-medium rounded-full flex items-center gap-1 !py-0"
            >
              <Plus className="w-4 h-4" />
              Add Executive
            </Button>
          </div>

          {executivesLoading && executives.length === 0 ? (
            <div className="py-8 text-center">
              <RefreshCw className="w-5 h-5 text-gray-400 animate-spin mx-auto" />
            </div>
          ) : executives.length === 0 ? (
            <div className="py-8 text-center text-gray-500">
              <Users className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-sm">No executives yet</p>
              <p className="text-xs text-gray-400">Add executives to create their profiles</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {executiveTree.map((exec) => (
                <ExecutiveRow
                  key={exec.id}
                  executive={exec}
                  onClick={onSelectExecutive}
                  indentLevel={exec.indentLevel}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create Executive Modal */}
      <Modal
        isOpen={isExecModalOpen}
        onClose={handleCloseExecModal}
        title="Add Executive"
      >
        <div className="space-y-4">
          <FormInput
            type="text"
            placeholder="Full Name"
            value={newExec.name}
            onChange={handleNameChange}
            required
            maxLength={255}
          />

          <FormInput
            type="text"
            placeholder="Executive ID (auto-generated)"
            value={newExec.id}
            onChange={(value) => setNewExec((prev) => ({ ...prev, id: value.toLowerCase().replace(/[^a-z0-9_]/g, '') }))}
            required
            maxLength={50}
          />
          <p className="text-xs text-gray-400 -mt-2">
            Unique identifier (lowercase, alphanumeric, underscores)
          </p>

          <FormInput
            type="text"
            placeholder="Title (e.g., CEO, CTO)"
            value={newExec.title}
            onChange={(value) => setNewExec((prev) => ({ ...prev, title: value }))}
            maxLength={100}
          />

          {executives.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Reports To
              </label>
              <select
                value={newExec.reports_to}
                onChange={(e) => setNewExec((prev) => ({ ...prev, reports_to: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">None (Top Level)</option>
                {executives.map((exec) => (
                  <option key={exec.id} value={exec.id}>
                    {exec.name} {exec.title ? `(${exec.title})` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <Button
              variant="outline"
              onClick={handleCloseExecModal}
              disabled={isCreatingExec}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateExecutive}
              disabled={isCreatingExec || !newExec.id.trim() || !newExec.name.trim()}
              className="flex-1"
            >
              {isCreatingExec ? 'Creating...' : 'Add Executive'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default CompanyDetailView;
