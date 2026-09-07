"""
Query Router

Classifies queries into fast/standard/agentic paths based on complexity.
Uses pattern matching and feature extraction (NO LLM dependency).
"""
import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from config.llm_config_loader import get_config

logger = logging.getLogger(__name__)


@dataclass
class RouteDecision:
    """
    Routing decision for a query.
    
    Attributes:
        path: Chosen path (fast, standard, agentic)
        model_key: Model key for path (fast, standard, complex)
        confidence: Confidence in routing decision (0-1)
        reasoning: Human-readable explanation
        features: Extracted features used for decision
        settings: Path-specific settings (temperature, max_tokens, etc.)
    """
    path: str
    model_key: str
    confidence: float
    reasoning: str
    features: Dict[str, Any]
    settings: Dict[str, Any]


class QueryRouter:
    """
    Routes queries to appropriate processing path based on complexity.
    
    Uses pattern matching and heuristics (no LLM calls) to classify:
    - Fast path: Simple factual queries
    - Standard path: Decision/recommendation queries
    - Agentic path: Complex analysis queries
    """
    
    def __init__(self):
        """Initialize QueryRouter with configuration."""
        config = get_config()
        router_config = config._config.get('router', {})
        
        # Load pattern rules
        patterns = router_config.get('patterns', {})
        self.fast_patterns = patterns.get('fast', [])
        self.standard_patterns = patterns.get('standard', [])
        self.agentic_patterns = patterns.get('agentic', [])
        
        # Load thresholds
        thresholds = router_config.get('thresholds', {})
        self.entity_threshold = thresholds.get('entity_count_for_agentic', 5)
        self.word_count_threshold = thresholds.get('word_count_for_agentic', 25)
        self.min_confidence = thresholds.get('min_confidence', 0.6)
        
        # Default fallback
        self.default_path = router_config.get('default_path', 'standard')
        
        # Compile regex patterns for performance
        self._compile_patterns()
        
        # Get path settings
        self.path_settings = {
            'fast': config.get_path_settings('fast'),
            'standard': config.get_path_settings('standard'),
            'agentic': config.get_path_settings('agentic'),
        }
        
        logger.info("QueryRouter initialized")
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self.fast_regex = [
            re.compile(r'\b' + re.escape(pattern) + r'\b', re.IGNORECASE)
            for pattern in self.fast_patterns
        ]
        self.standard_regex = [
            re.compile(r'\b' + re.escape(pattern) + r'\b', re.IGNORECASE)
            for pattern in self.standard_patterns
        ]
        self.agentic_regex = [
            re.compile(r'\b' + re.escape(pattern) + r'\b', re.IGNORECASE)
            for pattern in self.agentic_patterns
        ]
    
    def route(
        self,
        query: str,
        query_analysis: Optional[Dict[str, Any]] = None
    ) -> RouteDecision:
        """
        Route query to appropriate path.
        
        Args:
            query: Query string
            query_analysis: Optional pre-analyzed query data from QueryAnalyzer
            
        Returns:
            RouteDecision with path and settings
        """
        # Extract features
        features = self._extract_features(query, query_analysis)
        
        # Calculate scores for each path
        scores = self._calculate_path_scores(features)
        
        # Make decision
        path, confidence, reasoning = self._decide_path(features, scores)
        
        # Map path to model key
        model_key = self._map_path_to_model_key(path)
        
        # Get settings for path
        settings = self.path_settings[path]
        
        decision = RouteDecision(
            path=path,
            model_key=model_key,
            confidence=confidence,
            reasoning=reasoning,
            features=features,
            settings=settings
        )
        
        logger.info(
            f"Routed query to {path} path (confidence: {confidence:.2f}): {reasoning}"
        )
        
        return decision
    
    def _extract_features(
        self,
        query: str,
        query_analysis: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract features from query for classification.
        
        Args:
            query: Query string
            query_analysis: Optional pre-analyzed query data
            
        Returns:
            Dict of extracted features
        """
        features = {}
        
        # Basic text features
        features['word_count'] = len(query.split())
        features['char_count'] = len(query)
        features['question_marks'] = query.count('?')
        features['has_multiple_questions'] = query.count('?') > 1
        
        # Pattern matches
        features['fast_pattern_matches'] = sum(
            1 for pattern in self.fast_regex if pattern.search(query)
        )
        features['standard_pattern_matches'] = sum(
            1 for pattern in self.standard_regex if pattern.search(query)
        )
        features['agentic_pattern_matches'] = sum(
            1 for pattern in self.agentic_regex if pattern.search(query)
        )
        
        # Query analysis features (if available)
        if query_analysis:
            features['entity_count'] = len(query_analysis.get('entities', []))
            features['query_type'] = query_analysis.get('query_type', 'unknown')
            features['complexity'] = query_analysis.get('complexity', 'medium')
        else:
            # Fallback: estimate entity count by looking for capitalized words
            capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
            features['entity_count'] = len(set(capitalized))
            features['query_type'] = 'unknown'
            features['complexity'] = 'medium'
        
        # Complex indicators
        features['has_comparison'] = bool(
            re.search(r'\b(compare|versus|vs|difference between|similarities)\b', query, re.IGNORECASE)
        )
        features['has_analysis_request'] = bool(
            re.search(r'\b(analyze|evaluate|assess|examine|investigate)\b', query, re.IGNORECASE)
        )
        features['has_multiple_parts'] = bool(
            re.search(r'\band\b.*\band\b', query, re.IGNORECASE) or
            re.search(r'\bor\b.*\bor\b', query, re.IGNORECASE)
        )
        
        # NEW: Query decomposition indicators
        features['needs_decomposition'] = self._check_decomposition_indicators(query, features)
        
        return features
    
    def _calculate_path_scores(self, features: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate scores for each path based on features.
        
        Args:
            features: Extracted features
            
        Returns:
            Dict mapping path names to scores (0-1)
        """
        scores = {
            'fast': 0.0,
            'standard': 0.0,
            'agentic': 0.0
        }
        
        # Fast path scoring (simple factual queries)
        if features['fast_pattern_matches'] > 0:
            scores['fast'] += 0.5
        if features['word_count'] <= 10:
            scores['fast'] += 0.3
        if features['entity_count'] <= 2:
            scores['fast'] += 0.2
        
        # Standard path scoring (decisions/recommendations)
        if features['standard_pattern_matches'] > 0:
            scores['standard'] += 0.6  # Strong signal
        if 6 < features['word_count'] <= 20:
            scores['standard'] += 0.2
        if 2 < features['entity_count'] <= 5:
            scores['standard'] += 0.2
        
        # Agentic path scoring (complex analysis)
        # REQUIRES multiple strong signals, not just one
        if features['agentic_pattern_matches'] > 0:
            scores['agentic'] += 0.7  # Very strong signal
        if features['word_count'] > self.word_count_threshold:
            scores['agentic'] += 0.2  # Reduced from 0.3 - word count alone isn't enough
        if features['entity_count'] > self.entity_threshold:
            scores['agentic'] += 0.3
        if features['has_comparison']:
            scores['agentic'] += 0.5  # Strong signal for agentic
        if features['has_analysis_request']:
            scores['agentic'] += 0.5  # Strong signal for agentic
        if features['has_multiple_parts'] or features['has_multiple_questions']:
            scores['agentic'] += 0.3

        # NEW: Penalty for short queries claiming to be agentic (avoid false positives)
        if features['word_count'] < 15 and scores['agentic'] > 0:
            scores['agentic'] *= 0.5  # Reduce agentic score for very short queries
        
        # NEW: Boost agentic score for queries needing decomposition
        if features.get('needs_decomposition', False):
            scores['agentic'] += 0.4
        
        # Normalize scores to 0-1 range
        max_score = max(scores.values()) if max(scores.values()) > 0 else 1.0
        scores = {k: v / max_score for k, v in scores.items()}
        
        return scores
    
    def _decide_path(
        self,
        features: Dict[str, Any],
        scores: Dict[str, float]
    ) -> Tuple[str, float, str]:
        """
        Make final routing decision based on scores.
        
        Args:
            features: Extracted features
            scores: Path scores
            
        Returns:
            Tuple of (path, confidence, reasoning)
        """
        # Get highest scoring path
        best_path = max(scores, key=scores.get)
        confidence = scores[best_path]
        
        # Build reasoning
        reasoning_parts = []
        
        if best_path == 'fast':
            if features['fast_pattern_matches'] > 0:
                reasoning_parts.append("simple factual query pattern")
            if features['word_count'] <= 10:
                reasoning_parts.append("short query")
            if features['entity_count'] <= 2:
                reasoning_parts.append("few entities")
                
        elif best_path == 'standard':
            if features['standard_pattern_matches'] > 0:
                reasoning_parts.append("decision/recommendation pattern")
            if features['query_type'] in ['decision', 'recommendation']:
                reasoning_parts.append(f"query type: {features['query_type']}")
            if 2 < features['entity_count'] <= 5:
                reasoning_parts.append("moderate entity count")
                
        elif best_path == 'agentic':
            if features['agentic_pattern_matches'] > 0:
                reasoning_parts.append("complex analysis pattern")
            if features['has_comparison']:
                reasoning_parts.append("comparison requested")
            if features['entity_count'] > self.entity_threshold:
                reasoning_parts.append(f"many entities ({features['entity_count']})")
            if features['word_count'] > self.word_count_threshold:
                reasoning_parts.append(f"long query ({features['word_count']} words)")
        
        reasoning = "Chose " + best_path + " path: " + ", ".join(reasoning_parts)
        
        # If confidence too low, use default
        if confidence < self.min_confidence:
            logger.warning(
                f"Low confidence ({confidence:.2f}), using default path: {self.default_path}"
            )
            return self.default_path, confidence, f"Low confidence, defaulted to {self.default_path}"
        
        return best_path, confidence, reasoning
    
    def _map_path_to_model_key(self, path: str) -> str:
        """
        Map path name to model key.
        
        Args:
            path: Path name (fast, standard, agentic)
            
        Returns:
            Model key (fast, standard, complex)
        """
        mapping = {
            'fast': 'fast',
            'standard': 'standard',
            'agentic': 'complex'
        }
        return mapping.get(path, 'standard')
    
    def _check_decomposition_indicators(self, query: str, features: Dict[str, Any]) -> bool:
        """
        Check if query shows indicators that would benefit from decomposition.
        
        This is a simplified version of the complexity detection in QueryDecomposer
        to provide early routing hints.
        
        Args:
            query: Query string
            features: Already extracted features
            
        Returns:
            True if query likely needs decomposition
        """
        # Check query length
        if len(query) > 150:
            return True
        
        # Check entity count
        if features.get('entity_count', 0) > 3:
            return True
        
        # Check multiple conjunctions
        conjunction_count = len(re.findall(r'\b(and|but|while|also|plus)\b', query, re.IGNORECASE))
        if conjunction_count > 1:
            return True
        
        # Check comparison words
        if re.search(r'\b(compare|versus|vs|difference between|similarities|pros and cons)\b', query, re.IGNORECASE):
            return True
        
        # Check multiple question types
        question_words = re.findall(r'\b(what|how|why|when|where|who|which)\b', query, re.IGNORECASE)
        if len(set(question_words)) > 1:
            return True
        
        return False
