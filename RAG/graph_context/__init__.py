"""
Graph Context Provider Module

Provides graph-based context to enhance vector search.
This is NOT a standalone search engine - it's a helper for VectorSearchEngine.

Public API:
    GraphContextProvider - Main class for discovering graph context
    
Usage:
    from graph_context import GraphContextProvider
    
    # Initialize provider
    provider = GraphContextProvider(neo4j_config)
    
    # Discover context for a query
    context = provider.discover_context(
        query="Who worked with Akiko on Acme?",
        allowed_scopes=["public", "confidential"]
    )
    
    # Use context to constrain vector search
    if context["has_context"]:
        vector_search(candidate_ids=context["candidate_ids"], ...)
"""

from .provider import GraphContextProvider
from .config import (
    GRAPH_CONTEXT_CONFIG,
    ENTITY_PATTERNS,
    NEO4J_CONFIG
)

__all__ = [
    'GraphContextProvider',
    'GRAPH_CONTEXT_CONFIG',
    'ENTITY_PATTERNS',
    'NEO4J_CONFIG'
]

__version__ = '1.0.0'
