"""
Configuration for Embedding Service Microservice
"""

import os
from pathlib import Path
from typing import Dict, Any, List

# Load environment variables from .env file (look in project root for consolidated config)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

# ============================================================================
# SERVICE CONFIGURATION
# ============================================================================

# FastAPI Service
SERVICE_NAME = "Embedding Service"
SERVICE_VERSION = "1.0.0"
SERVICE_DESCRIPTION = "Incremental Embedding Update Microservice"
HOST = os.getenv("EMBEDDING_SERVICE_HOST", "0.0.0.0")
PORT = int(os.getenv("EMBEDDING_SERVICE_PORT", "8001"))
DEBUG = os.getenv("EMBEDDING_SERVICE_DEBUG", "false").lower() == "true"

# ============================================================================
# DATABASE CONFIGURATION (reused from main RAG)
# ============================================================================

# PostgreSQL Configuration
POSTGRES_CONFIG = {
    'database': os.getenv('POSTGRES_DB', 'ai_officer_dev'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', '1234'),
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432'))
}

# Neo4j Configuration
NEO4J_CONFIG = {
    'uri': os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    'user': os.getenv('NEO4J_USER', 'neo4j'),
    'password': os.getenv('NEO4J_PASSWORD', 'neo4j123')
}

# ============================================================================
# EMBEDDING MODEL CONFIGURATION
# ============================================================================

# Model settings (reuse from embedding_generation)
# MIGRATED: From English-only all-mpnet-base-v2 (768d) to multilingual BAAI/bge-m3 (1024d)
# BGE-M3 supports 100+ languages including Japanese + English
MODEL_NAME = 'BAAI/bge-m3'
EMBEDDING_DIMENSION = 1024
DEVICE = 'cuda'  # Use GPU if available
BATCH_SIZE = 32  # Optimized for incremental processing
NORMALIZE_EMBEDDINGS = True

# ============================================================================
# QUEUE CONFIGURATION (Redis/Celery)
# ============================================================================

# Redis Configuration
REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', '6379')),
    'db': int(os.getenv('REDIS_DB', '1')),  # Use different DB for queue
    'password': os.getenv('REDIS_PASSWORD'),
    'decode_responses': True,
    'socket_timeout': 30,
    'socket_connect_timeout': 30,
}

# Celery Configuration - build URL with password if provided
_redis_auth = f":{REDIS_CONFIG['password']}@" if REDIS_CONFIG.get('password') else ""
_redis_broker_url = f"redis://{_redis_auth}{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/{REDIS_CONFIG['db']}"

CELERY_CONFIG = {
    'broker_url': _redis_broker_url,
    'result_backend': _redis_broker_url,
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'timezone': 'UTC',
    'enable_utc': True,
    'task_track_started': True,
    'task_time_limit': 300,  # 5 minutes per task
    'task_soft_time_limit': 240,  # 4 minutes soft limit
    'worker_prefetch_multiplier': 1,
    'worker_max_tasks_per_child': 50,
}

# Queue names
QUEUES = {
    'high_priority': 'embedding.high',
    'normal_priority': 'embedding.normal',
    'low_priority': 'embedding.low',
    'batch_processing': 'embedding.batch',
}

# ============================================================================
# VERSION MANAGEMENT
# ============================================================================

# Version control settings
VERSION_TABLE = 'embedding_versions'
VERSION_RETENTION_DAYS = 30  # Keep versions for 30 days
MAX_VERSIONS_PER_DOCUMENT = 10  # Maximum versions to keep per document

# Rollback settings
ROLLBACK_TIMEOUT_SECONDS = 60  # Max time for rollback operation
ROLLBACK_BATCH_SIZE = 100  # Documents per rollback batch

# ============================================================================
# INCREMENTAL PROCESSING
# ============================================================================

