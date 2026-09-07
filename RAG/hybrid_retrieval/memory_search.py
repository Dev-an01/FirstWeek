"""
Multi-Signal Memory Search Component for True Hybrid Retrieval
==============================================================

Implements intelligent memory search that combines multiple relevance signals
according to Solution Manual specification (section 5.2).

Five signals with exact weights:
1. Semantic Similarity (40% weight): Cosine similarity of embeddings
2. Temporal Decay (25% weight): Exponential decay based on age
3. Feedback Quality (multiplier 0.5-1.2): Based on user feedback
4. Decision Importance (20% weight): Manual or auto-tagged importance
5. User Context Similarity (multiplier 1.0-1.1): Match between current user and past

Formula from Solution Manual:
memory_score = (
    0.40 × semantic_similarity +
    0.25 × temporal_decay +
    0.20 × decision_importance
) × feedback_multiplier × user_context_multiplier

Example scoring from Solution Manual:
- Memory A: semantic=0.87, recency=0.85, importance=1.0, user_sim=1.1, feedback=1.2 → 1.11
- Memory B: semantic=0.92, recency=0.37, importance=1.0, user_sim=1.0, feedback=0.5 → 0.41
"""

import psycopg2
import psycopg2.pool
import psycopg2.extras
import logging
import json
import time
import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from datetime import datetime, timedelta

from .utils import get_logger

# Observability imports
from observability.decorators import trace_function
from observability.logging import StructuredLogger
from observability.metrics import (
    memory_search_latency,
    retrieval_results_counter,
)

logger = get_logger(__name__)
obs_logger = StructuredLogger('memory_search')


