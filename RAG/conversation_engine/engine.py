"""
Conversation Engine - Main Entry Point

The ConversationEngine is the unified system for context-aware,
conversation-stateful prompt generation with authentic executive voice.

Pipeline Stages:
1. Context Analyzer → Classify query (theme, urgency, emotion)
2. Response Calibrator → Adjust tone/style based on context
3. Example Selector → Match best communication example
4. Precedent Selector → Find relevant decision cases
5. Prompt Assembler → Build final prompt within token budget

Conversation Modes:
- STATELESS: No session (~45ms overhead)
- SESSION: Multi-turn with history (~60ms overhead)
- MEMORY_AWARE: Session + episodic memory (~85ms overhead)
"""

import logging
import time
from typing import Optional, Tuple, List, Dict, Any, TYPE_CHECKING

# LangSmith tracing (optional)
try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return decorator

# Local imports
from .context.models import (
    ConversationMode,
    ConversationState,
    ConversationTurn,
    ManagedContext,
)
from .analysis.models import (
    Theme,
    Urgency,
    UserEmotion,
    TurnType,
    QueryType,
    AnalyzedContext,
)
from .calibration.models import ResponseCalibration
from .examples.models import SelectedExample
from .precedents.models import SelectedPrecedent

# Context management
from .context.context_manager import ContextManager
from .context.session_store import SessionStore
from .context.reference_resolver import ReferenceResolver

# Analysis and calibration
from .analysis.analyzer import ContextAnalyzer
from .calibration.calibrator import ResponseCalibrator

# Example and precedent selection
from .examples.selector import SemanticExampleSelector
from .examples.embedding_cache import EmbeddingCache
from .precedents.selector import PrecedentSelector

# Prompt assembly
from .prompt.assembler import PromptAssembler

# State management
from .state.updater import StateUpdater, StateUpdateResult

# Semantic attention
from .calibration.attention import get_semantic_attention

# Type checking imports (avoid circular dependencies)
if TYPE_CHECKING:
    from memory.session_manager import SessionManager
    from profile_management.profile_manager import ProfileManager
    from llm_integration.prompt_builder import RetrievalContext
    from hybrid_retrieval.memory_search import MultiSignalMemorySearch

logger = logging.getLogger(__name__)


