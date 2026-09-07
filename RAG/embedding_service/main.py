"""
FastAPI Application for Embedding Service Microservice

Provides REST API endpoints for incremental embedding updates,
version management, and monitoring with queue-based processing.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

# Local imports
from .config import (
    SERVICE_NAME,
    SERVICE_VERSION,
    SERVICE_DESCRIPTION,
    HOST,
    PORT,
    DEBUG,
    CORS_ORIGINS,
    API_CONFIG,
    LOG_LEVEL,
    LOG_FORMAT
)
from .models import (
    DocumentRequest,
    BatchEmbeddingRequest,
    IncrementalUpdateRequest,
    RollbackRequest,
    BatchEmbeddingResponse,
    AsyncTaskResponse,
    TaskStatus,
    VersionInfo,
    RollbackResponse,
    ServiceHealth,
    ProcessingMetrics,
    ErrorResponse
)
from .embedding_service import EmbeddingService
from .version_manager import VersionManager
from .metrics import get_metrics_collector
from .celery_app import (
    process_single_document,
    process_batch_documents,
    process_incremental_update,
    rollback_version,
    get_task_status,
    get_queue_info
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT
)
logger = logging.getLogger(__name__)


# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # STARTUP
    logger.info("=" * 70)
    logger.info(f"STARTING {SERVICE_NAME}")
    logger.info("=" * 70)
    
    try:
        # Initialize services
        app.state.embedding_service = EmbeddingService()
        app.state.version_manager = VersionManager()
        app.state.metrics = get_metrics_collector()
        
        # Store startup time
        app.state.startup_time = time.time()
        
        logger.info("✅ Embedding Service ready")
        logger.info(f"   Listening on http://{HOST}:{PORT}")
        logger.info(f"   Swagger UI: http://{HOST}:{PORT}/docs")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    
    yield  # Server is running
    
    # SHUTDOWN
    logger.info("Shutting down Embedding Service...")
    if hasattr(app.state, 'embedding_service'):
        app.state.embedding_service.close()
    logger.info("✅ Shutdown complete")


# ============================================================================
# FASTAPI APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title=SERVICE_NAME,
    description=SERVICE_DESCRIPTION,
    version=SERVICE_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            message=str(exc),
            request_id=getattr(request.state, 'request_id', None)
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred",
            detail=str(exc) if DEBUG else None,
            request_id=getattr(request.state, 'request_id', None)
        ).dict()
    )


# ============================================================================
# MIDDLEWARE - Request ID and Logging
# ============================================================================

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID and log requests."""
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    
    start_time = time.time()
    logger.info(f"[{request_id}] {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000
    
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} "
        f"→ {response.status_code} ({duration_ms:.1f}ms)"
    )
    
    response.headers["X-Request-ID"] = request_id
    return response


