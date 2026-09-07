"""
Result Fusion
=============

Merges results from vector, graph, and memory sources.

Key challenges:
1. Different result formats from each source
2. Duplicates (same document from multiple sources)
3. Score normalization (different scales)
4. Composite scoring (weighted combination)
"""

import logging
from typing import Dict, List, Optional

from .utils import get_logger, deduplicate_results

logger = get_logger(__name__)


class ResultFusion:
    """
    Fuse and deduplicate results from multiple sources with enhanced deduplication
    """
    
    def __init__(self):
        """Initialize result fusion component"""
        logger.info("[ResultFusion] Initialized with enhanced deduplication")
    
    def fuse(
        self,
        retrieval_results: Dict,
        weights: Dict[str, float]
    ) -> List[Dict]:
        """
        Merge results from vector, graph, memory
        
        Args:
            retrieval_results: {
                "vector": {"results": [...]},
                "graph": {
                    "candidate_ids": [...],
                    "graph_distances": {...},
                    "relationships": [...]
                },
                "memory": {"results": [...]}
            }
            weights: {
                "vector": 0.60,
                "graph": 0.30,
                "memory": 0.10
            }
        
        Returns:
            List of fused results with composite scores
            [
                {
                    "id": "DC_AKIKO_001",
                    "content": "...",
                    "composite_score": 0.92,
                    "source_scores": {
                        "vector": 0.89,
                        "graph": 1.0,
                        "memory": 0.85
                    },
                    "found_in": ["vector", "graph", "memory"],
                    "provenance": {...}
                },
                ...
            ]
        """
        all_docs = {}
        
        # Step 1: Collect vector results
        for result in retrieval_results.get("vector", {}).get("results", []):
            doc_id = result.get("source_id") or result.get("id")
            all_docs[doc_id] = {
                "id": doc_id,
                "type": result.get("type") or result.get("source_type"),
                "title": result.get("title"),
                "content": result.get("content"),
                "metadata": result.get("metadata", {}),
                "scores": {
                    "vector": result.get("similarity_score", 0),
                    "graph": 0.0,
                    "memory": 0.0
                },
                "found_in": ["vector"],
                "provenance": {
                    "vector_metadata": result.get("metadata", {})
                }
            }
        
        # Step 2: Add graph scores
        graph_data = retrieval_results.get("graph", {})
        graph_distances = graph_data.get("graph_distances", {})
        graph_relationships = graph_data.get("relationships", [])
        
        for doc_id, distance in graph_distances.items():
            # Convert distance to score (closer = higher score)
            # Use normalized decay (1.0, 0.75, 0.50) instead of 1/distance for balanced scoring
            graph_score = max(0, 1.0 - (distance - 1) * 0.25) if distance > 0 else 0
            
            if doc_id in all_docs:
                # Document already from vector, add graph score
                all_docs[doc_id]["scores"]["graph"] = graph_score
                all_docs[doc_id]["found_in"].append("graph")
                all_docs[doc_id]["provenance"]["graph_context"] = self._find_relationship_context(
                    doc_id, graph_relationships
                )
            else:
                # Document only from graph (not in vector top 20)
                all_docs[doc_id] = {
                    "id": doc_id,
                    "type": "document",  # Default type
                    "scores": {
                        "vector": 0.0,
                        "graph": graph_score,
                        "memory": 0.0
                    },
                    "found_in": ["graph"],
                    "provenance": {
                        "graph_context": self._find_relationship_context(
                            doc_id, graph_relationships
                        )
                    }
                }
        
        # Step 3: Add memory scores (if available)
        for mem_result in retrieval_results.get("memory", {}).get("results", []):
            # Memory results reference past queries, not necessarily documents
            # Extract document IDs from sources_used
            for source in mem_result.get("sources_used", []) if mem_result.get("sources_used") else []:
                doc_id = source.get("source_id")
                if doc_id and doc_id in all_docs:
                    all_docs[doc_id]["scores"]["memory"] = mem_result.get("memory_score", 0)
                    if "memory" not in all_docs[doc_id]["found_in"]:
                        all_docs[doc_id]["found_in"].append("memory")
                    all_docs[doc_id]["provenance"]["memory_context"] = (
                        f"Similar to query from {mem_result.get('days_ago')} days ago "
                        f"({'👍' if mem_result.get('user_feedback') == 1 else '👎' if mem_result.get('user_feedback') == -1 else 'no feedback'})"
                    )
        
        # Step 4: Calculate composite scores
        for doc_id, doc_data in all_docs.items():
            scores = doc_data["scores"]
            composite = (
                weights["vector"] * scores["vector"] +
                weights["graph"] * scores["graph"] +
                weights["memory"] * scores["memory"]
            )
            doc_data["composite_score"] = composite
            
            # Multi-source boost (documents found in multiple sources are more relevant)
            source_count = len(doc_data["found_in"])
            if source_count >= 2:
                boost = 0.10 if source_count == 2 else 0.15  # 10% for 2 sources, 15% for 3+
                doc_data["composite_score"] = min(1.0, doc_data["composite_score"] + boost)
            
            # Store source scores separately for transparency
            doc_data["source_scores"] = scores.copy()
        
        # Step 5: Sort by composite score
        fused_results = sorted(
            all_docs.values(),
            key=lambda x: x["composite_score"],
            reverse=True
        )
        
        # Log fusion statistics
        source_counts = {"vector": 0, "graph": 0, "memory": 0}
        multi_source_count = 0
        
        for doc in fused_results:
            for source in doc["found_in"]:
                source_counts[source] += 1
            if len(doc["found_in"]) > 1:
                multi_source_count += 1
        
        logger.info(f"[ResultFusion] Fused {len(fused_results)} unique documents from {len(retrieval_results)} sources")
        logger.debug(f"[ResultFusion] Source distribution: {source_counts}, Multi-source: {multi_source_count}")
        
        return fused_results
    
    def _generate_relevance_explanation(self, doc_data: Dict) -> str:
        """Generate human-readable relevance explanation for a document"""
        found_in = doc_data.get("found_in", [])
        scores = doc_data.get("source_scores", {})
        provenance = doc_data.get("provenance", {})
        
        explanations = []
        
        # Multi-source agreement
        if len(found_in) >= 2:
            explanations.append(f"Found in {len(found_in)} sources ({', '.join(found_in)})")
        
        # High individual scores
        for source, score in scores.items():
            if score >= 0.8:
                explanations.append(f"High {source} relevance ({score:.2f})")
        
        # Specific provenance
        if "graph_context" in provenance:
            explanations.append(provenance["graph_context"])
        if "memory_context" in provenance:
            explanations.append(provenance["memory_context"])
        
        if not explanations:
            explanations.append("Relevant match")
        
        return "; ".join(explanations)
        logger.info(f"[ResultFusion] Fused {len(fused_results)} unique documents from {len(retrieval_results)} sources")
        
        return fused_results
    
    def _find_relationship_context(
        self,
        doc_id: str,
        relationships: List[Dict]
    ) -> str:
        """
        Find human-readable relationship context for document
        
        Args:
            doc_id: Document ID
            relationships: List of graph relationships
        
        Returns:
            Explanation string like "Akiko MADE_DECISION involving Acme Corp"
        """
        for rel in relationships:
            if rel.get("target") == doc_id or rel.get("target_id") == doc_id:
                return (
                    f"{rel.get('source')} {rel.get('type')} "
                    f"(distance: {rel.get('distance', '?')} hops)"
                )
        return "Found via graph traversal"


__all__ = ['ResultFusion']
