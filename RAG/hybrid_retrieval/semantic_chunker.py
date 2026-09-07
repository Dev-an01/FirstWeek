"""
Semantic Chunker for AI Officer RAG System

Splits long documents into semantically coherent sections using a 3-signal approach:
1. Explicit headings (Markdown, ALL CAPS, numbered)
2. Topic shift detection (sentence embedding similarity)
3. Paragraph breaks (fallback)

This addresses the embedding dilution problem where relevant information
gets "drowned out" by irrelevant content in long documents.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Splits documents into semantic sections to improve retrieval precision.

    Benefits:
    - Reduces embedding dilution for long documents
    - Enables section-level retrieval for better precision
    - Maintains parent document context
    - Reduces token usage (62% reduction expected)
    """

    def __init__(
        self,
        embedding_model: Optional[SentenceTransformer] = None,
        min_section_words: int = 50,
        max_section_words: int = 1000,
        topic_shift_threshold: float = 0.65,
        confidence_threshold: float = 0.6
    ):
        """
        Initialize semantic chunker.

        Args:
            embedding_model: SentenceTransformer model for topic shift detection
            min_section_words: Minimum words per section (default: 50)
            max_section_words: Maximum words per section (default: 1000)
            topic_shift_threshold: Similarity threshold for topic shifts (default: 0.65)
            confidence_threshold: Minimum confidence for boundaries (default: 0.6)
        """
        self.embedding_model = embedding_model
        self.min_section_words = min_section_words
        self.max_section_words = max_section_words
        self.topic_shift_threshold = topic_shift_threshold
        self.confidence_threshold = confidence_threshold

        # Heading patterns for Signal A
        self.heading_patterns = [
            (r'^#{1,6}\s+.+$', 'markdown'),              # Markdown: ## Heading
            (r'^[A-Z\s]{5,}:.*$', 'all_caps'),           # All caps: SECTION:
            (r'^\d+\.\s+[A-Z].*$', 'numbered'),          # Numbered: 1. Title
            (r'^[A-Z][A-Za-z\s]{3,}:$', 'colon_title'),  # Title: with colon
        ]

        logger.info(f"SemanticChunker initialized with min_words={min_section_words}, "
                   f"max_words={max_section_words}, topic_threshold={topic_shift_threshold}")

    def chunk_document(
        self,
        document: Dict[str, Any],
        document_text: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Main entry point: chunk a document into sections.

        Args:
            document: Document dict with 'id', 'text', and metadata
            document_text: Optional text override (if not in document['text'])

        Returns:
            List of section dicts with embeddings and metadata
        """
        text = document_text or document.get('text', '')

        if not text or len(text.strip()) == 0:
            logger.warning(f"Empty document: {document.get('id', 'unknown')}")
            return []

        word_count = len(text.split())

        # Skip chunking for short documents
        if word_count < self.min_section_words * 2:
            logger.info(f"Document {document.get('id')} too short ({word_count} words), "
                       f"treating as single section")
            return self._create_single_section(document, text)

        logger.info(f"Chunking document {document.get('id')} ({word_count} words)")

        # Step 1: Detect boundaries
        boundaries = self.detect_section_boundaries(text)

        if not boundaries or len(boundaries) < 2:
            logger.info(f"No sufficient boundaries found, treating as single section")
            return self._create_single_section(document, text)

        # Step 2: Create sections
        sections = self.create_sections(document, text, boundaries)

        logger.info(f"Created {len(sections)} sections from document {document.get('id')}")

        return sections

    def detect_section_boundaries(self, document_text: str) -> List[Dict[str, Any]]:
        """
        Identify where to split a document into sections using 3 signals.

        Args:
            document_text: Full document text

        Returns:
            List of boundary dicts with position, type, confidence
        """
        boundaries = []

        # Signal A: Explicit Heading Detection
        heading_boundaries = self._detect_explicit_headings(document_text)
        boundaries.extend(heading_boundaries)

        # Signal B: Topic Shift Detection (only if <2 explicit headings)
        if len(boundaries) < 2 and self.embedding_model is not None:
            logger.info("Few headings found, trying topic shift detection")
            topic_boundaries = self._detect_topic_shifts(document_text)
            boundaries.extend(topic_boundaries)

        # Signal C: Paragraph Breaks (fallback if still <2 boundaries)
        if len(boundaries) < 2:
            logger.info("Few boundaries found, using paragraph breaks as fallback")
            para_boundaries = self._detect_paragraph_breaks(document_text)
            boundaries.extend(para_boundaries)

        # Sort by position and filter by confidence
        boundaries = sorted(boundaries, key=lambda x: x['position'])
        boundaries = [b for b in boundaries if b['confidence'] >= self.confidence_threshold]

        # Deduplicate boundaries that are too close (within 50 chars)
        boundaries = self._deduplicate_boundaries(boundaries, min_distance=50)

        logger.info(f"Detected {len(boundaries)} section boundaries")

        return boundaries

    def _detect_explicit_headings(self, text: str) -> List[Dict[str, Any]]:
        """Signal A: Find explicit headings using regex patterns."""
        boundaries = []

        for pattern, pattern_type in self.heading_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)

            for match in matches:
                boundaries.append({
                    'position': match.start(),
                    'type': 'explicit_heading',
                    'subtype': pattern_type,
                    'confidence': 0.95,
                    'text': match.group().strip()
                })

        logger.debug(f"Found {len(boundaries)} explicit headings")
        return boundaries

    def _detect_topic_shifts(self, text: str) -> List[Dict[str, Any]]:
        """Signal B: Detect topic shifts using sentence embeddings."""
        if self.embedding_model is None:
            return []

        boundaries = []

        # Split into sentences
        sentences = self._split_into_sentences(text)

        if len(sentences) < 3:
            return []

        # Generate embeddings
        try:
            sentence_embeddings = self.embedding_model.encode(sentences, show_progress_bar=False)
        except Exception as e:
            logger.error(f"Failed to generate embeddings for topic shifts: {e}")
            return []

        # Calculate similarity between consecutive sentences
        for i in range(1, len(sentences)):
            similarity = cosine_similarity(
                sentence_embeddings[i-1].reshape(1, -1),
                sentence_embeddings[i].reshape(1, -1)
            )[0][0]

            # Low similarity indicates topic shift
            if similarity < self.topic_shift_threshold:
                position = self._get_sentence_position(text, sentences, i)

                boundaries.append({
                    'position': position,
                    'type': 'topic_shift',
                    'confidence': 0.75,
                    'similarity_drop': float(1 - similarity),
                    'text': sentences[i][:50] + '...'
                })

        logger.debug(f"Found {len(boundaries)} topic shifts")
        return boundaries

    def _detect_paragraph_breaks(self, text: str) -> List[Dict[str, Any]]:
        """Signal C: Use paragraph breaks as fallback boundaries."""
        boundaries = []

        # Find double newlines (paragraph breaks)
        paragraph_breaks = [m.start() for m in re.finditer(r'\n\n+', text)]

        for pos in paragraph_breaks:
            # Get text around boundary for preview
            preview_start = max(0, pos - 20)
            preview_end = min(len(text), pos + 30)
            preview = text[preview_start:preview_end].replace('\n', ' ')

            boundaries.append({
                'position': pos,
                'type': 'paragraph_break',
                'confidence': 0.6,  # Increased from 0.5 to pass threshold
                'text': preview
            })

        logger.debug(f"Found {len(boundaries)} paragraph breaks")
        return boundaries

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using simple regex."""
        # Simple sentence splitter (could be improved with spaCy if needed)
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def _get_sentence_position(self, text: str, sentences: List[str], sentence_idx: int) -> int:
        """Find the character position of a sentence in the text."""
        # Reconstruct text up to this sentence
        preceding_text = ' '.join(sentences[:sentence_idx])

        # Find position in original text
        position = text.find(sentences[sentence_idx])

        return max(0, position)

    def _deduplicate_boundaries(self, boundaries: List[Dict], min_distance: int = 50) -> List[Dict]:
        """Remove boundaries that are too close to each other."""
        if len(boundaries) <= 1:
            return boundaries

        deduplicated = [boundaries[0]]

        for boundary in boundaries[1:]:
            last_pos = deduplicated[-1]['position']

            if boundary['position'] - last_pos >= min_distance:
                deduplicated.append(boundary)
            else:
                # Keep the one with higher confidence
                if boundary['confidence'] > deduplicated[-1]['confidence']:
                    deduplicated[-1] = boundary

        return deduplicated

    def create_sections(
        self,
        document: Dict[str, Any],
        document_text: str,
        boundaries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Split document into Section objects based on boundaries.

        Args:
            document: Parent document dict
            document_text: Full document text
            boundaries: List of boundary positions

        Returns:
            List of section dicts with embeddings and metadata
        """
        sections = []

        # Add start boundary if not present
        if not boundaries or boundaries[0]['position'] > 0:
            boundaries.insert(0, {
                'position': 0,
                'type': 'start',
                'confidence': 1.0,
                'text': document_text[:50]
            })

        for i, boundary in enumerate(boundaries):
            # Determine section range
            start = boundary['position']
            end = boundaries[i+1]['position'] if i+1 < len(boundaries) else len(document_text)

            section_text = document_text[start:end].strip()

            # Skip empty or too-short sections
            word_count = len(section_text.split())
            if word_count < self.min_section_words:
                logger.debug(f"Skipping short section {i} ({word_count} words)")
                continue

            # Generate section title
            section_title = self._generate_section_title(boundary, section_text)

            # Infer section type
            section_type = self._infer_section_type(section_text)

            # Generate embedding (using same model as for topic detection)
            section_embedding = None
            if self.embedding_model is not None:
                try:
                    section_embedding = self.embedding_model.encode(
                        section_text,
                        show_progress_bar=False
                    ).tolist()
                except Exception as e:
                    logger.error(f"Failed to generate embedding for section {i}: {e}")

            # Create section dict (use len(sections) for consistent numbering)
            section_number = len(sections)
            section = {
                'id': f"{document['id']}_section_{section_number}",
                'parent_document_id': document['id'],
                'section_number': section_number,
                'section_title': section_title,
                'content': section_text,
                'word_count': word_count,
                'section_type': section_type,
                'boundary_type': boundary['type'],
                'boundary_confidence': boundary['confidence'],
                'embedding': section_embedding,
                # Preserve parent metadata
                'parent_metadata': {
                    'doc_type': document.get('doc_type', 'unknown'),
                    'created_at': document.get('created_at', None),
                    'executive_id': document.get('executive_id', None)
                }
            }

            sections.append(section)

        return sections

    def _generate_section_title(self, boundary: Dict[str, Any], section_text: str) -> str:
        """Generate a title for the section based on boundary or content."""
        # If explicit heading, use it
        if boundary['type'] == 'explicit_heading' and 'text' in boundary:
            title = boundary['text']
            # Clean up markdown/numbering
            title = re.sub(r'^#+\s+', '', title)  # Remove markdown ##
            title = re.sub(r'^\d+\.\s+', '', title)  # Remove numbering
            return title[:100]

        # Otherwise, use first sentence
        sentences = self._split_into_sentences(section_text)
        if sentences:
            return sentences[0][:100]

        return section_text[:100]

    def _infer_section_type(self, section_text: str) -> str:
        """
        Classify section as intro/methodology/results/discussion/conclusion.

        Uses keyword-based heuristics.
        """
        keywords = {
            'introduction': ['background', 'overview', 'introduction', 'context', 'summary'],
            'methodology': ['method', 'approach', 'process', 'implementation', 'procedure'],
            'results': ['results', 'findings', 'outcome', 'achieved', 'impact'],
            'discussion': ['implications', 'analysis', 'interpretation', 'significance'],
            'conclusion': ['conclusion', 'summary', 'in summary', 'in conclusion', 'finally']
        }

        section_lower = section_text.lower()
        scores = {
            stype: sum(1 for kw in kws if kw in section_lower)
            for stype, kws in keywords.items()
        }

        max_score = max(scores.values())
        if max_score > 0:
            return max(scores, key=scores.get)

        return 'body'

    def _create_single_section(self, document: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
        """Create a single section for short documents."""
        section_embedding = None
        if self.embedding_model is not None:
            try:
                section_embedding = self.embedding_model.encode(
                    text,
                    show_progress_bar=False
                ).tolist()
            except Exception as e:
                logger.error(f"Failed to generate embedding: {e}")

        section = {
            'id': f"{document['id']}_section_0",
            'parent_document_id': document['id'],
            'section_number': 0,
            'section_title': document.get('title', text[:100]),
            'content': text,
            'word_count': len(text.split()),
            'section_type': 'body',
            'boundary_type': 'single_section',
            'boundary_confidence': 1.0,
            'embedding': section_embedding,
            'parent_metadata': {
                'doc_type': document.get('doc_type', 'unknown'),
                'created_at': document.get('created_at', None),
                'executive_id': document.get('executive_id', None)
            }
        }

        return [section]


def create_semantic_chunker(
    model_name: str = 'BAAI/bge-m3',
    **kwargs
) -> SemanticChunker:
    """
    Factory function to create a SemanticChunker with embedding model.

    Args:
        model_name: SentenceTransformer model name (default: BAAI/bge-m3, 1024-dim multilingual)
        **kwargs: Additional arguments for SemanticChunker

    Returns:
        SemanticChunker instance
    """
    logger.info(f"Loading embedding model: {model_name}")
    embedding_model = SentenceTransformer(model_name)

    return SemanticChunker(embedding_model=embedding_model, **kwargs)