# ============================================================================
# ENDPOINTS - Root and Health
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with service information."""
    return {
        "name": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "description": SERVICE_DESCRIPTION,
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "embeddings": "/embeddings",
            "batch": "/embeddings/batch",
            "incremental": "/embeddings/incremental",
            "version": "/embeddings/version",
            "rollback": "/embeddings/rollback",
            "tasks": "/tasks/{task_id}",
            "metrics": "/metrics",
            "health": "/health"
        }
    }


@app.get("/health", response_model=ServiceHealth, tags=["Health"])
async def health_check(request: Request):
    """Health check endpoint with detailed component status."""
    metrics = request.app.state.metrics
    return metrics.get_health_status()


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics(request: Request):
    """Get current processing metrics."""
    metrics = request.app.state.metrics
    return metrics.get_current_metrics()


@app.get("/metrics/prometheus", tags=["Monitoring"])
async def get_prometheus_metrics(request: Request):
    """Export metrics in Prometheus format."""
    metrics = request.app.state.metrics
    return PlainTextResponse(
        content=metrics.export_prometheus(),
        media_type="text/plain"
    )


@app.get("/alerts", tags=["Monitoring"])
async def get_alerts(request: Request, limit: int = 10):
    """Get recent performance alerts."""
    metrics = request.app.state.metrics
    return {
        "alerts": metrics.get_recent_alerts(limit),
        "total": len(metrics.alerts)
    }


# ============================================================================
# ENDPOINTS - Embedding Operations
# ============================================================================

@app.post("/embeddings/documents", tags=["Embeddings"])
async def embed_single_document(
    request: Request,
    document: DocumentRequest,
    background_tasks: BackgroundTasks,
    async_processing: bool = False
):
    """
    Embed a single document.
    
    Args:
        document: Document to embed
        async_processing: If True, process asynchronously (returns task ID)
    
    Returns:
        EmbeddingResult or task ID for async processing
    """
    try:
        if async_processing:
            # Queue for async processing
            task = process_single_document.delay(
                document.dict(),
                priority=_priority_to_number(document.priority)
            )
            
            return {
                "task_id": task.id,
                "status": "queued",
                "message": "Document queued for processing"
            }
        else:
            # Synchronous processing
            embedding_service = request.app.state.embedding_service
            result = embedding_service.process_single_document(document)
            
            # Record metrics
            request.app.state.metrics.record_embedding_processed(result)
            
            return result.dict()
            
    except Exception as e:
        logger.error(f"Single document embedding failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding failed: {str(e)}"
        )


@app.post("/embeddings/batch", tags=["Embeddings"])
async def embed_batch_documents(
    request: Request,
    batch_request: BatchEmbeddingRequest,
    background_tasks: BackgroundTasks,
    async_processing: bool = True
):
    """
    Embed multiple documents in batch.

    Args:
        batch_request: Batch embedding request
        async_processing: If True, process asynchronously (recommended for large batches)

    Returns:
        AsyncTaskResponse if async_processing=True, BatchEmbeddingResponse if sync
    """
    try:
        if async_processing:
            # Queue for async processing
            task = process_batch_documents.delay(
                [doc.dict() for doc in batch_request.documents],
                batch_request.batch_id,
                priority=_priority_to_number(batch_request.priority)
            )

            return AsyncTaskResponse(
                task_id=task.id,
                status="queued",
                batch_id=batch_request.batch_id,
                total_documents=len(batch_request.documents),
                message="Batch queued for processing"
            ).model_dump()
        else:
            # Synchronous processing (not recommended for large batches)
            embedding_service = request.app.state.embedding_service
            results = embedding_service.process_batch(batch_request.documents)
            
            # Record metrics
            for result in results:
                request.app.state.metrics.record_embedding_processed(result)
            
            # Create version snapshot
            version_manager = request.app.state.version_manager
            version = version_manager.create_snapshot(
                description=f"Batch {batch_request.batch_id or 'manual'}"
            )
            
            successful = sum(1 for r in results if r.status.value == "completed")
            failed = len(results) - successful
            
            return BatchEmbeddingResponse(
                success=failed == 0,
                batch_id=batch_request.batch_id,
                total_documents=len(batch_request.documents),
                successful=successful,
                failed=failed,
                results=results,
                processing_time_ms=0,  # Would be calculated in real implementation
                version=version,
                request_id=request.state.request_id
            ).dict()
            
    except Exception as e:
        logger.error(f"Batch embedding failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch embedding failed: {str(e)}"
        )


@app.post("/embeddings/incremental", tags=["Embeddings"])
async def incremental_update(
    request: Request,
    update_request: IncrementalUpdateRequest
):
    """
    Process incremental updates with change detection.
    
    Args:
        update_request: Incremental update request
    
    Returns:
        Task ID for async processing
    """
    try:
        # Queue for async processing (always async for incremental updates)
        task = process_incremental_update.delay(
            [doc.dict() for doc in update_request.documents],
            update_request.similarity_threshold,
            priority=_priority_to_number(update_request.priority)
        )
        
        return {
            "task_id": task.id,
            "status": "queued",
            "total_documents": len(update_request.documents),
            "similarity_threshold": update_request.similarity_threshold,
            "message": "Incremental update queued for processing"
        }
        
    except Exception as e:
        logger.error(f"Incremental update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Incremental update failed: {str(e)}"
        )


# ============================================================================
# ENDPOINTS - Version Management
# ============================================================================

@app.get("/embeddings/version", response_model=List[VersionInfo], tags=["Version Management"])
async def get_version_history(request: Request, limit: int = 20):
    """Get version history."""
    try:
        version_manager = request.app.state.version_manager
        history = version_manager.get_version_history(limit)
        
        return [version.dict() for version in history]
        
    except Exception as e:
        logger.error(f"Failed to get version history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get version history: {str(e)}"
        )


@app.get("/embeddings/version/current", tags=["Version Management"])
async def get_current_version(request: Request):
    """Get current version information."""
    try:
        version_manager = request.app.state.version_manager
        current_version = version_manager.get_current_version()
        
        if not current_version:
            return {"current_version": None, "message": "No versions found"}
        
        version_info = version_manager.get_version_info(current_version)
        return version_info.dict() if version_info else {"current_version": current_version}
        
    except Exception as e:
        logger.error(f"Failed to get current version: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get current version: {str(e)}"
        )


@app.post("/embeddings/version/snapshot", tags=["Version Management"])
async def create_version_snapshot(
    request: Request,
    description: str = ""
):
    """Create a manual version snapshot."""
    try:
        version_manager = request.app.state.version_manager
        version = version_manager.create_snapshot(description=description)
        
        return {
            "version": version,
            "message": "Version snapshot created successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to create version snapshot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create version snapshot: {str(e)}"
        )


@app.post("/embeddings/rollback", tags=["Version Management"])
async def rollback_to_version(
    request: Request,
    rollback_request: RollbackRequest
):
    """
    Rollback to a previous version.

    Args:
        rollback_request: Rollback request with target version

    Returns:
        AsyncTaskResponse (rollback is always async)
    """
    try:
        # Queue for async processing (always async for rollbacks)
        task = rollback_version.delay(
            rollback_request.target_version,
            rollback_request.source_ids,
            rollback_request.confirm
        )

        return {
            "task_id": task.id,
            "status": "queued",
            "target_version": rollback_request.target_version,
            "message": "Rollback queued for processing"
        }
        
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback failed: {str(e)}"
        )


# ============================================================================
# ENDPOINTS - Task Management
# ============================================================================

@app.get("/tasks/{task_id}", tags=["Task Management"])
async def get_task_status_endpoint(task_id: str):
    """Get status of a specific task."""
    try:
        task_status = get_task_status(task_id)
        
        if 'error' in task_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}"
            )
        
        return task_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )


@app.delete("/tasks/{task_id}", tags=["Task Management"])
async def cancel_task(task_id: str, terminate: bool = False):
    """Cancel or terminate a task."""
    try:
        from .celery_app import cancel_task
        success = cancel_task(task_id, terminate)
        
        if success:
            return {
                "task_id": task_id,
                "cancelled": True,
                "terminated": terminate,
                "message": f"Task {task_id} cancelled successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found or already completed: {task_id}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )


@app.get("/tasks", tags=["Task Management"])
async def get_queue_status():
    """Get queue and task status information."""
    try:
        queue_info = get_queue_info()
        return queue_info
        
    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue status: {str(e)}"
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _priority_to_number(priority) -> int:
    """Convert priority enum to number for Celery."""
    priority_map = {
        "low": 2,
        "normal": 5,
        "high": 8,
        "critical": 10
    }
    return priority_map.get(priority.value if hasattr(priority, 'value') else priority, 5)


# ============================================================================
# RUN SERVER (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "embedding_service.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info"
    )