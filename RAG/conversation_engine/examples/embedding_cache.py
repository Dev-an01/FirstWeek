"""
Embedding Cache for Conversation Engine.

Caches pre-computed embeddings for communication examples and decision cases
per executive profile. Embeddings are computed on first access and reused.

Target: <1ms cache retrieval after initial warming.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np

from .models import ExampleEmbedding
from ..precedents.models import PrecedentEmbedding

logger = logging.getLogger(__name__)


@dataclass
class ProfileEmbeddings:
    """Container for all embeddings for a single executive profile."""
    executive_id: str
    examples: List[ExampleEmbedding] = field(default_factory=list)
    precedents: List[PrecedentEmbedding] = field(default_factory=list)
    loaded_at: Optional[datetime] = None
    model_version: str = "BAAI/bge-m3"  # MIGRATED: from all-MiniLM-L6-v2

    # Numpy arrays for fast similarity computation
    example_embeddings_array: Optional[np.ndarray] = None
    precedent_embeddings_array: Optional[np.ndarray] = None

    def is_valid(self) -> bool:
        """Check if cache is valid."""
        return self.loaded_at is not None and (
            len(self.examples) > 0 or len(self.precedents) > 0
        )


class EmbeddingCache:
    """
    In-memory cache for pre-computed example and precedent embeddings.

    Cache structure:
    {
        "exec_001_test": ProfileEmbeddings(
            examples=[ExampleEmbedding, ...],
            precedents=[PrecedentEmbedding, ...],
            example_embeddings_array=np.ndarray,  # (n, 1024)  MIGRATED from 384
            precedent_embeddings_array=np.ndarray,  # (m, 1024)  MIGRATED from 384
        )
    }

    Features:
    - Lazy loading on first access
    - Pre-computed numpy arrays for vectorized similarity
    - Profile invalidation support
    - Model version tracking
    """

    # Default paths
    PROFILES_DIR = Path(__file__).parent.parent.parent / "test_data" / "executive_profiles"
    MODEL_NAME = "BAAI/bge-m3"  # MIGRATED: from all-MiniLM-L6-v2

    def __init__(self, embedding_service=None, profiles_dir: Optional[Path] = None):
        """
        Initialize EmbeddingCache.

        Args:
            embedding_service: EmbeddingService instance (lazy loaded if None)
            profiles_dir: Path to executive profiles directory
        """
        self._cache: Dict[str, ProfileEmbeddings] = {}
        self._embedding_service = embedding_service
        self._profiles_dir = profiles_dir or self.PROFILES_DIR

        logger.debug(f"EmbeddingCache initialized (profiles_dir={self._profiles_dir})")

    def _ensure_embedding_service(self):
        """Lazy load embedding service."""
        if self._embedding_service is None:
            from .embedding_service import get_embedding_service
            self._embedding_service = get_embedding_service()

    def get_example_embeddings(self, profile_id: str) -> List[ExampleEmbedding]:
        """
        Get cached example embeddings for a profile.

        Loads and computes embeddings on first access.

        Args:
            profile_id: Executive profile ID

        Returns:
            List of ExampleEmbedding objects
        """
        self._ensure_cache(profile_id)
        return self._cache[profile_id].examples

    def get_precedent_embeddings(self, profile_id: str) -> List[PrecedentEmbedding]:
        """
        Get cached precedent embeddings for a profile.

        Loads and computes embeddings on first access.

        Args:
            profile_id: Executive profile ID

        Returns:
            List of PrecedentEmbedding objects
        """
        self._ensure_cache(profile_id)
        return self._cache[profile_id].precedents

    def get_example_embeddings_array(self, profile_id: str) -> np.ndarray:
        """
        Get example embeddings as numpy array for vectorized similarity.

        Args:
            profile_id: Executive profile ID

        Returns:
            Numpy array of shape (n_examples, 1024)  # MIGRATED from 384
        """
        self._ensure_cache(profile_id)
        return self._cache[profile_id].example_embeddings_array

    def get_precedent_embeddings_array(self, profile_id: str) -> np.ndarray:
        """
        Get precedent embeddings as numpy array for vectorized similarity.

        Args:
            profile_id: Executive profile ID

        Returns:
            Numpy array of shape (n_precedents, 1024)  # MIGRATED from 384
        """
        self._ensure_cache(profile_id)
        return self._cache[profile_id].precedent_embeddings_array

    def _ensure_cache(self, profile_id: str) -> None:
        """Ensure cache is populated for profile."""
        if profile_id not in self._cache or not self._cache[profile_id].is_valid():
            self._warm_cache(profile_id)

    def _warm_cache(self, profile_id: str) -> None:
        """
        Load and compute embeddings for a profile.

        Called on first access to a profile.
        """
        start = time.time()
        self._ensure_embedding_service()

        # Load profile data
        profile_data = self._load_profile(profile_id)
        if not profile_data:
            logger.warning(f"Profile not found: {profile_id}")
            self._cache[profile_id] = ProfileEmbeddings(
                executive_id=profile_id,
                loaded_at=datetime.now(),
            )
            return

        # Extract examples and precedents
        examples = profile_data.get("communication_examples", [])
        precedents = profile_data.get("decision_cases", [])

        logger.info(
            f"Warming cache for {profile_id}: "
            f"{len(examples)} examples, {len(precedents)} precedents"
        )

        # Compute example embeddings
        example_embeddings = self._compute_example_embeddings(
            examples, profile_id
        )

        # Compute precedent embeddings
        precedent_embeddings = self._compute_precedent_embeddings(
            precedents, profile_id
        )

        # Build numpy arrays for vectorized operations
        example_array = None
        if example_embeddings:
            example_array = np.array([e.embedding for e in example_embeddings])

        precedent_array = None
        if precedent_embeddings:
            precedent_array = np.array([p.embedding for p in precedent_embeddings])

        # Store in cache
        self._cache[profile_id] = ProfileEmbeddings(
            executive_id=profile_id,
            examples=example_embeddings,
            precedents=precedent_embeddings,
            loaded_at=datetime.now(),
            model_version=self.MODEL_NAME,
            example_embeddings_array=example_array,
            precedent_embeddings_array=precedent_array,
        )

        warm_time = (time.time() - start) * 1000
        logger.info(
            f"Cache warmed for {profile_id} in {warm_time:.0f}ms "
            f"({len(example_embeddings)} examples, {len(precedent_embeddings)} precedents)"
        )

    def _load_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Load profile data from JSON file."""
        # Try to find profile file by ID
        # Profile files are named like "akiko_tanaka.json" with ID inside

        for profile_path in self._profiles_dir.glob("*.json"):
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("id") == profile_id:
                        return data
            except Exception as e:
                logger.warning(f"Failed to read {profile_path}: {e}")
                continue

        return None

    def _compute_example_embeddings(
        self,
        examples: List[Dict[str, Any]],
        executive_id: str,
    ) -> List[ExampleEmbedding]:
        """
        Compute embeddings for communication examples.

        Embedding strategy: context + first 200 chars of full_text
        """
        if not examples:
            return []

        example_embeddings = []
        texts_to_embed = []
        example_metadata = []

        for ex in examples:
            # Build text for embedding: context + first 200 chars
            context = ex.get("context", "")
            full_text = ex.get("full_text", "")
            embed_text = f"{context} {full_text[:200]}"
            texts_to_embed.append(embed_text)

            # Analyze example metadata
            word_count = len(full_text.split())
            has_emoji = any(ord(c) > 0x1F300 for c in full_text)
            tone_markers = self._detect_tone_markers(full_text)
            formality_score = self._estimate_formality(full_text)

            example_metadata.append({
                "example_id": ex.get("example_id", ""),
                "example_type": ex.get("type", ""),
                "context": context,
                "full_text": full_text,
                "word_count": word_count,
                "has_emoji": has_emoji,
                "tone_markers": tone_markers,
                "formality_score": formality_score,
            })

        # Batch embed all texts
        embeddings_array, _ = self._embedding_service.embed_texts_batch(texts_to_embed)

        # Build ExampleEmbedding objects
        for i, metadata in enumerate(example_metadata):
            example_embeddings.append(ExampleEmbedding(
                example_id=metadata["example_id"],
                example_type=metadata["example_type"],
                executive_id=executive_id,
                embedding=embeddings_array[i].tolist(),
                context=metadata["context"],
                full_text=metadata["full_text"],  # Store full example text
                word_count=metadata["word_count"],
                tone_markers=metadata["tone_markers"],
                has_emoji=metadata["has_emoji"],
                formality_score=metadata["formality_score"],
                computed_at=datetime.now().isoformat(),
                model_name=self.MODEL_NAME,
            ))

        return example_embeddings

    def _compute_precedent_embeddings(
        self,
        precedents: List[Dict[str, Any]],
        executive_id: str,
    ) -> List[PrecedentEmbedding]:
        """
        Compute embeddings for decision cases.

        Embedding strategy: situation[:300] + decision_made[:200]
        """
        if not precedents:
            return []

        precedent_embeddings = []
        texts_to_embed = []
        precedent_metadata = []

        for dc in precedents:
            # Build text for embedding: situation + decision
            situation = dc.get("situation", "")[:300]
            decision = dc.get("decision_made", "")[:200]
            embed_text = f"{situation} {decision}"
            texts_to_embed.append(embed_text)

            # Extract summaries (truncate if needed)
            situation_summary = self._summarize_text(dc.get("situation", ""), 100)
            decision_summary = self._summarize_text(dc.get("decision_made", ""), 80)
            rationale_summary = self._summarize_text(dc.get("rationale", ""), 80)
            outcome_summary = self._summarize_text(dc.get("outcome", ""), 60)

            # Determine outcome type
            outcome = dc.get("outcome", "").upper()
            if "SUCCESS" in outcome:
                outcome_type = "SUCCESS"
            elif "MIXED" in outcome or "PARTIAL" in outcome:
                outcome_type = "MIXED"
            elif "FAIL" in outcome:
                outcome_type = "FAILURE"
            else:
                outcome_type = "UNKNOWN"

            # Extract stakeholders from context
            stakeholders = []
            context = dc.get("context", {})
            if isinstance(context, dict):
                for_approval = context.get("stakeholders", {}).get("for_approval", [])
                against = context.get("stakeholders", {}).get("against", [])
                stakeholders = for_approval + against

            precedent_metadata.append({
                "case_id": dc.get("case_id", ""),
                "category": dc.get("category", ""),
                "date": dc.get("date", ""),
                "situation_summary": situation_summary,
                "decision_summary": decision_summary,
                "rationale_summary": rationale_summary,
                "outcome_summary": outcome_summary,
                "outcome_type": outcome_type,
                "full_situation": dc.get("situation", ""),
                "full_rationale": dc.get("rationale", ""),
                "key_factors": dc.get("values_aligned", []),
                "stakeholders": stakeholders,
            })

        # Batch embed all texts
        embeddings_array, _ = self._embedding_service.embed_texts_batch(texts_to_embed)

        # Build PrecedentEmbedding objects
        for i, metadata in enumerate(precedent_metadata):
            precedent_embeddings.append(PrecedentEmbedding(
                case_id=metadata["case_id"],
                category=metadata["category"],
                executive_id=executive_id,
                embedding=embeddings_array[i].tolist(),
                date=metadata["date"],
                situation_summary=metadata["situation_summary"],
                decision_summary=metadata["decision_summary"],
                rationale_summary=metadata["rationale_summary"],
                outcome_summary=metadata["outcome_summary"],
                outcome_type=metadata["outcome_type"],
                full_situation=metadata["full_situation"],
                full_rationale=metadata["full_rationale"],
                key_factors=metadata["key_factors"],
                stakeholders=metadata["stakeholders"],
                computed_at=datetime.now().isoformat(),
                model_name=self.MODEL_NAME,
            ))

        return precedent_embeddings

    def _detect_tone_markers(self, text: str) -> List[str]:
        """Detect emotional tone markers in text."""
        markers = []
        text_lower = text.lower()

        # Empathetic markers
        if any(w in text_lower for w in ["understand", "hear you", "feel", "appreciate"]):
            markers.append("empathetic")

        # Direct markers
        if any(w in text_lower for w in ["need to", "must", "should", "decision"]):
            markers.append("direct")

        # Supportive markers
        if any(w in text_lower for w in ["help", "support", "here for you", "together"]):
            markers.append("supportive")

        # Analytical markers
        if any(w in text_lower for w in ["data", "analysis", "roi", "metrics", "numbers"]):
            markers.append("analytical")

        # Celebratory markers
        if any(w in text_lower for w in ["congratulations", "amazing", "excellent", "great news"]):
            markers.append("celebratory")

        return markers if markers else ["neutral"]

    def _estimate_formality(self, text: str) -> int:
        """Estimate formality level 1-10."""
        score = 5  # Start at neutral

        # Increase for formal markers
        formal_markers = ["respectfully", "please", "kindly", "regarding", "pursuant"]
        for marker in formal_markers:
            if marker in text.lower():
                score += 1

        # Decrease for casual markers
        casual_markers = ["hey", "cool", "awesome", "gonna", "wanna"]
        for marker in casual_markers:
            if marker in text.lower():
                score -= 1

        # Emojis decrease formality
        emoji_count = sum(1 for c in text if ord(c) > 0x1F300)
        score -= min(emoji_count, 2)

        return max(1, min(10, score))

    def _summarize_text(self, text: str, max_chars: int) -> str:
        """Create summary by truncating at sentence boundary."""
        if len(text) <= max_chars:
            return text

        # Try to truncate at sentence boundary
        truncated = text[:max_chars]
        last_period = truncated.rfind(".")
        if last_period > max_chars * 0.6:
            return truncated[:last_period + 1]

        return truncated.rsplit(" ", 1)[0] + "..."

    def invalidate(self, profile_id: str) -> None:
        """
        Invalidate cache for a profile.

        Call when profile data has been updated.
        """
        if profile_id in self._cache:
            del self._cache[profile_id]
            logger.info(f"Cache invalidated for {profile_id}")

    def invalidate_all(self) -> None:
        """Invalidate all cached profiles."""
        self._cache.clear()
        logger.info("All caches invalidated")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "profiles_cached": len(self._cache),
            "profiles": {
                pid: {
                    "examples": len(pe.examples),
                    "precedents": len(pe.precedents),
                    "loaded_at": pe.loaded_at.isoformat() if pe.loaded_at else None,
                }
                for pid, pe in self._cache.items()
            },
        }


# Singleton instance
_default_cache: Optional[EmbeddingCache] = None


def get_embedding_cache() -> EmbeddingCache:
    """Get singleton EmbeddingCache instance."""
    global _default_cache
    if _default_cache is None:
        _default_cache = EmbeddingCache()
    return _default_cache


def create_embedding_cache(
    embedding_service=None,
    profiles_dir: Optional[Path] = None,
) -> EmbeddingCache:
    """Create a new EmbeddingCache instance."""
    return EmbeddingCache(
        embedding_service=embedding_service,
        profiles_dir=profiles_dir,
    )
