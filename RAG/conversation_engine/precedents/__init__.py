"""
Precedent Selection Module

Stage 4 of the Conversation Engine pipeline.
Selects relevant decision cases for decision-type queries.
"""

# Models
from .models import (
    SelectedPrecedent,
    PrecedentCategory,
    PrecedentEmbedding,
    PRECEDENT_CATEGORIES,
)

# Selector
from .selector import (
    PrecedentSelector,
    get_precedent_selector,
    create_precedent_selector,
)

__all__ = [
    # Models
    "SelectedPrecedent",
    "PrecedentCategory",
    "PrecedentEmbedding",
    "PRECEDENT_CATEGORIES",
    # Selector
    "PrecedentSelector",
    "get_precedent_selector",
    "create_precedent_selector",
]
