"""
Advanced Response Formatter with Citation Handling
==============================================

Enhanced response formatting system according to Solution Manual specifications:

Features:
- Citation extraction and validation
- Multiple citation styles (inline, footnote, none)
- Source attribution with confidence scores
- Structured response formatting with metadata
- Citation accuracy verification
- Source confidence scoring

Author: AI Officer Implementation Team
Date: 2025-10-30
"""

import re
import json
import time
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class CitationStyle(Enum):
    """Supported citation styles"""
    INLINE = "inline"
    FOOTNOTE = "footnote"
    NONE = "none"


class SourceType(Enum):
    """Supported source types"""
    DECISION_CASE = "decision_case"
    POLICY = "policy"
    EXECUTIVE_PROFILE = "executive_profile"
    MEMORY = "memory"
    GRAPH = "graph"


@dataclass
class Citation:
    """Enhanced citation with validation and confidence"""
    source: str
    source_id: str
    source_type: SourceType
    raw_text: str
    position: int
    context: str
    confidence: float = 0.0
    is_valid: bool = False
    validation_details: Dict[str, Any] = None
    snippet: str = ""
    relevance_score: float = 0.0
    
    def __post_init__(self):
        if self.validation_details is None:
            self.validation_details = {}


@dataclass
class SourceAttribution:
    """Source attribution with confidence scoring"""
    source_id: str
    source_type: SourceType
    title: str
    confidence: float
    relevance_score: float
    citation_count: int = 0
    first_citation_pos: int = -1
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class FormattedResponse:
    """Enhanced formatted response with comprehensive metadata"""
    content: str
    citations: List[Citation]
    sources: List[SourceAttribution]
    citation_style: CitationStyle
    metadata: Dict[str, Any]
    
    # Performance metrics
    formatting_time_ms: float = 0.0
    citation_extraction_time_ms: float = 0.0
    validation_time_ms: float = 0.0
    
    # Quality metrics
    citation_accuracy: float = 0.0
    source_diversity: float = 0.0
    citation_density: float = 0.0
    
    def __post_init__(self):
        if not isinstance(self.citation_style, CitationStyle):
            self.citation_style = CitationStyle(self.citation_style)


