"""
Relationship Mapper - Build human-readable relationship explanations

Maps graph paths to explanations of why results are relevant.
"""

import logging
from typing import List, Dict, Any, Optional

from .config import RELATIONSHIP_TYPES
from .utils import build_path_string, parse_neo4j_node, parse_neo4j_relationship

logger = logging.getLogger('graph_context.relationship_mapper')


class RelationshipMapper:
    """
    Map graph relationships to human-readable explanations
    
    Builds explanations like:
    - "Akiko Tanaka MADE_DECISION on this case"
    - "This decision INVOLVES_COMPANY Acme Corp"
    """
    
    def __init__(self):
        """Initialize relationship mapper"""
        self.rel_types = RELATIONSHIP_TYPES
    
    def explain_path(
        self,
        path_data: Optional[Dict],
        source_name: str = None
    ) -> str:
        """
        Build explanation from graph path
        
        Args:
            path_data: Path dictionary from GraphTraversal.find_shortest_path()
            source_name: Name of source entity for context
        
        Returns:
            Human-readable explanation
            
        Examples:
            "Akiko Tanaka MADE_DECISION (distance: 1 hop)"
            "Related to Acme Corp via decision (distance: 2 hops)"
        """
        if not path_data:
            return "No relationship found"
        
        distance = path_data.get('distance', 0)
        nodes = path_data.get('nodes', [])
        rels = path_data.get('relationships', [])
        
        if distance == 0:
            return "Same entity"
        
        if distance == 1:
            # Direct relationship
            return self._explain_direct_relationship(nodes, rels, source_name)
        else:
            # Multi-hop relationship
            return self._explain_multi_hop(nodes, rels, distance, source_name)
    
    def _explain_direct_relationship(
        self,
        nodes: List[Dict],
        rels: List[Dict],
        source_name: str = None
    ) -> str:
        """
        Explain direct (1-hop) relationship
        
        Args:
            nodes: List of node dictionaries
            rels: List of relationship dictionaries
            source_name: Source entity name
        
        Returns:
            Explanation like "Akiko Tanaka MADE_DECISION on this case"
        """
        if len(nodes) < 2 or len(rels) < 1:
            return "Direct relationship"
        
        source_node = nodes[0]
        target_node = nodes[1]
        relationship = rels[0]
        
        # Get names
        source = source_name or source_node.get('name', 'Entity')
        rel_type = relationship.get('type', 'RELATED_TO')
        
        # Get human-readable relationship description
        rel_desc = self.rel_types.get(rel_type, rel_type.lower().replace('_', ' '))
        
        # Build explanation
        explanation = f"{source} {rel_desc}"
        
        # Add target context if available
        target_type = target_node.get('labels', [])
        if target_type:
            explanation += f" (direct {target_type[0].lower()} relationship)"
        
        return explanation
    
    def _explain_multi_hop(
        self,
        nodes: List[Dict],
        rels: List[Dict],
        distance: int,
        source_name: str = None
    ) -> str:
        """
        Explain multi-hop relationship
        
        Args:
            nodes: List of node dictionaries
            rels: List of relationship dictionaries
            distance: Path length
            source_name: Source entity name
        
        Returns:
            Explanation like "Related to Akiko via 2 entities"
        """
        if len(nodes) < 2:
            return f"Related (distance: {distance} hops)"
        
        source_node = nodes[0]
        target_node = nodes[-1]
        
        source = source_name or source_node.get('name', 'entity')
        
        # Build simplified multi-hop explanation
        intermediate_count = len(nodes) - 2
        
        if intermediate_count == 1:
            # Mention intermediate entity
            intermediate = nodes[1].get('name', 'an entity')
            explanation = f"Related to {source} via {intermediate}"
        else:
            explanation = f"Related to {source} via {intermediate_count} entities"
        
        # Add distance context
        explanation += f" (distance: {distance} hops)"
        
        return explanation
    
    def explain_relationship_type(self, rel_type: str) -> str:
        """
        Get human-readable description of relationship type
        
        Args:
            rel_type: Relationship type (e.g., "MADE_DECISION")
        
        Returns:
            Human-readable description (e.g., "made decision")
        """
        return self.rel_types.get(rel_type, rel_type.lower().replace('_', ' '))
    
    def build_context_summary(
        self,
        entities: List[Dict],
        candidate_count: int,
        relationships: List[Dict]
    ) -> str:
        """
        Build context discovery summary
        
        Args:
            entities: Extracted entities
            candidate_count: Number of candidate documents found
            relationships: List of relationships
        
        Returns:
            Summary like "Found 15 decisions related to Akiko Tanaka and Acme Corp"
        """
        if not entities or candidate_count == 0:
            return "No graph context available"
        
        # Build entity list
        entity_names = []
        for entity in entities:
            name = entity.get('matched_name', entity.get('text', 'entity'))
            entity_names.append(name)
        
        # Format entity list
        if len(entity_names) == 1:
            entity_str = entity_names[0]
        elif len(entity_names) == 2:
            entity_str = f"{entity_names[0]} and {entity_names[1]}"
        else:
            entity_str = ", ".join(entity_names[:-1]) + f", and {entity_names[-1]}"
        
        # Determine document type
        doc_type = "documents"
        if relationships:
            # Infer type from relationships
            first_rel = relationships[0]
            target = first_rel.get('target', '')
            if 'DC_' in target or 'decision' in target.lower():
                doc_type = "decisions"
            elif 'POLICY' in target:
                doc_type = "policies"
        
        # Build summary
        summary = f"Found {candidate_count} {doc_type} related to {entity_str}"
        
        return summary
    
    def format_relationship_list(self, relationships: List[Dict], limit: int = 5) -> str:
        """
        Format list of relationships for display
        
        Args:
            relationships: List of relationship dictionaries
            limit: Maximum relationships to show
        
        Returns:
            Formatted string with relationship list
        """
        if not relationships:
            return "No relationships"
        
        lines = []
        for i, rel in enumerate(relationships[:limit]):
            source = rel.get('source', 'Unknown')
            target = rel.get('target', 'Unknown')
            distance = rel.get('distance', '?')
            score = rel.get('score', 0.0)
            
            line = f"  {i+1}. {source} → {target} (distance: {distance}, score: {score:.2f})"
            lines.append(line)
        
        if len(relationships) > limit:
            lines.append(f"  ... and {len(relationships) - limit} more")
        
        return "\n".join(lines)
