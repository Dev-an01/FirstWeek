"""
Dynamic Examples Learning

Implements learning from successful interactions to build a library
of few-shot examples that improve over time.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import uuid

import asyncpg
from asyncpg import Connection

logger = logging.getLogger(__name__)


class DynamicExamples:
    """
    Manages dynamic few-shot examples learned from successful interactions.
    
    Implements learning loop from user feedback, quality assessment,
    and example lifecycle management.
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        min_quality_threshold: float = 0.3,
        max_examples_per_executive: int = 20,
        example_expiry_days: int = 90
    ):
        """
        Initialize DynamicExamples manager.
        
        Args:
            db_pool: PostgreSQL connection pool
            min_quality_threshold: Minimum quality score for inclusion
            max_examples_per_executive: Maximum examples to keep per executive
            example_expiry_days: Days before examples expire
        """
        self.db_pool = db_pool
        self.min_quality_threshold = min_quality_threshold
        self.max_examples_per_executive = max_examples_per_executive
        self.example_expiry_days = example_expiry_days
        
        self.logger = logging.getLogger(__name__)
    
    async def learn_from_interaction(
        self,
        executive_id: str,
        query: str,
        response: str,
        user_feedback: int,
        context_sources: Optional[Dict[str, Any]] = None,
        query_type: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        embedding: Optional[List[float]] = None
    ) -> Optional[str]:
        """
        Learn from a successful interaction.
        
        Args:
            executive_id: Executive profile ID
            query: User's query
            response: AI's response
            user_feedback: User feedback (1=👍, -1=👎, 0=no feedback)
            context_sources: Sources used in response
            query_type: Type of query (approval, recommendation, etc.)
            response_time_ms: Response time in milliseconds
            embedding: Query embedding vector
            
        Returns:
            Example ID if learned, None if not qualified
        """
        # Only learn from positive feedback
        if user_feedback != 1:
            self.logger.debug(
                f"Skipping learning from interaction with feedback={user_feedback}"
            )
            return None
        
        # Assess quality criteria
        quality_score = await self._assess_example_quality(
            query, response, context_sources, response_time_ms
        )
        
        if quality_score < self.min_quality_threshold:
            self.logger.debug(
                f"Example quality {quality_score} below threshold "
                f"{self.min_quality_threshold}"
            )
            return None
        
        # Check for novelty (avoid duplicates)
        if not await self._is_example_novel(executive_id, query, response):
            self.logger.debug("Example too similar to existing examples")
            return None
        
        # Determine example type
        example_type = self._classify_example_type(query, response)
        query_type = query_type or self._classify_query_type(query)
        
        # Store the example
        async with self.db_pool.acquire() as conn:
            try:
                example_id = await conn.fetchval(
                    """
                    INSERT INTO communication_examples (
                        executive_id, query, response, user_feedback,
                        quality_score, example_type, query_type,
                        context_sources, timestamp, is_bootstrap,
                        avg_response_time_ms, embedding
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    RETURNING id
                    """,
                    executive_id,
                    query,
                    response,
                    user_feedback,
                    quality_score,
                    example_type,
                    query_type,
                    json.dumps(context_sources or {}),
                    datetime.utcnow(),
                    False,  # Learned example
                    response_time_ms,
                    embedding
                )
                
                self.logger.info(
                    f"Learned new example for {executive_id}: "
                    f"quality={quality_score:.2f}, type={example_type}"
                )
                
                # Trigger pruning if needed
                await self._ensure_example_limit(executive_id, conn)
                
                return str(example_id)
                
            except Exception as e:
                self.logger.error(f"Failed to learn example: {e}")
                return None
    
    async def get_examples_for_prompt(
        self,
        executive_id: str,
        query_type: Optional[str] = None,
        max_examples: int = 5,
        include_bootstrap: bool = True,
        diversity_factor: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Get best examples for prompt generation.
        
        Args:
            executive_id: Executive profile ID
            query_type: Optional query type filter
            max_examples: Maximum examples to return
            include_bootstrap: Whether to include bootstrap examples
            diversity_factor: How much to prioritize diversity (0-1)
            
        Returns:
            List of example dictionaries
        """
        async with self.db_pool.acquire() as conn:
            try:
                # Get diverse, high-quality examples
                examples = await conn.fetch(
                    """
                    WITH ranked_examples AS (
                        SELECT 
                            ce.*,
                            -- Calculate diversity score
                            (ce.quality_score * 0.4 + ce.success_rate * 0.3 + ce.usage_count * 0.3) as base_score,
                            -- Penalize similar examples
                            ROW_NUMBER() OVER (
                                PARTITION BY ce.diversity_cluster 
                                ORDER BY ce.quality_score DESC, ce.timestamp DESC
                            ) as cluster_rank
                        FROM communication_examples ce
                        WHERE ce.executive_id = $1
                          AND ce.is_active = true
                          AND ce.quality_score >= $2
                          AND ($3::boolean OR ce.is_bootstrap = false)
                          AND ($4 IS NULL OR ce.query_type = $4)
                          AND (ce.expires_at IS NULL OR ce.expires_at > NOW())
                    ),
                    diversity_adjusted AS (
                        SELECT 
                            re.*,
                            -- Apply diversity penalty
                            CASE 
                                WHEN re.cluster_rank > 1 THEN re.base_score * (1 - $5)
                                ELSE re.base_score
                            END as final_score
                        FROM ranked_examples re
                    )
                    SELECT 
                        id,
                        query,
                        response,
                        quality_score,
                        usage_count,
                        success_rate,
                        example_type,
                        query_type,
                        is_bootstrap,
                        timestamp,
                        last_used
                    FROM diversity_adjusted
                    ORDER BY final_score DESC, timestamp DESC
                    LIMIT $6
                    """,
                    executive_id,
                    self.min_quality_threshold,
                    include_bootstrap,
                    query_type,
                    diversity_factor,
                    max_examples
                )
                
                # Convert to dictionaries
                result = []
                for row in examples:
                    result.append({
                        'id': str(row['id']),
                        'query': row['query'],
                        'response': row['response'],
                        'quality_score': float(row['quality_score']),
                        'usage_count': row['usage_count'],
                        'success_rate': float(row['success_rate']),
                        'example_type': row['example_type'],
                        'query_type': row['query_type'],
                        'is_bootstrap': row['is_bootstrap'],
                        'timestamp': row['timestamp'].isoformat(),
                        'last_used': row['last_used'].isoformat() if row['last_used'] else None
                    })
                
                self.logger.debug(
                    f"Retrieved {len(result)} examples for {executive_id}"
                )
                
                return result
                
            except Exception as e:
                self.logger.error(f"Failed to get examples: {e}")
                return []
    
    async def update_example_usage(
        self,
        example_id: str,
        success: bool = True
    ) -> bool:
        """
        Update usage statistics for an example.
        
        Args:
            example_id: Example ID
            success: Whether the example led to successful response
            
        Returns:
            True if updated successfully
        """
        async with self.db_pool.acquire() as conn:
            try:
                await conn.execute(
                    "SELECT update_example_usage($1, $2)",
                    uuid.UUID(example_id),
                    success
                )
                
                self.logger.debug(f"Updated usage for example {example_id}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to update example usage: {e}")
                return False
    
    async def process_feedback(
        self,
        example_id: str,
        user_feedback: int
    ) -> bool:
        """
        Process user feedback on an example.
        
        Args:
            example_id: Example ID
            user_feedback: User feedback (1=👍, -1=👎)
            
        Returns:
            True if processed successfully
        """
        async with self.db_pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    UPDATE communication_examples 
                    SET user_feedback = $1,
                        updated_at = NOW()
                    WHERE id = $2
                    """,
                    user_feedback,
                    uuid.UUID(example_id)
                )
                
                self.logger.info(
                    f"Processed feedback {user_feedback} for example {example_id}"
                )
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to process feedback: {e}")
                return False
    
    async def prune_examples(
        self,
        executive_id: Optional[str] = None
    ) -> int:
        """
        Prune old or low-quality examples.
        
        Args:
            executive_id: Specific executive ID, or None for all
            
        Returns:
            Number of examples pruned
        """
        async with self.db_pool.acquire() as conn:
            try:
                if executive_id:
                    pruned = await conn.fetchval(
                        "SELECT prune_old_examples($1, $2, $3)",
                        executive_id,
                        self.max_examples_per_executive,
                        self.min_quality_threshold
                    )
                else:
                    # Prune for all executives
                    total_pruned = 0
                    exec_ids = await conn.fetch(
                        "SELECT DISTINCT executive_id FROM communication_examples"
                    )
                    
                    for row in exec_ids:
                        pruned = await conn.fetchval(
                            "SELECT prune_old_examples($1, $2, $3)",
                            row['executive_id'],
                            self.max_examples_per_executive,
                            self.min_quality_threshold
                        )
                        total_pruned += pruned
                    
                    pruned = total_pruned
                
                self.logger.info(f"Pruned {pruned} examples")
                return pruned
                
            except Exception as e:
                self.logger.error(f"Failed to prune examples: {e}")
                return 0
    
    async def get_learning_stats(
        self,
        executive_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get learning statistics for monitoring.
        
        Args:
            executive_id: Specific executive ID, or None for all
            
        Returns:
            Statistics dictionary
        """
        async with self.db_pool.acquire() as conn:
            try:
                if executive_id:
                    stats = await conn.fetchrow(
                        """
                        SELECT 
                            COUNT(*) as total_examples,
                            COUNT(CASE WHEN is_bootstrap = false THEN 1 END) as learned_examples,
                            COUNT(CASE WHEN is_bootstrap = true THEN 1 END) as bootstrap_examples,
                            AVG(quality_score) as avg_quality,
                            AVG(success_rate) as avg_success_rate,
                            SUM(usage_count) as total_usage,
                            COUNT(CASE WHEN user_feedback = 1 THEN 1 END) as thumbs_up,
                            COUNT(CASE WHEN user_feedback = -1 THEN 1 END) as thumbs_down
                        FROM communication_examples
                        WHERE executive_id = $1
                          AND is_active = true
                        """,
                        executive_id
                    )
                else:
                    stats = await conn.fetchrow(
                        """
                        SELECT 
                            COUNT(*) as total_examples,
                            COUNT(CASE WHEN is_bootstrap = false THEN 1 END) as learned_examples,
                            COUNT(CASE WHEN is_bootstrap = true THEN 1 END) as bootstrap_examples,
                            AVG(quality_score) as avg_quality,
                            AVG(success_rate) as avg_success_rate,
                            SUM(usage_count) as total_usage,
                            COUNT(CASE WHEN user_feedback = 1 THEN 1 END) as thumbs_up,
                            COUNT(CASE WHEN user_feedback = -1 THEN 1 END) as thumbs_down
                        FROM communication_examples
                        WHERE is_active = true
                        """
                    )
                
                if stats:
                    return {
                        'total_examples': stats['total_examples'],
                        'learned_examples': stats['learned_examples'],
                        'bootstrap_examples': stats['bootstrap_examples'],
                        'avg_quality': float(stats['avg_quality']) if stats['avg_quality'] else 0,
                        'avg_success_rate': float(stats['avg_success_rate']) if stats['avg_success_rate'] else 0,
                        'total_usage': stats['total_usage'],
                        'thumbs_up': stats['thumbs_up'],
                        'thumbs_down': stats['thumbs_down'],
                        'satisfaction_rate': (
                            stats['thumbs_up'] / (stats['thumbs_up'] + stats['thumbs_down'])
                            if (stats['thumbs_up'] + stats['thumbs_down']) > 0 else 0
                        )
                    }
                
                return {}
                
            except Exception as e:
                self.logger.error(f"Failed to get learning stats: {e}")
                return {}
    
    async def _assess_example_quality(
        self,
        query: str,
        response: str,
        context_sources: Optional[Dict[str, Any]],
        response_time_ms: Optional[int]
    ) -> float:
        """
        Assess quality of an example based on multiple criteria.
        
        Args:
            query: User query
            response: AI response
            context_sources: Sources used
            response_time_ms: Response time
            
        Returns:
            Quality score (0-1)
        """
        score = 0.5  # Base score
        
        # Length and completeness (0.2 weight)
        if len(query) > 20 and len(response) > 100:
            score += 0.2
        
        # Has sources (0.2 weight)
        if context_sources and len(context_sources.get('sources', [])) > 0:
            score += 0.2
        
        # Response time (0.1 weight)
        if response_time_ms and response_time_ms < 3000:  # Under 3 seconds
            score += 0.1
        
        return min(1.0, score)
    
    async def _is_example_novel(
        self,
        executive_id: str,
        query: str,
        response: str
    ) -> bool:
        """
        Check if example is novel enough to add.
        
        Args:
            executive_id: Executive ID
            query: Query text
            response: Response text
            
        Returns:
            True if example is novel
        """
        # Create similarity hash
        content = f"{query.lower().strip()}|{response.lower().strip()}"
        similarity_hash = hashlib.md5(content.encode()).hexdigest()
        
        async with self.db_pool.acquire() as conn:
            try:
                existing = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM communication_examples
                    WHERE executive_id = $1
                      AND similarity_hash = $2
                      AND is_active = true
                    """,
                    executive_id,
                    similarity_hash
                )
                
                return existing == 0
                
            except Exception as e:
                self.logger.error(f"Failed to check novelty: {e}")
                return True  # Assume novel if check fails
    
    def _classify_example_type(self, query: str, response: str) -> str:
        """
        Classify the type of example based on content.
        
        Args:
            query: Query text
            response: Response text
            
        Returns:
            Example type (email, slack, formal, casual, general)
        """
        query_lower = query.lower()
        response_lower = response.lower()
        
        # Check for email indicators
        if any(indicator in query_lower or indicator in response_lower 
               for indicator in ['email', 'mail', 'subject:', 'to:', 'from:']):
            return 'email'
        
        # Check for Slack indicators
        if any(indicator in query_lower or indicator in response_lower 
               for indicator in ['slack', 'channel', '@', 'dm']):
            return 'slack'
        
        # Check formality
        formal_indicators = ['dear', 'sincerely', 'regards', 'best regards']
        if any(indicator in response_lower for indicator in formal_indicators):
            return 'formal'
        
        casual_indicators = ['hey', 'hi', 'thanks', 'cool', 'awesome']
        if any(indicator in response_lower for indicator in casual_indicators):
            return 'casual'
        
        return 'general'
    
    def _classify_query_type(self, query: str) -> str:
        """
        Classify the type of query.
        
        Args:
            query: Query text
            
        Returns:
            Query type (approval, recommendation, information, decision, strategy, general)
        """
        query_lower = query.lower()
        
        # Approval queries
        if any(indicator in query_lower 
               for indicator in ['approve', 'approval', 'should we', 'can i']):
            return 'approval'
        
        # Recommendation queries
        if any(indicator in query_lower 
               for indicator in ['recommend', 'suggest', 'advice', 'what should']):
            return 'recommendation'
        
        # Information queries
        if any(indicator in query_lower 
               for indicator in ['what is', 'who is', 'show me', 'find', 'tell me about']):
            return 'information'
        
        # Decision queries
        if any(indicator in query_lower 
               for indicator in ['decide', 'decision', 'choose', 'select']):
            return 'decision'
        
        # Strategy queries
        if any(indicator in query_lower 
               for indicator in ['strategy', 'plan', 'approach', 'how should we']):
            return 'strategy'
        
        return 'general'
    
    async def _ensure_example_limit(
        self,
        executive_id: str,
        conn: Connection
    ) -> None:
        """
        Ensure executive doesn't exceed maximum examples.
        
        Args:
            executive_id: Executive ID
            conn: Database connection
        """
        try:
            await conn.execute(
                "SELECT prune_old_examples($1, $2, $3)",
                executive_id,
                self.max_examples_per_executive,
                self.min_quality_threshold
            )
        except Exception as e:
            self.logger.error(f"Failed to ensure example limit: {e}")