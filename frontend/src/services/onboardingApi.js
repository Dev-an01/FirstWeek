/**
 * Onboarding Service API Client
 *
 * Handles all API calls to the onboarding service (port 8002)
 * for managing companies, executives, documents, and calibration.
 */

import axios from 'axios';

const BASE_URL = '/api/onboarding';

const client = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor - extract data
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message =
      error.response?.data?.detail?.[0]?.msg ||
      error.response?.data?.message ||
      error.message ||
      'Request failed';
    return Promise.reject(new Error(message));
  }
);

// ============================================================================
// COMPANIES
// ============================================================================

/**
 * List all companies
 * @returns {Promise<Array>} List of companies
 */
export const getCompanies = () => client.get('/companies');

/**
 * Get company with executives
 * @param {string} companyId - Company ID
 * @returns {Promise<Object>} Company with executives array
 */
export const getCompany = (companyId) => client.get(`/companies/${companyId}`);

/**
 * Create a new company
 * @param {Object} data - { id, name, industry?, description?, metadata? }
 * @returns {Promise<Object>} Created company
 */
export const createCompany = (data) => client.post('/companies', data);

/**
 * Update company
 * @param {string} companyId - Company ID
 * @param {Object} data - { name?, industry?, description?, metadata? }
 * @returns {Promise<Object>} Updated company
 */
export const updateCompany = (companyId, data) =>
  client.patch(`/companies/${companyId}`, data);

// ============================================================================
// EXECUTIVES
// ============================================================================

/**
 * List executives for a company
 * @param {string} companyId - Company ID
 * @param {Object} options - { hierarchy?: boolean, sort?: string }
 * @returns {Promise<Object>} { company_id, total, executives, by_level? }
 */
export const getExecutives = (companyId, options = {}) => {
  const params = new URLSearchParams();
  if (options.hierarchy) params.append('hierarchy', 'true');
  if (options.sort) params.append('sort', options.sort);
  if (options.email) params.append('email', options.email);
  const query = params.toString();
  return client.get(`/companies/${companyId}/executives${query ? `?${query}` : ''}`);
};

/**
 * Get executive detail with optional includes
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {Array<string>} include - ['profile', 'voiceprint', 'documents']
 * @returns {Promise<Object>} Executive detail
 */
export const getExecutive = (companyId, executiveId, include = []) => {
  const query = include.length > 0 ? `?include=${include.join(',')}` : '';
  return client.get(`/companies/${companyId}/executives/${executiveId}${query}`);
};

/**
 * Create executive
 * @param {string} companyId - Company ID
 * @param {Object} data - { id, name, company_id, title?, reports_to?, hierarchy_level? }
 * @returns {Promise<Object>} Created executive
 */
export const createExecutive = (companyId, data) =>
  client.post(`/companies/${companyId}/executives`, {
    ...data,
    company_id: companyId,
  });

/**
 * Update executive
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {Object} data - { name?, title?, reports_to?, hierarchy_level? }
 * @returns {Promise<Object>} Updated executive
 */
export const updateExecutive = (companyId, executiveId, data) =>
  client.patch(`/companies/${companyId}/executives/${executiveId}`, data);

/**
 * Delete executive (soft delete)
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @returns {Promise<void>}
 */
export const deleteExecutive = (companyId, executiveId) =>
  client.delete(`/companies/${companyId}/executives/${executiveId}`);

// ============================================================================
// PROFILE DOCUMENTS (Executive-specific)
// ============================================================================

/**
 * List documents for an executive
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {boolean} includeInactive - Include soft-deleted docs
 * @returns {Promise<Object>} { company_id, executive_id, total, documents }
 */
export const getDocuments = (companyId, executiveId, includeInactive = false) => {
  const query = includeInactive ? '?include_inactive=true' : '';
  return client.get(
    `/companies/${companyId}/executives/${executiveId}/documents${query}`
  );
};

/**
 * Upload profile documents for an executive
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {File[]} files - Array of files to upload
 * @param {Object} options - { autoCalibrate?: boolean, calibrateMode?: string }
 * @returns {Promise<Object>} Upload response with document metadata
 */
export const uploadDocuments = async (companyId, executiveId, files, options = {}) => {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));

  const params = new URLSearchParams();
  if (options.autoCalibrate) params.append('auto_calibrate', 'true');
  if (options.calibrateMode) params.append('calibrate_mode', options.calibrateMode);
  if (options.accessLevel) params.append('access_level', options.accessLevel);
  const query = params.toString();

  return client.post(
    `/companies/${companyId}/executives/${executiveId}/documents${query ? `?${query}` : ''}`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    }
  );
};