class AdvancedResponseFormatter:
    """
    Advanced response formatter with comprehensive citation handling
    
    Enhances the basic response formatter with:
    - Multiple citation styles
    - Citation validation and accuracy scoring
    - Source attribution with confidence
    - Structured response formatting
    - Performance metrics
    """
    
    def __init__(self, citation_style: str = "inline", 
                 enable_validation: bool = True,
                 confidence_threshold: float = 0.7):
        """
        Initialize advanced response formatter
        
        Args:
            citation_style: Citation format (inline, footnote, none)
            enable_validation: Enable citation validation
            confidence_threshold: Minimum confidence for citations
        """
        self.citation_style = CitationStyle(citation_style.lower())
        self.enable_validation = enable_validation
        self.confidence_threshold = confidence_threshold
        
        # Citation patterns (enhanced)
        self.citation_patterns = [
            r'\[Source:\s*([^\]]+)\]',           # [Source: doc_name]
            r'\[Ref:\s*([^\]]+)\]',              # [Ref: doc_name]
            r'\[Document:\s*([^\]]+)\]',          # [Document: doc_name]
            r'\[File:\s*([^\]]+)\]',              # [File: doc_name]
            r'\[([^\]]+)\]',                      # [doc_name] (fallback)
            r'\(([^)]*source[^)]*)\)',             # (source: doc_name)
            r'Source:\s*([^\n,\.]+)',             # Source: doc_name
        ]
        
        # Source type patterns
        self.source_type_patterns = {
            'decision': [r'decision', r'case', r'precedent'],
            'policy': [r'policy', r'guideline', r'rule', r'procedure'],
            'profile': [r'profile', r'executive', r'person'],
            'memory': [r'memory', r'conversation', r'chat'],
            'graph': [r'graph', r'entity', r'relationship']
        }
        
        logger.info(f"AdvancedResponseFormatter initialized (style={self.citation_style.value}, "
                   f"validation={self.enable_validation})")
    
    def format_response(
        self,
        llm_content: str,
        retrieval_context: Optional[Dict[str, Any]] = None,
        available_sources: Optional[List[Dict[str, Any]]] = None
    ) -> FormattedResponse:
        """
        Format LLM response with advanced citation handling
        
        Args:
            llm_content: Raw LLM response text
            retrieval_context: Original retrieval results for validation
            available_sources: List of available source documents
            
        Returns:
            FormattedResponse with enhanced metadata
        """
        start_time = time.time()
        
        # Step 1: Extract citations
        citation_start = time.time()
        citations = self._extract_citations(llm_content)
        citation_time = (time.time() - citation_start) * 1000
        
        # Step 2: Validate citations if enabled
        validation_start = time.time()
        if self.enable_validation and available_sources:
            citations = self._validate_citations(citations, available_sources)
        validation_time = (time.time() - validation_start) * 1000
        
        # Step 3: Create source attributions
        source_attributions = self._create_source_attributions(citations, retrieval_context)
        
        # Step 4: Format content based on citation style
        formatted_content = self._format_content(llm_content, citations)
        
        # Step 5: Calculate quality metrics
        quality_metrics = self._calculate_quality_metrics(
            formatted_content, citations, source_attributions
        )
        
        # Step 6: Build metadata
        metadata = {
            'citation_count': len(citations),
            'unique_sources': len(source_attributions),
            'citation_style': self.citation_style.value,
            'validation_enabled': self.enable_validation,
            'confidence_threshold': self.confidence_threshold,
            'retrieval_context_provided': retrieval_context is not None,
            'available_sources_count': len(available_sources) if available_sources else 0,
            **quality_metrics
        }
        
        # Step 7: Calculate performance metrics
        total_time = (time.time() - start_time) * 1000
        
        response = FormattedResponse(
            content=formatted_content,
            citations=citations,
            sources=source_attributions,
            citation_style=self.citation_style,
            metadata=metadata,
            formatting_time_ms=total_time,
            citation_extraction_time_ms=citation_time,
            validation_time_ms=validation_time,
            **quality_metrics
        )
        
        logger.debug(f"Formatted response: {len(citations)} citations, "
                    f"{len(source_attributions)} sources, {total_time:.1f}ms")
        
        return response
    
    def _extract_citations(self, text: str) -> List[Citation]:
        """
        Extract all citations from text with enhanced parsing
        
        Args:
            text: Response text
            
        Returns:
            List of Citation objects
        """
        citations = []
        
        for pattern in self.citation_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                # Extract source information
                source_text = match.group(1).strip() if match.groups() else match.group(0).strip()
                
                # Clean source text
                source_text = self._clean_source_text(source_text)
                
                # Determine source type
                source_type = self._determine_source_type(source_text)
                
                # Generate source ID
                source_id = self._generate_source_id(source_text, source_type)
                
                # Get context
                context = self._get_citation_context(text, match.start())
                
                # Create citation
                citation = Citation(
                    source=source_text,
                    source_id=source_id,
                    source_type=source_type,
                    raw_text=match.group(0),
                    position=match.start(),
                    context=context,
                    confidence=0.0,  # Will be calculated during validation
                    is_valid=False,    # Will be determined during validation
                    snippet=self._extract_snippet(text, match.start(), match.end())
                )
                
                citations.append(citation)
        
        # Sort by position and deduplicate
        citations = sorted(citations, key=lambda x: x.position)
        citations = self._deduplicate_citations(citations)
        
        return citations
    
    def _validate_citations(
        self,
        citations: List[Citation],
        available_sources: List[Dict[str, Any]]
    ) -> List[Citation]:
        """
        Validate citations against available sources
        
        Args:
            citations: List of citations to validate
            available_sources: Available source documents
            
        Returns:
            List of validated citations with confidence scores
        """
        if not available_sources:
            return citations
        
        # Create source lookup
        source_lookup = {}
        for source in available_sources:
            source_id = source.get('id', source.get('source_id', ''))
            title = source.get('title', '')
            content = source.get('content', '')
            
            source_lookup[source_id] = {
                'title': title,
                'content': content.lower(),
                'type': source.get('type', source.get('doc_type', 'unknown')),
                'metadata': source.get('metadata', {})
            }
            
            # Also add title-based lookup
            if title:
                source_lookup[title.lower()] = source_lookup[source_id]
        
        # Validate each citation
        for citation in citations:
            validation_result = self._validate_single_citation(citation, source_lookup)
            
            citation.is_valid = validation_result['is_valid']
            citation.confidence = validation_result['confidence']
            citation.validation_details = validation_result['details']
            citation.relevance_score = validation_result['relevance_score']
            
            if validation_result.get('snippet'):
                citation.snippet = validation_result['snippet']
        
        return citations
    
    def _validate_single_citation(
        self,
        citation: Citation,
        source_lookup: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate a single citation against available sources
        
        Args:
            citation: Citation to validate
            source_lookup: Lookup table of available sources
            
        Returns:
            Validation result with confidence and details
        """
        result = {
            'is_valid': False,
            'confidence': 0.0,
            'details': {},
            'relevance_score': 0.0,
            'snippet': ''
        }
        
        # Try exact match first
        source_key = citation.source.lower()
        
        if source_key in source_lookup:
            source_info = source_lookup[source_key]
            result['is_valid'] = True
            result['confidence'] = 1.0
            result['details']['match_type'] = 'exact'
            result['details']['source_type'] = source_info['type']
            result['snippet'] = source_info['content'][:200] + "..." if len(source_info['content']) > 200 else source_info['content']
            return result
        
        # Try partial match
        for source_key, source_info in source_lookup.items():
            if citation.source.lower() in source_key or source_key in citation.source.lower():
                # Calculate confidence based on match quality
                if citation.source.lower() == source_key:
                    confidence = 0.9
                    match_type = 'case_insensitive'
                elif citation.source.lower() in source_key:
                    confidence = 0.7
                    match_type = 'substring'
                else:
                    confidence = 0.6
                    match_type = 'partial'
                
                result['is_valid'] = confidence >= self.confidence_threshold
                result['confidence'] = confidence
                result['details']['match_type'] = match_type
                result['details']['source_type'] = source_info['type']
                result['details']['matched_key'] = source_key
                result['snippet'] = source_info['content'][:200] + "..." if len(source_info['content']) > 200 else source_info['content']
                
                # Calculate relevance score based on content similarity
                result['relevance_score'] = self._calculate_relevance_score(
                    citation.context, source_info['content']
                )
                
                return result
        
        # No match found
        result['details']['reason'] = 'source_not_found'
        result['details']['available_sources'] = list(source_lookup.keys())[:5]  # First 5 for debugging
        
        return result
    
    def _create_source_attributions(
        self,
        citations: List[Citation],
        retrieval_context: Optional[Dict[str, Any]] = None
    ) -> List[SourceAttribution]:
        """
        Create source attributions from citations
        
        Args:
            citations: List of validated citations
            retrieval_context: Original retrieval context
            
        Returns:
            List of SourceAttribution objects
        """
        source_map = defaultdict(list)
        
        # Group citations by source
        for citation in citations:
            if citation.is_valid:
                source_map[citation.source_id].append(citation)
        
        # Create attributions
        attributions = []
        for source_id, source_citations in source_map.items():
            # Use first citation for basic info
            first_citation = source_citations[0]
            
            # Calculate aggregate confidence
            avg_confidence = sum(c.confidence for c in source_citations) / len(source_citations)
            
            # Calculate relevance score
            avg_relevance = sum(c.relevance_score for c in source_citations) / len(source_citations)
            
            # Get title from retrieval context if available
            title = first_citation.source
            if retrieval_context:
                title = self._extract_title_from_context(source_id, retrieval_context) or title
            
            attribution = SourceAttribution(
                source_id=source_id,
                source_type=first_citation.source_type,
                title=title,
                confidence=avg_confidence,
                relevance_score=avg_relevance,
                citation_count=len(source_citations),
                first_citation_pos=min(c.position for c in source_citations),
                metadata={
                    'citations': [asdict(c) for c in source_citations],
                    'validation_details': first_citation.validation_details
                }
            )
            
            attributions.append(attribution)
        
        # Sort by first citation position
        attributions.sort(key=lambda x: x.first_citation_pos)
        
        return attributions
    
    def _format_content(self, content: str, citations: List[Citation]) -> str:
        """
        Format content based on citation style
        
        Args:
            content: Original content
            citations: List of citations
            
        Returns:
            Formatted content
        """
        if self.citation_style == CitationStyle.NONE:
            return self._remove_all_citations(content)
        
        elif self.citation_style == CitationStyle.INLINE:
            # Keep original inline citations
            return content
        
        elif self.citation_style == CitationStyle.FOOTNOTE:
            return self._convert_to_footnotes(content, citations)
        
        return content
    
    def _convert_to_footnotes(self, content: str, citations: List[Citation]) -> str:
        """
        Convert inline citations to footnote style
        
        Args:
            content: Content with inline citations
            citations: List of citations
            
        Returns:
            Content with footnote-style citations
        """
        # Create footnote mapping
        footnote_map = {}
        numbered_content = content
        
        # Replace citations with numbers
        for i, citation in enumerate(citations, 1):
            if citation.is_valid:
                # Replace citation with superscript number
                numbered_content = numbered_content.replace(
                    citation.raw_text,
                    f'[{i}]',
                    1  # Replace only first occurrence
                )
                footnote_map[i] = citation
        
        # Generate footnotes
        footnotes = []
        for i, citation in sorted(footnote_map.items()):
            footnote_text = f"[{i}] {citation.source}"
            if citation.snippet:
                footnote_text += f" - \"{citation.snippet[:100]}...\""
            footnotes.append(footnote_text)
        
        # Append footnotes
        if footnotes:
            numbered_content += "\n\n---\n**References:**\n" + "\n".join(footnotes)
        
        return numbered_content
    
    def _calculate_quality_metrics(
        self,
        content: str,
        citations: List[Citation],
        sources: List[SourceAttribution]
    ) -> Dict[str, float]:
        """
        Calculate quality metrics for the response
        
        Args:
            content: Formatted content
            citations: List of citations
            sources: List of source attributions
            
        Returns:
            Dictionary of quality metrics
        """
        metrics = {}
        
        # Citation accuracy
        if citations:
            valid_citations = [c for c in citations if c.is_valid]
            metrics['citation_accuracy'] = len(valid_citations) / len(citations)
        else:
            metrics['citation_accuracy'] = 1.0  # No citations to validate
        
        # Source diversity (unique source types)
        if sources:
            source_types = set(s.source_type for s in sources)
            metrics['source_diversity'] = len(source_types) / len(SourceType)
        else:
            metrics['source_diversity'] = 0.0
        
        # Citation density (citations per 1000 characters)
        content_length = len(content)
        if content_length > 0:
            metrics['citation_density'] = (len(citations) / content_length) * 1000
        else:
            metrics['citation_density'] = 0.0
        
        return metrics
    
    def _clean_source_text(self, source_text: str) -> str:
        """Clean and normalize source text"""
        # Remove common prefixes
        prefixes = ['source:', 'ref:', 'document:', 'file:', 'the', 'a', 'an']
        
        cleaned = source_text.strip()
        for prefix in prefixes:
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        # Remove quotes and extra whitespace
        cleaned = cleaned.strip('\'"')
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned
    
    def _determine_source_type(self, source_text: str) -> SourceType:
        """Determine source type from source text"""
        source_lower = source_text.lower()
        
        for source_type, patterns in self.source_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, source_lower):
                    return SourceType(source_type)
        
        return SourceType.DECISION_CASE  # Default
    
    def _generate_source_id(self, source_text: str, source_type: SourceType) -> str:
        """Generate consistent source ID"""
        # Normalize and hash for consistent ID
        normalized = f"{source_type.value}:{source_text.lower()}"
        import hashlib
        return hashlib.md5(normalized.encode()).hexdigest()[:12]
    
    def _get_citation_context(self, text: str, position: int, window: int = 100) -> str:
        """Get surrounding context for a citation"""
        start = max(0, position - window)
        end = min(len(text), position + window)
        
        context = text[start:end].strip()
        
        # Clean up
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        
        return context
    
    def _extract_snippet(self, text: str, start: int, end: int, max_length: int = 50) -> str:
        """Extract snippet around citation"""
        snippet_start = max(0, start - 20)
        snippet_end = min(len(text), end + 30)
        
        snippet = text[snippet_start:snippet_end].strip()
        
        if len(snippet) > max_length:
            snippet = snippet[:max_length] + "..."
        
        return snippet
    
    def _deduplicate_citations(self, citations: List[Citation]) -> List[Citation]:
        """Remove duplicate citations"""
        if not citations:
            return []
        
        unique = []
        seen = set()
        
        for citation in citations:
            # Key: source + approximate position (grouped by 50 chars)
            key = (citation.source.lower(), citation.position // 50)
            
            if key not in seen:
                unique.append(citation)
                seen.add(key)
        
        return unique
    
    def _remove_all_citations(self, text: str) -> str:
        """Remove all citation markers from text"""
        cleaned = text
        
        for pattern in self.citation_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def _calculate_relevance_score(self, context: str, content: str) -> float:
        """Calculate relevance score between context and content"""
        if not context or not content:
            return 0.0
        
        # Simple word overlap for relevance
        context_words = set(context.lower().split())
        content_words = set(content.lower().split())
        
        if not context_words:
            return 0.0
        
        overlap = len(context_words & content_words)
        return overlap / len(context_words)
    
    def _extract_title_from_context(
        self,
        source_id: str,
        retrieval_context: Dict[str, Any]
    ) -> Optional[str]:
        """Extract title from retrieval context"""
        # This is a simplified implementation
        # In practice, this would search through the retrieval context
        # to find the title for the given source ID
        
        if 'results' in retrieval_context:
            for result in retrieval_context['results']:
                if result.get('id') == source_id or result.get('source_id') == source_id:
                    return result.get('title')
        
        return None
    
    def get_supported_citation_styles(self) -> List[str]:
        """Get list of supported citation styles"""
        return [style.value for style in CitationStyle]
    
    def update_citation_style(self, style: str) -> bool:
        """Update citation style"""
        try:
            new_style = CitationStyle(style.lower())
            self.citation_style = new_style
            logger.info(f"Updated citation style to {new_style.value}")
            return True
        except ValueError:
            logger.error(f"Invalid citation style: {style}")
            return False


__all__ = [
    'AdvancedResponseFormatter',
    'FormattedResponse',
    'Citation',
    'SourceAttribution',
    'CitationStyle',
    'SourceType'
]