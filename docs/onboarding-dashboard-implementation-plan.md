# Onboarding Dashboard - Optimized Implementation Plan

**Goal:** Build a fast, snappy admin dashboard by maximizing component reuse and minimizing re-renders.

---

## 1. Performance Strategy

### 1.1 Core Principles

| Principle | How |
|-----------|-----|
| **Reuse existing components** | Button, Modal, Toast, FormInput, DashboardCard, Sidebar, Navbar |
| **Lazy load new pages** | Add to App.jsx with React.lazy() |
| **Zustand with selectors** | Never destructure entire store |
| **Memoize list items** | React.memo for CompanyCard, ExecutiveRow, DocumentRow |
| **Memoize handlers** | useCallback for all onClick handlers |
| **Memoize computed values** | useMemo for filtered/sorted lists |
| **Debounce search** | useDebounce hook for search inputs |
| **Optimistic updates** | Show changes immediately, sync in background |

### 1.2 What NOT to Do

```javascript
// BAD - causes re-render on ANY store change
const { companies, loading, error, fetchCompanies } = useOnboardingStore();

// GOOD - only re-renders when companies change
const companies = useOnboardingStore((state) => state.companies);
const fetchCompanies = useOnboardingStore((state) => state.fetchCompanies);
```

---

## 2. File Structure (Minimal New Files)

```
src/
├── pages/
│   └── admin/
│       └── OnboardingPage.jsx        # Single page with tabs/views
│
├── components/
│   └── onboarding/
│       ├── CompanyList.jsx           # Grid of company cards
│       ├── CompanyCard.jsx           # Memoized card component
│       ├── CompanyDetail.jsx         # Company detail view
│       ├── ExecutiveList.jsx         # Hierarchical executive list
│       ├── ExecutiveRow.jsx          # Memoized row component
│       ├── ExecutiveDetail.jsx       # Executive detail view
│       ├── DocumentList.jsx          # Reusable document list
│       ├── DocumentRow.jsx           # Memoized document row
│       ├── FileUploader.jsx          # Multi-file drag-drop
│       ├── StatusBadge.jsx           # Status indicator
│       └── CalibrationProgress.jsx   # Progress display
│
├── store/
│   └── onboardingStore.js            # Single Zustand store
│
└── services/
    └── onboardingApi.js              # API client for onboarding service
```

**Total: 13 new files** (1 page, 11 components, 1 store, 1 API service)

---

## 3. Component Reuse Map

### Existing → New Usage

| Existing Component | Reuse In |
|--------------------|----------|
| `Button` | All forms, actions |
| `Modal` | Create company, Create executive, Confirm delete |
| `Toast` | Success/error notifications |
| `FormInput` | Company name, executive name, etc. |
| `DashboardCard` | Stats cards on main view |
| `Navbar` | Page header |
| `Sidebar` | Navigation (add "Onboarding" link) |
| `PageLoader` | Lazy load fallback |
| `ProtectedRoute` | Admin route protection |

### New Components (Keep Minimal)

| Component | Purpose | Memoized |
|-----------|---------|----------|
| `CompanyCard` | Company summary in grid | Yes |
| `ExecutiveRow` | Executive in list | Yes |
| `DocumentRow` | Document in list | Yes |
| `StatusBadge` | Status indicator | Yes |
| `FileUploader` | Drag-drop upload | No (complex state) |
| `CalibrationProgress` | Job progress | No (polling) |

---

## 4. Zustand Store Design

### Single Store with Selectors

