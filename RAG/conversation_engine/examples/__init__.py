"""
Semantic Example Selection Module

Stage 3 of the Conversation Engine pipeline.
Selects best-matching communication examples using semantic similarity.
"""

# Models
from .models import SelectedExample, ExampleEmbedding

# Embedding infrastructure
from .embedding_service import (
    EmbeddingService,
    get_embedding_service,
    create_embedding_service,
)
from .embedding_cache import (
    EmbeddingCache,
    ProfileEmbeddings,
    get_embedding_cache,
    create_embedding_cache,
)

# Selector
from .selector import (
    SemanticExampleSelector,
    get_example_selector,
    create_example_selector,
)

__all__ = [
    # Models
    "SelectedExample",
    "ExampleEmbedding",
    # Embedding infrastructure
    "EmbeddingService",
    "get_embedding_service",
    "create_embedding_service",
    "EmbeddingCache",
    "ProfileEmbeddings",
    "get_embedding_cache",
    "create_embedding_cache",
    # Selector
    "SemanticExampleSelector",
    "get_example_selector",
    "create_example_selector",
]
