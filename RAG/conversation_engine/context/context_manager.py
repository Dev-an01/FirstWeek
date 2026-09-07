"""
Context Manager - Orchestrates context loading for Conversation Engine.

Responsibilities:
1. Detect conversation mode (STATELESS/SESSION/MEMORY_AWARE)
2. Load session state from PostgreSQL (via SessionStore)
3. Search episodic memory (via MultiSignalMemorySearch)
4. Resolve references ("the timeline" → actual context)
5. Aggregate into ManagedContext

Performance Targets:
- STATELESS: Skip all loading (~5ms)
- SESSION: Load state + resolve refs (~20ms)
- MEMORY_AWARE: SESSION + memory search (~50ms)
"""

import asyncio
import logging
import time
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from .models import ConversationMode, ConversationState, ConversationTurn, ManagedContext
from .reference_resolver import ReferenceResolver
from .session_store import SessionStore

if TYPE_CHECKING:
    from hybrid_retrieval.memory_search import MultiSignalMemorySearch

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Orchestrates context loading for Conversation Engine.

    Coordinates:
    - Mode detection based on provided parameters
    - Session state loading via SessionStore
    - Reference resolution via ReferenceResolver
    - Memory search via MultiSignalMemorySearch (MEMORY_AWARE only)

    Thread-safe: Uses async operations, no shared mutable state.
    """

    # Timeout for memory search to prevent latency spikes
    MEMORY_SEARCH_TIMEOUT_MS = 50

    # Maximum episodic memory results to include
    MAX_MEMORY_RESULTS = 5

    def __init__(
        self,
        session_store: Optional[SessionStore] = None,
        memory_search: Optional["MultiSignalMemorySearch"] = None,
        reference_resolver: Optional[ReferenceResolver] = None,
    ):
        """
        Initialize ContextManager.

        Args:
            session_store: SessionStore for state management
            memory_search: MultiSignalMemorySearch for episodic memory
            reference_resolver: ReferenceResolver for multi-turn refs
        """
        self.session_store = session_store
        self.memory_search = memory_search
        self.reference_resolver = reference_resolver or ReferenceResolver()

    async def load_context(
        self,
        query: str,
        profile_id: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        memory_enabled: bool = False,
    ) -> ManagedContext:
        """
        Main entry point - returns complete context for pipeline.

        Orchestrates mode detection, state loading, reference resolution,
        and memory search based on the detected mode.

        Args:
            query: User's query text
            profile_id: Executive profile ID
            session_id: Session ID (None = STATELESS)
            user_id: User ID (required for MEMORY_AWARE)
            memory_enabled: Whether to enable memory search

        Returns:
            ManagedContext with all aggregated context
        """
        start_time = time.time()

        # 1. Detect mode
        mode = self.detect_mode(
            session_id=session_id,
            user_id=user_id,
            memory_enabled=memory_enabled,
        )

        # 2. STATELESS - fast return
        if mode == ConversationMode.STATELESS:
            elapsed_ms = (time.time() - start_time) * 1000

            logger.debug(
                f"ContextManager.load_context completed",
                extra={
                    "mode": mode.value,
                    "session_id": session_id,
                    "latency_ms": elapsed_ms,
                }
            )

            return ManagedContext(
                mode=mode,
                original_query=query,
                resolved_query=query,
                context_load_time_ms=elapsed_ms,
            )

        # 3. Load session state
        session_state = await self._load_session_state(
            session_id=session_id,
            user_id=user_id or "anonymous",
            profile_id=profile_id,
        )

        # 4. Resolve references (if multi-turn)
        resolved_query = query
        resolved_references: Dict[str, str] = {}

        if session_state and session_state.turn_count > 0:
            try:
                resolved_query, resolved_references = self.reference_resolver.resolve(
                    query=query,
                    session_state=session_state,
                )
            except Exception as e:
                logger.warning(f"Reference resolution failed: {e}")
                # Continue with original query

        # 5. Search episodic memory (MEMORY_AWARE only)
        episodic_memory: List[Dict[str, Any]] = []

        if mode == ConversationMode.MEMORY_AWARE:
            episodic_memory = await self._search_memory(
                query=resolved_query,
                profile_id=profile_id,
                user_id=user_id,
            )

        # 6. Extract user preferences from memory (if available)
        user_preferences = self._extract_user_preferences(episodic_memory)

        # 7. Aggregate into ManagedContext
        elapsed_ms = (time.time() - start_time) * 1000

        context = ManagedContext(
            mode=mode,
            session_state=session_state,
            turn_history=session_state.turns if session_state else [],
            episodic_memory=episodic_memory,
            resolved_references=resolved_references,
            original_query=query,
            resolved_query=resolved_query,
            facts_to_avoid=session_state.facts_already_provided if session_state else [],
            user_preferences=user_preferences,
            context_load_time_ms=elapsed_ms,
        )

        # Log completion
        logger.info(
            f"ContextManager.load_context completed",
            extra={
                "mode": mode.value,
                "session_id": session_id,
                "turn_number": context.get_turn_number(),
                "resolved_refs_count": len(resolved_references),
                "memory_results_count": len(episodic_memory),
                "facts_to_avoid_count": len(context.facts_to_avoid),
                "latency_ms": elapsed_ms,
            }
        )

        return context

    def detect_mode(
        self,
        session_id: Optional[str],
        user_id: Optional[str],
        memory_enabled: bool,
    ) -> ConversationMode:
        """
        Determine conversation mode based on provided parameters.

        Logic:
        - No session_id → STATELESS
        - session_id only → SESSION
        - session_id + user_id (no memory) → SESSION
        - session_id + user_id + memory_enabled → MEMORY_AWARE

        Args:
            session_id: Session ID (None = STATELESS)
            user_id: User ID (required for MEMORY_AWARE)
            memory_enabled: Whether memory search is enabled

        Returns:
            ConversationMode enum value
        """
        if not session_id:
            return ConversationMode.STATELESS

        if user_id and memory_enabled and self.memory_search:
            return ConversationMode.MEMORY_AWARE

        return ConversationMode.SESSION

    async def _load_session_state(
        self,
        session_id: str,
        user_id: str,
        profile_id: str,
    ) -> Optional[ConversationState]:
        """
        Load ConversationState from SessionStore.

        Handles errors gracefully by returning None.

        Args:
            session_id: Session UUID
            user_id: User identifier
            profile_id: Executive profile ID

        Returns:
            ConversationState or None on error
        """
        if not self.session_store:
            logger.warning("No SessionStore configured, skipping state load")
            return None

        try:
            state = await self.session_store.get_or_create_state(
                session_id=session_id,
                user_id=user_id,
                executive_id=profile_id,
            )
            return state

        except Exception as e:
            logger.error(f"Failed to load session state: {e}")
            return None

    async def _search_memory(
        self,
        query: str,
        profile_id: str,
        user_id: str,
        top_k: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Search episodic memory for relevant past conversations.

        Protected by timeout to prevent latency spikes.

        Args:
            query: Search query (resolved)
            profile_id: Executive profile ID
            user_id: User ID for context matching
            top_k: Maximum results (defaults to MAX_MEMORY_RESULTS)

        Returns:
            List of memory results or empty list on error/timeout
        """
        if not self.memory_search:
            logger.debug("No memory search configured")
            return []

        if top_k is None:
            top_k = self.MAX_MEMORY_RESULTS

        try:
            # Wrap in timeout to prevent latency spikes
            result = await asyncio.wait_for(
                self._execute_memory_search(
                    query=query,
                    profile_id=profile_id,
                    user_id=user_id,
                    top_k=top_k,
                ),
                timeout=self.MEMORY_SEARCH_TIMEOUT_MS / 1000,
            )

            return result.get("results", [])

        except asyncio.TimeoutError:
            logger.warning(
                f"Memory search timed out after {self.MEMORY_SEARCH_TIMEOUT_MS}ms"
            )
            return []

        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    async def _execute_memory_search(
        self,
        query: str,
        profile_id: str,
        user_id: str,
        top_k: int,
    ) -> Dict[str, Any]:
        """
        Execute the actual memory search.

        Separated for timeout wrapping.
        """
        # MultiSignalMemorySearch.search_executive_memory is sync,
        # so we run it in executor
        import asyncio

        loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(
            None,
            lambda: self.memory_search.search_executive_memory(
                query=query,
                executive_id=profile_id,
                current_user_id=user_id,
                top_k=top_k,
            )
        )

        return result

    def _extract_user_preferences(
        self,
        episodic_memory: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Extract user preferences from episodic memory patterns.

        Analyzes past interactions to identify:
        - Preferred response length
        - Common topics
        - Communication style preferences

        Args:
            episodic_memory: Memory search results

        Returns:
            User preferences dict or None
        """
        if not episodic_memory:
            return None

        try:
            # Analyze memory for patterns
            preferences: Dict[str, Any] = {}

            # Count topics from past interactions
            topic_counts: Dict[str, int] = {}
            for memory in episodic_memory:
                metadata = memory.get("metadata", {})
                topic = metadata.get("topic")
                if topic:
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1

            if topic_counts:
                preferences["common_topics"] = sorted(
                    topic_counts.keys(),
                    key=lambda t: topic_counts[t],
                    reverse=True
                )[:5]

            # Analyze feedback patterns
            positive_count = sum(
                1 for m in episodic_memory
                if m.get("metadata", {}).get("feedback") == "positive"
            )
            negative_count = sum(
                1 for m in episodic_memory
                if m.get("metadata", {}).get("feedback") == "negative"
            )

            if positive_count + negative_count > 0:
                preferences["feedback_positive_rate"] = (
                    positive_count / (positive_count + negative_count)
                )

            return preferences if preferences else None

        except Exception as e:
            logger.warning(f"Failed to extract user preferences: {e}")
            return None

    async def update_state_after_response(
        self,
        session_id: str,
        query: str,
        response: str,
        detected_emotion: str = "neutral",
        topic: str = "",
        sources_used: List[str] = None,
        facts_provided: List[str] = None,
    ) -> bool:
        """
        Update session state after LLM response.

        Called after receiving LLM response to persist turn data.

        Args:
            session_id: Session UUID
            query: User's query
            response: LLM response
            detected_emotion: Detected user emotion
            topic: Topic of this turn
            sources_used: Source IDs cited
            facts_provided: Facts mentioned

        Returns:
            True if update successful
        """
        if not self.session_store:
            return True  # No-op if no store

        sources_used = sources_used or []
        facts_provided = facts_provided or []

        try:
            # Load current state
            state = await self.session_store.get_or_create_state(
                session_id=session_id,
                user_id="",  # Will be preserved from existing
                executive_id="",
            )

            # Create turn
            turn = ConversationTurn(
                turn_number=state.turn_count + 1,
                user_query=query,
                assistant_response=response[:500],  # Truncate for storage
                detected_emotion=detected_emotion,
                topic=topic,
                sources_used=sources_used,
                facts_provided=facts_provided,
            )

            # Update state
            state.add_turn(turn)
            state.add_facts(facts_provided)
            state.add_sources(sources_used)
            state.update_emotion(detected_emotion)
            if topic:
                state.update_topic(topic)

            # Persist
            return await self.session_store.save_state(state)

        except Exception as e:
            logger.error(f"Failed to update state after response: {e}")
            return False


# Factory function for dependency injection
def create_context_manager(
    session_store: Optional[SessionStore] = None,
    memory_search: Optional["MultiSignalMemorySearch"] = None,
) -> ContextManager:
    """
    Factory function to create ContextManager with dependencies.

    Args:
        session_store: Optional SessionStore
        memory_search: Optional MultiSignalMemorySearch

    Returns:
        Configured ContextManager instance
    """
    return ContextManager(
        session_store=session_store,
        memory_search=memory_search,
        reference_resolver=ReferenceResolver(),
    )