```javascript
// src/store/onboardingStore.js
import { create } from 'zustand';
import * as api from '../services/onboardingApi';

export const useOnboardingStore = create((set, get) => ({
  // ─────────────────────────────────────────────
  // STATE (organized by entity)
  // ─────────────────────────────────────────────

  // Companies
  companies: [],
  companiesLoading: false,
  selectedCompany: null,

  // Executives (for selected company)
  executives: [],
  executivesLoading: false,
  selectedExecutive: null,

  // Documents (for selected executive or company KB)
  documents: [],
  documentsLoading: false,

  // Calibration jobs
  activeJob: null,
  jobPollingInterval: null,

  // ─────────────────────────────────────────────
  // ACTIONS
  // ─────────────────────────────────────────────

  // Companies
  fetchCompanies: async () => {
    set({ companiesLoading: true });
    try {
      const data = await api.getCompanies();
      set({ companies: data, companiesLoading: false });
    } catch (error) {
      set({ companiesLoading: false });
      throw error;
    }
  },

  createCompany: async (companyData) => {
    // Optimistic update
    const tempId = `temp-${Date.now()}`;
    const optimistic = { ...companyData, id: tempId, _optimistic: true };
    set((state) => ({ companies: [...state.companies, optimistic] }));

    try {
      const created = await api.createCompany(companyData);
      // Replace optimistic with real
      set((state) => ({
        companies: state.companies.map((c) =>
          c.id === tempId ? created : c
        ),
      }));
      return created;
    } catch (error) {
      // Rollback
      set((state) => ({
        companies: state.companies.filter((c) => c.id !== tempId),
      }));
      throw error;
    }
  },

  selectCompany: async (companyId) => {
    set({ selectedCompany: null, executives: [], executivesLoading: true });
    try {
      const company = await api.getCompany(companyId);
      const executives = await api.getExecutives(companyId);
      set({
        selectedCompany: company,
        executives,
        executivesLoading: false,
      });
    } catch (error) {
      set({ executivesLoading: false });
      throw error;
    }
  },

  // Executives
  createExecutive: async (companyId, execData) => {
    const tempId = `temp-${Date.now()}`;
    const optimistic = { ...execData, id: tempId, _optimistic: true };
    set((state) => ({ executives: [...state.executives, optimistic] }));

    try {
      const created = await api.createExecutive(companyId, execData);
      set((state) => ({
        executives: state.executives.map((e) =>
          e.id === tempId ? created : e
        ),
      }));
      return created;
    } catch (error) {
      set((state) => ({
        executives: state.executives.filter((e) => e.id !== tempId),
      }));
      throw error;
    }
  },

  selectExecutive: async (companyId, execId) => {
    set({ selectedExecutive: null, documents: [], documentsLoading: true });
    try {
      const exec = await api.getExecutive(companyId, execId);
      const docs = await api.getDocuments(companyId, execId);
      set({
        selectedExecutive: exec,
        documents: docs,
        documentsLoading: false,
      });
    } catch (error) {
      set({ documentsLoading: false });
      throw error;
    }
  },

  // Documents
  uploadDocuments: async (companyId, execId, files, docType) => {
    // Show uploading state immediately
    const tempDocs = files.map((f, i) => ({
      id: `uploading-${Date.now()}-${i}`,
      filename: f.name,
      status: 'uploading',
      _optimistic: true,
    }));
    set((state) => ({ documents: [...state.documents, ...tempDocs] }));

    try {
      const uploaded = await api.uploadDocuments(companyId, execId, files, docType);
      // Replace optimistic with real
      set((state) => ({
        documents: [
          ...state.documents.filter((d) => !d._optimistic),
          ...uploaded,
        ],
      }));
      return uploaded;
    } catch (error) {
      // Remove optimistic
      set((state) => ({
        documents: state.documents.filter((d) => !d._optimistic),
      }));
      throw error;
    }
  },

  deleteDocument: async (companyId, execId, docId) => {
    // Optimistic remove
    set((state) => ({
      documents: state.documents.filter((d) => d.id !== docId),
    }));

    try {
      await api.deleteDocument(companyId, execId, docId);
    } catch (error) {
      // Rollback - refetch
      const docs = await api.getDocuments(companyId, execId);
      set({ documents: docs });
      throw error;
    }
  },

  // Calibration
  startCalibration: async (companyId, execId, options) => {
    const job = await api.startCalibration(companyId, execId, options);
    set({ activeJob: job });

    // Start polling
    const interval = setInterval(async () => {
      try {
        const status = await api.getJobStatus(companyId, execId, job.id);
        set({ activeJob: status });

        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(interval);
          set({ jobPollingInterval: null });
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 2000); // Poll every 2 seconds

    set({ jobPollingInterval: interval });
    return job;
  },

  stopPolling: () => {
    const interval = get().jobPollingInterval;
    if (interval) {
      clearInterval(interval);
      set({ jobPollingInterval: null });
    }
  },

  // Reset
  reset: () => {
    get().stopPolling();
    set({
      companies: [],
      selectedCompany: null,
      executives: [],
      selectedExecutive: null,
      documents: [],
      activeJob: null,
    });
  },
}));
```

---

## 5. API Service

