"""
State Updater - Conversation Engine Component.

Handles post-response session state updates for multi-turn conversations.
Updates conversation history, tracks facts provided, and maintains emotional state.
"""

import re
import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..context.models import ConversationState, ConversationTurn
    from ..context.session_store import SessionStore
    from ..analysis.models import AnalyzedContext
    from ..calibration.models import ResponseCalibration

logger = logging.getLogger(__name__)


@dataclass
class StateUpdateResult:
    """Result of a state update operation."""

    success: bool
    session_id: str
    turn_number: int
    facts_tracked: List[str] = field(default_factory=list)
    sources_tracked: List[str] = field(default_factory=list)
    emotion_updated: bool = False
    error: Optional[str] = None
    update_time_ms: float = 0.0


class StateUpdater:
    """
    Updates session state after LLM response generation.

    Responsibilities:
    - Add conversation turn to history
    - Track facts provided (to avoid repetition in future turns)
    - Track sources cited
    - Update user emotion state based on response
    - Maintain topic continuity

    Thread-safe: Uses SessionStore for atomic updates.
    """

    # Patterns to extract facts from response
    FACT_PATTERNS = [
        r'(\d+%)',  # Percentages
        r'(¥[\d,]+(?:\s*(?:million|billion|M|B))?)',  # Yen amounts
        r'(\$[\d,]+(?:\s*(?:million|billion|M|B))?)',  # Dollar amounts
        r'(Q[1-4]\s*\d{4})',  # Quarterly references
        r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',  # Dates
        r'(DC_\w+_\d+)',  # Decision case IDs
        r'(\d+\s*(?:days?|weeks?|months?|years?))',  # Time durations
    ]

    # Citation patterns
    CITATION_PATTERNS = [
        r'\[Source:\s*([^\]]+)\]',
        r'\[([^\]]+\.(?:pdf|doc|xlsx|pptx))\]',
        r'(?:according to|from|per)\s+([A-Z][^,\.]+(?:\.pdf|\.doc)?)',
    ]

    def __init__(
        self,
        session_store: Optional["SessionStore"] = None,
    ):
        """
        Initialize StateUpdater.

        Args:
            session_store: SessionStore for persisting updates
        """
        self._session_store = session_store
        logger.debug("StateUpdater initialized")

    def update(
        self,
        session_id: str,
        query: str,
        response: str,
        analyzed_context: "AnalyzedContext",
        calibration: "ResponseCalibration",
        sources_used: Optional[List[str]] = None,
        llm_tokens: Optional[Dict[str, int]] = None,
    ) -> StateUpdateResult:
        """
        Update session state after response generation.

        Args:
            session_id: Session to update
            query: Original user query
            response: LLM response text
            analyzed_context: Query analysis from Phase 3
            calibration: Response calibration from Phase 3
            sources_used: List of source IDs cited
            llm_tokens: Token usage from LLM

        Returns:
            StateUpdateResult with update status
        """
        start_time = time.time()

        try:
            # Get current session state
            if self._session_store is None:
                logger.warning("No session store configured, skipping state update")
                return StateUpdateResult(
                    success=False,
                    session_id=session_id,
                    turn_number=0,
                    error="No session store configured",
                )

            session_state = self._session_store.get_session(session_id)
            if session_state is None:
                logger.warning(f"Session {session_id} not found, creating new session")
                # Create minimal session state
                from ..context.models import ConversationState
                session_state = ConversationState(
                    session_id=session_id,
                    executive_id="unknown",
                )

            # Extract facts from response
            facts_provided = self._extract_facts(response)

            # Extract citations from response
            citations = self._extract_citations(response, sources_used or [])

            # Create conversation turn
            turn = self._create_turn(
                query=query,
                response=response,
                analyzed_context=analyzed_context,
                calibration=calibration,
                facts_provided=facts_provided,
                sources_used=citations,
                llm_tokens=llm_tokens,
            )

            # Update session state
            updated_state = self._update_session_state(
                session_state=session_state,
                turn=turn,
                analyzed_context=analyzed_context,
                facts_provided=facts_provided,
            )

            # Persist updated state
            self._session_store.save_session(updated_state)

            update_time = (time.time() - start_time) * 1000

            logger.info(
                f"Session {session_id} updated: turn {updated_state.turn_count}, "
                f"{len(facts_provided)} facts, {len(citations)} sources "
                f"({update_time:.1f}ms)"
            )

            return StateUpdateResult(
                success=True,
                session_id=session_id,
                turn_number=updated_state.turn_count,
                facts_tracked=facts_provided,
                sources_tracked=citations,
                emotion_updated=True,
                update_time_ms=update_time,
            )

        except Exception as e:
            logger.error(f"State update failed for session {session_id}: {e}")
            return StateUpdateResult(
                success=False,
                session_id=session_id,
                turn_number=0,
                error=str(e),
                update_time_ms=(time.time() - start_time) * 1000,
            )

    def _extract_facts(self, response: str) -> List[str]:
        """
        Extract key facts from response to track for future turns.

        Extracts:
        - Percentages (23%, 15%)
        - Monetary amounts (¥50M, $100K)
        - Dates and time references
        - Decision case IDs
        - Specific numbers and metrics

        Args:
            response: LLM response text

        Returns:
            List of extracted facts
        """
        facts = []

        for pattern in self.FACT_PATTERNS:
            matches = re.findall(pattern, response, re.IGNORECASE)
            facts.extend(matches)

        # Deduplicate and limit
        unique_facts = list(dict.fromkeys(facts))[:10]  # Keep top 10

        return unique_facts

    def _extract_citations(
        self,
        response: str,
        known_sources: List[str],
    ) -> List[str]:
        """
        Extract citations from response.

        Args:
            response: LLM response text
            known_sources: List of sources that were available

        Returns:
            List of cited source names
        """
        citations = []

        # Extract from citation patterns
        for pattern in self.CITATION_PATTERNS:
            matches = re.findall(pattern, response, re.IGNORECASE)
            citations.extend(matches)

        # Also check for known sources mentioned
        for source in known_sources:
            if source.lower() in response.lower():
                citations.append(source)

        # Deduplicate
        unique_citations = list(dict.fromkeys(citations))

        return unique_citations

    def _create_turn(
        self,
        query: str,
        response: str,
        analyzed_context: "AnalyzedContext",
        calibration: "ResponseCalibration",
        facts_provided: List[str],
        sources_used: List[str],
        llm_tokens: Optional[Dict[str, int]] = None,
    ) -> "ConversationTurn":
        """
        Create a ConversationTurn record.

        Args:
            query: User query
            response: LLM response
            analyzed_context: Query analysis
            calibration: Response calibration
            facts_provided: Facts extracted from response
            sources_used: Sources cited
            llm_tokens: Token usage

        Returns:
            ConversationTurn object
        """
        from ..context.models import ConversationTurn
        import datetime

        return ConversationTurn(
            query=query,
            response=response,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            theme=analyzed_context.theme.value if analyzed_context.theme else None,
            emotion=analyzed_context.user_emotion.value if analyzed_context.user_emotion else None,
            turn_type=analyzed_context.turn_type.value if analyzed_context.turn_type else None,
            tone_used=calibration.tone,
            warmth_used=calibration.warmth_level,
            facts_provided=facts_provided,
            sources_used=sources_used,
            tokens_used=llm_tokens or {},
        )

    def _update_session_state(
        self,
        session_state: "ConversationState",
        turn: "ConversationTurn",
        analyzed_context: "AnalyzedContext",
        facts_provided: List[str],
    ) -> "ConversationState":
        """
        Update session state with new turn information.

        Args:
            session_state: Current session state
            turn: New conversation turn
            analyzed_context: Query analysis
            facts_provided: Facts from response

        Returns:
            Updated ConversationState
        """
        # Add turn to history
        if session_state.conversation_history is None:
            session_state.conversation_history = []
        session_state.conversation_history.append(turn)

        # Update turn count
        session_state.turn_count = len(session_state.conversation_history)

        # Update topic if changed
        if analyzed_context.theme:
            # Keep topic if same theme, otherwise note topic shift
            theme_str = analyzed_context.theme.value
            if session_state.current_topic:
                if theme_str not in session_state.current_topic.lower():
                    session_state.current_topic = f"{session_state.current_topic} → {theme_str}"
            else:
                session_state.current_topic = theme_str

        # Update emotion tracking
        if analyzed_context.user_emotion:
            emotion_str = analyzed_context.user_emotion.value
            session_state.current_user_emotion = emotion_str
            if session_state.user_emotion_history is None:
                session_state.user_emotion_history = []
            session_state.user_emotion_history.append(emotion_str)

        # Update facts mentioned (for "don't repeat" tracking)
        if session_state.facts_mentioned is None:
            session_state.facts_mentioned = []
        session_state.facts_mentioned.extend(facts_provided)
        # Keep last 20 facts
        session_state.facts_mentioned = session_state.facts_mentioned[-20:]

        # Update last activity timestamp
        import datetime
        session_state.last_activity = datetime.datetime.now(datetime.timezone.utc)

        return session_state

    def get_facts_to_avoid(
        self,
        session_id: str,
        max_facts: int = 5,
    ) -> List[str]:
        """
        Get facts to avoid repeating in next response.

        Args:
            session_id: Session ID
            max_facts: Maximum facts to return

        Returns:
            List of facts mentioned recently
        """
        if self._session_store is None:
            return []

        session_state = self._session_store.get_session(session_id)
        if session_state is None:
            return []

        facts = session_state.facts_mentioned or []
        return facts[-max_facts:]  # Most recent facts


# Singleton instance
_default_updater: Optional[StateUpdater] = None


def get_state_updater() -> StateUpdater:
    """Get singleton StateUpdater instance."""
    global _default_updater
    if _default_updater is None:
        _default_updater = StateUpdater()
    return _default_updater


def create_state_updater(
    session_store: Optional["SessionStore"] = None,
) -> StateUpdater:
    """Create a new StateUpdater instance."""
    return StateUpdater(session_store=session_store)
