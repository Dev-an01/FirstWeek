"""
Pydantic request/response schemas for the Onboarding Service API.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class JobStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    ASSEMBLING = "assembling"
    VALIDATING = "validating"
    DEPLOYING = "deploying"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, Enum):
    FULL_ONBOARDING = "full_onboarding"
    PROFILE_ONLY = "profile_only"
    VOICEPRINT_ONLY = "voiceprint_only"
    CALIBRATION = "calibration"


class CalibrationMode(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


class MergeStrategy(str, Enum):
    REPLACE = "replace"
    MERGE = "merge"


class DocumentType(str, Enum):
    """Type of document determining processing pipeline."""
    PROFILE = "profile"  # Executive-specific, goes through LLM extraction
    KNOWLEDGEBASE = "knowledgebase"  # Company-wide, direct embedding (no extraction)


class ExtractorName(str, Enum):
    BACKGROUND_IDENTITY = "background_identity"
    THINKING_PATTERNS = "thinking_patterns"
    COMMUNICATION_STYLE = "communication_style"
    VALUES_DECISIONS = "values_decisions"
    DOMAIN_TECH = "domain_tech"
    RED_FLAGS_INFERENCE = "red_flags_inference"
    SPEAKING_PATTERNS = "speaking_patterns"


# ============================================================================
# Company Models
# ============================================================================

class CompanyCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=50, description="Unique company ID (slug)")
    name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CompanyResponse(BaseModel):
    id: str
    name: str
    industry: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# Executive Models
# ============================================================================

class ExecutiveCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=50, description="Unique executive ID (slug)")
    name: str = Field(..., min_length=1, max_length=255)
    name_english: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    company_id: str = Field(..., description="Company this executive belongs to")
    email: Optional[str] = None
    reports_to: Optional[str] = Field(None, description="ID of executive this person reports to")
    hierarchy_level: int = Field(0, description="Hierarchy level: 0=CEO, 1=C-suite, 2=VP, etc.")
    sort_order: int = Field(0, description="Custom sort order within same level")


class ExecutiveResponse(BaseModel):
    id: str
    name: str
    name_english: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    company_id: Optional[str] = None
    email: Optional[str] = None
    has_profile: bool = False
    has_voiceprint: bool = False
    has_voice_keys: bool = False
    reports_to: Optional[str] = None
    hierarchy_level: int = 0
    sort_order: int = 0


class ExecutiveDetailResponse(BaseModel):
    """Extended executive response with profile, voiceprint, and direct reports."""
    id: str
    name: str
    name_english: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    company_id: Optional[str] = None
    email: Optional[str] = None
    has_profile: bool = False
    has_voiceprint: bool = False
    has_voice_keys: bool = False
    embeddings_count: int = 0
    reports_to: Optional[str] = None
    hierarchy_level: int = 0
    sort_order: int = 0
    profile: Optional[Dict[str, Any]] = None
    voiceprint: Optional[Dict[str, Any]] = None
    documents: Optional[List[Dict[str, Any]]] = None
    direct_reports: List[str] = Field(default_factory=list)


class ExecutiveHierarchyItem(BaseModel):
    """Executive item with hierarchy information for company view."""
    id: str
    name: str
    name_english: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    hierarchy_level: int = 0
    has_profile: bool = False
    has_voiceprint: bool = False
    has_voice_keys: bool = False
    reports_to: Optional[str] = None
    direct_reports: List[str] = Field(default_factory=list)


class CompanyDetailResponse(BaseModel):
    """Company response with executives hierarchy."""
    id: str
    name: str
    industry: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    executives_count: int = 0
    executives: List[ExecutiveHierarchyItem] = Field(default_factory=list)


class ExecutiveListResponse(BaseModel):
    """Response for listing executives with optional hierarchy grouping."""
    company_id: str
    total: int
    by_level: Optional[Dict[str, List[ExecutiveHierarchyItem]]] = None
    executives: List[ExecutiveHierarchyItem] = Field(default_factory=list)


# ============================================================================
# Onboarding Job Models
# ============================================================================

class OnboardingStartRequest(BaseModel):
    job_type: JobType = JobType.FULL_ONBOARDING


class JobStatusResponse(BaseModel):
    id: str
    company_id: Optional[str] = None
    executive_id: Optional[str] = None
    job_type: str
    status: str
    progress: float = 0.0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class JobResultResponse(BaseModel):
    id: str
    status: str
    profile: Optional[Dict[str, Any]] = None
    voiceprint: Optional[Dict[str, Any]] = None
    validation_report: Optional[Dict[str, Any]] = None


# ============================================================================
# Document Upload
# ============================================================================

class UploadedDocument(BaseModel):
    filename: str
    size: int
    content_type: Optional[str] = None
    text_length: int = 0


class UploadResponse(BaseModel):
    executive_id: str
    documents: List[UploadedDocument]
    total_text_length: int


# ============================================================================
# Health
# ============================================================================

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "onboarding"
    version: str = "1.0.0"
    database: str = "unknown"


# ============================================================================
# Document Management Models
# ============================================================================

class DocumentMetadata(BaseModel):
    """Document metadata (without extracted text)."""
    id: str
    company_id: str
    executive_id: Optional[str] = None  # NULL for knowledgebase documents
    filename: str
    content_type: Optional[str] = None
    file_size: int = 0
    text_length: int = 0
    doc_type: str = "profile"  # 'profile' or 'knowledgebase'
    is_active: bool = True
    uploaded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentDetail(BaseModel):
    """Full document including extracted text."""
    id: str
    company_id: str
    executive_id: Optional[str] = None  # NULL for knowledgebase documents
    filename: str
    content_type: Optional[str] = None
    file_size: int = 0
    extracted_text: str
    text_length: int = 0
    doc_type: str = "profile"  # 'profile' or 'knowledgebase'
    is_active: bool = True
    uploaded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    """Response for listing documents."""
    company_id: str
    executive_id: str
    total: int
    documents: List[DocumentMetadata]


class DocumentUploadResponse(BaseModel):
    """Response for document upload (with optional auto-calibration)."""
    company_id: str
    executive_id: str
    documents: List[DocumentMetadata]
    total_text_length: int
    job_id: Optional[str] = Field(None, description="Calibration job ID if auto_calibrate=true")


# ============================================================================
# Profile & Voiceprint Edit Models
# ============================================================================

class ProfileEditRequest(BaseModel):
    """
    Request to edit profile sections.

    Supports dot notation for nested keys:
    - "core_values": [...] replaces entire section
    - "communication_style.formality_scale": 7 updates nested field
    """
    sections: Dict[str, Any] = Field(
        ...,
        description="Section updates. Keys can use dot notation for nested paths."
    )
    regenerate_embeddings: bool = Field(
        False,
        description="If true, regenerate embeddings after edit."
    )


class ProfileEditResponse(BaseModel):
    """Response for profile edit."""
    success: bool
    updated_sections: List[str]
    regenerate_job_id: Optional[str] = None


class VoiceprintEditRequest(BaseModel):
    """
    Request to edit voiceprint sections.

    Supports dot notation for nested keys:
    - "casual_responses.greetings": ["Hi!", "Hello!"]
    - "style_markers.formality": 8
    """
    sections: Dict[str, Any] = Field(
        ...,
        description="Section updates. Keys can use dot notation for nested paths."
    )
    regenerate_embeddings: bool = Field(
        False,
        description="If true, regenerate embeddings after edit."
    )


class VoiceprintEditResponse(BaseModel):
    """Response for voiceprint edit."""
    success: bool
    updated_sections: List[str]
    regenerate_job_id: Optional[str] = None


class ProfileViewResponse(BaseModel):
    """Response for viewing full profile with voiceprint and validation."""
    profile: Optional[Dict[str, Any]] = None
    voiceprint: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None


# ============================================================================
# Calibration Models
# ============================================================================

class CalibrationRequest(BaseModel):
    """Request to calibrate/re-extract an executive profile."""
    mode: CalibrationMode = Field(
        CalibrationMode.FULL,
        description="full = re-extract everything, incremental = specific extractors only"
    )
    extractors: Optional[List[ExtractorName]] = Field(
        None,
        description="For incremental mode: list of extractors to run"
    )
    merge_strategy: MergeStrategy = Field(
        MergeStrategy.REPLACE,
        description="For incremental mode: how to merge new extractions"
    )
    regenerate_embeddings: bool = Field(
        True,
        description="Whether to regenerate embeddings after calibration"
    )


class CalibrationResponse(BaseModel):
    """Response for calibration request."""
    job_id: str
    status: str = "started"
    mode: str
    extractors: Optional[List[str]] = None


# ============================================================================
# Executive Update Model
# ============================================================================

class ExecutiveUpdate(BaseModel):
    """Request to update executive basic info."""
    name: Optional[str] = None
    name_english: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    reports_to: Optional[str] = None
    hierarchy_level: Optional[int] = None
    sort_order: Optional[int] = None


# ============================================================================
# Company Update Model
# ============================================================================

class CompanyUpdate(BaseModel):
    """Request to update company info."""
    name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# Knowledgebase Models
# ============================================================================

class KnowledgebaseDocumentMetadata(BaseModel):
    """Knowledgebase document metadata."""
    id: str
    company_id: str
    filename: str
    content_type: Optional[str] = None
    file_size: int = 0
    text_length: int = 0
    chunk_count: int = 0
    is_active: bool = True
    uploaded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class KnowledgebaseUploadResponse(BaseModel):
    """Response for knowledgebase document upload."""
    company_id: str
    documents: List[KnowledgebaseDocumentMetadata]
    total_text_length: int
    total_chunks: int
    embedding_status: str = "pending"  # 'pending', 'completed', 'failed'


class KnowledgebaseListResponse(BaseModel):
    """Response for listing knowledgebase documents."""
    company_id: str
    total: int
    documents: List[KnowledgebaseDocumentMetadata]
