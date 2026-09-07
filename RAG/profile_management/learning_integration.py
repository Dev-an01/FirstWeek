"""
Learning Integration

Integrates dynamic few-shot learning with existing profile management system.
Provides a unified interface for the complete learning system.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import uuid

import asyncpg

from .dynamic_examples import DynamicExamples
from .example_selector import ExampleSelector
from .feedback_processor import FeedbackProcessor
from .learning_pipeline import LearningPipeline
from .profile_manager import get_profile_manager

logger = logging.getLogger(__name__)


class LearningIntegration:
    """
    Integrates dynamic few-shot learning with existing profile management.
    
    Provides a unified interface that:
    - Extends existing ProfileManager with learning capabilities
    - Maintains backward compatibility
    - Provides comprehensive learning dashboard
    - Handles all learning lifecycle operations
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        learning_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize LearningIntegration.
        
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
            'usage_weight': 0.05,
            'bootstrap_examples_count': 3,
            'learned_examples_count': 2
        }
        
        # Merge with provided config
        self.config = {**default_config, **(learning_config or {})}
        
        # Initialize learning components
        self.learning_pipeline = LearningPipeline(
            db_pool=db_pool,
            learning_config=self.config
        )
        
        # Get existing profile manager
        self.profile_manager = get_profile_manager()
        
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """
        Initialize the integrated learning system.
        
        Initializes both the learning pipeline and ensures
        compatibility with existing profile manager.
        """
        self.logger.info("Initializing integrated learning system")
        
        # Initialize learning pipeline
        await self.learning_pipeline.initialize()
        
        # Ensure bootstrap examples are loaded
        await self._ensure_bootstrap_examples()
        
        self.logger.info("Integrated learning system initialized successfully")
    
    async def shutdown(self):
        """
        Shutdown the integrated learning system.
        """
        self.logger.info("Shutting down integrated learning system")
        
        # Shutdown learning pipeline
        await self.learning_pipeline.shutdown()
        
        self.logger.info("Integrated learning system shutdown complete")
    
    async def generate_system_prompt(
        self,
        executive_id: str,
        include_examples: bool = True,
        max_examples: int = 5,
        query: Optional[str] = None,
        query_type: Optional[str] = None,
        context_sources: Optional[List[Dict[str, Any]]] = None,
        use_cache: bool = True
    ) -> str:
        """
        Generate system prompt with dynamic examples.
        
        Args:
            executive_id: Executive profile ID
            include_examples: Whether to include few-shot examples
            max_examples: Maximum examples to include
            query: Current query for context-relevant examples
            query_type: Type of query for filtering examples
            context_sources: Sources used in current query
            use_cache: Whether to use cached prompt if available
            
        Returns:
            System prompt string
        """
        try:
            # Get profile from existing profile manager
            profile = self.profile_manager.get_profile(executive_id)
            if not profile:
                self.logger.error(f"Profile not found: {executive_id}")
                return ""
            
            # Generate prompt sections
            sections = []
            
            # 1. Identity and Role
            sections.append(self._generate_identity_section(profile))
            
            # 2. Communication Style
            sections.append(self._generate_communication_style_section(profile))
            
            # 3. Core Values
            sections.append(self._generate_core_values_section(profile))
            
            # 4. Decision Philosophy
            sections.append(self._generate_decision_philosophy_section(profile))
            
            # 5. Few-Shot Examples (if enabled)
            if include_examples:
                examples_section = await self._generate_examples_section(
                    executive_id, max_examples, query, query_type, context_sources
                )
                if examples_section:
                    sections.append(examples_section)
            
            # 6. Instructions
            sections.append(self._generate_instructions_section())
            
            # Combine all sections
            prompt = "\n\n".join(sections)
            
            self.logger.debug(f"Generated system prompt for {executive_id}")
            return prompt
            
        except Exception as e:
            self.logger.error(f"Failed to generate system prompt: {e}")
            return ""
    
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
        session_id: Optional[str] = None
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
        # Process through learning pipeline
        return await self.learning_pipeline.process_interaction(
            executive_id=executive_id,
            user_id=user_id,
            query=query,
            response=response,
            context_sources=context_sources,
            query_type=query_type,
            response_time_ms=response_time_ms,
            embedding=embedding,
            session_id=session_id
        )
    
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
        # Process through learning pipeline
        return await self.learning_pipeline.process_feedback(
            interaction_id=interaction_id,
            executive_id=executive_id,
            user_id=user_id,
            feedback=feedback,
            feedback_type=feedback_type,
            metadata=metadata
        )
    
    async def get_learning_dashboard(
        self,
        executive_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get comprehensive learning dashboard.
        
        Args:
            executive_id: Specific executive ID, or None for all
            days: Number of days to analyze
            
        Returns:
            Dashboard data dictionary
        """
        try:
            # Get dashboard from learning pipeline
            dashboard = await self.learning_pipeline.get_learning_dashboard(
                executive_id, days
            )
            
            # Add profile manager stats
            profile_stats = self.profile_manager.get_cache_stats()
            dashboard['profile_manager'] = profile_stats
            
            # Add configuration
            dashboard['integration_config'] = self.config
            
            return dashboard
            
        except Exception as e:
            self.logger.error(f"Failed to get learning dashboard: {e}")
            return {}
    
    async def update_configuration(
        self,
        new_config: Dict[str, Any]
    ) -> bool:
        """
        Update learning configuration.
        
        Args:
            new_config: New configuration values
            
        Returns:
            True if updated successfully
        """
        try:
            # Update configuration
            self.config.update(new_config)
            
            # Update learning pipeline
            success = await self.learning_pipeline.update_configuration(new_config)
            
            self.logger.info(f"Updated learning configuration: {new_config}")
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to update configuration: {e}")
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
        # Get examples from learning pipeline
        return await self.learning_pipeline.get_examples_for_prompt(
            executive_id=executive_id,
            query=query,
            query_type=query_type,
            context_sources=context_sources,
            max_examples=max_examples
        )
    
    async def _ensure_bootstrap_examples(self) -> None:
        """
        Ensure bootstrap examples are loaded from profiles.
        
        Loads communication examples from executive profiles into the
        communication_examples table with is_bootstrap=true.
        """
        try:
            # Get all profiles from profile manager
            profiles = self.profile_manager.get_all_profiles()
            
            for executive_id, profile in profiles.items():
                # Check if bootstrap examples already loaded
                async with self.db_pool.acquire() as conn:
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
                    comm_examples = profile.get('communication_examples', [])
                    
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
                            ON CONFLICT DO NOTHING
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
    
    async def _generate_examples_section(
        self,
        executive_id: str,
        max_examples: int,
        query: Optional[str] = None,
        query_type: Optional[str] = None,
        context_sources: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate few-shot examples section.
        
        Args:
            executive_id: Executive profile ID
            max_examples: Maximum examples to include
            query: Current query for context-relevant examples
            query_type: Type of query for filtering examples
            context_sources: Sources used in current query
            
        Returns:
            Examples section string or empty
        """
        try:
            # Get examples from learning pipeline
            examples = await self.learning_pipeline.get_examples_for_prompt(
                executive_id=executive_id,
                query=query,
                query_type=query_type,
                context_sources=context_sources,
                max_examples=max_examples
            )
            
            if not examples:
                return ""
            
            # Format examples
            section = "COMMUNICATION EXAMPLES:\n"
            section += "Here are examples of how you communicate:\n"
            
            for example in examples:
                section += f"\n--- Example {example['id']} ---\n"
                section += example['content']
            
            return section
            
        except Exception as e:
            self.logger.error(f"Failed to generate examples section: {e}")
            return ""
    
    def _generate_identity_section(self, profile: Dict[str, Any]) -> str:
        """
        Generate identity and role section.
        
        Args:
            profile: Executive profile
            
        Returns:
            Identity section string
        """
        name = profile.get('name', '')
        title = profile.get('title', '')
        department = profile.get('department', '')
        
        section = "IDENTITY AND ROLE:\n"
        section += f"You are {name}, {title}"
        
        if department:
            section += f" of the {department} department"
        
        section += ".\n"
        section += "Respond in your authentic voice and style.\n"
        
        return section
    
    def _generate_communication_style_section(self, profile: Dict[str, Any]) -> str:
        """
        Generate communication style section.
        
        Args:
            profile: Executive profile
            
        Returns:
            Communication style section string
        """
        style = profile.get('communication_style', {})
        
        section = "COMMUNICATION STYLE:\n"
        
        # Tone
        tone = style.get('tone', '')
        if tone:
            section += f"Tone: {tone}\n"
        
        # Formality
        formality = style.get('formality', '')
        if formality:
            section += f"Formality: {formality}\n"
        
        # Directness
        directness = style.get('directness', '')
        if directness:
            section += f"Directness: {directness}\n"
        
        # Warmth
        warmth = style.get('warmth', '')
        if warmth:
            section += f"Warmth: {warmth}\n"
        
        # Common phrases
        phrases = style.get('common_phrases', [])
        if phrases:
            section += "Common phrases:\n"
            for phrase in phrases:
                section += f"- {phrase}\n"
        
        return section
    
    def _generate_core_values_section(self, profile: Dict[str, Any]) -> str:
        """
        Generate core values section.
        
        Args:
            profile: Executive profile
            
        Returns:
            Core values section string
        """
        values = profile.get('core_values', [])
        
        section = "CORE VALUES:\n"
        section += "Your decisions should align with these core values:\n"
        
        for i, value in enumerate(values, 1):
            name = value.get('name', '')
            description = value.get('description', '')
            priority = value.get('priority', i)
            
            section += f"{i}. {name} (Priority: {priority})\n"
            section += f"   {description}\n"
        
        return section
    
    def _generate_decision_philosophy_section(self, profile: Dict[str, Any]) -> str:
        """
        Generate decision philosophy section.
        
        Args:
            profile: Executive profile
            
        Returns:
            Decision philosophy section string
        """
        philosophy = profile.get('decision_philosophy', {})
        
        section = "DECISION PHILOSOPHY:\n"
        
        # Approach
        approach = philosophy.get('approach', '')
        if approach:
            section += f"Approach: {approach}\n"
        
        # Risk tolerance
        risk_tolerance = philosophy.get('risk_tolerance', '')
        if risk_tolerance:
            section += f"Risk tolerance: {risk_tolerance}\n"
        
        # Data-driven
        data_driven = philosophy.get('data_driven', False)
        if data_driven:
            section += "Data-driven: Always base decisions on data\n"
        
        # Red flags
        red_flags = philosophy.get('red_flags', [])
        if red_flags:
            section += "Red flags (never approve without escalation):\n"
            for flag in red_flags:
                section += f"- {flag}\n"
        
        return section
    
    def _generate_instructions_section(self) -> str:
        """
        Generate instructions section.
        
        Returns:
            Instructions section string
        """
        section = "INSTRUCTIONS:\n"
        section += "1. Be helpful and accurate\n"
        section += "2. Cite your sources when providing facts\n"
        section += "3. If uncertain, ask for clarification\n"
        section += "4. Maintain your authentic communication style\n"
        section += "5. Use the examples above as guidance for tone and approach\n"
        
        return section


# Global integration instance
_integration = None


def get_learning_integration(
    db_pool: asyncpg.Pool,
    learning_config: Optional[Dict[str, Any]] = None
) -> LearningIntegration:
    """
    Get the singleton LearningIntegration instance.
    
    Args:
        db_pool: PostgreSQL connection pool
        learning_config: Configuration for learning process
        
    Returns:
        LearningIntegration instance
    """
    global _integration
    if _integration is None:
        _integration = LearningIntegration(db_pool, learning_config)
    return _integration