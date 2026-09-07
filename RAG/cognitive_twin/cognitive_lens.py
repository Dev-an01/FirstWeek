"""
Cognitive Lens - Layer 1 of the Cognitive Twin system.

Makes executives SEE differently by reranking retrieved documents based on
their domain affinity. A CFO sees financial documents first, a CTO sees
technical documents first.

Key principle: Different executives notice different things in the same
information set, based on their expertise and domain focus.

Uses embedding-based similarity (not keywords) for robust matching.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np

from .config import is_layer_enabled, get_layer_config
from .profile_loader import get_cognitive_profile_loader, DomainAffinity

logger = logging.getLogger(__name__)


# Domain descriptions for embedding-based matching
# These are expanded descriptions that capture the semantic meaning of each domain
DOMAIN_DESCRIPTIONS = {
    "finance": """
        Financial analysis, budgeting, revenue, cost management, ROI calculations,
        cash flow, burn rate, unit economics, CAC, LTV, profitability, margins,
        financial modeling, forecasting, investment decisions, risk assessment,
        payback period, NPV, IRR, capital allocation, expense management.
    """,
    "technology": """
        Technical architecture, software engineering, system design, scalability,
        security, API design, infrastructure, cloud computing, DevOps, CI/CD,
        performance optimization, technical debt, code quality, data engineering,
        machine learning systems, microservices, databases, distributed systems.
    """,
    "marketing": """
        Customer acquisition, brand strategy, marketing campaigns, conversion rates,
        customer journey, brand perception, market positioning, content strategy,
        digital marketing, funnel optimization, engagement metrics, customer insights,
        market research, competitive analysis, product marketing, demand generation.
    """,
    "strategy": """
        Strategic planning, business development, market expansion, competitive
        positioning, organizational alignment, stakeholder management, vision setting,
        mission alignment, growth strategy, partnership development, M&A evaluation,
        long-term planning, resource allocation, strategic priorities, governance.
    """,
    "operations": """
        Process optimization, operational efficiency, supply chain management,
        logistics, inventory management, quality assurance, vendor management,
        capacity planning, workflow optimization, standard operating procedures,
        compliance, risk management, service delivery, customer support operations.
    """,
    "hr": """
        Talent acquisition, employee engagement, performance management, organizational
        culture, team development, compensation and benefits, workforce planning,
        diversity and inclusion, training and development, succession planning,
        employee relations, HR compliance, organizational design, retention strategies.
    """,
}


@dataclass
class CognitiveLensResult:
    """Result of applying cognitive lens to retrieval results."""
    original_results: List[Dict[str, Any]]
    reranked_results: List[Dict[str, Any]]
    domain_used: str
    affinity_weight: float
    documents_boosted: int
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict for LangGraph state."""
        return {
            "original_results": self.original_results,
            "reranked_results": self.reranked_results,
            "domain_used": self.domain_used,
            "affinity_weight": float(self.affinity_weight),
            "documents_boosted": self.documents_boosted,
            "reasoning": self.reasoning,
        }


