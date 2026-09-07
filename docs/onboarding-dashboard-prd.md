# Product Requirements Document (PRD)
# Onboarding Dashboard for AI Officer

**Version:** 1.0
**Date:** February 2026
**Author:** AI Officer Team
**Status:** Draft

---

## 1. Executive Summary

### 1.1 Problem Statement

The AI Officer system requires a user-friendly interface for administrators to onboard companies and executives into the cognitive twin platform. Currently, onboarding is done via API calls, which is error-prone and not scalable for non-technical users.

### 1.2 Solution

Build an admin dashboard integrated into the existing React frontend that enables:
- Company management (CRUD operations)
- Executive profile management with organizational hierarchy
- Document upload and management (both company knowledgebase and executive profiles)
- Calibration triggering and monitoring
- Status visibility across all entities

### 1.3 Success Metrics

| Metric | Target |
|--------|--------|
| Time to onboard new company + executive | < 10 minutes |
| Admin task completion rate | > 95% without support |
| Document upload success rate | > 99% |
| System adoption | 100% of onboarding done via dashboard |

---

## 2. Product Overview

### 2.1 Target Users

| User Type | Description | Access Level |
|-----------|-------------|--------------|
| **System Admin** | Manages all companies and executives | Full CRUD |
| **Company Admin** | Manages their company's executives (future) | Company-scoped |

### 2.2 User Stories

#### Epic 1: Company Management

| ID | User Story | Priority |
|----|------------|----------|
| US-1.1 | As an admin, I want to create a new company so that I can start onboarding their executives | P0 |
| US-1.2 | As an admin, I want to view all companies in a list so that I can navigate to any company | P0 |
| US-1.3 | As an admin, I want to edit company details so that I can update metadata | P1 |
| US-1.4 | As an admin, I want to search/filter companies so that I can find specific ones quickly | P1 |
| US-1.5 | As an admin, I want to see company statistics (exec count, doc count) at a glance | P1 |

#### Epic 2: Company Knowledgebase

| ID | User Story | Priority |
|----|------------|----------|
| US-2.1 | As an admin, I want to upload documents to company knowledgebase so all executives can access them | P0 |
| US-2.2 | As an admin, I want to see all knowledgebase documents for a company | P0 |
| US-2.3 | As an admin, I want to delete knowledgebase documents when they're outdated | P0 |
| US-2.4 | As an admin, I want to see processing status of each document | P1 |
| US-2.5 | As an admin, I want to drag-and-drop multiple files at once | P1 |

#### Epic 3: Executive Management

| ID | User Story | Priority |
|----|------------|----------|
| US-3.1 | As an admin, I want to add an executive to a company | P0 |
| US-3.2 | As an admin, I want to view all executives in a company with hierarchy | P0 |
| US-3.3 | As an admin, I want to edit executive details (name, title, reports_to) | P1 |
| US-3.4 | As an admin, I want to see executive status (pending, calibrated, etc.) | P0 |
| US-3.5 | As an admin, I want to delete/archive an executive | P2 |

#### Epic 4: Executive Documents

| ID | User Story | Priority |
|----|------------|----------|
| US-4.1 | As an admin, I want to upload profile documents for an executive | P0 |
| US-4.2 | As an admin, I want to view all documents for an executive | P0 |
| US-4.3 | As an admin, I want to delete documents from an executive's profile | P0 |
| US-4.4 | As an admin, I want to see which company docs the executive has access to | P2 |

#### Epic 5: Calibration & Processing

| ID | User Story | Priority |
|----|------------|----------|
| US-5.1 | As an admin, I want to trigger calibration for an executive | P0 |
| US-5.2 | As an admin, I want to see calibration progress in real-time | P1 |
| US-5.3 | As an admin, I want to see if calibration failed and why | P0 |
| US-5.4 | As an admin, I want to re-run calibration after adding new documents | P1 |

---

## 3. Functional Requirements

### 3.1 Company Management

#### FR-1.1: Create Company
- **Input:** Company ID (slug), Name, Industry, Metadata (optional JSON)
- **Validation:** ID must be unique, alphanumeric with underscores
- **Output:** Company created, redirect to company detail page
- **API:** `POST /api/v1/companies`

