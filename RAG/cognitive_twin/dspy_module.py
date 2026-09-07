"""
DSPy Cognitive Response Module - For automatic prompt optimization.

This module provides DSPy-compatible signatures and modules for
optimizing the cognitive twin prompts using RAGAS metrics.

DSPy allows us to:
1. Define structured input/output signatures
2. Automatically optimize prompts using training data
3. Use MIPROv2 optimizer for few-shot selection
4. Measure and improve response quality

Key principle: Instead of manually tweaking prompts, let DSPy learn
the optimal prompt structure from evaluation data.
"""

import logging
import asyncio
from typing import Optional, List, Dict, Any

try:
    import dspy
    from dspy import Signature, InputField, OutputField
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    # Create placeholder classes if DSPy not installed
    class Signature:
        pass
    class InputField:
        def __init__(self, *args, **kwargs): pass
    class OutputField:
        def __init__(self, *args, **kwargs): pass

# Import RAGAS evaluator
try:
    from evaluation.ragas_evaluator import RAGASEvaluator, EvaluationResult
    RAGAS_EVALUATOR_AVAILABLE = True
except ImportError:
    RAGAS_EVALUATOR_AVAILABLE = False
    RAGASEvaluator = None
    EvaluationResult = None

from .config import COGNITIVE_CONFIG
from .profile_loader import get_cognitive_profile_loader

logger = logging.getLogger(__name__)


# ============================================================================
# DSPy Signatures
# ============================================================================

if DSPY_AVAILABLE:

    class CognitiveResponseSignature(dspy.Signature):
        """
        DSPy signature for cognitive twin responses.

        This defines the input/output structure that DSPy will optimize.
        """
        # Inputs
        query: str = dspy.InputField(desc="User's question or request")
        executive_identity: str = dspy.InputField(desc="Who you are (name, title)")
        thinking_patterns: str = dspy.InputField(desc="Your reasoning frameworks")
        situation_context: str = dspy.InputField(desc="Situational awareness")
        relationship_context: str = dspy.InputField(desc="Communication adaptation")
        retrieved_context: str = dspy.InputField(desc="Relevant information sources")

        # Output
        response: str = dspy.OutputField(desc="Response in executive's voice and thinking style")


    class PersonalityConsistencySignature(dspy.Signature):
        """
        Signature for evaluating personality consistency.

        Used to score whether response matches executive's voice.
        """
        executive_name: str = dspy.InputField(desc="Executive's name")
        executive_style: str = dspy.InputField(desc="Executive's communication style description")
        response: str = dspy.InputField(desc="Generated response")

        consistency_score: float = dspy.OutputField(desc="Score from 0-1 for personality match")
        reasoning: str = dspy.OutputField(desc="Explanation of score")


    class CognitiveConsistencySignature(dspy.Signature):
        """
        Signature for evaluating cognitive consistency.

        Used to score whether response follows executive's reasoning patterns.
        """
        reasoning_patterns: str = dspy.InputField(desc="Executive's thinking patterns")
        response: str = dspy.InputField(desc="Generated response")

        consistency_score: float = dspy.OutputField(desc="Score from 0-1 for reasoning match")
        reasoning: str = dspy.OutputField(desc="Explanation of score")


# ============================================================================
# DSPy Modules
# ============================================================================

class CognitiveResponseModule:
    """
    DSPy module for generating cognitive twin responses.

    Can be optimized with MIPROv2 using RAGAS + personality metrics.
    """

    def __init__(self, model_name: str = "gpt-4"):
        """
        Initialize the CognitiveResponseModule.

        Args:
            model_name: Name of the LLM to use
        """
        self._profile_loader = get_cognitive_profile_loader()

        if DSPY_AVAILABLE:
            self._predictor = dspy.ChainOfThought(CognitiveResponseSignature)
        else:
            self._predictor = None
            logger.warning("DSPy not available - module will use fallback")

        logger.info(f"CognitiveResponseModule initialized (DSPy: {DSPY_AVAILABLE})")

    def forward(
        self,
        query: str,
        profile_id: str,
        thinking_patterns: str,
        situation_context: str,
        relationship_context: str,
        retrieved_context: str,
    ) -> str:
        """
        Generate cognitive response using DSPy.

        Args:
            query: User's question
            profile_id: Executive profile ID
            thinking_patterns: Formatted thinking patterns
            situation_context: Formatted situation context
            relationship_context: Formatted relationship context
            retrieved_context: Formatted retrieved sources

        Returns:
            Generated response
        """
        if not DSPY_AVAILABLE or not self._predictor:
            return self._fallback_generate(
                query, profile_id, thinking_patterns,
                situation_context, relationship_context, retrieved_context
            )

        # Load profile for identity
        profile = self._profile_loader.load_profile(profile_id)
        if not profile:
            return self._fallback_generate(
                query, profile_id, thinking_patterns,
                situation_context, relationship_context, retrieved_context
            )

        executive_identity = f"You are {profile.name}, {profile.title}."

        # Call DSPy predictor
        try:
            result = self._predictor(
                query=query,
                executive_identity=executive_identity,
                thinking_patterns=thinking_patterns,
                situation_context=situation_context,
                relationship_context=relationship_context,
                retrieved_context=retrieved_context,
            )
            return result.response
        except Exception as e:
            logger.error(f"DSPy prediction failed: {e}")
            return self._fallback_generate(
                query, profile_id, thinking_patterns,
                situation_context, relationship_context, retrieved_context
            )

    def _fallback_generate(
        self,
        query: str,
        profile_id: str,
        thinking_patterns: str,
        situation_context: str,
        relationship_context: str,
        retrieved_context: str,
    ) -> str:
        """Fallback generation without DSPy."""
        # This would integrate with the existing LLM call
        # For now, return placeholder
        return f"[Fallback response for: {query}]"


