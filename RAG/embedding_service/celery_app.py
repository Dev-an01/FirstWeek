"""
Celery Application for Queue-based Embedding Processing

Handles asynchronous embedding tasks with priority queues,
retry mechanisms, and progress tracking.
"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import Celery, Task
from celery.exceptions import Retry

# Local imports
from .config import CELERY_CONFIG, QUEUES, PROCESSING_CONFIG
from .models import (
    DocumentRequest,
    EmbeddingResult,
    ProcessingStatus,
    Priority
)
from .embedding_service import EmbeddingService
from .version_manager import VersionManager
from .metrics import MetricsCollector

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery('embedding_service')
celery_app.config_from_object(CELERY_CONFIG)

# Configure queues
celery_app.conf.task_routes = {
    'embedding_service.tasks.process_single_document': {'queue': QUEUES['high_priority']},
    'embedding_service.tasks.process_batch_documents': {'queue': QUEUES['batch_processing']},
    'embedding_service.tasks.process_incremental_update': {'queue': QUEUES['high_priority']},
    'embedding_service.tasks.rollback_version': {'queue': QUEUES['high_priority']},
}

# Configure task priorities
celery_app.conf.task_default_priority = 5
celery_app.conf.worker_prefetch_multiplier = 1


class EmbeddingTask(Task):
    """Base task class for embedding operations with error handling."""
    
    def __init__(self):
        self.embedding_service = None
        self.version_manager = None
        self.metrics = None
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {task_id} completed successfully")
        if self.metrics:
            self.metrics.record_task_success(task_id, retval)
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}")
        if self.metrics:
            self.metrics.record_task_failure(task_id, exc)
        
        # Retry logic for specific exceptions
        if isinstance(exc, (ConnectionError, TimeoutError)):
            raise Retry(exc, countdown=PROCESSING_CONFIG['retry_delay_seconds'])
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Task {task_id} retrying: {exc}")
    
    def get_services(self):
        """Lazy initialization of services."""
        if not self.embedding_service:
            self.embedding_service = EmbeddingService()
        if not self.version_manager:
            self.version_manager = VersionManager()
        if not self.metrics:
            self.metrics = MetricsCollector()
        return self.embedding_service, self.version_manager, self.metrics


# Register base task
celery_app.Task = EmbeddingTask


@celery_app.task(bind=True, name='embedding_service.tasks.process_single_document')
def process_single_document(self, document_data: Dict[str, Any], priority: int = 5):
    """
    Process a single document asynchronously.
    
    Args:
        document_data: Document request data as dict
        priority: Task priority (1-10, higher = more important)
    
    Returns:
        EmbeddingResult dict
    """
    task_id = self.request.id
    logger.info(f"Processing single document task: {task_id}")
    
    try:
        # Get services
        embedding_service, version_manager, metrics = self.get_services()
        
        # Convert dict to DocumentRequest
        document = DocumentRequest(**document_data)
        
        # Update task state
        self.update_state(
            state='PROCESSING',
            meta={'current_step': 'validating_document', 'progress': 10}
        )
        
        # Process document
        result = embedding_service.process_single_document(document)
        
        # Update task state
        self.update_state(
            state='PROCESSING',
            meta={'current_step': 'completed', 'progress': 100}
        )
        
        # Record metrics
        if metrics:
            metrics.record_embedding_processed(result)
        
        return result.dict()
        
    except Exception as e:
        logger.error(f"Single document processing failed: {e}")
        raise


@celery_app.task(bind=True, name='embedding_service.tasks.process_batch_documents')
def process_batch_documents(
    self,
    documents_data: List[Dict[str, Any]],
    batch_id: Optional[str] = None,
    priority: int = 5
):
    """
    Process multiple documents in batch asynchronously.
    
    Args:
        documents_data: List of document request data as dicts
        batch_id: Optional batch identifier for tracking
        priority: Task priority
    
    Returns:
        Dict with batch results
    """
    task_id = self.request.id
    batch_id = batch_id or f"batch_{task_id[:8]}"
    total_docs = len(documents_data)
    
    logger.info(f"Processing batch task: {task_id} ({total_docs} documents)")
    
    try:
        # Get services
        embedding_service, version_manager, metrics = self.get_services()
        
        # Convert dicts to DocumentRequest objects
        documents = [DocumentRequest(**doc_data) for doc_data in documents_data]
        
        # Initialize progress tracking
        processed_count = 0
        results = []
        
        # Process in sub-batches
        batch_size = PROCESSING_CONFIG['batch_processing_size']
        for i in range(0, len(documents), batch_size):
            sub_batch = documents[i:i + batch_size]
            
            # Update progress
            progress = int((i / total_docs) * 100)
            self.update_state(
                state='PROCESSING',
                meta={
                    'current_step': f'processing_subbatch_{i//batch_size + 1}',
                    'progress': progress,
                    'processed_documents': processed_count,
                    'total_documents': total_docs
                }
            )
            
            # Process sub-batch
            sub_results = embedding_service.process_batch(sub_batch)
            results.extend(sub_results)
            processed_count += len(sub_results)
            
            # Record metrics
            if metrics:
                for result in sub_results:
                    metrics.record_embedding_processed(result)
        
        # Create version snapshot for batch
        version = version_manager.create_snapshot(
            description=f"Batch {batch_id} - {processed_count} documents"
        )
        
        # Final progress update
        self.update_state(
            state='PROCESSING',
            meta={
                'current_step': 'completed',
                'progress': 100,
                'processed_documents': processed_count,
                'total_documents': total_docs
            }
        )
        
        # Calculate batch statistics
        successful = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
        failed = len(results) - successful
        
        return {
            'batch_id': batch_id,
            'task_id': task_id,
            'total_documents': total_docs,
            'successful': successful,
            'failed': failed,
            'results': [r.dict() for r in results],
            'version': version,
            'processing_time_ms': time.time() * 1000  # Will be updated by caller
        }
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise


@celery_app.task(bind=True, name='embedding_service.tasks.process_incremental_update')
def process_incremental_update(
    self,
    documents_data: List[Dict[str, Any]],
    similarity_threshold: float = 0.95,
    priority: int = 8  # Higher priority for incremental updates
):
    """
    Process incremental updates with change detection.
    
    Args:
        documents_data: List of changed document data
        similarity_threshold: Threshold for change detection
        priority: Task priority
    
    Returns:
        Dict with incremental update results
    """
    task_id = self.request.id
    total_docs = len(documents_data)
    
    logger.info(f"Processing incremental update task: {task_id} ({total_docs} documents)")
    
    try:
        # Get services
        embedding_service, version_manager, metrics = self.get_services()
        
        # Convert dicts to DocumentRequest objects
        documents = [DocumentRequest(**doc_data) for doc_data in documents_data]
        
        # Initialize tracking
        processed_count = 0
        changed_count = 0
        unchanged_count = 0
        results = []
        
        # Process each document with change detection
        for i, document in enumerate(documents):
            # Update progress
            progress = int((i / total_docs) * 100)
            self.update_state(
                state='PROCESSING',
                meta={
                    'current_step': f'processing_document_{i + 1}',
                    'progress': progress,
                    'processed_documents': processed_count,
                    'changed_documents': changed_count,
                    'unchanged_documents': unchanged_count,
                    'total_documents': total_docs
                }
            )
            
            # Process with change detection
            result = embedding_service.process_single_document(
                document, 
                detect_changes=True
            )
            results.append(result)
            processed_count += 1
            
            # Track changes
            if result.metadata and result.metadata.get('skipped') == 'no_changes':
                unchanged_count += 1
            else:
                changed_count += 1
            
            # Record metrics
            if metrics:
                metrics.record_incremental_update(result)
        
        # Create version snapshot for incremental update
        version = version_manager.create_snapshot(
            description=f"Incremental update - {changed_count} changed, {unchanged_count} unchanged"
        )
        
        # Final progress update
        self.update_state(
            state='PROCESSING',
            meta={
                'current_step': 'completed',
                'progress': 100,
                'processed_documents': processed_count,
                'changed_documents': changed_count,
                'unchanged_documents': unchanged_count,
                'total_documents': total_docs
            }
        )
        
        # Calculate statistics
        successful = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
        failed = len(results) - successful
        
        return {
            'task_id': task_id,
            'total_documents': total_docs,
            'processed_documents': processed_count,
            'changed_documents': changed_count,
            'unchanged_documents': unchanged_count,
            'successful': successful,
            'failed': failed,
            'results': [r.dict() for r in results],
            'version': version,
            'similarity_threshold': similarity_threshold,
            'processing_time_ms': time.time() * 1000  # Will be updated by caller
        }
        
    except Exception as e:
        logger.error(f"Incremental update failed: {e}")
        raise


@celery_app.task(bind=True, name='embedding_service.tasks.rollback_version')
def rollback_version(
    self,
    target_version: str,
    source_ids: Optional[List[str]] = None,
    confirm: bool = False,
    priority: int = 10  # Highest priority for rollbacks
):
    """
    Rollback to a previous version.
    
    Args:
        target_version: Target version to rollback to
        source_ids: Specific document IDs to rollback (None = all)
        confirm: Confirmation flag for safety
    
    Returns:
        Dict with rollback results
    """
    task_id = self.request.id
    
    if not confirm:
        raise ValueError("Rollback must be confirmed")
    
    logger.info(f"Processing rollback task: {task_id} (version: {target_version})")
    
    try:
        # Get services
        embedding_service, version_manager, metrics = self.get_services()
        
        # Update progress
        self.update_state(
            state='PROCESSING',
            meta={'current_step': 'validating_rollback', 'progress': 10}
        )
        
        # Perform rollback
        rollback_result = version_manager.rollback_to_version(
            target_version=target_version,
            source_ids=source_ids
        )
        
        # Update progress
        self.update_state(
            state='PROCESSING',
            meta={'current_step': 'completed', 'progress': 100}
        )
        
        # Record metrics
        if metrics:
            metrics.record_rollback(rollback_result)
        
        return rollback_result.dict()
        
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise


@celery_app.task(bind=True, name='embedding_service.tasks.cleanup_old_versions')
def cleanup_old_versions(self):
    """
    Clean up expired versions periodically.
    
    Returns:
        Dict with cleanup results
    """
    task_id = self.request.id
    
    logger.info(f"Processing cleanup task: {task_id}")
    
    try:
        # Get services
        embedding_service, version_manager, metrics = self.get_services()
        
        # Update progress
        self.update_state(
            state='PROCESSING',
            meta={'current_step': 'cleaning_versions', 'progress': 50}
        )
        
        # Perform cleanup
        cleanup_result = version_manager.cleanup_expired_versions()
        
        # Update progress
        self.update_state(
            state='PROCESSING',
            meta={'current_step': 'completed', 'progress': 100}
        )
        
        # Record metrics
        if metrics:
            metrics.record_cleanup(cleanup_result)
        
        return cleanup_result
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise


# ============================================================================
# TASK MANAGEMENT UTILITIES
# ============================================================================

def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a Celery task."""
    try:
        result = celery_app.AsyncResult(task_id)
        
        status = {
            'task_id': task_id,
            'state': result.state,
            'result': result.result if result.ready() else None,
            'traceback': result.traceback if result.failed() else None,
            'date_done': result.date_done,
        }
        
        # Add progress info if available
        if result.info:
            status.update(result.info)
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        return {'task_id': task_id, 'error': str(e)}


