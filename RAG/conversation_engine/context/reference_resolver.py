"""
Reference Resolver - Resolves vague references in multi-turn conversations.

Handles conversational references like:
- "the timeline" → "MegaCorp contract expiry deadline"
- "the discussion" → "budget allocation conversation"
- "what we talked about" → previous topic
- "that decision" → last decision mentioned

Resolution Strategy:
1. Pattern matching for reference phrases
2. Look up in session state (entities_mentioned, current_topic)
3. Return mapping + resolved query
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any

from .models import ConversationState

logger = logging.getLogger(__name__)


class ReferenceResolver:
    """
    Resolves vague references in multi-turn conversations.

    Uses pattern matching to identify reference phrases, then looks them up
    in the conversation session state to find concrete replacements.

    Thread-safe: No mutable state, can be shared across requests.
    """

    # Reference patterns: (regex_pattern, reference_type)
    # Ordered by specificity (more specific patterns first)
    REFERENCE_PATTERNS: List[Tuple[str, str]] = [
        # Temporal references
        (r"\bthe timeline\b", "temporal"),
        (r"\bthe deadline\b", "temporal"),
        (r"\bthe schedule\b", "temporal"),
        (r"\bthe timeframe\b", "temporal"),
        (r"\bthe due date\b", "temporal"),

        # Discussion/conversation references
        (r"\bthe discussion\b", "discussion"),
        (r"\bthe conversation\b", "discussion"),
        (r"\bwhat we (talked|discussed|covered) about\b", "previous_topic"),
        (r"\bour (last|previous) (talk|discussion|conversation)\b", "previous_topic"),
        (r"\bearlier\b", "previous_topic"),

        # Decision references
        (r"\bthat decision\b", "last_decision"),
        (r"\bthe decision\b", "last_decision"),
        (r"\bwhat (we|I) decided\b", "last_decision"),

        # Topic references
        (r"\bthat issue\b", "current_topic"),
        (r"\bthe issue\b", "current_topic"),
        (r"\bthe problem\b", "current_topic"),
        (r"\bthis topic\b", "current_topic"),
        (r"\bthat matter\b", "current_topic"),

        # Entity references (pronouns - be careful with these)
        (r"\bthey(?!\s+(are|were|have|had|will|would|can|could|should|might))\b", "last_entity"),
        (r"\btheir\b", "last_entity"),
        (r"\bthem\b", "last_entity"),
    ]

    # Keywords that indicate temporal context
    TEMPORAL_KEYWORDS = [
        "deadline", "timeline", "schedule", "date", "expiry", "expiration",
        "due", "target", "milestone", "eta", "delivery"
    ]

    def __init__(self):
        """Initialize reference resolver."""
        # Compile patterns for performance
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), ref_type)
            for pattern, ref_type in self.REFERENCE_PATTERNS
        ]

    def resolve(
        self,
        query: str,
        session_state: ConversationState,
    ) -> Tuple[str, Dict[str, str]]:
        """
        Resolve references in query.

        Args:
            query: User's query text
            session_state: Current conversation state with history

        Returns:
            Tuple of (resolved_query, references_map)
            - resolved_query: Query with references replaced
            - references_map: {"the timeline": "MegaCorp deadline", ...}
        """
        if not query or not session_state:
            return query, {}

        # Skip resolution for first turn (no history to reference)
        if session_state.turn_count == 0:
            return query, {}

        resolved_query = query
        references_map: Dict[str, str] = {}

        # Find and resolve each pattern
        for pattern, ref_type in self._compiled_patterns:
            matches = pattern.finditer(resolved_query)
            for match in matches:
                original_text = match.group(0)

                # Skip if already resolved
                if original_text in references_map:
                    continue

                try:
                    resolved_text = self._lookup_reference(
                        reference_type=ref_type,
                        original_text=original_text,
                        session_state=session_state,
                    )

                    if resolved_text and resolved_text != original_text:
                        references_map[original_text] = resolved_text
                        resolved_query = resolved_query.replace(
                            original_text, resolved_text, 1
                        )

                except Exception as e:
                    logger.warning(
                        f"Reference resolution failed for '{original_text}': {e}"
                    )
                    # Continue with other references, don't break flow

        if references_map:
            logger.debug(
                f"Resolved {len(references_map)} references: {references_map}"
            )

        return resolved_query, references_map

    def _lookup_reference(
        self,
        reference_type: str,
        original_text: str,
        session_state: ConversationState,
    ) -> Optional[str]:
        """
        Look up reference in session context.

        Args:
            reference_type: Type of reference (temporal, discussion, etc.)
            original_text: Original matched text
            session_state: Session state to search

        Returns:
            Resolved text or None if not found
        """
        try:
            if reference_type == "temporal":
                return self._resolve_temporal(session_state)

            elif reference_type in ("discussion", "previous_topic"):
                return self._resolve_topic(session_state)

            elif reference_type == "last_decision":
                return self._resolve_decision(session_state)

            elif reference_type == "current_topic":
                return self._resolve_current_topic(session_state)

            elif reference_type == "last_entity":
                return self._resolve_entity(session_state)

            else:
                logger.debug(f"Unknown reference type: {reference_type}")
                return None

        except Exception as e:
            logger.warning(
                f"Lookup failed for {reference_type} '{original_text}': {e}"
            )
            return None

    def _resolve_temporal(
        self,
        session_state: ConversationState,
    ) -> Optional[str]:
        """
        Resolve temporal references like "the timeline".

        Looks for entities containing temporal keywords.
        """
        # Check entities for temporal-related ones
        temporal_entities = []
        for entity, count in session_state.entities_mentioned.items():
            entity_lower = entity.lower()
            if any(kw in entity_lower for kw in self.TEMPORAL_KEYWORDS):
                temporal_entities.append((entity, count))

        # Return most mentioned temporal entity
        if temporal_entities:
            temporal_entities.sort(key=lambda x: x[1], reverse=True)
            return temporal_entities[0][0]

        # Fallback: check turns for timeline mentions
        for turn in reversed(session_state.turns[-3:]):  # Last 3 turns
            text = turn.user_query + " " + turn.assistant_response
            for kw in self.TEMPORAL_KEYWORDS:
                if kw in text.lower():
                    # Extract context around keyword
                    return self._extract_context(text, kw)

        return None

    def _resolve_topic(
        self,
        session_state: ConversationState,
    ) -> Optional[str]:
        """
        Resolve discussion/topic references.

        Returns previous or current topic.
        """
        # Try topic history
        if len(session_state.topic_history) > 1:
            return session_state.topic_history[-2]  # Previous topic

        # Fall back to current topic
        if session_state.current_topic:
            return session_state.current_topic

        # Last resort: infer from last turn
        if session_state.turns:
            last_turn = session_state.turns[-1]
            if last_turn.topic:
                return last_turn.topic

        return None

    def _resolve_decision(
        self,
        session_state: ConversationState,
    ) -> Optional[str]:
        """
        Resolve decision references like "that decision".

        Returns summary of last decision made.
        """
        if session_state.decisions_made:
            last_decision = session_state.decisions_made[-1]
            # Return summary or description
            if isinstance(last_decision, dict):
                return last_decision.get(
                    "summary",
                    last_decision.get("description", str(last_decision))
                )
            return str(last_decision)

        # Check pending decisions
        if session_state.pending_decisions:
            return session_state.pending_decisions[-1]

        return None

    def _resolve_current_topic(
        self,
        session_state: ConversationState,
    ) -> Optional[str]:
        """
        Resolve current topic references.

        Returns current conversation topic.
        """
        if session_state.current_topic:
            return session_state.current_topic

        # Infer from last turn
        if session_state.turns:
            last_turn = session_state.turns[-1]
            if last_turn.topic:
                return last_turn.topic

        return None

    def _resolve_entity(
        self,
        session_state: ConversationState,
    ) -> Optional[str]:
        """
        Resolve entity references like "they" or "them".

        Returns most recently/frequently mentioned entity.
        """
        if not session_state.entities_mentioned:
            return None

        # Get most mentioned entity
        sorted_entities = sorted(
            session_state.entities_mentioned.items(),
            key=lambda x: x[1],
            reverse=True
        )

        if sorted_entities:
            return sorted_entities[0][0]

        return None

    def _extract_context(
        self,
        text: str,
        keyword: str,
        context_words: int = 3,
    ) -> Optional[str]:
        """
        Extract context around a keyword from text.

        Args:
            text: Full text to search
            keyword: Keyword to find
            context_words: Number of words before/after to include

        Returns:
            Context string or None
        """
        try:
            words = text.split()
            keyword_lower = keyword.lower()

            for i, word in enumerate(words):
                if keyword_lower in word.lower():
                    start = max(0, i - context_words)
                    end = min(len(words), i + context_words + 1)
                    context = " ".join(words[start:end])
                    return context

        except Exception:
            pass

        return None

    def find_references(self, query: str) -> List[Dict[str, Any]]:
        """
        Find all references in query without resolving them.

        Useful for debugging or analysis.

        Args:
            query: Query text

        Returns:
            List of found references with metadata
        """
        found = []
        for pattern, ref_type in self._compiled_patterns:
            for match in pattern.finditer(query):
                found.append({
                    "text": match.group(0),
                    "type": ref_type,
                    "start": match.start(),
                    "end": match.end(),
                })
        return found


# Singleton instance for stateless use
_default_resolver: Optional[ReferenceResolver] = None


def get_reference_resolver() -> ReferenceResolver:
    """Get singleton ReferenceResolver instance."""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = ReferenceResolver()
    return _default_resolver
