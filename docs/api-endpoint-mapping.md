# API Endpoint Mapping - Onboarding Dashboard

## Service Ports

| Service | Port | Base Path |
|---------|------|-----------|
| **Onboarding Service** | 8002 | `/api/v1` |
| **Embedding Service** | 8001 | `/` |
| **RAG API** | 8000 | `/api/v1` |

---

## Onboarding Service (Port 8002)

### Companies

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `GET` | `/api/v1/companies` | List all companies | - | `CompanyResponse[]` |
| `POST` | `/api/v1/companies` | Create company | `CompanyCreate` | `CompanyResponse` |
| `GET` | `/api/v1/companies/{company_id}` | Get company with executives | - | `CompanyDetailResponse` |
| `PATCH` | `/api/v1/companies/{company_id}` | Update company | `CompanyUpdate` | `CompanyResponse` |

**CompanyCreate Schema:**
```json
{
  "id": "string (required, slug, 1-50 chars)",
  "name": "string (required, 1-255 chars)",
  "industry": "string (optional)",
  "description": "string (optional)",
  "metadata": "object (optional)"
}
```

**CompanyDetailResponse includes:**
- `executives`: Array of executives with hierarchy info
- `executives_count`: Number of executives

---

### Executives

| Method | Endpoint | Description | Query Params | Request Body |
|--------|----------|-------------|--------------|--------------|
| `GET` | `/api/v1/companies/{company_id}/executives` | List executives | `hierarchy=bool`, `sort=name\|hierarchy\|created` | - |
| `POST` | `/api/v1/companies/{company_id}/executives` | Create executive | - | `ExecutiveCreate` |
| `GET` | `/api/v1/companies/{company_id}/executives/{executive_id}` | Get executive detail | `include=profile,voiceprint,documents` | - |
| `PATCH` | `/api/v1/companies/{company_id}/executives/{executive_id}` | Update executive | - | `ExecutiveUpdate` |
| `DELETE` | `/api/v1/companies/{company_id}/executives/{executive_id}` | Soft delete executive | - | - |

**ExecutiveCreate Schema:**
```json
{
  "id": "string (required, slug)",
  "name": "string (required)",
  "company_id": "string (required)",
  "name_english": "string (optional)",
  "title": "string (optional)",
  "department": "string (optional)",
  "email": "string (optional)",
  "reports_to": "string (optional, executive_id)",
  "hierarchy_level": "integer (default: 0, 0=CEO)",
  "sort_order": "integer (default: 0)"
}
```

**ExecutiveDetailResponse includes:**
- `has_profile`: boolean
- `has_voiceprint`: boolean
- `direct_reports`: string[] (executive IDs)
- `profile`: object (if include=profile)
- `voiceprint`: object (if include=voiceprint)
- `documents`: array (if include=documents)

---

### Profile Documents (Executive-specific)

| Method | Endpoint | Description | Query Params | Request Body |
|--------|----------|-------------|--------------|--------------|
| `POST` | `/api/v1/companies/{cid}/executives/{eid}/documents` | Upload documents | `auto_calibrate=bool`, `calibrate_mode=full\|incremental` | `multipart/form-data` with `files[]` |
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/documents` | List documents | `include_inactive=bool` | - |
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/documents/{doc_id}` | Get document with text | - | - |
| `DELETE` | `/api/v1/companies/{cid}/executives/{eid}/documents/{doc_id}` | Soft delete document | - | - |
| `POST` | `/api/v1/companies/{cid}/executives/{eid}/documents/{doc_id}/restore` | Restore document | - | - |

**Upload Response:**
```json
{
  "company_id": "string",
  "executive_id": "string",
  "documents": [
    {
      "id": "uuid",
      "filename": "string",
      "content_type": "string",
      "file_size": "integer",
      "text_length": "integer",
      "doc_type": "profile",
      "is_active": true,
      "uploaded_at": "datetime"
    }
  ],
  "total_text_length": "integer",
  "job_id": "string (if auto_calibrate=true)"
}
```

**Supported File Types:** PDF, DOCX, TXT, JSON, PNG, JPG (max 50MB)

---

### Knowledgebase Documents (Company-wide)

| Method | Endpoint | Description | Query Params | Request Body |
|--------|----------|-------------|--------------|--------------|
| `POST` | `/api/v1/companies/{company_id}/knowledgebase` | Upload KB documents | - | `multipart/form-data` with `files[]` |
| `GET` | `/api/v1/companies/{company_id}/knowledgebase` | List KB documents | `include_inactive=bool` | - |
| `GET` | `/api/v1/companies/{company_id}/knowledgebase/{doc_id}` | Get KB document | - | - |
| `DELETE` | `/api/v1/companies/{company_id}/knowledgebase/{doc_id}` | Delete KB document | - | - |

**Key Difference from Profile Documents:**
- KB docs bypass LLM extraction pipeline
- KB docs are embedded directly (chunked → embedded)
- KB docs are shared by ALL executives in the company
- KB docs have `executive_id = NULL` in database

---

