"""
GraphRAG Module - Global Search for Broad/Thematic Queries

Complements existing graph-enhanced vector search:
- Local search (existing): Entity -> Graph -> Vector -> Results
- Global search (new): Query -> Communities -> Summaries -> Answer

This module provides community-based retrieval for queries that lack
clear entity references but need broader thematic context.
"""

from .global_search import GraphRAGProvider
from .community_detector import CommunityDetector

__all__ = ["GraphRAGProvider", "CommunityDetector"]