def cancel_task(task_id: str, terminate: bool = False) -> bool:
    """Cancel or terminate a Celery task."""
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        logger.info(f"Task {task_id} cancelled (terminate={terminate})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        return False


def get_queue_info() -> Dict[str, Any]:
    """Get information about active queues and tasks."""
    try:
        inspect = celery_app.control.inspect()
        
        # Get active tasks
        active_tasks = inspect.active()
        scheduled_tasks = inspect.scheduled()
        reserved_tasks = inspect.reserved()
        
        # Get queue lengths (requires Redis)
        queue_lengths = {}
        try:
            from celery.backends.redis import RedisBackend
            backend = RedisBackend(app=celery_app)
            client = backend.client
            
            for queue_name in QUEUES.values():
                queue_lengths[queue_name] = client.llen(queue_name)
                
        except Exception as e:
            logger.warning(f"Failed to get queue lengths: {e}")
        
        return {
            'active_tasks': active_tasks,
            'scheduled_tasks': scheduled_tasks,
            'reserved_tasks': reserved_tasks,
            'queue_lengths': queue_lengths,
            'total_active': sum(len(tasks) for tasks in (active_tasks or {}).values()),
        }
        
    except Exception as e:
        logger.error(f"Failed to get queue info: {e}")
        return {'error': str(e)}


# Configure periodic tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'cleanup-old-versions': {
        'task': 'embedding_service.tasks.cleanup_old_versions',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'options': {'queue': QUEUES['low_priority']}
    },
}