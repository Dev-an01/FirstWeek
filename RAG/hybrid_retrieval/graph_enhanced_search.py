"""
Graph-Enhanced Vector Search Component
=====================================

Implementation of the True Hybrid Retrieval system where the graph structure
ENHANCES vector search, not just runs parallel to it.

This component follows the Solution Manual specification that "the graph structure
ENHANCES vector search, not just runs parallel to it."

Key Features:
1. Extracts entities and intent from queries
2. Finds anchor entities in the graph
3. Performs graph traversal around entities
4. Executes vector similarity on related nodes
5. Combines graph distance and vector similarity into hybrid score
6. Uses the 60% vector + 40% graph scoring formula from the manual

Author: AI Officer Implementation Team
Date: 2025-10-29
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from neo4j import GraphDatabase

# Import existing components (use absolute imports to avoid relative import issues)
from vector_search.embedding_client import get_embedding_client
from graph_context.provider import GraphContextProvider
from graph_context.entity_extractor import EntityExtractor, get_entity_extractor
from graph_context.utils import calculate_graph_score, combine_scores
from graph_context.config import (
    NEO4J_CONFIG,
    GRAPH_CONTEXT_CONFIG,
    ENTITY_TYPE_MAPPING,
    CYPHER_TEMPLATES
)

logger = logging.getLogger(__name__)


class GraphConstrainedVectorSearch:
    """
    Graph-Enhanced Vector Search implementation
    
    This class implements the True Hybrid Retrieval system where the graph structure
    ENHANCES vector search, not just runs parallel to it.
    
    The implementation follows the Solution Manual specification and uses the
    60% vector + 40% graph scoring formula.
    """
    
    def __init__(
        self,
        neo4j_config: Optional[Dict] = None,
        vector_weight: float = 0.6,
        graph_weight: float = 0.4,
        enable_caching: bool = True,
        max_hops: int = 2,
        max_candidates: int = 50
    ):
        """
        Initialize the graph-enhanced vector search component
        
        Args:
            neo4j_config: Neo4j configuration (defaults to config)
            vector_weight: Weight for vector similarity in hybrid score (default: 0.6)
            graph_weight: Weight for graph proximity in hybrid score (default: 0.4)
            enable_caching: Enable caching of entity resolutions (default: True)
            max_hops: Maximum graph traversal hops (default: 2)
            max_candidates: Maximum candidate documents to consider (default: 50)
        """
        logger.info("Initializing GraphConstrainedVectorSearch...")
        
        # Configuration
        self.neo4j_config = neo4j_config or NEO4J_CONFIG
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight
        self.enable_caching = enable_caching
        self.max_hops = max_hops
        self.max_candidates = max_candidates
        
        # Connect to Neo4j
        try:
            logger.info(f"Connecting to Neo4j at {self.neo4j_config['uri']}")
            self.driver = GraphDatabase.driver(
                self.neo4j_config['uri'],
                auth=(self.neo4j_config['user'], self.neo4j_config['password'])
            )
            
            # Test connection
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                result.single()
            
            logger.info("✅ Neo4j connection established")
            
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
        
        # Initialize components (use singleton for EntityExtractor to prevent OOM)
        self.embedding_client = get_embedding_client()
        self.graph_provider = GraphContextProvider(neo4j_config=self.neo4j_config)
        self.entity_extractor = get_entity_extractor(
            neo4j_driver=self.driver,
            confidence_threshold=GRAPH_CONTEXT_CONFIG['entity_confidence_threshold']
        )
        
        # Initialize cache for entity resolutions
        self.entity_cache = {} if enable_caching else None
        
        logger.info("✅ GraphConstrainedVectorSearch initialized successfully")
    
    def extract_query_entities(self, query: str) -> List[Dict[str, Any]]:
        """
        Extract entities and intent from the query
        
        Args:
            query: User's natural language query
            
        Returns:
            List of extracted entities with metadata:
            [
                {
                    "text": "Akiko Tanaka",
                    "matched_name": "Akiko Tanaka",
                    "node_id": "exec_001_test",
                    "type": "Executive",
                    "confidence": 0.95,
                    "spacy_label": "PERSON",
                    "source": "spacy+neo4j"
                },
                ...
            ]
        """
        logger.info(f"Extracting entities from query: {query}")
        
        # Check cache first
        if self.entity_cache and query in self.entity_cache:
            logger.debug(f"Using cached entities for query: {query[:50]}...")
            return self.entity_cache[query]
        
        try:
            # Extract entities using the enhanced entity extractor
            entities = self.entity_extractor.extract(query, max_entities=10)
            
            # Cache the results
            if self.entity_cache:
                self.entity_cache[query] = entities
            
            logger.info(f"✅ Extracted {len(entities)} entities from query")
            return entities
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []
    
    def find_anchor_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Locate entities in Neo4j graph to serve as anchor points
        
        Args:
            entities: List of extracted entities from extract_query_entities()
            
        Returns:
            List of anchor entities that exist in the graph:
            [
                {
                    "text": "Akiko Tanaka",
                    "matched_name": "Akiko Tanaka",
                    "node_id": "exec_001_test",
                    "type": "Executive",
                    "confidence": 0.95
                },
                ...
            ]
        """
        logger.info(f"Finding anchor entities in graph from {len(entities)} extracted entities")
        
        anchor_entities = []
        
        for entity in entities:
            # Skip entities without node_id (not found in graph)
            if not entity.get('node_id'):
                logger.debug(f"Skipping entity not found in graph: {entity.get('text', 'Unknown')}")
                continue
            
            # Only include entities with sufficient confidence
            if entity.get('confidence', 0) < GRAPH_CONTEXT_CONFIG['entity_confidence_threshold']:
                logger.debug(f"Skipping low-confidence entity: {entity.get('text', 'Unknown')}")
                continue
            
            anchor_entities.append({
                'text': entity.get('text'),
                'matched_name': entity.get('matched_name'),
                'node_id': entity.get('node_id'),
                'type': entity.get('type'),
                'confidence': entity.get('confidence')
            })
        
        logger.info(f"✅ Found {len(anchor_entities)} anchor entities in graph")
        return anchor_entities
    
    def traverse_graph_context(
        self,
        anchor_entities: List[Dict[str, Any]],
        allowed_scopes: List[str] = None,
        company_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find related nodes within 1-2 hops of anchor entities
        
        Args:
            anchor_entities: List of anchor entities from find_anchor_entities()
            allowed_scopes: RBAC scopes for filtering (default: ['public'])
            
        Returns:
            Dictionary with traversal results:
            {
                "candidate_ids": ["exec_001_test_DEC_001", "POLICY-FIN-001", ...],
                "graph_distances": {
                    "exec_001_test_DEC_001": 1,
                    "POLICY-FIN-001": 2
                },
                "relationships": [
                    {
                        "source": "exec_001_test",
                        "target": "exec_001_test_DEC_001",
                        "distance": 1,
                        "relationship_type": "MADE_DECISION"
                    }
                ]
            }
        """
        logger.info(f"Traversing graph context from {len(anchor_entities)} anchor entities")
        
        # Use default scopes if not provided
        if not allowed_scopes:
            allowed_scopes = GRAPH_CONTEXT_CONFIG['default_scopes']
        
        if not anchor_entities:
            logger.warning("No anchor entities provided for graph traversal")
            return {
                "candidate_ids": [],
                "graph_distances": {},
                "relationships": []
            }
        
        try:
            # Build Cypher query for efficient graph traversal
            # This follows the example from the Solution Manual (section 5.1)
            anchor_ids = [entity['node_id'] for entity in anchor_entities]
            
            cypher_query = """
                UNWIND $anchor_ids AS anchor_id
                MATCH (anchor {id: anchor_id})
                MATCH path = (anchor)-[*1..$max_hops]-(doc)
                WHERE (doc:Decision OR doc:Policy OR doc:Executive)
                  AND (doc.confidentiality IS NULL OR doc.confidentiality IN $allowed_scopes)
                  AND ($company_id IS NULL OR doc.company_id IS NULL OR doc.company_id = $company_id)
                WITH DISTINCT doc,
                     anchor_id,
                     length(shortestPath((anchor)-[*]-(doc))) AS distance
                ORDER BY doc.id, distance ASC
                RETURN doc.id AS doc_id,
                       collect(DISTINCT {source: anchor_id, distance: distance})[0] AS distance_info,
                       labels(doc) AS doc_type
                LIMIT $max_candidates
            """

            with self.driver.session() as session:
                result = session.run(
                    cypher_query,
                    anchor_ids=anchor_ids,
                    max_hops=self.max_hops,
                    allowed_scopes=allowed_scopes,
                    company_id=company_id,
                    max_candidates=self.max_candidates
                )
                
                records = list(result)
                
                # Process results
                candidate_ids = []
                graph_distances = {}
                relationships = []
                
                for record in records:
                    doc_id = record['doc_id']
                    distance_info = record['distance_info']
                    doc_type = record['doc_type']
                    
                    # Add to candidates
                    if doc_id not in candidate_ids:
                        candidate_ids.append(doc_id)
                        graph_distances[doc_id] = distance_info['distance']
                        
                        # Create relationship record
                        relationships.append({
                            "source": distance_info['source'],
                            "target": doc_id,
                            "distance": distance_info['distance'],
                            "relationship_type": "RELATED_TO",
                            "target_type": doc_type[0] if doc_type else "Unknown"
                        })
                
                logger.info(f"✅ Graph traversal found {len(candidate_ids)} candidate documents")
                
                return {
                    "candidate_ids": candidate_ids,
                    "graph_distances": graph_distances,
                    "relationships": relationships
                }
                
        except Exception as e:
            logger.error(f"Graph traversal failed: {e}")
            return {
                "candidate_ids": [],
                "graph_distances": {},
                "relationships": []
            }
    
    def execute_hybrid_search(
        self,
        query: str,
        user_context: Dict[str, Any] = None,
        top_k: int = 10,
        allowed_scopes: List[str] = None,
        company_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete hybrid search combining graph and vector search
        
        This is the main method that orchestrates the entire graph-enhanced
        vector search process.
        
        Args:
            query: User's natural language query
            user_context: User context for RBAC filtering
            top_k: Number of results to return
            allowed_scopes: RBAC scopes for filtering
            
        Returns:
            Dictionary with hybrid search results:
            {
                "results": [
                    {
                        "id": "exec_001_test_DEC_001",
                        "type": "decision",
                        "title": "MegaCorp Discount Approval",
                        "content": "...",
                        "hybrid_score": 0.94,
                        "vector_score": 0.89,
                        "graph_score": 1.0,
                        "graph_distance": 1
                    },
                    ...
                ],
                "metadata": {
                    "query": "...",
                    "entities_found": 2,
                    "candidates_found": 15,
                    "execution_time_ms": 123
                }
            }
        """
        start_time = time.time()
        
        # Default user context
        if user_context is None:
            user_context = {
                "user_id": "unknown",
                "role": "employee",
                "allowed_scopes": allowed_scopes or ["public"]
            }
        
        # Default allowed scopes
        if not allowed_scopes:
            allowed_scopes = user_context.get("allowed_scopes", ["public"])
        
        logger.info(f"Executing hybrid search for query: {query[:50]}...")
        
        try:
            # Step 1: Extract entities from query
            entities = self.extract_query_entities(query)
            
            # Step 2: Find anchor entities in graph
            anchor_entities = self.find_anchor_entities(entities)
            
            # Step 3: Traverse graph to find related documents
            graph_context = self.traverse_graph_context(
                anchor_entities=anchor_entities,
                allowed_scopes=allowed_scopes,
                company_id=company_id,
            )
            
            # Step 4: Generate query embedding
            query_embedding = self.embedding_client.generate_embedding(
                text=query,
                source_id=f"query_{int(time.time())}",
                source_type="query"
            )
            
            # Step 5: Execute vector search constrained by graph context
            vector_results = self._execute_constrained_vector_search(
                query_embedding=query_embedding,
                candidate_ids=graph_context.get("candidate_ids"),
                top_k=top_k * 2,  # Get more for reranking
                allowed_scopes=allowed_scopes
            )
            
            # Step 6: Calculate hybrid scores
            hybrid_results = self._calculate_hybrid_scores(
                vector_results=vector_results,
                graph_distances=graph_context.get("graph_distances", {}),
                anchor_entities=anchor_entities
            )
            
            # Step 7: Sort by hybrid score and limit to top_k
            hybrid_results.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)
            final_results = hybrid_results[:top_k]
            
            # Step 8: Build response
            execution_time = (time.time() - start_time) * 1000
            
            response = {
                "results": final_results,
                "metadata": {
                    "query": query,
                    "entities_found": len(anchor_entities),
                    "candidates_found": len(graph_context.get("candidate_ids", [])),
                    "execution_time_ms": execution_time,
                    "vector_weight": self.vector_weight,
                    "graph_weight": self.graph_weight
                }
            }
            
            logger.info(f"✅ Hybrid search completed: {len(final_results)} results in {execution_time:.1f}ms")
            return response
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}", exc_info=True)
            return {
                "results": [],
                "metadata": {
                    "query": query,
                    "error": str(e),
                    "execution_time_ms": (time.time() - start_time) * 1000
                }
            }
    
    def calculate_hybrid_score(
        self,
        vector_score: float,
        graph_distance: int,
        max_distance: int = 5
    ) -> Dict[str, float]:
        """
        Calculate hybrid score using the 60/40 scoring formula
        
        Args:
            vector_score: Vector similarity score (0.0 to 1.0)
            graph_distance: Graph distance (number of hops)
            max_distance: Maximum distance to consider (default: 5)
            
        Returns:
            Dictionary with score components:
            {
                "vector_score": 0.89,
                "graph_score": 1.0,
                "hybrid_score": 0.934
            }
        """
        # Calculate graph score from distance
        graph_score = calculate_graph_score(graph_distance, max_distance)
        
        # Calculate hybrid score using 60% vector + 40% graph formula
        hybrid_score = combine_scores(
            vector_score=vector_score,
            graph_score=graph_score,
            vector_weight=self.vector_weight,
            graph_weight=self.graph_weight
        )
        
        return {
            "vector_score": vector_score,
            "graph_score": graph_score,
            "hybrid_score": hybrid_score
        }
    
    def _execute_constrained_vector_search(
        self,
        query_embedding: np.ndarray,
        candidate_ids: List[str] = None,
        top_k: int = 20,
        allowed_scopes: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute vector search constrained by graph candidate IDs
        
        Args:
            query_embedding: Query embedding vector
            candidate_ids: List of candidate document IDs from graph traversal
            top_k: Maximum results to return
            allowed_scopes: RBAC scopes for filtering
            
        Returns:
            List of vector search results with metadata
        """
        # Import here to avoid circular imports
        from vector_search.postgres_client import PostgresVectorClient
        from vector_search.config import POSTGRES_CONFIG
        
        try:
            # Initialize PostgreSQL client
            vector_client = PostgresVectorClient(config=POSTGRES_CONFIG)
            
            # Execute constrained vector search
            results = vector_client.vector_search(
                query_embedding=query_embedding,
                candidate_ids=candidate_ids,
                top_k=top_k,
                min_score=0.3  # Lower threshold for hybrid search
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Constrained vector search failed: {e}")
            return []
    
    def _calculate_hybrid_scores(
        self,
        vector_results: List[Dict[str, Any]],
        graph_distances: Dict[str, int],
        anchor_entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate hybrid scores for vector search results
        
        Args:
            vector_results: Results from vector search
            graph_distances: Graph distances from traversal
            anchor_entities: Anchor entities used for traversal
            
        Returns:
            List of results with hybrid scores
        """
        hybrid_results = []
        
        for result in vector_results:
            doc_id = result.get('source_id')
            vector_score = result.get('similarity_score', 0.0)
            
            # Get graph distance (default to max_distance if not found)
            graph_distance = graph_distances.get(doc_id, self.max_hops + 1)
            
            # Calculate hybrid score
            scores = self.calculate_hybrid_score(
                vector_score=vector_score,
                graph_distance=graph_distance
            )
            
            # Create enhanced result
            hybrid_result = {
                "id": doc_id,
                "type": result.get('source_type', 'unknown'),
                "title": result.get('title', ''),
                "content": result.get('content', ''),
                "vector_score": scores["vector_score"],
                "graph_score": scores["graph_score"],
                "hybrid_score": scores["hybrid_score"],
                "graph_distance": graph_distance
            }
            
            # Add metadata from original result
            for key, value in result.items():
                if key not in hybrid_result:
                    hybrid_result[key] = value
            
            hybrid_results.append(hybrid_result)
        
        return hybrid_results
    
    def close(self):
        """Close Neo4j connection and clean up resources"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Export the main class
__all__ = ['GraphConstrainedVectorSearch']