```javascript
// src/services/onboardingApi.js
import axios from 'axios';

const BASE_URL = '/api/onboarding'; // Proxy to localhost:8002

const client = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
});

// Companies
export const getCompanies = () =>
  client.get('/companies').then((r) => r.data);

export const getCompany = (id) =>
  client.get(`/companies/${id}`).then((r) => r.data);

export const createCompany = (data) =>
  client.post('/companies', data).then((r) => r.data);

export const updateCompany = (id, data) =>
  client.patch(`/companies/${id}`, data).then((r) => r.data);

// Executives
export const getExecutives = (companyId) =>
  client.get(`/companies/${companyId}/executives`).then((r) => r.data);

export const getExecutive = (companyId, execId) =>
  client.get(`/companies/${companyId}/executives/${execId}`).then((r) => r.data);

export const createExecutive = (companyId, data) =>
  client.post(`/companies/${companyId}/executives`, data).then((r) => r.data);

export const updateExecutive = (companyId, execId, data) =>
  client.patch(`/companies/${companyId}/executives/${execId}`, data).then((r) => r.data);

// Documents
export const getDocuments = (companyId, execId) =>
  client.get(`/companies/${companyId}/executives/${execId}/documents`).then((r) => r.data);

export const getKnowledgebase = (companyId) =>
  client.get(`/companies/${companyId}/knowledgebase`).then((r) => r.data);

export const uploadDocuments = async (companyId, execId, files, docType = 'profile') => {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));

  const endpoint = docType === 'knowledgebase'
    ? `/companies/${companyId}/knowledgebase`
    : `/companies/${companyId}/executives/${execId}/documents`;

  return client.post(endpoint, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data);
};

export const deleteDocument = (companyId, execId, docId, docType = 'profile') => {
  const endpoint = docType === 'knowledgebase'
    ? `/companies/${companyId}/knowledgebase/${docId}`
    : `/companies/${companyId}/executives/${execId}/documents/${docId}`;

  return client.delete(endpoint);
};

// Calibration
export const startCalibration = (companyId, execId, options = {}) =>
  client.post(`/companies/${companyId}/executives/${execId}/calibrate`, options).then((r) => r.data);

export const getJobStatus = (companyId, execId, jobId) =>
  client.get(`/companies/${companyId}/executives/${execId}/jobs/${jobId}`).then((r) => r.data);
```

---

## 6. Component Implementation

### 6.1 StatusBadge (Memoized)

```jsx
// src/components/onboarding/StatusBadge.jsx
import { memo } from 'react';

const statusConfig = {
  pending: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'Pending' },
  uploading: { bg: 'bg-blue-100', text: 'text-blue-600', label: 'Uploading' },
  processing: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Processing' },
  calibrating: { bg: 'bg-blue-100', text: 'text-blue-600', label: 'Calibrating' },
  calibrated: { bg: 'bg-green-100', text: 'text-green-600', label: 'Ready' },
  completed: { bg: 'bg-green-100', text: 'text-green-600', label: 'Completed' },
  failed: { bg: 'bg-red-100', text: 'text-red-600', label: 'Failed' },
};

function StatusBadgeComponent({ status }) {
  const config = statusConfig[status] || statusConfig.pending;

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  );
}

export const StatusBadge = memo(StatusBadgeComponent);
```

### 6.2 CompanyCard (Memoized)

```jsx
// src/components/onboarding/CompanyCard.jsx
import { memo } from 'react';
import { Building2, Users, FileText } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

function CompanyCardComponent({ company, onClick }) {
  return (
    <div
      onClick={() => onClick(company.id)}
      className="bg-white rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow cursor-pointer border border-gray-100"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="p-2 bg-primary-light rounded-lg">
          <Building2 className="w-5 h-5 text-primary" />
        </div>
        <StatusBadge status={company.status || 'pending'} />
      </div>

      <h3 className="font-semibold text-gray-900 mb-1">{company.name}</h3>
      <p className="text-sm text-gray-500 mb-3">{company.industry || 'No industry'}</p>

      <div className="flex items-center gap-4 text-sm text-gray-600">
        <span className="flex items-center gap-1">
          <Users className="w-4 h-4" />
          {company.executive_count || 0}
        </span>
        <span className="flex items-center gap-1">
          <FileText className="w-4 h-4" />
          {company.kb_doc_count || 0}
        </span>
      </div>
    </div>
  );
}

export const CompanyCard = memo(CompanyCardComponent);
```

### 6.3 DocumentRow (Memoized)

```jsx
// src/components/onboarding/DocumentRow.jsx
import { memo, useCallback } from 'react';
import { FileText, Trash2, Loader2 } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

function DocumentRowComponent({ document, onDelete }) {
  const handleDelete = useCallback((e) => {
    e.stopPropagation();
    onDelete(document.id);
  }, [document.id, onDelete]);

  const isUploading = document.status === 'uploading';

  return (
    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
      <div className="flex items-center gap-3">
        {isUploading ? (
          <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
        ) : (
          <FileText className="w-5 h-5 text-gray-400" />
        )}
        <div>
          <p className="text-sm font-medium text-gray-900">{document.filename}</p>
          <p className="text-xs text-gray-500">
            {document.file_size ? `${Math.round(document.file_size / 1024)} KB` : ''}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <StatusBadge status={document.status || 'pending'} />
        {!isUploading && (
          <button
            onClick={handleDelete}
            className="p-1 text-gray-400 hover:text-red-500 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}

export const DocumentRow = memo(DocumentRowComponent);
```

