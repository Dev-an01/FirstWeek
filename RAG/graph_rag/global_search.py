"""
GraphRAG Global Search Provider

Implements global (thematic) search using community summaries.

Complements existing graph-enhanced vector search:
- Local search (existing): Entity -> Graph -> Vector -> Results
- Global search (new): Query -> Communities -> Summaries -> Answer

Best for broad queries like:
- "What are our main strategic risks?"
- "Summarize our relationship with key partners"
- "What themes emerge from recent decisions?"
"""

import logging
import time
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from .community_detector import CommunityDetector, Community

# LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    LANGSMITH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class GlobalSearchResult:
    """Result from global search."""
    success: bool
    strategy: str  # 'global', 'hybrid', 'fallback'
    communities_used: int
    context: str
    summaries: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "strategy": self.strategy,
            "communities_used": self.communities_used,
            "context": self.context,
            "summaries": self.summaries,
            "metadata": self.metadata,
            "error": self.error
        }


class GraphRAGProvider:
    """
    GraphRAG implementation for global (thematic) queries.

    Complements existing graph-enhanced vector search:
    - Local search (existing): Entity -> Graph -> Vector -> Results
    - Global search (new): Query -> Communities -> Summaries -> Answer

    Usage:
        provider = GraphRAGProvider(neo4j_driver, embedding_model, llm_client)

        # For broad thematic queries
        result = await provider.global_search(
            query="What are our main strategic initiatives?",
            top_k=5
        )

        # For queries needing both specific and broad context
        result = await provider.hybrid_search(
            query="How does Yuki's approach align with company strategy?",
            entities=["Yuki Nakamura"],
            local_results=[...]
        )
    """

    def __init__(
        self,
        neo4j_driver,
        embedding_model=None,
        llm_client=None,
        cache_ttl_seconds: int = 3600
    ):
        """
        Initialize GraphRAG provider.

        Args:
            neo4j_driver: Neo4j driver instance
            embedding_model: Embedding model for semantic matching
            llm_client: LLM client for summary generation
            cache_ttl_seconds: Cache TTL for community data
        """
        self.driver = neo4j_driver
        self.embedding_model = embedding_model
        self.llm_client = llm_client

        # Initialize community detector
        self.community_detector = CommunityDetector(
            neo4j_driver=neo4j_driver,
            embedding_model=embedding_model,
            llm_client=llm_client,
            cache_ttl_seconds=cache_ttl_seconds
        )

        # Query embedding cache
        self._query_embedding_cache: Dict[str, List[float]] = {}

        logger.info("GraphRAGProvider initialized")

    @traceable(name="graphrag_global_search")
    async def global_search(
        self,
        query: str,
        top_k: int = 5,
        min_relevance_score: float = 0.3
    ) -> GlobalSearchResult:
        """
        Global search using community summaries.

        Best for broad queries like:
        - "What are our main strategic risks?"
        - "Summarize our relationship with key partners"
        - "What themes emerge from recent decisions?"

        Args:
            query: User query
            top_k: Maximum communities to include
            min_relevance_score: Minimum relevance score (0-1)

        Returns:
            GlobalSearchResult with context and summaries
        """
        start_time = time.time()
        logger.info(f"Starting global search: query='{query[:50]}...', top_k={top_k}")

        try:
            # 1. Find relevant communities
            communities = await self._find_relevant_communities(
                query=query,
                top_k=top_k,
                min_score=min_relevance_score
            )

            if not communities:
                logger.info("No relevant communities found for global search")
                return GlobalSearchResult(
                    success=False,
                    strategy="global",
                    communities_used=0,
                    context="",
                    error="No relevant communities found for this query"
                )

            # 2. Get community summaries
            summaries = []
            for community, score in communities:
                summary = await self.community_detector.generate_community_summary(community)
                summaries.append({
                    "community_id": community.id,
                    "name": community.name,
                    "summary": summary,
                    "relevance_score": score,
                    "member_count": community.member_count,
                    "central_entities": community.central_entities,
                    "entity_types": community.entity_types
                })

            # 3. Build global context
            context = self._build_global_context(summaries)

            latency_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Global search complete: {len(summaries)} communities, "
                f"{latency_ms:.0f}ms"
            )

            return GlobalSearchResult(
                success=True,
                strategy="global",
                communities_used=len(summaries),
                context=context,
                summaries=summaries,
                metadata={
                    "latency_ms": latency_ms,
                    "query_length": len(query),
                    "min_relevance_score": min_relevance_score
                }
            )

        except Exception as e:
            logger.error(f"Global search failed: {e}", exc_info=True)
            return GlobalSearchResult(
                success=False,
                strategy="global",
                communities_used=0,
                context="",
                error=str(e)
            )

    @traceable(name="graphrag_hybrid_search")
    async def hybrid_search(
        self,
        query: str,
        entities: List[str],
        local_results: List[Dict],
        global_top_k: int = 3
    ) -> GlobalSearchResult:
        """
        Combine local (entity-based) and global (community-based) search.

        Used for complex queries that need both specific details
        and broader context.

        Args:
            query: User query
            entities: Entities extracted from query
            local_results: Results from local entity-based search
            global_top_k: Max communities for global context

        Returns:
            GlobalSearchResult with combined context
        """
        start_time = time.time()
        logger.info(
            f"Starting hybrid search: query='{query[:50]}...', "
            f"entities={len(entities)}, local_results={len(local_results)}"
        )

        try:
            # Get global context
            global_result = await self.global_search(
                query=query,
                top_k=global_top_k,
                min_relevance_score=0.25
            )

            # Format local results
            local_context = self._format_local_results(local_results)

            # Combine contexts
            combined_context = f"""
=== Specific Context (Entity-Based) ===
{local_context if local_context else "No specific entity context available."}

=== Broader Context (Thematic) ===
{global_result.context if global_result.context else "No thematic context available."}
""".strip()

            latency_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Hybrid search complete: local={len(local_results)}, "
                f"global={global_result.communities_used}, {latency_ms:.0f}ms"
            )

            return GlobalSearchResult(
                success=True,
                strategy="hybrid",
                communities_used=global_result.communities_used,
                context=combined_context,
                summaries=global_result.summaries,
                metadata={
                    "latency_ms": latency_ms,
                    "local_results_count": len(local_results),
                    "entities_count": len(entities),
                    "global_communities": global_result.communities_used
                }
            )

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}", exc_info=True)
            # Fallback to local-only context
            local_context = self._format_local_results(local_results)
            return GlobalSearchResult(
                success=True,
                strategy="fallback",
                communities_used=0,
                context=local_context,
                error=f"Global search failed, using local only: {e}"
            )

    async def _find_relevant_communities(
        self,
        query: str,
        top_k: int,
        min_score: float
    ) -> List[Tuple[Community, float]]:
        """
        Find communities relevant to query.

        Uses two strategies:
        1. Semantic similarity (if embeddings available)
        2. Keyword matching (fallback)
        """
        # Ensure communities are detected
        communities = self.community_detector.get_all_communities()
        if not communities:
            logger.warning("No communities detected")
            return []

        # Try semantic matching first
        if self.embedding_model:
            try:
                return await self._find_communities_semantic(query, communities, top_k, min_score)
            except Exception as e:
                logger.warning(f"Semantic community matching failed: {e}")

        # Fallback to keyword matching
        return self._find_communities_keyword(query, communities, top_k, min_score)

    async def _find_communities_semantic(
        self,
        query: str,
        communities: List[Community],
        top_k: int,
        min_score: float
    ) -> List[Tuple[Community, float]]:
        """Find communities using semantic similarity."""
        # Get query embedding
        if query not in self._query_embedding_cache:
            query_embedding = self.embedding_model.encode(query, show_progress_bar=False)
            self._query_embedding_cache[query] = query_embedding.tolist()
        else:
            query_embedding = np.array(self._query_embedding_cache[query])

        # Ensure community embeddings exist
        if not any(c.embedding for c in communities):
            self.community_detector.compute_community_embeddings()
            communities = self.community_detector.get_all_communities()

        # Calculate similarities
        results = []
        for community in communities:
            if not community.embedding:
                continue

            comm_embedding = np.array(community.embedding)

            # Cosine similarity
            dot_product = np.dot(query_embedding, comm_embedding)
            norm_a = np.linalg.norm(query_embedding)
            norm_b = np.linalg.norm(comm_embedding)

            if norm_a > 0 and norm_b > 0:
                similarity = dot_product / (norm_a * norm_b)
                if similarity >= min_score:
                    results.append((community, float(similarity)))

        # Sort by similarity and take top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _find_communities_keyword(
        self,
        query: str,
        communities: List[Community],
        top_k: int,
        min_score: float
    ) -> List[Tuple[Community, float]]:
        """Find communities using keyword matching."""
        # Extract keywords from query
        query_words = set(query.lower().split())

        # Remove stop words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how',
                      'when', 'where', 'who', 'which', 'do', 'does', 'did', 'have',
                      'has', 'had', 'be', 'been', 'being', 'to', 'of', 'and', 'or',
                      'in', 'on', 'at', 'for', 'with', 'about', 'by', 'from', 'our',
                      'my', 'your', 'their', 'this', 'that', 'these', 'those'}
        query_keywords = query_words - stop_words

        # Use community detector's keyword matching
        results = self.community_detector.find_communities_by_keyword(
            keywords=list(query_keywords),
            min_match_score=min_score
        )

        return results[:top_k]

    def _build_global_context(self, summaries: List[Dict]) -> str:
        """Build context string from community summaries."""
        if not summaries:
            return ""

        context_parts = []
        for s in summaries:
            relevance_pct = int(s['relevance_score'] * 100)
            context_parts.append(
                f"**{s['name']}** (relevance: {relevance_pct}%)\n"
                f"{s['summary']}\n"
                f"Key entities: {', '.join(s['central_entities'][:3])}"
            )

        return "\n\n".join(context_parts)

    def _format_local_results(self, results: List[Dict]) -> str:
        """Format local search results as context."""
        if not results:
            return ""

        context_parts = []
        for i, result in enumerate(results[:5], 1):
            title = result.get('title', result.get('name', f'Result {i}'))
            content = result.get('content', result.get('text', ''))
            score = result.get('score', result.get('similarity', 0))

            # Truncate content if too long
            if len(content) > 500:
                content = content[:497] + "..."

            context_parts.append(
                f"[{i}] {title} (score: {score:.2f})\n{content}"
            )

        return "\n\n".join(context_parts)

    def should_use_global_search(
        self,
        query: str,
        entities: List[str],
        threshold_entities: int = 1
    ) -> bool:
        """
        Determine if global search should be used for a query.

        Global search is recommended when:
        - Few or no entities are found
        - Query contains broad/thematic keywords
        - Query asks about trends, patterns, or summaries

        Args:
            query: User query
            entities: Entities extracted from query
            threshold_entities: Max entities to trigger global search

        Returns:
            True if global search recommended
        """
        # Check entity count
        if len(entities) <= threshold_entities:
            logger.info(f"Few entities ({len(entities)}) - global search recommended")
            return True

        # Check for broad/thematic keywords
        broad_keywords = {
            'summary', 'summarize', 'overview', 'trends', 'patterns',
            'themes', 'overall', 'general', 'broad', 'strategic',
            'main', 'key', 'important', 'significant', 'major',
            'across', 'throughout', 'organization', 'company-wide',
            'all', 'everything', 'landscape', 'picture'
        }

        query_lower = query.lower()
        if any(keyword in query_lower for keyword in broad_keywords):
            logger.info("Broad keywords detected - global search recommended")
            return True

        return False

    def invalidate_cache(self):
        """Invalidate all caches."""
        self._query_embedding_cache.clear()
        self.community_detector._communities.clear()
        self.community_detector._community_embeddings.clear()
        self.community_detector._last_detection_time = 0
        logger.info("GraphRAG caches invalidated")
