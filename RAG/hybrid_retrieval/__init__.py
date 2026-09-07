"""
Hybrid Retrieval Pipeline
==========================

Unified retrieval interface combining:
- Vector search (semantic similarity)
- Graph context (relationship awareness with enhanced spaCy NER)
- Personal memory (executive-specific history)

Usage:
    from hybrid_retrieval import HybridRetrievalManager
    from vector_search import VectorSearchEngine
    from graph_context import GraphContextProvider
    from hybrid_retrieval import MemorySearchEngine
    from hybrid_retrieval.config import POSTGRES_CONFIG, NEO4J_CONFIG
    
    # Initialize components
    vector_engine = VectorSearchEngine()
    graph_provider = GraphContextProvider()
    memory_engine = MemorySearchEngine(POSTGRES_CONFIG)
    
    # Create hybrid manager
    retrieval = HybridRetrievalManager(
        vector_search_engine=vector_engine,
        graph_context_provider=graph_provider,
        memory_search_engine=memory_engine
    )
    
    # Unified retrieval
    results = retrieval.retrieve(
        query="Should we approve 15% discount for Acme?",
        executive_id="exec_001",
        user_context={"role": "employee", "allowed_scopes": ["public", "internal"]},
        top_k=10
    )
    
    # Access results
    for result in results['results']:
        print(f"{result['rank']}. {result['title']} (score: {result['final_score']:.3f})")
        print(f"   Found in: {', '.join(result['found_in'])}")
        print(f"   Why: {result['provenance']['why_relevant']}")
"""

from .manager import HybridRetrievalManager
from .unified_retrieval import UnifiedRetrieval, RetrievalPath, PathPerformanceMetrics
from .memory_search import MultiSignalMemorySearch
from .query_analyzer import QueryAnalyzer
from .result_fusion import ResultFusion
from .adaptive_reranker import AdaptiveReranker
from .response_builder import ResponseBuilder
from .config import HYBRID_RETRIEVAL_CONFIG, POSTGRES_CONFIG, NEO4J_CONFIG

__all__ = [
    'HybridRetrievalManager',
    'UnifiedRetrieval',
    'RetrievalPath',
    'PathPerformanceMetrics',
    'MultiSignalMemorySearch',
    'QueryAnalyzer',
    'ResultFusion',
    'AdaptiveReranker',
    'ResponseBuilder',
    'HYBRID_RETRIEVAL_CONFIG',
    'POSTGRES_CONFIG',
    'NEO4J_CONFIG'
]

__version__ = '1.0.0'
__author__ = 'AI Officer Team'
__description__ = 'Full Hybrid Retrieval Pipeline (Blueprint #4)'