### 6.4 FileUploader

```jsx
// src/components/onboarding/FileUploader.jsx
import { useState, useCallback, useRef } from 'react';
import { Upload, X } from 'lucide-react';
import { Button } from '../ui/Button';

const ACCEPTED_TYPES = '.pdf,.docx,.txt,.json,.png,.jpg,.jpeg';
const MAX_SIZE_MB = 50;

export function FileUploader({ onUpload, disabled }) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const inputRef = useRef(null);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const validateFiles = useCallback((files) => {
    return Array.from(files).filter((file) => {
      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        console.warn(`File ${file.name} exceeds ${MAX_SIZE_MB}MB limit`);
        return false;
      }
      return true;
    });
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const valid = validateFiles(e.dataTransfer.files);
    setSelectedFiles((prev) => [...prev, ...valid]);
  }, [validateFiles]);

  const handleFileSelect = useCallback((e) => {
    const valid = validateFiles(e.target.files);
    setSelectedFiles((prev) => [...prev, ...valid]);
  }, [validateFiles]);

  const removeFile = useCallback((index) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0) return;
    await onUpload(selectedFiles);
    setSelectedFiles([]);
  }, [selectedFiles, onUpload]);

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`
          border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors
          ${isDragging ? 'border-primary bg-primary-light/50' : 'border-gray-300 hover:border-primary'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
        <p className="text-sm text-gray-600">
          Drag & drop files or <span className="text-primary font-medium">browse</span>
        </p>
        <p className="text-xs text-gray-400 mt-1">
          PDF, DOCX, TXT, JSON, PNG, JPG (max {MAX_SIZE_MB}MB)
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES}
          onChange={handleFileSelect}
          className="hidden"
          disabled={disabled}
        />
      </div>

      {/* Selected files */}
      {selectedFiles.length > 0 && (
        <div className="space-y-2">
          {selectedFiles.map((file, index) => (
            <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
              <span className="text-sm text-gray-700 truncate">{file.name}</span>
              <button onClick={() => removeFile(index)} className="p-1 hover:text-red-500">
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
          <Button onClick={handleUpload} disabled={disabled}>
            Upload {selectedFiles.length} file{selectedFiles.length > 1 ? 's' : ''}
          </Button>
        </div>
      )}
    </div>
  );
}
```

---

## 7. Main Page Component

```jsx
// src/pages/admin/OnboardingPage.jsx
import { memo, useEffect, useCallback, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Navbar } from '../../components/Navbar/Navbar';
import { Sidebar } from '../../components/Sidebar/Sidebar';
import { useOnboardingStore } from '../../store/onboardingStore';
import { useUIStore } from '../../store/uiStore';

// Sub-views (could be separate files)
import { CompanyListView } from './views/CompanyListView';
import { CompanyDetailView } from './views/CompanyDetailView';
import { ExecutiveDetailView } from './views/ExecutiveDetailView';

function OnboardingPageComponent() {
  const { companyId, executiveId } = useParams();
  const navigate = useNavigate();

  // Selective store subscriptions (IMPORTANT for performance)
  const fetchCompanies = useOnboardingStore((s) => s.fetchCompanies);
  const selectCompany = useOnboardingStore((s) => s.selectCompany);
  const selectExecutive = useOnboardingStore((s) => s.selectExecutive);
  const reset = useOnboardingStore((s) => s.reset);

  const { showErrorToast } = useUIStore();

  // Load companies on mount
  useEffect(() => {
    fetchCompanies().catch((err) => showErrorToast(err.message));
    return () => reset(); // Cleanup on unmount
  }, []);

  // Load company when ID changes
  useEffect(() => {
    if (companyId) {
      selectCompany(companyId).catch((err) => showErrorToast(err.message));
    }
  }, [companyId]);

  // Load executive when ID changes
  useEffect(() => {
    if (companyId && executiveId) {
      selectExecutive(companyId, executiveId).catch((err) => showErrorToast(err.message));
    }
  }, [companyId, executiveId]);

  // Determine which view to show
  const renderContent = () => {
    if (executiveId) {
      return <ExecutiveDetailView />;
    }
    if (companyId) {
      return <CompanyDetailView />;
    }
    return <CompanyListView />;
  };

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 overflow-auto p-6">
          {renderContent()}
        </main>
      </div>
    </div>
  );
}

