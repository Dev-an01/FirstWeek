"""
Configuration for Vector Search Module

Reuses database credentials from Phase 1 and adds vector search specific settings.
"""
import os
from pathlib import Path

# Load environment variables from .env file (look in project root for consolidated config)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

# ============================================================================
# REUSED FROM PHASE 1 (embedding_generation/config.py)
# ============================================================================

# PostgreSQL Configuration (reads from environment variables with defaults)
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'ai_officer'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres123')
}

# Neo4j Configuration (reads from environment variables with defaults)
NEO4J_CONFIG = {
    'uri': os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    'user': os.getenv('NEO4J_USER', 'neo4j'),
    'password': os.getenv('NEO4J_PASSWORD', 'neo4j123')
}

# Model Configuration
# MIGRATED: From English-only all-mpnet-base-v2 (768d) to multilingual BAAI/bge-m3 (1024d)
# BGE-M3 supports 100+ languages including Japanese + English
MODEL_NAME = "BAAI/bge-m3"
EMBEDDING_DIMENSION = 1024

# ============================================================================
# VECTOR SEARCH MODULE CONFIGURATION
# ============================================================================

# Vector Search Settings
VECTOR_SEARCH_CONFIG = {
    # Default search parameters
    'top_k_default': 30,  # Increased from 20 for better retrieval coverage
    # Priority 2 Fix: Lowered from 0.35 to 0.30 for better recall (was missing relevant docs)
    'min_score_default': 0.30,  # Minimum cosine similarity score (0-1)
    'max_query_length': 1000,  # Maximum characters in query

    # Phase 5 Fix: Configurable person name boost (was hardcoded 1.4x, reduced to 1.2x)
    'person_name_boost': 1.2,  # Boost factor for exact name matches
    
    # Cache settings
    'cache_size': 1000,  # Number of query embeddings to cache in memory (L1)
    'cache_ttl_seconds': 604800,  # 7 days for Redis cache (L2)
    'enable_redis_cache': False,  # Set to True if Redis is available
    
    # Connection pooling
    'connection_pool_size': 10,
    'connection_pool_max': 20,
    
    # Performance settings
    'batch_size': 50,  # Maximum queries per batch_search()
    'timeout_seconds': 30,
    
    # Result enrichment
    'include_metadata': True,
    'include_citations': True,
    'max_citation_length': 500,  # Characters to include in citation snippets
}

# Redis Configuration (optional, for L2 cache - reads from environment)
REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', '6379')),
    'db': 0,
    'password': os.getenv('REDIS_PASSWORD'),
    'decode_responses': False,  # We store binary embeddings
    'socket_timeout': 5,
    'socket_connect_timeout': 5,
}

# ============================================================================
# EMBEDDING SERVICE CONFIGURATION
# ============================================================================

# Embedding Service Integration
EMBEDDING_SERVICE_CONFIG = {
    'enabled': os.getenv('EMBEDDING_SERVICE_ENABLED', 'false').lower() == 'true',
    'base_url': os.getenv('EMBEDDING_SERVICE_URL', 'http://localhost:8001'),
    'timeout_seconds': int(os.getenv('EMBEDDING_SERVICE_TIMEOUT', '30')),
    'retry_attempts': int(os.getenv('EMBEDDING_SERVICE_RETRIES', '3')),
    'async_processing': os.getenv('EMBEDDING_SERVICE_ASYNC', 'true').lower() == 'true',
}

# Fallback to local embedding generation if service is unavailable
EMBEDDING_FALLBACK_ENABLED = os.getenv('EMBEDDING_FALLBACK_ENABLED', 'true').lower() == 'true'

# ============================================================================
# RBAC (Role-Based Access Control) CONFIGURATION
# ============================================================================
# Canonical RBAC definitions live in shared/rbac.py
# Import from there for role-to-scope mapping.
from shared.rbac import DEFAULT_ROLE

# ============================================================================
# SOURCE TYPE MAPPING
# ============================================================================

# Maps friendly names to database source types
SOURCE_TYPE_MAPPING = {
    'decision': 'decision_case',
    'decisions': 'decision_case',
    'policy': 'policy',  # Changed to match actual DB
    'policies': 'policy',  # Changed to match actual DB
    'policy_document': 'policy',  # Map policy_document to policy
    'profile': 'executive_profile',
    'profiles': 'executive_profile',
    'executive': 'executive_profile',
    'executives': 'executive_profile',
    'slack': 'slack_message',
    'slack_messages': 'slack_message',
    'communication': 'slack_message',
    'communications': 'slack_message',
}

# Valid source types (what's actually stored in database)
# Phase 5 Fix: Added 'document' and 'voiceprint' which were being excluded (214 of 250 embeddings!)
# Added 'slack_message' for Slack communications from executives
VALID_SOURCE_TYPES = ['decision_case', 'policy', 'executive_profile', 'document', 'voiceprint', 'slack_message']

# ============================================================================
# METADATA FIELD MAPPINGS
# ============================================================================

# Fields to retrieve for each source type
METADATA_FIELDS = {
    'decision_case': [
        'id',
        'executive_id',
        'title',
        'date',
        'category',
        'situation',
        'decision_made',
        'rationale',
        'outcome',
        'lessons_learned',
        'confidence',
        'precedent',
        'full_content',
    ],
    'policy': [
        'id',
        'name',
        'version',
        'category',
        'content_markdown',
        'content_sections',
        'effective_date',
        'owner_executive',
        'confidentiality',
        'file_path',
    ],
    'executive_profile': [
        'id',
        'name',
        'title',
        'department',
        'email',
        'profile_data',
        'formality_scale',
        'directness_scale',
        'warmth_scale',
    ],
    # Phase 5 Fix: Added voiceprint metadata fields
    'voiceprint': [
        'source_id',
        'name',
        'executive_title',
        'voiceprint_text',
    ],
    # Phase 5 Fix: Added document metadata fields
    'document': [
        'source_id',
        'title',
        'parent_document_id',
        'parent_document_type',
        'content',
        'section_type',
    ],
}

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s'
        },
        'simple': {
            'format': '%(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': 'vector_search.log',
            'mode': 'a',
        },
    },
    'loggers': {
        'vector_search': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
            'propagate': False,
        },
    },
}
