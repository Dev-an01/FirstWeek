"""
Pydantic models for Embedding Service API
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class ProcessingStatus(str, Enum):
    """Processing status for embedding tasks"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class Priority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class SourceType(str, Enum):
    """Valid source types"""
    DECISION_CASE = "decision_case"
    POLICY = "policy"
    EXECUTIVE_PROFILE = "executive_profile"
    DOCUMENT = "document"


# ============================================================================
# REQUEST MODELS
# ============================================================================

class DocumentRequest(BaseModel):
    """Single document embedding request"""
    
    source_id: str = Field(
        ..., 
        description="Unique identifier for the document",
        examples=["POLICY-HR-001", "DECISION-TECH-042"]
    )
    
    source_type: SourceType = Field(
        ..., 
        description="Type of document",
        examples=[SourceType.POLICY, SourceType.DECISION_CASE]
    )
    
    content: str = Field(
        ..., 
        description="Document content to embed",
        min_length=1,
        max_length=100000
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata for the document"
    )
    
    priority: Priority = Field(
        default=Priority.NORMAL,
        description="Processing priority"
    )
    
    force_update: bool = Field(
        default=False,
        description="Force re-embedding even if content unchanged"
    )
    
    version: Optional[str] = Field(
        default=None,
        description="Document version (for tracking)"
    )

    access_level: Optional[str] = Field(
        default=None,
        description="Access scope: public, internal, executive, confidential"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "source_id": "POLICY-HR-001",
                "source_type": "policy",
                "content": "This is the content of the HR policy document...",
                "metadata": {
                    "title": "HR Policy v2.1",
                    "department": "Human Resources",
                    "effective_date": "2024-01-15"
                },
                "priority": "normal",
                "force_update": False,
                "version": "2.1"
            }
        }


class BatchEmbeddingRequest(BaseModel):
    """Batch embedding request for multiple documents"""
    
    documents: List[DocumentRequest] = Field(
        ..., 
        description="List of documents to embed",
        min_items=1,
        max_items=1000
    )
    
    priority: Priority = Field(
        default=Priority.NORMAL,
        description="Default priority for all documents (can be overridden per document)"
    )
    
    batch_id: Optional[str] = Field(
        default=None,
        description="Optional batch identifier for tracking"
    )
    
    @validator('documents')
    def validate_documents(cls, v):
        if not v:
            raise ValueError("At least one document must be provided")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "documents": [
                    {
                        "source_id": "POLICY-HR-001",
                        "source_type": "policy",
                        "content": "HR policy content...",
                        "priority": "normal"
                    },
                    {
                        "source_id": "DECISION-TECH-042",
                        "source_type": "decision_case",
                        "content": "Technical decision content...",
                        "priority": "high"
                    }
                ],
                "priority": "normal",
                "batch_id": "batch_2024_01_15_001"
            }
        }


class IncrementalUpdateRequest(BaseModel):
    """Request for incremental updates (changed documents only)"""
    
    documents: List[DocumentRequest] = Field(
        ..., 
        description="List of changed documents to update",
        min_items=1,
        max_items=500
    )
    
    change_detection: bool = Field(
        default=True,
        description="Enable automatic change detection"
    )
    
    similarity_threshold: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for change detection"
    )
    
    priority: Priority = Field(
        default=Priority.HIGH,
        description="Priority for incremental updates"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "documents": [
                    {
                        "source_id": "POLICY-HR-001",
                        "source_type": "policy",
                        "content": "Updated HR policy content with new sections...",
                        "version": "2.2"
                    }
                ],
                "change_detection": True,
                "similarity_threshold": 0.95,
                "priority": "high"
            }
        }