#### FR-1.2: List Companies
- **Display:** Card grid with company name, industry, executive count, KB doc count
- **Search:** Filter by name (client-side for < 100, server-side for more)
- **Sorting:** By name (default), by created date
- **API:** `GET /api/v1/companies`

#### FR-1.3: View Company Detail
- **Display:** Company header, knowledgebase section, executives section
- **Navigation:** Breadcrumb: Onboarding > Companies > {Company Name}
- **API:** `GET /api/v1/companies/{id}`

#### FR-1.4: Update Company
- **Editable fields:** Name, Industry, Metadata
- **Non-editable:** ID (immutable)
- **API:** `PATCH /api/v1/companies/{id}`

### 3.2 Knowledgebase Management

#### FR-2.1: Upload Knowledgebase Documents
- **Supported formats:** PDF, DOCX, TXT, JSON, PNG, JPG
- **Max file size:** 50MB per file
- **Multi-file:** Yes, up to 10 files at once
- **Upload method:** Drag-drop zone or file picker
- **API:** `POST /api/v1/companies/{cid}/knowledgebase`

#### FR-2.2: List Knowledgebase Documents
- **Display:** Table with filename, size, upload date, status
- **Status badges:** Uploading, Processing, Processed, Failed
- **API:** `GET /api/v1/companies/{cid}/knowledgebase`

#### FR-2.3: Delete Knowledgebase Document
- **Confirmation:** Modal with warning about embedding deletion
- **Soft delete:** Document marked as deleted, can be restored
- **API:** `DELETE /api/v1/companies/{cid}/knowledgebase/{did}`

### 3.3 Executive Management

#### FR-3.1: Create Executive
- **Input:** Executive ID (slug), Name, Title, Reports To (dropdown)
- **Validation:** ID unique within company
- **Output:** Executive created, redirect to executive detail
- **API:** `POST /api/v1/companies/{cid}/executives`

#### FR-3.2: List Executives (Hierarchical)
- **Display:** Tree view with indentation based on `reports_to`
- **Each row:** Avatar placeholder, name, title, doc count, status badge
- **Click action:** Navigate to executive detail
- **API:** `GET /api/v1/companies/{cid}/executives`

#### FR-3.3: View Executive Detail
- **Sections:**
  1. Header: Name, title, status badges
  2. Profile Status Card: Profile, Voiceprint, Embeddings status
  3. Profile Documents list
  4. Company KB access (read-only reference)
- **Actions:** Edit, Calibrate, Delete
- **API:** `GET /api/v1/companies/{cid}/executives/{eid}`

#### FR-3.4: Update Executive
- **Editable:** Name, Title, Reports To
- **Non-editable:** ID
- **API:** `PATCH /api/v1/companies/{cid}/executives/{eid}`

### 3.4 Executive Documents

#### FR-4.1: Upload Profile Documents
- **Same specs as knowledgebase upload**
- **API:** `POST /api/v1/companies/{cid}/executives/{eid}/documents`

#### FR-4.2: List Profile Documents
- **Same display as knowledgebase**
- **API:** `GET /api/v1/companies/{cid}/executives/{eid}/documents`

#### FR-4.3: Delete Profile Document
- **Same flow as knowledgebase delete**
- **API:** `DELETE /api/v1/companies/{cid}/executives/{eid}/documents/{did}`

### 3.5 Calibration

#### FR-5.1: Trigger Calibration
- **Button:** "Calibrate" on executive detail page
- **Options modal:**
  - Mode: Full (default) or Incremental
  - Regenerate embeddings: Yes (default) / No
- **API:** `POST /api/v1/companies/{cid}/executives/{eid}/calibrate`

#### FR-5.2: Calibration Progress
- **Display:** Progress indicator with current stage
- **Stages:** Parsing → Extracting → Assembling → Validating → Deploying → Embedding
- **Polling:** Every 3 seconds until complete
- **API:** `GET /api/v1/companies/{cid}/executives/{eid}/jobs/{jid}`

#### FR-5.3: Calibration Result
- **Success:** Update status badges, show success toast
- **Failure:** Show error message, allow retry
- **API:** `GET /api/v1/companies/{cid}/executives/{eid}/jobs/{jid}/result`

---

