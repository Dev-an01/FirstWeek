/**
 * Onboarding Store (Zustand)
 *
 * Manages state for the admin onboarding dashboard.
 * Follows performance patterns: selective subscriptions, optimistic updates.
 */

import { create } from 'zustand';
import * as api from '../services/onboardingApi';

export const useOnboardingStore = create((set, get) => ({
  // ═══════════════════════════════════════════════════════════════════════════
  // STATE
  // ═══════════════════════════════════════════════════════════════════════════

  // Companies
  companies: [],
  companiesLoading: false,
  companiesError: null,

  // Selected Company
  selectedCompany: null,
  selectedCompanyLoading: false,

  // Executives (for selected company)
  executives: [],
  executivesLoading: false,

  // Selected Executive
  selectedExecutive: null,
  selectedExecutiveLoading: false,

  // Profile Documents (for selected executive)
  profileDocuments: [],
  profileDocumentsLoading: false,

  // Knowledgebase Documents (for selected company)
  knowledgebaseDocuments: [],
  knowledgebaseLoading: false,

  // Voice Keys
  voiceKeysStatus: null,
  voiceKeysLoading: false,

  // Active calibration/onboarding job
  activeJob: null,
  jobPollingInterval: null,

  // ═══════════════════════════════════════════════════════════════════════════
  // COMPANIES
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Fetch all companies
   */
  fetchCompanies: async () => {
    set({ companiesLoading: true, companiesError: null });
    try {
      const data = await api.getCompanies();
      set({ companies: data || [], companiesLoading: false });
      return data;
    } catch (error) {
      set({ companiesLoading: false, companiesError: error.message });
      throw error;
    }
  },

  /**
   * Create a new company (optimistic update)
   */
  createCompany: async (companyData) => {
    const tempId = `temp-${Date.now()}`;
    const optimistic = {
      ...companyData,
      id: companyData.id || tempId,
      executives_count: 0,
      created_at: new Date().toISOString(),
      _optimistic: true,
    };

    // Optimistic add
    set((state) => ({
      companies: [...state.companies, optimistic],
    }));

    try {
      const created = await api.createCompany(companyData);
      // Replace optimistic with real
      set((state) => ({
        companies: state.companies.map((c) =>
          c.id === optimistic.id ? created : c
        ),
      }));
      return created;
    } catch (error) {
      // Rollback
      set((state) => ({
        companies: state.companies.filter((c) => c.id !== optimistic.id),
      }));
      throw error;
    }
  },

  /**
   * Update company
   */
  updateCompany: async (companyId, data) => {
    // Optimistic update
    set((state) => ({
      companies: state.companies.map((c) =>
        c.id === companyId ? { ...c, ...data, _optimistic: true } : c
      ),
      selectedCompany:
        state.selectedCompany?.id === companyId
          ? { ...state.selectedCompany, ...data }
          : state.selectedCompany,
    }));

    try {
      const updated = await api.updateCompany(companyId, data);
      set((state) => ({
        companies: state.companies.map((c) =>
          c.id === companyId ? { ...updated, _optimistic: false } : c
        ),
        selectedCompany:
          state.selectedCompany?.id === companyId ? updated : state.selectedCompany,
      }));
      return updated;
    } catch (error) {
      // Refetch to rollback
      await get().fetchCompanies();
      throw error;
    }
  },

  /**
   * Select and load company details
   */
  selectCompany: async (companyId) => {
    if (!companyId) {
      set({
        selectedCompany: null,
        executives: [],
        knowledgebaseDocuments: [],
      });
      return null;
    }

    set({
      selectedCompanyLoading: true,
      executivesLoading: true,
      knowledgebaseLoading: true,
    });

    try {
      // Fetch company (includes executives) and knowledgebase in parallel
      const [companyData, kbData] = await Promise.all([
        api.getCompany(companyId),
        api.getKnowledgebase(companyId).catch(() => ({ documents: [] })),
      ]);

      set({
        selectedCompany: companyData,
        executives: companyData.executives || [],
        knowledgebaseDocuments: kbData.documents || [],
        selectedCompanyLoading: false,
        executivesLoading: false,
        knowledgebaseLoading: false,
        // Clear executive selection when switching companies
        selectedExecutive: null,
        profileDocuments: [],
      });

      return companyData;
    } catch (error) {
      set({
        selectedCompanyLoading: false,
        executivesLoading: false,
        knowledgebaseLoading: false,
      });
      throw error;
    }
  },

  /**
   * Clear company selection
   */
  clearCompanySelection: () => {
    set({
      selectedCompany: null,
      executives: [],
      knowledgebaseDocuments: [],
      selectedExecutive: null,
      profileDocuments: [],
    });
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // EXECUTIVES
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Create executive (optimistic update)
   */
  createExecutive: async (companyId, execData) => {
    const tempId = `temp-${Date.now()}`;
    const optimistic = {
      ...execData,
      id: execData.id || tempId,
      company_id: companyId,
      has_profile: false,
      has_voiceprint: false,
      direct_reports: [],
      _optimistic: true,
    };

    // Optimistic add
    set((state) => ({
      executives: [...state.executives, optimistic],
    }));

    try {
      const created = await api.createExecutive(companyId, execData);
      // Replace optimistic with real
      set((state) => ({
        executives: state.executives.map((e) =>
          e.id === optimistic.id ? created : e
        ),
      }));
      return created;
    } catch (error) {
      // Rollback
      set((state) => ({
        executives: state.executives.filter((e) => e.id !== optimistic.id),
      }));
      throw error;
    }
  },

  /**
   * Update executive
   */
  updateExecutive: async (companyId, executiveId, data) => {
    // Optimistic update
    set((state) => ({
      executives: state.executives.map((e) =>
        e.id === executiveId ? { ...e, ...data, _optimistic: true } : e
      ),
      selectedExecutive:
        state.selectedExecutive?.id === executiveId
          ? { ...state.selectedExecutive, ...data }
          : state.selectedExecutive,
    }));

    try {
      const updated = await api.updateExecutive(companyId, executiveId, data);
      set((state) => ({
        executives: state.executives.map((e) =>
          e.id === executiveId ? { ...e, ...updated, _optimistic: false } : e
        ),
        selectedExecutive:
          state.selectedExecutive?.id === executiveId
            ? { ...state.selectedExecutive, ...updated }
            : state.selectedExecutive,
      }));
      return updated;
    } catch (error) {
      // Refetch
      if (get().selectedCompany) {
        await get().selectCompany(get().selectedCompany.id);
      }
      throw error;
    }
  },

  /**
   * Delete executive (optimistic)
   */
  deleteExecutive: async (companyId, executiveId) => {
    const previousExecutives = get().executives;

    // Optimistic remove
    set((state) => ({
      executives: state.executives.filter((e) => e.id !== executiveId),
      selectedExecutive:
        state.selectedExecutive?.id === executiveId ? null : state.selectedExecutive,
    }));

    try {
      await api.deleteExecutive(companyId, executiveId);
    } catch (error) {
      // Rollback
      set({ executives: previousExecutives });
      throw error;
    }
  },

  /**
   * Select and load executive details
   */
  selectExecutive: async (companyId, executiveId) => {
    if (!executiveId) {
      set({
        selectedExecutive: null,
        profileDocuments: [],
        voiceKeysStatus: null,
      });
      return null;
    }

    set({
      selectedExecutiveLoading: true,
      profileDocumentsLoading: true,
      voiceKeysLoading: true,
    });

    try {
      // Fetch executive with profile, documents, and voice key status in parallel
      const [execData, docsData, voiceKeys] = await Promise.all([
        api.getExecutive(companyId, executiveId, ['profile', 'voiceprint']),
        api.getDocuments(companyId, executiveId),
        api.getVoiceKeysStatus(companyId, executiveId).catch(() => null),
      ]);

      set({
        selectedExecutive: execData,
        profileDocuments: docsData.documents || [],
        voiceKeysStatus: voiceKeys,
        selectedExecutiveLoading: false,
        profileDocumentsLoading: false,
        voiceKeysLoading: false,
      });

      return execData;
    } catch (error) {
      set({
        selectedExecutiveLoading: false,
        profileDocumentsLoading: false,
        voiceKeysLoading: false,
      });
      throw error;
    }
  },

  /**
   * Clear executive selection
   */
  clearExecutiveSelection: () => {
    set({
      selectedExecutive: null,
      profileDocuments: [],
    });
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // PROFILE DOCUMENTS
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Upload profile documents (optimistic)
   */
  uploadProfileDocuments: async (companyId, executiveId, files, options = {}) => {
    // Create optimistic documents
    const tempDocs = Array.from(files).map((file, i) => ({
      id: `uploading-${Date.now()}-${i}`,
      filename: file.name,
      file_size: file.size,
      content_type: file.type,
      status: 'uploading',
      doc_type: 'profile',
      is_active: true,
      _optimistic: true,
    }));

    // Optimistic add
    set((state) => ({
      profileDocuments: [...state.profileDocuments, ...tempDocs],
    }));

    try {
      const response = await api.uploadDocuments(companyId, executiveId, files, options);
      // Replace optimistic with real
      set((state) => ({
        profileDocuments: [
          ...state.profileDocuments.filter((d) => !d._optimistic),
          ...(response.documents || []),
        ],
      }));
      return response;
    } catch (error) {
      // Rollback
      set((state) => ({
        profileDocuments: state.profileDocuments.filter((d) => !d._optimistic),
      }));
      throw error;
    }
  },

  /**
   * Delete profile document (optimistic)
   */
  deleteProfileDocument: async (companyId, executiveId, docId) => {
    const previousDocs = get().profileDocuments;

    // Optimistic remove
    set((state) => ({
      profileDocuments: state.profileDocuments.filter((d) => d.id !== docId),
    }));

    try {
      await api.deleteDocument(companyId, executiveId, docId);
    } catch (error) {
      // Rollback
      set({ profileDocuments: previousDocs });
      throw error;
    }
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // KNOWLEDGEBASE DOCUMENTS
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Upload knowledgebase documents (optimistic)
   */
  uploadKnowledgebase: async (companyId, files, options = {}) => {
    // Create optimistic documents
    const tempDocs = Array.from(files).map((file, i) => ({
      id: `uploading-${Date.now()}-${i}`,
      filename: file.name,
      file_size: file.size,
      content_type: file.type,
      status: 'uploading',
      doc_type: 'knowledgebase',
      is_active: true,
      _optimistic: true,
    }));

    // Optimistic add
    set((state) => ({
      knowledgebaseDocuments: [...state.knowledgebaseDocuments, ...tempDocs],
    }));

    try {
      const response = await api.uploadKnowledgebase(companyId, files, options);
      // Replace optimistic with real
      set((state) => ({
        knowledgebaseDocuments: [
          ...state.knowledgebaseDocuments.filter((d) => !d._optimistic),
          ...(response.documents || []),
        ],
      }));
      return response;
    } catch (error) {
      // Rollback
      set((state) => ({
        knowledgebaseDocuments: state.knowledgebaseDocuments.filter((d) => !d._optimistic),
      }));
      throw error;
    }
  },

  /**
   * Delete knowledgebase document (optimistic)
   */
  deleteKnowledgebaseDocument: async (companyId, docId) => {
    const previousDocs = get().knowledgebaseDocuments;

    // Optimistic remove
    set((state) => ({
      knowledgebaseDocuments: state.knowledgebaseDocuments.filter((d) => d.id !== docId),
    }));

    try {
      await api.deleteKnowledgebaseDocument(companyId, docId);
    } catch (error) {
      // Rollback
      set({ knowledgebaseDocuments: previousDocs });
      throw error;
    }
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // VOICE KEYS
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Fetch voice key status for selected executive
   */
  fetchVoiceKeysStatus: async (companyId, executiveId) => {
    set({ voiceKeysLoading: true });
    try {
      const data = await api.getVoiceKeysStatus(companyId, executiveId);
      set({ voiceKeysStatus: data, voiceKeysLoading: false });
      return data;
    } catch (error) {
      set({ voiceKeysLoading: false });
      throw error;
    }
  },

  /**
   * Validate voice samples via STT
   */
  validateVoiceSamples: async (companyId, executiveId, referenceAudio, consentAudio, language) => {
    return api.validateVoiceSamples(companyId, executiveId, referenceAudio, consentAudio, language);
  },

  /**
   * Generate voice cloning key
   */
  generateVoiceKey: async (companyId, executiveId, referenceAudio, consentAudio, language) => {
    const result = await api.generateVoiceKey(companyId, executiveId, referenceAudio, consentAudio, language);
    // Refresh voice key status after generation
    try {
      const status = await api.getVoiceKeysStatus(companyId, executiveId);
      set({ voiceKeysStatus: status });
    } catch (_) {
      // non-fatal
    }
    return result;
  },

  /**
   * Delete a voice key
   */
  deleteVoiceKey: async (companyId, executiveId, language) => {
    await api.deleteVoiceKey(companyId, executiveId, language);
    // Refresh voice key status
    try {
      const status = await api.getVoiceKeysStatus(companyId, executiveId);
      set({ voiceKeysStatus: status });
    } catch (_) {
      // non-fatal
    }
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // CALIBRATION & JOBS
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Start calibration and begin polling
   */
  startCalibration: async (companyId, executiveId, options = {}) => {
    // Stop any existing polling
    get().stopJobPolling();

    try {
      const job = await api.startCalibration(companyId, executiveId, options);
      set({ activeJob: job });

      // Start polling for job status
      const pollInterval = setInterval(async () => {
        try {
          const status = await api.getJobStatus(companyId, executiveId, job.job_id);
          set({ activeJob: status });

          // Stop polling when job completes
          if (status.status === 'completed' || status.status === 'failed') {
            get().stopJobPolling();

            // Refresh executive data if completed
            if (status.status === 'completed') {
              await get().selectExecutive(companyId, executiveId);
            }
          }
        } catch (error) {
          console.error('Job polling error:', error);
        }
      }, 2000); // Poll every 2 seconds

      set({ jobPollingInterval: pollInterval });
      return job;
    } catch (error) {
      set({ activeJob: null });
      throw error;
    }
  },

  /**
   * Start onboarding pipeline
   */
  startOnboarding: async (companyId, executiveId, jobType = 'full_onboarding') => {
    // Stop any existing polling
    get().stopJobPolling();

    try {
      const job = await api.startOnboarding(companyId, executiveId, jobType);
      set({ activeJob: job });

      // Start polling for job status
      const pollInterval = setInterval(async () => {
        try {
          const status = await api.getJobStatus(companyId, executiveId, job.id);
          set({ activeJob: status });

          // Stop polling when job completes
          if (status.status === 'completed' || status.status === 'failed') {
            get().stopJobPolling();

            // Refresh executive data if completed
            if (status.status === 'completed') {
              await get().selectExecutive(companyId, executiveId);
            }
          }
        } catch (error) {
          console.error('Job polling error:', error);
        }
      }, 2000);

      set({ jobPollingInterval: pollInterval });
      return job;
    } catch (error) {
      set({ activeJob: null });
      throw error;
    }
  },

  /**
   * Stop job polling
   */
  stopJobPolling: () => {
    const interval = get().jobPollingInterval;
    if (interval) {
      clearInterval(interval);
      set({ jobPollingInterval: null });
    }
  },

  /**
   * Clear active job
   */
  clearActiveJob: () => {
    get().stopJobPolling();
    set({ activeJob: null });
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // RESET
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Reset all state
   */
  reset: () => {
    get().stopJobPolling();
    set({
      companies: [],
      companiesLoading: false,
      companiesError: null,
      selectedCompany: null,
      selectedCompanyLoading: false,
      executives: [],
      executivesLoading: false,
      selectedExecutive: null,
      selectedExecutiveLoading: false,
      profileDocuments: [],
      profileDocumentsLoading: false,
      knowledgebaseDocuments: [],
      knowledgebaseLoading: false,
      voiceKeysStatus: null,
      voiceKeysLoading: false,
      activeJob: null,
      jobPollingInterval: null,
    });
  },
}));

export default useOnboardingStore;