# ============================================================================
# DSPy Metrics for Optimization
# ============================================================================

def personality_consistency_metric(
    example: Dict[str, Any],
    prediction: str,
    trace: Optional[Any] = None,
) -> float:
    """
    Metric for measuring personality consistency.

    Used by DSPy optimizer to evaluate responses.

    Args:
        example: Training example with expected attributes
        prediction: Model's predicted response
        trace: Optional DSPy trace

    Returns:
        Score from 0 to 1
    """
    if not DSPY_AVAILABLE:
        return 0.5

    try:
        # Use LLM to evaluate consistency
        evaluator = dspy.ChainOfThought(PersonalityConsistencySignature)
        result = evaluator(
            executive_name=example.get("executive_name", ""),
            executive_style=example.get("executive_style", ""),
            response=prediction,
        )
        return result.consistency_score
    except Exception as e:
        logger.warning(f"Personality metric failed: {e}")
        return 0.5


def cognitive_consistency_metric(
    example: Dict[str, Any],
    prediction: str,
    trace: Optional[Any] = None,
) -> float:
    """
    Metric for measuring cognitive/reasoning consistency.

    Args:
        example: Training example with reasoning patterns
        prediction: Model's predicted response
        trace: Optional DSPy trace

    Returns:
        Score from 0 to 1
    """
    if not DSPY_AVAILABLE:
        return 0.5

    try:
        evaluator = dspy.ChainOfThought(CognitiveConsistencySignature)
        result = evaluator(
            reasoning_patterns=example.get("reasoning_patterns", ""),
            response=prediction,
        )
        return result.consistency_score
    except Exception as e:
        logger.warning(f"Cognitive metric failed: {e}")
        return 0.5


def ragas_relevance_metric(
    example: Dict[str, Any],
    prediction: str,
    trace: Optional[Any] = None,
) -> float:
    """
    Evaluate response relevance using RAGAS metrics.

    Uses the RAGASEvaluator to get:
    - faithfulness: Is response grounded in context?
    - answer_relevancy: Does response address the question?
    - context_precision: Are retrieved docs relevant?

    Args:
        example: Training example with 'query', 'contexts', optional 'ground_truth'
        prediction: Model's predicted response
        trace: Optional DSPy trace

    Returns:
        RAGAS overall score from 0 to 1
    """
    if not RAGAS_EVALUATOR_AVAILABLE:
        logger.debug("RAGAS evaluator not available, using default relevance score")
        return 0.7  # Default fallback

    try:
        # Get data from example
        query = example.get("query", "")
        contexts = example.get("contexts", [])
        ground_truth = example.get("expected_response") or example.get("ground_truth")

        if not query:
            logger.warning("No query in example for RAGAS evaluation")
            return 0.7

        # Create evaluator
        evaluator = RAGASEvaluator(use_lightweight_fallback=True)

        # Run evaluation (async -> sync wrapper)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                evaluator.evaluate_response(
                    question=query,
                    answer=prediction,
                    contexts=contexts if contexts else [prediction],  # Use response as context if none
                    ground_truth=ground_truth
                )
            )
        finally:
            loop.close()

        logger.debug(
            f"RAGAS evaluation: faithfulness={result.faithfulness:.2f}, "
            f"relevancy={result.answer_relevancy:.2f}, "
            f"overall={result.overall_score:.2f}"
        )

        return result.overall_score

    except Exception as e:
        logger.warning(f"RAGAS relevance metric failed: {e}")
        return 0.7  # Fallback on error


