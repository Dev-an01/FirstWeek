"""
LangGraph Studio Entry Point
Creates and exports the RAG workflow for visualization and debugging
"""
import sys
import os
from pathlib import Path
import logging
import atexit
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from langgraph.graph import StateGraph
from langgraph_workflow.graph import create_rag_workflow

# Import required components
from vector_search.search_engine import VectorSearchEngine
from graph_context.provider import GraphContextProvider
from hybrid_retrieval.query_analyzer import QueryAnalyzer
from hybrid_retrieval.query_router import QueryRouter
from hybrid_retrieval.result_fusion import ResultFusion
from hybrid_retrieval.adaptive_reranker import AdaptiveReranker
from hybrid_retrieval.manager import HybridRetrievalManager
from llm_integration.orchestrator import LLMOrchestrator


# Singleton cache to prevent recreating heavy components with blocking I/O
# This eliminates repeated BlockingError warnings during LangGraph dev
_COMPONENT_CACHE = {
    'vector_engine': None,
    'graph_provider': None,
    'llm_orchestrator': None,
}


def _cleanup_components():
    """Cleanup components with blocking I/O in a thread to avoid async context issues"""
    def _do_cleanup():
        if _COMPONENT_CACHE['graph_provider']:
            try:
                _COMPONENT_CACHE['graph_provider'].driver.close()
                logger.info("Neo4j driver closed successfully")
            except Exception as e:
                logger.warning(f"Error closing Neo4j driver: {e}")

    # Run cleanup in a thread to avoid blocking warnings
    with ThreadPoolExecutor() as executor:
        executor.submit(_do_cleanup)


# Register cleanup handler
atexit.register(_cleanup_components)


# Mock session manager for LangGraph Studio (not needed for visualization)
class MockSessionManager:
    """Mock session manager for LangGraph Studio"""
    def __init__(self):
        pass

    async def initialize(self):
        pass


def create_workflow() -> StateGraph:
    """
    Create and return the compiled RAG workflow for LangGraph Studio

    This is the entry point that LangGraph Studio uses to load your workflow.
    It initializes all required dependencies and creates the workflow.

    Uses singleton caching to prevent recreating heavy components with blocking I/O.

    Returns:
        StateGraph: Compiled workflow ready for execution
    """
    logger.info("Initializing RAG workflow for LangGraph Studio...")

    try:
        # Initialize vector search engine with lazy loading and singleton caching
        if _COMPONENT_CACHE['vector_engine'] is None:
            logger.info("Loading VectorSearchEngine (first time)...")
            try:
                # Create engine in a thread to avoid blocking file I/O for model loading
                with ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: VectorSearchEngine(enable_cache=True, enable_redis=False)
                    )
                    _COMPONENT_CACHE['vector_engine'] = future.result(timeout=30)
            except Exception as e:
                logger.warning(f"VectorSearchEngine initialization failed: {e}")
                logger.warning("Using mock vector engine for graph visualization")
                _COMPONENT_CACHE['vector_engine'] = None
        else:
            logger.info("Reusing cached VectorSearchEngine")

        vector_engine = _COMPONENT_CACHE['vector_engine']

        # Initialize graph context provider with singleton caching
        if _COMPONENT_CACHE['graph_provider'] is None:
            logger.info("Loading GraphContextProvider (first time)...")
            try:
                # Create provider in a thread to avoid blocking socket operations
                with ThreadPoolExecutor() as executor:
                    future = executor.submit(GraphContextProvider)
                    _COMPONENT_CACHE['graph_provider'] = future.result(timeout=10)
            except Exception as e:
                logger.warning(f"Graph provider unavailable: {e}")
                _COMPONENT_CACHE['graph_provider'] = None
        else:
            logger.info("Reusing cached GraphContextProvider")

        graph_provider = _COMPONENT_CACHE['graph_provider']

        # Initialize other components (these are non-blocking and lightweight)
        logger.info("Loading hybrid retrieval components...")
        query_analyzer = QueryAnalyzer()
        query_router = QueryRouter()
        result_fusion = ResultFusion()
        adaptive_reranker = AdaptiveReranker()

        # Initialize LLM orchestrator with singleton caching
        if _COMPONENT_CACHE['llm_orchestrator'] is None:
            logger.info("Loading LLM Orchestrator (first time)...")
            try:
                # Create orchestrator in a thread to avoid blocking async context
                with ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: LLMOrchestrator(provider="groq"))
                    _COMPONENT_CACHE['llm_orchestrator'] = future.result(timeout=10)

            except Exception as e:
                logger.warning(f"LLMOrchestrator initialization failed: {e}")
                logger.warning("Creating minimal orchestrator for graph visualization")
                _COMPONENT_CACHE['llm_orchestrator'] = None
        else:
            logger.info("Reusing cached LLM Orchestrator")

        llm_orchestrator = _COMPONENT_CACHE['llm_orchestrator']

        # Initialize session manager (mock for Studio)
        session_manager = MockSessionManager()

        # Initialize hybrid retrieval manager
        logger.info("Loading HybridRetrievalManager...")
        hybrid_retrieval_manager = HybridRetrievalManager(
            vector_search_engine=vector_engine,
            graph_context_provider=graph_provider,
            memory_search_engine=None,
            enable_cache=True,
            enable_metrics=False,
            enable_decomposition=False
        )

        # Create workflow with all dependencies
        logger.info("Creating RAG workflow graph...")
        workflow = create_rag_workflow(
            vector_engine=vector_engine,
            graph_provider=graph_provider,
            query_analyzer=query_analyzer,
            query_router=query_router,
            result_fusion=result_fusion,
            adaptive_reranker=adaptive_reranker,
            llm_orchestrator=llm_orchestrator,
            session_manager=session_manager,
            hybrid_retrieval_manager=hybrid_retrieval_manager
        )

        logger.info("✅ RAG workflow initialized successfully for LangGraph Studio")
        return workflow

    except Exception as e:
        logger.error(f"❌ Failed to initialize RAG workflow: {e}")
        raise