class ConversationEngine:
    """
    Main entry point for conversation-aware prompt generation.

    Replaces the scattered prompt builders with a unified pipeline that:
    - Detects conversation mode (stateless/session/memory)
    - Classifies query context (theme, urgency, emotion)
    - Calibrates response style per executive and situation
    - Selects semantically-matched examples
    - Includes relevant precedents for decision queries
    - Assembles prompt within token budget

    Usage:
        engine = ConversationEngine(session_manager, profile_manager)

        system_prompt, user_prompt, state = await engine.generate(
            query="What's our approach to budget overruns?",
            profile_id="exec_001_test",
            retrieved_context=context,
            session_id="sess_123"
        )
    """

    def __init__(
        self,
        session_manager: Optional["SessionManager"] = None,
        profile_manager: Optional["ProfileManager"] = None,
        memory_search: Optional["MultiSignalMemorySearch"] = None,
        embedding_model: Optional[Any] = None,  # EmbeddingModel from embedding_generation
    ):
        """
        Initialize the Conversation Engine.

        Args:
            session_manager: For session state management (optional in STATELESS mode)
            profile_manager: For loading executive profiles
            memory_search: For episodic memory search (MEMORY_AWARE mode)
            embedding_model: For semantic example matching
        """
        self.session_manager = session_manager
        self.profile_manager = profile_manager
        self._memory_search = memory_search
        self.embedding_model = embedding_model

        # Context management components
        self._session_store: Optional[SessionStore] = None
        self._reference_resolver: Optional[ReferenceResolver] = None
        self._context_manager: Optional[ContextManager] = None

        if session_manager:
            self._session_store = SessionStore(session_manager)
            self._reference_resolver = ReferenceResolver()
            self._context_manager = ContextManager(
                session_store=self._session_store,
                memory_search=memory_search,
                reference_resolver=self._reference_resolver,
            )

        # Analysis and calibration components
        self._context_analyzer = ContextAnalyzer()
        self._response_calibrator = ResponseCalibrator(
            profile_manager=profile_manager,
        )

        # Example and precedent selectors
        self._embedding_cache = EmbeddingCache()
        self._example_selector = SemanticExampleSelector(
            embedding_cache=self._embedding_cache,
        )
        self._precedent_selector = PrecedentSelector(
            embedding_cache=self._embedding_cache,
        )

        # Prompt assembler
        self._prompt_assembler = PromptAssembler(
            profile_manager=profile_manager,
        )

        # State updater
        self._state_updater = StateUpdater(
            session_store=self._session_store,
        )

        # Fallback to legacy prompt builder
        self._legacy_prompt_builder = None
        self._use_legacy_fallback = False

        # Metrics
        self._generation_count = 0
        self._fallback_count = 0
        self._error_count = 0
        self._context_load_count = 0

        logger.info(
            f"ConversationEngine initialized - "
            f"context_manager={'enabled' if self._context_manager else 'disabled'}, "
            f"context_analyzer={'enabled' if self._context_analyzer else 'disabled'}, "
            f"response_calibrator={'enabled' if self._response_calibrator else 'disabled'}, "
            f"example_selector={'enabled' if self._example_selector else 'disabled'}, "
            f"precedent_selector={'enabled' if self._precedent_selector else 'disabled'}, "
            f"prompt_assembler={'enabled' if self._prompt_assembler else 'disabled'}, "
            f"state_updater={'enabled' if self._state_updater else 'disabled'}, "
            f"memory_search={'enabled' if memory_search else 'disabled'}"
        )

    @traceable(name="conversation_engine_generate")
    async def generate(
        self,
        query: str,
        profile_id: str,
        retrieved_context: "RetrievalContext",
        path: str = "standard",
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        memory_enabled: bool = False,
        language: str = "en",
        audio_mode: bool = False,
    ) -> Tuple[str, str, Optional[ConversationState]]:
        """
        Generate system and user prompts for LLM.

        This is the main entry point that orchestrates the 5-stage pipeline.

        Args:
            query: User's question
            profile_id: Executive profile ID (e.g., "exec_001_test")
            retrieved_context: Vector/graph/precedent search results
            path: Processing path (fast/standard/agentic)
            session_id: Session ID for multi-turn (None = STATELESS)
            user_id: User ID for memory search (None = skip memory)
            memory_enabled: Whether to search episodic memory
            language: Response language (en/ja)
            audio_mode: If True, include natural speaking patterns for audio/video

        Returns:
            Tuple of (system_prompt, user_prompt, updated_state)
            - system_prompt: Complete system prompt for LLM
            - user_prompt: User message with context
            - updated_state: New session state (None if STATELESS)

        Raises:
            ValueError: If profile_id is invalid
            RuntimeError: If engine fails and no fallback available
        """
        start_time = time.time()
        self._generation_count += 1

        logger.debug(
            f"ConversationEngine.generate() called: "
            f"profile={profile_id}, path={path}, "
            f"session_id={session_id}, memory_enabled={memory_enabled}, "
            f"audio_mode={audio_mode}"
        )

        try:
            # Use legacy fallback if enabled
            if self._use_legacy_fallback:
                return await self._generate_with_fallback(
                    query=query,
                    profile_id=profile_id,
                    retrieved_context=retrieved_context,
                    path=path,
                    language=language,
                )

            # Stage 0: Detect mode and load context
            managed_context = await self._load_context(
                query=query,
                session_id=session_id,
                user_id=user_id,
                memory_enabled=memory_enabled,
                profile_id=profile_id,
            )

            # Stage 1: Analyze context
            analyzed_context = await self._analyze_context(
                query=query,
                retrieved_context=retrieved_context,
                managed_context=managed_context,
            )

            # Stage 2: Calibrate response
            calibration = await self._calibrate_response(
                profile_id=profile_id,
                analyzed_context=analyzed_context,
                managed_context=managed_context,
            )

            # Stage 3: Select example
            selected_example, query_embedding = await self._select_example(
                query=query,
                profile_id=profile_id,
                analyzed_context=analyzed_context,
                calibration=calibration,
            )

            # Refine attention with semantic similarity
            # Uses the query_embedding from ExampleSelector for zero-cost semantic attention
            if query_embedding is not None and calibration.attention_weights is not None:
                try:
                    semantic_attention = get_semantic_attention()
                    calibration.attention_weights = semantic_attention.refine_with_embedding(
                        pattern_weights=calibration.attention_weights,
                        query_embedding=query_embedding,
                        executive_id=profile_id,
                    )
                    logger.debug(
                        f"Attention refined semantically: "
                        f"type={calibration.attention_weights.query_type}, "
                        f"blend={calibration.attention_weights.blend_ratio}, "
                        f"top_3={calibration.attention_weights.get_top_k(3)}"
                    )
                except Exception as e:
                    logger.warning(f"Semantic attention refinement failed: {e}, using pattern-only")

            # Stage 4: Select precedent (if decision query)
            selected_precedent = await self._select_precedent(
                query=query,
                query_embedding=query_embedding,
                profile_id=profile_id,
                analyzed_context=analyzed_context,
            )

            # Stage 5: Assemble prompt
            system_prompt, user_prompt = await self._assemble_prompt(
                profile_id=profile_id,
                path=path,
                language=language,
                retrieved_context=retrieved_context,
                analyzed_context=analyzed_context,
                calibration=calibration,
                selected_example=selected_example,
                selected_precedent=selected_precedent,
                managed_context=managed_context,
                audio_mode=audio_mode,
            )

            # Prepare updated state
            updated_state = managed_context.session_state if managed_context else None

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"ConversationEngine.generate() completed in {elapsed_ms:.1f}ms "
                f"(mode={managed_context.mode.value if managed_context else 'legacy'})"
            )

            return system_prompt, user_prompt, updated_state

        except Exception as e:
            self._error_count += 1
            logger.error(f"ConversationEngine.generate() failed: {e}")

            # Attempt fallback on error
            if self._use_legacy_fallback or True:  # Always try fallback on error
                logger.warning("Falling back to legacy prompt builder")
                self._fallback_count += 1
                return await self._generate_with_fallback(
                    query=query,
                    profile_id=profile_id,
                    retrieved_context=retrieved_context,
                    path=path,
                    language=language,
                )

            raise RuntimeError(f"ConversationEngine failed: {e}") from e

    async def _generate_with_fallback(
        self,
        query: str,
        profile_id: str,
        retrieved_context: "RetrievalContext",
        path: str,
        language: str,
    ) -> Tuple[str, str, None]:
        """
        Generate prompts using legacy PromptBuilder.

        Used as fallback when the main pipeline fails.
        """
        try:
            # Lazy import to avoid circular dependencies
            from llm_integration.prompt_builder import PromptBuilder

            # Create or reuse prompt builder
            if (
                self._legacy_prompt_builder is None
                or self._legacy_prompt_builder.profile_id != profile_id
                or self._legacy_prompt_builder.path != path
            ):
                self._legacy_prompt_builder = PromptBuilder(
                    profile_id=profile_id,
                    path=path,
                )

            # Build prompts using legacy builder
            system_prompt, user_prompt = self._legacy_prompt_builder.build_full_prompt(
                query=query,
                context=retrieved_context,
                language=language,
            )

            logger.debug(
                f"Generated prompts via legacy fallback "
                f"(system: {len(system_prompt)} chars, user: {len(user_prompt)} chars)"
            )

            return system_prompt, user_prompt, None

        except Exception as e:
            logger.error(f"Legacy fallback failed: {e}")
            raise

    @traceable(name="ce_post_response_update")
    async def post_response_update(
        self,
        session_id: str,
        query: str,
        response: str,
        analyzed_context: Optional[AnalyzedContext] = None,
        calibration: Optional[ResponseCalibration] = None,
        sources_used: Optional[List[str]] = None,
        llm_tokens: Optional[Dict[str, int]] = None,
    ) -> StateUpdateResult:
        """
        Update session state after LLM response.

        Called after receiving LLM response to:
        - Store the turn in session history
        - Track facts provided (to avoid repetition)
        - Track sources cited
        - Update emotional state
        - Update topic tracking

        Args:
            session_id: Session ID to update
            query: Original user query
            response: LLM response text
            analyzed_context: Query analysis from analyzer
            calibration: Response calibration from calibrator
            sources_used: Source IDs cited in response
            llm_tokens: Token usage from LLM

        Returns:
            StateUpdateResult with update status
        """
        if not session_id:
            logger.debug("Skipping post_response_update: no session_id")
            return StateUpdateResult(
                success=True,
                session_id="",
                turn_number=0,
            )

        # Use StateUpdater if available
        if self._state_updater:
            try:
                # Provide defaults if not given
                if analyzed_context is None:
                    analyzed_context = AnalyzedContext()
                if calibration is None:
                    calibration = ResponseCalibration()

                result = self._state_updater.update(
                    session_id=session_id,
                    query=query,
                    response=response,
                    analyzed_context=analyzed_context,
                    calibration=calibration,
                    sources_used=sources_used,
                    llm_tokens=llm_tokens,
                )

                logger.debug(
                    f"Post-response update for session {session_id}: "
                    f"success={result.success}, turn={result.turn_number}"
                )

                return result

            except Exception as e:
                logger.error(f"StateUpdater failed: {e}")
                return StateUpdateResult(
                    success=False,
                    session_id=session_id,
                    turn_number=0,
                    error=str(e),
                )

        # Fallback: Basic integration with SessionManager
        if self.session_manager:
            try:
                success = await self.session_manager.update_session_activity(
                    session_id=session_id,
                    tokens_used=len(response.split()) * 4,  # Rough token estimate
                    response_time_ms=0,
                )

                return StateUpdateResult(
                    success=success,
                    session_id=session_id,
                    turn_number=0,
                )

            except Exception as e:
                logger.error(f"SessionManager update failed: {e}")
                return StateUpdateResult(
                    success=False,
                    session_id=session_id,
                    turn_number=0,
                    error=str(e),
                )

        return StateUpdateResult(
            success=True,
            session_id=session_id,
            turn_number=0,
        )

    @traceable(name="ce_stage0_load_context")
    async def _load_context(
        self,
        query: str,
        session_id: Optional[str],
        user_id: Optional[str],
        memory_enabled: bool,
        profile_id: str,
    ) -> ManagedContext:
        """
        Detect mode and load session/memory context.

        Uses ContextManager to:
        - Load ConversationState from SessionStore
        - Resolve references via ReferenceResolver
        - Search episodic memory for MEMORY_AWARE mode
        """
        self._context_load_count += 1

        # Use ContextManager if available
        if self._context_manager:
            try:
                return await self._context_manager.load_context(
                    query=query,
                    profile_id=profile_id,
                    session_id=session_id,
                    user_id=user_id,
                    memory_enabled=memory_enabled,
                )
            except Exception as e:
                logger.error(f"ContextManager.load_context failed: {e}")
                # Fall back to basic mode detection

        # Fallback: Basic mode detection
        if not session_id:
            mode = ConversationMode.STATELESS
        elif user_id and memory_enabled:
            mode = ConversationMode.MEMORY_AWARE
        else:
            mode = ConversationMode.SESSION

        return ManagedContext(
            mode=mode,
            original_query=query,
            resolved_query=query,
        )

    @traceable(name="ce_stage1_analyze_context")
    async def _analyze_context(
        self,
        query: str,
        retrieved_context: "RetrievalContext",
        managed_context: ManagedContext,
    ) -> AnalyzedContext:
        """
        Analyze query for theme, urgency, emotion, etc.

        Uses ContextAnalyzer to classify query.
        """
        if self._context_analyzer is None:
            logger.warning("ContextAnalyzer not initialized, returning defaults")
            return AnalyzedContext()

        try:
            return self._context_analyzer.analyze(
                query=query,
                managed_context=managed_context,
                retrieved_context=retrieved_context,
            )
        except Exception as e:
            logger.error(f"Context analysis failed: {e}")
            return AnalyzedContext()  # Return defaults on error

    @traceable(name="ce_stage2_calibrate_response")
    async def _calibrate_response(
        self,
        profile_id: str,
        analyzed_context: AnalyzedContext,
        managed_context: ManagedContext,
    ) -> ResponseCalibration:
        """
        Calibrate response tone and style.

        Uses ResponseCalibrator with voiceprint and rules.
        """
        if self._response_calibrator is None:
            logger.warning("ResponseCalibrator not initialized, returning defaults")
            return ResponseCalibration()

        try:
            return self._response_calibrator.calibrate(
                profile_id=profile_id,
                analyzed_context=analyzed_context,
                managed_context=managed_context,
            )
        except Exception as e:
            logger.error(f"Response calibration failed: {e}")
            return ResponseCalibration()  # Return defaults on error

    @traceable(name="ce_stage3_select_example")
    async def _select_example(
        self,
        query: str,
        profile_id: str,
        analyzed_context: AnalyzedContext,
        calibration: ResponseCalibration,
        channel: str = "slack",
    ) -> Tuple[SelectedExample, Any]:
        """
        Select best-matching communication example.

        Uses SemanticExampleSelector with multi-signal matching.

        Returns:
            Tuple of (SelectedExample, query_embedding)
            - SelectedExample: Best matching example
            - query_embedding: For reuse by precedent selector
        """
        if self._example_selector is None:
            logger.warning("ExampleSelector not initialized, returning fallback")
            import numpy as np
            return SelectedExample.create_fallback("selector_not_initialized"), np.zeros(1024)  # MIGRATED: 384→1024

        try:
            return self._example_selector.select(
                query=query,
                profile_id=profile_id,
                analyzed_context=analyzed_context,
                calibration=calibration,
                channel=channel,
            )
        except Exception as e:
            logger.error(f"Example selection failed: {e}")
            import numpy as np
            return SelectedExample.create_fallback(f"selection_error: {e}"), np.zeros(1024)  # MIGRATED: 384→1024

    @traceable(name="ce_stage4_select_precedent")
    async def _select_precedent(
        self,
        query: str,
        query_embedding: Any,
        profile_id: str,
        analyzed_context: AnalyzedContext,
    ) -> SelectedPrecedent:
        """
        Select relevant decision precedent.

        Uses PrecedentSelector with category + semantic + recency scoring.

        Args:
            query: User's query
            query_embedding: Pre-computed embedding from example selector
            profile_id: Executive profile ID
            analyzed_context: Analysis results

        Returns:
            SelectedPrecedent (may be skipped if not decision query)
        """
        if self._precedent_selector is None:
            logger.warning("PrecedentSelector not initialized, returning skipped")
            return SelectedPrecedent.create_skipped("selector_not_initialized")

        try:
            return self._precedent_selector.select(
                query=query,
                query_embedding=query_embedding,
                profile_id=profile_id,
                analyzed_context=analyzed_context,
            )
        except Exception as e:
            logger.error(f"Precedent selection failed: {e}")
            return SelectedPrecedent.create_no_match(f"selection_error: {e}")

    @traceable(name="ce_stage5_assemble_prompt")
    async def _assemble_prompt(
        self,
        profile_id: str,
        path: str,
        language: str,
        retrieved_context: "RetrievalContext",
        analyzed_context: AnalyzedContext,
        calibration: ResponseCalibration,
        selected_example: SelectedExample,
        selected_precedent: SelectedPrecedent,
        managed_context: ManagedContext,
        audio_mode: bool = False,
    ) -> Tuple[str, str]:
        """
        Assemble final prompt from all components.

        Uses PromptAssembler to build system and user prompts.

        Args:
            profile_id: Executive profile ID
            path: Processing path (fast/standard/agentic)
            language: Response language (en/ja)
            retrieved_context: Vector/graph search results
            analyzed_context: From context analyzer
            calibration: From response calibrator
            selected_example: From example selector
            selected_precedent: From precedent selector
            managed_context: From context manager
            audio_mode: If True, include natural speaking patterns

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        if self._prompt_assembler is None:
            logger.warning("PromptAssembler not initialized, returning empty prompts")
            return "", ""

        try:
            return self._prompt_assembler.assemble(
                profile_id=profile_id,
                path=path,
                language=language,
                retrieved_context=retrieved_context,
                managed_context=managed_context,
                analyzed_context=analyzed_context,
                calibration=calibration,
                selected_example=selected_example,
                selected_precedent=selected_precedent,
                audio_mode=audio_mode,
            )
        except Exception as e:
            logger.error(f"Prompt assembly failed: {e}")
            return "", ""  # Will trigger legacy fallback

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics for monitoring."""
        return {
            "generation_count": self._generation_count,
            "fallback_count": self._fallback_count,
            "error_count": self._error_count,
            "context_load_count": self._context_load_count,
            "fallback_rate": (
                self._fallback_count / self._generation_count
                if self._generation_count > 0
                else 0
            ),
            "error_rate": (
                self._error_count / self._generation_count
                if self._generation_count > 0
                else 0
            ),
            "use_legacy_fallback": self._use_legacy_fallback,
            "components_initialized": {
                "session_store": self._session_store is not None,
                "reference_resolver": self._reference_resolver is not None,
                "context_manager": self._context_manager is not None,
                "memory_search": self._memory_search is not None,
                "context_analyzer": self._context_analyzer is not None,
                "response_calibrator": self._response_calibrator is not None,
                "embedding_cache": self._embedding_cache is not None,
                "example_selector": self._example_selector is not None,
                "precedent_selector": self._precedent_selector is not None,
                "prompt_assembler": self._prompt_assembler is not None,
                "state_updater": self._state_updater is not None,
            },
            "embedding_cache_stats": (
                self._embedding_cache.get_cache_stats()
                if self._embedding_cache else None
            ),
        }

    def set_legacy_fallback(self, enabled: bool) -> None:
        """Enable/disable legacy fallback mode."""
        self._use_legacy_fallback = enabled
        logger.info(f"Legacy fallback {'enabled' if enabled else 'disabled'}")


# Factory function for dependency injection
def get_conversation_engine(
    session_manager: Optional["SessionManager"] = None,
    profile_manager: Optional["ProfileManager"] = None,
) -> ConversationEngine:
    """
    Factory function to create ConversationEngine with dependencies.

    Use this for proper dependency injection rather than direct instantiation.

    Args:
        session_manager: Optional session manager (None for STATELESS only)
        profile_manager: Optional profile manager

    Returns:
        Configured ConversationEngine instance
    """
    return ConversationEngine(
        session_manager=session_manager,
        profile_manager=profile_manager,
    )