def combined_quality_metric(
    example: Dict[str, Any],
    prediction: str,
    trace: Optional[Any] = None,
) -> float:
    """
    Combined metric: RAGAS quality + personality + cognitive consistency.

    This is the main metric for DSPy optimization, combining:
    - RAGAS metrics (faithfulness, relevancy, precision) - 40%
    - Personality consistency (voice match) - 30%
    - Cognitive consistency (reasoning pattern match) - 30%

    Args:
        example: Training example with:
            - query: The question
            - contexts: Retrieved documents
            - expected_response: Ground truth (optional)
            - executive_name, executive_style: For personality
            - reasoning_patterns: For cognitive consistency
        prediction: Model's predicted response
        trace: Optional DSPy trace

    Returns:
        Combined score from 0 to 1
    """
    # Weight configuration
    weights = {
        "personality": 0.3,
        "cognitive": 0.3,
        "relevance": 0.4,  # RAGAS metrics
    }

    scores = {}

    # Personality consistency (LLM-based evaluation)
    scores["personality"] = personality_consistency_metric(example, prediction, trace)

    # Cognitive consistency (LLM-based evaluation)
    scores["cognitive"] = cognitive_consistency_metric(example, prediction, trace)

    # RAGAS relevance metrics (faithfulness + answer_relevancy + context_precision)
    scores["relevance"] = ragas_relevance_metric(example, prediction, trace)

    # Weighted combination
    total = sum(weights[k] * scores[k] for k in weights)

    logger.info(
        f"Combined quality metric: personality={scores['personality']:.2f}, "
        f"cognitive={scores['cognitive']:.2f}, relevance={scores['relevance']:.2f}, "
        f"total={total:.2f}"
    )

    return total


# ============================================================================
# DSPy Optimizer Setup
# ============================================================================

def create_optimizer(
    trainset: List[Dict[str, Any]],
    metric: callable = combined_quality_metric,
    num_candidates: int = 10,
) -> Optional[Any]:
    """
    Create DSPy optimizer for cognitive twin.

    Uses MIPROv2 for automatic prompt optimization.

    Args:
        trainset: List of training examples
        metric: Metric function for evaluation
        num_candidates: Number of candidates to consider

    Returns:
        Configured optimizer or None if DSPy not available
    """
    if not DSPY_AVAILABLE:
        logger.warning("DSPy not available - cannot create optimizer")
        return None

    try:
        from dspy.teleprompt import MIPROv2

        optimizer = MIPROv2(
            metric=metric,
            num_candidates=num_candidates,
            init_temperature=1.0,
        )

        logger.info(f"Created MIPROv2 optimizer with {num_candidates} candidates")
        return optimizer

    except Exception as e:
        logger.error(f"Failed to create optimizer: {e}")
        return None


def optimize_cognitive_module(
    module: CognitiveResponseModule,
    trainset: List[Dict[str, Any]],
    valset: Optional[List[Dict[str, Any]]] = None,
) -> CognitiveResponseModule:
    """
    Optimize the cognitive response module using training data.

    Args:
        module: CognitiveResponseModule to optimize
        trainset: Training examples
        valset: Optional validation examples

    Returns:
        Optimized module
    """
    if not DSPY_AVAILABLE:
        logger.warning("DSPy not available - returning unoptimized module")
        return module

    optimizer = create_optimizer(trainset)
    if not optimizer:
        return module

    try:
        optimized = optimizer.compile(
            module,
            trainset=trainset,
            valset=valset,
        )
        logger.info("Successfully optimized cognitive module")
        return optimized

    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        return module


# ============================================================================
# Training Data Generation
# ============================================================================

def generate_training_example(
    query: str,
    profile_id: str,
    expected_response: str,
    quality_score: float = 0.8,
) -> Dict[str, Any]:
    """
    Generate a training example for DSPy optimization.

    Args:
        query: User's query
        profile_id: Executive profile ID
        expected_response: Human-validated ideal response
        quality_score: Quality score of the example (0-1)

    Returns:
        Training example dict
    """
    profile_loader = get_cognitive_profile_loader()
    profile = profile_loader.load_profile(profile_id)

    if not profile:
        return {}

    return {
        "query": query,
        "profile_id": profile_id,
        "executive_name": profile.name,
        "executive_style": f"Warmth: {profile.communication_style.warmth_scale}/10, "
                          f"Directness: {profile.communication_style.directness_scale}/10",
        "reasoning_patterns": ", ".join(profile.thinking_patterns.framework_examples),
        "expected_response": expected_response,
        "quality_score": quality_score,
    }


# Singleton module instance
_cognitive_module: Optional[CognitiveResponseModule] = None


def get_cognitive_response_module() -> CognitiveResponseModule:
    """Get the singleton CognitiveResponseModule instance."""
    global _cognitive_module
    if _cognitive_module is None:
        _cognitive_module = CognitiveResponseModule()
    return _cognitive_module
