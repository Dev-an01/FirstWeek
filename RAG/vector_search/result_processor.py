"""
Result Processor

Enriches search results with metadata and creates citation snippets.
"""

import re
from typing import List, Dict, Any, Optional
import logging

from .config import VECTOR_SEARCH_CONFIG

logger = logging.getLogger('vector_search.result_processor')


class ResultProcessor:
    """
    Processes and enriches search results.
    
    Responsibilities:
    - Merge vector search results with source metadata
    - Generate citation snippets
    - Score normalization and ranking
    - Result formatting
    """
    
    def __init__(self):
        """Initialize result processor."""
        self.max_citation_length = VECTOR_SEARCH_CONFIG['max_citation_length']
        self.include_metadata = VECTOR_SEARCH_CONFIG['include_metadata']
        self.include_citations = VECTOR_SEARCH_CONFIG['include_citations']
        logger.info("ResultProcessor initialized")
    
    def process(
        self,
        search_results: List[Dict[str, Any]],
        metadata_dict: Dict[str, Dict[str, Any]],
        include_metadata: Optional[bool] = None,
        include_citations: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process search results by enriching with metadata.
        
        Args:
            search_results: Raw results from vector search
            metadata_dict: Metadata keyed by source_id
            include_metadata: Whether to include full metadata
            include_citations: Whether to include citation snippets
        
        Returns:
            List of enriched results
        """
        include_meta = include_metadata if include_metadata is not None else self.include_metadata
        include_cite = include_citations if include_citations is not None else self.include_citations
        
        enriched_results = []
        
        for idx, result in enumerate(search_results):
            source_id = result['source_id']
            source_type = result['source_type']
            score = float(result['similarity_score'])
            
            # Get metadata
            metadata = metadata_dict.get(source_id, {})
            
            # Build enriched result
            enriched = {
                'rank': idx + 1,
                'source_id': source_id,
                'source_type': source_type,
                'similarity_score': round(score, 4),
                'title': self._extract_title(metadata, source_type, source_id),
                'content': result.get('text_content') or result.get('content'),  # Include content from database query
            }
            
            # Add metadata if requested
            if include_meta and metadata:
                enriched['metadata'] = self._format_metadata(metadata, source_type)
            
            # Add citation if requested
            if include_cite and metadata:
                enriched['citation'] = self._generate_citation(metadata, source_type)
            
            enriched_results.append(enriched)
        
        logger.debug(f"Processed {len(enriched_results)} results")
        return enriched_results
    
    def _extract_title(self, metadata: Dict[str, Any], source_type: str, source_id: str = None) -> str:
        """
        Extract a human-readable title from metadata.

        Tries multiple strategies:
        1. Use title/name if meaningful (not generic)
        2. Extract from source_id/document_id if title is generic
        3. Fallback to "Unknown"

        Args:
            metadata: Source metadata
            source_type: Type of source
            source_id: Optional source_id for extracting title from document ID

        Returns:
            Title string
        """
        if not metadata:
            return "Unknown"

        # Source-specific title fields
        title_fields = {
            'decision_case': 'title',
            'policy': 'name',
            'executive_profile': 'name',
        }

        title_field = title_fields.get(source_type)
        if title_field and title_field in metadata:
            title = metadata[title_field]
            # Check if title is meaningful (not generic)
            if title and title.lower() not in ('document', 'unknown', 'untitled', ''):
                return title

        # Try standard title/name fields
        title = metadata.get('title', '') or metadata.get('name', '')
        if title and title.lower() not in ('document', 'unknown', 'untitled', ''):
            return title

        # Extract from source_id if title is generic
        doc_id = source_id or metadata.get('document_id', '') or metadata.get('id', '')
        if doc_id:
            extracted = self._extract_title_from_id(doc_id)
            if extracted:
                return extracted

        return metadata.get('title', metadata.get('name', 'Unknown'))

    def _extract_title_from_id(self, doc_id: str) -> str:
        """
        Extract human-readable title from document ID.

        Examples:
        - "document:doc_2024-10-20_marketing_performance_q3" → "Marketing Performance Q3"
        - "chunk_doc_security_incident_response_2024_0" → "Security Incident Response"

        Args:
            doc_id: Document ID string

        Returns:
            Extracted title or empty string
        """
        if not doc_id:
            return ""

        # Remove common prefixes
        clean_id = doc_id
        prefixes_to_remove = ['document:', 'doc_', 'chunk_', 'document_', 'file_']
        for prefix in prefixes_to_remove:
            clean_id = clean_id.replace(prefix, '')

        # Split on underscore (after replacing hyphens in date-like parts)
        parts = clean_id.replace('-', '_').split('_')

        # Filter out dates, numeric indices, and common prefixes
        meaningful_parts = []
        for p in parts:
            p_lower = p.lower()
            # Skip common prefixes
            if p_lower in ['doc', 'chunk', 'document', 'file']:
                continue
            # Skip year patterns (2024, 2023, etc.)
            if p_lower.startswith('20') and len(p) == 4 and p.isdigit():
                continue
            # Skip month-day patterns (10, 20, etc.)
            if p.isdigit() and len(p) <= 2:
                continue
            # Skip chunk indices at the end
            if p.isdigit():
                continue
            meaningful_parts.append(p)

        if meaningful_parts:
            # Capitalize each word nicely
            return ' '.join(word.capitalize() for word in meaningful_parts)

        return ""
    
    def _format_metadata(
        self,
        metadata: Dict[str, Any],
        source_type: str
    ) -> Dict[str, Any]:
        """
        Format metadata for output (remove internal fields, convert types).
        
        Args:
            metadata: Raw metadata from database
            source_type: Type of source
        
        Returns:
            Formatted metadata
        """
        # Fields to exclude from output
        exclude_fields = {'embedding', 'created_at', 'updated_at'}
        
        formatted = {}
        for key, value in metadata.items():
            if key not in exclude_fields:
                # Convert to JSON-serializable types
                if hasattr(value, 'isoformat'):  # datetime
                    formatted[key] = value.isoformat()
                else:
                    formatted[key] = value
        
        return formatted
    
    def _generate_citation(
        self,
        metadata: Dict[str, Any],
        source_type: str
    ) -> str:
        """
        Generate a citation snippet from metadata.
        
        Args:
            metadata: Source metadata
            source_type: Type of source
        
        Returns:
            Citation text (truncated to max length)
        """
        # Source-specific citation generation
        if source_type == 'decision_case':
            return self._cite_decision(metadata)
        elif source_type == 'policy_document':
            return self._cite_policy(metadata)
        elif source_type == 'executive_profile':
            return self._cite_profile(metadata)
        else:
            return "No citation available"
    
    def _cite_decision(self, metadata: Dict[str, Any]) -> str:
        """Generate citation for a decision case."""
        parts = []
        
        # Title
        if 'title' in metadata:
            parts.append(metadata['title'])
        
        # Situation or context
        if 'situation' in metadata:
            parts.append(metadata['situation'])
        
        # Decision made
        if 'decision_made' in metadata:
            parts.append(f"Decision: {metadata['decision_made']}")
        
        citation = ' - '.join(parts)
        return self._truncate(citation)
    
    def _cite_policy(self, metadata: Dict[str, Any]) -> str:
        """Generate citation for a policy document."""
        parts = []
        
        # Policy name
        if 'name' in metadata:
            parts.append(metadata['name'])
        
        # Version
        if 'version' in metadata:
            parts.append(f"v{metadata['version']}")
        
        # Extract first paragraph from content
        if 'content_markdown' in metadata:
            content = metadata['content_markdown']
            # Get first sentence or paragraph
            first_para = content.split('\n\n')[0] if '\n\n' in content else content.split('\n')[0]
            parts.append(first_para)
        
        citation = ' - '.join(parts)
        return self._truncate(citation)
    
    def _cite_profile(self, metadata: Dict[str, Any]) -> str:
        """Generate citation for an executive profile."""
        parts = []
        
        # Name and title
        if 'name' in metadata:
            parts.append(metadata['name'])
        if 'title' in metadata:
            parts.append(metadata['title'])
        
        # Profile data (JSON field)
        if 'profile_data' in metadata:
            import json
            try:
                profile_json = metadata['profile_data']
                if isinstance(profile_json, str):
                    profile = json.loads(profile_json)
                else:
                    profile = profile_json
                
                # Extract background summary
                if 'background_summary' in profile:
                    parts.append(profile['background_summary'])
                elif 'decision_making_style' in profile:
                    parts.append(f"Style: {profile['decision_making_style']}")
            except:
                pass
        
        citation = ' - '.join(parts)
        return self._truncate(citation)
    
    def _truncate(self, text: str) -> str:
        """
        Truncate text to maximum citation length.
        
        Args:
            text: Text to truncate
        
        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= self.max_citation_length:
            return text
        
        # Truncate at word boundary
        truncated = text[:self.max_citation_length]
        
        # Find last space
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]
        
        return truncated + '...'
    
    def deduplicate(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate results (same source_id).
        
        Args:
            results: List of results
        
        Returns:
            Deduplicated list (keeps highest scoring result per source)
        """
        seen = set()
        deduped = []
        
        for result in results:
            source_id = result['source_id']
            if source_id not in seen:
                seen.add(source_id)
                deduped.append(result)
        
        logger.debug(f"Deduplicated: {len(results)} → {len(deduped)} results")
        return deduped
