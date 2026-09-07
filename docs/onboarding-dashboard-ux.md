# Onboarding Dashboard - UX Design Document

## Overview

Admin-only dashboard for managing company onboarding, executive profiles, and document management in the AI Officer system.

---

## User Role

**Admin Only** - Restricted access for administrators who manage the onboarding of companies and executives.

---

## Information Architecture

### Navigation Structure

```
/admin/onboarding
  ├── /companies                              # List all companies
  │     └── /companies/:id                    # Company detail + knowledgebase + executives
  │           └── /executives/:eid            # Executive detail + profile documents
  │
  └── /processing (optional)                  # Global processing status monitor
```

### Three-Level Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ADMIN ONBOARDING DASHBOARD                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LEVEL 1: Companies List                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ [+ New Company]                          [Search] [Filter by status] │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ Acme Corp    │  │ TechStart    │  │ GlobalBank   │               │   │
│  │  │ Technology   │  │ Fintech      │  │ Finance      │               │   │
│  │  │ 5 executives │  │ 2 executives │  │ 12 executives│               │   │
│  │  │ 8 KB docs    │  │ 3 KB docs    │  │ 25 KB docs   │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  LEVEL 2: Company Detail (click on company)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ ← Back to Companies        ACME CORP                    [Edit] [⚙]  │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐│   │
│  │  │ COMPANY KNOWLEDGEBASE                           [+ Upload Files] ││   │
│  │  │ ───────────────────────────────────────────────────────────────  ││   │
│  │  │ 📄 company_policy.pdf          12 KB    Processed ✓   [🗑]      ││   │
│  │  │ 📄 employee_handbook.pdf       45 KB    Processed ✓   [🗑]      ││   │
│  │  │ 📄 compliance_guide.docx       8 KB     Processing... [🗑]      ││   │
│  │  └─────────────────────────────────────────────────────────────────┘│   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐│   │
│  │  │ EXECUTIVES                                    [+ Add Executive]  ││   │
│  │  │ ───────────────────────────────────────────────────────────────  ││   │
│  │  │  👤 John Doe         CEO         3 docs   Calibrated ✓    [→]   ││   │
│  │  │    └─ 👤 Jane Smith  CTO         5 docs   Calibrated ✓    [→]   ││   │
│  │  │       └─ 👤 Bob Lee  VP Eng      2 docs   Pending...      [→]   ││   │
│  │  │  👤 Alice Wong       CFO         4 docs   Calibrated ✓    [→]   ││   │
│  │  └─────────────────────────────────────────────────────────────────┘│   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  LEVEL 3: Executive Detail (click on executive)                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ ← Back to Acme Corp       JOHN DOE - CEO            [Edit] [Calibrate]│  │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐│   │
│  │  │ PROFILE STATUS                                                   ││   │
│  │  │ ───────────────────────────────────────────────────────────────  ││   │
│  │  │ Profile: ✓ Generated    Voiceprint: ✓ Ready    Embeddings: ✓    ││   │
│  │  │ Last calibrated: 2 days ago                                      ││   │
│  │  └─────────────────────────────────────────────────────────────────┘│   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐│   │
│  │  │ PROFILE DOCUMENTS                               [+ Upload Files] ││   │
│  │  │ ───────────────────────────────────────────────────────────────  ││   │
│  │  │ 📄 interview_transcript.pdf    25 KB   Extracted ✓    [🗑]      ││   │
│  │  │ 📄 keynote_speech.docx         12 KB   Extracted ✓    [🗑]      ││   │
│  │  │ 📄 bio_article.txt             3 KB    Extracted ✓    [🗑]      ││   │
│  │  └─────────────────────────────────────────────────────────────────┘│   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐│   │
│  │  │ ACCESS TO COMPANY KNOWLEDGEBASE (Read-only view)                ││   │
│  │  │ ───────────────────────────────────────────────────────────────  ││   │
│  │  │ This executive has access to 3 company-wide documents            ││   │
│  │  │ (Manage at company level)                                        ││   │
│  │  └─────────────────────────────────────────────────────────────────┘│   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key UX Principles

| Principle | Implementation |
|-----------|----------------|
| **Hierarchy-first** | Companies → Executives → Documents (drill-down navigation) |
| **Two document contexts** | Company Knowledgebase (shared) vs Executive Profile (personal) |
| **Status visibility** | Clear badges for processing state (Pending, Processing, Calibrated, Failed) |
| **Immediate actions** | Upload/delete files inline without leaving the current view |
| **Org chart awareness** | Show `reports_to` hierarchy visually (indentation or tree) |