export const OnboardingPage = memo(OnboardingPageComponent);
```

---

## 8. Route Configuration

```jsx
// Add to App.jsx

// Lazy load the onboarding page
const OnboardingPage = lazy(() =>
  import('./pages/admin/OnboardingPage').then((m) => ({ default: m.OnboardingPage }))
);

// Add routes inside <Routes>
<Route
  path="/admin/onboarding"
  element={
    <ProtectedRoute>
      <Suspense fallback={<PageLoader />}>
        <OnboardingPage />
      </Suspense>
    </ProtectedRoute>
  }
/>
<Route
  path="/admin/onboarding/companies/:companyId"
  element={
    <ProtectedRoute>
      <Suspense fallback={<PageLoader />}>
        <OnboardingPage />
      </Suspense>
    </ProtectedRoute>
  }
/>
<Route
  path="/admin/onboarding/companies/:companyId/executives/:executiveId"
  element={
    <ProtectedRoute>
      <Suspense fallback={<PageLoader />}>
        <OnboardingPage />
      </Suspense>
    </ProtectedRoute>
  }
/>
```

---

## 9. Vite Proxy Configuration

```javascript
// Add to vite.config.js proxy section
'/api/onboarding': {
  target: process.env.ONBOARDING_SERVICE_URL || 'http://localhost:8002',
  changeOrigin: true,
  rewrite: (path) => path.replace(/^\/api\/onboarding/, '/api/v1'),
},
```

---

## 10. Implementation Order

### Phase 1: Foundation (Day 1)
1. [ ] Create `onboardingApi.js` - API service
2. [ ] Create `onboardingStore.js` - Zustand store
3. [ ] Add Vite proxy config
4. [ ] Add route to App.jsx

### Phase 2: Company Management (Day 2)
5. [ ] Create `StatusBadge.jsx` (memoized)
6. [ ] Create `CompanyCard.jsx` (memoized)
7. [ ] Create `CompanyListView.jsx`
8. [ ] Create company modal (reuse Modal + FormInput)

### Phase 3: Executive Management (Day 3)
9. [ ] Create `ExecutiveRow.jsx` (memoized)
10. [ ] Create `ExecutiveList.jsx`
11. [ ] Create `CompanyDetailView.jsx`
12. [ ] Create executive modal

### Phase 4: Document Management (Day 4)
13. [ ] Create `DocumentRow.jsx` (memoized)
14. [ ] Create `DocumentList.jsx`
15. [ ] Create `FileUploader.jsx`
16. [ ] Create `ExecutiveDetailView.jsx`

### Phase 5: Calibration (Day 5)
17. [ ] Create `CalibrationProgress.jsx`
18. [ ] Add calibration modal
19. [ ] Implement job polling
20. [ ] Add sidebar link

### Phase 6: Polish (Day 6)
21. [ ] Add loading skeletons
22. [ ] Add empty states
23. [ ] Test all flows
24. [ ] Performance audit

---

## 11. Performance Checklist

- [ ] All list items memoized with React.memo
- [ ] All handlers wrapped in useCallback
- [ ] Computed values in useMemo
- [ ] Zustand selectors (not destructuring)
- [ ] Lazy loaded page
- [ ] Debounced search inputs
- [ ] Optimistic updates for CRUD
- [ ] No unnecessary re-renders (React DevTools Profiler)

---

## 12. Quick Reference: Selector Patterns

```javascript
// COMPANY LIST VIEW
const companies = useOnboardingStore((s) => s.companies);
const companiesLoading = useOnboardingStore((s) => s.companiesLoading);
const fetchCompanies = useOnboardingStore((s) => s.fetchCompanies);
const createCompany = useOnboardingStore((s) => s.createCompany);

// COMPANY DETAIL VIEW
const selectedCompany = useOnboardingStore((s) => s.selectedCompany);
const executives = useOnboardingStore((s) => s.executives);
const executivesLoading = useOnboardingStore((s) => s.executivesLoading);

// EXECUTIVE DETAIL VIEW
const selectedExecutive = useOnboardingStore((s) => s.selectedExecutive);
const documents = useOnboardingStore((s) => s.documents);
const documentsLoading = useOnboardingStore((s) => s.documentsLoading);
const activeJob = useOnboardingStore((s) => s.activeJob);
```

This pattern ensures components only re-render when their specific subscribed state changes.
