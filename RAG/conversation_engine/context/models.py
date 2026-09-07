"""
Context Management Data Models

Defines the core data structures for conversation state management,
session persistence, and context passing between pipeline stages.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ConversationMode(Enum):
    """
    Three modes of conversation handling with different capabilities and overhead.

    STATELESS: No session tracking, fastest path (~45ms overhead)
        - Trigger: No session_id provided
        - Use cases: curl tests, API integration, one-off queries

    SESSION: Multi-turn with history and reference resolution (~60ms overhead)
        - Trigger: session_id provided
        - Use cases: Chat UI, multi-turn conversations

    MEMORY_AWARE: Session + episodic memory + user preferences (~85ms overhead)
        - Trigger: session_id + user_id + memory_enabled=true
        - Use cases: Full relationship context, returning users
    """
    STATELESS = "stateless"
    SESSION = "session"
    MEMORY_AWARE = "memory_aware"


@dataclass
class ConversationTurn:
    """
    Single turn in a conversation with analysis metadata.

    Captures the user query, assistant response, and contextual analysis
    at the time of the turn for later reference and state tracking.
    """
    turn_number: int
    user_query: str
    assistant_response: str

    # Analysis at time of turn
    query_type: str = "factual"  # factual, decision, emotional, analytical
    detected_emotion: str = "neutral"  # stressed, tense, neutral, positive, celebratory
    topic: str = ""
    entities: List[str] = field(default_factory=list)

    # What was provided in this turn
    sources_used: List[str] = field(default_factory=list)
    facts_provided: List[str] = field(default_factory=list)
    response_tone: str = "neutral"

    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "turn_number": self.turn_number,
            "user_query": self.user_query,
            "assistant_response": self.assistant_response,
            "query_type": self.query_type,
            "detected_emotion": self.detected_emotion,
            "topic": self.topic,
            "entities": self.entities,
            "sources_used": self.sources_used,
            "facts_provided": self.facts_provided,
            "response_tone": self.response_tone,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationTurn":
        """Deserialize from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        return cls(
            turn_number=data["turn_number"],
            user_query=data["user_query"],
            assistant_response=data["assistant_response"],
            query_type=data.get("query_type", "factual"),
            detected_emotion=data.get("detected_emotion", "neutral"),
            topic=data.get("topic", ""),
            entities=data.get("entities", []),
            sources_used=data.get("sources_used", []),
            facts_provided=data.get("facts_provided", []),
            response_tone=data.get("response_tone", "neutral"),
            timestamp=timestamp,
        )