## 4. Non-Functional Requirements

### 4.1 Performance

| Requirement | Target |
|-------------|--------|
| Page load time | < 2 seconds |
| File upload start | < 500ms after drop |
| API response time | < 1 second (95th percentile) |
| Support concurrent uploads | Up to 10 files |

### 4.2 Security

- Admin authentication required (existing auth system)
- CSRF protection on all mutations
- File type validation (server-side)
- Max file size enforcement (server-side)
- Audit logging for all admin actions (future)

### 4.3 Reliability

- Graceful error handling with user-friendly messages
- Retry logic for failed uploads (up to 3 attempts)
- Offline detection with appropriate messaging

### 4.4 Usability

- Responsive design (desktop-first, tablet-friendly)
- Keyboard accessible
- Loading states for all async operations
- Confirmation dialogs for destructive actions

---

## 5. Technical Architecture

### 5.1 Frontend Stack

- **Framework:** React (existing)
- **Routing:** React Router (existing)
- **State Management:** React Query for server state
- **UI Components:** Existing design system (to be analyzed)
- **File Upload:** react-dropzone or similar

### 5.2 API Integration

| Service | Base URL | Purpose |
|---------|----------|---------|
| Onboarding Service | `http://localhost:8002/api/v1` | Companies, Executives, Documents, Calibration |
| Embedding Service | `http://localhost:8001` | (Internal, called by onboarding) |
| RAG API | `http://localhost:8000/api/v1` | Chat (not used in dashboard) |

### 5.3 New Routes

```
/admin/onboarding                           # Companies list
/admin/onboarding/companies/new             # Create company form
/admin/onboarding/companies/:id             # Company detail
/admin/onboarding/companies/:id/edit        # Edit company
/admin/onboarding/companies/:cid/executives/:eid    # Executive detail
/admin/onboarding/companies/:cid/executives/:eid/edit  # Edit executive
```

### 5.4 Component Structure

```
src/
  pages/
    admin/
      onboarding/
        index.tsx                 # Companies list page
        CompanyDetail.tsx         # Company detail page
        ExecutiveDetail.tsx       # Executive detail page
  components/
    onboarding/
      CompanyCard.tsx
      CompanyForm.tsx
      ExecutiveTree.tsx
      ExecutiveForm.tsx
      DocumentList.tsx
      FileUploader.tsx
      StatusBadge.tsx
      CalibrationModal.tsx
  hooks/
    useCompanies.ts
    useExecutives.ts
    useDocuments.ts
    useCalibration.ts
  api/
    onboarding.ts                 # API client for onboarding service
```

---

## 6. Design Specifications

### 6.1 Visual Design

- Follow existing design system
- Status colors:
  - Pending: Gray
  - Processing: Blue (with animation)
  - Success/Calibrated: Green
  - Failed: Red

### 6.2 Interaction Patterns

- **Create entities:** Modal forms
- **Edit entities:** Inline or dedicated page
- **Delete entities:** Confirmation modal
- **Upload files:** Drag-drop zone with progress
- **Long operations:** Progress indicator with cancel option

---

## 7. Release Plan

### Phase 1: MVP (P0 features)
- Company CRUD
- Executive CRUD
- Document upload/list/delete
- Basic calibration trigger

### Phase 2: Enhanced (P1 features)
- Search and filtering
- Hierarchical executive view
- Real-time calibration progress
- Drag-drop multi-file upload
- Status badges and notifications

### Phase 3: Polish (P2 features)
- Document preview
- Bulk operations
- Audit logging
- Company admin role (multi-tenant)

---

## 8. Open Questions

1. **Authentication:** Use existing auth or separate admin auth?
2. **Multi-tenancy:** Should company admins see only their company?
3. **Notifications:** Email notifications for calibration completion?
4. **Document preview:** Show extracted text in UI?
5. **Bulk import:** CSV upload for executives?

---

## 9. Appendix

### 9.1 API Reference

See `RAG/README_SERVICES.md` for complete API documentation.

### 9.2 Database Schema

See `RAG/config/` for migration files and schema details.

### 9.3 Related Documents

- [UX Design Document](./onboarding-dashboard-ux.md)
- [Services Documentation](../RAG/README_SERVICES.md)
