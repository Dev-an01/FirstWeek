/**
 * ExecutiveDetailView
 *
 * Shows executive profile, documents, and calibration controls.
 */

import { useState, useCallback, useMemo } from 'react';
import {
  ArrowLeft,
  User,
  Plus,
  FileText,
  RefreshCw,
  Play,
  CheckCircle,
  XCircle,
  AlertCircle,
  Mic,
  Database,
  Building2,
  ChevronDown,
  ChevronRight,
  Brain,
  MessageSquare,
  Volume2,
} from 'lucide-react';
import { useOnboardingStore } from '../../../store/onboardingStore';
import { useUIStore } from '../../../store/uiStore';
import { DocumentRow } from '../../../components/onboarding/DocumentRow';
import { FileUploader } from '../../../components/onboarding/FileUploader';
import { CalibrationProgress } from '../../../components/onboarding/CalibrationProgress';
import { Button } from '../../../components/ui/Button';
import Modal from '../../../components/ui/Modal';
import { FormInput } from '../../../components/ui/FormInput';
import { VoiceSampleUploader } from '../../../components/onboarding/VoiceSampleUploader';

export function ExecutiveDetailView({ onBack }) {
  // Store subscriptions (selective for performance)
  const selectedCompany = useOnboardingStore((s) => s.selectedCompany);
  const selectedExecutive = useOnboardingStore((s) => s.selectedExecutive);
  const selectedExecutiveLoading = useOnboardingStore((s) => s.selectedExecutiveLoading);
  const profileDocuments = useOnboardingStore((s) => s.profileDocuments);
  const profileDocumentsLoading = useOnboardingStore((s) => s.profileDocumentsLoading);
  const activeJob = useOnboardingStore((s) => s.activeJob);
  const executives = useOnboardingStore((s) => s.executives);

  const voiceKeysStatus = useOnboardingStore((s) => s.voiceKeysStatus);
  const fetchVoiceKeysStatus = useOnboardingStore((s) => s.fetchVoiceKeysStatus);

  const uploadProfileDocuments = useOnboardingStore((s) => s.uploadProfileDocuments);
  const deleteProfileDocument = useOnboardingStore((s) => s.deleteProfileDocument);
  const startCalibration = useOnboardingStore((s) => s.startCalibration);
  const updateExecutive = useOnboardingStore((s) => s.updateExecutive);
  const selectExecutive = useOnboardingStore((s) => s.selectExecutive);

  const showSuccessToast = useUIStore((s) => s.showSuccessToast);
  const showErrorToast = useUIStore((s) => s.showErrorToast);

  // Local state
  const [showUploader, setShowUploader] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [editForm, setEditForm] = useState({
    name: '',
    title: '',
    reports_to: '',
  });
  const [showProfile, setShowProfile] = useState(false);
  const [showVoiceprint, setShowVoiceprint] = useState(false);
  const [showVoiceCloning, setShowVoiceCloning] = useState(false);

  // Get manager name for display
  const managerName = useMemo(() => {
    if (!selectedExecutive?.reports_to || !executives.length) return null;
    const manager = executives.find((e) => e.id === selectedExecutive.reports_to);
    return manager?.name || selectedExecutive.reports_to;
  }, [selectedExecutive?.reports_to, executives]);

  // Profile status indicators
  const profileStatus = useMemo(() => {
    if (!selectedExecutive) return null;
    const keys = voiceKeysStatus?.keys || {};
    const voiceKeyCount = (keys['en-US']?.exists ? 1 : 0) + (keys['ja-JP']?.exists ? 1 : 0);
    return {
      hasProfile: selectedExecutive.has_profile || false,
      hasVoiceprint: selectedExecutive.has_voiceprint || false,
      hasEmbeddings: selectedExecutive.embeddings_count > 0,
      embeddingsCount: selectedExecutive.embeddings_count || 0,
      documentsCount: profileDocuments.length,
      voiceKeyCount,
    };
  }, [selectedExecutive, profileDocuments.length, voiceKeysStatus]);

  // Check if calibration can start
  const canCalibrate = useMemo(() => {
    return profileDocuments.length > 0 && !activeJob;
  }, [profileDocuments.length, activeJob]);

  // Handlers
  const handleRefresh = useCallback(() => {
    if (selectedCompany?.id && selectedExecutive?.id) {
      selectExecutive(selectedCompany.id, selectedExecutive.id).catch((err) =>
        showErrorToast(err.message)
      );
    }
  }, [selectedCompany?.id, selectedExecutive?.id, selectExecutive, showErrorToast]);

  const handleUploadDocuments = useCallback(
    async (files, options = {}) => {
      setIsUploading(true);
      try {
        await uploadProfileDocuments(selectedCompany.id, selectedExecutive.id, files, options);
        showSuccessToast(`${files.length} document(s) uploaded`);
        setShowUploader(false);
      } catch (error) {
        showErrorToast(error.message || 'Failed to upload documents');
      } finally {
        setIsUploading(false);
      }
    },
    [selectedCompany?.id, selectedExecutive?.id, uploadProfileDocuments, showSuccessToast, showErrorToast]
  );

  const handleDeleteDocument = useCallback(
    async (docId) => {
      try {
        await deleteProfileDocument(selectedCompany.id, selectedExecutive.id, docId);
        showSuccessToast('Document deleted');
      } catch (error) {
        showErrorToast(error.message || 'Failed to delete document');
      }
    },
    [selectedCompany?.id, selectedExecutive?.id, deleteProfileDocument, showSuccessToast, showErrorToast]
  );

  const handleStartCalibration = useCallback(async () => {
    if (!canCalibrate) return;

    setIsCalibrating(true);
    try {
      await startCalibration(selectedCompany.id, selectedExecutive.id);
      showSuccessToast('Calibration started');
    } catch (error) {
      showErrorToast(error.message || 'Failed to start calibration');
    } finally {
      setIsCalibrating(false);
    }
  }, [canCalibrate, selectedCompany?.id, selectedExecutive?.id, startCalibration, showSuccessToast, showErrorToast]);

  const handleVoiceKeyGenerated = useCallback(() => {
    if (selectedCompany?.id && selectedExecutive?.id) {
      fetchVoiceKeysStatus(selectedCompany.id, selectedExecutive.id).catch(() => {});
    }
  }, [selectedCompany?.id, selectedExecutive?.id, fetchVoiceKeysStatus]);

  const handleOpenEditModal = useCallback(() => {
    if (selectedExecutive) {
      setEditForm({
        name: selectedExecutive.name || '',
        title: selectedExecutive.title || '',
        reports_to: selectedExecutive.reports_to || '',
      });
      setIsEditModalOpen(true);
    }
  }, [selectedExecutive]);

  const handleCloseEditModal = useCallback(() => {
    setIsEditModalOpen(false);
  }, []);

  const handleSaveEdit = useCallback(async () => {
    if (!editForm.name.trim()) {
      showErrorToast('Name is required');
      return;
    }

    setIsSavingEdit(true);
    try {
      await updateExecutive(selectedCompany.id, selectedExecutive.id, {
        name: editForm.name.trim(),
        title: editForm.title.trim() || undefined,
        reports_to: editForm.reports_to || undefined,
      });
      showSuccessToast('Executive updated');
      handleCloseEditModal();
    } catch (error) {
      showErrorToast(error.message || 'Failed to update executive');
    } finally {
      setIsSavingEdit(false);
    }
  }, [editForm, selectedCompany?.id, selectedExecutive?.id, updateExecutive, showSuccessToast, showErrorToast, handleCloseEditModal]);

  // Loading state
  if (selectedExecutiveLoading && !selectedExecutive) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-6 h-6 text-primary animate-spin" />
      </div>
    );
  }

  if (!selectedExecutive) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Executive not found</p>
        {onBack && (
          <Button onClick={onBack} className="mt-4">
            Back to Company
          </Button>
        )}
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
          <span className="text-sm">Back to {selectedCompany?.name || 'Company'}</span>
        </button>
      )}

      {/* Executive Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-primary-light rounded-xl">
              <User className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">{selectedExecutive.name}</h1>
              <p className="text-sm text-gray-500">
                {selectedExecutive.title || 'No title'}
                {managerName && ` • Reports to ${managerName}`}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                ID: {selectedExecutive.id}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-5 h-5" />
            </button>
            <Button variant="outline" onClick={handleOpenEditModal}>
              Edit
            </Button>
          </div>
        </div>
      </div>

      {/* Profile Status Cards */}
      {profileStatus && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-2">
              {profileStatus.hasProfile ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <XCircle className="w-4 h-4 text-gray-300" />
              )}
              <span className="text-xs text-gray-500">Profile</span>
            </div>
            <p className={`text-sm font-medium ${profileStatus.hasProfile ? 'text-green-600' : 'text-gray-400'}`}>
              {profileStatus.hasProfile ? 'Generated' : 'Not Generated'}
            </p>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-2">
              {profileStatus.hasVoiceprint ? (
                <Mic className="w-4 h-4 text-green-500" />
              ) : (
                <Mic className="w-4 h-4 text-gray-300" />
              )}
              <span className="text-xs text-gray-500">Voiceprint</span>
            </div>
            <p className={`text-sm font-medium ${profileStatus.hasVoiceprint ? 'text-green-600' : 'text-gray-400'}`}>
              {profileStatus.hasVoiceprint ? 'Generated' : 'Not Generated'}
            </p>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Database className={`w-4 h-4 ${profileStatus.hasEmbeddings ? 'text-green-500' : 'text-gray-300'}`} />
              <span className="text-xs text-gray-500">Embeddings</span>
            </div>
            <p className={`text-sm font-medium ${profileStatus.hasEmbeddings ? 'text-green-600' : 'text-gray-400'}`}>
              {profileStatus.embeddingsCount > 0 ? `${profileStatus.embeddingsCount} vectors` : 'None'}
            </p>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-primary" />
              <span className="text-xs text-gray-500">Documents</span>
            </div>
            <p className="text-sm font-medium text-gray-900">
              {profileStatus.documentsCount} file{profileStatus.documentsCount !== 1 ? 's' : ''}
            </p>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Volume2 className={`w-4 h-4 ${profileStatus.voiceKeyCount > 0 ? 'text-green-500' : 'text-gray-300'}`} />
              <span className="text-xs text-gray-500">Voice Keys</span>
            </div>
            <p className={`text-sm font-medium ${profileStatus.voiceKeyCount > 0 ? 'text-green-600' : 'text-gray-400'}`}>
              {profileStatus.voiceKeyCount}/2 languages
            </p>
          </div>
        </div>
      )}

      {/* Active Job Progress */}
      {activeJob && (
        <div className="mb-6">
          <CalibrationProgress job={activeJob} />
        </div>
      )}

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Profile Documents Section */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-primary" />
              <h2 className="font-semibold text-gray-900">Profile Documents</h2>
              <span className="text-sm text-gray-400">({profileDocuments.length})</span>
            </div>
            <Button
              variant="outline"
              fullWidth={false}
              className="h-9 px-5 text-sm font-medium rounded-full flex items-center gap-1 !py-0"
              onClick={() => setShowUploader(!showUploader)}
            >
              <Plus className="w-4 h-4" />
              Upload
            </Button>
          </div>

          <p className="text-xs text-gray-500 mb-4">
            Interview transcripts, bios, speeches - used for profile extraction
          </p>

          {showUploader && (
            <div className="mb-4">
              <FileUploader
                onUpload={handleUploadDocuments}
                uploading={isUploading}
                showAccessLevel
              />
            </div>
          )}

          {profileDocumentsLoading && profileDocuments.length === 0 ? (
            <div className="py-8 text-center">
              <RefreshCw className="w-5 h-5 text-gray-400 animate-spin mx-auto" />
            </div>
          ) : profileDocuments.length === 0 ? (
            <div className="py-8 text-center text-gray-500">
              <FileText className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-sm">No profile documents</p>
              <p className="text-xs text-gray-400">Upload interviews or bios to generate profile</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {profileDocuments.map((doc) => (
                <DocumentRow
                  key={doc.id}
                  document={doc}
                  onDelete={handleDeleteDocument}
                />
              ))}
            </div>
          )}
        </div>

        {/* Calibration Section */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Play className="w-5 h-5 text-primary" />
            <h2 className="font-semibold text-gray-900">Calibration</h2>
          </div>

          <p className="text-sm text-gray-600 mb-4">
            Run calibration to extract the executive profile from uploaded documents.
            This will generate:
          </p>

          <ul className="text-sm text-gray-500 mb-6 space-y-2">
            <li className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-gray-400" />
              Executive profile (values, priorities, style)
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-gray-400" />
              Voiceprint (communication patterns)
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-gray-400" />
              Vector embeddings for RAG retrieval
            </li>
          </ul>

          {!canCalibrate && profileDocuments.length === 0 && (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg mb-4">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-amber-500 mt-0.5" />
                <p className="text-sm text-amber-700">
                  Upload at least one profile document before calibrating.
                </p>
              </div>
            </div>
          )}

          {activeJob && (
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg mb-4">
              <div className="flex items-start gap-2">
                <RefreshCw className="w-4 h-4 text-blue-500 mt-0.5 animate-spin" />
                <p className="text-sm text-blue-700">
                  Calibration in progress. Please wait for it to complete.
                </p>
              </div>
            </div>
          )}

          <Button
            onClick={handleStartCalibration}
            disabled={!canCalibrate || isCalibrating}
            className="w-full"
          >
            {isCalibrating ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Start Calibration
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Voice Cloning Section */}
      <div className="mt-6 bg-white rounded-xl border border-gray-200 overflow-hidden">
        <button
          onClick={() => setShowVoiceCloning(!showVoiceCloning)}
          className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Volume2 className="w-5 h-5 text-primary" />
            <span className="font-semibold text-gray-900">Voice Cloning</span>
            {voiceKeysStatus?.keys && (
              <div className="flex items-center gap-1.5 ml-2">
                {voiceKeysStatus.keys['en-US']?.exists && (
                  <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded">en-US</span>
                )}
                {voiceKeysStatus.keys['ja-JP']?.exists && (
                  <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded">ja-JP</span>
                )}
                {!voiceKeysStatus.keys['en-US']?.exists && !voiceKeysStatus.keys['ja-JP']?.exists && (
                  <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">No Keys</span>
                )}
              </div>
            )}
          </div>
          {showVoiceCloning ? (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-400" />
          )}
        </button>
        {showVoiceCloning && (
          <div className="border-t border-gray-200 p-4">
            <p className="text-sm text-gray-600 mb-4">
              Upload voice samples to generate per-executive voice cloning keys.
              Each language requires a reference audio and a consent audio reading the script below.
            </p>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <VoiceSampleUploader
                companyId={selectedCompany?.id}
                executiveId={selectedExecutive?.id}
                language="en"
                hasExistingKey={voiceKeysStatus?.keys?.['en-US']?.exists || false}
                onKeyGenerated={handleVoiceKeyGenerated}
              />
              <VoiceSampleUploader
                companyId={selectedCompany?.id}
                executiveId={selectedExecutive?.id}
                language="ja"
                hasExistingKey={voiceKeysStatus?.keys?.['ja-JP']?.exists || false}
                onKeyGenerated={handleVoiceKeyGenerated}
              />
            </div>
          </div>
        )}
      </div>

      {/* Profile Viewer */}
      {selectedExecutive?.profile && (
        <div className="mt-6 bg-white rounded-xl border border-gray-200 overflow-hidden">
          <button
            onClick={() => setShowProfile(!showProfile)}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-primary" />
              <span className="font-semibold text-gray-900">Executive Profile</span>
              <span className="text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded">Generated</span>
            </div>
            {showProfile ? (
              <ChevronDown className="w-5 h-5 text-gray-400" />
            ) : (
              <ChevronRight className="w-5 h-5 text-gray-400" />
            )}
          </button>
          {showProfile && (
            <div className="border-t border-gray-200 p-4 max-h-96 overflow-y-auto">
              <div className="space-y-4">
                {/* Core Values */}
                {selectedExecutive.profile.core_values && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Core Values</h4>
                    <div className="space-y-2">
                      {selectedExecutive.profile.core_values.map((value, idx) => (
                        <div key={idx} className="bg-gray-50 rounded-lg p-3">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs bg-primary text-white px-2 py-0.5 rounded">#{value.priority}</span>
                            <span className="font-medium text-sm">{value.name}</span>
                          </div>
                          <p className="text-xs text-gray-600">{value.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Background */}
                {selectedExecutive.profile.background && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Background</h4>
                    <div className="bg-gray-50 rounded-lg p-3 text-sm">
                      {selectedExecutive.profile.background.education && (
                        <p><span className="text-gray-500">Education:</span> {selectedExecutive.profile.background.education}</p>
                      )}
                      {selectedExecutive.profile.background.expertise && (
                        <p className="mt-1"><span className="text-gray-500">Expertise:</span> {selectedExecutive.profile.background.expertise.join(', ')}</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Decision Making */}
                {selectedExecutive.profile.decision_making && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Decision Making</h4>
                    <div className="bg-gray-50 rounded-lg p-3 text-sm">
                      <p className="text-gray-600">{selectedExecutive.profile.decision_making.philosophy}</p>
                      {selectedExecutive.profile.decision_making.risk_tolerance && (
                        <p className="mt-2"><span className="text-gray-500">Risk Tolerance:</span> {selectedExecutive.profile.decision_making.risk_tolerance}</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Red Flags */}
                {selectedExecutive.profile.red_flags && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Red Flags</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {selectedExecutive.profile.red_flags.always_do && (
                        <div className="bg-green-50 rounded-lg p-3">
                          <p className="text-xs font-medium text-green-700 mb-1">Always Do</p>
                          <ul className="text-xs text-green-600 space-y-1">
                            {selectedExecutive.profile.red_flags.always_do.slice(0, 3).map((item, idx) => (
                              <li key={idx}>• {item}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {selectedExecutive.profile.red_flags.never_approve && (
                        <div className="bg-red-50 rounded-lg p-3">
                          <p className="text-xs font-medium text-red-700 mb-1">Never Approve</p>
                          <ul className="text-xs text-red-600 space-y-1">
                            {selectedExecutive.profile.red_flags.never_approve.slice(0, 3).map((item, idx) => (
                              <li key={idx}>• {item}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Full JSON view toggle */}
                <details className="mt-4">
                  <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">View Raw JSON</summary>
                  <pre className="mt-2 p-3 bg-gray-100 rounded-lg text-xs overflow-x-auto max-h-64">
                    {JSON.stringify(selectedExecutive.profile, null, 2)}
                  </pre>
                </details>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Voiceprint Viewer */}
      {selectedExecutive?.voiceprint && (
        <div className="mt-4 bg-white rounded-xl border border-gray-200 overflow-hidden">
          <button
            onClick={() => setShowVoiceprint(!showVoiceprint)}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-purple-500" />
              <span className="font-semibold text-gray-900">Voiceprint</span>
              <span className="text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded">Generated</span>
            </div>
            {showVoiceprint ? (
              <ChevronDown className="w-5 h-5 text-gray-400" />
            ) : (
              <ChevronRight className="w-5 h-5 text-gray-400" />
            )}
          </button>
          {showVoiceprint && (
            <div className="border-t border-gray-200 p-4 max-h-96 overflow-y-auto">
              <pre className="p-3 bg-gray-100 rounded-lg text-xs overflow-x-auto">
                {JSON.stringify(selectedExecutive.voiceprint, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Company Knowledgebase Reference */}
      <div className="mt-6 bg-gray-50 rounded-xl border border-gray-200 p-4">
        <div className="flex items-center gap-2 mb-2">
          <Building2 className="w-4 h-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">Company Knowledgebase</span>
        </div>
        <p className="text-xs text-gray-500">
          This executive also has access to company-wide knowledgebase documents.
          Manage them from the company page.
        </p>
      </div>

      {/* Edit Executive Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={handleCloseEditModal}
        title="Edit Executive"
      >
        <div className="space-y-4">
          <FormInput
            type="text"
            placeholder="Full Name"
            value={editForm.name}
            onChange={(value) => setEditForm((prev) => ({ ...prev, name: value }))}
            required
            maxLength={255}
          />

          <FormInput
            type="text"
            placeholder="Title (e.g., CEO, CTO)"
            value={editForm.title}
            onChange={(value) => setEditForm((prev) => ({ ...prev, title: value }))}
            maxLength={100}
          />

          {executives.length > 1 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Reports To
              </label>
              <select
                value={editForm.reports_to}
                onChange={(e) => setEditForm((prev) => ({ ...prev, reports_to: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">None (Top Level)</option>
                {executives
                  .filter((exec) => exec.id !== selectedExecutive?.id)
                  .map((exec) => (
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
              onClick={handleCloseEditModal}
              disabled={isSavingEdit}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveEdit}
              disabled={isSavingEdit || !editForm.name.trim()}
              className="flex-1"
            >
              {isSavingEdit ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default ExecutiveDetailView;
