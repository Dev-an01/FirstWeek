"""
Graph Context Provider - Main API for graph-enhanced vector search

Discovers graph context to enhance vector search by:
1. Extracting entities from queries
2. Finding related documents via graph traversal
3. Providing candidate IDs for constrained vector search
4. Calculating graph proximity scores for hybrid ranking

This is NOT a standalone search engine - it's a helper for VectorSearchEngine.
"""

import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import time

from .config import (
    NEO4J_CONFIG,
    GRAPH_CONTEXT_CONFIG,
    ENTITY_PATTERNS
)
from .entity_extractor import EntityExtractor, get_entity_extractor
from .graph_traversal import GraphTraversal
from .relationship_mapper import RelationshipMapper
from .utils import (
    format_entity_list,
    calculate_graph_score
)

# Observability imports
from observability.decorators import trace_function
from observability.logging import StructuredLogger
from observability.metrics import (
    graph_query_latency,
    retrieval_results_counter,
)

# WEEK 1, DAY 3: LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    # Fallback: no-op decorator that accepts keyword arguments
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        # Handle both @traceable and @traceable(name=..., tags=...)
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return decorator
    LANGSMITH_AVAILABLE = False

logger = logging.getLogger('graph_context.provider')
obs_logger = StructuredLogger('graph_context_provider')


