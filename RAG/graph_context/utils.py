"""
Utility functions for graph context provider

Helper functions for text processing, similarity matching, and data transformation.
"""

import re
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher


def normalize_text(text: str) -> str:
    """
    Normalize text for entity matching
    
    Args:
        text: Input text
        
    Returns:
        Normalized text (lowercase, stripped, no extra spaces)
    """
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Strip leading/trailing spaces
    text = text.strip()
    
    return text


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate string similarity using SequenceMatcher
    
    Args:
        text1: First string
        text2: Second string
        
    Returns:
        Similarity score (0.0 to 1.0)
    """
    if not text1 or not text2:
        return 0.0
    
    # Normalize texts
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    
    # Calculate similarity
    similarity = SequenceMatcher(None, norm1, norm2).ratio()
    
    return similarity


def extract_capitalized_phrases(text: str, max_words: int = 3) -> List[str]:
    """
    Extract capitalized words and phrases from text
    
    Args:
        text: Input text
        max_words: Maximum words per phrase
        
    Returns:
        List of capitalized phrases
    """
    phrases = []
    words = text.split()
    
    i = 0
    while i < len(words):
        word = words[i]
        
        # Skip if first word in sentence (likely not a name)
        if i > 0 and word[0].isupper():
            # Collect consecutive capitalized words
            phrase_words = [word]
            j = i + 1
            
            while j < len(words) and j < i + max_words:
                next_word = words[j]
                if next_word[0].isupper():
                    phrase_words.append(next_word)
                    j += 1
                else:
                    break
            
            # Add phrase if meaningful
            phrase = ' '.join(phrase_words)
            if len(phrase) > 2:  # Avoid single letters
                phrases.append(phrase)
            
            i = j
        else:
            i += 1
    
    return list(set(phrases))  # Remove duplicates


def is_company_name(text: str, keywords: List[str]) -> bool:
    """
    Check if text likely represents a company name
    
    Args:
        text: Text to check
        keywords: List of company keywords (Corp, Inc, etc.)
        
    Returns:
        True if likely a company name
    """
    if not text:
        return False
    
    # Check for company keywords
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            return True
    
    return False


def is_person_name(text: str, title_keywords: List[str]) -> bool:
    """
    Check if text likely represents a person name
    
    Args:
        text: Text to check
        title_keywords: List of title keywords (CEO, Director, etc.)
        
    Returns:
        True if likely a person name
    """
    if not text:
        return False
    
    # Check for title keywords
    text_upper = text.upper()
    for keyword in title_keywords:
        if keyword.upper() in text_upper:
            return True
    
    # Check if it looks like a name (2-3 capitalized words)
    words = text.split()
    if 1 <= len(words) <= 3:
        if all(w[0].isupper() for w in words if w):
            return True
    
    return False


def fuzzy_match(
    query: str, 
    candidates: List[Dict], 
    key: str = 'name',
    threshold: float = 0.7
) -> Optional[Dict]:
    """
    Fuzzy match query string to list of candidates
    
    Args:
        query: Search string
        candidates: List of candidate dictionaries
        key: Dictionary key to match against
        threshold: Minimum similarity threshold
        
    Returns:
        Best matching candidate or None
    """
    if not query or not candidates:
        return None
    
    best_match = None
    best_score = 0.0
    
    for candidate in candidates:
        candidate_text = candidate.get(key, '')
        if not candidate_text:
            continue
        
        # Calculate similarity
        score = calculate_similarity(query, candidate_text)
        
        if score >= threshold and score > best_score:
            best_score = score
            best_match = candidate.copy()
            best_match['match_score'] = score
    
    return best_match


def build_path_string(nodes: List[Dict], relationships: List[Dict]) -> str:
    """
    Build human-readable path string from graph path
    
    Args:
        nodes: List of node dictionaries
        relationships: List of relationship dictionaries
        
    Returns:
        Path string like "Akiko → MADE_DECISION → DC_001"
    """
    if not nodes:
        return "Empty path"
    
    path_parts = []
    
    for i, node in enumerate(nodes):
        # Add node name or ID
        node_label = node.get('name', node.get('id', f"Node{i}"))
        path_parts.append(node_label)
        
        # Add relationship if not last node
        if i < len(relationships):
            rel = relationships[i]
            rel_type = rel.get('type', 'RELATED_TO')
            path_parts.append(f"→ {rel_type} →")
    
    return ' '.join(path_parts)


def parse_neo4j_node(node_data: Any) -> Dict:
    """
    Parse Neo4j node object to dictionary
    
    Args:
        node_data: Neo4j node object
        
    Returns:
        Dictionary with node properties
    """
    if hasattr(node_data, '__dict__'):
        # Neo4j Node object
        return {
            'id': node_data.get('id', ''),
            'name': node_data.get('name', ''),
            'labels': list(node_data.labels) if hasattr(node_data, 'labels') else [],
            'properties': dict(node_data)
        }
    elif isinstance(node_data, dict):
        # Already a dictionary
        return node_data
    else:
        return {}


def parse_neo4j_relationship(rel_data: Any) -> Dict:
    """
    Parse Neo4j relationship object to dictionary
    
    Args:
        rel_data: Neo4j relationship object
        
    Returns:
        Dictionary with relationship properties
    """
    if hasattr(rel_data, 'type'):
        # Neo4j Relationship object
        return {
            'type': rel_data.type,
            'properties': dict(rel_data) if hasattr(rel_data, '__iter__') else {}
        }
    elif isinstance(rel_data, dict):
        return rel_data
    else:
        return {'type': 'UNKNOWN'}


def calculate_graph_score(distance: int, max_distance: int = 5) -> float:
    """
    Calculate graph proximity score from distance
    
    Args:
        distance: Graph distance (number of hops)
        max_distance: Maximum distance to consider
        
    Returns:
        Score from 0.0 to 1.0 (closer = higher score)
    """
    if distance <= 0:
        return 1.0
    
    if distance >= max_distance:
        return 0.1  # Minimum score for far nodes
    
    # Inverse distance scoring
    score = 1.0 / distance
    
    return score


def combine_scores(
    vector_score: float,
    graph_score: float,
    vector_weight: float = 0.6,
    graph_weight: float = 0.4
) -> float:
    """
    Combine vector and graph scores into hybrid score
    
    Args:
        vector_score: Vector similarity score (0.0 to 1.0)
        graph_score: Graph proximity score (0.0 to 1.0)
        vector_weight: Weight for vector score (default: 0.6)
        graph_weight: Weight for graph score (default: 0.4)
        
    Returns:
        Hybrid score (0.0 to 1.0)
    """
    # Normalize weights
    total_weight = vector_weight + graph_weight
    if total_weight == 0:
        return 0.0
    
    norm_vector_weight = vector_weight / total_weight
    norm_graph_weight = graph_weight / total_weight
    
    # Calculate weighted sum
    hybrid_score = (
        norm_vector_weight * vector_score +
        norm_graph_weight * graph_score
    )
    
    return hybrid_score


def format_entity_list(entities: List[Dict]) -> str:
    """
    Format entity list for logging/display
    
    Args:
        entities: List of entity dictionaries
        
    Returns:
        Formatted string like "Akiko (Person), Acme Corp (Company)"
    """
    if not entities:
        return "No entities"
    
    formatted = []
    for entity in entities:
        name = entity.get('matched_name', entity.get('text', 'Unknown'))
        entity_type = entity.get('type', 'Unknown')
        formatted.append(f"{name} ({entity_type})")
    
    return ', '.join(formatted)
