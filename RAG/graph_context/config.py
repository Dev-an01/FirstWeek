"""
Configuration for Graph Context Provider

Reuses configurations from Blueprint #1 and adds graph-specific settings.
"""

import sys
import os

# Import configurations from Phase 1
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from embedding_generation.config import NEO4J_CONFIG

# ============================================================================
# GRAPH CONTEXT CONFIGURATION
# ============================================================================

GRAPH_CONTEXT_CONFIG = {
    # Entity extraction
    'entity_confidence_threshold': 0.6,  # Minimum confidence for entity matching
    'max_entity_extractions': 10,  # Max entities to extract per query
    
    # Graph traversal
    'max_traversal_hops': 3,  # Maximum depth for graph traversal
    'max_candidates': 50,  # Maximum candidate documents to return
    'default_top_k': 20,  # Default number of candidates if not specified
    
    # Scoring
    'vector_weight': 0.6,  # Weight for vector similarity in hybrid scoring
    'graph_weight': 0.4,  # Weight for graph proximity in hybrid scoring
    
    # Performance
    'cache_enabled': True,  # Cache graph traversal results
    'query_timeout_ms': 5000,  # Timeout for Neo4j queries (5 seconds)
    
    # RBAC
    'default_scopes': ['public'],  # Default confidentiality scopes if not provided
}

# ============================================================================
# ENTITY EXTRACTION MODELS
# ============================================================================

MODEL_CONFIG = {
    # GLiNER settings (Primary)
    'use_gliner': True,
    'gliner_model_path': '/app/models/gliner',  # Local path in Docker
    'gliner_labels': [
        "Person", "Company", "Organization", "Location", 
        "Product", "Date", "Money", "Percent", "Policy", "Decision"
    ],
    'gliner_threshold': 0.3,  # Zero-shot threshold
    
    # spaCy settings (Fallback)
    'use_spacy': True,
    'spacy_model': "en_core_web_lg",
}

# ============================================================================
# ENTITY EXTRACTION PATTERNS
# ============================================================================

ENTITY_PATTERNS = {
    # Company indicators
    'company_keywords': [
        'Corp', 'Inc', 'Ltd', 'Company', 'LLC', 'Corporation',
        'Incorporated', 'Limited', 'Solutions', 'Technologies',
        'Systems', 'Enterprises', 'Group'
    ],
    
    # Person title indicators
    'person_titles': [
        'CEO', 'CFO', 'CTO', 'CMO', 'COO', 'CIO', 'CISO',
        'VP', 'Vice President', 'President',
        'Director', 'Manager', 'Lead', 'Head',
        'Executive', 'Officer', 'Chief'
    ],
    
    # Policy/document patterns
    'policy_patterns': [
        'POLICY-', 'policy on', 'guidelines for', 'procedure for',
        'regulation', 'standard', 'protocol'
    ],
    
    # Decision/project patterns
    'decision_patterns': [
        'decision', 'approval', 'case', 'project', 'initiative',
        'deal', 'contract', 'agreement'
    ]
}

# ============================================================================
# ENTITY TYPE MAPPING
# ============================================================================

ENTITY_TYPE_MAPPING = {
    # Neo4j node labels
    'person': 'Executive',
    'executive': 'Executive',
    'company': 'Company',
    'client': 'Company',
    'partner': 'Company',
    'decision': 'Decision',
    'policy': 'Policy',
    'project': 'Project',
    'department': 'Department',
    'product': 'Product'
}

# ============================================================================
# GRAPH RELATIONSHIP TYPES
# ============================================================================

RELATIONSHIP_TYPES = {
    # Executive relationships
    'MADE_DECISION': 'made decision',
    'APPROVED_POLICY': 'approved policy',
    'WORKED_ON': 'worked on',
    'MANAGES': 'manages',
    'REPORTS_TO': 'reports to',
    
    # Entity relationships
    'INVOLVES_COMPANY': 'involves company',
    'RELATED_TO_PROJECT': 'related to project',
    'AFFECTS_DEPARTMENT': 'affects department',
    'CONCERNS_PRODUCT': 'concerns product',
    
    # Document relationships
    'REFERENCES': 'references',
    'SUPERSEDES': 'supersedes',
    'DEPENDS_ON': 'depends on'
}

# ============================================================================
# FUZZY MATCHING THRESHOLDS
# ============================================================================

FUZZY_MATCH_CONFIG = {
    'min_similarity': 0.7,  # Minimum string similarity for fuzzy matching
    'max_candidates': 5,  # Max candidates to return per entity match
    'case_sensitive': False,  # Case-insensitive matching
    'use_partial_match': True  # Allow partial string matches
}

# ============================================================================
# CYPHER QUERY TEMPLATES
# ============================================================================

CYPHER_TEMPLATES = {
    # Find nodes by name/ID
    'find_node_by_name': """
        MATCH (n)
        WHERE toLower(n.name) CONTAINS toLower($name)
           OR n.id CONTAINS $name
        RETURN n.id AS node_id, 
               n.name AS node_name, 
               labels(n) AS node_labels
        LIMIT $limit
    """,
    
    # Find related documents
    'find_related_documents': """
        MATCH (anchor {id: $anchor_id})
        MATCH path = (anchor)-[*1..$max_hops]-(doc)
        WHERE (doc:Decision OR doc:Policy)
          AND (doc.confidentiality IS NULL OR doc.confidentiality IN $allowed_scopes)
        WITH DISTINCT doc, 
             length(shortestPath((anchor)-[*]-(doc))) AS distance
        RETURN doc.id AS doc_id,
               distance,
               labels(doc) AS doc_type
        ORDER BY distance ASC
        LIMIT $max_candidates
    """,
    
    # Find shortest path
    'shortest_path': """
        MATCH (source {id: $source_id}),
              (target {id: $target_id}),
              path = shortestPath((source)-[*]-(target))
        RETURN nodes(path) AS nodes,
               relationships(path) AS rels,
               length(path) AS distance
    """
}

# Export Neo4j config for convenience
__all__ = [
    'NEO4J_CONFIG',
    'GRAPH_CONTEXT_CONFIG',
    'ENTITY_PATTERNS',
    'ENTITY_TYPE_MAPPING',
    'RELATIONSHIP_TYPES',
    'FUZZY_MATCH_CONFIG',
    'CYPHER_TEMPLATES'
]
