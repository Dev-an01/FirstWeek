"""
Metrics Collection and Monitoring for Embedding Service

Tracks performance metrics, health indicators, and operational
statistics with support for Prometheus export and alerting.
"""

import logging
import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
import json

# Local imports
from .config import (
    METRICS_CONFIG,
    PERFORMANCE_THRESHOLDS,
    HEALTH_CHECK,
    REDIS_CONFIG
)
from .models import (
    ProcessingMetrics,
    ServiceHealth,
    EmbeddingResult,
    ProcessingStatus
)

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and manages metrics for the embedding service.
    
    Features:
    - Real-time performance metrics
    - Health monitoring with alerts
    - Prometheus-compatible export
    - Historical data retention
    - Thread-safe operations
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        logger.info("Initializing MetricsCollector...")
        
        # Metrics storage
        self.metrics = defaultdict(float)
        self.counters = defaultdict(int)
        self.histograms = defaultdict(lambda: deque(maxlen=1000))
        self.alerts = deque(maxlen=100)
        
        # Timing data
        self.start_time = time.time()
        self.last_update = time.time()
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Initialize system metrics
        self._init_system_metrics()
        
        logger.info("✅ MetricsCollector initialized successfully")
    
    def _init_system_metrics(self):
        """Initialize system monitoring."""
        try:
            # Initial system metrics
            self.metrics['system_memory_total_mb'] = psutil.virtual_memory().total / (1024 * 1024)
            self.metrics['system_cpu_count'] = psutil.cpu_count()
            
        except Exception as e:
            logger.warning(f"Failed to initialize system metrics: {e}")
    
    def record_embedding_processed(self, result: EmbeddingResult):
        """Record metrics for a processed embedding."""
        with self.lock:
            # Update counters
            self.counters['total_embeddings'] += 1
            
            if result.status == ProcessingStatus.COMPLETED:
                self.counters['successful_embeddings'] += 1
            else:
                self.counters['failed_embeddings'] += 1
            
            # Record processing time
            if result.processing_time_ms:
                self.histograms['embedding_processing_time_ms'].append(result.processing_time_ms)
                self.metrics['average_processing_time_ms'] = (
                    sum(self.histograms['embedding_processing_time_ms']) / 
                    len(self.histograms['embedding_processing_time_ms'])
                )
            
            # Record similarity scores
            if result.similarity_score is not None:
                self.histograms['similarity_scores'].append(result.similarity_score)
                self.metrics['average_similarity_score'] = (
                    sum(self.histograms['similarity_scores']) / 
                    len(self.histograms['similarity_scores'])
                )
            
            # Check performance thresholds
            self._check_performance_thresholds(result)
            
            self.last_update = time.time()
    
    def record_incremental_update(self, result: EmbeddingResult):
        """Record metrics for incremental update."""
        with self.lock:
            self.counters['incremental_updates'] += 1
            
            if result.metadata and result.metadata.get('skipped') == 'no_changes':
                self.counters['unchanged_documents'] += 1
            else:
                self.counters['changed_documents'] += 1
            
            self.last_update = time.time()
    
    def record_task_success(self, task_id: str, result: Any):
        """Record successful task completion."""
        with self.lock:
            self.counters['successful_tasks'] += 1
            self.metrics['last_successful_task'] = task_id
            self.last_update = time.time()
    
    def record_task_failure(self, task_id: str, error: Exception):
        """Record task failure."""
        with self.lock:
            self.counters['failed_tasks'] += 1
            self.metrics['last_failed_task'] = task_id
            self.histograms['task_errors'].append(str(error))
            self.last_update = time.time()
    
    def record_rollback(self, rollback_result: Dict[str, Any]):
        """Record rollback operation metrics."""
        with self.lock:
            self.counters['rollback_operations'] += 1
            if rollback_result.get('success'):
                self.counters['successful_rollbacks'] += 1
            else:
                self.counters['failed_rollbacks'] += 1
            
            if rollback_result.get('documents_rolled_back'):
                self.counters['documents_rolled_back'] += rollback_result['documents_rolled_back']
            
            self.last_update = time.time()
    
    def record_cleanup(self, cleanup_result: Dict[str, Any]):
        """Record cleanup operation metrics."""
        with self.lock:
            self.counters['cleanup_operations'] += 1
            if cleanup_result.get('success'):
                self.counters['successful_cleanups'] += 1
            else:
                self.counters['failed_cleanups'] += 1
            
            self.last_update = time.time()
    
    def _check_performance_thresholds(self, result: EmbeddingResult):
        """Check if performance thresholds are exceeded and create alerts."""
        alerts = []
        
        # Check processing time
        if (result.processing_time_ms and 
            result.processing_time_ms > PERFORMANCE_THRESHOLDS['embedding_generation_time_ms']):
            alerts.append({
                'type': 'performance',
                'metric': 'embedding_generation_time_ms',
                'value': result.processing_time_ms,
                'threshold': PERFORMANCE_THRESHOLDS['embedding_generation_time_ms'],
                'source_id': result.source_id,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Check memory usage
        memory_usage = self.get_memory_usage()
        if memory_usage > PERFORMANCE_THRESHOLDS['memory_usage_percent']:
            alerts.append({
                'type': 'resource',
                'metric': 'memory_usage_percent',
                'value': memory_usage,
                'threshold': PERFORMANCE_THRESHOLDS['memory_usage_percent'],
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Add alerts to queue
        for alert in alerts:
            self.alerts.append(alert)
            logger.warning(f"Performance alert: {alert}")
    
    def get_current_metrics(self) -> ProcessingMetrics:
        """Get current processing metrics."""
        with self.lock:
            # Calculate rates
            uptime_hours = (time.time() - self.start_time) / 3600
            embeddings_per_second = (
                self.counters['total_embeddings'] / (time.time() - self.start_time)
                if self.counters['total_embeddings'] > 0 else 0
            )
            
            # Get system metrics
            memory_usage = self.get_memory_usage()
            cpu_usage = self.get_cpu_usage()
            
            # Get queue info (if available)
            queue_size = self.get_queue_size()
            active_workers = self.get_active_workers()
            
            return ProcessingMetrics(
                total_embeddings=self.counters['total_embeddings'],
                successful_embeddings=self.counters['successful_embeddings'],
                failed_embeddings=self.counters['failed_embeddings'],
                average_processing_time_ms=self.metrics.get('average_processing_time_ms', 0.0),
                embeddings_per_second=embeddings_per_second,
                queue_size=queue_size,
                active_workers=active_workers,
                memory_usage_mb=memory_usage * psutil.virtual_memory().total / (1024 * 1024) / 100,
                uptime_hours=uptime_hours,
                last_updated=datetime.utcnow()
            )
    
    def get_health_status(self) -> ServiceHealth:
        """Get overall service health status."""
        with self.lock:
            # Determine overall status
            status = "healthy"
            components = {}
            
            # Check embedding service
            if self.counters['failed_embeddings'] > self.counters['successful_embeddings']:
                status = "degraded"
                components['embedding_service'] = "degraded"
            else:
                components['embedding_service'] = "healthy"
            
            # Check system resources
            memory_usage = self.get_memory_usage()
            if memory_usage > PERFORMANCE_THRESHOLDS['memory_usage_percent']:
                status = "unhealthy"
                components['memory'] = "critical"
            elif memory_usage > PERFORMANCE_THRESHOLDS['memory_usage_percent'] * 0.8:
                components['memory'] = "warning"
            else:
                components['memory'] = "healthy"
            
            # Check queue health
            queue_size = self.get_queue_size()
            if queue_size > HEALTH_CHECK['max_queue_size']:
                status = "degraded"
                components['queue'] = "warning"
            else:
                components['queue'] = "healthy"
            
            # Check processing time
            avg_time = self.metrics.get('average_processing_time_ms', 0)
            if avg_time > PERFORMANCE_THRESHOLDS['embedding_generation_time_ms']:
                status = "degraded"
                components['performance'] = "warning"
            else:
                components['performance'] = "healthy"
            
            return ServiceHealth(
                status=status,
                version="1.0.0",  # From config
                uptime_seconds=time.time() - self.start_time,
                components=components,
                queue_size=queue_size,
                active_tasks=self.get_active_workers(),
                memory_usage_mb=memory_usage * psutil.virtual_memory().total / (1024 * 1024) / 100,
                cpu_usage_percent=self.get_cpu_usage()
            )
    
    def get_memory_usage(self) -> float:
        """Get current memory usage percentage."""
        try:
            return psutil.virtual_memory().percent
        except Exception:
            return 0.0
    
    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        try:
            return psutil.cpu_percent(interval=1)
        except Exception:
            return 0.0
    
    def get_queue_size(self) -> Optional[int]:
        """Get current queue size from Redis."""
        try:
            import redis
            client = redis.Redis(**REDIS_CONFIG)
            
            # Get sizes of all queues
            total_size = 0
            for queue_name in ['embedding.high', 'embedding.normal', 'embedding.low', 'embedding.batch']:
                total_size += client.llen(queue_name)
            
            return total_size
            
        except Exception as e:
            logger.debug(f"Failed to get queue size: {e}")
            return None
    
    def get_active_workers(self) -> Optional[int]:
        """Get number of active Celery workers."""
        try:
            from .celery_app import celery_app
            inspect = celery_app.control.inspect()
            active = inspect.active()
            
            if active:
                return sum(len(tasks) for tasks in active.values())
            return 0
            
        except Exception as e:
            logger.debug(f"Failed to get active workers: {e}")
            return None
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        with self.lock:
            metrics = []
            
            # Counter metrics
            metrics.append(f"# TYPE embedding_total counter")
            metrics.append(f"embedding_total {self.counters['total_embeddings']}")
            
            metrics.append(f"# TYPE embedding_successful counter")
            metrics.append(f"embedding_successful {self.counters['successful_embeddings']}")
            
            metrics.append(f"# TYPE embedding_failed counter")
            metrics.append(f"embedding_failed {self.counters['failed_embeddings']}")
            
            metrics.append(f"# TYPE incremental_updates counter")
            metrics.append(f"incremental_updates {self.counters['incremental_updates']}")
            
            # Gauge metrics
            metrics.append(f"# TYPE embedding_processing_time_ms gauge")
            metrics.append(f"embedding_processing_time_ms {self.metrics.get('average_processing_time_ms', 0)}")
            
            metrics.append(f"# TYPE memory_usage_percent gauge")
            metrics.append(f"memory_usage_percent {self.get_memory_usage()}")
            
            metrics.append(f"# TYPE cpu_usage_percent gauge")
            metrics.append(f"cpu_usage_percent {self.get_cpu_usage()}")
            
            metrics.append(f"# TYPE queue_size gauge")
            queue_size = self.get_queue_size()
            if queue_size is not None:
                metrics.append(f"queue_size {queue_size}")
            
            metrics.append(f"# TYPE active_workers gauge")
            active_workers = self.get_active_workers()
            if active_workers is not None:
                metrics.append(f"active_workers {active_workers}")
            
            # Histogram metrics (simplified)
            if self.histograms['embedding_processing_time_ms']:
                times = list(self.histograms['embedding_processing_time_ms'])
                if times:
                    metrics.append(f"# TYPE embedding_processing_time_ms histogram")
                    metrics.append(f"embedding_processing_time_ms_sum {sum(times)}")
                    metrics.append(f"embedding_processing_time_ms_count {len(times)}")
            
            return '\n'.join(metrics)
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        with self.lock:
            return list(self.alerts)[-limit:]
    
    def reset_metrics(self):
        """Reset all metrics (for testing)."""
        with self.lock:
            self.metrics.clear()
            self.counters.clear()
            self.histograms.clear()
            self.alerts.clear()
            self.start_time = time.time()
            self.last_update = time.time()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a comprehensive metrics summary."""
        with self.lock:
            return {
                'counters': dict(self.counters),
                'metrics': dict(self.metrics),
                'histogram_sizes': {
                    name: len(values) for name, values in self.histograms.items()
                },
                'recent_alerts': len(self.alerts),
                'uptime_seconds': time.time() - self.start_time,
                'last_update': self.last_update,
                'collection_enabled': METRICS_CONFIG['enabled']
            }


# Global metrics instance
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def record_embedding_processed(result: EmbeddingResult):
    """Convenience function to record embedding metrics."""
    collector = get_metrics_collector()
    collector.record_embedding_processed(result)


def record_task_success(task_id: str, result: Any):
    """Convenience function to record task success."""
    collector = get_metrics_collector()
    collector.record_task_success(task_id, result)


def record_task_failure(task_id: str, error: Exception):
    """Convenience function to record task failure."""
    collector = get_metrics_collector()
    collector.record_task_failure(task_id, error)