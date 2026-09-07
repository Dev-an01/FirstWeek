"""
Feedback Processor

Processes user feedback to improve the few-shot learning system.
Implements feedback collection, quality assessment, and learning triggers.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import uuid

import asyncpg
from asyncpg import Connection

from .dynamic_examples import DynamicExamples

logger = logging.getLogger(__name__)


class FeedbackProcessor:
    """
    Processes user feedback to improve the few-shot learning system.
    
    Handles:
    - Feedback collection from various sources
    - Quality assessment and scoring
    - Learning triggers for successful interactions
    - Feedback aggregation and analysis
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        learning_threshold: float = 0.8,
        feedback_window_hours: int = 24,
        min_feedback_for_learning: int = 3
    ):
        """
        Initialize FeedbackProcessor.
        
        Args:
            db_pool: PostgreSQL connection pool
            learning_threshold: Success rate threshold to trigger learning
            feedback_window_hours: Hours to consider for feedback aggregation
            min_feedback_for_learning: Minimum feedback count for learning
        """
        self.db_pool = db_pool
        self.learning_threshold = learning_threshold
        self.feedback_window_hours = feedback_window_hours
        self.min_feedback_for_learning = min_feedback_for_learning
        
        # Initialize dynamic examples manager
        self.dynamic_examples = DynamicExamples(db_pool)
        
        self.logger = logging.getLogger(__name__)
    
    async def process_feedback(
        self,
        interaction_id: str,
        executive_id: str,
        user_id: str,
        feedback: int,
        feedback_type: str = "thumbs",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Process user feedback on an interaction.
        
        Args:
            interaction_id: ID of the interaction
            executive_id: Executive profile ID
            user_id: User who provided feedback
            feedback: Feedback value (1=👍, -1=👎, 0=neutral)
            feedback_type: Type of feedback (thumbs, rating, comment)
            metadata: Additional feedback metadata
            
        Returns:
            True if processed successfully
        """
        try:
            # Store feedback in episodic memory
            success = await self._store_feedback(
                interaction_id, executive_id, user_id, feedback, 
                feedback_type, metadata
            )
            
            if not success:
                return False
            
            # Update example usage if this was a learned example
            if feedback == 1:  # Thumbs up
                await self._update_example_success(interaction_id)
            
            # Check if we should trigger learning
            await self._check_learning_trigger(executive_id)
            
            self.logger.info(
                f"Processed feedback {feedback} for interaction {interaction_id}"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process feedback: {e}")
            return False
    
    async def get_feedback_analytics(
        self,
        executive_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get feedback analytics for monitoring.
        
        Args:
            executive_id: Specific executive ID, or None for all
            days: Number of days to analyze
            
        Returns:
            Analytics dictionary
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Get feedback statistics
                if executive_id:
                    stats = await conn.fetchrow(
                        """
                        SELECT 
                            COUNT(*) as total_interactions,
                            COUNT(CASE WHEN user_feedback = 1 THEN 1 END) as thumbs_up,
                            COUNT(CASE WHEN user_feedback = -1 THEN 1 END) as thumbs_down,
                            COUNT(CASE WHEN user_feedback = 0 THEN 1 END) as neutral,
                            AVG(CASE WHEN user_feedback = 1 THEN 1.0 
                                WHEN user_feedback = -1 THEN 0.0 
                                ELSE 0.5 END) as avg_score
                        FROM episodic_memory
                        WHERE executive_id = $1
                          AND timestamp >= NOW() - INTERVAL '%s days'
                        """,
                        executive_id,
                        days
                    )
                    
                    # Get daily feedback trends
                    daily_trends = await conn.fetch(
                        """
                        SELECT 
                            DATE(timestamp) as date,
                            COUNT(*) as interactions,
                            COUNT(CASE WHEN user_feedback = 1 THEN 1 END) as thumbs_up,
                            COUNT(CASE WHEN user_feedback = -1 THEN 1 END) as thumbs_down,
                            AVG(CASE WHEN user_feedback = 1 THEN 1.0 
                                WHEN user_feedback = -1 THEN 0.0 
                                ELSE 0.5 END) as avg_score
                        FROM episodic_memory
                        WHERE executive_id = $1
                          AND timestamp >= NOW() - INTERVAL '%s days'
                        GROUP BY DATE(timestamp)
                        ORDER BY date DESC
                        """,
                        executive_id,
                        days
                    )
                    
                    # Get feedback by query type
                    query_type_stats = await conn.fetch(
                        """
                        SELECT 
                            query_type,
                            COUNT(*) as count,
                            COUNT(CASE WHEN user_feedback = 1 THEN 1 END) as thumbs_up,
                            COUNT(CASE WHEN user_feedback = -1 THEN 1 END) as thumbs_down,
                            AVG(CASE WHEN user_feedback = 1 THEN 1.0 
                                WHEN user_feedback = -1 THEN 0.0 
                                ELSE 0.5 END) as avg_score
                        FROM episodic_memory
                        WHERE executive_id = $1
                          AND timestamp >= NOW() - INTERVAL '%s days'
                          AND query_type IS NOT NULL
                        GROUP BY query_type
                        ORDER BY count DESC
                        """,
                        executive_id,
                        days
                    )
                else:
                    # Get stats for all executives
                    stats = await conn.fetchrow(
                        """
                        SELECT 
                            COUNT(*) as total_interactions,
                            COUNT(CASE WHEN user_feedback = 1 THEN 1 END) as thumbs_up,
                            COUNT(CASE WHEN user_feedback = -1 THEN 1 END) as thumbs_down,
                            COUNT(CASE WHEN user_feedback = 0 THEN 1 END) as neutral,
                            AVG(CASE WHEN user_feedback = 1 THEN 1.0 
                                WHEN user_feedback = -1 THEN 0.0 
                                ELSE 0.5 END) as avg_score
                        FROM episodic_memory
                        WHERE timestamp >= NOW() - INTERVAL '%s days'
                        """,
                        days
                    )
                    
                    # Get daily trends for all executives
                    daily_trends = await conn.fetch(
                        """
                        SELECT 
                            DATE(timestamp) as date,
                            COUNT(*) as interactions,
                            COUNT(CASE WHEN user_feedback = 1 THEN 1 END) as thumbs_up,
                            COUNT(CASE WHEN user_feedback = -1 THEN 1 END) as thumbs_down,
                            AVG(CASE WHEN user_feedback = 1 THEN 1.0 
                                WHEN user_feedback = -1 THEN 0.0 
                                ELSE 0.5 END) as avg_score
                        FROM episodic_memory
                        WHERE timestamp >= NOW() - INTERVAL '%s days'
                        GROUP BY DATE(timestamp)
                        ORDER BY date DESC
                        """,
                        days
                    )
                    
                    # Get query type stats for all executives
                    query_type_stats = await conn.fetch(
                        """
                        SELECT 
                            query_type,
                            COUNT(*) as count,
                            COUNT(CASE WHEN user_feedback = 1 THEN 1 END) as thumbs_up,
                            COUNT(CASE WHEN user_feedback = -1 THEN 1 END) as thumbs_down,
                            AVG(CASE WHEN user_feedback = 1 THEN 1.0 
                                WHEN user_feedback = -1 THEN 0.0 
                                ELSE 0.5 END) as avg_score
                        FROM episodic_memory
                        WHERE timestamp >= NOW() - INTERVAL '%s days'
                          AND query_type IS NOT NULL
                        GROUP BY query_type
                        ORDER BY count DESC
                        """,
                        days
                    )
                
                # Build analytics result
                result = {
                    'period_days': days,
                    'total_interactions': stats['total_interactions'],
                    'thumbs_up': stats['thumbs_up'],
                    'thumbs_down': stats['thumbs_down'],
                    'neutral': stats['neutral'],
                    'avg_score': float(stats['avg_score']) if stats['avg_score'] else 0.5,
                    'satisfaction_rate': (
                        stats['thumbs_up'] / stats['total_interactions']
                        if stats['total_interactions'] > 0 else 0
                    ),
                    'daily_trends': [
                        {
                            'date': row['date'].isoformat(),
                            'interactions': row['interactions'],
                            'thumbs_up': row['thumbs_up'],
                            'thumbs_down': row['thumbs_down'],
                            'avg_score': float(row['avg_score'])
                        }
                        for row in daily_trends
                    ],
                    'query_type_stats': [
                        {
                            'query_type': row['query_type'],
                            'count': row['count'],
                            'thumbs_up': row['thumbs_up'],
                            'thumbs_down': row['thumbs_down'],
                            'avg_score': float(row['avg_score'])
                        }
                        for row in query_type_stats
                    ]
                }
                
                return result
                
        except Exception as e:
            self.logger.error(f"Failed to get feedback analytics: {e}")
            return {}
    
    async def identify_learning_opportunities(
        self,
        executive_id: str,
        min_success_rate: float = 0.8,
        min_interactions: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Identify opportunities for learning from successful interactions.
        
        Args:
            executive_id: Executive profile ID
            min_success_rate: Minimum success rate threshold
            min_interactions: Minimum interactions to consider
            
        Returns:
            List of learning opportunities
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Find query patterns with high success rates
                opportunities = await conn.fetch(
                    """
                    WITH query_patterns AS (
                        SELECT 
                            -- Extract key terms from query
                            REGEXP_REPLACE(
                                REGEXP_REPLACE(LOWER(query), '[^a-z0-9\s]', ' ', ' '),
                                '\s+', ' '
                            ) as query_pattern,
                            COUNT(*) as interactions,
                            COUNT(CASE WHEN user_feedback = 1 THEN 1 END) as successes,
                            AVG(CASE WHEN user_feedback = 1 THEN 1.0 
                                WHEN user_feedback = -1 THEN 0.0 
                                ELSE 0.5 END) as avg_score,
                            STRING_AGG(DISTINCT query_type) as query_types,
                            MAX(timestamp) as last_interaction
                        FROM episodic_memory
                        WHERE executive_id = $1
                          AND timestamp >= NOW() - INTERVAL '30 days'
                        GROUP BY 
                            REGEXP_REPLACE(
                                REGEXP_REPLACE(LOWER(query), '[^a-z0-9\s]', ' ', ' '),
                                '\s+', ' '
                            )
                        HAVING COUNT(*) >= $2
                    )
                    SELECT 
                        query_pattern,
                        interactions,
                        successes,
                        avg_score,
                        query_types,
                        last_interaction,
                        -- Check if this pattern has learned examples
                        EXISTS(
                            SELECT 1 FROM communication_examples ce
                            WHERE ce.executive_id = $1
                              AND ce.is_active = true
                              AND LOWER(ce.query) LIKE '%' || query_pattern || '%'
                        ) as has_learned_example
                    FROM query_patterns
                    WHERE avg_score >= $3
                      AND successes >= $4
                      AND NOT has_learned_example
                    ORDER BY avg_score DESC, successes DESC
                    LIMIT 10
                    """,
                    executive_id,
                    min_interactions,
                    min_success_rate,
                    min_interactions
                )
                
                # Convert to dictionaries
                result = []
                for row in opportunities:
                    result.append({
                        'query_pattern': row['query_pattern'],
                        'interactions': row['interactions'],
                        'successes': row['successes'],
                        'success_rate': row['successes'] / row['interactions'],
                        'avg_score': float(row['avg_score']),
                        'query_types': row['query_types'].split(',') if row['query_types'] else [],
                        'last_interaction': row['last_interaction'].isoformat(),
                        'has_learned_example': row['has_learned_example']
                    })
                
                self.logger.info(
                    f"Found {len(result)} learning opportunities for {executive_id}"
                )
                
                return result
                
        except Exception as e:
            self.logger.error(f"Failed to identify learning opportunities: {e}")
            return []
    
    async def generate_learning_report(
        self,
        executive_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Generate comprehensive learning report.
        
        Args:
            executive_id: Specific executive ID, or None for all
            days: Number of days to analyze
            
        Returns:
            Learning report dictionary
        """
        try:
            # Get feedback analytics
            analytics = await self.get_feedback_analytics(executive_id, days)
            
            # Get learning opportunities
            opportunities = []
            if executive_id:
                opportunities = await self.identify_learning_opportunities(
                    executive_id
                )
            
            # Get learning statistics from dynamic examples
            learning_stats = await self.dynamic_examples.get_learning_stats(executive_id)
            
            # Build report
            report = {
                'executive_id': executive_id,
                'report_period_days': days,
                'generated_at': datetime.utcnow().isoformat(),
                'feedback_analytics': analytics,
                'learning_opportunities': opportunities,
                'learning_statistics': learning_stats,
                'recommendations': await self._generate_recommendations(
                    analytics, opportunities, learning_stats
                )
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"Failed to generate learning report: {e}")
            return {}
    
    async def _store_feedback(
        self,
        interaction_id: str,
        executive_id: str,
        user_id: str,
        feedback: int,
        feedback_type: str,
        metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Store feedback in episodic memory.
        
        Args:
            interaction_id: ID of the interaction
            executive_id: Executive profile ID
            user_id: User who provided feedback
            feedback: Feedback value
            feedback_type: Type of feedback
            metadata: Additional feedback metadata
            
        Returns:
            True if stored successfully
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE episodic_memory
                    SET 
                        user_feedback = $1,
                        feedback_type = $2,
                        feedback_metadata = $3,
                        feedback_timestamp = NOW()
                    WHERE id = $4
                      AND executive_id = $5
                    """,
                    feedback,
                    feedback_type,
                    json.dumps(metadata or {}),
                    uuid.UUID(interaction_id),
                    executive_id
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to store feedback: {e}")
            return False
    
    async def _update_example_success(
        self,
        interaction_id: str
    ) -> None:
        """
        Update example success based on positive feedback.
        
        Args:
            interaction_id: ID of the interaction
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Find if this interaction has a learned example
                example_id = await conn.fetchval(
                    """
                    SELECT ce.id FROM communication_examples ce
                    JOIN episodic_memory em ON ce.executive_id = em.executive_id
                    WHERE em.id = $1
                      AND ce.is_active = true
                      AND ce.is_bootstrap = false
                      AND (
                          ce.query = em.query OR
                          ce.response = em.response
                      )
                    LIMIT 1
                    """,
                    uuid.UUID(interaction_id)
                )
                
                if example_id:
                    # Update example usage and success
                    await self.dynamic_examples.update_example_usage(
                        str(example_id), success=True
                    )
                    
                    self.logger.debug(
                        f"Updated success for example {example_id} "
                        f"from interaction {interaction_id}"
                    )
                
        except Exception as e:
            self.logger.error(f"Failed to update example success: {e}")
    
    async def _check_learning_trigger(
        self,
        executive_id: str
    ) -> None:
        """
        Check if learning should be triggered based on feedback.
        
        Args:
            executive_id: Executive profile ID
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Get recent feedback statistics
                stats = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) as total_feedback,
                        COUNT(CASE WHEN user_feedback = 1 THEN 1 END) as thumbs_up,
                        AVG(CASE WHEN user_feedback = 1 THEN 1.0 
                            WHEN user_feedback = -1 THEN 0.0 
                            ELSE 0.5 END) as avg_score
                    FROM episodic_memory
                    WHERE executive_id = $1
                      AND user_feedback IS NOT NULL
                      AND feedback_timestamp >= NOW() - INTERVAL '%s hours'
                    """,
                    executive_id,
                    self.feedback_window_hours
                )
                
                if not stats or stats['total_feedback'] < self.min_feedback_for_learning:
                    return
                
                # Check if we meet learning threshold
                if stats['avg_score'] >= self.learning_threshold:
                    self.logger.info(
                        f"Learning threshold met for {executive_id}: "
                        f"avg_score={stats['avg_score']:.2f}"
                    )
                    
                    # Trigger learning from successful interactions
                    await self._trigger_learning(executive_id, conn)
                
        except Exception as e:
            self.logger.error(f"Failed to check learning trigger: {e}")
    
    async def _trigger_learning(
        self,
        executive_id: str,
        conn: Connection
    ) -> None:
        """
        Trigger learning from successful interactions.
        
        Args:
            executive_id: Executive profile ID
            conn: Database connection
        """
        try:
            # Find successful interactions without learned examples
            successful_interactions = await conn.fetch(
                """
                SELECT 
                    id,
                    query,
                    response,
                    user_feedback,
                    context_sources,
                    query_type,
                    timestamp,
                    embedding
                FROM episodic_memory
                WHERE executive_id = $1
                  AND user_feedback = 1
                  AND timestamp >= NOW() - INTERVAL '24 hours'
                  AND id NOT IN (
                      SELECT em.id FROM episodic_memory em
                      JOIN communication_examples ce ON (
                          ce.executive_id = em.executive_id AND
                          ce.is_active = true AND
                          ce.is_bootstrap = false AND
                          (ce.query = em.query OR ce.response = em.response)
                      )
                      WHERE em.executive_id = $1
                  )
                ORDER BY timestamp DESC
                LIMIT 10
                """,
                executive_id
            )
            
            # Learn from each successful interaction
            for interaction in successful_interactions:
                await self.dynamic_examples.learn_from_interaction(
                    executive_id=executive_id,
                    query=interaction['query'],
                    response=interaction['response'],
                    user_feedback=interaction['user_feedback'],
                    context_sources=interaction['context_sources'],
                    query_type=interaction['query_type'],
                    embedding=interaction['embedding']
                )
            
            self.logger.info(
                f"Triggered learning from {len(successful_interactions)} "
                f"successful interactions for {executive_id}"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to trigger learning: {e}")
    
    async def _generate_recommendations(
        self,
        analytics: Dict[str, Any],
        opportunities: List[Dict[str, Any]],
        learning_stats: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on analytics.
        
        Args:
            analytics: Feedback analytics
            opportunities: Learning opportunities
            learning_stats: Learning statistics
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Low satisfaction recommendation
        if analytics.get('satisfaction_rate', 0) < 0.7:
            recommendations.append({
                'type': 'improvement',
                'priority': 'high',
                'title': 'Low User Satisfaction',
                'description': (
                    f"Satisfaction rate is {analytics['satisfaction_rate']:.1%}, "
                    "below target of 70%. Review response quality and tone."
                ),
                'action': 'Review and adjust communication style'
            })
        
        # Learning opportunities recommendation
        if opportunities:
            recommendations.append({
                'type': 'learning',
                'priority': 'medium',
                'title': 'Learning Opportunities Available',
                'description': (
                    f"Found {len(opportunities)} query patterns with high success rates "
                    "that could be learned from."
                ),
                'action': 'Review and approve learning opportunities'
            })
        
        # Low example quality recommendation
        if learning_stats.get('avg_quality', 1.0) < 0.5:
            recommendations.append({
                'type': 'quality',
                'priority': 'medium',
                'title': 'Low Example Quality',
                'description': (
                    f"Average example quality is {learning_stats['avg_quality']:.2f}, "
                    "below recommended threshold of 0.5."
                ),
                'action': 'Improve example quality assessment'
            })
        
        # Too many examples recommendation
        if learning_stats.get('learned_examples', 0) > 15:
            recommendations.append({
                'type': 'maintenance',
                'priority': 'low',
                'title': 'Example Pool Maintenance',
                'description': (
                    f"Executive has {learning_stats['learned_examples']} learned examples, "
                    "consider pruning low-quality examples."
                ),
                'action': 'Run example pruning process'
            })
        
        return recommendations