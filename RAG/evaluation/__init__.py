"""
Evaluation Module - RAGAS-based Quality Metrics for RAG

Provides evaluation capabilities for RAG responses.

Metrics:
- Faithfulness: Is the answer grounded in the retrieved context?
- Answer Relevancy: Does the answer address the question?
- Context Precision: Are the retrieved documents relevant?
- Context Recall: Did we retrieve all relevant documents? (requires ground truth)
"""

from .ragas_evaluator import RAGASEvaluator, EvaluationResult
from .quality_metrics import QualityMetrics, ResponseQualityChecker

__all__ = [
    "RAGASEvaluator",
    "EvaluationResult",
    "QualityMetrics",
    "ResponseQualityChecker"
]
