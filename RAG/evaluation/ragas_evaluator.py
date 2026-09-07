"""
RAGAS Evaluator for RAG Quality Assessment

Provides comprehensive evaluation of RAG responses using
RAGAS metrics when available, with fallback to lightweight metrics.

Metrics:
- Faithfulness: Is the answer grounded in the retrieved context?
- Answer Relevancy: Does the answer address the question?
- Context Precision: Are the retrieved documents relevant?
- Context Recall: Did we retrieve all relevant documents? (requires ground truth)

Usage:
    evaluator = RAGASEvaluator()

    result = await evaluator.evaluate_response(
        question="What is our Q3 budget?",
        answer="The Q3 budget is $1.2M based on...",
        contexts=["Q3 budget document: The allocated budget is $1.2M..."],
        ground_truth="The Q3 budget is $1.2 million"  # Optional
    )

    print(f"Faithfulness: {result.faithfulness}")
    print(f"Overall: {result.overall_score}")
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import time

from .quality_metrics import ResponseQualityChecker, QualityMetrics

logger = logging.getLogger(__name__)

# Try to import RAGAS
try:
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall
    )
    from datasets import Dataset
    RAGAS_AVAILABLE = True
    RAGAS_VERSION = "0.1+"  # New API uses 'reference' instead of 'ground_truth'
    logger.info("RAGAS library available for evaluation")
except ImportError:
    RAGAS_AVAILABLE = False
    RAGAS_VERSION = None
    logger.info("RAGAS not installed - using lightweight metrics")

# Try to import LangChain for RAGAS LLM wrapper
try:
    from langchain_openai import ChatOpenAI
    from langchain_groq import ChatGroq
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.info("LangChain not available - RAGAS will use default LLM")


@dataclass
class EvaluationResult:
    """Result of RAG response evaluation."""
    # Core RAGAS metrics
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: Optional[float] = None

    # Derived scores
    overall_score: float = 0.0
    quality_grade: str = "unknown"  # A, B, C, D, F

    # Metadata
    evaluation_method: str = "unknown"  # 'ragas' or 'lightweight'
    evaluation_time_ms: float = 0.0
    error: Optional[str] = None

    # Detailed breakdown
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "faithfulness": round(self.faithfulness, 3),
            "answer_relevancy": round(self.answer_relevancy, 3),
            "context_precision": round(self.context_precision, 3),
            "context_recall": round(self.context_recall, 3) if self.context_recall else None,
            "overall_score": round(self.overall_score, 3),
            "quality_grade": self.quality_grade,
            "evaluation_method": self.evaluation_method,
            "evaluation_time_ms": round(self.evaluation_time_ms, 1),
            "error": self.error,
            "details": self.details
        }

    @property
    def passed(self) -> bool:
        """Check if evaluation meets minimum quality threshold."""
        return self.overall_score >= 0.6 and self.quality_grade in ['A', 'B', 'C']


class RAGASEvaluator:
    """
    RAGAS-based evaluation for RAG quality metrics.

    Supports two evaluation modes:
    1. Full RAGAS (if library installed): Uses LLM-based evaluation
    2. Lightweight (fallback): Uses heuristic-based metrics

    The evaluator automatically selects the best available method.
    """

    def __init__(
        self,
        llm_client=None,
        embedding_model=None,
        enable_async: bool = True,
        use_lightweight_fallback: bool = True
    ):
        """
        Initialize evaluator.

        Args:
            llm_client: LLM client for RAGAS evaluation (optional)
            embedding_model: Embedding model for semantic similarity
            enable_async: Enable async evaluation
            use_lightweight_fallback: Use lightweight metrics if RAGAS fails
        """
        self.llm_client = llm_client
        self.embedding_model = embedding_model
        self.enable_async = enable_async
        self.use_lightweight_fallback = use_lightweight_fallback

        # Initialize lightweight checker
        self.quality_checker = ResponseQualityChecker(
            embedding_model=embedding_model
        )

        # RAGAS configuration
        self._ragas_metrics = None
        if RAGAS_AVAILABLE:
            self._setup_ragas_metrics()

        logger.info(
            f"RAGASEvaluator initialized: "
            f"RAGAS={'available' if RAGAS_AVAILABLE else 'not available'}, "
            f"LLM={'provided' if llm_client else 'none'}"
        )

    def _setup_ragas_metrics(self):
        """Configure RAGAS metrics."""
        # Note: In RAGAS 0.1+, context_precision requires 'reference' column
        # We'll only use metrics that don't require reference by default
        self._ragas_metrics_no_reference = [
            faithfulness,
            answer_relevancy,
        ]
        self._ragas_metrics_with_reference = [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ]
        logger.info("RAGAS metrics configured (with/without reference support)")

    async def evaluate_response(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None
    ) -> EvaluationResult:
        """
        Evaluate a RAG response.

        Args:
            question: User's query
            answer: Generated response
            contexts: Retrieved documents used for generation
            ground_truth: Optional expected answer for recall calculation

        Returns:
            EvaluationResult with metric scores
        """
        start_time = time.time()

        # DISABLED: Full RAGAS evaluation has issues with Groq:
        # - Groq doesn't support n > 1 parameter (required by RAGAS)
        # - High token usage (10K+ tokens per evaluation)
        # - Rate limiting issues
        # Using lightweight evaluation instead (faster, more reliable)
        #
        # To re-enable full RAGAS, uncomment the block below and ensure
        # OPENAI_API_KEY is set (OpenAI supports n > 1)
        #
        # if RAGAS_AVAILABLE and self.llm_client:
        #     try:
        #         result = await self._evaluate_with_ragas(
        #             question, answer, contexts, ground_truth
        #         )
        #         result.evaluation_time_ms = (time.time() - start_time) * 1000
        #         return result
        #     except Exception as e:
        #         logger.warning(f"RAGAS evaluation failed: {e}")

        # Use lightweight evaluation (fast, reliable, works with any LLM)
        logger.info("Using lightweight evaluation (full RAGAS disabled for performance)")
        result = await self._evaluate_lightweight(
            question, answer, contexts, ground_truth
        )
        result.evaluation_time_ms = (time.time() - start_time) * 1000
        return result

    async def _evaluate_with_ragas(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str]
    ) -> EvaluationResult:
        """Evaluate using RAGAS library."""
        logger.info("Evaluating with RAGAS")

        # Prepare dataset - RAGAS 0.1+ uses 'reference' instead of 'ground_truth'
        data = {
            "question": [question],
            "answer": [answer],
            "contexts": [contexts],
        }

        # Select metrics based on whether ground_truth/reference is provided
        # In RAGAS 0.1+, context_precision requires 'reference' column
        if ground_truth:
            data["reference"] = [ground_truth]  # New column name in RAGAS 0.1+
            metrics_to_use = list(self._ragas_metrics_with_reference)
            logger.info(f"Using full RAGAS metrics with reference (ground_truth provided)")
        else:
            # Without ground_truth, only use metrics that don't require reference
            metrics_to_use = list(self._ragas_metrics_no_reference)
            logger.info(f"Using RAGAS metrics without reference (faithfulness, answer_relevancy only)")

        dataset = Dataset.from_dict(data)

        # Truncate contexts to avoid token limits (RAGAS can be token-heavy)
        MAX_CONTEXT_CHARS = 8000  # ~2000 tokens
        truncated_contexts = []
        total_chars = 0
        for ctx in contexts:
            if total_chars + len(ctx) > MAX_CONTEXT_CHARS:
                # Truncate this context
                remaining = MAX_CONTEXT_CHARS - total_chars
                if remaining > 100:
                    truncated_contexts.append(ctx[:remaining] + "...")
                break
            truncated_contexts.append(ctx)
            total_chars += len(ctx)

        if len(truncated_contexts) < len(contexts):
            logger.info(f"Truncated contexts from {len(contexts)} to {len(truncated_contexts)} for RAGAS evaluation")
            # Update dataset with truncated contexts
            data["contexts"] = [truncated_contexts]
            dataset = Dataset.from_dict(data)

        # Configure LLM for RAGAS if LangChain is available
        # Use dedicated evaluator API key to avoid rate limits on main LLM
        llm = None
        embeddings = None
        if LANGCHAIN_AVAILABLE and self.llm_client:
            try:
                import os
                # Priority: OpenAI > Dedicated Groq Evaluator Key > Main Groq Key
                if os.getenv("OPENAI_API_KEY"):
                    llm = ChatOpenAI(
                        model="gpt-4o-mini",
                        temperature=0
                    )
                    logger.info("Using OpenAI LLM for RAGAS evaluation")
                elif os.getenv("GROQ_EVALUATOR_API_KEY"):
                    # Use dedicated evaluator key (separate from main LLM)
                    llm = ChatGroq(
                        model="llama-3.1-8b-instant",
                        temperature=0,
                        api_key=os.getenv("GROQ_EVALUATOR_API_KEY")
                    )
                    logger.info("Using dedicated Groq Evaluator LLM for RAGAS (separate rate limits)")
                elif os.getenv("GROQ_API_KEY"):
                    # Fallback to main Groq key
                    llm = ChatGroq(
                        model="llama-3.1-8b-instant",
                        temperature=0
                    )
                    logger.info("Using main Groq LLM for RAGAS evaluation (may hit rate limits)")
            except Exception as e:
                logger.warning(f"Could not configure LangChain LLM for RAGAS: {e}")

        # Run evaluation
        def run_evaluation():
            eval_kwargs = {"dataset": dataset, "metrics": metrics_to_use}
            if llm:
                eval_kwargs["llm"] = llm
            if embeddings:
                eval_kwargs["embeddings"] = embeddings
            return ragas_evaluate(**eval_kwargs)

        if self.enable_async:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_evaluation)
        else:
            result = run_evaluation()

        # Extract scores - RAGAS 0.1+ returns EvaluationResult object, not dict
        # Handle both old dict format and new object format
        def get_score(key: str, default: float = 0.0) -> float:
            # Try object attribute first (newer RAGAS)
            if hasattr(result, key):
                val = getattr(result, key)
                return float(val) if val is not None else default
            # Try dict-style access (older RAGAS)
            if hasattr(result, 'get'):
                val = result.get(key, default)
                return float(val) if val is not None else default
            # Try __getitem__ (pandas-like)
            try:
                val = result[key]
                # If it's a Series/array, get first value
                if hasattr(val, 'iloc'):
                    val = val.iloc[0]
                elif hasattr(val, '__iter__') and not isinstance(val, str):
                    val = list(val)[0] if len(list(val)) > 0 else default
                return float(val) if val is not None else default
            except (KeyError, TypeError, IndexError):
                pass
            return default

        faithfulness_score = get_score("faithfulness", 0)
        relevancy_score = get_score("answer_relevancy", 0)
        # context_precision only available when reference is provided
        precision_score = get_score("context_precision", 0) if ground_truth else 0
        recall_score = get_score("context_recall") if ground_truth else None

        # Calculate overall score
        overall = self._calculate_overall_score(
            faithfulness_score,
            relevancy_score,
            precision_score,
            recall_score
        )

        return EvaluationResult(
            faithfulness=faithfulness_score,
            answer_relevancy=relevancy_score,
            context_precision=precision_score,
            context_recall=recall_score,
            overall_score=overall,
            quality_grade=self._score_to_grade(overall),
            evaluation_method="ragas",
            details={
                "metrics_used": [m.name for m in metrics_to_use],
                "has_ground_truth": ground_truth is not None,
                "llm_used": "groq" if llm and "Groq" in str(type(llm)) else "openai" if llm else "default"
            }
        )

    async def _evaluate_lightweight(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str]
    ) -> EvaluationResult:
        """Evaluate using lightweight heuristic metrics."""
        logger.info("Evaluating with lightweight metrics")

        # Use quality checker
        metrics = self.quality_checker.evaluate(
            question=question,
            answer=answer,
            contexts=contexts
        )

        # Map to RAGAS-like metrics
        faithfulness_score = metrics.faithfulness_estimate
        relevancy_score = metrics.answer_relevance
        precision_score = metrics.context_coverage

        # Calculate recall if ground truth provided
        recall_score = None
        if ground_truth:
            recall_score = self._calculate_recall(answer, ground_truth, contexts)

        # Calculate overall
        overall = self._calculate_overall_score(
            faithfulness_score,
            relevancy_score,
            precision_score,
            recall_score
        )

        return EvaluationResult(
            faithfulness=faithfulness_score,
            answer_relevancy=relevancy_score,
            context_precision=precision_score,
            context_recall=recall_score,
            overall_score=overall,
            quality_grade=self._score_to_grade(overall),
            evaluation_method="lightweight",
            details={
                "citation_quality": metrics.citation_quality,
                "response_completeness": metrics.response_completeness,
                "raw_metrics": metrics.to_dict()
            }
        )

    def _calculate_overall_score(
        self,
        faithfulness: float,
        relevancy: float,
        precision: float,
        recall: Optional[float]
    ) -> float:
        """Calculate weighted overall score."""
        if recall is not None:
            weights = {
                'faithfulness': 0.35,
                'relevancy': 0.30,
                'precision': 0.20,
                'recall': 0.15
            }
            total = (
                faithfulness * weights['faithfulness'] +
                relevancy * weights['relevancy'] +
                precision * weights['precision'] +
                recall * weights['recall']
            )
        else:
            weights = {
                'faithfulness': 0.40,
                'relevancy': 0.35,
                'precision': 0.25
            }
            total = (
                faithfulness * weights['faithfulness'] +
                relevancy * weights['relevancy'] +
                precision * weights['precision']
            )

        return min(1.0, max(0.0, total))

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 0.9:
            return 'A'
        elif score >= 0.8:
            return 'B'
        elif score >= 0.7:
            return 'C'
        elif score >= 0.6:
            return 'D'
        else:
            return 'F'

    def _calculate_recall(
        self,
        answer: str,
        ground_truth: str,
        contexts: List[str]
    ) -> float:
        """
        Calculate context recall (how much ground truth is covered).

        This is a simplified version - full RAGAS uses LLM-based evaluation.
        """
        import re

        # Extract key terms from ground truth
        gt_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', ground_truth.lower()))
        gt_words -= self.quality_checker.STOP_WORDS

        if not gt_words:
            return 0.5

        # Check how many ground truth terms appear in contexts
        all_context = " ".join(contexts).lower()
        context_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', all_context))

        covered = len(gt_words & context_words)
        recall = covered / len(gt_words)

        return min(1.0, recall)

    async def batch_evaluate(
        self,
        samples: List[Dict[str, Any]]
    ) -> List[EvaluationResult]:
        """
        Evaluate multiple samples.

        Args:
            samples: List of dicts with keys:
                - question: str
                - answer: str
                - contexts: List[str]
                - ground_truth: Optional[str]

        Returns:
            List of EvaluationResult objects
        """
        results = []

        for sample in samples:
            result = await self.evaluate_response(
                question=sample['question'],
                answer=sample['answer'],
                contexts=sample['contexts'],
                ground_truth=sample.get('ground_truth')
            )
            results.append(result)

        return results

    def get_aggregate_metrics(
        self,
        results: List[EvaluationResult]
    ) -> Dict[str, Any]:
        """
        Calculate aggregate metrics across multiple evaluations.

        Args:
            results: List of evaluation results

        Returns:
            Aggregated statistics
        """
        if not results:
            return {"error": "No results to aggregate"}

        valid_results = [r for r in results if r.error is None]

        if not valid_results:
            return {"error": "All evaluations failed"}

        # Calculate averages
        faithfulness_avg = sum(r.faithfulness for r in valid_results) / len(valid_results)
        relevancy_avg = sum(r.answer_relevancy for r in valid_results) / len(valid_results)
        precision_avg = sum(r.context_precision for r in valid_results) / len(valid_results)
        overall_avg = sum(r.overall_score for r in valid_results) / len(valid_results)

        # Calculate with recall if available
        recall_results = [r for r in valid_results if r.context_recall is not None]
        recall_avg = None
        if recall_results:
            recall_avg = sum(r.context_recall for r in recall_results) / len(recall_results)

        # Grade distribution
        grade_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        for r in valid_results:
            grade_counts[r.quality_grade] = grade_counts.get(r.quality_grade, 0) + 1

        pass_rate = sum(1 for r in valid_results if r.passed) / len(valid_results)

        return {
            "total_samples": len(results),
            "successful_evaluations": len(valid_results),
            "failed_evaluations": len(results) - len(valid_results),
            "metrics": {
                "faithfulness_avg": round(faithfulness_avg, 3),
                "answer_relevancy_avg": round(relevancy_avg, 3),
                "context_precision_avg": round(precision_avg, 3),
                "context_recall_avg": round(recall_avg, 3) if recall_avg else None,
                "overall_avg": round(overall_avg, 3)
            },
            "grade_distribution": grade_counts,
            "pass_rate": round(pass_rate, 3),
            "evaluation_method": valid_results[0].evaluation_method if valid_results else "unknown"
        }

    def is_ragas_available(self) -> bool:
        """Check if RAGAS library is available."""
        return RAGAS_AVAILABLE

    def get_capabilities(self) -> Dict[str, Any]:
        """Get evaluator capabilities."""
        return {
            "ragas_available": RAGAS_AVAILABLE,
            "llm_available": self.llm_client is not None,
            "embedding_available": self.embedding_model is not None,
            "async_enabled": self.enable_async,
            "lightweight_fallback": self.use_lightweight_fallback,
            "supported_metrics": [
                "faithfulness",
                "answer_relevancy",
                "context_precision",
                "context_recall (with ground_truth)"
            ]
        }