# Change detection
CHANGE_DETECTION = {
    'content_similarity_threshold': 0.95,  # Similarity below this indicates significant change
    'min_content_length': 50,  # Minimum content length to process
    'max_content_length': 100000,  # Maximum content length
    'chunk_size': 1000,  # Text chunking size for large documents
    'chunk_overlap': 200,  # Overlap between chunks
}

# Processing settings
PROCESSING_CONFIG = {
    'max_concurrent_tasks': 5,  # Maximum concurrent embedding tasks
    'retry_attempts': 3,  # Number of retry attempts for failed tasks
    'retry_delay_seconds': 5,  # Delay between retries
    'batch_processing_size': 50,  # Documents per batch
    'progress_update_interval': 10,  # Update progress every N documents
}

# ============================================================================
# MONITORING AND METRICS
# ============================================================================

# Metrics collection
METRICS_CONFIG = {
    'enabled': True,
    'collection_interval': 60,  # Seconds
    'retention_days': 7,  # Keep metrics for 7 days
    'export_format': 'prometheus',  # prometheus, json, or both
}

# Health check settings
HEALTH_CHECK = {
    'timeout_seconds': 10,
    'max_queue_size': 1000,  # Alert if queue exceeds this size
    'max_processing_time_minutes': 30,  # Alert if processing takes too long
}

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    'embedding_generation_time_ms': 5000,  # Max time for single embedding
    'batch_processing_time_ms': 30000,  # Max time for batch processing
    'queue_processing_delay_ms': 10000,  # Max acceptable queue delay
    'memory_usage_percent': 80,  # Max memory usage before alert
}

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = os.getenv('EMBEDDING_SERVICE_LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
LOG_FILE = 'embedding_service.log'
LOG_TO_CONSOLE = True
LOG_TO_FILE = True

# ============================================================================
# API CONFIGURATION
# ============================================================================

# API settings
API_CONFIG = {
    'max_request_size_mb': 100,  # Maximum request size
    'max_batch_size': 1000,  # Maximum documents per batch request
    'request_timeout_seconds': 300,  # 5 minutes
    'rate_limit_per_minute': 60,  # Rate limit per IP
}

# CORS settings
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5173",
    "http://localhost:8000",  # Main RAG API
]

# ============================================================================
# INTEGRATION CONFIGURATION
# ============================================================================

# Main RAG API integration
RAG_API_CONFIG = {
    'base_url': os.getenv('RAG_API_URL', 'http://localhost:8000'),
    'timeout_seconds': 30,
    'retry_attempts': 3,
}

# Webhook configuration for notifications
WEBHOOK_CONFIG = {
    'enabled': False,
    'url': os.getenv('EMBEDDING_WEBHOOK_URL', ''),
    'timeout_seconds': 10,
    'retry_attempts': 3,
}

# ============================================================================
# VALID SOURCE TYPES
# ============================================================================

VALID_SOURCE_TYPES = ['decision_case', 'policy', 'executive_profile']
SOURCE_TYPE_MAPPING = {
    'decision': 'decision_case',
    'decisions': 'decision_case',
    'policy': 'policy',
    'policies': 'policy',
    'policy_document': 'policy',
    'profile': 'executive_profile',
    'profiles': 'executive_profile',
    'executive': 'executive_profile',
    'executives': 'executive_profile',
}

# ============================================================================
# ENVIRONMENT-SPECIFIC SETTINGS
# ============================================================================

# Development overrides
if DEBUG:
    LOG_LEVEL = 'DEBUG'
    METRICS_CONFIG['enabled'] = False
    PROCESSING_CONFIG['max_concurrent_tasks'] = 2

# Production overrides
if os.getenv('ENVIRONMENT', 'development') == 'production':
    DEBUG = False
    LOG_LEVEL = 'WARNING'
    METRICS_CONFIG['enabled'] = True
    PERFORMANCE_THRESHOLDS['embedding_generation_time_ms'] = 3000
    PERFORMANCE_THRESHOLDS['batch_processing_time_ms'] = 20000