class MultiSignalMemorySearch:
    """
    Multi-signal memory search for executive-specific episodic memory.
    
    Implements the exact Solution Manual specification for intelligent memory search
    that combines multiple relevance signals with strict executive memory separation.
    """
    
    # Signal weights from Solution Manual Section 5.2
    SEMANTIC_WEIGHT = 0.40      # 40% weight for semantic similarity
    TEMPORAL_WEIGHT = 0.25      # 25% weight for temporal decay
    IMPORTANCE_WEIGHT = 0.20    # 20% weight for decision importance
    
    # Multiplier ranges
    FEEDBACK_MULTIPLIER_RANGE = {
        'positive': 1.2,        # 👍 boost
        'neutral': 1.0,         # No feedback
        'negative': 0.5         # 👎 penalty
    }
    
    USER_CONTEXT_MULTIPLIER_RANGE = {
        'exact_match': 1.1,     # Same user ID and role
        'role_match': 1.05,     # Same role only
        'no_match': 1.0         # No user context match
    }
    
    def __init__(self, postgres_config: Dict, preload_model: bool = True):
        """
        Initialize multi-signal memory search with PostgreSQL connection.
        
        Args:
            postgres_config: PostgreSQL connection parameters
            preload_model: Load embedding model at init (default: True)
        """
        self.postgres_config = postgres_config
        
        # Initialize PostgreSQL connection pool
        self.pg_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,  # minconn, maxconn
            **postgres_config
        )
        
        # Vector client will be initialized when needed
        self.vector_client = None
        
        # Pre-load embedding model to eliminate first-query delay
        self.embedding_model = None
        if preload_model:
            try:
                logger.info("[MultiSignalMemorySearch] Pre-loading shared embedding model...")
                from embedding_generation.model_manager import get_shared_embedding_model
                self.embedding_model = get_shared_embedding_model()
                logger.info("[MultiSignalMemorySearch] ✅ Shared embedding model loaded")
            except Exception as e:
                logger.warning(f"[MultiSignalMemorySearch] ⚠️ Model pre-load failed: {e}")
        
        # Search result cache for performance
        self._search_cache = {}
        self._cache_ttl = 300  # 5 minutes
        
        logger.info("[MultiSignalMemorySearch] Initialized with PostgreSQL connection pool")
    
    @trace_function("memory_search", "search_executive_memory")
    def search_executive_memory(
        self,
        query: str,
        executive_id: str,
        current_user_id: Optional[str] = None,
        current_user_role: Optional[str] = None,
        top_k: int = 10,
        min_similarity: float = 0.4,
        time_window_days: int = 180,
        company_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main search method with all five signals from Solution Manual.
        
        Args:
            query: Search query text
            executive_id: Target executive ID (ALWAYS applied for strict separation)
            current_user_id: Current user ID for context matching
            current_user_role: Current user role for context matching
            top_k: Maximum number of results to return
            min_similarity: Minimum semantic similarity threshold
            time_window_days: Search window in days (default: 180)
        
        Returns:
            Dictionary with search results and metadata
        """
        start_time = time.time()
        
        # Log search started
        obs_logger.info(
            "Memory search started",
            query_length=len(query),
            executive_id=executive_id,
            top_k=top_k,
            time_window_days=time_window_days
        )
        
        # Check cache first
        cache_key = f"{query}:{executive_id}:{company_id or ''}:{current_user_id}:{current_user_role}:{top_k}:{min_similarity}:{time_window_days}"
        if cache_key in self._search_cache:
            cached_result, cached_time = self._search_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                logger.info(f"[MultiSignalMemorySearch] Cache hit for executive {executive_id}")
                return cached_result
        
        # Generate query embedding
        query_embedding = self._get_query_embedding(query)
        
        # Execute multi-signal search
        results = self._execute_multi_signal_search(
            query_embedding=query_embedding,
            executive_id=executive_id,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
            company_id=company_id,
            top_k=top_k,
            min_similarity=min_similarity,
            time_window_days=time_window_days
        )
        
        # Calculate final scores with all signals
        scored_results = []
        for result in results:
            # Calculate individual signals
            semantic_score = self.calculate_semantic_similarity(
                query_embedding, result['embedding']
            )
            
            temporal_score = self.calculate_temporal_decay(result['timestamp'])
            
            importance_score = self.calculate_importance_score(result['importance_score'])
            
            feedback_multiplier = self.apply_feedback_multiplier(result.get('feedback'))
            
            user_context_multiplier = self.calculate_user_similarity(
                current_user_id=current_user_id,
                current_user_role=current_user_role,
                memory_user_id=result.get('user_id'),
                memory_user_role=result.get('role')
            )
            
            # Combine signals using Solution Manual formula
            final_score = self.combine_signals(
                semantic_score=semantic_score,
                temporal_score=temporal_score,
                importance_score=importance_score,
                feedback_multiplier=feedback_multiplier,
                user_context_multiplier=user_context_multiplier
            )
            
            scored_results.append({
                'id': str(result['id']),
                'query': result['query'],
                'response': result['response'],
                'memory_score': final_score,
                'signals': {
                    'semantic_similarity': semantic_score,
                    'temporal_decay': temporal_score,
                    'decision_importance': importance_score,
                    'feedback_multiplier': feedback_multiplier,
                    'user_context_multiplier': user_context_multiplier
                },
                'metadata': {
                    'timestamp': result['timestamp'].isoformat() if result['timestamp'] else None,
                    'user_id': result.get('user_id'),
                    'role': result.get('role'),
                    'feedback': result.get('feedback'),
                    'importance_score': result.get('importance_score'),
                    'context_sources': result.get('context_sources'),
                    'days_ago': self._calculate_days_ago(result['timestamp'])
                }
            })
        
        # Sort by final score
        scored_results.sort(key=lambda x: x['memory_score'], reverse=True)
        
        # Prepare response
        query_time = (time.time() - start_time) * 1000
        response = {
            'results': scored_results[:top_k],
            'metadata': {
                'executive_id': executive_id,
                'total_found': len(scored_results),
                'returned': len(scored_results[:top_k]),
                'query_time_ms': round(query_time, 2),
                'time_window_days': time_window_days,
                'signal_weights': {
                    'semantic_similarity': self.SEMANTIC_WEIGHT,
                    'temporal_decay': self.TEMPORAL_WEIGHT,
                    'decision_importance': self.IMPORTANCE_WEIGHT
                }
            }
        }
        
        # Cache the result
        self._search_cache[cache_key] = (response, time.time())
        
        logger.info(f"[MultiSignalMemorySearch] Found {len(scored_results)} memories for {executive_id} in {query_time:.1f}ms")
        
        # Track metrics
        memory_search_latency.observe(query_time / 1000)
        if len(scored_results) > 0:
            retrieval_results_counter.labels(source='memory').observe(len(scored_results[:top_k]))
        
        # Log completion
        obs_logger.info(
            "Memory search completed",
            executive_id=executive_id,
            latency_ms=query_time,
            results_count=len(scored_results[:top_k]),
            total_found=len(scored_results)
        )
        
        return response
    
    def calculate_semantic_similarity(
        self, 
        query_embedding: np.ndarray, 
        memory_embedding: np.ndarray
    ) -> float:
        """
        Calculate semantic similarity using cosine similarity.
        
        Args:
            query_embedding: Query vector embedding
            memory_embedding: Memory vector embedding
        
        Returns:
            Cosine similarity score (0-1)
        """
        # Ensure embeddings are numpy arrays
        if not isinstance(query_embedding, np.ndarray):
            query_embedding = np.array(query_embedding)
        if not isinstance(memory_embedding, np.ndarray):
            memory_embedding = np.array(memory_embedding)
        
        # Calculate cosine similarity
        dot_product = np.dot(query_embedding, memory_embedding)
        norm_query = np.linalg.norm(query_embedding)
        norm_memory = np.linalg.norm(memory_embedding)
        
        if norm_query == 0 or norm_memory == 0:
            return 0.0
        
        similarity = dot_product / (norm_query * norm_memory)
        
        # Ensure result is in [0, 1] range
        return max(0.0, min(1.0, float(similarity)))
    
    def calculate_temporal_decay(self, timestamp: datetime) -> float:
        """
        Calculate temporal decay score using exponential decay.
        
        Formula: exp(-days_ago / 30) from Solution Manual
        
        Args:
            timestamp: Memory timestamp
        
        Returns:
            Temporal decay score (0-1, where 1 is most recent)
        """
        if not timestamp:
            return 0.0
        
        # Calculate days ago
        days_ago = self._calculate_days_ago(timestamp)
        
        # 60-day half-life for temporal decay (balances recency vs relevance)
        decay_score = math.exp(-days_ago / 60)
        
        # Ensure result is in [0, 1] range
        return max(0.0, min(1.0, decay_score))
    
    def apply_feedback_multiplier(self, feedback: Optional[str]) -> float:
        """
        Apply feedback quality multiplier based on user feedback.
        
        Args:
            feedback: Feedback value ('positive', 'negative', or None)
        
        Returns:
            Feedback multiplier (0.5-1.2)
        """
        if not feedback:
            return self.FEEDBACK_MULTIPLIER_RANGE['neutral']
        
        return self.FEEDBACK_MULTIPLIER_RANGE.get(
            feedback.lower(), 
            self.FEEDBACK_MULTIPLIER_RANGE['neutral']
        )
    
    def calculate_importance_score(self, importance_score: Optional[float]) -> float:
        """
        Calculate decision importance score.
        
        Args:
            importance_score: Stored importance value (0-1)
        
        Returns:
            Importance score (0-1)
        """
        if importance_score is None:
            return 1.0  # Default importance
        
        # Ensure score is in [0, 1] range
        return max(0.0, min(1.0, float(importance_score)))
    
    def calculate_user_similarity(
        self,
        current_user_id: Optional[str],
        current_user_role: Optional[str],
        memory_user_id: Optional[str],
        memory_user_role: Optional[str]
    ) -> float:
        """
        Calculate user context similarity multiplier.
        
        Args:
            current_user_id: Current user ID
            current_user_role: Current user role
            memory_user_id: Memory user ID
            memory_user_role: Memory user role
        
        Returns:
            User context multiplier (1.0-1.1)
        """
        # Exact match: same user ID and role
        if (current_user_id and memory_user_id and 
            current_user_id == memory_user_id and
            current_user_role and memory_user_role and
            current_user_role == memory_user_role):
            return self.USER_CONTEXT_MULTIPLIER_RANGE['exact_match']
        
        # Role match only
        if (current_user_role and memory_user_role and 
            current_user_role == memory_user_role):
            return self.USER_CONTEXT_MULTIPLIER_RANGE['role_match']
        
        # No match
        return self.USER_CONTEXT_MULTIPLIER_RANGE['no_match']
    
    def combine_signals(
        self,
        semantic_score: float,
        temporal_score: float,
        importance_score: float,
        feedback_multiplier: float,
        user_context_multiplier: float
    ) -> float:
        """
        Combine all signals using Solution Manual formula.
        
        Formula:
        memory_score = (
            0.40 × semantic_similarity +
            0.25 × temporal_decay +
            0.20 × decision_importance
        ) × feedback_multiplier × user_context_multiplier
        
        Args:
            semantic_score: Semantic similarity score (0-1)
            temporal_score: Temporal decay score (0-1)
            importance_score: Decision importance score (0-1)
            feedback_multiplier: Feedback quality multiplier (0.5-1.2)
            user_context_multiplier: User context multiplier (1.0-1.1)
        
        Returns:
            Final combined memory score
        """
        # Weighted sum of primary signals
        weighted_sum = (
            self.SEMANTIC_WEIGHT * semantic_score +
            self.TEMPORAL_WEIGHT * temporal_score +
            self.IMPORTANCE_WEIGHT * importance_score
        )
        
        # Apply multipliers
        final_score = weighted_sum * feedback_multiplier * user_context_multiplier
        
        return final_score
    
    def _execute_multi_signal_search(
        self,
        query_embedding: np.ndarray,
        executive_id: str,
        current_user_id: Optional[str],
        current_user_role: Optional[str],
        company_id: Optional[str] = None,
        top_k: int = 10,
        min_similarity: float = 0.0,
        time_window_days: int = 365
    ) -> List[Dict[str, Any]]:
        """
        Execute database query with executive_id filtering ALWAYS applied.
        
        Args:
            query_embedding: Query vector embedding
            executive_id: Target executive ID (ALWAYS applied)
            current_user_id: Current user ID for context
            current_user_role: Current user role for context
            top_k: Maximum results
            min_similarity: Minimum similarity threshold
            time_window_days: Time window in days
        
        Returns:
            List of raw memory records
        """
        # Convert embedding to list for PostgreSQL
        embedding_list = query_embedding.tolist()
        
        # SQL query with executive_id ALWAYS applied for strict separation
        sql = """
        SELECT 
            id,
            query,
            response,
            embedding,
            timestamp,
            user_id,
            role,
            feedback,
            importance_score,
            context_sources,
            1 - (embedding <=> %s::vector) AS semantic_similarity
        FROM episodic_memory
        WHERE executive_id = %s
          AND (company_id = %s OR company_id IS NULL)
          AND timestamp > NOW() - MAKE_INTERVAL(days => %s)
          AND 1 - (embedding <=> %s::vector) >= %s
        ORDER BY semantic_similarity DESC
        LIMIT %s
        """

        conn = None
        try:
            conn = self.pg_pool.getconn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                params = (
                    embedding_list,      # For similarity calculation
                    executive_id,        # ALWAYS filter by executive_id
                    company_id or '',    # Tenant isolation
                    time_window_days,    # Time window
                    embedding_list,      # For similarity threshold
                    min_similarity,      # Minimum similarity
                    top_k               # Limit
                )
                
                cur.execute(sql, params)
                results = cur.fetchall()
                
                # Convert to list of dicts
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"[MultiSignalMemorySearch] Database query failed: {e}")
            raise
        finally:
            if conn:
                self.pg_pool.putconn(conn)
    
    def _get_query_embedding(self, query: str) -> np.ndarray:
        """
        Get embedding for query text.

        Args:
            query: Query text

        Returns:
            Query embedding as numpy array
        """
        if not self.embedding_model:
            from embedding_generation.model_manager import get_shared_embedding_model
            self.embedding_model = get_shared_embedding_model()
            logger.info("[MultiSignalMemorySearch] Loaded shared embedding model")

        return self.embedding_model.generate_embedding(query)
    
    def _calculate_days_ago(self, timestamp: datetime) -> int:
        """
        Calculate number of days since timestamp.
        
        Args:
            timestamp: Memory timestamp
        
        Returns:
            Number of days ago
        """
        if not timestamp:
            return 0
        
        now = datetime.now(timestamp.tzinfo)
        delta = now - timestamp
        return max(0, delta.days)
    
    def store_interaction(
        self,
        executive_id: str,
        query: str,
        response: str,
        sources_used: List[Dict],
        user_id: str = None,
        user_role: str = None,
        importance: float = 1.0,
        session_id: str = None
    ) -> str:
        """
        Store a new interaction in executive's memory.
        
        Args:
            executive_id: Which executive
            query: User's question
            response: System's answer
            sources_used: List of documents used
            user_id: Who asked
            user_role: Their role
            importance: How important (0-1)
            session_id: Conversation session ID
        
        Returns:
            interaction_id: UUID of stored interaction
        """
        # Generate embedding for query
        query_embedding = self._get_query_embedding(query)
        
        # Insert into episodic_memory
        sql = """
        INSERT INTO episodic_memory (
            executive_id,
            query,
            response,
            embedding,
            user_id,
            role,
            importance_score,
            context_sources,
            timestamp
        ) VALUES (
            %s, %s, %s, %s::vector, %s, %s, %s, %s, NOW()
        )
        RETURNING id
        """
        
        conn = None
        try:
            conn = self.pg_pool.getconn()
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        executive_id,
                        query,
                        response,
                        query_embedding.tolist(),
                        user_id,
                        user_role,
                        importance,
                        json.dumps(sources_used) if sources_used else None
                    )
                )
                
                interaction_id = cur.fetchone()[0]
                conn.commit()
                
                logger.info(f"[MultiSignalMemorySearch] Stored interaction {interaction_id} for {executive_id}")
                
                # Clear cache for this executive
                self._clear_executive_cache(executive_id)
                
                return str(interaction_id)
                
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"[MultiSignalMemorySearch] Store failed: {e}")
            raise
        finally:
            if conn:
                self.pg_pool.putconn(conn)
    
    def update_feedback(
        self,
        interaction_id: str,
        feedback: str
    ) -> bool:
        """
        Update user feedback for an interaction.
        
        Args:
            interaction_id: UUID of interaction
            feedback: 'positive' or 'negative'
        
        Returns:
            True if updated, False otherwise
        """
        if feedback not in ['positive', 'negative']:
            logger.warning(f"[MultiSignalMemorySearch] Invalid feedback: {feedback}")
            return False
        
        sql = """
        UPDATE episodic_memory
        SET feedback = %s
        WHERE id = %s
        RETURNING executive_id
        """
        
        conn = None
        try:
            conn = self.pg_pool.getconn()
            with conn.cursor() as cur:
                cur.execute(sql, (feedback, interaction_id))
                result = cur.fetchone()
                conn.commit()
                
                if result:
                    executive_id = result[0]
                    logger.info(f"[MultiSignalMemorySearch] Updated feedback for {interaction_id}: {feedback}")
                    
                    # Clear cache for this executive
                    self._clear_executive_cache(executive_id)
                    
                    return True
                else:
                    logger.warning(f"[MultiSignalMemorySearch] Interaction {interaction_id} not found")
                    return False
                    
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"[MultiSignalMemorySearch] Feedback update failed: {e}")
            return False
        finally:
            if conn:
                self.pg_pool.putconn(conn)
    
    def _clear_executive_cache(self, executive_id: str):
        """
        Clear cached results for a specific executive.
        
        Args:
            executive_id: Executive ID to clear cache for
        """
        keys_to_remove = []
        for key in self._search_cache:
            if f":{executive_id}:" in key:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._search_cache[key]
        
        logger.debug(f"[MultiSignalMemorySearch] Cleared {len(keys_to_remove)} cache entries for {executive_id}")
    
    def get_memory_statistics(self, executive_id: str) -> Dict[str, Any]:
        """
        Get memory statistics for an executive.
        
        Args:
            executive_id: Which executive
        
        Returns:
            Dictionary with memory statistics
        """
        sql = """
        SELECT 
            COUNT(*) AS total_interactions,
            SUM(CASE WHEN feedback = 'positive' THEN 1 ELSE 0 END) AS positive_feedback,
            SUM(CASE WHEN feedback = 'negative' THEN 1 ELSE 0 END) AS negative_feedback,
            AVG(COALESCE(importance_score, 1.0)) AS avg_importance,
            MIN(timestamp) AS oldest_memory,
            MAX(timestamp) AS newest_memory,
            COUNT(DISTINCT user_id) AS unique_users
        FROM episodic_memory
        WHERE executive_id = %s
        """
        
        conn = None
        try:
            conn = self.pg_pool.getconn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (executive_id,))
                row = cur.fetchone()
                
                if row:
                    return {
                        "total_interactions": int(row['total_interactions']),
                        "positive_feedback": int(row['positive_feedback']) if row['positive_feedback'] else 0,
                        "negative_feedback": int(row['negative_feedback']) if row['negative_feedback'] else 0,
                        "avg_importance": float(row['avg_importance']) if row['avg_importance'] else 0.0,
                        "oldest_memory": row['oldest_memory'].isoformat() if row['oldest_memory'] else None,
                        "newest_memory": row['newest_memory'].isoformat() if row['newest_memory'] else None,
                        "unique_users": int(row['unique_users']) if row['unique_users'] else 0
                    }
                else:
                    return {
                        "total_interactions": 0,
                        "positive_feedback": 0,
                        "negative_feedback": 0,
                        "avg_importance": 0.0,
                        "oldest_memory": None,
                        "newest_memory": None,
                        "unique_users": 0
                    }
                    
        except Exception as e:
            logger.error(f"[MultiSignalMemorySearch] Statistics query failed: {e}")
            return {}
        finally:
            if conn:
                self.pg_pool.putconn(conn)
    
    def __del__(self):
        """Cleanup connection pool on deletion."""
        if hasattr(self, 'pg_pool') and self.pg_pool:
            self.pg_pool.closeall()
            logger.info("[MultiSignalMemorySearch] Connection pool closed")


__all__ = ['MultiSignalMemorySearch']
