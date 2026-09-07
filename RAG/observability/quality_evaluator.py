"""
Quality Evaluator
=================

Evaluates response quality metrics:
- Decision fidelity
- Citation coverage
- Factual grounding
- Tone match

Features:
- Automatic evaluation after each response
- Prometheus metrics integration
- Sampling support (to reduce overhead)

Usage:
    from observability.quality_evaluator import QualityEvaluator
    
    metrics = QualityEvaluator.evaluate_response(
        response=answer,
        sources=retrieval_results,
        executive_id=profile_id
    )
"""

from typing import Dict, Any, List, Optional
import re
import random
from datetime import datetime

from .logging import StructuredLogger
from .metrics import (
    decision_fidelity_score,
    citation_coverage,
    factual_grounding_rate,
)
from .config import QUALITY_EVAL_ENABLED, QUALITY_EVAL_SAMPLING_RATE

logger = StructuredLogger(__name__)


class QualityEvaluator:
    """
    Evaluate response quality.
    
    Provides automated quality assessment for AI responses.
    """
    
    @staticmethod
    def should_evaluate() -> bool:
        """
        Determine if response should be evaluated (sampling).
        
        Returns:
            True if should evaluate based on sampling rate
        """
        if not QUALITY_EVAL_ENABLED:
            return False
        
        return random.random() < QUALITY_EVAL_SAMPLING_RATE
    
    @staticmethod
    def extract_citations(response: str) -> List[int]:
        """
        Extract citation numbers from response.
        
        Finds all [1], [2], [3] patterns.
        
        Args:
            response: Response text
            
        Returns:
            List of citation numbers
            
        Example:
            citations = extract_citations("Based on [1] and [2]...")
            # Returns: [1, 2]
        """
        # Find all [1], [2], [3] patterns
        citations = re.findall(r'\[(\d+)\]', response)
        return [int(c) for c in citations]
    
    @staticmethod
    def calculate_citation_coverage(
        response: str,
        sources: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate citation coverage percentage.
        
        Coverage = (unique sources cited / total sources) * 100
        
        Args:
            response: Response text with citations
            sources: List of source documents
            
        Returns:
            Coverage percentage (0-100)
        """
        if not sources:
            return 100.0
        
        citations = QualityEvaluator.extract_citations(response)
        unique_citations = set(citations)
        
        # Coverage = (unique sources cited / total sources) * 100
        coverage = len(unique_citations) / len(sources) * 100
        return min(coverage, 100.0)
    
    @staticmethod
    def check_factual_grounding(
        response: str,
        sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Check if claims are grounded in sources.
        
        Uses simple heuristic: sentences with citations are grounded.
        For production, use more sophisticated NLI models.
        
        Args:
            response: Response text
            sources: List of source documents
            
        Returns:
            Dictionary with grounding metrics
        """
        # Extract citations
        citations = QualityEvaluator.extract_citations(response)
        
        if not citations:
            # No citations = not grounded
            return {
                'total_claims': 1,
                'grounded_claims': 0,
                'grounding_rate': 0.0
            }
        
        # Split response into sentences
        sentences = re.split(r'[.!?]', response)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Simple heuristic: sentences with citations are grounded
        grounded_sentences = sum(
            1 for sent in sentences 
            if any(f"[{c}]" in sent for c in citations)
        )
        
        # Grounding rate
        total_claims = len(sentences)
        grounding_rate = grounded_sentences / total_claims if total_claims > 0 else 1.0
        
        return {
            'total_claims': total_claims,
            'grounded_claims': grounded_sentences,
            'grounding_rate': grounding_rate
        }
    
    @staticmethod
    def evaluate_response(
        response: str,
        sources: List[Dict[str, Any]],
        executive_id: str,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate response quality.
        
        Returns comprehensive quality metrics.
        
        Args:
            response: Generated response text
            sources: List of source documents used
            executive_id: Executive profile ID
            query: Optional original query
            
        Returns:
            Dictionary with quality metrics
            
        Example:
            metrics = QualityEvaluator.evaluate_response(
                response=answer,
                sources=retrieval_results,
                executive_id="exec_001"
            )
        """
        if not QualityEvaluator.should_evaluate():
            # Skip evaluation (sampling)
            return {}
        
        try:
            # Citation coverage
            cit_coverage = QualityEvaluator.calculate_citation_coverage(response, sources)
            
            # Factual grounding
            grounding_result = QualityEvaluator.check_factual_grounding(response, sources)
            
            # Update metrics
            citation_coverage.labels(executive_id=executive_id).set(cit_coverage)
            factual_grounding_rate.labels(executive_id=executive_id).set(
                grounding_result['grounding_rate'] * 100
            )
            
            # Log evaluation
            logger.info(
                "Response quality evaluated",
                executive_id=executive_id,
                citation_coverage=cit_coverage,
                grounding_rate=grounding_result['grounding_rate'] * 100,
                total_claims=grounding_result['total_claims'],
                grounded_claims=grounding_result['grounded_claims']
            )
            
            return {
                'citation_coverage': cit_coverage,
                **grounding_result
            }
            
        except Exception as e:
            logger.error("Quality evaluation failed", error=e)
            return {}
    
    @staticmethod
    def evaluate_decision_fidelity(
        response: str,
        expected_decision: Optional[str],
        executive_id: str
    ) -> float:
        """
        Evaluate decision fidelity.
        
        Compares generated decision with expected decision.
        For production, use semantic similarity models.
        
        Args:
            response: Generated response
            expected_decision: Expected decision (from test bank)
            executive_id: Executive profile ID
            
        Returns:
            Fidelity score (0-1)
        """
        if not expected_decision:
            return 1.0  # No expected decision to compare
        
        # TODO: Implement proper semantic similarity
        # For now, use simple keyword matching as placeholder
        
        response_lower = response.lower()
        expected_lower = expected_decision.lower()
        
        # Extract key decision words
        decision_words = ['approve', 'reject', 'defer', 'escalate', 'recommend']
        
        response_decision = None
        expected_decision_word = None
        
        for word in decision_words:
            if word in response_lower:
                response_decision = word
            if word in expected_lower:
                expected_decision_word = word
        
        # Simple match
        if response_decision == expected_decision_word:
            score = 0.9  # High fidelity
        elif response_decision and expected_decision_word:
            score = 0.5  # Different decision
        else:
            score = 0.7  # Unclear
        
        # Update metric
        decision_fidelity_score.labels(executive_id=executive_id).observe(score)
        
        logger.info(
            "Decision fidelity evaluated",
            executive_id=executive_id,
            fidelity_score=score,
            response_decision=response_decision,
            expected_decision=expected_decision_word
        )
        
        return score


class QualityReport:
    """Generate quality reports"""
    
    @staticmethod
    def generate_daily_report() -> Dict[str, Any]:
        """
        Generate daily quality report.
        
        Returns:
            Dictionary with aggregated quality metrics
        """
        # TODO: Implement daily aggregation from Prometheus
        # For now, return placeholder
        return {
            'date': str(datetime.utcnow().date()),
            'message': 'Quality report generation not yet implemented'
        }
