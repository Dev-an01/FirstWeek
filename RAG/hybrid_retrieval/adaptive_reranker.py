"""
Adaptive Reranker
=================

Applies reranking based on result quality assessment according to Solution Manual specification.

Three strategies:
1. Lightweight (40% queries): Normalize + source weights + MMR (~50ms)
2. Medium (35% queries): + Fast cross-encoder on top 10 (~100ms)
3. Full (25% queries): + Full cross-encoder on all results (~200ms)

Quality Assessment (Solution Manual section 5.3):
- HIGH: top score > 0.9, gap > 0.2 → Clear winner
- MEDIUM: top score 0.75-0.9, gap 0.1-0.2 → Reasonable results
- LOW: top score < 0.75, gap < 0.1 → Unclear best result
"""

import logging
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple
import numpy as np

import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from hybrid_retrieval.utils import get_logger
from hybrid_retrieval.config import HYBRID_RETRIEVAL_CONFIG

# WEEK 1, DAY 3: LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    # Fallback: no-op decorator that accepts keyword arguments
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return decorator
    LANGSMITH_AVAILABLE = False

logger = get_logger(__name__)


class AdaptiveReranker:
    """
    Adaptive reranking based on result quality with distribution tracking
    and time target enforcement according to Solution Manual specification
    """
    
    def __init__(self):
        """
        Initialize adaptive reranker with distribution tracking and performance monitoring
        
        Loads cross-encoder at initialization (3s one-time cost)
        to avoid first-query latency spike.
        """
        # Pre-load cross-encoder (eliminates 3s first-query delay)
        # Use model from config
        self.cross_encoder_model = HYBRID_RETRIEVAL_CONFIG.get("cross_encoder", {}).get("model_name", "cross-encoder/ms-marco-MiniLM-L12-v2")
        
        try:
            logger.info("[AdaptiveReranker] Loading cross-encoder model...")
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder(self.cross_encoder_model)
            logger.info("[AdaptiveReranker] ✅ Cross-encoder loaded successfully")
        except Exception as e:
            logger.error(f"[AdaptiveReranker] ❌ Failed to load cross-encoder: {e}")
            self.cross_encoder = None
        
        # Distribution tracking (40% lightweight, 35% medium, 25% full)
        self.strategy_counts = defaultdict(int)
        self.total_queries = 0
        self.recent_strategies = deque(maxlen=100)  # Track last 100 for distribution
        
        # Performance metrics from config
        self.performance_history = defaultdict(list)
        self.time_targets = HYBRID_RETRIEVAL_CONFIG.get("time_targets", {
            "lightweight": 50,   # 50ms target
            "medium": 100,       # 100ms target
            "full": 200          # 200ms target
        })
        
        # Distribution targets from config
        self.distribution_targets = HYBRID_RETRIEVAL_CONFIG.get("distribution_targets", {
            "lightweight": 0.40,  # 40% of queries
            "medium": 0.35,       # 35% of queries
            "full": 0.25          # 25% of queries
        })
        
        # Maximum candidates for full reranking
        self.max_candidates = HYBRID_RETRIEVAL_CONFIG.get("performance_optimization", {}).get("max_candidates", 40)
        
        logger.info("[AdaptiveReranker] Initialized with distribution tracking and time targets")
    
    @traceable(name="adaptive_reranking", tags=["retrieval", "reranking"])
    def rerank(
        self,
        results: List[Dict],
        query: str,
        quality_assessment: Dict,
        config: Dict,
        query_classification: Optional[Dict] = None
    ) -> Dict:
        """
        Apply adaptive reranking with distribution tracking and time target enforcement

        Args:
            results: Fused results with composite scores
            query: Original query text
            quality_assessment: From QueryAnalyzer
            config: Reranking thresholds
            query_classification: Query type classification for smarter strategy selection

        Returns:
            {
                "results": [...],  # Reranked results with final_score
                "strategy": "medium",
                "metadata": {...}
            }
        """
        start_time = time.time()

        if not results:
            return {
                "results": [],
                "strategy": "none",
                "metadata": {"time_ms": 0}
            }

        # Step 1: Assess result quality using Solution Manual criteria
        quality_level = self.assess_result_quality(results)

        # Step 2: Select strategy based on quality AND query type (Priority 2 fix)
        # Use enhanced method that enables cross-encoder for complex queries
        if query_classification:
            initial_strategy = self._select_strategy_from_quality_and_type(
                quality_level,
                query_classification,
                len(results)
            )
        else:
            # Fallback to legacy method if no classification provided
            initial_strategy = self._select_strategy_from_quality(quality_level)

        # Step 3: Adjust strategy based on distribution targets
        strategy = self._enforce_distribution_targets(initial_strategy)
        
        # Step 4: Apply selected strategy with time monitoring
        if strategy == "lightweight":
            reranked = self.apply_lightweight_reranking(results, query)
        elif strategy == "medium":
            reranked = self.apply_medium_reranking(results, query)
        else:  # full
            reranked = self.apply_full_reranking(results, query)
        
        rerank_time = (time.time() - start_time) * 1000
        
        # Step 5: Update distribution tracking
        self._update_distribution_tracking(strategy, rerank_time)
        
        # Step 6: Check if time target was met
        time_target_met = rerank_time <= self.time_targets[strategy]
        
        logger.info(f"[AdaptiveReranker] Applied {strategy} reranking in {rerank_time:.1f}ms "
                   f"(target: {self.time_targets[strategy]}ms, met: {time_target_met})")
        
        return {
            "results": reranked,
            "strategy": strategy,
            "metadata": {
                "time_ms": rerank_time,
                "time_target": self.time_targets[strategy],
                "time_target_met": time_target_met,
                "results_count": len(reranked),
                "quality_assessment": quality_level,
                "distribution_metrics": self._get_distribution_metrics()
            }
        }
    
    def assess_result_quality(self, results: List[Dict]) -> str:
        """
        Assess result quality using fast heuristics according to Solution Manual section 5.3
        
        Args:
            results: List of results with composite scores
        
        Returns:
            Quality level: "HIGH", "MEDIUM", or "LOW"
        """
        if len(results) < 2:
            return "HIGH"  # Single result is automatically high quality
        
        # Get scores
        scores = [r.get("composite_score", 0) for r in results]
        top_score = scores[0]
        fifth_score = scores[4] if len(scores) > 4 else scores[-1]
        gap = top_score - fifth_score
        score_range = max(scores) - min(scores)
        
        # Thresholds tuned to trigger full reranking when results are unclear
        # HIGH: top score > 0.85, gap > 0.25 → Clear winner
        if top_score > 0.85 and gap > 0.25:
            return "HIGH"

        # MEDIUM: top score 0.70-0.85, gap 0.15-0.25 → Reasonable results
        elif 0.70 <= top_score <= 0.85 and 0.15 <= gap <= 0.25:
            return "MEDIUM"

        # LOW: top score < 0.70, gap < 0.15 → Unclear best result (trigger full reranking)
        else:
            return "LOW"
    
    def _select_strategy_from_quality(self, quality_level: str) -> str:
        """
        Select reranking strategy based on quality assessment (LEGACY)

        Args:
            quality_level: "HIGH", "MEDIUM", or "LOW"

        Returns:
            Strategy: "lightweight", "medium", or "full"
        """
        if quality_level == "HIGH":
            return "lightweight"
        elif quality_level == "MEDIUM":
            return "medium"
        else:  # LOW
            return "full"

    def _select_strategy_from_quality_and_type(
        self,
        quality_level: str,
        query_classification: Optional[Dict],
        candidate_count: int
    ) -> str:
        """
        Select reranking strategy based on BOTH quality assessment AND query type

        NEW (Day 5): Two-Stage Reranking Decision Logic

        Decision tree from spec:
        1. Always skip stage 2 (full reranking) on fast path → Use lightweight
        2. Always skip if too few candidates (<15) → Use lightweight
        3. Always use stage 2 (medium/full) for complex query types (decision, comparison, procedural)
        4. Use stage 2 if many candidates (>30) regardless of type
        5. Skip stage 2 for simple factual lookups with few candidates

        Args:
            quality_level: "HIGH", "MEDIUM", or "LOW" from quality assessment
            query_classification: {
                "type": "factual_lookup"|"relationship"|"decision"|"procedural"|"comparison"|"conversational_context",
                "confidence": float
            }
            candidate_count: Number of candidates to rerank

        Returns:
            Strategy: "lightweight", "medium", or "full"
        """
        # Rule 1: Too few candidates → lightweight (no benefit from cross-encoder)
        if candidate_count < 15:
            logger.debug(
                f"[AdaptiveReranker] Few candidates ({candidate_count}) → lightweight "
                "(no benefit from cross-encoder)"
            )
            return "lightweight"

        # Extract query type if available
        if query_classification:
            query_type = query_classification.get("type", "unknown")
            confidence = query_classification.get("confidence", 0.5)
        else:
            query_type = "unknown"
            confidence = 0.5

        # Rule 2: Complex query types → ALWAYS use cross-encoder (medium or full)
        complex_types = ["decision", "comparison", "procedural"]
        if query_type in complex_types:
            # Use full reranking for low quality complex queries
            if quality_level == "LOW":
                logger.info(
                    f"[AdaptiveReranker] Complex query type '{query_type}' + LOW quality → full reranking "
                    f"(expected +17-20% precision)"
                )
                return "full"
            else:
                logger.info(
                    f"[AdaptiveReranker] Complex query type '{query_type}' → medium reranking "
                    f"(expected +13-17% precision)"
                )
                return "medium"

        # Rule 3: Factual lookup with good quality → lightweight (already 89% precision)
        if query_type == "factual_lookup":
            if quality_level == "HIGH":
                logger.debug(
                    f"[AdaptiveReranker] Factual query + HIGH quality → lightweight "
                    f"(already 89% precision, only +2% from cross-encoder)"
                )
                return "lightweight"
            elif quality_level == "MEDIUM":
                logger.debug(
                    f"[AdaptiveReranker] Factual query + MEDIUM quality → medium reranking "
                    f"(modest +5% improvement expected)"
                )
                return "medium"
            else:  # LOW
                logger.info(
                    f"[AdaptiveReranker] Factual query + LOW quality → full reranking "
                    f"(precision boost needed)"
                )
                return "full"

        # Rule 4: Relationship queries → use cross-encoder if >20 candidates
        if query_type == "relationship":
            if candidate_count >= 20:
                if quality_level == "LOW":
                    logger.info(
                        f"[AdaptiveReranker] Relationship query + many candidates ({candidate_count}) + LOW quality → full "
                        f"(expected +15% precision)"
                    )
                    return "full"
                else:
                    logger.info(
                        f"[AdaptiveReranker] Relationship query + many candidates ({candidate_count}) → medium "
                        f"(expected +10-15% precision)"
                    )
                    return "medium"
            else:
                logger.debug(
                    f"[AdaptiveReranker] Relationship query + few candidates ({candidate_count}) → lightweight"
                )
                return "lightweight"

        # Rule 5: Many candidates (>30) → use cross-encoder regardless of type
        if candidate_count >= 30:
            if quality_level == "LOW":
                logger.info(
                    f"[AdaptiveReranker] Many candidates ({candidate_count}) + LOW quality → full reranking"
                )
                return "full"
            else:
                logger.info(
                    f"[AdaptiveReranker] Many candidates ({candidate_count}) → medium reranking"
                )
                return "medium"

        # Rule 6: Conversational context → use cross-encoder if quality is not high
        if query_type == "conversational_context" and quality_level != "HIGH":
            logger.info(
                f"[AdaptiveReranker] Conversational query + {quality_level} quality → medium reranking"
            )
            return "medium"

        # Default: Fall back to quality-based selection
        logger.debug(
            f"[AdaptiveReranker] Fallback to quality-based selection "
            f"(type={query_type}, quality={quality_level})"
        )
        return self._select_strategy_from_quality(quality_level)
    
    def _enforce_distribution_targets(self, initial_strategy: str) -> str:
        """
        Adjust strategy to maintain 40/35/25 distribution targets
        
        Args:
            initial_strategy: Strategy selected based on quality
        
        Returns:
            Final strategy after distribution adjustment
        """
        if self.total_queries < 10:  # Don't enforce until we have enough data
            return initial_strategy
        
        # Calculate current distribution
        current_dist = self._get_current_distribution()
        
        # Target distribution from config
        target_dist = self.distribution_targets
        
        # Check if we need to adjust
        for strategy, target_pct in target_dist.items():
            current_pct = current_dist.get(strategy, 0)
            deviation = current_pct - target_pct
            
            # If we're overusing a strategy by more than 10%, consider alternatives
            if deviation > 0.10 and initial_strategy == strategy:
                # Find alternative strategy that's underused
                for alt_strategy, alt_target in target_dist.items():
                    alt_current = current_dist.get(alt_strategy, 0)
                    if alt_current < alt_target - 0.05:  # Underused by at least 5%
                        logger.debug(f"[AdaptiveReranker] Adjusting {initial_strategy} -> {alt_strategy} "
                                   f"for distribution compliance (current: {current_pct:.2f}, target: {target_pct:.2f})")
                        return alt_strategy
        
        return initial_strategy
    
    def _update_distribution_tracking(self, strategy: str, time_ms: float):
        """
        Update distribution tracking and performance metrics
        
        Args:
            strategy: Strategy used
            time_ms: Time taken in milliseconds
        """
        self.strategy_counts[strategy] += 1
        self.total_queries += 1
        self.recent_strategies.append(strategy)
        self.performance_history[strategy].append(time_ms)
        
        # Keep only last 100 performance measurements
        if len(self.performance_history[strategy]) > 100:
            self.performance_history[strategy] = self.performance_history[strategy][-100:]
    
    def _get_current_distribution(self) -> Dict[str, float]:
        """
        Get current distribution of strategies used
        
        Returns:
            Dictionary with strategy percentages
        """
        if self.total_queries == 0:
            return {"lightweight": 0.0, "medium": 0.0, "full": 0.0}
        
        return {
            strategy: count / self.total_queries
            for strategy, count in self.strategy_counts.items()
        }
    
    def _get_distribution_metrics(self) -> Dict:
        """
        Get comprehensive distribution metrics
        
        Returns:
            Dictionary with distribution and performance metrics
        """
        current_dist = self._get_current_distribution()
        target_dist = {"lightweight": 0.40, "medium": 0.35, "full": 0.25}
        
        # Calculate performance stats
        # NOTE: Use float() to convert numpy.float64 to Python float for msgpack serialization
        performance_stats = {}
        for strategy in ["lightweight", "medium", "full"]:
            times = self.performance_history.get(strategy, [])
            if times:
                performance_stats[strategy] = {
                    "avg_time_ms": float(np.mean(times)),
                    "p95_time_ms": float(np.percentile(times, 95)),
                    "target_ms": self.time_targets[strategy],
                    "target_met_pct": float(sum(1 for t in times if t <= self.time_targets[strategy]) / len(times) * 100)
                }
            else:
                performance_stats[strategy] = {
                    "avg_time_ms": 0.0,
                    "p95_time_ms": 0.0,
                    "target_ms": self.time_targets[strategy],
                    "target_met_pct": 0.0
                }
        
        return {
            "current_distribution": current_dist,
            "target_distribution": target_dist,
            "total_queries": self.total_queries,
            "strategy_counts": dict(self.strategy_counts),
            "performance_stats": performance_stats
        }
    
    def apply_lightweight_reranking(self, results: List[Dict], query: str) -> List[Dict]:
        """
        Lightweight reranking: Normalize + source weights + MMR (~50ms)
        
        Fast path for high quality results, skips cross-encoder
        """
        start_time = time.time()
        
        # Stage 1: Normalize scores (0-1 range)
        results = self.normalize_scores(results)
        
        # Stage 2: Apply source weights (Policy docs: 1.2x, Decision precedents: 1.1x)
        results = self.apply_source_weights(results, query)
        
        # Stage 3: MMR diversification (remove near-duplicates)
        results = self.diversify_results(results)
        
        # Final score = weighted score (no cross-encoder for lightweight)
        # Ensure Python float for serialization
        for result in results:
            result["final_score"] = float(result.get("mmr_score", result.get("weighted_score", result.get("normalized_score", 0))))
        
        # Re-sort
        results.sort(key=lambda x: x["final_score"], reverse=True)
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug(f"[AdaptiveReranker] Lightweight reranking completed in {elapsed_ms:.1f}ms")
        
        return results
    
    def apply_medium_reranking(self, results: List[Dict], query: str) -> List[Dict]:
        """
        Medium reranking: Lightweight + fast cross-encoder on top 10 (~100ms)
        
        Balanced approach for medium quality results
        """
        start_time = time.time()
        
        # Stage 1-3: Apply lightweight pipeline
        results = self.apply_lightweight_reranking(results, query)
        
        # Cross-encoder should already be loaded at initialization
        if self.cross_encoder is None:
            logger.warning("[AdaptiveReranker] Cross-encoder not available, skipping medium rerank")
            return results
        
        # Stage 4: Fast cross-encoder on top 10 only (MiniLM-L6 vs L12)
        top_n = min(10, len(results))
        top_results = results[:top_n]
        
        # Prepare pairs - extract text content for cross-encoder
        pairs = []
        for r in top_results:
            text = self._extract_text_content(r)
            pairs.append((query, text))
        
        # Get cross-encoder scores with batch processing
        if pairs:
            try:
                cross_scores = self.cross_encoder.predict(pairs, batch_size=32)
                
                # Stage 5: Merge top 10 reranked + bottom 10 original (40% cross-encoder)
                # Ensure Python float for serialization
                for i, result in enumerate(top_results):
                    result["final_score"] = float(
                        0.60 * result.get("final_score", result.get("weighted_score", 0)) +
                        0.40 * float(cross_scores[i])
                    )
                    result["cross_encoder_score"] = float(cross_scores[i])
            except Exception as e:
                logger.warning(f"[AdaptiveReranker] Cross-encoder prediction failed: {e}")
                # Fall back to lightweight scores
                for result in top_results:
                    result["final_score"] = float(result.get("final_score", result.get("weighted_score", 0)))

        # Bottom results keep lightweight score
        for result in results[top_n:]:
            result["final_score"] = float(result.get("final_score", result.get("weighted_score", 0)))
        
        # Re-sort all
        results.sort(key=lambda x: x["final_score"], reverse=True)
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug(f"[AdaptiveReranker] Medium reranking completed in {elapsed_ms:.1f}ms")
        
        return results
    
    def apply_full_reranking(self, results: List[Dict], query: str) -> List[Dict]:
        """
        Full reranking: Complete 5-stage pipeline for all 40 candidates (~200ms)
        
        Comprehensive reranking for low quality results
        """
        start_time = time.time()
        
        # Limit to top candidates as specified in config
        candidates = results[:self.max_candidates]
        
        # Stage 1: Normalize scores (0-1 range)
        candidates = self.normalize_scores(candidates)
        
        # Stage 2: Apply source weights (query-type specific)
        candidates = self.apply_source_weights(candidates, query)
        
        # Stage 3: MMR diversification (remove near-duplicates)
        candidates = self.diversify_results(candidates)
        
        # Stage 4: Cross-encoder reranking on all 40 candidates
        if self.cross_encoder is None:
            logger.warning("[AdaptiveReranker] Cross-encoder not available, using diversified scores only")
            for result in candidates:
                result["final_score"] = float(result.get("mmr_score", result.get("weighted_score", 0)))
        else:
            # Prepare pairs for all candidates
            pairs = []
            for r in candidates:
                text = self._extract_text_content(r)
                pairs.append((query, text))

            # Get cross-encoder scores with optimized batch processing
            if pairs:
                try:
                    cross_scores = self.cross_encoder.predict(pairs, batch_size=32)

                    # Stage 5: Final ranking (30% original + 70% cross-encoder)
                    # Ensure Python float for serialization
                    for i, result in enumerate(candidates):
                        result["cross_encoder_score"] = float(cross_scores[i])
                        result["final_score"] = float(
                            0.30 * result.get("mmr_score", result.get("weighted_score", 0)) +
                            0.70 * float(cross_scores[i])
                        )
                except Exception as e:
                    logger.warning(f"[AdaptiveReranker] Cross-encoder prediction failed: {e}")
                    # Fall back to diversified scores
                    for result in candidates:
                        result["final_score"] = float(result.get("mmr_score", result.get("weighted_score", 0)))
        
        # Re-sort by final score
        candidates.sort(key=lambda x: x["final_score"], reverse=True)
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug(f"[AdaptiveReranker] Full reranking completed in {elapsed_ms:.1f}ms")
        
        return candidates
    
    def normalize_scores(self, results: List[Dict]) -> List[Dict]:
        """
        Normalize scores to 0-1 range across sources
        
        Args:
            results: List of results with composite scores
        
        Returns:
            Results with normalized_score added
        """
        if not results:
            return results
        
        # Get all scores
        scores = [r.get("composite_score", 0) for r in results]
        min_score, max_score = min(scores), max(scores)
        score_range = max_score - min_score if max_score != min_score else 1.0
        
        # Normalize each result (ensure Python float for serialization)
        for result in results:
            result["normalized_score"] = float((result.get("composite_score", 0) - min_score) / score_range)

        return results
    
    def apply_source_weights(self, results: List[Dict], query: str) -> List[Dict]:
        """
        Apply source weights based on document type
        
        Args:
            results: List of results with normalized scores
            query: Original query text
        
        Returns:
            Results with weighted_score added
        """
        for result in results:
            result_type = result.get("type", "").lower()

            # Apply source weight and ensure Python float for serialization
            # Policy docs: 1.2x
            if "policy" in result_type:
                result["weighted_score"] = float(result.get("normalized_score", 0) * 1.2)
            # Decision precedents: 1.1x
            elif "decision" in result_type or "precedent" in result_type:
                result["weighted_score"] = float(result.get("normalized_score", 0) * 1.1)
            # Default weight
            else:
                result["weighted_score"] = float(result.get("normalized_score", 0))

        return results
    
    def diversify_results(self, results: List[Dict], lambda_param: float = 0.7) -> List[Dict]:
        """
        Apply MMR diversification to remove near-duplicates
        
        Args:
            results: List of results with weighted scores
            lambda_param: Balance between relevance and diversity (0-1)
        
        Returns:
            Diversified results with mmr_score added
        """
        if not results:
            return results
        
        # Extract embeddings for similarity calculation
        embeddings = []
        for result in results:
            if "embedding" in result:
                embeddings.append(result["embedding"])
            else:
                # Fallback: use normalized score as proxy
                embeddings.append([result.get("normalized_score", result.get("composite_score", 0))])
        
        # Convert to numpy array for efficient computation
        embeddings = np.array(embeddings)
        
        # MMR algorithm
        selected_indices = []
        remaining_indices = list(range(len(results)))
        
        # Select first (highest scored) result
        if remaining_indices:
            selected_indices.append(remaining_indices[0])
            remaining_indices.pop(0)
        
        # Iteratively select results
        while remaining_indices and len(selected_indices) < len(results):
            best_idx = None
            best_score = -float('inf')
            
            for idx in remaining_indices:
                # Relevance component
                relevance = results[idx].get("weighted_score", results[idx].get("composite_score", 0))
                
                # Diversity component (max similarity to selected)
                if selected_indices:
                    selected_embeddings = embeddings[selected_indices]
                    current_embedding = embeddings[idx:idx+1]
                    
                    # Compute cosine similarity
                    similarities = np.dot(selected_embeddings, current_embedding.T).flatten()
                    max_similarity = float(np.max(similarities))  # Convert to Python float for serialization
                else:
                    max_similarity = 0.0

                # MMR score (ensure Python float for serialization)
                mmr_score = float(lambda_param * relevance - (1 - lambda_param) * max_similarity)
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx
            
            if best_idx is not None:
                selected_indices.append(best_idx)
                remaining_indices.remove(best_idx)
            else:
                break
        
        # Create diversified results list
        diversified = []
        for i, idx in enumerate(selected_indices):
            result = results[idx].copy()
            # Ensure mmr_score is a Python float for serialization
            if i == 0:
                result["mmr_score"] = float(result.get("weighted_score", result.get("composite_score", 0)))
            else:
                result["mmr_score"] = float(best_score) if best_score != -float('inf') else 0.0
            diversified.append(result)
        
        return diversified
    
    def _extract_text_content(self, result: Dict) -> str:
        """
        Extract text content from result for cross-encoder processing
        
        Args:
            result: Result dictionary
        
        Returns:
            Extracted text content
        """
        # Try to get text content from various fields
        text = ""
        if "content" in result and isinstance(result["content"], str):
            text = result["content"]
        elif "metadata" in result and isinstance(result["metadata"], dict):
            # Extract from metadata
            meta = result["metadata"]
            text = meta.get("content_markdown", meta.get("situation", meta.get("decision_made", "")))
        if not text:  # Fallback to title
            text = result.get("title", "")
        
        return text
    
    def track_distribution(self) -> Dict:
        """
        Track distribution of reranking strategies
        
        Returns:
            Dictionary with current distribution metrics
        """
        return self._get_distribution_metrics()


__all__ = ['AdaptiveReranker']
