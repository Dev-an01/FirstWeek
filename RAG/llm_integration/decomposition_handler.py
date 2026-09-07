"""
Decomposition Handler for AI Officer RAG System
==============================================

Orchestrates the query decomposition pipeline with comprehensive error handling,
performance monitoring, and context preservation.

This module handles:
1. Query analysis for decomposition indicators
2. Sub-query generation with proper formatting
3. Independent sub-query processing
4. Result synthesis with coherence checks
5. Performance monitoring and optimization
"""

import logging
import time
import json
import traceback
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum

# Import dataclasses from query_decomposition
from .query_decomposition import (
    QueryType, DecompositionStrategy, SubQuery, SubQueryResult, DecompositionResult
)
# Import actual implementation classes from hybrid_retrieval
# Note: Import at module level causes circular import, so we'll import inside __init__
from .base_client import LLMError

logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Status of decomposition processing"""
    INITIALIZING = "initializing"
    ANALYZING = "analyzing"
    DECOMPOSING = "decomposing"
    PROCESSING = "processing"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"
    FALLBACK = "fallback"


@dataclass
class ProcessingMetrics:
    """Metrics for decomposition processing"""
    total_processing_time_ms: float = 0.0
    analysis_time_ms: float = 0.0
    decomposition_time_ms: float = 0.0
    sub_query_processing_time_ms: float = 0.0
    synthesis_time_ms: float = 0.0
    sub_query_count: int = 0
    successful_sub_queries: int = 0
    failed_sub_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    llm_calls: int = 0
    error_count: int = 0
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "total_processing_time_ms": self.total_processing_time_ms,
            "analysis_time_ms": self.analysis_time_ms,
            "decomposition_time_ms": self.decomposition_time_ms,
            "sub_query_processing_time_ms": self.sub_query_processing_time_ms,
            "synthesis_time_ms": self.synthesis_time_ms,
            "sub_query_count": self.sub_query_count,
            "successful_sub_queries": self.successful_sub_queries,
            "failed_sub_queries": self.failed_sub_queries,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "llm_calls": self.llm_calls,
            "error_count": self.error_count,
            "warnings": self.warnings
        }


@dataclass
class ProcessingContext:
    """Context preserved across sub-query processing"""
    original_query: str
    executive_id: str
    user_context: Dict[str, Any]
    entities: List[str]
    query_analysis: Dict[str, Any]
    accumulated_findings: List[Dict[str, Any]] = field(default_factory=list)
    shared_context: Dict[str, Any] = field(default_factory=dict)
    processing_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_finding(self, finding: Dict[str, Any]):
        """Add a finding to accumulated context"""
        self.accumulated_findings.append(finding)
    
    def add_processing_step(self, step: Dict[str, Any]):
        """Add a processing step to history"""
        self.processing_history.append(step)
    
    def update_shared_context(self, key: str, value: Any):
        """Update shared context"""
        self.shared_context[key] = value


class DecompositionHandler:
    """
    Main orchestrator for query decomposition functionality.
    
    Coordinates complexity detection, LLM decomposition, sub-query processing,
    and answer synthesis with comprehensive error handling and monitoring.
    """
    
    def __init__(
        self,
        retrieval_manager,
        llm_provider: str = "openai",
        llm_config: Dict = None,
        config: Dict = None
    ):
        """
        Initialize the decomposition handler.
        
        Args:
            retrieval_manager: HybridRetrievalManager instance
            llm_provider: LLM provider for decomposition/synthesis
            llm_config: LLM configuration
            config: Additional configuration
        """
        self.retrieval_manager = retrieval_manager
        self.llm_provider = llm_provider
        self.llm_config = llm_config or {}
        self.config = config or {}

        # Import components locally to avoid circular imports
        from hybrid_retrieval.query_decomposer import (
            QueryComplexityDetector, LLMQueryDecomposer, AnswerSynthesizer
        )

        # Initialize components
        self.complexity_detector = QueryComplexityDetector(
            config=self.config.get("complexity_indicators", {})
        )
        self.llm_decomposer = LLMQueryDecomposer(llm_provider, llm_config)
        self.answer_synthesizer = AnswerSynthesizer(llm_provider, llm_config)
        
        # Performance tracking
        self.metrics = ProcessingMetrics()
        self.processing_history: List[Dict[str, Any]] = []
        
        # Configuration
        self.enable_caching = self.config.get("enable_caching", True)
        self.enable_monitoring = self.config.get("enable_monitoring", True)
        self.max_sub_queries = self.config.get("max_sub_queries", 4)
        self.min_confidence_threshold = self.config.get("min_confidence_threshold", 0.5)
        
        # Simple cache for decomposition results
        self._decomposition_cache = {}
        
        logger.info("DecompositionHandler initialized with all components")
    
    def process_query(
        self,
        query: str,
        executive_id: str,
        user_context: Dict = None,
        entities: List[str] = None,
        query_analysis: Dict = None
    ) -> DecompositionResult:
        """
        Process a query with intelligent decomposition if needed.
        
        Args:
            query: The input query
            executive_id: Executive context ID
            user_context: User context for RBAC
            entities: Pre-extracted entities
            query_analysis: Pre-computed query analysis
            
        Returns:
            DecompositionResult with processing details
        """
        start_time = time.time()
        status = ProcessingStatus.INITIALIZING
        
        # Initialize processing context
        context = self._initialize_context(query, executive_id, user_context, entities, query_analysis)
        
        try:
            # Step 1: Analyze query complexity
            status = ProcessingStatus.ANALYZING
            analysis_start = time.time()
            
            if not query_analysis:
                query_analysis = self.complexity_detector.detect_complexity(query, entities)
            
            context.query_analysis = query_analysis
            self.metrics.analysis_time_ms = (time.time() - analysis_start) * 1000
            
            needs_decomposition = query_analysis['needs_decomposition']
            decomposition_confidence = query_analysis['confidence']
            strategy = DecompositionStrategy(query_analysis.get('recommended_strategy', 'entity_based'))
            
            if not needs_decomposition:
                logger.info(f"Query doesn't need decomposition (confidence: {decomposition_confidence:.2f})")
                return self._create_no_decomposition_result(query, decomposition_confidence, start_time)
            
            # Step 2: Check cache
            if self.enable_caching:
                cached_result = self._check_cache(query, executive_id)
                if cached_result:
                    self.metrics.cache_hits += 1
                    logger.info("Using cached decomposition result")
                    return cached_result
                else:
                    self.metrics.cache_misses += 1
            
            # Step 3: Decompose query
            status = ProcessingStatus.DECOMPOSING
            decomposition_start = time.time()
            
            sub_queries, decomp_confidence = self.llm_decomposer.decompose_query(
                query, entities, strategy
            )
            
            self.metrics.decomposition_time_ms = (time.time() - decomposition_start) * 1000
            self.metrics.llm_calls += 1
            
            if not sub_queries or len(sub_queries) > self.max_sub_queries:
                logger.warning("LLM decomposition failed or produced too many sub-queries")
                return self._handle_decomposition_failure(query, context, start_time)
            
            # Step 4: Process sub-queries
            status = ProcessingStatus.PROCESSING
            processing_start = time.time()
            
            sub_query_results = self._process_sub_queries(sub_queries, context)
            
            self.metrics.sub_query_processing_time_ms = (time.time() - processing_start) * 1000
            self.metrics.sub_query_count = len(sub_queries)
            self.metrics.successful_sub_queries = len([r for r in sub_query_results if r.confidence > 0.3])
            self.metrics.failed_sub_queries = len(sub_query_results) - self.metrics.successful_sub_queries
            
            # Step 5: Synthesize answer
            status = ProcessingStatus.SYNTHESIZING
            synthesis_start = time.time()
            
            synthesized_answer, synthesis_confidence = self.answer_synthesizer.synthesize_answer(
                query, sub_query_results, strategy
            )
            
            self.metrics.synthesis_time_ms = (time.time() - synthesis_start) * 1000
            self.metrics.llm_calls += 1
            
            # Step 6: Build final result
            status = ProcessingStatus.COMPLETED
            total_time_ms = (time.time() - start_time) * 1000
            self.metrics.total_processing_time_ms = total_time_ms
            
            result = self._build_decomposition_result(
                query, sub_queries, sub_query_results, synthesized_answer,
                decomposition_confidence, synthesis_confidence, strategy, context, total_time_ms
            )
            
            # Cache result
            if self.enable_caching:
                self._cache_result(query, executive_id, result)
            
            # Record processing history
            if self.enable_monitoring:
                self._record_processing_history(query, context, result, status.value)
            
            logger.info(
                f"Query decomposition completed in {total_time_ms:.1f}ms "
                f"({len(sub_queries)} sub-queries, confidence: {synthesis_confidence:.2f})"
            )
            
            return result
            
        except Exception as e:
            status = ProcessingStatus.FAILED
            self.metrics.error_count += 1
            logger.error(f"Decomposition processing failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return self._handle_processing_error(query, context, e, start_time)
    
    def _initialize_context(
        self,
        query: str,
        executive_id: str,
        user_context: Dict = None,
        entities: List[str] = None,
        query_analysis: Dict = None
    ) -> ProcessingContext:
        """Initialize processing context"""
        if user_context is None:
            user_context = {
                "user_id": "unknown",
                "role": "employee",
                "allowed_scopes": ["public", "internal"]
            }
        
        if entities is None:
            entities = []
        
        return ProcessingContext(
            original_query=query,
            executive_id=executive_id,
            user_context=user_context,
            entities=entities,
            query_analysis=query_analysis or {}
        )
    
    def _process_sub_queries(
        self,
        sub_queries: List[SubQuery],
        context: ProcessingContext
    ) -> List[SubQueryResult]:
        """Process sub-queries with dependency management"""
        results = []
        processed_queries = {}
        
        # Process sub-queries in order, respecting dependencies
        for sub_query in sub_queries:
            # Check if dependencies are satisfied
            if sub_query.dependencies:
                missing_deps = [
                    dep for dep in sub_query.dependencies
                    if dep not in processed_queries
                ]
                if missing_deps:
                    logger.warning(f"Skipping {sub_query.id} due to missing dependencies: {missing_deps}")
                    continue
            
            logger.info(f"Processing sub-query {sub_query.id}: {sub_query.text[:50]}...")
            
            start_time = time.time()
            
            try:
                # Add context from previous sub-queries
                enhanced_context = context.user_context.copy()
                if sub_query.dependencies:
                    dependency_context = self._build_dependency_context(
                        sub_query.dependencies, processed_queries
                    )
                    enhanced_context["dependency_context"] = dependency_context
                
                # Retrieve relevant documents for this sub-query
                retrieval_response = self.retrieval_manager.retrieve(
                    query=sub_query.text,
                    executive_id=context.executive_id,
                    user_context=enhanced_context,
                    top_k=self.config.get("top_k_per_subquery", 5),
                    strategy="auto"
                )
                
                # Generate focused answer for this sub-query
                answer = self._generate_sub_query_answer(sub_query, retrieval_response)
                
                # Extract sources
                sources = []
                for result in retrieval_response.get('results', []):
                    if 'id' in result:
                        sources.append(result['id'])
                
                # Calculate confidence based on retrieval quality
                confidence = self._calculate_sub_query_confidence(retrieval_response)
                
                processing_time_ms = (time.time() - start_time) * 1000
                
                sub_query_result = SubQueryResult(
                    sub_query=sub_query,
                    results=retrieval_response.get('results', []),
                    answer=answer,
                    sources=sources,
                    confidence=confidence,
                    processing_time_ms=processing_time_ms,
                    metadata={
                        "retrieval_metadata": retrieval_response.get('metadata', {}),
                        "dependency_context": enhanced_context.get("dependency_context", {})
                    }
                )
                
                results.append(sub_query_result)
                processed_queries[sub_query.id] = sub_query_result
                
                # Add to context
                context.add_finding({
                    "sub_query_id": sub_query.id,
                    "sub_query_text": sub_query.text,
                    "answer": answer,
                    "confidence": confidence,
                    "sources": sources
                })
                
                logger.info(
                    f"Sub-query {sub_query.id} processed in {processing_time_ms:.1f}ms "
                    f"(confidence: {confidence:.2f})"
                )
                
            except Exception as e:
                logger.error(f"Failed to process sub-query {sub_query.id}: {e}")
                
                # Create a fallback result
                sub_query_result = SubQueryResult(
                    sub_query=sub_query,
                    results=[],
                    answer=f"Unable to process this sub-query due to an error: {str(e)}",
                    sources=[],
                    confidence=0.0,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    metadata={"error": str(e)}
                )
                results.append(sub_query_result)
                self.metrics.error_count += 1
        
        return results
    
    def _build_dependency_context(
        self,
        dependencies: List[str],
        processed_queries: Dict[str, SubQueryResult]
    ) -> Dict[str, Any]:
        """Build context from dependent sub-queries"""
        dependency_context = {}
        
        for dep_id in dependencies:
            if dep_id in processed_queries:
                result = processed_queries[dep_id]
                dependency_context[dep_id] = {
                    "answer": result.answer,
                    "confidence": result.confidence,
                    "sources": result.sources,
                    "metadata": result.metadata
                }
        
        return dependency_context
    
    def _generate_sub_query_answer(
        self,
        sub_query: SubQuery,
        retrieval_response: Dict
    ) -> str:
        """Generate a focused answer for a sub-query based on retrieval results"""
        if not retrieval_response.get('results'):
            return f"No relevant information found for: {sub_query.text}"
        
        # Simple answer generation based on top results
        # In a real implementation, this might use an LLM for better synthesis
        top_results = retrieval_response['results'][:3]
        
        answer_parts = [f"Answer for: {sub_query.text}\n"]
        
        for i, result in enumerate(top_results, 1):
            content = result.get('content', '')
            title = result.get('title', 'Untitled')
            score = result.get('final_score', 0)
            
            # Truncate content for readability
            if len(content) > 200:
                content = content[:200] + "..."
            
            answer_parts.append(
                f"{i}. {title} (relevance: {score:.2f})\n"
                f"   {content}\n"
            )
        
        return "\n".join(answer_parts)
    
    def _calculate_sub_query_confidence(self, retrieval_response: Dict) -> float:
        """Calculate confidence in the sub-query answer based on retrieval quality"""
        if not retrieval_response.get('results'):
            return 0.0
        
        # Base confidence on top result scores
        top_scores = [r.get('final_score', 0) for r in retrieval_response['results'][:3]]
        
        if not top_scores:
            return 0.0
        
        # Average of top 3 scores, weighted towards the top result
        weights = [0.5, 0.3, 0.2]
        weighted_score = sum(score * weight for score, weight in zip(top_scores, weights))
        
        # Consider result count
        result_count_factor = min(len(retrieval_response['results']) / 5, 1.0)
        
        # Combine factors
        confidence = weighted_score * 0.7 + result_count_factor * 0.3
        
        return min(confidence, 1.0)
    
    def _create_no_decomposition_result(
        self,
        query: str,
        confidence: float,
        start_time: float
    ) -> DecompositionResult:
        """Create result for queries that don't need decomposition"""
        return DecompositionResult(
            original_query=query,
            needs_decomposition=False,
            sub_queries=[],
            sub_query_results=[],
            synthesized_answer="",
            all_sources=[],
            total_processing_time_ms=(time.time() - start_time) * 1000,
            decomposition_confidence=confidence,
            synthesis_confidence=0.0,
            strategy_used=None,
            metadata={"reason": "Query too simple for decomposition"}
        )
    
    def _handle_decomposition_failure(
        self,
        query: str,
        context: ProcessingContext,
        start_time: float
    ) -> DecompositionResult:
        """Handle decomposition failure with fallback"""
        logger.warning("Using fallback due to decomposition failure")
        
        return DecompositionResult(
            original_query=query,
            needs_decomposition=False,
            sub_queries=[],
            sub_query_results=[],
            synthesized_answer="Unable to decompose query. Please rephrase with simpler terms.",
            all_sources=[],
            total_processing_time_ms=(time.time() - start_time) * 1000,
            decomposition_confidence=0.0,
            synthesis_confidence=0.0,
            strategy_used=None,
            metadata={"fallback_reason": "Decomposition failed"}
        )
    
    def _handle_processing_error(
        self,
        query: str,
        context: ProcessingContext,
        error: Exception,
        start_time: float
    ) -> DecompositionResult:
        """Handle processing error with graceful fallback"""
        return DecompositionResult(
            original_query=query,
            needs_decomposition=False,
            sub_queries=[],
            sub_query_results=[],
            synthesized_answer=f"Processing error occurred: {str(error)}",
            all_sources=[],
            total_processing_time_ms=(time.time() - start_time) * 1000,
            decomposition_confidence=0.0,
            synthesis_confidence=0.0,
            strategy_used=None,
            metadata={"error": str(error), "traceback": traceback.format_exc()}
        )
    
    def _build_decomposition_result(
        self,
        query: str,
        sub_queries: List[SubQuery],
        sub_query_results: List[SubQueryResult],
        synthesized_answer: str,
        decomposition_confidence: float,
        synthesis_confidence: float,
        strategy: DecompositionStrategy,
        context: ProcessingContext,
        total_time_ms: float
    ) -> DecompositionResult:
        """Build the final decomposition result"""
        # Collect all sources
        all_sources = []
        for result in sub_query_results:
            all_sources.extend(result.sources)
        all_sources = list(set(all_sources))  # Deduplicate
        
        return DecompositionResult(
            original_query=query,
            needs_decomposition=True,
            sub_queries=sub_queries,
            sub_query_results=sub_query_results,
            synthesized_answer=synthesized_answer,
            all_sources=all_sources,
            total_processing_time_ms=total_time_ms,
            decomposition_confidence=decomposition_confidence,
            synthesis_confidence=synthesis_confidence,
            strategy_used=strategy,
            metadata={
                "processing_metrics": self.metrics.to_dict(),
                "context": {
                    "executive_id": context.executive_id,
                    "entities": context.entities,
                    "accumulated_findings": context.accumulated_findings,
                    "shared_context": context.shared_context
                }
            }
        )
    
    def _check_cache(self, query: str, executive_id: str) -> Optional[DecompositionResult]:
        """Check if result is cached"""
        cache_key = f"{query}_{executive_id}"
        return self._decomposition_cache.get(cache_key)
    
    def _cache_result(self, query: str, executive_id: str, result: DecompositionResult):
        """Cache the decomposition result"""
        cache_key = f"{query}_{executive_id}"
        self._decomposition_cache[cache_key] = result
        
        # Simple cache size management
        if len(self._decomposition_cache) > 100:
            # Remove oldest entries (simple FIFO)
            oldest_key = next(iter(self._decomposition_cache))
            del self._decomposition_cache[oldest_key]
    
    def _record_processing_history(
        self,
        query: str,
        context: ProcessingContext,
        result: DecompositionResult,
        status: str
    ):
        """Record processing history for monitoring"""
        history_entry = {
            "timestamp": time.time(),
            "query": query,
            "executive_id": context.executive_id,
            "status": status,
            "sub_query_count": len(result.sub_queries),
            "total_time_ms": result.total_processing_time_ms,
            "decomposition_confidence": result.decomposition_confidence,
            "synthesis_confidence": result.synthesis_confidence,
            "strategy": result.strategy_used.value if result.strategy_used else None
        }
        
        self.processing_history.append(history_entry)
        
        # Keep history size manageable
        if len(self.processing_history) > 1000:
            self.processing_history = self.processing_history[-500:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current processing metrics"""
        return {
            "current_metrics": self.metrics.to_dict(),
            "processing_history_size": len(self.processing_history),
            "cache_size": len(self._decomposition_cache),
            "recent_performance": self._calculate_recent_performance()
        }
    
    def _calculate_recent_performance(self) -> Dict[str, Any]:
        """Calculate performance metrics from recent history"""
        if not self.processing_history:
            return {}
        
        recent_entries = self.processing_history[-50:]  # Last 50 entries
        
        if not recent_entries:
            return {}
        
        avg_time = sum(e["total_time_ms"] for e in recent_entries) / len(recent_entries)
        avg_decomp_conf = sum(e["decomposition_confidence"] for e in recent_entries) / len(recent_entries)
        avg_synthesis_conf = sum(e["synthesis_confidence"] for e in recent_entries) / len(recent_entries)
        
        return {
            "avg_processing_time_ms": avg_time,
            "avg_decomposition_confidence": avg_decomp_conf,
            "avg_synthesis_confidence": avg_synthesis_conf,
            "total_queries_processed": len(recent_entries)
        }
    
    def reset_metrics(self):
        """Reset processing metrics"""
        self.metrics = ProcessingMetrics()
        self.processing_history.clear()
        self._decomposition_cache.clear()
        logger.info("DecompositionHandler metrics reset")


__all__ = [
    'DecompositionHandler',
    'ProcessingStatus',
    'ProcessingMetrics',
    'ProcessingContext'
]