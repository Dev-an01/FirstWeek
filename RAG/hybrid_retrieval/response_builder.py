"""
Response Builder
================

Formats final response with:
- Ranked results
- Query metadata
- Performance metrics
- Provenance (why each result was returned)
- Diagnostics
"""

import logging
from typing import Dict, List, Optional

from .utils import get_logger

logger = get_logger(__name__)


class ResponseBuilder:
    """
    Build final structured response
    """
    
    def __init__(self):
        """Initialize response builder"""
        logger.info("[ResponseBuilder] Initialized")
    
    def build(
        self,
        results: List[Dict],
        query: str,
        query_analysis: Dict,
        retrieval_metadata: Dict,
        reranking_info: Dict,
        total_time: float
    ) -> Dict:
        """
        Build comprehensive response
        
        Args:
            results: Final ranked results
            query: Original query
            query_analysis: From QueryAnalyzer
            retrieval_metadata: From multi-source retrieval
            reranking_info: From adaptive reranker
            total_time: Total execution time (seconds)
        
        Returns:
            Complete structured response
        """
        # Add ranks
        for i, result in enumerate(results, start=1):
            result["rank"] = i
            
            # Add "why_relevant" explanation
            if "provenance" not in result:
                result["provenance"] = {}
            result["provenance"]["why_relevant"] = self._explain_relevance(result)
        
        # Build metadata
        metadata = {
            "query": query,
            "query_analysis": {
                "type": query_analysis.get("query_type"),
                "complexity": query_analysis.get("complexity"),
                "has_entities": query_analysis.get("has_entities"),
                "entity_count": len(query_analysis.get("entities", []))
            },
            "retrieval_strategy": {
                "strategy": retrieval_metadata.get("strategy"),
                "sources_used": list(retrieval_metadata.get("timing", {}).keys()),
                "execution_mode": retrieval_metadata.get("execution_mode")
            },
            "reranking": {
                "strategy": reranking_info.get("strategy"),
                "time_ms": reranking_info.get("metadata", {}).get("time_ms", 0)
            },
            "performance": {
                "total_time_ms": total_time * 1000,
                "breakdown": {
                    "retrieval": retrieval_metadata.get("timing", {}),
                    "reranking": reranking_info.get("metadata", {}).get("time_ms", 0)
                }
            },
            "results_summary": {
                "total_returned": len(results),
                "multi_source_count": sum(1 for r in results if len(r.get("found_in", [])) > 1)
            }
        }
        
        logger.info(f"[ResponseBuilder] Built response with {len(results)} results in {total_time*1000:.1f}ms")
        
        return {
            "results": results,
            "metadata": metadata
        }
    
    def _explain_relevance(self, result: Dict) -> str:
        """
        Generate human-readable relevance explanation
        
        Args:
            result: Single result object
        
        Returns:
            Explanation string
        """
        found_in = result.get("found_in", [])
        scores = result.get("source_scores", result.get("scores", {}))
        
        explanations = []
        
        # Multi-source agreement
        if len(found_in) >= 2:
            explanations.append(f"Found in {len(found_in)} sources ({', '.join(found_in)})")
        
        # High vector similarity
        if scores.get("vector", 0) >= 0.85:
            explanations.append("High semantic similarity")
        
        # Strong graph connection
        if scores.get("graph", 0) >= 0.8:
            explanations.append("Direct graph relationship")
        
        # Memory precedent
        if "memory" in found_in:
            explanations.append("Similar past interaction")
        
        if not explanations:
            explanations.append("Relevant match")
        
        return "; ".join(explanations)


__all__ = ['ResponseBuilder']
