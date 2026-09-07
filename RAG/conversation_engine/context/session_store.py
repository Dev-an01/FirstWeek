"""
Session Store - Wraps existing SessionManager with ConversationState support.

The existing SessionManager handles:
- Session lifecycle (create, expire, cleanup)
- Turn storage in episodic_memory
- Session caching

SessionStore adds:
- ConversationState serialization to conversation_state JSONB column
- Facts/sources tracking
- Emotional trend persistence
- Graceful fallback on errors
"""

import logging
import time
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from .models import ConversationState, ConversationTurn

if TYPE_CHECKING:
    from memory.session_manager import SessionManager

logger = logging.getLogger(__name__)


class SessionStore:
    """
    Wraps existing SessionManager with ConversationState support.

    Provides:
    - ConversationState loading/saving with JSONB serialization
    - Turn history retrieval
    - Facts and sources tracking
    - Graceful error handling with fallback to empty state

    Thread-safe: Delegates to SessionManager which handles concurrency.
    """

    def __init__(
        self,
        session_manager: "SessionManager",
    ):
        """
        Initialize SessionStore.

        Args:
            session_manager: Existing SessionManager instance
        """
        self.session_manager = session_manager
        self._state_cache: Dict[str, tuple] = {}  # session_id -> (state, timestamp)
        self._cache_ttl_seconds = 30  # 30 second cache

    async def get_or_create_state(
        self,
        session_id: str,
        user_id: str,
        executive_id: str,
    ) -> ConversationState:
        """
        Get existing ConversationState or create new one.

        Gracefully handles errors by returning a new empty state.

        Args:
            session_id: Session UUID
            user_id: User identifier
            executive_id: Executive profile ID

        Returns:
            ConversationState (existing or new)
        """
        start_time = time.time()

        # Check cache first
        cached = self._get_from_cache(session_id)
        if cached:
            logger.debug(f"SessionStore cache hit for {session_id}")
            return cached

        try:
            # Try to load existing state
            session_info = await self._get_session_with_state(session_id)

            if session_info:
                state_data = session_info.get("conversation_state")
                if state_data and isinstance(state_data, dict) and state_data:
                    # Deserialize existing state
                    state = ConversationState.from_dict(state_data)

                    # Ensure session metadata is current
                    state.session_id = session_id
                    state.executive_id = executive_id
                    state.user_id = user_id

                    # Update cache
                    self._add_to_cache(session_id, state)

                    elapsed_ms = (time.time() - start_time) * 1000
                    logger.debug(
                        f"Loaded ConversationState for {session_id} "
                        f"(turns={state.turn_count}, {elapsed_ms:.1f}ms)"
                    )
                    return state

            # No existing state, create new
            logger.debug(f"Creating new ConversationState for {session_id}")
            return self._create_new_state(session_id, user_id, executive_id)

        except Exception as e:
            logger.warning(
                f"Session state load failed for {session_id}, creating new: {e}"
            )
            return self._create_new_state(session_id, user_id, executive_id)

    def _create_new_state(
        self,
        session_id: str,
        user_id: str,
        executive_id: str,
    ) -> ConversationState:
        """Create a new empty ConversationState."""
        return ConversationState(
            session_id=session_id,
            executive_id=executive_id,
            user_id=user_id,
        )

    async def save_state(
        self,
        state: ConversationState,
    ) -> bool:
        """
        Persist ConversationState to database.

        Uses the conversation_state JSONB column added by Phase 1 migration.

        Args:
            state: ConversationState to persist

        Returns:
            True if saved successfully, False otherwise
        """
        if not state.session_id:
            logger.warning("Cannot save state without session_id")
            return False

        try:
            # Serialize state
            state_dict = state.to_dict()

            # Update via SessionManager's conversation_sessions
            success = await self._update_conversation_state(
                session_id=state.session_id,
                conversation_state=state_dict,
                current_topic=state.current_topic,
                current_emotion=state.current_user_emotion,
                emotional_trend=state.get_emotional_trend(),
            )

            if success:
                # Update cache
                self._add_to_cache(state.session_id, state)
                logger.debug(f"Saved ConversationState for {state.session_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to save state for {state.session_id}: {e}")
            return False

    async def get_turn_history(
        self,
        session_id: str,
        max_turns: int = 10,
    ) -> List[ConversationTurn]:
        """
        Get conversation turn history from session.

        Args:
            session_id: Session UUID
            max_turns: Maximum turns to retrieve

        Returns:
            List of ConversationTurn objects
        """
        try:
            # Get context from SessionManager
            context = await self.session_manager.get_conversation_context(
                session_id=session_id,
                include_metadata=False,
            )

            turns_data = context.get("turns", [])

            # Convert to ConversationTurn objects
            turns = []
            for i, turn_data in enumerate(turns_data[-max_turns:]):
                try:
                    # Handle different turn data formats
                    if isinstance(turn_data, dict):
                        turn = ConversationTurn(
                            turn_number=turn_data.get("turn_number", i + 1),
                            user_query=turn_data.get("user_query", turn_data.get("query", "")),
                            assistant_response=turn_data.get("assistant_response", turn_data.get("response", "")),
                            query_type=turn_data.get("query_type", "factual"),
                            detected_emotion=turn_data.get("detected_emotion", "neutral"),
                            topic=turn_data.get("topic", ""),
                            sources_used=turn_data.get("sources_used", []),
                        )
                        turns.append(turn)
                except Exception as e:
                    logger.warning(f"Failed to parse turn {i}: {e}")
                    continue

            return turns

        except Exception as e:
            logger.warning(f"Failed to get turn history for {session_id}: {e}")
            return []

    async def add_facts(
        self,
        session_id: str,
        facts: List[str],
    ) -> bool:
        """
        Add facts to session for repetition avoidance.

        Args:
            session_id: Session UUID
            facts: List of facts provided in response

        Returns:
            True if successful
        """
        try:
            state = await self.get_or_create_state(
                session_id=session_id,
                user_id="",  # Will be overwritten if exists
                executive_id="",
            )

            state.add_facts(facts)
            return await self.save_state(state)

        except Exception as e:
            logger.warning(f"Failed to add facts to {session_id}: {e}")
            return False

    async def add_sources(
        self,
        session_id: str,
        sources: List[str],
    ) -> bool:
        """
        Add cited sources to session.

        Args:
            session_id: Session UUID
            sources: List of source IDs cited

        Returns:
            True if successful
        """
        try:
            state = await self.get_or_create_state(
                session_id=session_id,
                user_id="",
                executive_id="",
            )

            state.add_sources(sources)
            return await self.save_state(state)

        except Exception as e:
            logger.warning(f"Failed to add sources to {session_id}: {e}")
            return False

    async def _get_session_with_state(
        self,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get session info including conversation_state JSONB.

        Uses the get_session_with_state() function from Phase 1 migration.
        """
        try:
            # Get session info from SessionManager's conversation_sessions
            session_info = await self.session_manager.conversation_sessions.get_session_info(
                session_id=session_id
            )

            if session_info:
                # The conversation_state column is in the session info
                return session_info

            return None

        except Exception as e:
            logger.warning(f"Failed to get session with state: {e}")
            return None

    async def _update_conversation_state(
        self,
        session_id: str,
        conversation_state: Dict[str, Any],
        current_topic: Optional[str] = None,
        current_emotion: str = "neutral",
        emotional_trend: str = "stable",
    ) -> bool:
        """
        Update conversation_state JSONB column.

        Uses helper function from Phase 1 migration.
        """
        try:
            # Use the conversation_sessions to update
            pool = self.session_manager.conversation_sessions.pool

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE conversation_sessions
                    SET
                        conversation_state = $1::jsonb,
                        current_topic = COALESCE($2, current_topic),
                        current_emotion = $3,
                        emotional_trend = $4,
                        last_activity = NOW()
                    WHERE session_id = $5::uuid
                    """,
                    conversation_state,
                    current_topic,
                    current_emotion,
                    emotional_trend,
                    session_id,
                )

            return True

        except Exception as e:
            logger.error(f"Failed to update conversation state: {e}")
            return False

    # Cache management methods

    def _get_from_cache(
        self,
        session_id: str,
    ) -> Optional[ConversationState]:
        """Get state from cache if not expired."""
        if session_id in self._state_cache:
            state, cached_at = self._state_cache[session_id]
            if time.time() - cached_at < self._cache_ttl_seconds:
                return state
            else:
                # Expired, remove from cache
                del self._state_cache[session_id]
        return None

    def _add_to_cache(
        self,
        session_id: str,
        state: ConversationState,
    ) -> None:
        """Add state to cache with timestamp."""
        self._state_cache[session_id] = (state, time.time())

        # Limit cache size
        if len(self._state_cache) > 100:
            # Remove oldest entries
            oldest_key = min(
                self._state_cache.keys(),
                key=lambda k: self._state_cache[k][1]
            )
            del self._state_cache[oldest_key]

    def invalidate_cache(self, session_id: str) -> None:
        """Invalidate cached state for a session."""
        if session_id in self._state_cache:
            del self._state_cache[session_id]

    def clear_cache(self) -> None:
        """Clear entire state cache."""
        self._state_cache.clear()
