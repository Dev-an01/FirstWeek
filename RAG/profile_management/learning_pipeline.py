"""
Learning Pipeline

Orchestrates the dynamic few-shot learning process.
Coordinates between dynamic examples, example selection, and feedback processing.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import uuid

import asyncpg
from asyncpg import Connection

from .dynamic_examples import DynamicExamples
from .example_selector import ExampleSelector
from .feedback_processor import FeedbackProcessor

logger = logging.getLogger(__name__)


class LearningPipeline:
    """
    Orchestrates the dynamic few-shot learning process.
    
    Coordinates:
    - Learning from successful interactions
    - Example selection for prompts
    - Feedback processing and quality assessment
    - Example lifecycle management
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        learning_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize LearningPipeline.
        
        Args:
            db_pool: PostgreSQL connection pool
            learning_config: Configuration for learning process
        """
        self.db_pool = db_pool
        
        # Default configuration
        default_config = {
            'learning_enabled': True,
            'auto_learning': True,
            'learning_threshold': 0.8,
            'min_feedback_for_learning': 3,
            'max_examples_per_executive': 20,
            'example_expiry_days': 90,
            'pruning_interval_hours': 24,
            'diversity_factor': 0.3,
            'recency_weight': 0.25,
            'quality_weight': 0.4,
            'usage_weight': 0.05
        }
        
        # Merge with provided config
        self.config = {**default_config, **(learning_config or {})}
        
        # Initialize components
        self.dynamic_examples = DynamicExamples(
            db_pool=db_pool,
            min_quality_threshold=self.config.get('min_quality_threshold', 0.3),
            max_examples_per_executive=self.config.get('max_examples_per_executive', 20),
            example_expiry_days=self.config.get('example_expiry_days', 90)
        )
        
        self.example_selector = ExampleSelector(
            db_pool=db_pool,
            max_bootstrap=self.config.get('max_bootstrap', 3),
            max_learned=self.config.get('max_learned', 2),
            diversity_factor=self.config.get('diversity_factor', 0.3),
            recency_weight=self.config.get('recency_weight', 0.25),
            quality_weight=self.config.get('quality_weight', 0.4),
            usage_weight=self.config.get('usage_weight', 0.05)
        )
        
        self.feedback_processor = FeedbackProcessor(
            db_pool=db_pool,
            learning_threshold=self.config.get('learning_threshold', 0.8),
            feedback_window_hours=self.config.get('feedback_window_hours', 24),
            min_feedback_for_learning=self.config.get('min_feedback_for_learning', 3)
        )
        
        self.logger = logging.getLogger(__name__)
        
        # Background task reference
        self._pruning_task = None
    
    async def initialize(self):
        """
        Initialize the learning pipeline.
        
        Starts background tasks for maintenance.
        """
        if not self.config.get('learning_enabled', True):
            self.logger.info("Learning pipeline is disabled")
            return
        
        self.logger.info("Initializing learning pipeline")
        
        # Start background pruning task
        self._pruning_task = asyncio.create_task(self._pruning_loop())
        
        # Load bootstrap examples if needed
        await self._ensure_bootstrap_examples()
        
        self.logger.info("Learning pipeline initialized successfully")
    
    async def shutdown(self):
        """
        Shutdown the learning pipeline.
        
        Stops background tasks.
        """
        self.logger.info("Shutting down learning pipeline")
        
        # Cancel background task
        if self._pruning_task:
            self._pruning_task.cancel()
            try:
                await self._pruning_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Learning pipeline shutdown complete")
    
    async def process_interaction(
        self,
        executive_id: str,
        user_id: str,
        query: str,
        response: str,
        context_sources: Optional[Dict[str, Any]] = None,
        query_type: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        embedding: Optional[List[float]] = None,
        session_id: Optional[str] = None,
        company_id: Optional[str] = None
    ) -> str:
        """
        Process a complete interaction for learning.
        
        Args:
            executive_id: Executive profile ID
            user_id: User ID
            query: User's query
            response: AI's response
            context_sources: Sources used in response
            query_type: Type of query
            response_time_ms: Response time in milliseconds
            embedding: Query embedding vector
            session_id: Session ID
            
        Returns:
            Interaction ID for feedback tracking
        """
        try:
            # Generate interaction ID
            interaction_id = str(uuid.uuid4())
            
            # Store in episodic memory
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO episodic_memory (
                        id, executive_id, user_id, query, response,
                        context_sources, query_type, timestamp, embedding,
                        session_id, importance_score, company_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    uuid.UUID(interaction_id),
                    executive_id,
                    user_id,
                    query,
                    response,
                    json.dumps(context_sources or {}),
                    query_type,
                    datetime.utcnow(),
                    embedding,
                    session_id,
                    0.5,  # Default importance
                    company_id
                )
            
            # Trigger auto-learning if enabled
            if self.config.get('auto_learning', True):
                # Simulate positive feedback for high-quality responses
                # In real implementation, this would wait for actual user feedback
                quality_score = await self.dynamic_examples._assess_example_quality(
                    query, response, context_sources, response_time_ms
                )
                
                # Auto-learn from high-quality interactions
                if quality_score >= 0.7:
                    await self.dynamic_examples.learn_from_interaction(
                        executive_id=executive_id,
                        query=query,
                        response=response,
                        user_feedback=1,  # Simulate thumbs up
                        context_sources=context_sources,
                        query_type=query_type,
                        response_time_ms=response_time_ms,
                        embedding=embedding
                    )
                    
                    self.logger.debug(
                        f"Auto-learned from high-quality interaction "
                        f"{interaction_id} (quality={quality_score:.2f})"
                    )
            
            self.logger.debug(f"Processed interaction {interaction_id}")
            return interaction_id
            
        except Exception as e:
            self.logger.error(f"Failed to process interaction: {e}")
            return str(uuid.uuid4())  # Return ID even if processing fails
    
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
            feedback_type: Type of feedback
            metadata: Additional feedback metadata
            
        Returns:
            True if processed successfully
        """
        try:
            # Process feedback through feedback processor
            success = await self.feedback_processor.process_feedback(
                interaction_id=interaction_id,
                executive_id=executive_id,
                user_id=user_id,
                feedback=feedback,
                feedback_type=feedback_type,
                metadata=metadata
            )
            
            if success and feedback == 1:
                # Trigger learning for positive feedback
                await self._trigger_learning_from_feedback(
                    interaction_id, executive_id
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to process feedback: {e}")
            return False
    
    async def get_examples_for_prompt(
        self,
        executive_id: str,
        query: Optional[str] = None,
        query_type: Optional[str] = None,
        context_sources: Optional[List[Dict[str, Any]]] = None,
        max_examples: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get examples for prompt generation.
        
        Args:
            executive_id: Executive profile ID
            query: Current query for similarity matching
            query_type: Optional query type filter
            context_sources: Sources used in current query
            max_examples: Maximum examples to return
            
        Returns:
            List of examples for prompt
        """
        try:
            # Get bootstrap examples
            bootstrap_examples = self.example_selector.select_bootstrap_examples(
                {'id': executive_id}  # Mock profile dict
            )
            
            # Get learned examples
            learned_examples = await self.example_selector.select_learned_examples(
                executive_id=executive_id,
                query=query,
                query_type=query_type,
                context_sources=context_sources,
                max_examples=max_examples - len(bootstrap_examples)
            )
            
            # Get context-relevant examples if context provided
            context_examples = []
            if context_sources and len(learned_examples) < max_examples:
                context_examples = await self.example_selector.select_context_relevant_examples(
                    executive_id=executive_id,
                    query=query or "",
                    context_sources=context_sources,
                    max_examples=max_examples - len(bootstrap_examples) - len(learned_examples)
                )
            
            # Combine and format examples
            all_examples = bootstrap_examples + learned_examples + context_examples
            
            # Limit to max_examples
            all_examples = all_examples[:max_examples]
            
            # Format examples for prompt
            formatted_examples = []
            for i, example in enumerate(all_examples, 1):
                if isinstance(example, dict):
                    formatted_examples.append({
                        'id': example.get('id', f"example_{i}"),
                        'content': self.example_selector.format_example_for_prompt(example),
                        'type': example.get('example_type', 'general'),
                        'is_bootstrap': example.get('is_bootstrap', True)
                    })
                else:
                    # Handle bootstrap examples from profile
                    formatted_examples.append({
                        'id': f"bootstrap_{i}",
                        'content': example,
                        'type': 'bootstrap',
                        'is_bootstrap': True
                    })
            
            self.logger.debug(
                f"Retrieved {len(formatted_examples)} examples for {executive_id}"
            )
            
            return formatted_examples
            
        except Exception as e:
            self.logger.error(f"Failed to get examples for prompt: {e}")
            return []
    
    async def get_learning_dashboard(
        self,
        executive_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get learning dashboard data.
        
        Args:
            executive_id: Specific executive ID, or None for all
            days: Number of days to analyze
            
        Returns:
            Dashboard data dictionary
        """
        try:
            # Get feedback analytics
            feedback_analytics = await self.feedback_processor.get_feedback_analytics(
                executive_id, days
            )
            
            # Get learning statistics
            learning_stats = await self.dynamic_examples.get_learning_stats(
                executive_id
            )
            
            # Get learning opportunities
            learning_opportunities = []
            if executive_id:
                learning_opportunities = await self.feedback_processor.identify_learning_opportunities(
                    executive_id
                )
            
            # Get example quality distribution
            quality_distribution = await self._get_quality_distribution(executive_id)
            
            # Get learning trends
            learning_trends = await self._get_learning_trends(executive_id, days)
            
            # Build dashboard
            dashboard = {
                'executive_id': executive_id,
                'period_days': days,
                'generated_at': datetime.utcnow().isoformat(),
                'feedback_analytics': feedback_analytics,
                'learning_statistics': learning_stats,
                'learning_opportunities': learning_opportunities,
                'quality_distribution': quality_distribution,
                'learning_trends': learning_trends,
                'configuration': self.config
            }
            
            return dashboard
            
        except Exception as e:
            self.logger.error(f"Failed to get learning dashboard: {e}")
            return {}
    
    async def update_configuration(
        self,
        new_config: Dict[str, Any]
    ) -> bool:
        """
        Update learning pipeline configuration.
        
        Args:
            new_config: New configuration values
            
        Returns:
            True if updated successfully
        """
        try:
            # Update configuration
            self.config.update(new_config)
            
            # Reinitialize components with new config
            self.dynamic_examples = DynamicExamples(
                db_pool=self.db_pool,
                min_quality_threshold=self.config.get('min_quality_threshold', 0.3),
                max_examples_per_executive=self.config.get('max_examples_per_executive', 20),
                example_expiry_days=self.config.get('example_expiry_days', 90)
            )
            
            self.example_selector = ExampleSelector(
                db_pool=self.db_pool,
                max_bootstrap=self.config.get('max_bootstrap', 3),
                max_learned=self.config.get('max_learned', 2),
                diversity_factor=self.config.get('diversity_factor', 0.3),
                recency_weight=self.config.get('recency_weight', 0.25),
                quality_weight=self.config.get('quality_weight', 0.4),
                usage_weight=self.config.get('usage_weight', 0.05)
            )
            
            self.feedback_processor = FeedbackProcessor(
                db_pool=self.db_pool,
                learning_threshold=self.config.get('learning_threshold', 0.8),
                feedback_window_hours=self.config.get('feedback_window_hours', 24),
                min_feedback_for_learning=self.config.get('min_feedback_for_learning', 3)
            )
            
            self.logger.info(f"Updated learning pipeline configuration: {new_config}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update configuration: {e}")
            return False
    
    async def _ensure_bootstrap_examples(self) -> None:
        """
        Ensure bootstrap examples are loaded.
        
        This would load examples from executive profiles into the
        communication_examples table with is_bootstrap=true.
        """
        try:
            # Get all executive profiles (with company_id for tenant isolation)
            async with self.db_pool.acquire() as conn:
                exec_profiles = await conn.fetch(
                    "SELECT id, company_id, profile_data FROM executive_profiles WHERE profile_data IS NOT NULL"
                )

                for profile in exec_profiles:
                    executive_id = profile['id']
                    exec_company_id = profile.get('company_id')
                    profile_data = profile['profile_data']
                    
                    # Check if bootstrap examples already loaded
                    existing_count = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM communication_examples
                        WHERE executive_id = $1 AND is_bootstrap = true
                        """,
                        executive_id
                    )
                    
                    if existing_count > 0:
                        self.logger.debug(
                            f"Bootstrap examples already loaded for {executive_id}"
                        )
                        continue
                    
                    # Extract communication examples from profile
                    comm_examples = profile_data.get('communication_examples', [])
                    
                    # Load bootstrap examples
                    for example in comm_examples:
                        await conn.execute(
                            """
                            INSERT INTO communication_examples (
                                executive_id, query, response, user_feedback,
                                quality_score, example_type, query_type,
                                context_sources, timestamp, is_bootstrap,
                                usage_count, success_rate
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                            """,
                            executive_id,
                            example.get('context', ''),
                            example.get('full_text', example.get('text', '')),
                            1,  # Assume positive feedback for bootstrap
                            0.8,  # High quality for bootstrap
                            example.get('type', 'general'),
                            None,  # Query type not specified
                            json.dumps({}),  # Empty context sources
                            datetime.utcnow(),
                            True,  # Bootstrap example
                            0,  # No usage yet
                            1.0  # Perfect success rate
                        )
                    
                    self.logger.info(
                        f"Loaded {len(comm_examples)} bootstrap examples for {executive_id}"
                    )
        
        except Exception as e:
            self.logger.error(f"Failed to ensure bootstrap examples: {e}")
    
    async def _trigger_learning_from_feedback(
        self,
        interaction_id: str,
        executive_id: str
    ) -> None:
        """
        Trigger learning from positive feedback.
        
        Args:
            interaction_id: Interaction ID
            executive_id: Executive ID
        """
        try:
            # Get interaction details
            async with self.db_pool.acquire() as conn:
                interaction = await conn.fetchrow(
                    """
                    SELECT query, response, context_sources, query_type,
                           embedding, timestamp
                    FROM episodic_memory
                    WHERE id = $1 AND executive_id = $2
                    """,
                    uuid.UUID(interaction_id),
                    executive_id
                )
                
                if not interaction:
                    self.logger.warning(
                        f"Interaction {interaction_id} not found for learning"
                    )
                    return
                
                # Learn from this interaction
                await self.dynamic_examples.learn_from_interaction(
                    executive_id=executive_id,
                    query=interaction['query'],
                    response=interaction['response'],
                    user_feedback=1,  # Positive feedback
                    context_sources=interaction['context_sources'],
                    query_type=interaction['query_type'],
                    response_time_ms=None,  # Not available
                    embedding=interaction['embedding']
                )
                
                self.logger.info(
                    f"Triggered learning from positive feedback "
                    f"for interaction {interaction_id}"
                )
        
        except Exception as e:
            self.logger.error(f"Failed to trigger learning from feedback: {e}")
    
    async def _pruning_loop(self) -> None:
        """
        Background task to prune old examples.
        
        Runs at configured intervals.
        """
        self.logger.info("Starting example pruning loop")
        
        while True:
            try:
                # Wait for pruning interval
                await asyncio.sleep(
                    self.config.get('pruning_interval_hours', 24) * 3600
                )
                
                # Prune examples for all executives
                pruned = await self.dynamic_examples.prune_examples()
                
                if pruned > 0:
                    self.logger.info(f"Pruned {pruned} old examples")
                
            except asyncio.CancelledError:
                self.logger.info("Pruning loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in pruning loop: {e}")
    
    async def _get_quality_distribution(
        self,
        executive_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Get quality distribution of examples.
        
        Args:
            executive_id: Specific executive ID, or None for all
            
        Returns:
            Quality distribution data
        """
        try:
            async with self.db_pool.acquire() as conn:
                if executive_id:
                    # Get distribution for specific executive
                    quality_dist = await conn.fetch(
                        """
                        SELECT 
                            CASE 
                                WHEN quality_score >= 0.8 THEN 'high'
                                WHEN quality_score >= 0.6 THEN 'medium'
                                WHEN quality_score >= 0.4 THEN 'low'
                                ELSE 'very_low'
                            END as quality_bucket,
                            COUNT(*) as count
                        FROM communication_examples
                        WHERE executive_id = $1
                          AND is_active = true
                        GROUP BY quality_bucket
                        ORDER BY 
                            CASE quality_bucket
                                WHEN 'high' THEN 1
                                WHEN 'medium' THEN 2
                                WHEN 'low' THEN 3
                                WHEN 'very_low' THEN 4
                            END
                        """,
                        executive_id
                    )
                else:
                    # Get distribution for all executives
                    quality_dist = await conn.fetch(
                        """
                        SELECT 
                            CASE 
                                WHEN quality_score >= 0.8 THEN 'high'
                                WHEN quality_score >= 0.6 THEN 'medium'
                                WHEN quality_score >= 0.4 THEN 'low'
                                ELSE 'very_low'
                            END as quality_bucket,
                            COUNT(*) as count
                        FROM communication_examples
                        WHERE is_active = true
                        GROUP BY quality_bucket
                        ORDER BY 
                            CASE quality_bucket
                                WHEN 'high' THEN 1
                                WHEN 'medium' THEN 2
                                WHEN 'low' THEN 3
                                WHEN 'very_low' THEN 4
                            END
                        """
                    )
                
                # Convert to dictionary
                distribution = {}
                total_count = 0
                
                for row in quality_dist:
                    bucket = row['quality_bucket']
                    count = row['count']
                    distribution[bucket] = count
                    total_count += count
                
                # Calculate percentages
                for bucket in distribution:
                    distribution[f"{bucket}_percent"] = (
                        distribution[bucket] / total_count * 100
                        if total_count > 0 else 0
                    )
                
                distribution['total'] = total_count
                
                return distribution
                
        except Exception as e:
            self.logger.error(f"Failed to get quality distribution: {e}")
            return {}
    
    async def _get_learning_trends(
        self,
        executive_id: Optional[str],
        days: int
    ) -> List[Dict[str, Any]]:
        """
        Get learning trends over time.
        
        Args:
            executive_id: Specific executive ID, or None for all
            days: Number of days to analyze
            
        Returns:
            List of daily trend data
        """
        try:
            async with self.db_pool.acquire() as conn:
                if executive_id:
                    # Get trends for specific executive
                    trends = await conn.fetch(
                        """
                        SELECT 
                            DATE(timestamp) as date,
                            COUNT(*) as examples_added,
                            COUNT(CASE WHEN is_bootstrap = false THEN 1 END) as learned_examples,
                            AVG(quality_score) as avg_quality
                        FROM communication_examples
                        WHERE executive_id = $1
                          AND timestamp >= NOW() - INTERVAL '%s days'
                        GROUP BY DATE(timestamp)
                        ORDER BY date DESC
                        """,
                        executive_id,
                        days
                    )
                else:
                    # Get trends for all executives
                    trends = await conn.fetch(
                        """
                        SELECT 
                            DATE(timestamp) as date,
                            COUNT(*) as examples_added,
                            COUNT(CASE WHEN is_bootstrap = false THEN 1 END) as learned_examples,
                            AVG(quality_score) as avg_quality
                        FROM communication_examples
                        WHERE timestamp >= NOW() - INTERVAL '%s days'
                        GROUP BY DATE(timestamp)
                        ORDER BY date DESC
                        """,
                        days
                    )
                
                # Convert to dictionaries
                result = []
                for row in trends:
                    result.append({
                        'date': row['date'].isoformat(),
                        'examples_added': row['examples_added'],
                        'learned_examples': row['learned_examples'],
                        'avg_quality': float(row['avg_quality']) if row['avg_quality'] else 0
                    })
                
                return result
                
        except Exception as e:
            self.logger.error(f"Failed to get learning trends: {e}")
            return []