/**
 * Get document with extracted text
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {string} docId - Document UUID
 * @returns {Promise<Object>} Document with extracted_text
 */
export const getDocument = (companyId, executiveId, docId) =>
  client.get(`/companies/${companyId}/executives/${executiveId}/documents/${docId}`);

/**
 * Delete document (soft delete)
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {string} docId - Document UUID
 * @returns {Promise<void>}
 */
export const deleteDocument = (companyId, executiveId, docId) =>
  client.delete(`/companies/${companyId}/executives/${executiveId}/documents/${docId}`);

/**
 * Restore soft-deleted document
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {string} docId - Document UUID
 * @returns {Promise<void>}
 */
export const restoreDocument = (companyId, executiveId, docId) =>
  client.post(
    `/companies/${companyId}/executives/${executiveId}/documents/${docId}/restore`
  );

// ============================================================================
// KNOWLEDGEBASE DOCUMENTS (Company-wide)
// ============================================================================

/**
 * List knowledgebase documents for a company
 * @param {string} companyId - Company ID
 * @param {boolean} includeInactive - Include soft-deleted docs
 * @returns {Promise<Object>} { company_id, total, documents }
 */
export const getKnowledgebase = (companyId, includeInactive = false) => {
  const query = includeInactive ? '?include_inactive=true' : '';
  return client.get(`/companies/${companyId}/knowledgebase${query}`);
};

/**
 * Upload knowledgebase documents for a company
 * @param {string} companyId - Company ID
 * @param {File[]} files - Array of files to upload
 * @returns {Promise<Object>} Upload response with document metadata
 */
export const uploadKnowledgebase = async (companyId, files, options = {}) => {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));

  const params = new URLSearchParams();
  if (options.accessLevel) params.append('access_level', options.accessLevel);
  const query = params.toString();

  return client.post(
    `/companies/${companyId}/knowledgebase${query ? `?${query}` : ''}`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
};

/**
 * Get knowledgebase document with extracted text
 * @param {string} companyId - Company ID
 * @param {string} docId - Document UUID
 * @returns {Promise<Object>} Document with extracted_text
 */
export const getKnowledgebaseDocument = (companyId, docId) =>
  client.get(`/companies/${companyId}/knowledgebase/${docId}`);

/**
 * Delete knowledgebase document (soft delete)
 * @param {string} companyId - Company ID
 * @param {string} docId - Document UUID
 * @returns {Promise<void>}
 */
export const deleteKnowledgebaseDocument = (companyId, docId) =>
  client.delete(`/companies/${companyId}/knowledgebase/${docId}`);

// ============================================================================
// PROFILE & VOICEPRINT
// ============================================================================

/**
 * Get executive profile with voiceprint and validation
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @returns {Promise<Object>} { profile, voiceprint, validation }
 */
export const getProfile = (companyId, executiveId) =>
  client.get(`/companies/${companyId}/executives/${executiveId}/profile`);

/**
 * Edit profile sections
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {Object} sections - Section updates (supports dot notation)
 * @param {boolean} regenerateEmbeddings - Whether to regenerate embeddings
 * @returns {Promise<Object>} { success, updated_sections, regenerate_job_id? }
 */
export const editProfile = (companyId, executiveId, sections, regenerateEmbeddings = false) =>
  client.patch(`/companies/${companyId}/executives/${executiveId}/profile`, {
    sections,
    regenerate_embeddings: regenerateEmbeddings,
  });

/**
 * Get voiceprint
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @returns {Promise<Object>} Voiceprint data
 */
export const getVoiceprint = (companyId, executiveId) =>
  client.get(`/companies/${companyId}/executives/${executiveId}/voiceprint`);

/**
 * Edit voiceprint sections
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {Object} sections - Section updates (supports dot notation)
 * @param {boolean} regenerateEmbeddings - Whether to regenerate embeddings
 * @returns {Promise<Object>} { success, updated_sections, regenerate_job_id? }
 */
export const editVoiceprint = (companyId, executiveId, sections, regenerateEmbeddings = false) =>
  client.patch(`/companies/${companyId}/executives/${executiveId}/voiceprint`, {
    sections,
    regenerate_embeddings: regenerateEmbeddings,
  });

// ============================================================================
// CALIBRATION & JOBS
// ============================================================================

/**
 * Start calibration for an executive
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {Object} options - { mode?: 'full'|'incremental', extractors?: string[], merge_strategy?: 'replace'|'merge', regenerate_embeddings?: boolean }
 * @returns {Promise<Object>} { job_id, status, mode, extractors? }
 */
