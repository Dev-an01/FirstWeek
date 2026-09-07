"""
Sub-Query Processor for AI Officer RAG System
===========================================

Handles independent processing of sub-queries with result validation,
context preservation, and performance optimization.

This module handles:
1. Independent sub-query processing
2. Sub-query result validation
3. Context preservation across sub-queries
4. Performance monitoring and optimization
"""

import logging
import time
import json
import hashlib
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

from .query_decomposition import SubQuery, SubQueryResult, QueryType
from .base_client import LLMError

logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """Processing modes for sub-queries"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEPENDENCY_AWARE = "dependency_aware"


class ValidationResult(Enum):
    """Validation result for sub-query processing"""
    VALID = "valid"
    LOW_CONFIDENCE = "low_confidence"
    NO_RESULTS = "no_results"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class ValidationMetrics:
    """Metrics for sub-query validation"""
    validation_result: ValidationResult
    confidence_score: float
    result_count: int
    source_count: int
    processing_time_ms: float
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "validation_result": self.validation_result.value,
            "confidence_score": self.confidence_score,
            "result_count": self.result_count,
            "source_count": self.source_count,
            "processing_time_ms": self.processing_time_ms,
            "error_message": self.error_message,
            "warnings": self.warnings
        }


@dataclass
class ProcessingConfig:
    """Configuration for sub-query processing"""
    mode: ProcessingMode = ProcessingMode.DEPENDENCY_AWARE
    max_workers: int = 3
    timeout_seconds: int = 30
    min_confidence_threshold: float = 0.3
    min_result_count: int = 1
    enable_caching: bool = True
    enable_validation: bool = True
    retry_failed_queries: bool = True
    max_retries: int = 2
    cache_ttl_seconds: int = 300


class SubQueryProcessor:
    """
    Processes individual sub-queries through the standard retrieval pipeline.
    
    Routes each sub-query through the hybrid retrieval manager and generates
    focused answers for each with comprehensive validation.
    """
    
    def __init__(
        self,
        retrieval_manager,
        config: ProcessingConfig = None
    ):
        """
        Initialize the sub-query processor.
        
        Args:
            retrieval_manager: HybridRetrievalManager instance
            config: Processing configuration
        """
        self.retrieval_manager = retrieval_manager
        self.config = config or ProcessingConfig()
        
        # Performance tracking
        self.processing_metrics = {}
        self.cache = {} if self.config.enable_caching else None
        
        # Validation rules
        self.validation_rules = self._initialize_validation_rules()
        
        logger.info(f"SubQueryProcessor initialized with mode={self.config.mode.value}")
    
    def process_sub_queries(
        self,
        sub_queries: List[SubQuery],
        executive_id: str,
        user_context: Dict = None,
        shared_context: Dict = None
    ) -> List[SubQueryResult]:
        """
        Process a list of sub-queries through the retrieval pipeline.
        
        Args:
            sub_queries: List of sub-queries to process
            executive_id: Executive context ID
            user_context: User context for RBAC
            shared_context: Context shared across sub-queries
            
        Returns:
            List of SubQueryResult objects
        """
        start_time = time.time()
        
        if user_context is None:
            user_context = {
                "user_id": "unknown",
                "role": "employee",
                "allowed_scopes": ["public", "internal"]
            }
        
        if shared_context is None:
            shared_context = {}
        
        logger.info(f"Processing {len(sub_queries)} sub-queries in {self.config.mode.value} mode")
        
        # Choose processing mode
        if self.config.mode == ProcessingMode.PARALLEL:
            results = self._process_parallel(sub_queries, executive_id, user_context, shared_context)
        elif self.config.mode == ProcessingMode.DEPENDENCY_AWARE:
            results = self._process_dependency_aware(sub_queries, executive_id, user_context, shared_context)
        else:  # SEQUENTIAL
            results = self._process_sequential(sub_queries, executive_id, user_context, shared_context)
        
        # Validate results if enabled
        if self.config.enable_validation:
            results = self._validate_results(results)
        
        # Retry failed queries if enabled
        if self.config.retry_failed_queries:
            results = self._retry_failed_queries(results, executive_id, user_context, shared_context)
        
        total_time_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"Processed {len(sub_queries)} sub-queries in {total_time_ms:.1f}ms "
            f"(successful: {len([r for r in results if r.confidence > self.config.min_confidence_threshold])})"
        )
        
        return results
    
    def _process_sequential(
        self,
        sub_queries: List[SubQuery],
        executive_id: str,
        user_context: Dict,
        shared_context: Dict
    ) -> List[SubQueryResult]:
        """Process sub-queries sequentially"""
        results = []
        accumulated_context = shared_context.copy()
        
        for sub_query in sub_queries:
            result = self._process_single_sub_query(
                sub_query, executive_id, user_context, accumulated_context
            )
            results.append(result)
            
            # Update accumulated context with successful results
            if result.confidence > self.config.min_confidence_threshold:
                accumulated_context[f"subquery_{sub_query.id}_result"] = {
                    "answer": result.answer,
                    "confidence": result.confidence,
                    "sources": result.sources
                }
        
        return results
    
    def _process_parallel(
        self,
        sub_queries: List[SubQuery],
        executive_id: str,
        user_context: Dict,
        shared_context: Dict
    ) -> List[SubQueryResult]:
        """Process sub-queries in parallel"""
        results = [None] * len(sub_queries)
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all sub-queries
            future_to_index = {
                executor.submit(
                    self._process_single_sub_query,
                    sub_query, executive_id, user_context, shared_context
                ): i
                for i, sub_query in enumerate(sub_queries)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_index, timeout=self.config.timeout_seconds):
                index = future_to_index[future]
                try:
                    result = future.result()
                    results[index] = result
                except Exception as e:
                    logger.error(f"Parallel processing failed for sub-query {index}: {e}")
                    # Create fallback result
                    sub_query = sub_queries[index]
                    results[index] = SubQueryResult(
                        sub_query=sub_query,
                        results=[],
                        answer=f"Processing failed: {str(e)}",
                        sources=[],
                        confidence=0.0,
                        processing_time_ms=0.0,
                        metadata={"error": str(e)}
                    )
        
        return results
    
    def _process_dependency_aware(
        self,
        sub_queries: List[SubQuery],
        executive_id: str,
        user_context: Dict,
        shared_context: Dict
    ) -> List[SubQueryResult]:
        """Process sub-queries with dependency awareness"""
        # Create dependency graph
        dependency_map = {sq.id: sq.dependencies for sq in sub_queries}
        processed_queries = {}
        results = []
        
        # Process in dependency order
        remaining_queries = sub_queries.copy()
        
        while remaining_queries:
            # Find queries with no unprocessed dependencies
            ready_queries = [
                sq for sq in remaining_queries
                if all(dep in processed_queries for dep in sq.dependencies)
            ]
            
            if not ready_queries:
                logger.warning("Circular dependency detected or missing dependencies")
                # Process remaining queries without dependencies
                ready_queries = remaining_queries
            
            # Process ready queries in parallel
            if len(ready_queries) > 1:
                ready_results = self._process_parallel(
                    ready_queries, executive_id, user_context, shared_context
                )
            else:
                ready_results = [
                    self._process_single_sub_query(
                        ready_queries[0], executive_id, user_context, shared_context
                    )
                ]
            
            # Add results and update context
            for i, sub_query in enumerate(ready_queries):
                result = ready_results[i]
                results.append(result)
                processed_queries[sub_query.id] = result
                
                # Remove from remaining
                if sub_query in remaining_queries:
                    remaining_queries.remove(sub_query)
        
        # Sort results by original order
        results.sort(key=lambda x: x.sub_query.order)
        
        return results
    
    def _process_single_sub_query(
        self,
        sub_query: SubQuery,
        executive_id: str,
        user_context: Dict,
        context: Dict
    ) -> SubQueryResult:
        """Process a single sub-query"""
        start_time = time.time()
        
        # Check cache first
        cache_key = self._generate_cache_key(sub_query, executive_id, user_context)
        if self.cache and cache_key in self.cache:
            cached_result = self.cache[cache_key]
            if time.time() - cached_result["timestamp"] < self.config.cache_ttl_seconds:
                logger.debug(f"Cache hit for sub-query {sub_query.id}")
                return cached_result["result"]
        
        try:
            # Enhance context with dependency information
            enhanced_context = user_context.copy()
            enhanced_context.update(context)
            
            if sub_query.dependencies:
                dependency_context = {
                    dep_id: context.get(f"subquery_{dep_id}_result", {})
                    for dep_id in sub_query.dependencies
                }
                enhanced_context["dependency_context"] = dependency_context
            
            # Retrieve relevant documents for this sub-query
            retrieval_response = self.retrieval_manager.retrieve(
                query=sub_query.text,
                executive_id=executive_id,
                user_context=enhanced_context,
                top_k=self.config.top_k_per_subquery if hasattr(self.config, 'top_k_per_subquery') else 5,
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
                    "enhanced_context": enhanced_context,
                    "cache_hit": False
                }
            )
            
            # Cache result
            if self.cache:
                self.cache[cache_key] = {
                    "result": sub_query_result,
                    "timestamp": time.time()
                }
            
            return sub_query_result
            
        except Exception as e:
            logger.error(f"Failed to process sub-query {sub_query.id}: {e}")
            
            # Create a fallback result
            return SubQueryResult(
                sub_query=sub_query,
                results=[],
                answer=f"Unable to process this sub-query due to an error: {str(e)}",
                sources=[],
                confidence=0.0,
                processing_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": str(e)}
            )
    
    def _generate_cache_key(
        self,
        sub_query: SubQuery,
        executive_id: str,
        user_context: Dict
    ) -> str:
        """Generate cache key for sub-query"""
        key_data = {
            "query": sub_query.text,
            "executive_id": executive_id,
            "user_role": user_context.get("role", "unknown"),
            "allowed_scopes": sorted(user_context.get("allowed_scopes", []))
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _generate_sub_query_answer(
        self,
        sub_query: SubQuery,
        retrieval_response: Dict
    ) -> str:
        """Generate a focused answer for a sub-query based on retrieval results"""
        if not retrieval_response.get('results'):
            return f"No relevant information found for: {sub_query.text}"
        
        # Enhanced answer generation based on query type
        if sub_query.query_type == QueryType.COMPARISON:
            return self._generate_comparison_answer(sub_query, retrieval_response)
        elif sub_query.query_type == QueryType.DECISION:
            return self._generate_decision_answer(sub_query, retrieval_response)
        elif sub_query.query_type == QueryType.ANALYSIS:
            return self._generate_analysis_answer(sub_query, retrieval_response)
        else:
            # Default factual answer
            return self._generate_factual_answer(sub_query, retrieval_response)
    
    def _generate_factual_answer(
        self,
        sub_query: SubQuery,
        retrieval_response: Dict
    ) -> str:
        """Generate factual answer"""
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
    
    def _generate_comparison_answer(
        self,
        sub_query: SubQuery,
        retrieval_response: Dict
    ) -> str:
        """Generate comparison answer"""
        top_results = retrieval_response['results'][:5]
        
        answer_parts = [f"Comparison analysis for: {sub_query.text}\n"]
        
        # Group results by entities if possible
        entity_groups = {}
        for result in top_results:
            for entity in sub_query.entities:
                if entity.lower() in result.get('content', '').lower():
                    if entity not in entity_groups:
                        entity_groups[entity] = []
                    entity_groups[entity].append(result)
        
        if entity_groups:
            for entity, results in entity_groups.items():
                answer_parts.append(f"\n{entity}:\n")
                for i, result in enumerate(results[:2], 1):
                    content = result.get('content', '')[:150] + "..."
                    answer_parts.append(f"  {i}. {content}")
        else:
            # Fallback to simple listing
            for i, result in enumerate(top_results, 1):
                content = result.get('content', '')[:200] + "..."
                answer_parts.append(f"{i}. {content}")
        
        return "\n".join(answer_parts)
    
    def _generate_decision_answer(
        self,
        sub_query: SubQuery,
        retrieval_response: Dict
    ) -> str:
        """Generate decision-focused answer"""
        top_results = retrieval_response['results'][:3]
        
        answer_parts = [f"Decision context for: {sub_query.text}\n"]
        
        # Look for decision-related content
        decision_keywords = ['decision', 'approved', 'rejected', 'recommended', 'chosen']
        
        for i, result in enumerate(top_results, 1):
            content = result.get('content', '')
            title = result.get('title', 'Untitled')
            
            # Highlight decision-related content
            highlighted_content = content
            for keyword in decision_keywords:
                if keyword in content.lower():
                    highlighted_content = content.replace(keyword, f"**{keyword.upper()}**")
            
            # Truncate for readability
            if len(highlighted_content) > 250:
                highlighted_content = highlighted_content[:250] + "..."
            
            answer_parts.append(
                f"{i}. {title}\n"
                f"   {highlighted_content}\n"
            )
        
        return "\n".join(answer_parts)
    
    def _generate_analysis_answer(
        self,
        sub_query: SubQuery,
        retrieval_response: Dict
    ) -> str:
        """Generate analysis-focused answer"""
        top_results = retrieval_response['results'][:4]
        
        answer_parts = [f"Analysis for: {sub_query.text}\n"]
        
        # Extract key insights from results
        insights = []
        for result in top_results:
            content = result.get('content', '')
            title = result.get('title', 'Untitled')
            
            # Simple insight extraction (look for analytical patterns)
            if any(word in content.lower() for word in ['analysis', 'trend', 'pattern', 'impact', 'effect']):
                insights.append(f"- From {title}: {content[:200]}...")
        
        if insights:
            answer_parts.append("\nKey Insights:\n")
            answer_parts.extend(insights)
        else:
            # Fallback to standard format
            for i, result in enumerate(top_results, 1):
                content = result.get('content', '')[:200] + "..."
                answer_parts.append(f"{i}. {content}")
        
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
        
        # Consider source diversity
        sources = set(r.get('source', 'unknown') for r in retrieval_response['results'])
        diversity_factor = min(len(sources) / 3, 1.0)
        
        # Combine factors
        confidence = (
            weighted_score * 0.6 +
            result_count_factor * 0.2 +
            diversity_factor * 0.2
        )
        
        return min(confidence, 1.0)
    
    def _validate_results(self, results: List[SubQueryResult]) -> List[SubQueryResult]:
        """Validate and filter sub-query results"""
        validated_results = []
        
        for result in results:
            validation = self._validate_single_result(result)
            
            # Update result metadata with validation
            result.metadata["validation"] = validation.to_dict()
            
            # Add warnings if any
            if validation.warnings:
                result.metadata["warnings"] = validation.warnings
            
            # Keep result even if validation fails, but mark it
            validated_results.append(result)
        
        return validated_results
    
    def _validate_single_result(self, result: SubQueryResult) -> ValidationMetrics:
        """Validate a single sub-query result"""
        # Check confidence
        if result.confidence < self.config.min_confidence_threshold:
            return ValidationMetrics(
                validation_result=ValidationResult.LOW_CONFIDENCE,
                confidence_score=result.confidence,
                result_count=len(result.results),
                source_count=len(result.sources),
                processing_time_ms=result.processing_time_ms,
                warnings=[f"Low confidence: {result.confidence:.2f}"]
            )
        
        # Check result count
        if len(result.results) < self.config.min_result_count:
            return ValidationMetrics(
                validation_result=ValidationResult.NO_RESULTS,
                confidence_score=result.confidence,
                result_count=len(result.results),
                source_count=len(result.sources),
                processing_time_ms=result.processing_time_ms,
                warnings=[f"Insufficient results: {len(result.results)}"]
            )
        
        # Check for errors
        if "error" in result.metadata:
            return ValidationMetrics(
                validation_result=ValidationResult.ERROR,
                confidence_score=result.confidence,
                result_count=len(result.results),
                source_count=len(result.sources),
                processing_time_ms=result.processing_time_ms,
                error_message=result.metadata["error"]
            )
        
        # Check timeout
        if result.processing_time_ms > self.config.timeout_seconds * 1000:
            return ValidationMetrics(
                validation_result=ValidationResult.TIMEOUT,
                confidence_score=result.confidence,
                result_count=len(result.results),
                source_count=len(result.sources),
                processing_time_ms=result.processing_time_ms,
                warnings=[f"Processing timeout: {result.processing_time_ms:.1f}ms"]
            )
        
        # Valid result
        return ValidationMetrics(
            validation_result=ValidationResult.VALID,
            confidence_score=result.confidence,
            result_count=len(result.results),
            source_count=len(result.sources),
            processing_time_ms=result.processing_time_ms
        )
    
    def _retry_failed_queries(
        self,
        results: List[SubQueryResult],
        executive_id: str,
        user_context: Dict,
        shared_context: Dict
    ) -> List[SubQueryResult]:
        """Retry failed sub-queries with modified parameters"""
        retry_results = []
        
        for i, result in enumerate(results):
            validation = result.metadata.get("validation", {})
            
            # Check if retry is needed
            needs_retry = (
                validation.get("validation_result") in ["low_confidence", "no_results", "error"] and
                result.sub_query.id not in self.processing_metrics
            )
            
            if needs_retry and len(self.processing_metrics.get(result.sub_query.id, [])) < self.config.max_retries:
                logger.info(f"Retrying sub-query {result.sub_query.id}")
                
                # Track retry attempt
                if result.sub_query.id not in self.processing_metrics:
                    self.processing_metrics[result.sub_query.id] = []
                self.processing_metrics[result.sub_query.id].append(validation)
                
                # Retry with modified parameters
                retry_result = self._retry_with_modified_params(
                    result.sub_query, executive_id, user_context, shared_context
                )
                
                # Use retry if better
                if retry_result.confidence > result.confidence:
                    retry_results.append(retry_result)
                    logger.info(f"Retry successful for {result.sub_query.id}")
                else:
                    retry_results.append(result)
                    logger.info(f"Retry did not improve {result.sub_query.id}")
            else:
                retry_results.append(result)
        
        return retry_results
    
    def _retry_with_modified_params(
        self,
        sub_query: SubQuery,
        executive_id: str,
        user_context: Dict,
        shared_context: Dict
    ) -> SubQueryResult:
        """Retry sub-query with modified parameters"""
        # Modify user context for retry
        modified_context = user_context.copy()
        modified_context["retry_attempt"] = True
        modified_context["top_k"] = 10  # Increase top_k for retry
        
        # Process with modified context
        return self._process_single_sub_query(
            sub_query, executive_id, modified_context, shared_context
        )
    
    def _initialize_validation_rules(self) -> Dict[str, Any]:
        """Initialize validation rules"""
        return {
            "min_confidence_threshold": self.config.min_confidence_threshold,
            "min_result_count": self.config.min_result_count,
            "max_processing_time_ms": self.config.timeout_seconds * 1000,
            "required_fields": ["answer", "sources", "confidence"],
            "warning_thresholds": {
                "low_confidence": 0.5,
                "few_results": 2,
                "slow_processing": 5000  # ms
            }
        }
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            "cache_size": len(self.cache) if self.cache else 0,
            "processing_metrics": self.processing_metrics,
            "config": {
                "mode": self.config.mode.value,
                "max_workers": self.config.max_workers,
                "timeout_seconds": self.config.timeout_seconds,
                "min_confidence_threshold": self.config.min_confidence_threshold
            }
        }
    
    def clear_cache(self):
        """Clear processing cache"""
        if self.cache:
            self.cache.clear()
            logger.info("SubQueryProcessor cache cleared")


__all__ = [
    'SubQueryProcessor',
    'ProcessingMode',
    'ValidationResult',
    'ValidationMetrics',
    'ProcessingConfig'
]