"""
Configuration constants for embedding generation system.
All database credentials, model settings, and processing parameters.
"""
import os
from pathlib import Path

# Load environment variables from .env file (project root: ai officer/.env)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

POSTGRES_CONFIG = {
    'dbname': os.getenv('POSTGRES_DB', 'ai_officer'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres123'),
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432'))
}

NEO4J_CONFIG = {
    'uri': os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    'user': os.getenv('NEO4J_USER', 'neo4j'),
    'password': os.getenv('NEO4J_PASSWORD', 'neo4j123')
}

# ============================================================================
# MODEL CONFIGURATION
# ============================================================================

# Sentence Transformers model for local embedding generation
# MIGRATED: From English-only all-mpnet-base-v2 (768d) to multilingual BAAI/bge-m3 (1024d)
# BGE-M3 supports 100+ languages including Japanese + English
# This enables cross-lingual retrieval for executive digital twins
MODEL_NAME = 'BAAI/bge-m3'
EMBEDDING_DIMENSION = 1024
DEVICE = os.getenv('EMBEDDING_DEVICE', 'cuda')
BATCH_SIZE = 10 

# Model characteristics
MAX_SEQUENCE_LENGTH = 384  
NORMALIZE_EMBEDDINGS = True  # L2 normalization (unit vectors)

# ============================================================================
# PROCESSING CONFIGURATION
# ============================================================================

# Text processing
MAX_TEXT_LENGTH = 8000  # Maximum tokens per text (safe limit)
TRUNCATE_LONG_TEXT = True  # Truncate if exceeds max length

# Error handling
RETRY_ATTEMPTS = 3  # Number of retries for failed operations
RETRY_DELAY = 5  # Seconds to wait between retries

# Progress tracking
SHOW_PROGRESS = True  # Display progress for each item
LOG_ERRORS = True  # Log all errors to file

# ============================================================================
# STORAGE CONFIGURATION
# ============================================================================

# PostgreSQL storage
UPSERT_MODE = True  # Use ON CONFLICT for idempotent operations
CHUNK_INDEX_DEFAULT = 0  # Default chunk index for single embeddings

# Neo4j storage
NEO4J_TIMEOUT = 30  # Seconds for Neo4j operations
NEO4J_REQUIRED = False  # If False, failures won't stop process

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
LOG_FILE = 'embedding_generation.log'
LOG_TO_CONSOLE = True
LOG_TO_FILE = True

# ============================================================================
# EXPECTED COUNTS (For Verification)
# ============================================================================

EXPECTED_COUNTS = {
    'executive_profile': 1,  # sample only for FIRSTWEEK
    'decision_case': 10,
    'policy': 3,
    'total': 14
}

# Neo4j expected counts
NEO4J_EXPECTED_COUNTS = {
    'Decision': 10,
    'Policy': 3,
    'total': 13
}

# ============================================================================
# VERIFICATION CONFIGURATION
# ============================================================================

# Similarity test query
TEST_QUERY = "discount approval for customer"
TEST_EXPECTED_KEYWORDS = ['discount', 'approval', 'megacorp', 'pricing']

# Normalization tolerance
NORM_TOLERANCE = 0.02  # Allow 0.98 to 1.02 for L2 norm

# Distance thresholds for similarity test
SIMILARITY_THRESHOLD = 0.5  # Results must be at least this similar
