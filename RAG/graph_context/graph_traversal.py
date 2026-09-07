"""
Graph Traversal - Execute Neo4j Cypher queries to discover context

Finds related documents by traversing the knowledge graph from anchor entities.
"""

import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase

from .config import (
    GRAPH_CONTEXT_CONFIG,
    CYPHER_TEMPLATES
)
from .utils import (
    parse_neo4j_node,
    parse_neo4j_relationship,
    calculate_graph_score
)

logger = logging.getLogger('graph_context.graph_traversal')


class GraphTraversal:
    """
    Execute Cypher queries to discover graph context
    
    Traverses from anchor nodes (entities) to find related documents
    with RBAC filtering and distance calculation.
    """
    
    def __init__(self, neo4j_driver):
        """
        Initialize graph traversal engine
        
        Args:
            neo4j_driver: Neo4j driver instance
        """
        self.driver = neo4j_driver
        self.max_hops = GRAPH_CONTEXT_CONFIG['max_traversal_hops']
        self.timeout_ms = GRAPH_CONTEXT_CONFIG['query_timeout_ms']
    
    def find_related_documents(
        self,
        anchor_nodes: List[Dict],
        max_hops: int = None,
        max_candidates: int = None,
        allowed_scopes: List[str] = None,
        company_id: str = None
    ) -> Dict:
        """
        Find documents related to anchor nodes via graph traversal
        
        Args:
            anchor_nodes: Starting points (e.g., [{"node_id": "exec_001_test", "type": "Executive"}])
            max_hops: Maximum traversal depth (default: from config)
            max_candidates: Max documents to return (default: from config)
            allowed_scopes: RBAC filtering (default: ['public'])
        
        Returns:
            {
                "candidate_ids": ["DC_AKIKO_001", "POLICY-FIN-001", ...],
                "distances": {"DC_AKIKO_001": 1, "POLICY-FIN-001": 2, ...},
                "relationships": [
                    {
                        "source": "exec_001_test",
                        "target": "DC_AKIKO_001",
                        "distance": 1,
                        "path_description": "Akiko → MADE_DECISION → DC_001"
                    },
                    ...
                ]
            }
        """
        logger.info(f"Finding related documents for {len(anchor_nodes)} anchor nodes")
        
        # Use defaults if not provided
        max_hops = max_hops or self.max_hops
        max_candidates = max_candidates or GRAPH_CONTEXT_CONFIG['max_candidates']
        allowed_scopes = allowed_scopes or GRAPH_CONTEXT_CONFIG['default_scopes']
        
        # Traverse from each anchor
        all_candidates = {}
        all_relationships = []
        
        for anchor in anchor_nodes:
            anchor_id = anchor['node_id']
            
            logger.debug(f"Traversing from anchor: {anchor_id}")
            
            # Find documents related to this anchor
            result = self._traverse_from_anchor(
                anchor_id=anchor_id,
                max_hops=max_hops,
                allowed_scopes=allowed_scopes,
                company_id=company_id
            )
            
            # Merge results
            for doc_id, distance in result['distances'].items():
                # Keep shortest distance if duplicate
                if doc_id not in all_candidates or distance < all_candidates[doc_id]:
                    all_candidates[doc_id] = distance
            
            all_relationships.extend(result['relationships'])
        
        # Sort by distance and limit
        sorted_candidates = sorted(
            all_candidates.items(),
            key=lambda x: x[1]  # Sort by distance
        )[:max_candidates]
        
        candidate_ids = [doc_id for doc_id, _ in sorted_candidates]
        distances = dict(sorted_candidates)
        
        logger.info(f"Found {len(candidate_ids)} candidate documents")
        
        return {
            'candidate_ids': candidate_ids,
            'distances': distances,
            'relationships': all_relationships[:max_candidates]
        }
    
    def _traverse_from_anchor(
        self,
        anchor_id: str,
        max_hops: int,
        allowed_scopes: List[str],
        company_id: str = None
    ) -> Dict:
        """
        Traverse from single anchor node

        Args:
            anchor_id: Node ID to start from
            max_hops: Maximum traversal depth
            allowed_scopes: RBAC scopes
            company_id: Optional company filter for multi-tenant isolation

        Returns:
            Dictionary with distances and relationships
        """
        # Build Cypher query with optional company_id filter
        company_filter = ""
        if company_id:
            company_filter = "AND ($company_id IS NULL OR doc.company_id = $company_id)"

        cypher = f"""
            MATCH (anchor {{id: $anchor_id}})
            MATCH path = (anchor)-[*1..{max_hops}]-(doc)
            WHERE (doc:Decision OR doc:Policy)
              AND (doc.confidentiality IS NULL
                   OR doc.confidentiality IN $allowed_scopes)
              {company_filter}
            WITH DISTINCT doc,
                 length(shortestPath((anchor)-[*]-(doc))) AS distance,
                 path
            RETURN doc.id AS doc_id,
                   distance,
                   nodes(path) AS path_nodes,
                   relationships(path) AS path_rels
            ORDER BY distance ASC
            LIMIT 100
        """

        try:
            with self.driver.session() as session:
                params = {
                    "anchor_id": anchor_id,
                    "allowed_scopes": allowed_scopes,
                }
                if company_id:
                    params["company_id"] = company_id

                result = session.run(cypher, **params)
                records = list(result)
                
                distances = {}
                relationships = []
                
                for record in records:
                    doc_id = record['doc_id']
                    distance = record['distance']
                    
                    distances[doc_id] = distance
                    
                    # Build relationship description
                    relationships.append({
                        'source': anchor_id,
                        'target': doc_id,
                        'distance': distance,
                        'score': calculate_graph_score(distance)
                    })
                
                return {
                    'distances': distances,
                    'relationships': relationships
                }
                
        except Exception as e:
            logger.error(f"Graph traversal failed from anchor '{anchor_id}': {e}")
            return {
                'distances': {},
                'relationships': []
            }
    
    def find_shortest_path(
        self,
        source_id: str,
        target_id: str
    ) -> Optional[Dict]:
        """
        Find shortest path between two nodes
        
        Used for relationship explanations
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
        
        Returns:
            {
                "distance": 2,
                "nodes": [{"id": "...", "name": "..."}, ...],
                "relationships": [{"type": "MADE_DECISION"}, ...]
            }
            or None if no path found
        """
        cypher = CYPHER_TEMPLATES['shortest_path']
        
        try:
            with self.driver.session() as session:
                result = session.run(
                    cypher,
                    source_id=source_id,
                    target_id=target_id
                )
                record = result.single()
                
                if not record:
                    return None
                
                # Parse nodes and relationships
                nodes = []
                for node in record['nodes']:
                    nodes.append(parse_neo4j_node(node))
                
                rels = []
                for rel in record['rels']:
                    rels.append(parse_neo4j_relationship(rel))
                
                return {
                    'distance': record['distance'],
                    'nodes': nodes,
                    'relationships': rels
                }
                
        except Exception as e:
            logger.error(f"Shortest path query failed: {e}")
            return None
    
    def get_node_details(self, node_id: str) -> Optional[Dict]:
        """
        Get details for a specific node
        
        Args:
            node_id: Node ID
        
        Returns:
            Node details or None
        """
        cypher = """
            MATCH (n {id: $node_id})
            RETURN n.id AS id,
                   n.name AS name,
                   labels(n) AS labels,
                   properties(n) AS properties
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(cypher, node_id=node_id)
                record = result.single()
                
                if not record:
                    return None
                
                return {
                    'id': record['id'],
                    'name': record['name'],
                    'labels': record['labels'],
                    'properties': record['properties']
                }
                
        except Exception as e:
            logger.error(f"Failed to get node details for '{node_id}': {e}")
            return None
    
    def count_relationships(self, node_id: str) -> int:
        """
        Count number of relationships for a node
        
        Args:
            node_id: Node ID
        
        Returns:
            Number of relationships
        """
        cypher = """
            MATCH (n {id: $node_id})-[r]-()
            RETURN count(r) AS rel_count
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(cypher, node_id=node_id)
                record = result.single()
                
                if record:
                    return record['rel_count']
                
        except Exception as e:
            logger.error(f"Failed to count relationships for '{node_id}': {e}")
        
        return 0
