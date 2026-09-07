"""
Quality Metrics for RAG Response Evaluation

Phase 4: Provides lightweight quality metrics that can run without
external dependencies (fallback when RAGAS is not available).

Metrics implemented:
- Answer Relevance: Lexical and semantic overlap with query
- Context Coverage: How much context is used in the answer
- Citation Quality: Presence and accuracy of citations
- Response Completeness: Length and structure checks
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
import math

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """Container for quality metric scores."""
    answer_relevance: float = 0.0
    context_coverage: float = 0.0
    citation_quality: float = 0.0
    response_completeness: float = 0.0
    faithfulness_estimate: float = 0.0
    overall_score: float = 0.0

    # Detailed breakdown
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer_relevance": round(self.answer_relevance, 3),
            "context_coverage": round(self.context_coverage, 3),
            "citation_quality": round(self.citation_quality, 3),
            "response_completeness": round(self.response_completeness, 3),
            "faithfulness_estimate": round(self.faithfulness_estimate, 3),
            "overall_score": round(self.overall_score, 3),
            "details": self.details
        }


class ResponseQualityChecker:
    """
    Lightweight quality checker for RAG responses.

    Provides quick quality metrics without requiring external LLM calls
    or RAGAS dependencies. Useful for real-time quality monitoring.
    """

    # Stop words for relevance calculation
    STOP_WORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
        'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'between', 'under', 'again', 'further', 'then', 'once',
        'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few',
        'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
        'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'just', 'don',
        'now', 'and', 'or', 'but', 'if', 'because', 'until', 'while', 'this',
        'that', 'these', 'those', 'what', 'which', 'who', 'whom', 'i', 'me',
        'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your',
        'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself',
        'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them',
        'their', 'theirs', 'themselves'
    }

    def __init__(
        self,
        embedding_model=None,
        min_answer_length: int = 50,
        max_answer_length: int = 2000
    ):
        """
        Initialize quality checker.

        Args:
            embedding_model: Optional embedding model for semantic similarity
            min_answer_length: Minimum expected answer length
            max_answer_length: Maximum expected answer length
        """
        self.embedding_model = embedding_model
        self.min_answer_length = min_answer_length
        self.max_answer_length = max_answer_length

    def evaluate(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        expected_citations: Optional[int] = None
    ) -> QualityMetrics:
        """
        Evaluate the quality of a RAG response.

        Args:
            question: User's query
            answer: Generated response
            contexts: Retrieved context documents
            expected_citations: Expected number of citations (optional)

        Returns:
            QualityMetrics with scores and details
        """
        metrics = QualityMetrics()

        # Calculate individual metrics
        metrics.answer_relevance = self._calculate_answer_relevance(question, answer)
        metrics.context_coverage = self._calculate_context_coverage(answer, contexts)
        metrics.citation_quality = self._calculate_citation_quality(answer, contexts, expected_citations)
        metrics.response_completeness = self._calculate_completeness(answer, question)
        metrics.faithfulness_estimate = self._estimate_faithfulness(answer, contexts)

        # Calculate weighted overall score
        weights = {
            'answer_relevance': 0.25,
            'context_coverage': 0.20,
            'citation_quality': 0.15,
            'response_completeness': 0.15,
            'faithfulness_estimate': 0.25
        }

        metrics.overall_score = sum(
            getattr(metrics, metric) * weight
            for metric, weight in weights.items()
        )

        # Add details
        metrics.details = {
            "question_length": len(question),
            "answer_length": len(answer),
            "context_count": len(contexts),
            "total_context_length": sum(len(c) for c in contexts),
            "weights_used": weights
        }

        return metrics

    def _calculate_answer_relevance(self, question: str, answer: str) -> float:
        """
        Calculate how relevant the answer is to the question.

        Uses term overlap and optional semantic similarity.
        """
        # Extract significant terms
        question_terms = self._extract_terms(question)
        answer_terms = self._extract_terms(answer)

        if not question_terms:
            return 0.5  # Neutral if no terms extracted

        # Calculate term overlap (Jaccard-like)
        overlap = len(question_terms & answer_terms)
        relevance = overlap / len(question_terms)

        # Boost if answer contains question's key entities
        entities = self._extract_entities(question)
        entity_coverage = sum(1 for e in entities if e.lower() in answer.lower())
        if entities:
            entity_bonus = 0.2 * (entity_coverage / len(entities))
            relevance = min(1.0, relevance + entity_bonus)

        # Use semantic similarity if embedding model available
        if self.embedding_model:
            try:
                q_emb = self.embedding_model.encode(question, show_progress_bar=False)
                a_emb = self.embedding_model.encode(answer[:500], show_progress_bar=False)

                import numpy as np
                dot = np.dot(q_emb, a_emb)
                norm = np.linalg.norm(q_emb) * np.linalg.norm(a_emb)
                if norm > 0:
                    semantic_sim = dot / norm
                    # Blend lexical and semantic (60% semantic, 40% lexical)
                    relevance = 0.6 * semantic_sim + 0.4 * relevance
            except Exception as e:
                logger.warning(f"Semantic relevance calculation failed: {e}")

        return min(1.0, max(0.0, relevance))

    def _calculate_context_coverage(self, answer: str, contexts: List[str]) -> float:
        """
        Calculate how much of the context is reflected in the answer.

        Higher score = answer incorporates more context material.
        """
        if not contexts:
            return 0.5  # Neutral if no context

        answer_terms = self._extract_terms(answer)

        # Calculate coverage for each context
        coverages = []
        for context in contexts:
            context_terms = self._extract_terms(context)
            if context_terms:
                overlap = len(answer_terms & context_terms)
                coverage = overlap / len(context_terms)
                coverages.append(coverage)

        if not coverages:
            return 0.5

        # Use average coverage with bonus for using multiple contexts
        avg_coverage = sum(coverages) / len(coverages)
        multi_context_bonus = 0.1 * min(sum(1 for c in coverages if c > 0.1), 3)

        return min(1.0, avg_coverage + multi_context_bonus)

    def _calculate_citation_quality(
        self,
        answer: str,
        contexts: List[str],
        expected_citations: Optional[int]
    ) -> float:
        """
        Evaluate citation usage in the answer.

        Checks for:
        - Presence of citation markers
        - Correct citation format
        - Citation accuracy (if contexts indexed)
        """
        # Find citation patterns
        bracket_citations = re.findall(r'\[(\d+)\]', answer)
        parenthetical = re.findall(r'\((?:Source|Ref|Doc)\s*:?\s*(\d+)\)', answer, re.I)

        all_citations = bracket_citations + parenthetical
        citation_count = len(all_citations)

        if not contexts:
            return 0.5 if citation_count == 0 else 0.7

        # Base score on citation presence
        if citation_count == 0:
            base_score = 0.3  # No citations is not ideal
        elif expected_citations and citation_count >= expected_citations:
            base_score = 0.9
        else:
            base_score = min(0.8, 0.4 + 0.1 * citation_count)

        # Verify citation indices are valid
        valid_citations = 0
        for cite in all_citations:
            try:
                idx = int(cite)
                if 1 <= idx <= len(contexts):
                    valid_citations += 1
            except ValueError:
                pass

        if all_citations:
            validity_bonus = 0.1 * (valid_citations / len(all_citations))
            base_score = min(1.0, base_score + validity_bonus)

        return base_score

    def _calculate_completeness(self, answer: str, question: str) -> float:
        """
        Evaluate response completeness.

        Checks:
        - Appropriate length
        - Contains reasoning indicators
        - Structured response
        """
        score = 0.5  # Start neutral

        # Length check
        length = len(answer)
        if length < self.min_answer_length:
            score -= 0.2  # Too short
        elif self.min_answer_length <= length <= self.max_answer_length:
            score += 0.2  # Good length
        else:
            score += 0.1  # Acceptable but long

        # Check for reasoning indicators
        reasoning_patterns = [
            r'\bbecause\b', r'\btherefore\b', r'\bthus\b', r'\bhence\b',
            r'\bbased on\b', r'\bdue to\b', r'\bas a result\b', r'\bgiven that\b',
            r'\bconsidering\b', r'\bsince\b', r'\bhowever\b', r'\balthough\b'
        ]

        reasoning_count = sum(
            1 for pattern in reasoning_patterns
            if re.search(pattern, answer, re.I)
        )
        score += 0.05 * min(reasoning_count, 4)

        # Check for structure (paragraphs, bullets, numbered lists)
        has_paragraphs = len(answer.split('\n\n')) > 1
        has_bullets = bool(re.search(r'^[\s]*[-•*]', answer, re.M))
        has_numbers = bool(re.search(r'^[\s]*\d+[.)]', answer, re.M))

        structure_score = sum([has_paragraphs, has_bullets, has_numbers])
        score += 0.05 * structure_score

        # Check question type alignment
        if '?' in question:
            if question.lower().startswith(('what', 'who', 'where', 'when')):
                # Factual question - should have direct answer
                if len(answer.split('.')[0]) < 100:
                    score += 0.1  # Good concise start
            elif question.lower().startswith(('how', 'why')):
                # Explanation question - should be longer
                if length > 150:
                    score += 0.1

        return min(1.0, max(0.0, score))

    def _estimate_faithfulness(self, answer: str, contexts: List[str]) -> float:
        """
        Estimate faithfulness (is answer grounded in context?).

        This is a heuristic approximation. For accurate faithfulness
        measurement, use RAGAS with LLM evaluation.
        """
        if not contexts:
            return 0.5

        # Combine all contexts
        all_context = " ".join(contexts).lower()
        all_context_terms = self._extract_terms(all_context)

        # Extract answer sentences
        answer_sentences = re.split(r'[.!?]+', answer)
        answer_sentences = [s.strip() for s in answer_sentences if len(s.strip()) > 20]

        if not answer_sentences:
            return 0.5

        # Check each sentence for grounding
        grounded_count = 0
        for sentence in answer_sentences:
            sentence_terms = self._extract_terms(sentence)
            if not sentence_terms:
                continue

            # Check overlap with context
            overlap = len(sentence_terms & all_context_terms)
            coverage = overlap / len(sentence_terms)

            if coverage >= 0.4:  # At least 40% of terms from context
                grounded_count += 1

        faithfulness = grounded_count / len(answer_sentences)

        # Boost if citations are used correctly
        if re.search(r'\[\d+\]', answer):
            faithfulness = min(1.0, faithfulness + 0.1)

        return faithfulness

    def _extract_terms(self, text: str) -> Set[str]:
        """Extract significant terms from text."""
        # Tokenize and lowercase
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

        # Remove stop words
        return set(words) - self.STOP_WORDS

    def _extract_entities(self, text: str) -> List[str]:
        """Extract potential named entities from text."""
        # Simple heuristic: capitalized words that aren't sentence starters
        entities = []

        # Find capitalized sequences
        pattern = r'(?<!\. )(?<![.!?]\s)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        matches = re.findall(pattern, text)

        for match in matches:
            if match.lower() not in self.STOP_WORDS:
                entities.append(match)

        return entities

    def quick_check(
        self,
        answer: str,
        min_length: int = 50
    ) -> Dict[str, Any]:
        """
        Quick quality check for basic validation.

        Returns:
            Dict with pass/fail and basic stats
        """
        issues = []

        # Length check
        if len(answer) < min_length:
            issues.append(f"Answer too short ({len(answer)} chars < {min_length})")

        # Empty or placeholder check
        placeholder_patterns = [
            r"I don't have enough information",
            r"I cannot answer",
            r"No relevant.*found",
            r"Unable to provide"
        ]

        for pattern in placeholder_patterns:
            if re.search(pattern, answer, re.I):
                issues.append("Answer appears to be a placeholder/fallback")
                break

        # Repetition check
        words = answer.lower().split()
        if len(words) > 10:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.3:
                issues.append("High word repetition detected")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "length": len(answer),
            "word_count": len(words) if words else 0
        }