class GraphContextProvider:
    """
    Graph Context Provider - Enhances vector search with graph relationships
    
    Key Methods:
        discover_context() - Main method: extract entities and find related documents
        calculate_graph_scores() - Calculate proximity scores for hybrid ranking
        explain_relationship() - Explain why a result is relevant
    
    Usage (by VectorSearchEngine):
        provider = GraphContextProvider(neo4j_config)
        
        # Get graph context
        context = provider.discover_context(
            query="Who worked with Akiko on Acme?",
            allowed_scopes=["public", "confidential"]
        )
        
        # Use context to constrain vector search
        if context["has_context"]:
            vector_search(candidate_ids=context["candidate_ids"], ...)
    """
    
    def __init__(
        self,
        neo4j_config: Dict = None,
        entity_confidence_threshold: float = None
    ):
        """
        Initialize graph context provider
        
        Args:
            neo4j_config: Neo4j connection configuration (defaults to config)
            entity_confidence_threshold: Min confidence for entity matching
        """
        logger.info("Initializing GraphContextProvider...")
        
        # Configuration
        self.neo4j_config = neo4j_config or NEO4J_CONFIG
        self.confidence_threshold = (
            entity_confidence_threshold or 
            GRAPH_CONTEXT_CONFIG['entity_confidence_threshold']
        )
        
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
        self.entity_extractor = get_entity_extractor(self.driver)
        self.graph_traversal = GraphTraversal(self.driver)
        self.relationship_mapper = RelationshipMapper()
        
        logger.info("✅ GraphContextProvider initialized successfully")
    
    @trace_function("graph_context_provider", "discover_context")
    @traceable(name="graph_context_discovery", tags=["retrieval", "graph"])
    def discover_context(
        self,
        query: str,
        entities: List[Dict] = None,
        max_candidates: int = None,
        allowed_scopes: List[str] = None,
        company_id: str = None
    ) -> Dict:
        """
        Discover graph context around query entities
        
        THIS IS THE KEY METHOD called by VectorSearchEngine
        
        Flow:
        1. Extract entities from query (if not provided)
        2. Find corresponding nodes in Neo4j graph
        3. Traverse graph to find related documents
        4. Return candidate IDs for constrained vector search
        
        Args:
            query: User's question text
            entities: Pre-extracted entities (optional, will extract if None)
            max_candidates: Max document IDs to return
            allowed_scopes: RBAC scopes (filter graph traversal)
        
        Returns:
            {
                "has_context": bool,  # True if graph context found
                "candidate_ids": List[str],  # Document IDs to search within
                "graph_distances": Dict[str, int],  # Document ID → distance
                "relationships": List[Dict],  # Relationship paths
                "entities": List[Dict],  # Extracted entities
                "context_explanation": str  # Human-readable summary
            }
        
        Example Return Value:
            {
                "has_context": True,
                "candidate_ids": ["exec_001_test_DEC_001", "POLICY-FIN-001", ...],
                "graph_distances": {
                    "exec_001_test_DEC_001": 1,  # 1 hop from Akiko
                    "POLICY-FIN-001": 2  # 2 hops
                },
                "relationships": [
                    {
                        "source": "exec_001_test",
                        "target": "exec_001_test_DEC_001",
                        "distance": 1,
                        "score": 1.0
                    }
                ],
                "entities": [
                    {
                        "text": "Akiko",
                        "matched_name": "Akiko Tanaka",
                        "node_id": "exec_001_test",
                        "type": "Executive",
                        "confidence": 0.95
                    }
                ],
                "context_explanation": "Found 15 decisions related to Akiko Tanaka"
            }
        
        If no graph context:
            {
                "has_context": False,
                "candidate_ids": None,  # Vector search will NOT constrain
                "context_explanation": "No entities found in graph"
            }
        """
        start_time = time.time()
        
        logger.info(f"Discovering graph context for query: {query}")
        obs_logger.info(
            "Graph context discovery started",
            query_length=len(query),
            max_candidates=max_candidates
        )
        
        # Use defaults if not provided
        max_candidates = max_candidates or GRAPH_CONTEXT_CONFIG['max_candidates']
        allowed_scopes = allowed_scopes or GRAPH_CONTEXT_CONFIG['default_scopes']
        
        # Step 1: Extract entities if not provided
        if entities is None:
            entities = self.entity_extractor.extract(query)
        
        # Filter entities by confidence threshold
        entities = [
            e for e in entities 
            if e.get('confidence', 0) >= self.confidence_threshold
        ]
        
        # If no entities found, return empty context
        if not entities:
            logger.info("No entities extracted from query")
            latency_ms = (time.time() - start_time) * 1000
            graph_query_latency.observe(latency_ms / 1000)
            obs_logger.info(
                "Graph context discovery completed - no entities",
                latency_ms=latency_ms,
                has_context=False
            )
            return {
                "has_context": False,
                "candidate_ids": [],  # Changed from None to []
                "entities": [],
                "context_explanation": "No entities extracted from query"
            }
        
        logger.info(f"Extracted {len(entities)} entities: {format_entity_list(entities)}")
        
        # Step 2: Build anchor nodes list
        anchor_nodes = []
        for entity in entities:
            if 'node_id' in entity:
                anchor_nodes.append({
                    'node_id': entity['node_id'],
                    'type': entity['type'],
                    'name': entity.get('matched_name', entity['text'])
                })
        
        if not anchor_nodes:
            logger.info("No entities matched to graph nodes")
            return {
                "has_context": False,
                "candidate_ids": [],  # Changed from None to []
                "entities": entities,
                "context_explanation": "Entities not found in knowledge graph"
            }
        
        logger.info(f"Found {len(anchor_nodes)} anchor nodes in graph")
        
        # NEW: Include Executive nodes themselves as candidates
        # (for queries like "Tell me about Sarah Kim" where the profile is the answer)
        executive_node_ids = [
            node['node_id'] 
            for node in anchor_nodes 
            if node.get('type') == 'Executive' and node.get('node_id')
        ]
        
        # Step 3: Traverse graph to find related documents
        try:
            traversal_result = self.graph_traversal.find_related_documents(
                anchor_nodes=anchor_nodes,
                max_candidates=max_candidates,
                allowed_scopes=allowed_scopes,
                company_id=company_id
            )
        except Exception as e:
            logger.error(f"Graph traversal failed: {e}")
            return {
                "has_context": False,
                "candidate_ids": [],  # Changed from None to []
                "entities": entities,
                "context_explanation": f"Graph traversal error: {str(e)}"
            }
        
        # Extract results
        candidate_ids = traversal_result.get('candidate_ids', [])
        distances = traversal_result.get('distances', {})
        relationships = traversal_result.get('relationships', [])
        
        # NEW: Add Executive nodes to candidates (for profile queries)
        if executive_node_ids:
            for exec_id in executive_node_ids:
                if exec_id not in candidate_ids:
                    candidate_ids.append(exec_id)
                    distances[exec_id] = 0  # Distance 0 = exact entity match
            logger.info(f"Added {len(executive_node_ids)} Executive profiles to candidates: {executive_node_ids}")
        
        # If no candidates found, return empty context
        if not candidate_ids:
            logger.info("No related documents found in graph")
            return {
                "has_context": False,
                "candidate_ids": [],  # Changed from None to []
                "entities": entities,
                "context_explanation": "No related documents found in knowledge graph"
            }
        
        # Step 4: Build context explanation
        explanation = self.relationship_mapper.build_context_summary(
            entities=entities,
            candidate_count=len(candidate_ids),
            relationships=relationships
        )
        
        logger.info(f"✅ Graph context discovered: {len(candidate_ids)} candidates")
        logger.debug(f"Context: {explanation}")
        
        # Track metrics
        latency_ms = (time.time() - start_time) * 1000
        graph_query_latency.observe(latency_ms / 1000)
        retrieval_results_counter.labels(source='graph').observe(len(candidate_ids))
        
        # Log completion
        obs_logger.info(
            "Graph context discovery completed",
            latency_ms=latency_ms,
            has_context=True,
            candidates_count=len(candidate_ids),
            entities_count=len(entities),
            relationships_count=len(relationships)
        )
        
        # Return graph context
        return {
            "has_context": True,
            "candidate_ids": candidate_ids,
            "graph_distances": distances,
            "relationships": relationships,
            "entities": entities,
            "context_explanation": explanation
        }
    
    def calculate_graph_scores(
        self,
        document_ids: List[str],
        anchor_entities: List[Dict]
    ) -> Dict[str, float]:
        """
        Calculate graph proximity scores for documents
        
        Used for hybrid scoring: 60% vector + 40% graph
        
        Args:
            document_ids: List of document IDs (from vector search)
            anchor_entities: Entities extracted from query
        
        Returns:
            {
                "exec_001_test_DEC_001": 1.0,  # Distance 1 → score 1.0
                "POLICY-FIN-001": 0.5,  # Distance 2 → score 0.5
                "exec_002_test_DEC_001": 0.33  # Distance 3 → score 0.33
            }
        
        Formula: score = 1.0 / graph_distance
        """
        logger.debug(f"Calculating graph scores for {len(document_ids)} documents")
        
        scores = {}
        
        # Get anchor node IDs
        anchor_ids = [
            e['node_id'] for e in anchor_entities 
            if 'node_id' in e
        ]
        
        if not anchor_ids:
            logger.warning("No anchor nodes provided, returning zero scores")
            return {doc_id: 0.0 for doc_id in document_ids}
        
        # Calculate shortest path from any anchor to each document
        for doc_id in document_ids:
            min_distance = float('inf')
            
            # Find shortest path from any anchor
            for anchor_id in anchor_ids:
                try:
                    path = self.graph_traversal.find_shortest_path(
                        source_id=anchor_id,
                        target_id=doc_id
                    )
                    
                    if path:
                        distance = path['distance']
                        min_distance = min(min_distance, distance)
                
                except Exception as e:
                    logger.debug(f"Path finding failed for {anchor_id} → {doc_id}: {e}")
                    continue
            
            # Calculate score
            if min_distance == float('inf'):
                # No path found
                scores[doc_id] = 0.0
            else:
                scores[doc_id] = calculate_graph_score(min_distance)
        
        logger.debug(f"Calculated scores for {len(scores)} documents")
        return scores
    
    def explain_relationship(
        self,
        source_entity: str,
        target_document_id: str
    ) -> str:
        """
        Explain how target document relates to source entity
        
        Args:
            source_entity: Entity name or node ID (e.g., "Akiko Tanaka" or "exec_001_test")
            target_document_id: Document ID (e.g., "exec_001_test_DEC_001")
        
        Returns:
            Human-readable explanation
            "Akiko Tanaka MADE_DECISION on this case"
        """
        logger.debug(f"Explaining relationship: {source_entity} → {target_document_id}")
        
        # Try to find source node ID
        if not source_entity.startswith('exec_') and not source_entity.startswith('POLICY'):
            # It's a name, try to match to node
            entities = self.entity_extractor.extract(source_entity)
            if entities:
                source_id = entities[0].get('node_id')
                source_name = entities[0].get('matched_name', source_entity)
            else:
                source_id = source_entity
                source_name = source_entity
        else:
            source_id = source_entity
            source_name = source_entity
        
        # Find path
        try:
            path = self.graph_traversal.find_shortest_path(
                source_id=source_id,
                target_id=target_document_id
            )
            
            if path:
                return self.relationship_mapper.explain_path(path, source_name)
            else:
                return "No direct relationship found"
        
        except Exception as e:
            logger.debug(f"Relationship explanation failed: {e}")
            return "Relationship unknown"
    
    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
