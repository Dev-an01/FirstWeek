"""
Query Processor

Validates and preprocesses queries before vector search.
Extracts parameters and normalizes input.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
import logging

from .config import (
    VECTOR_SEARCH_CONFIG,
    SOURCE_TYPE_MAPPING,
    VALID_SOURCE_TYPES
)

logger = logging.getLogger('vector_search.query_processor')


class QueryProcessor:
    """
    Validates and preprocesses search queries.
    
    Responsibilities:
    - Query validation (length, content)
    - Parameter extraction and normalization
    - Source type mapping
    - Query cleaning and normalization
    """
    
    def __init__(self):
        """Initialize query processor."""
        self.max_length = VECTOR_SEARCH_CONFIG['max_query_length']
        logger.info("QueryProcessor initialized")
    
    def process(
        self,
        query: str,
        source_types: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process and validate query parameters.
        
        Args:
            query: Natural language query
            source_types: Optional filter by source types
            top_k: Maximum results to return
            min_score: Minimum similarity score threshold
            role: User role for RBAC filtering
        
        Returns:
            Processed query parameters
        
        Raises:
            ValueError: If query is invalid
        """
        # Validate query
        validated_query = self._validate_query(query)
        
        # Normalize source types
        normalized_types = self._normalize_source_types(source_types)
        
        # Apply defaults
        final_top_k = top_k if top_k is not None else VECTOR_SEARCH_CONFIG['top_k_default']
        
        # Smart threshold adjustment based on query type
        if min_score is None:
            # Auto-adjust threshold for person name queries
            final_min_score = self._determine_optimal_threshold(validated_query)
        else:
            final_min_score = min_score
        
        final_role = role or 'employee'  # Default role
        
        # Validate parameters
        self._validate_parameters(final_top_k, final_min_score)
        
        result = {
            'query': validated_query,
            'source_types': normalized_types,
            'top_k': final_top_k,
            'min_score': final_min_score,
            'role': final_role,
            'original_query': query,  # Keep original for logging
            'threshold_adjusted': min_score is None and final_min_score != VECTOR_SEARCH_CONFIG['min_score_default'],
        }
        
        if result['threshold_adjusted']:
            logger.info(f"Auto-adjusted threshold: {VECTOR_SEARCH_CONFIG['min_score_default']:.2f} → {final_min_score:.2f}")
        
        logger.debug(f"Processed query: types={normalized_types}, k={final_top_k}, "
                    f"score={final_min_score}, role={final_role}")
        
        return result
    
    def _validate_query(self, query: str) -> str:
        """
        Validate and clean query text.
        
        Args:
            query: Raw query text
        
        Returns:
            Cleaned query text
        
        Raises:
            ValueError: If query is invalid
        """
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        
        # Strip whitespace
        query = query.strip()
        
        # Check length
        if len(query) == 0:
            raise ValueError("Query cannot be empty")
        
        if len(query) > self.max_length:
            raise ValueError(
                f"Query too long ({len(query)} chars). "
                f"Maximum is {self.max_length} characters."
            )
        
        # Clean query (remove excessive whitespace)
        query = re.sub(r'\s+', ' ', query)
        
        return query
    
    def _normalize_source_types(
        self,
        source_types: Optional[List[str]]
    ) -> List[str]:
        """
        Normalize source types using mapping.
        
        Args:
            source_types: User-provided source types (can use friendly names)
        
        Returns:
            List of valid database source types
        
        Raises:
            ValueError: If source type is invalid
        """
        if not source_types:
            # Default to all types
            return VALID_SOURCE_TYPES.copy()
        
        normalized = []
        for source_type in source_types:
            source_type_lower = source_type.lower()
            
            # Try mapping first
            if source_type_lower in SOURCE_TYPE_MAPPING:
                mapped_type = SOURCE_TYPE_MAPPING[source_type_lower]
                if mapped_type not in normalized:
                    normalized.append(mapped_type)
            # Then check if it's already a valid type
            elif source_type_lower in VALID_SOURCE_TYPES:
                if source_type_lower not in normalized:
                    normalized.append(source_type_lower)
            else:
                raise ValueError(
                    f"Invalid source type: '{source_type}'. "
                    f"Valid types: {list(SOURCE_TYPE_MAPPING.keys())} or {VALID_SOURCE_TYPES}"
                )
        
        return normalized
    
    def _validate_parameters(self, top_k: int, min_score: float):
        """
        Validate search parameters.
        
        Args:
            top_k: Number of results
            min_score: Minimum similarity score
        
        Raises:
            ValueError: If parameters are invalid
        """
        # Validate top_k
        if not isinstance(top_k, int):
            raise ValueError(f"top_k must be an integer, got {type(top_k)}")
        
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        
        if top_k > 100:
            raise ValueError(f"top_k too large ({top_k}). Maximum is 100.")
        
        # Validate min_score
        if not isinstance(min_score, (int, float)):
            raise ValueError(f"min_score must be a number, got {type(min_score)}")
        
        if not 0.0 <= min_score <= 1.0:
            raise ValueError(f"min_score must be between 0.0 and 1.0, got {min_score}")
    
    def _determine_optimal_threshold(self, query: str) -> float:
        """
        Determine optimal similarity threshold based on query characteristics.
        
        Uses heuristics to detect query type and adjust threshold:
        - Person name queries (e.g., "Sarah Kim") → Lower threshold (0.25)
        - Short queries (<5 words) → Slightly lower threshold (0.35)
        - General questions → Default threshold (0.4)
        
        Args:
            query: Processed query text
        
        Returns:
            Optimal similarity score threshold (0.0 - 1.0)
        """
        default_threshold = VECTOR_SEARCH_CONFIG['min_score_default']
        
        # Check for person name patterns
        # Common patterns: "Tell me about X", "Who is X", "X's profile", etc.
        person_indicators = [
            r'\b(tell me about|who is|about|profile of)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',  # "tell me about Sarah Kim"
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+profile|\s+bio|\s+background)?',  # "Sarah Kim profile"
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\'s\b',  # "Sarah Kim's"
        ]
        
        for pattern in person_indicators:
            if re.search(pattern, query):
                logger.debug(f"Detected person name query pattern: {pattern}")
                return 0.25  # Lower threshold for name queries
        
        # Check for capitalized names (2+ consecutive capitalized words)
        # This catches "Sarah Kim" even without context words
        if re.search(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', query):
            word_count = len(query.split())
            # If the query is mostly just a name (< 5 words total), lower threshold
            if word_count <= 5:
                logger.debug("Detected likely person name in short query")
                return 0.28  # Slightly higher than full person query
        
        # Short queries tend to be less semantically rich
        word_count = len(query.split())
        if word_count <= 4:
            logger.debug(f"Short query ({word_count} words), lowering threshold")
            return 0.35
        
        # Default threshold for general queries
        return default_threshold
    
    def extract_filters(self, query: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract inline filters from query text.
        
        Example: "discount policy type:policy" → ("discount policy", {"type": "policy"})
        
        Args:
            query: Query with potential inline filters
        
        Returns:
            Tuple of (cleaned_query, filters_dict)
        """
        filters = {}
        
        # Pattern: key:value
        pattern = r'\b(\w+):(\S+)'
        matches = re.findall(pattern, query)
        
        for key, value in matches:
            filters[key.lower()] = value
        
        # Remove filter syntax from query
        cleaned_query = re.sub(pattern, '', query)
        cleaned_query = re.sub(r'\s+', ' ', cleaned_query).strip()
        
        return cleaned_query, filters