class CognitiveLens:
    """
    Reranks retrieved documents based on executive's domain affinity.

    Uses embedding similarity (not keywords) for robust semantic matching.
    Documents that align with the executive's domain expertise get a boost
    in ranking, ensuring they see the most relevant information first.

    Thread-safe: Uses cached domain embeddings.
    """

    def __init__(self, embedding_client=None):
        """
        Initialize the CognitiveLens.

        Args:
            embedding_client: Optional EmbeddingServiceClient for generating embeddings.
                            If None, uses the global singleton.
        """
        self._profile_loader = get_cognitive_profile_loader()
        self._config = get_layer_config("foundation.cognitive_lens")

        # Lazy load embedding client to avoid circular imports
        self._embedding_client = embedding_client
        self._domain_embeddings: Dict[str, np.ndarray] = {}

        logger.info("CognitiveLens initialized")

    def _get_embedding_client(self):
        """Get or create embedding client (lazy loading)."""
        if self._embedding_client is None:
            from vector_search.embedding_client import get_embedding_client
            self._embedding_client = get_embedding_client()
        return self._embedding_client

    def _get_domain_embedding(self, domain: str) -> Optional[np.ndarray]:
        """
        Get or create embedding for a domain.

        Uses cached embeddings for performance.
        """
        if domain in self._domain_embeddings:
            return self._domain_embeddings[domain]

        description = DOMAIN_DESCRIPTIONS.get(domain)
        if not description:
            logger.warning(f"No description for domain: {domain}")
            return None

        try:
            client = self._get_embedding_client()
            embedding = client.generate_embedding(description.strip())
            self._domain_embeddings[domain] = embedding
            logger.debug(f"Generated embedding for domain: {domain}")
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate domain embedding for {domain}: {e}")
            return None

    def apply(
        self,
        results: List[Dict[str, Any]],
        profile_id: str,
    ) -> CognitiveLensResult:
        """
        Apply cognitive lens to retrieval results.

        Reranks documents based on the executive's domain affinity.

        Args:
            results: List of retrieval results (dicts with 'content', 'score', etc.)
            profile_id: Executive profile ID

        Returns:
            CognitiveLensResult with reranked documents
        """
        # Check if lens is enabled
        if not is_layer_enabled("foundation.cognitive_lens"):
            return CognitiveLensResult(
                original_results=results,
                reranked_results=results,
                domain_used="none",
                affinity_weight=0.0,
                documents_boosted=0,
                reasoning="Cognitive lens disabled",
            )

        if not results:
            return CognitiveLensResult(
                original_results=[],
                reranked_results=[],
                domain_used="none",
                affinity_weight=0.0,
                documents_boosted=0,
                reasoning="No results to rerank",
            )

        # Get executive's domain affinity
        domain_affinity = self._profile_loader.get_domain_affinity(profile_id)
        if not domain_affinity or not domain_affinity.primary_domain:
            return CognitiveLensResult(
                original_results=results,
                reranked_results=results,
                domain_used="unknown",
                affinity_weight=0.0,
                documents_boosted=0,
                reasoning=f"No domain affinity for {profile_id}",
            )

        domain = domain_affinity.primary_domain
        affinity_weight = self._config.get("affinity_weight", 0.4)
        min_similarity = self._config.get("min_similarity", 0.3)

        # Get domain embedding
        domain_embedding = self._get_domain_embedding(domain)
        if domain_embedding is None:
            return CognitiveLensResult(
                original_results=results,
                reranked_results=results,
                domain_used=domain,
                affinity_weight=affinity_weight,
                documents_boosted=0,
                reasoning=f"Failed to get domain embedding for {domain}",
            )

        # Apply domain affinity boost
        reranked = []
        boosted_count = 0

        for result in results:
            result_copy = result.copy()
            original_score = result_copy.get("score", 0.5)

            # Calculate domain similarity for this document
            domain_similarity = self._calculate_domain_similarity(
                result_copy, domain_embedding
            )

            # Apply boost if similarity is above threshold
            if domain_similarity >= min_similarity:
                boost = domain_similarity * affinity_weight
                new_score = min(1.0, original_score * (1 + boost))
                result_copy["score"] = new_score
                result_copy["_cognitive_lens"] = {
                    "domain": domain,
                    "original_score": original_score,
                    "domain_similarity": domain_similarity,
                    "boost_applied": boost,
                }
                boosted_count += 1
            else:
                result_copy["_cognitive_lens"] = {
                    "domain": domain,
                    "original_score": original_score,
                    "domain_similarity": domain_similarity,
                    "boost_applied": 0.0,
                }

            reranked.append(result_copy)

        # Sort by new scores
        reranked.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(
            f"CognitiveLens applied for {profile_id}: "
            f"domain={domain}, boosted={boosted_count}/{len(results)}"
        )

        return CognitiveLensResult(
            original_results=results,
            reranked_results=reranked,
            domain_used=domain,
            affinity_weight=affinity_weight,
            documents_boosted=boosted_count,
            reasoning=f"Boosted {boosted_count} documents with {domain} affinity",
        )

    def _calculate_domain_similarity(
        self,
        result: Dict[str, Any],
        domain_embedding: np.ndarray,
    ) -> float:
        """
        Calculate how similar a document is to the executive's domain.

        Uses cosine similarity between document content and domain embedding.
        """
        content = result.get("content", "") or result.get("text_content", "")
        if not content:
            return 0.0

        try:
            # Generate embedding for document content (truncate for efficiency)
            content_truncated = content[:2000]  # First 2000 chars
            client = self._get_embedding_client()
            content_embedding = client.generate_embedding(content_truncated)

            # Calculate cosine similarity
            similarity = self._cosine_similarity(content_embedding, domain_embedding)
            return max(0.0, similarity)  # Clamp to non-negative

        except Exception as e:
            logger.warning(f"Failed to calculate domain similarity: {e}")
            return 0.0

    def _cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    def apply_keyword_fallback(
        self,
        results: List[Dict[str, Any]],
        profile_id: str,
    ) -> CognitiveLensResult:
        """
        Fallback method using keyword matching if embeddings fail.

        Uses domain_affinity.boost_keywords from profile for matching.
        """
        # Get executive's domain affinity
        domain_affinity = self._profile_loader.get_domain_affinity(profile_id)
        if not domain_affinity:
            return CognitiveLensResult(
                original_results=results,
                reranked_results=results,
                domain_used="unknown",
                affinity_weight=0.0,
                documents_boosted=0,
                reasoning=f"No domain affinity for {profile_id}",
            )

        domain = domain_affinity.primary_domain
        keywords = set(kw.lower() for kw in domain_affinity.boost_keywords)
        affinity_weight = self._config.get("affinity_weight", 0.4)

        if not keywords:
            # Use default keywords for domain
            keywords = self._get_default_keywords(domain)

        reranked = []
        boosted_count = 0

        for result in results:
            result_copy = result.copy()
            original_score = result_copy.get("score", 0.5)

            content = (result_copy.get("content", "") or "").lower()
            matches = sum(1 for kw in keywords if kw in content)
            match_ratio = min(matches / max(len(keywords) // 3, 1), 1.0)

            if match_ratio > 0:
                boost = match_ratio * affinity_weight
                new_score = min(1.0, original_score * (1 + boost))
                result_copy["score"] = new_score
                boosted_count += 1

            reranked.append(result_copy)

        reranked.sort(key=lambda x: x.get("score", 0), reverse=True)

        return CognitiveLensResult(
            original_results=results,
            reranked_results=reranked,
            domain_used=domain,
            affinity_weight=affinity_weight,
            documents_boosted=boosted_count,
            reasoning=f"Keyword fallback: boosted {boosted_count} documents",
        )

    def _get_default_keywords(self, domain: str) -> set:
        """Get default keywords for a domain."""
        default_keywords = {
            "finance": {"revenue", "cost", "roi", "npv", "payback", "margin",
                        "budget", "cac", "ltv", "burn", "financial", "profit"},
            "technology": {"technical", "architecture", "scalability", "security",
                           "api", "performance", "tech", "system", "code", "data"},
            "marketing": {"customer", "brand", "funnel", "conversion", "campaign",
                          "engagement", "market", "perception", "growth"},
            "strategy": {"strategy", "stakeholder", "mission", "alignment",
                         "growth", "vision", "partnership", "competitive"},
            "operations": {"process", "efficiency", "supply", "logistics",
                           "quality", "compliance", "workflow", "operations"},
            "hr": {"talent", "employee", "culture", "team", "performance",
                   "training", "development", "retention", "engagement"},
        }
        return default_keywords.get(domain, set())


# Singleton instance
_lens: Optional[CognitiveLens] = None


def get_cognitive_lens() -> CognitiveLens:
    """Get the singleton CognitiveLens instance."""
    global _lens
    if _lens is None:
        _lens = CognitiveLens()
    return _lens