class RollbackRequest(BaseModel):
    """Request to rollback to a previous version"""
    
    target_version: str = Field(
        ..., 
        description="Target version to rollback to",
        examples=["v1.0", "2024-01-15-10-30-00"]
    )
    
    source_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific document IDs to rollback (empty = all documents in version)"
    )
    
    confirm: bool = Field(
        default=False,
        description="Confirmation flag for safety"
    )
    
    @validator('confirm')
    def validate_confirmation(cls, v):
        if not v:
            raise ValueError("Rollback must be confirmed by setting confirm=true")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "target_version": "v1.0",
                "source_ids": ["POLICY-HR-001", "DECISION-TECH-042"],
                "confirm": True
            }
        }


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class EmbeddingResult(BaseModel):
    """Result for a single document embedding"""
    
    source_id: str = Field(description="Document ID")
    source_type: SourceType = Field(description="Document type")
    status: ProcessingStatus = Field(description="Processing status")
    embedding_id: Optional[str] = Field(default=None, description="Embedding record ID")
    version: Optional[str] = Field(default=None, description="Document version")
    similarity_score: Optional[float] = Field(default=None, description="Similarity to previous version")
    processing_time_ms: Optional[float] = Field(default=None, description="Processing time in milliseconds")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BatchEmbeddingResponse(BaseModel):
    """Response for batch embedding requests"""
    
    success: bool = Field(description="Overall success status")
    batch_id: Optional[str] = Field(default=None, description="Batch identifier")
    total_documents: int = Field(description="Total documents processed")
    successful: int = Field(description="Number of successful embeddings")
    failed: int = Field(description="Number of failed embeddings")
    results: List[EmbeddingResult] = Field(description="Individual document results")
    processing_time_ms: float = Field(description="Total processing time")
    version: Optional[str] = Field(default=None, description="New version created")
    request_id: str = Field(description="Unique request identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class TaskStatus(BaseModel):
    """Status of an embedding task"""
    
    task_id: str = Field(description="Celery task ID")
    status: ProcessingStatus = Field(description="Current status")
    progress: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Progress percentage")
    current_step: Optional[str] = Field(default=None, description="Current processing step")
    total_documents: Optional[int] = Field(default=None, description="Total documents in task")
    processed_documents: Optional[int] = Field(default=None, description="Documents processed so far")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    created_at: datetime = Field(description="Task creation time")
    started_at: Optional[datetime] = Field(default=None, description="Task start time")
    completed_at: Optional[datetime] = Field(default=None, description="Task completion time")
    estimated_completion: Optional[datetime] = Field(default=None, description="Estimated completion time")


class VersionInfo(BaseModel):
    """Information about an embedding version"""
    
    version: str = Field(description="Version identifier")
    created_at: datetime = Field(description="Version creation time")
    document_count: int = Field(description="Number of documents in version")
    description: Optional[str] = Field(default=None, description="Version description")
    parent_version: Optional[str] = Field(default=None, description="Parent version")
    is_current: bool = Field(description="Whether this is the current version")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Version metadata")


class RollbackResponse(BaseModel):
    """Response for rollback operations"""
    
    success: bool = Field(description="Rollback success status")
    target_version: str = Field(description="Target version rolled back to")
    previous_version: str = Field(description="Version before rollback")
    documents_rolled_back: int = Field(description="Number of documents rolled back")
    rollback_time_ms: float = Field(description="Rollback processing time")
    new_version: str = Field(description="New version created after rollback")
    request_id: str = Field(description="Unique request identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


# ============================================================================
# HEALTH AND METRICS MODELS
# ============================================================================

class ServiceHealth(BaseModel):
    """Service health status"""
    
    status: str = Field(description="Overall service status")
    version: str = Field(description="Service version")
    uptime_seconds: float = Field(description="Service uptime in seconds")
    components: Dict[str, str] = Field(description="Component health statuses")
    queue_size: Optional[int] = Field(default=None, description="Current queue size")
    active_tasks: Optional[int] = Field(default=None, description="Number of active tasks")
    memory_usage_mb: Optional[float] = Field(default=None, description="Memory usage in MB")
    cpu_usage_percent: Optional[float] = Field(default=None, description="CPU usage percentage")


class ProcessingMetrics(BaseModel):
    """Processing performance metrics"""
    
    total_embeddings: int = Field(description="Total embeddings generated")
    successful_embeddings: int = Field(description="Successful embeddings")
    failed_embeddings: int = Field(description="Failed embeddings")
    average_processing_time_ms: float = Field(description="Average processing time")
    embeddings_per_second: float = Field(description="Processing rate")
    queue_size: int = Field(description="Current queue size")
    active_workers: int = Field(description="Number of active workers")
    memory_usage_mb: float = Field(description="Memory usage in MB")
    uptime_hours: float = Field(description="Service uptime in hours")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update time")


# ============================================================================
# ERROR MODELS
# ============================================================================

# ============================================================================
# ASYNC RESPONSE MODELS
# ============================================================================

class AsyncTaskResponse(BaseModel):
    """Response for async task operations"""

    task_id: str = Field(description="Celery task ID")
    status: str = Field(description="Task status (queued, processing, etc.)")
    batch_id: Optional[str] = Field(default=None, description="Batch identifier if applicable")
    total_documents: Optional[int] = Field(default=None, description="Total documents in task")
    message: str = Field(description="Status message")


class ErrorResponse(BaseModel):
    """Standard error response"""

    success: bool = Field(default=False, description="Error flag")
    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    request_id: Optional[str] = Field(default=None, description="Request identifier")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Error timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "ValidationError",
                "message": "Invalid document content",
                "detail": "Content length exceeds maximum allowed",
                "request_id": "req_abc123",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }