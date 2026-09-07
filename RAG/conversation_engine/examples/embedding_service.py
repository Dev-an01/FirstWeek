"""
Embedding Service for Conversation Engine.

Optimized for semantic similarity with context enrichment.
MIGRATED: From all-MiniLM-L6-v2 (384-dim English-only) to BAAI/bge-m3 (1024-dim multilingual)

This enables the Cognitive Engine to understand Japanese precedents and examples.
"""

import logging
import time
from typing import List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Lazy import to avoid loading model at module import time
_embedding_model = None
_model_name = "BAAI/bge-m3"  # MIGRATED: multilingual model for Japanese + English


def _get_model():
    """Lazy load the embedding model (singleton pattern)."""
    global _embedding_model
    if _embedding_model is None:
        try:
            # Add RAG root to path to find embedding_generation
            import sys
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # ../.. from conversation_engine/examples goes to RAG root
            rag_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
            if rag_root not in sys.path:
                sys.path.insert(0, rag_root)

            from embedding_generation.model_manager import get_shared_embedding_model
            
            logger.info(f"Loading/Retrieving shared embedding model for ConversationEngine: {_model_name}")
            start = time.time()
            
            # Use the shared wrapper and get the underlying SentenceTransformer
            wrapper = get_shared_embedding_model(_model_name)
            _embedding_model = wrapper.model
            
            load_time = (time.time() - start) * 1000
            logger.info(f"Shared model retrieved in {load_time:.0f}ms (dim={_embedding_model.get_sentence_embedding_dimension()})")
            
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    return _embedding_model



class EmbeddingService:
    """
    Embedding service for Conversation Engine.

    Features:
    - Uses BAAI/bge-m3 (1024-dim, multilingual 100+ languages)
    - Singleton model loading
    - Context enrichment for improved matching
    - Batch embedding for cache warming

    Thread-safe: Model is loaded once and shared across instances.

    MIGRATED: From English-only 384-dim to multilingual 1024-dim
    """

    EMBEDDING_DIMENSION = 1024  # Was: 384
    MODEL_NAME = "BAAI/bge-m3"  # Was: all-MiniLM-L6-v2

    def __init__(self):
        """Initialize EmbeddingService (model loaded lazily on first use)."""
        self._model = None
        logger.debug("EmbeddingService initialized (model will load on first use)")

    def _ensure_model(self):
        """Ensure model is loaded."""
        if self._model is None:
            self._model = _get_model()

    def embed_query(
        self,
        query: str,
        theme: Optional[str] = None,
        emotion: Optional[str] = None,
        turn_type: Optional[str] = None,
    ) -> Tuple[np.ndarray, float]:
        """
        Generate embedding for user query with optional context enrichment.

        Context enrichment improves semantic matching by including
        situational signals in the embedding.

        Args:
            query: User's query text
            theme: Query theme (e.g., "budget", "security")
            emotion: User emotion (e.g., "stressed", "positive")
            turn_type: Turn type (e.g., "followup", "new_topic")

        Returns:
            Tuple of (embedding, latency_ms)
            - embedding: numpy array of shape (1024,)  # MIGRATED from 384
            - latency_ms: Time taken for embedding generation
        """
        self._ensure_model()

        start = time.time()

        # Build enriched query if context provided
        enriched_query = query
        if theme or emotion or turn_type:
            context_parts = []
            if theme and theme != "other":
                context_parts.append(f"[{theme}]")
            if emotion and emotion != "neutral":
                context_parts.append(f"[{emotion}]")
            if turn_type and turn_type != "initial":
                context_parts.append(f"[{turn_type}]")

            if context_parts:
                enriched_query = f"{' '.join(context_parts)} {query}"
                logger.debug(f"Enriched query: {enriched_query[:100]}...")

        # Generate embedding
        embedding = self._model.encode(
            enriched_query,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        latency_ms = (time.time() - start) * 1000
        logger.debug(f"Query embedded in {latency_ms:.1f}ms")

        return embedding, latency_ms

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for arbitrary text (no enrichment).

        Used for embedding examples and precedents during cache warming.

        Args:
            text: Text to embed

        Returns:
            Numpy array of shape (1024,)  # MIGRATED from 384
        """
        self._ensure_model()

        embedding = self._model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        return embedding

    def embed_texts_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
    ) -> Tuple[np.ndarray, float]:
        """
        Batch embed multiple texts for cache warming.

        More efficient than individual calls for pre-computing embeddings.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing

        Returns:
            Tuple of (embeddings, latency_ms)
            - embeddings: numpy array of shape (len(texts), 1024)  # MIGRATED from 384
            - latency_ms: Total time taken
        """
        if not texts:
            return np.array([]), 0.0

        self._ensure_model()

        start = time.time()

        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
            batch_size=batch_size,
        )

        latency_ms = (time.time() - start) * 1000
        logger.debug(f"Batch embedded {len(texts)} texts in {latency_ms:.1f}ms")

        return embeddings, latency_ms

    def cosine_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Since embeddings are normalized, this is just the dot product.

        Args:
            embedding1: First embedding (normalized)
            embedding2: Second embedding (normalized)

        Returns:
            Similarity score in range [-1, 1], typically [0, 1] for text
        """
        return float(np.dot(embedding1, embedding2))

    def cosine_similarities(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray,
    ) -> np.ndarray:
        """
        Compute cosine similarities between query and multiple candidates.

        Vectorized for efficiency.

        Args:
            query_embedding: Query embedding of shape (1024,)  # MIGRATED from 384
            candidate_embeddings: Candidate embeddings of shape (n, 1024)

        Returns:
            Similarity scores of shape (n,)
        """
        return np.dot(candidate_embeddings, query_embedding)

    def get_model_info(self) -> dict:
        """Get information about the embedding model."""
        self._ensure_model()
        return {
            "model_name": self.MODEL_NAME,
            "embedding_dimension": self.EMBEDDING_DIMENSION,
            "max_sequence_length": self._model.max_seq_length,
        }


# Singleton instance
_default_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get singleton EmbeddingService instance."""
    global _default_service
    if _default_service is None:
        _default_service = EmbeddingService()
    return _default_service


def create_embedding_service() -> EmbeddingService:
    """Create a new EmbeddingService instance."""
    return EmbeddingService()