---

## User Flows

### Flow 1: Onboard New Company + Executive

```
1. Admin clicks [+ New Company]
2. Modal: Enter company name, industry, metadata → Save
3. Lands on Company Detail page (empty)
4. Admin uploads Knowledgebase documents (drag-drop)
5. Admin clicks [+ Add Executive]
6. Modal: Name, title, reports_to (dropdown) → Save
7. Lands on Executive Detail page
8. Admin uploads Profile documents (drag-drop)
9. Admin clicks [Calibrate] → Shows progress
10. Done - Executive ready for chat
```

### Flow 2: Add Document to Existing Executive

```
1. Admin navigates: Companies → Acme Corp → John Doe
2. Clicks [+ Upload Files] in Profile Documents section
3. Drag-drop or file picker
4. Files upload, show "Processing..." status
5. Optional: Click [Calibrate] to regenerate profile
```

### Flow 3: Remove Document

```
1. Navigate to document's location (company KB or executive profile)
2. Click [🗑] icon
3. Confirmation modal: "Remove document? This will delete embeddings."
4. Soft-delete (can restore if needed)
```

### Flow 4: View Company Hierarchy

```
1. Navigate to Company Detail
2. Executives section shows org tree with indentation
3. Click any executive to view their details
4. Breadcrumb shows: Companies > Acme Corp > John Doe
```

---

## Component Breakdown

| Component | Location | Purpose |
|-----------|----------|---------|
| `CompanyList` | `/admin/onboarding` | Grid/list of all companies |
| `CompanyCard` | Within list | Summary card with stats |
| `CompanyDetail` | `/admin/onboarding/companies/:id` | KB docs + executives list |
| `ExecutiveTree` | Within company detail | Hierarchical org view |
| `ExecutiveDetail` | `/admin/onboarding/companies/:cid/executives/:eid` | Profile docs + status |
| `DocumentList` | Reusable | File list with actions |
| `FileUploader` | Modal/inline | Drag-drop upload |
| `StatusBadge` | Everywhere | Processing state indicator |
| `CalibrationModal` | Executive detail | Trigger & monitor calibration |

---

## Status States

### Document Status
- `uploading` - File being uploaded
- `processing` - Being parsed/embedded
- `processed` - Ready for use
- `failed` - Processing error

### Executive Status
- `pending` - No documents uploaded
- `documents_uploaded` - Has documents, not calibrated
- `calibrating` - Calibration in progress
- `calibrated` - Profile generated and ready
- `failed` - Calibration error

### Calibration Job Status
- `pending` → `parsing` → `extracting` → `assembling` → `validating` → `deploying` → `embedding` → `completed`
- `failed` (can occur at any stage)

---

## Document Types

### Company Knowledgebase (Shared)
- Location: Company Detail page
- Access: All executives in company
- Processing: Direct embedding (no LLM extraction)
- Examples: Policies, procedures, handbooks, compliance docs

### Executive Profile Documents (Personal)
- Location: Executive Detail page
- Access: Only this executive
- Processing: 7 LLM extractors → Profile + Voiceprint → Embeddings
- Examples: Interviews, speeches, biographies, articles

---

## Wireframe Notes

### Company List View
- Card grid layout (responsive: 3 cols desktop, 2 tablet, 1 mobile)
- Each card shows: Name, industry, executive count, KB doc count
- Quick actions: View, Edit (on hover)
- Search bar filters by name/industry
- Status filter dropdown

### Company Detail View
- Header: Company name, industry badge, edit button
- Two sections stacked vertically:
  1. Knowledgebase Documents (collapsible)
  2. Executives List (tree view)
- Upload button triggers drag-drop zone or file picker

### Executive Detail View
- Header: Name, title, company breadcrumb
- Status card showing profile/voiceprint/embedding status
- Profile Documents section with upload
- Read-only reference to company knowledgebase
- Calibrate button (primary action)

---

## Responsive Considerations

- **Desktop-first**: Primary use case is admin on desktop
- **Tablet**: 2-column layout, stacked sections
- **Mobile**: Single column, collapsible sections (lower priority)

---

## Accessibility

- Keyboard navigation for all actions
- ARIA labels on status badges
- Focus management in modals
- Screen reader announcements for upload/processing status

---

## Future Enhancements

1. Bulk CSV import for executives
2. Document preview with extracted text
3. Profile editing interface
4. Voiceprint tuning controls
5. Processing queue dashboard
6. Audit log for changes