@dataclass
class ConversationState:
    """
    Persistent session state stored in PostgreSQL.

    Tracks conversation history, topics, emotions, and facts to:
    - Avoid repeating information already provided
    - Maintain emotional continuity
    - Enable reference resolution ("the timeline" → actual context)
    - Track decision-making patterns

    Includes explicit limits to prevent unbounded growth:
    - MAX_TURNS: 10 (keep first + last 9)
    - MAX_FACTS: 50 (most recent)
    - MAX_ENTITIES: 30 (most mentioned)
    - MAX_TOPICS: 20 (recent)
    """
    # Limits to prevent unbounded growth
    MAX_TURNS: int = 10
    MAX_FACTS: int = 50
    MAX_ENTITIES: int = 30
    MAX_TOPICS: int = 20

    # Session identification
    session_id: str = ""
    executive_id: str = ""
    user_id: Optional[str] = None

    # Turn history (bounded)
    turns: List[ConversationTurn] = field(default_factory=list)
    turn_count: int = 0

    # Topic tracking (bounded)
    current_topic: Optional[str] = None
    topic_history: List[str] = field(default_factory=list)
    entities_mentioned: Dict[str, int] = field(default_factory=dict)  # entity -> count

    # Decision tracking
    pending_decisions: List[str] = field(default_factory=list)
    decisions_made: List[Dict[str, Any]] = field(default_factory=list)

    # Emotional state tracking
    user_emotion_history: List[str] = field(default_factory=list)
    current_user_emotion: str = "neutral"

    # Avoid repetition (bounded)
    facts_already_provided: List[str] = field(default_factory=list)
    sources_already_cited: List[str] = field(default_factory=list)

    # Timestamps
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    def add_turn(self, turn: ConversationTurn) -> None:
        """
        Add a turn with automatic pruning to stay within MAX_TURNS.

        Keeps first turn (for context) + last (MAX_TURNS-1) turns.
        """
        self.turns.append(turn)
        self.turn_count += 1

        # Prune to keep first + last N-1 turns
        if len(self.turns) > self.MAX_TURNS:
            self.turns = [self.turns[0]] + self.turns[-(self.MAX_TURNS - 1):]

    def add_facts(self, facts: List[str]) -> None:
        """Add facts with automatic pruning to stay within MAX_FACTS."""
        self.facts_already_provided.extend(facts)
        if len(self.facts_already_provided) > self.MAX_FACTS:
            self.facts_already_provided = self.facts_already_provided[-self.MAX_FACTS:]

    def add_sources(self, sources: List[str]) -> None:
        """Add sources with deduplication."""
        for source in sources:
            if source not in self.sources_already_cited:
                self.sources_already_cited.append(source)

    def update_topic(self, topic: str) -> None:
        """Update current topic and history with pruning."""
        if topic and topic != self.current_topic:
            self.current_topic = topic
            self.topic_history.append(topic)
            if len(self.topic_history) > self.MAX_TOPICS:
                self.topic_history = self.topic_history[-self.MAX_TOPICS:]

    def update_entities(self, entities: List[str]) -> None:
        """Update entity mention counts with pruning."""
        for entity in entities:
            self.entities_mentioned[entity] = self.entities_mentioned.get(entity, 0) + 1

        # Keep only most mentioned entities
        if len(self.entities_mentioned) > self.MAX_ENTITIES:
            sorted_entities = sorted(
                self.entities_mentioned.items(),
                key=lambda x: x[1],
                reverse=True
            )
            self.entities_mentioned = dict(sorted_entities[:self.MAX_ENTITIES])

    def update_emotion(self, emotion: str) -> None:
        """Update emotion tracking."""
        self.current_user_emotion = emotion
        self.user_emotion_history.append(emotion)
        # Keep last 10 emotions for trend analysis
        if len(self.user_emotion_history) > 10:
            self.user_emotion_history = self.user_emotion_history[-10:]

    def get_emotional_trend(self) -> str:
        """
        Analyze emotional trend from history.

        Returns: stable, improving, or declining
        """
        if len(self.user_emotion_history) < 2:
            return "stable"

        # Map emotions to numeric values
        emotion_values = {
            "celebratory": 5,
            "positive": 4,
            "neutral": 3,
            "tense": 2,
            "stressed": 1,
        }

        recent = self.user_emotion_history[-3:]  # Last 3 emotions
        values = [emotion_values.get(e, 3) for e in recent]

        if len(values) < 2:
            return "stable"

        # Calculate trend
        trend = values[-1] - values[0]
        if trend > 0:
            return "improving"
        elif trend < 0:
            return "declining"
        return "stable"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for PostgreSQL JSONB storage."""
        return {
            "session_id": self.session_id,
            "executive_id": self.executive_id,
            "user_id": self.user_id,
            "turns": [t.to_dict() for t in self.turns],
            "turn_count": self.turn_count,
            "current_topic": self.current_topic,
            "topic_history": self.topic_history,
            "entities_mentioned": self.entities_mentioned,
            "pending_decisions": self.pending_decisions,
            "decisions_made": self.decisions_made,
            "user_emotion_history": self.user_emotion_history,
            "current_user_emotion": self.current_user_emotion,
            "facts_already_provided": self.facts_already_provided,
            "sources_already_cited": self.sources_already_cited,
            "started_at": self.started_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        """Deserialize from PostgreSQL JSONB."""
        turns = [ConversationTurn.from_dict(t) for t in data.get("turns", [])]

        started_at = data.get("started_at")
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)
        elif started_at is None:
            started_at = datetime.now()

        last_activity = data.get("last_activity")
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity)
        elif last_activity is None:
            last_activity = datetime.now()

        return cls(
            session_id=data.get("session_id", ""),
            executive_id=data.get("executive_id", ""),
            user_id=data.get("user_id"),
            turns=turns,
            turn_count=data.get("turn_count", 0),
            current_topic=data.get("current_topic"),
            topic_history=data.get("topic_history", []),
            entities_mentioned=data.get("entities_mentioned", {}),
            pending_decisions=data.get("pending_decisions", []),
            decisions_made=data.get("decisions_made", []),
            user_emotion_history=data.get("user_emotion_history", []),
            current_user_emotion=data.get("current_user_emotion", "neutral"),
            facts_already_provided=data.get("facts_already_provided", []),
            sources_already_cited=data.get("sources_already_cited", []),
            started_at=started_at,
            last_activity=last_activity,
        )


@dataclass
class ManagedContext:
    """
    Output of Context Manager, input to Conversation Engine stages.

    Aggregates all context needed for the pipeline:
    - Mode (determines which stages to run)
    - Session state (turn history, facts to avoid)
    - Episodic memory (past conversations, if MEMORY_AWARE)
    - Resolved references ("the timeline" → "MegaCorp contract expiry")
    - User preferences (learned from memory)
    """
    mode: ConversationMode

    # Session context (None if STATELESS)
    session_state: Optional[ConversationState] = None
    turn_history: List[ConversationTurn] = field(default_factory=list)

    # Episodic memory (empty if not MEMORY_AWARE)
    episodic_memory: List[Dict[str, Any]] = field(default_factory=list)

    # Reference resolution results
    resolved_references: Dict[str, str] = field(default_factory=dict)
    original_query: str = ""
    resolved_query: str = ""  # Query with references replaced

    # Avoid repetition
    facts_to_avoid: List[str] = field(default_factory=list)

    # User preferences (from memory)
    user_preferences: Optional[Dict[str, Any]] = None

    # Timing metadata
    context_load_time_ms: float = 0.0

    def is_multi_turn(self) -> bool:
        """Check if this is a multi-turn conversation (turn > 1)."""
        if self.session_state:
            return self.session_state.turn_count > 0
        return len(self.turn_history) > 0

    def get_turn_number(self) -> int:
        """Get current turn number (1-indexed)."""
        if self.session_state:
            return self.session_state.turn_count + 1
        return len(self.turn_history) + 1

    def get_emotional_trend(self) -> str:
        """Get emotional trend from session state."""
        if self.session_state:
            return self.session_state.get_emotional_trend()
        return "stable"