### Profile & Voiceprint

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|--------------|
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/profile` | Get profile + voiceprint + validation | - |
| `PATCH` | `/api/v1/companies/{cid}/executives/{eid}/profile` | Edit profile sections | `ProfileEditRequest` |
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/voiceprint` | Get voiceprint only | - |
| `PATCH` | `/api/v1/companies/{cid}/executives/{eid}/voiceprint` | Edit voiceprint sections | `VoiceprintEditRequest` |

**ProfileEditRequest Schema:**
```json
{
  "sections": {
    "core_values": ["value1", "value2"],
    "communication_style.formality_scale": 7,
    "decision_making.risk_tolerance": 6
  },
  "regenerate_embeddings": false
}
```
*Supports dot notation for nested keys*

---

### Calibration & Jobs

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|--------------|
| `POST` | `/api/v1/companies/{cid}/executives/{eid}/calibrate` | Start calibration | `CalibrationRequest` |
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/jobs/{job_id}` | Get job status | - |
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/jobs/{job_id}/result` | Get job result | - |

**CalibrationRequest Schema:**
```json
{
  "mode": "full | incremental",
  "extractors": ["background_identity", "thinking_patterns", ...],
  "merge_strategy": "replace | merge",
  "regenerate_embeddings": true
}
```

**Available Extractors:**
- `background_identity`
- `thinking_patterns`
- `communication_style`
- `values_decisions`
- `domain_tech`
- `red_flags_inference`
- `speaking_patterns`

**JobStatusResponse Schema:**
```json
{
  "id": "uuid",
  "company_id": "string",
  "executive_id": "string",
  "job_type": "full_onboarding | profile_only | voiceprint_only | calibration",
  "status": "pending | parsing | extracting | assembling | validating | deploying | embedding | completed | failed",
  "progress": 0.0-1.0,
  "error_message": "string (if failed)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

### Onboarding

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|--------------|
| `POST` | `/api/v1/companies/{cid}/executives/{eid}/onboard` | Start full onboarding | `OnboardingStartRequest` |

**OnboardingStartRequest Schema:**
```json
{
  "job_type": "full_onboarding | profile_only | voiceprint_only"
}
```

---

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |

---

## Embedding Service (Port 8001)

### Embeddings

| Method | Endpoint | Description | Query Params |
|--------|----------|-------------|--------------|
| `POST` | `/embeddings/documents` | Embed single document | `async_processing=bool` |
| `POST` | `/embeddings/batch` | Batch embed documents | `async_processing=bool` |
| `POST` | `/embeddings/incremental` | Incremental update | - |

### Version Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/embeddings/version` | Get version history |
| `GET` | `/embeddings/version/current` | Get current version |
| `POST` | `/embeddings/version/snapshot` | Create snapshot |
| `POST` | `/embeddings/rollback` | Rollback to version |

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tasks/{task_id}` | Get task status |
| `DELETE` | `/tasks/{task_id}` | Cancel task |
| `GET` | `/tasks` | Get queue status |

### Health & Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Processing metrics |

---

## Frontend API Proxy Configuration

**vite.config.js proxy setup:**

```javascript
proxy: {
  '/api/onboarding': {
    target: 'http://localhost:8002',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api\/onboarding/, '/api/v1'),
  },
  '/api/embedding': {
    target: 'http://localhost:8001',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api\/embedding/, ''),
  },
}
```

**Frontend API calls:**
```javascript
// Companies
GET    /api/onboarding/companies              → GET  :8002/api/v1/companies
POST   /api/onboarding/companies              → POST :8002/api/v1/companies
GET    /api/onboarding/companies/:id          → GET  :8002/api/v1/companies/:id

// Executives
GET    /api/onboarding/companies/:cid/executives
POST   /api/onboarding/companies/:cid/executives
GET    /api/onboarding/companies/:cid/executives/:eid?include=profile,documents

// Documents
POST   /api/onboarding/companies/:cid/executives/:eid/documents  (multipart)
GET    /api/onboarding/companies/:cid/executives/:eid/documents
DELETE /api/onboarding/companies/:cid/executives/:eid/documents/:did

// Knowledgebase
POST   /api/onboarding/companies/:cid/knowledgebase  (multipart)
GET    /api/onboarding/companies/:cid/knowledgebase
DELETE /api/onboarding/companies/:cid/knowledgebase/:did

// Calibration
POST   /api/onboarding/companies/:cid/executives/:eid/calibrate
GET    /api/onboarding/companies/:cid/executives/:eid/jobs/:jid
```

---

## Common Response Patterns

### Success Response
```json
{
  "id": "...",
  "...fields..."
}
```

### List Response
```json
{
  "company_id": "string",
  "total": 10,
  "documents": [...] | "executives": [...]
}
```

### Error Response (422 Validation)
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Error message",
      "type": "value_error"
    }
  ]
}
```

### Job Status Response
```json
{
  "id": "uuid",
  "status": "pending | parsing | ... | completed | failed",
  "progress": 0.5,
  "error_message": null
}
```
