"""
Dependency Injection
Manages shared resources (retrieval system, etc.)
"""

from functools import lru_cache
import logging
from typing import Optional
import sys
import os

# Add parent directory to path to import RAG modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vector_search.search_engine import VectorSearchEngine
from graph_context.provider import GraphContextProvider
import asyncpg

logger = logging.getLogger(__name__)


class RetrievalSystem:
    """Singleton retrieval system"""
    
    _instance: Optional['RetrievalSystem'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self):
        """Initialize retrieval components (called once at startup)"""
        if self._initialized:
            logger.info("Retrieval system already initialized")
            return
        
        logger.info("Initializing retrieval system...")
        
        try:
            # Initialize vector search engine with caching enabled
            logger.info("  Loading VectorSearchEngine...")
            # Enable Redis L2 cache if REDIS_URL is available
            enable_redis = bool(os.getenv('REDIS_URL'))
            if enable_redis:
                logger.info("  ✅ Redis L2 cache enabled")
            else:
                logger.info("  ⚠️  Redis L2 cache disabled (set REDIS_URL to enable)")

            self.vector_engine = VectorSearchEngine(
                enable_cache=True,  # L1 memory cache always enabled
                enable_redis=enable_redis  # L2 Redis cache if available
            )

            # Initialize graph context provider
            logger.info("  Loading GraphContextProvider...")
            try:
                self.graph_provider = GraphContextProvider()
                logger.info("✅ Graph context provider initialized")
            except Exception as e:
                logger.warning(f"⚠️ Graph context provider unavailable (Neo4j not running): {e}")
                logger.warning("  Continuing with pure vector search (no graph enhancement)")
                self.graph_provider = None

            self._initialized = True
            logger.info("✅ Retrieval system initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize retrieval system: {e}")
            raise
    
    def get_vector_engine(self) -> VectorSearchEngine:
        """Get the vector search engine instance"""
        if not self._initialized:
            raise RuntimeError("Retrieval system not initialized. Call initialize() first.")
        return self.vector_engine
    
    def get_graph_provider(self) -> GraphContextProvider:
        """Get the graph context provider instance"""
        if not self._initialized:
            raise RuntimeError("Retrieval system not initialized. Call initialize() first.")
        return self.graph_provider
    
    def get_memory_search(self):
        """Get memory search instance"""
        if not self._initialized:
            raise RuntimeError("Retrieval system not initialized. Call initialize() first.")
        # This would be implemented when memory search is integrated
        return None
    
    def get_profile_manager(self):
        """Get profile manager instance"""
        if not self._initialized:
            raise RuntimeError("Retrieval system not initialized. Call initialize() first.")
        # This would be implemented when profile manager is integrated
        return None
    
    def get_adaptive_reranker(self):
        """Get adaptive reranker instance"""
        if not self._initialized:
            raise RuntimeError("Retrieval system not initialized. Call initialize() first.")
        # This would be implemented when adaptive reranker is integrated
        return None


# Global instance
retrieval_system = RetrievalSystem()


@lru_cache()
def get_vector_engine() -> VectorSearchEngine:
    """
    Dependency injection for vector search engine
    Used by FastAPI endpoints
    """
    return retrieval_system.get_vector_engine()


@lru_cache()
def get_graph_provider() -> GraphContextProvider:
    """
    Dependency injection for graph context provider
    Used by FastAPI endpoints
    """
    return retrieval_system.get_graph_provider()


# Sentinel value: when used as company_id in vector search, matches nothing
NO_TENANT_SENTINEL = "__no_tenant__"


def resolve_company_id(company_id: Optional[str], user_role: str) -> Optional[str]:
    """
    Resolve company_id for tenant isolation (secure-by-default).

    - company_id provided → use it (filter to that company)
    - super_admin without company_id → None (no filter, sees all)
    - Any other role without company_id → sentinel (matches nothing)
    """
    if company_id:
        return company_id
    if user_role and user_role.lower() == "super_admin":
        return None  # super_admin may see all
    return NO_TENANT_SENTINEL


@lru_cache()
def get_db_pool():
    """
    Dependency injection for database connection pool
    Used by session endpoints
    """
    # This would be initialized in the main app
    # For now, return None - this needs to be properly initialized
    return None


@lru_cache()
def get_session_manager():
    """
    Dependency injection for session manager
    Used by chat endpoints
    """
    # This would be initialized in the main app
    # For now, return None - this needs to be properly initialized
    return None
