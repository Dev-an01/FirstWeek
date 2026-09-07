"""
Example Selection Data Models

Defines the output of semantic example selection.
Used by Stage 3 (Example Selector) of the Conversation Engine.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class SelectedExample:
    """
    Output of Semantic Example Selector (Stage 3).

    Contains the best-matching communication example for the current query,
    along with matching scores and metadata.

    The example is used in the prompt to guide the LLM on:
    - Communication style (tone, structure)
    - Response length and format
    - Appropriate level of formality
    - Use of emojis and casual language

    Example selection uses multi-signal matching:
    - 70% semantic similarity (embedding distance)
    - 10% type match bonus (email vs slack)
    - 10% length appropriateness
    - 10% emotional tone match
    """
    # Example identification
    example_id: str = ""  # e.g., "CE_AKIKO_001"
    example_type: str = ""  # email, slack, slack_dm

    # Example content
    context: str = ""  # Situation/context of the example
    full_text: str = ""  # Complete example text

    # Matching scores
    similarity_score: float = 0.0  # Overall match score (0-1)
    semantic_score: float = 0.0  # Embedding similarity (0-1)
    type_bonus: float = 0.0  # Type match bonus (0-0.1)
    length_bonus: float = 0.0  # Length appropriateness bonus (0-0.1)
    tone_bonus: float = 0.0  # Emotional tone match bonus (0-0.1)

    # Match metadata
    match_reason: str = ""  # Human-readable match explanation
    match_signals: Dict[str, float] = field(default_factory=dict)

    # Alternative examples (if close matches exist)
    runner_up_id: Optional[str] = None
    runner_up_score: float = 0.0

    # Fallback flag
    is_fallback: bool = False  # True if no good match, using generic calibration
    fallback_reason: Optional[str] = None

    # Timing
    selection_time_ms: float = 0.0

    def is_good_match(self, threshold: float = 0.6) -> bool:
        """Check if this is a confident match above threshold."""
        return self.similarity_score >= threshold and not self.is_fallback

    def get_truncated_example(self, max_tokens: int = 150) -> str:
        """
        Get example text truncated to fit token budget.

        P2 Fix: Smart truncation that preserves:
        - Complete sentences (not cut mid-sentence)
        - Sign-off line (e.g., "— R", "- sample")
        - Structure (opener + middle + closer)

        Approximates 1 token ≈ 4 characters.
        """
        max_chars = max_tokens * 4
        if len(self.full_text) <= max_chars:
            return self.full_text

        text = self.full_text

        # Try to preserve sign-off (last line starting with "—", "-", or short name)
        lines = text.strip().split('\n')
        sign_off = ""
        sign_off_patterns = ["—", "- ", "–"]

        if len(lines) > 1:
            last_line = lines[-1].strip()
            # Check if last line looks like a sign-off (short, starts with dash)
            if len(last_line) < 50 and any(last_line.startswith(p) for p in sign_off_patterns):
                sign_off = "\n" + last_line
                lines = lines[:-1]
                text = '\n'.join(lines)

        # Calculate available chars for main content
        available_chars = max_chars - len(sign_off) - 3  # -3 for "..."

        if len(text) <= available_chars:
            return text + sign_off

        # Truncate at sentence boundary if possible
        truncated = text[:available_chars]

        # Find last complete sentence (., !, ?)
        last_period = max(
            truncated.rfind('. '),
            truncated.rfind('! '),
            truncated.rfind('? '),
            truncated.rfind('.\n'),
            truncated.rfind('!\n'),
            truncated.rfind('?\n'),
        )

        # If we found a sentence boundary in the last 40% of text, use it
        if last_period > available_chars * 0.6:
            truncated = truncated[:last_period + 1]
        else:
            # Otherwise, truncate at last space to avoid cutting words
            last_space = truncated.rfind(' ')
            if last_space > available_chars * 0.7:
                truncated = truncated[:last_space]

        return truncated.rstrip() + "..." + sign_off

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/debugging."""
        return {
            "example_id": self.example_id,
            "example_type": self.example_type,
            "context": self.context,
            "full_text_length": len(self.full_text),
            "similarity_score": self.similarity_score,
            "semantic_score": self.semantic_score,
            "type_bonus": self.type_bonus,
            "length_bonus": self.length_bonus,
            "tone_bonus": self.tone_bonus,
            "match_reason": self.match_reason,
            "match_signals": self.match_signals,
            "is_fallback": self.is_fallback,
            "fallback_reason": self.fallback_reason,
            "selection_time_ms": self.selection_time_ms,
        }

    @classmethod
    def create_fallback(cls, reason: str = "no_matching_examples") -> "SelectedExample":
        """Create a fallback when no good example match is found."""
        return cls(
            example_id="FALLBACK",
            example_type="generic",
            context="Generic professional communication",
            full_text="",
            similarity_score=0.0,
            is_fallback=True,
            fallback_reason=reason,
            match_reason=f"Fallback: {reason}",
        )


@dataclass
class ExampleEmbedding:
    """
    Pre-computed embedding for a communication example.

    Embeddings are computed on profile load and cached for fast retrieval.
    The embedding combines context and the first 200 characters of the example
    to capture both situational and stylistic signals.
    """
    example_id: str
    example_type: str  # email, slack, slack_dm
    executive_id: str

    # Pre-computed embedding
    embedding: List[float] = field(default_factory=list)

    # Metadata for scoring bonuses
    context: str = ""
    full_text: str = ""  # Full example text for prompt inclusion
    word_count: int = 0
    tone_markers: List[str] = field(default_factory=list)  # e.g., ["empathetic", "direct"]
    has_emoji: bool = False
    formality_score: int = 5  # 1-10

    # Cache metadata
    computed_at: Optional[str] = None
    model_name: str = "BAAI/bge-m3"  # MIGRATED: from all-MiniLM-L6-v2

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for caching."""
        return {
            "example_id": self.example_id,
            "example_type": self.example_type,
            "executive_id": self.executive_id,
            "embedding": self.embedding,
            "context": self.context,
            "full_text": self.full_text,
            "word_count": self.word_count,
            "tone_markers": self.tone_markers,
            "has_emoji": self.has_emoji,
            "formality_score": self.formality_score,
            "computed_at": self.computed_at,
            "model_name": self.model_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExampleEmbedding":
        """Deserialize from cache."""
        return cls(
            example_id=data["example_id"],
            example_type=data["example_type"],
            executive_id=data["executive_id"],
            embedding=data.get("embedding", []),
            context=data.get("context", ""),
            full_text=data.get("full_text", ""),
            word_count=data.get("word_count", 0),
            tone_markers=data.get("tone_markers", []),
            has_emoji=data.get("has_emoji", False),
            formality_score=data.get("formality_score", 5),
            computed_at=data.get("computed_at"),
            model_name=data.get("model_name", "BAAI/bge-m3"),  # MIGRATED
        )
