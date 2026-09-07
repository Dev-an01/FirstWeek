"""
Response Formatter for LLM Integration

Extracts citations, formats responses, and structures output.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FormattedResponse:
    """Structured response with extracted metadata"""
    content: str  # Main response text
    citations: List[Dict[str, str]]  # Extracted citations
    sources: List[str]  # Unique source documents
    confidence: Optional[float] = None  # Future: confidence scoring
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata


class ResponseFormatter:
    """
    Formats LLM responses for API output.
    
    Handles:
    - Citation extraction from response text
    - Source document tracking
    - Response structuring
    - Confidence estimation (future)
    """
    
    def __init__(self, citation_style: str = "inline"):
        """
        Initialize response formatter.

        Args:
            citation_style: Citation format (inline, footnote, none)
        """
        self.citation_style = citation_style

        # Citation patterns - expects actual source names
        self.citation_patterns = [
            r'\[Source:\s*([^\]]+)\]',  # [Source: doc_name] - REQUIRED FORMAT
            r'\[Ref:\s*([^\]]+)\]',     # [Ref: doc_name] - ALTERNATIVE FORMAT
        ]

        # Invalid patterns (for detecting hallucinations)
        self.invalid_citation_patterns = [
            r'\[(\d+)\]',  # [1], [2] - NUMBER format (not allowed per product requirement)
        ]
    
    def format_response(
        self,
        llm_content: str,
        retrieval_context: Optional[Dict[str, Any]] = None
    ) -> FormattedResponse:
        """
        Format LLM response and extract citations.

        Args:
            llm_content: Raw LLM response text
            retrieval_context: Original retrieval results for validation

        Returns:
            FormattedResponse with extracted metadata
        """
        # Extract citations
        citations = self._extract_citations(llm_content)

        # FIX: If LLM didn't add citations but we have retrieval results,
        # automatically inject citations based on documents actually used
        if len(citations) == 0 and retrieval_context:
            citations = self._inject_automatic_citations(retrieval_context)
            logger.warning(
                f"LLM did not add citations - auto-injected {len(citations)} citations from retrieval context"
            )

        # Get unique sources
        sources = list(set(c['source'] for c in citations))

        # Clean content if citation style is 'none'
        if self.citation_style == "none":
            content = self._remove_citations(llm_content)
        else:
            content = llm_content

        # Strip excessive markdown formatting (bold headers, etc.)
        content = self._strip_excessive_formatting(content)

        # Build metadata
        metadata = {
            "citation_count": len(citations),
            "unique_sources": len(sources),
            "citation_style": self.citation_style,
            "auto_injected": len(citations) > 0 and len(self._extract_citations(llm_content)) == 0
        }

        logger.debug(
            f"Formatted response: {len(citations)} citations from {len(sources)} sources"
        )

        return FormattedResponse(
            content=content,
            citations=citations,
            sources=sources,
            metadata=metadata
        )
    
    def _inject_automatic_citations(
        self,
        retrieval_context: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Automatically create citations from retrieval results when LLM fails to add them.

        Args:
            retrieval_context: Dictionary containing retrieval results

        Returns:
            List of auto-generated citation dicts
        """
        citations = []

        # Extract documents from various retrieval sources
        all_docs = []

        if "vector_results" in retrieval_context:
            all_docs.extend(retrieval_context["vector_results"])

        if "graph_results" in retrieval_context:
            all_docs.extend(retrieval_context["graph_results"])

        if "memory_results" in retrieval_context:
            all_docs.extend(retrieval_context["memory_results"])

        # Create citations from top documents (limit to top 3-5)
        max_auto_citations = 5
        for i, doc in enumerate(all_docs[:max_auto_citations]):
            # Extract source name from various possible fields
            source_name = (
                doc.get('title') or
                doc.get('name') or
                doc.get('source_id') or
                doc.get('id') or
                f"Document {i+1}"
            )

            citation = {
                "source": source_name,
                "raw_text": f"[Source: {source_name}]",
                "position": -1,  # Auto-injected, no text position
                "context": "Auto-generated citation from retrieval context",
                "auto_generated": True
            }
            citations.append(citation)

        logger.info(
            f"Auto-injected {len(citations)} citations from {len(all_docs)} retrieved documents"
        )

        return citations

    def _extract_citations(self, text: str) -> List[Dict[str, str]]:
        """
        Extract all citations from text.

        Returns:
            List of citation dicts with source, context, position
        """
        citations = []

        for pattern in self.citation_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                citation = {
                    "source": match.group(1).strip(),
                    "raw_text": match.group(0),
                    "position": match.start(),
                    "context": self._get_citation_context(text, match.start())
                }
                citations.append(citation)

        # Sort by position and deduplicate
        citations = sorted(citations, key=lambda x: x['position'])
        citations = self._deduplicate_citations(citations)

        return citations
    
    def _get_citation_context(self, text: str, position: int, window: int = 100) -> str:
        """
        Get surrounding context for a citation.
        
        Args:
            text: Full text
            position: Citation position
            window: Characters before/after to include
            
        Returns:
            Context snippet
        """
        start = max(0, position - window)
        end = min(len(text), position + window)
        
        context = text[start:end].strip()
        
        # Clean up
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        
        return context
    
    def _deduplicate_citations(self, citations: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Remove duplicate citations (same source at similar positions)"""
        if not citations:
            return []
        
        unique = []
        seen = set()
        
        for cit in citations:
            # Key: source + approximate position (grouped by 50 chars)
            key = (cit['source'].lower(), cit['position'] // 50)
            
            if key not in seen:
                unique.append(cit)
                seen.add(key)
        
        return unique
    
    def _remove_citations(self, text: str) -> str:
        """Remove all citation markers from text"""
        cleaned = text

        for pattern in self.citation_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    def _strip_excessive_formatting(self, text: str) -> str:
        """
        Strip excessive markdown formatting from LLM responses.

        Removes:
        - Bold headers like **Section Title**
        - Numbered bold lists like 1. **Point**
        - Emoji bold headers like 🔍 **Section**
        - Markdown tables

        Preserves:
        - Simple bullet points
        - Citations [Source: ...]
        - Normal text

        Args:
            text: Raw LLM response text

        Returns:
            Cleaned text without excessive formatting
        """
        if not text:
            return text

        cleaned = text

        # Remove bold formatting: **text** → text
        # But preserve citations like [Source: **name**] by being careful
        cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)

        # Remove italic formatting: *text* → text (but not bullet points)
        # Only remove if it's at word boundaries, not at line start (bullets)
        cleaned = re.sub(r'(?<!\n)(?<![- ])\*([^*\n]+)\*(?!\*)', r'\1', cleaned)

        # Remove markdown tables (lines with |)
        lines = cleaned.split('\n')
        filtered_lines = []
        for line in lines:
            # Skip table separator lines like |---|---|
            if re.match(r'^\s*\|[-:| ]+\|\s*$', line):
                continue
            # Convert table rows to plain text
            if '|' in line and line.strip().startswith('|'):
                # Extract cell contents
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if cells:
                    filtered_lines.append(' - '.join(cells))
            else:
                filtered_lines.append(line)

        cleaned = '\n'.join(filtered_lines)

        # Clean up multiple blank lines
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        return cleaned.strip()

    def convert_to_footnotes(self, text: str, citations: List[Dict[str, str]]) -> str:
        """
        Convert inline citations to footnote style.
        
        Args:
            text: Text with inline citations
            citations: Extracted citations
            
        Returns:
            Text with footnote-style references
        """
        # Replace inline citations with numbers
        numbered_text = text
        footnotes = []
        
        for i, cit in enumerate(citations, 1):
            # Replace citation with superscript number
            numbered_text = numbered_text.replace(
                cit['raw_text'],
                f'[{i}]',
                1  # Replace only first occurrence
            )
            footnotes.append(f"[{i}] {cit['source']}")
        
        # Append footnotes
        if footnotes:
            numbered_text += "\n\nReferences:\n" + "\n".join(footnotes)
        
        return numbered_text
    
    def validate_citations(
        self,
        response_text: str,
        source_mapping: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate that citations reference actual source documents using source names.

        Args:
            response_text: LLM response text with citations
            source_mapping: Mapping of source names (titles) to document metadata

        Returns:
            Validation report with valid/invalid citations and confidence score
        """
        # Extract all citations from response
        valid_citations = []
        invalid_citations = []
        warnings = []

        # Normalize available source names for fuzzy matching
        available_sources = set(source_mapping.keys())
        normalized_sources = {s.lower(): s for s in available_sources}

        # Find all [Source: X] and [Ref: X] citations
        for pattern in self.citation_patterns:
            citation_matches = re.finditer(pattern, response_text, re.IGNORECASE)

            for match in citation_matches:
                cited_source = match.group(1).strip()
                cited_source_lower = cited_source.lower()

                # Try exact match first
                if cited_source in available_sources:
                    source = source_mapping[cited_source]
                    valid_citations.append({
                        'citation_text': match.group(0),
                        'source_name': cited_source,
                        'source_doc_id': source['doc_id'],
                        'position': match.start(),
                        'confidence': 1.0,
                        'match_type': 'exact'
                    })
                # Try case-insensitive match
                elif cited_source_lower in normalized_sources:
                    actual_source = normalized_sources[cited_source_lower]
                    source = source_mapping[actual_source]
                    valid_citations.append({
                        'citation_text': match.group(0),
                        'source_name': actual_source,
                        'source_doc_id': source['doc_id'],
                        'position': match.start(),
                        'confidence': 0.95,
                        'match_type': 'case_insensitive'
                    })
                    warnings.append(f"Citation case mismatch: cited '{cited_source}', actual '{actual_source}'")
                # Try fuzzy match (substring)
                else:
                    fuzzy_match = None
                    for avail_source in available_sources:
                        if cited_source_lower in avail_source.lower() or avail_source.lower() in cited_source_lower:
                            fuzzy_match = avail_source
                            break

                    if fuzzy_match:
                        source = source_mapping[fuzzy_match]
                        valid_citations.append({
                            'citation_text': match.group(0),
                            'source_name': fuzzy_match,
                            'source_doc_id': source['doc_id'],
                            'position': match.start(),
                            'confidence': 0.85,
                            'match_type': 'fuzzy'
                        })
                        warnings.append(f"Citation fuzzy match: cited '{cited_source}', matched '{fuzzy_match}'")
                    else:
                        # Invalid citation - source not found
                        invalid_citations.append({
                            'citation_text': match.group(0),
                            'cited_source': cited_source,
                            'reason': f'Source "{cited_source}" not in available sources',
                            'position': match.start()
                        })
                        warnings.append(f"Invalid citation: '{cited_source}' - not in available sources")

        # Check for number format citations (not allowed per product requirement)
        for pattern in self.invalid_citation_patterns:
            number_matches = re.finditer(pattern, response_text)
            for match in number_matches:
                invalid_citations.append({
                    'citation_text': match.group(0),
                    'reason': 'Used number format [N] instead of [Source: name]',
                    'position': match.start()
                })
                warnings.append(f"Invalid citation format: {match.group(0)} - use [Source: name] instead")

        # Calculate confidence score
        total_citations = len(valid_citations) + len(invalid_citations)
        if total_citations > 0:
            # Weighted by individual citation confidence
            total_confidence = sum(c.get('confidence', 0) for c in valid_citations)
            confidence_score = total_confidence / total_citations
        else:
            confidence_score = 1.0

        return {
            'valid_count': len(valid_citations),
            'invalid_count': len(invalid_citations),
            'valid_citations': valid_citations,
            'invalid_citations': invalid_citations,
            'confidence_score': confidence_score,
            'warnings': warnings,
            'total_available_sources': len(source_mapping),
            'available_sources': list(available_sources)
        }
    
    def add_metadata_footer(self, content: str, metadata: Dict[str, Any]) -> str:
        """
        Add metadata footer to response.
        
        Args:
            content: Response content
            metadata: Metadata to include (sources, confidence, etc.)
            
        Returns:
            Content with metadata footer
        """
        footer_parts = []
        
        if metadata.get('sources'):
            footer_parts.append(f"Sources: {', '.join(metadata['sources'][:5])}")
        
        if metadata.get('confidence'):
            footer_parts.append(f"Confidence: {metadata['confidence']:.0%}")
        
        if footer_parts:
            footer = "\n\n---\n" + " | ".join(footer_parts)
            return content + footer
        
        return content
