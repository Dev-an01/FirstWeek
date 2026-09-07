"""
Voiceprint Embedding Cache - Pre-computed embeddings for semantic attention.

Embeds voiceprint category examples at startup for zero-cost semantic similarity.
Target: ~60 embeddings (15 categories × 4 executives) = ~23KB memory.

Enables semantic attention mechanism for voiceprint matching.
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Categories to embed (must match voiceprint JSON structure)
EMBEDDABLE_CATEGORIES = [
    # Content categories
    "transparency_phrases",
    "challenge_invitation",
    "risk_language",
    "numbers_cadence",
    "decision_cadence",
    "accountability_phrases",
    # Style categories
    "signature_opener",
    "sign_off",
    "disagreement",
    "context_signatures",
    # Emotional categories
    "emotional_expressions",
    "mentorship_phrases",
    "deference_phrases",
    "energy_words",
    "humor_markers",
    # Lexicon (special handling - top level)
    "lexicon",
]


class VoiceprintEmbeddingCache:
    """
    Cache of pre-computed voiceprint category embeddings.

    Embeddings are computed at startup and stored in memory.
    Used by SemanticAttention for zero-cost similarity computation.

    Thread-safe: Read-only after warm_cache() completes.
    """

    VOICEPRINT_DIR = Path(__file__).parent.parent.parent / "test_data" / "voiceprints"

    def __init__(self):
        """Initialize empty cache (call warm_cache to populate)."""
        self._cache: Dict[str, Dict[str, np.ndarray]] = {}
        self._embedding_service = None
        self._warmed = False
        self._warm_time_ms = 0.0
        logger.debug("VoiceprintEmbeddingCache initialized (call warm_cache to populate)")

    def _ensure_embedding_service(self):
        """Lazy load embedding service."""
        if self._embedding_service is None:
            from ..examples.embedding_service import get_embedding_service
            self._embedding_service = get_embedding_service()

    def warm_cache(
        self,
        voiceprint_dir: Optional[Path] = None,
        executive_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Pre-compute embeddings for all voiceprint categories.

        Should be called once at application startup.

        Args:
            voiceprint_dir: Path to voiceprint JSON files
            executive_ids: Optional list of specific executives to load

        Returns:
            Stats dict with timing and counts
        """
        start = time.time()
        self._ensure_embedding_service()

        vp_dir = voiceprint_dir or self.VOICEPRINT_DIR

        # Find all voiceprint files
        vp_files = list(vp_dir.glob("*_voiceprint.json"))

        stats = {
            "executives_loaded": 0,
            "categories_embedded": 0,
            "total_embeddings": 0,
            "errors": [],
        }

        for vp_file in vp_files:
            try:
                with open(vp_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                exec_id = data.get("executive_id")
                if not exec_id:
                    continue

                if executive_ids and exec_id not in executive_ids:
                    continue

                # Embed categories for this executive
                self._cache[exec_id] = {}
                voiceprint = data.get("voiceprint", {})

                for category in EMBEDDABLE_CATEGORIES:
                    embedding = self._embed_category(voiceprint, category, data)
                    if embedding is not None:
                        self._cache[exec_id][category] = embedding
                        stats["total_embeddings"] += 1

                stats["executives_loaded"] += 1
                stats["categories_embedded"] += len(self._cache[exec_id])

                logger.debug(f"Embedded {len(self._cache[exec_id])} categories for {exec_id}")

            except Exception as e:
                stats["errors"].append(f"{vp_file.name}: {str(e)}")
                logger.warning(f"Failed to process {vp_file}: {e}")

        self._warm_time_ms = (time.time() - start) * 1000
        self._warmed = True

        stats["warm_time_ms"] = self._warm_time_ms

        logger.info(
            f"VoiceprintEmbeddingCache warmed: "
            f"{stats['executives_loaded']} executives, "
            f"{stats['total_embeddings']} embeddings in {self._warm_time_ms:.0f}ms"
        )

        return stats

    def _embed_category(
        self,
        voiceprint: Dict[str, Any],
        category: str,
        full_data: Dict[str, Any],
    ) -> Optional[np.ndarray]:
        """
        Embed a single voiceprint category.

        Concatenates examples into a single text for embedding.
        """
        # Special handling for lexicon (top-level, not in voiceprint)
        if category == "lexicon":
            lexicon = full_data.get("lexicon", [])
            if not lexicon:
                return None

            # Handle nested dict structure (e.g., {"business_philosophy": [...], "values_in_action": [...]})
            if isinstance(lexicon, dict):
                phrases = []
                for key, values in lexicon.items():
                    if isinstance(values, list):
                        phrases.extend(values)
                if not phrases:
                    return None
                text = " | ".join(str(p) for p in phrases[:20])  # First 20 phrases
            else:
                # Original list handling
                text = " | ".join(str(p) for p in lexicon[:20])  # First 20 phrases

            return self._embedding_service.embed_text(text)

        # Standard category handling
        cat_data = voiceprint.get(category)
        if not cat_data:
            return None

        # Extract examples from various possible structures
        examples = []
        if isinstance(cat_data, dict):
            # Most categories have "examples" list
            examples = cat_data.get("examples", [])
            # Some have "phrases" instead
            if not examples:
                examples = cat_data.get("phrases", [])
            # Some have "alternatives"
            if not examples:
                examples = cat_data.get("alternatives", [])
            # emotional_expressions has nested structure
            if not examples and category == "emotional_expressions":
                for emotion_type in ["pride", "concern", "encouragement"]:
                    examples.extend(cat_data.get(emotion_type, []))
            # context_signatures is a dict of contexts
            if not examples and category == "context_signatures":
                # Extract signature values
                for key, val in cat_data.items():
                    if isinstance(val, str) and key not in ["with_ps"]:
                        examples.append(val)
                # Also get ps_examples if present
                examples.extend(cat_data.get("ps_examples", []))
        elif isinstance(cat_data, list):
            examples = cat_data

        if not examples:
            return None

        # Concatenate examples for embedding
        text = " | ".join(str(ex) for ex in examples[:10])  # First 10 examples

        return self._embedding_service.embed_text(text)

    def get_category_embeddings(
        self,
        executive_id: str,
    ) -> Optional[Dict[str, np.ndarray]]:
        """
        Get all category embeddings for an executive.

        Returns:
            Dict mapping category name to embedding, or None if not found
        """
        if not self._warmed:
            logger.warning("Cache not warmed - call warm_cache() first")
            return None
        return self._cache.get(executive_id)

    def get_category_embedding(
        self,
        executive_id: str,
        category: str,
    ) -> Optional[np.ndarray]:
        """
        Get embedding for a specific category.

        Returns:
            1024-dim embedding or None if not found (MIGRATED from 384-dim)
        """
        exec_cache = self._cache.get(executive_id)
        if exec_cache is None:
            return None
        return exec_cache.get(category)

    def get_all_category_embeddings_array(
        self,
        executive_id: str,
    ) -> Tuple[List[str], Optional[np.ndarray]]:
        """
        Get category names and embeddings as aligned arrays for vectorized similarity.

        Returns:
            Tuple of (category_names, embeddings_array)
            - category_names: List of category names
            - embeddings_array: np.array of shape (n_categories, 1024)  # MIGRATED from 384
        """
        exec_cache = self._cache.get(executive_id)
        if not exec_cache:
            return [], None

        categories = list(exec_cache.keys())
        embeddings = np.array([exec_cache[cat] for cat in categories])

        return categories, embeddings

    def is_warmed(self) -> bool:
        """Check if cache has been warmed."""
        return self._warmed

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_embeddings = sum(len(cats) for cats in self._cache.values())
        return {
            "warmed": self._warmed,
            "warm_time_ms": self._warm_time_ms,
            "executives": len(self._cache),
            "total_embeddings": total_embeddings,
            "categories_per_executive": {
                exec_id: len(cats) for exec_id, cats in self._cache.items()
            },
        }


# Singleton instance
_default_cache: Optional[VoiceprintEmbeddingCache] = None


def get_voiceprint_embedding_cache() -> VoiceprintEmbeddingCache:
    """Get singleton VoiceprintEmbeddingCache instance."""
    global _default_cache
    if _default_cache is None:
        _default_cache = VoiceprintEmbeddingCache()
    return _default_cache


def create_voiceprint_embedding_cache() -> VoiceprintEmbeddingCache:
    """Create new VoiceprintEmbeddingCache instance."""
    return VoiceprintEmbeddingCache()