export const startCalibration = (companyId, executiveId, options = {}) =>
  client.post(`/companies/${companyId}/executives/${executiveId}/calibrate`, {
    mode: options.mode || 'full',
    extractors: options.extractors,
    merge_strategy: options.mergeStrategy || 'replace',
    regenerate_embeddings: options.regenerateEmbeddings !== false,
  });

/**
 * Start full onboarding pipeline
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {string} jobType - 'full_onboarding' | 'profile_only' | 'voiceprint_only'
 * @returns {Promise<Object>} Job status response
 */
export const startOnboarding = (companyId, executiveId, jobType = 'full_onboarding') =>
  client.post(`/companies/${companyId}/executives/${executiveId}/onboard`, {
    job_type: jobType,
  });

/**
 * Get job status
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {string} jobId - Job UUID
 * @returns {Promise<Object>} { id, status, progress, error_message?, ... }
 */
export const getJobStatus = (companyId, executiveId, jobId) =>
  client.get(`/companies/${companyId}/executives/${executiveId}/jobs/${jobId}`);

/**
 * Get job result
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {string} jobId - Job UUID
 * @returns {Promise<Object>} { id, status, profile?, voiceprint?, validation_report? }
 */
export const getJobResult = (companyId, executiveId, jobId) =>
  client.get(`/companies/${companyId}/executives/${executiveId}/jobs/${jobId}/result`);

// ============================================================================
// VOICE CLONING
// ============================================================================

/**
 * Validate voice samples via STT
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {File} referenceAudio - Reference voice sample
 * @param {File} consentAudio - Consent recording
 * @param {string} language - 'en' or 'ja'
 * @returns {Promise<Object>} Validation result with transcripts and pass/fail
 */
export const validateVoiceSamples = (companyId, executiveId, referenceAudio, consentAudio, language) => {
  const formData = new FormData();
  formData.append('reference_audio', referenceAudio);
  formData.append('consent_audio', consentAudio);
  formData.append('language', language);
  return client.post(
    `/companies/${companyId}/executives/${executiveId}/voice/validate`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
};

/**
 * Generate voice cloning key
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {File} referenceAudio - Reference voice sample
 * @param {File} consentAudio - Consent recording
 * @param {string} language - 'en' or 'ja'
 * @returns {Promise<Object>} { success, language, key_length }
 */
export const generateVoiceKey = (companyId, executiveId, referenceAudio, consentAudio, language) => {
  const formData = new FormData();
  formData.append('reference_audio', referenceAudio);
  formData.append('consent_audio', consentAudio);
  formData.append('language', language);
  return client.post(
    `/companies/${companyId}/executives/${executiveId}/voice/generate-key`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
};

/**
 * Get voice key status for an executive
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @returns {Promise<Object>} { executive_id, keys: { "en-US": {...}, "ja-JP": {...} } }
 */
export const getVoiceKeysStatus = (companyId, executiveId) =>
  client.get(`/companies/${companyId}/executives/${executiveId}/voice/keys`);

/**
 * Delete a voice key for a specific language
 * @param {string} companyId - Company ID
 * @param {string} executiveId - Executive ID
 * @param {string} language - 'en' or 'ja'
 * @returns {Promise<Object>} { success, deleted }
 */
export const deleteVoiceKey = (companyId, executiveId, language) =>
  client.delete(`/companies/${companyId}/executives/${executiveId}/voice/keys/${language}`);

// ============================================================================
// HEALTH
// ============================================================================

/**
 * Health check
 * @returns {Promise<Object>} { status, service, version, database }
 */
export const healthCheck = () => client.get('/health');

export default {
  // Companies
  getCompanies,
  getCompany,
  createCompany,
  updateCompany,
  // Executives
  getExecutives,
  getExecutive,
  createExecutive,
  updateExecutive,
  deleteExecutive,
  // Documents
  getDocuments,
  uploadDocuments,
  getDocument,
  deleteDocument,
  restoreDocument,
  // Knowledgebase
  getKnowledgebase,
  uploadKnowledgebase,
  getKnowledgebaseDocument,
  deleteKnowledgebaseDocument,
  // Profile
  getProfile,
  editProfile,
  getVoiceprint,
  editVoiceprint,
  // Calibration
  startCalibration,
  startOnboarding,
  getJobStatus,
  getJobResult,
  // Voice Cloning
  validateVoiceSamples,
  generateVoiceKey,
  getVoiceKeysStatus,
  deleteVoiceKey,
  // Health
  healthCheck,
};
