"""
Vector Search Module

This module provides semantic search capabilities over embedded executive decisions,
policies, and profiles using vector similarity search on PostgreSQL with pgvector.

Main Components:
- VectorSearchEngine: Main search API
- PostgresVectorClient: Vector similarity queries
- EmbeddingCache: Two-level caching (memory + Redis)
- QueryProcessor: Query validation and preprocessing
- ResultProcessor: Metadata enrichment
- ResponseBuilder: Structured JSON responses
- RBACFilter: Role-based access control
"""

# Lazy imports to avoid pulling in heavy dependencies (observability, etc.)
# when only lightweight components like postgres_client are needed
from .config import (
    POSTGRES_CONFIG,
    VECTOR_SEARCH_CONFIG,
    MODEL_NAME,
    EMBEDDING_DIMENSION
)
from .rbac_filter import RBAC_ROLES

# PostgresVectorClient can be imported directly without heavy deps
from .postgres_client import PostgresVectorClient

__version__ = "2.0.0"
__all__ = [
    "VectorSearchEngine",
    "PostgresVectorClient",
    "POSTGRES_CONFIG",
    "VECTOR_SEARCH_CONFIG",
    "RBAC_ROLES",
    "MODEL_NAME",
    "EMBEDDING_DIMENSION"
]


def __getattr__(name):
    """Lazy import for VectorSearchEngine to avoid loading observability."""
    if name == "VectorSearchEngine":
        from .search_engine import VectorSearchEngine
        return VectorSearchEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
