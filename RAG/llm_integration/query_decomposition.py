"""
Query Decomposition Module for AI Officer RAG System
====================================================

Intelligent decomposition of complex multi-part queries into simpler sub-queries.
This module handles:

1. Query Complexity Detection
2. LLM-based Decomposition 
3. Sub-query Processing
4. Answer Synthesis

Flow:
1. Detect if query needs decomposition based on complexity indicators
2. Use fast LLM (GPT-4o-mini) to break complex queries into sub-queries
3. Process each sub-query through standard retrieval pipeline
4. Synthesize comprehensive answer from sub-query results
"""

import json
import re
import time
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum

from .factory import LLMClientFactory
from .base_client import LLMMessage, LLMError, LLMResponse

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of queries for classification"""
    FACTUAL = "factual"
    DECISION = "decision"
    COMPARISON = "comparison"
    ANALYSIS = "analysis"
    RECOMMENDATION = "recommendation"
    TEMPORAL = "temporal"


class DecompositionStrategy(Enum):
    """Decomposition strategies"""
    ENTITY_BASED = "entity_based"
    TEMPORAL = "temporal"
    COMPARATIVE = "comparative"
    CAUSAL = "causal"
    HIERARCHICAL = "hierarchical"


@dataclass
class SubQuery:
    """Represents a decomposed sub-query"""
    id: str
    text: str
    order: int
    query_type: QueryType
    entities: List[str]
    context: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    strategy: DecompositionStrategy = DecompositionStrategy.ENTITY_BASED
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubQueryResult:
    """Result from processing a sub-query"""
    sub_query: SubQuery
    results: List[Dict]
    answer: str
    sources: List[str]
    confidence: float
    processing_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecompositionResult:
    """Complete decomposition and synthesis result"""
    original_query: str
    needs_decomposition: bool
    sub_queries: List[SubQuery]
    sub_query_results: List[SubQueryResult]
    synthesized_answer: str
    all_sources: List[str]
    total_processing_time_ms: float
    decomposition_confidence: float
    synthesis_confidence: float
    strategy_used: Optional[DecompositionStrategy] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class QueryComplexityDetector:
    """
    Detects when a query needs decomposition based on various indicators.
    
    Indicators for decomposition:
    - Multiple conjunctions ("and", "but", "while")
    - Comparison words ("compare", "versus", "vs")
    - Multiple entities (>3 distinct)
    - Multiple question types mixed
    - Query length >150 characters
    - Temporal complexity
    - Causal relationships
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the complexity detector with patterns and thresholds"""
        self.config = config or {}
        
        # Conjunction patterns indicating multiple parts
        self.conjunction_patterns = [
            r'\band\b.*\band\b',  # Multiple "and"s
            r'\bbut\b.*\bbut\b',  # Multiple "but"s
            r'\bwhile\b.*\bwhile\b',  # Multiple "while"s
            r'\balso\b.*\balso\b',  # Multiple "also"s
            r'\bplus\b.*\bplus\b',  # Multiple "plus"s
            r'\bas well as\b.*\bas well as\b',  # Multiple "as well as"s
        ]
        
        # Comparison patterns
        self.comparison_patterns = [
            r'\bcompare\b',
            r'\bversus\b',
            r'\bvs\b',
            r'\bdifference between\b',
            r'\bsimilarities\b',
            r'\bpros and cons\b',
            r'\badvantages and disadvantages\b',
            r'\bcompare and contrast\b',
        ]
        
        # Temporal patterns
        self.temporal_patterns = [
            r'\bover time\b',
            r'\btrend\b',
            r'\bevolution\b',
            r'\bhistory\b',
            r'\bchronology\b',
            r'\bbefore\b.*\bafter\b',
            r'\bsince\b.*\buntil\b',
        ]
        
        # Causal patterns
        self.causal_patterns = [
            r'\bwhy\b',
            r'\bcause\b',
            r'\beffect\b',
            r'\bimpact\b',
            r'\binfluence\b',
            r'\bbecause\b',
            r'\btherefore\b',
            r'\bconsequence\b',
        ]
        
        # Question type patterns
        self.question_patterns = {
            'what': r'\bwhat\b',
            'how': r'\bhow\b',
            'why': r'\bwhy\b',
            'when': r'\bwhen\b',
            'where': r'\bwhere\b',
            'who': r'\bwho\b',
            'which': r'\bwhich\b',
        }
        
        # Compile regex patterns for performance
        self.compiled_conjunctions = [re.compile(p, re.IGNORECASE) for p in self.conjunction_patterns]
        self.compiled_comparisons = [re.compile(p, re.IGNORECASE) for p in self.comparison_patterns]
        self.compiled_temporal = [re.compile(p, re.IGNORECASE) for p in self.temporal_patterns]
        self.compiled_causal = [re.compile(p, re.IGNORECASE) for p in self.causal_patterns]
        self.compiled_questions = {k: re.compile(v, re.IGNORECASE) for k, v in self.question_patterns.items()}
        
        # Thresholds from config
        self.min_query_length = self.config.get("min_query_length", 150)
        self.min_entity_count = self.config.get("min_entity_count", 4)
        self.min_conjunction_count = self.config.get("min_conjunction_count", 2)
        self.comparison_keywords = self.config.get("comparison_keywords", [])
    
    def detect_complexity(self, query: str, entities: List[str] = None) -> Dict[str, Any]:
        """
        Analyze query complexity and determine if decomposition is needed.
        
        Args:
            query: The input query string
            entities: List of entities already extracted from query
            
        Returns:
            Dict with complexity analysis and decomposition decision
        """
        if entities is None:
            entities = []
        
        analysis = {
            'query_length': len(query),
            'word_count': len(query.split()),
            'entity_count': len(entities),
            'conjunction_count': 0,
            'has_comparison': False,
            'has_temporal': False,
            'has_causal': False,
            'question_types': [],
            'multiple_question_types': False,
            'complexity_score': 0.0,
            'needs_decomposition': False,
            'confidence': 0.0,
            'reasons': [],
            'recommended_strategy': None
        }
        
        # Check query length
        if analysis['query_length'] > self.min_query_length:
            analysis['reasons'].append(f'Query length > {self.min_query_length} characters')
            analysis['complexity_score'] += 0.2
        
        # Check entity count
        if analysis['entity_count'] > self.min_entity_count:
            analysis['reasons'].append(f'More than {self.min_entity_count} entities ({analysis["entity_count"]})')
            analysis['complexity_score'] += 0.3
        
        # Check conjunctions
        for pattern in self.compiled_conjunctions:
            if pattern.search(query):
                analysis['conjunction_count'] += 1
        if analysis['conjunction_count'] >= self.min_conjunction_count:
            analysis['reasons'].append(f'Multiple conjunctions detected ({analysis["conjunction_count"]})')
            analysis['complexity_score'] += 0.25
        
        # Check comparisons
        for pattern in self.compiled_comparisons:
            if pattern.search(query):
                analysis['has_comparison'] = True
                analysis['reasons'].append('Comparison keywords detected')
                analysis['complexity_score'] += 0.35
                break
        
        # Check temporal patterns
        for pattern in self.compiled_temporal:
            if pattern.search(query):
                analysis['has_temporal'] = True
                analysis['reasons'].append('Temporal complexity detected')
                analysis['complexity_score'] += 0.3
                break
        
        # Check causal patterns
        for pattern in self.compiled_causal:
            if pattern.search(query):
                analysis['has_causal'] = True
                analysis['reasons'].append('Causal relationships detected')
                analysis['complexity_score'] += 0.3
                break
        
        # Check question types
        for qtype, pattern in self.compiled_questions.items():
            if pattern.search(query):
                analysis['question_types'].append(qtype)
        
        if len(analysis['question_types']) > 1:
            analysis['multiple_question_types'] = True
            analysis['reasons'].append(f'Multiple question types: {", ".join(analysis["question_types"])}')
            analysis['complexity_score'] += 0.2
        
        # Normalize complexity score to 0-1 range
        analysis['complexity_score'] = min(analysis['complexity_score'], 1.0)
        
        # Determine decomposition strategy
        analysis['recommended_strategy'] = self._determine_strategy(analysis)
        
        # Make final decision
        min_confidence_threshold = self.config.get("min_confidence_threshold", 0.5)
        analysis['needs_decomposition'] = analysis['complexity_score'] >= min_confidence_threshold
        analysis['confidence'] = analysis['complexity_score']
        
        logger.info(
            f"Complexity analysis: score={analysis['complexity_score']:.2f}, "
            f"needs_decomp={analysis['needs_decomposition']}, "
            f"strategy={analysis['recommended_strategy']}, "
            f"reasons={'; '.join(analysis['reasons'])}"
        )
        
        return analysis
    
    def _determine_strategy(self, analysis: Dict[str, Any]) -> DecompositionStrategy:
        """Determine the best decomposition strategy based on analysis"""
        if analysis['has_temporal']:
            return DecompositionStrategy.TEMPORAL
        elif analysis['has_comparison']:
            return DecompositionStrategy.COMPARATIVE
        elif analysis['has_causal']:
            return DecompositionStrategy.CAUSAL
        elif analysis['entity_count'] > 3:
            return DecompositionStrategy.ENTITY_BASED
        else:
            return DecompositionStrategy.HIERARCHICAL


class LLMQueryDecomposer:
    """
    Uses LLM to decompose complex queries into simpler sub-queries.
    
    Uses GPT-4o-mini for fast, efficient decomposition.
    Returns JSON array of ordered sub-queries with dependencies.
    """
    
    def __init__(self, llm_provider: str = "openai", llm_config: Dict = None):
        """
        Initialize the LLM-based decomposer.
        
        Args:
            llm_provider: LLM provider to use (default: openai)
            llm_config: LLM configuration
        """
        self.llm_provider = llm_provider
        self.llm_config = llm_config or {}
        
        # Create LLM client for decomposition (use fast model)
        try:
            self.llm_client = LLMClientFactory.create(
                provider=llm_provider,
                config=self.llm_config,
                path="fast"  # Use fast path for decomposition
            )
            logger.info(f"LLM decomposer initialized with {llm_provider}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM decomposer: {e}")
            self.llm_client = None
    
    def decompose_query(
        self, 
        query: str, 
        entities: List[str] = None,
        strategy: DecompositionStrategy = DecompositionStrategy.ENTITY_BASED
    ) -> Tuple[List[SubQuery], float]:
        """
        Decompose a complex query into simpler sub-queries.
        
        Args:
            query: The complex query to decompose
            entities: List of entities already extracted
            strategy: Decomposition strategy to use
            
        Returns:
            Tuple of (sub_queries, confidence)
        """
        if not self.llm_client:
            logger.error("LLM client not available for decomposition")
            return [], 0.0
        
        # Prepare the decomposition prompt
        system_prompt = self._build_decomposition_prompt(strategy)
        user_prompt = self._build_user_prompt(query, entities, strategy)
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        try:
            start_time = time.time()
            response = self.llm_client.generate(
                messages=messages,
                temperature=0.1,  # Low temperature for consistent decomposition
                max_tokens=1500  # Increased for more detailed decomposition
            )
            latency_ms = (time.time() - start_time) * 1000
            
            # Parse the JSON response
            sub_queries_data = self._parse_decomposition_response(response.content)
            
            # Convert to SubQuery objects
            sub_queries = []
            for i, sq_data in enumerate(sub_queries_data):
                # Convert string query_type to enum
                query_type_str = sq_data.get('query_type', 'factual')
                try:
                    query_type = QueryType(query_type_str)
                except ValueError:
                    query_type = QueryType.FACTUAL
                
                # Convert string strategy to enum
                strategy_str = sq_data.get('strategy', strategy.value)
                try:
                    sub_query_strategy = DecompositionStrategy(strategy_str)
                except ValueError:
                    sub_query_strategy = strategy
                
                sub_query = SubQuery(
                    id=sq_data.get('id', f"subquery_{i+1}"),
                    text=sq_data.get('text', ''),
                    order=sq_data.get('order', i+1),
                    query_type=query_type,
                    entities=sq_data.get('entities', []),
                    context=sq_data.get('context'),
                    dependencies=sq_data.get('dependencies', []),
                    strategy=sub_query_strategy,
                    confidence=sq_data.get('confidence', 0.0),
                    metadata=sq_data.get('metadata', {})
                )
                sub_queries.append(sub_query)
            
            # Sort by order and validate dependencies
            sub_queries.sort(key=lambda x: x.order)
            self._validate_dependencies(sub_queries)
            
            confidence = self._calculate_decomposition_confidence(response.content, sub_queries)
            
            logger.info(
                f"Decomposed query into {len(sub_queries)} sub-queries "
                f"in {latency_ms:.1f}ms (confidence: {confidence:.2f})"
            )
            
            return sub_queries, confidence
            
        except LLMError as e:
            logger.error(f"LLM decomposition failed: {e}")
            return [], 0.0
        except Exception as e:
            logger.error(f"Unexpected error during decomposition: {e}")
            return [], 0.0
    
    def _build_decomposition_prompt(self, strategy: DecompositionStrategy) -> str:
        """Build the system prompt for query decomposition based on strategy"""
        base_prompt = """You are an expert at breaking down complex questions into simpler, focused sub-questions.

Your task is to decompose a complex query into 2-4 simpler sub-queries that can be answered independently.

Guidelines:
1. Each sub-query should focus on one specific aspect of the original query
2. Order sub-queries logically (general → specific, or chronological)
3. Preserve all important entities and context
4. Ensure sub-queries are answerable with available information
5. Avoid redundancy between sub-queries
6. Identify dependencies between sub-queries when applicable

Return your response as a JSON array with the following structure:
[
  {
    "id": "subquery_1",
    "text": "The sub-question text",
    "order": 1,
    "query_type": "factual|decision|comparison|analysis|recommendation|temporal",
    "entities": ["entity1", "entity2"],
    "context": "Optional context for this sub-query",
    "dependencies": ["subquery_1"],  # IDs of sub-queries this depends on
    "strategy": "entity_based|temporal|comparative|causal|hierarchical",
    "confidence": 0.9,
    "metadata": {"key": "value"}
  }
]"""

        strategy_specific = {
            DecompositionStrategy.ENTITY_BASED: """
            
For ENTITY_BASED decomposition:
- Group sub-queries by entities or topics
- Each sub-query should focus on one primary entity
- Consider relationships between entities
- Example: "Compare Q2 and Q3 financial performance" → ["What was Q2 performance?", "What was Q3 performance?"]""",
            
            DecompositionStrategy.TEMPORAL: """
            
For TEMPORAL decomposition:
- Break down by time periods or sequences
- Maintain chronological order
- Consider trends and changes over time
- Example: "How has our strategy evolved?" → ["What was the initial strategy?", "What changes occurred in Q2?", "What is the current strategy?"]""",
            
            DecompositionStrategy.COMPARATIVE: """
            
For COMPARATIVE decomposition:
- Separate each item being compared
- Include a final comparison sub-query
- Ensure parallel structure for comparison items
- Example: "Compare A and B" → ["What are A's features?", "What are B's features?", "How do A and B compare?"]""",
            
            DecompositionStrategy.CAUSAL: """
            
For CAUSAL decomposition:
- Separate causes from effects
- Identify intermediate steps
- Consider root causes and downstream impacts
- Example: "Why did X happen?" → ["What were the conditions before X?", "What triggered X?", "What were the consequences of X?"]""",
            
            DecompositionStrategy.HIERARCHICAL: """
            
For HIERARCHICAL decomposition:
- Break down from general to specific
- Maintain logical dependency chain
- Each level builds on previous
- Example: "Analyze our market position" → ["What is our overall market?", "What is our segment?", "How do we compare in segment?"]"""
        }
        
        return base_prompt + strategy_specific.get(strategy, "")
    
    def _build_user_prompt(
        self, 
        query: str, 
        entities: List[str] = None,
        strategy: DecompositionStrategy = DecompositionStrategy.ENTITY_BASED
    ) -> str:
        """Build the user prompt with the query to decompose"""
        prompt = f"Decompose this complex query into simpler sub-queries using {strategy.value} strategy:\n\n{query}\n\n"
        
        if entities:
            prompt += f"Key entities identified: {', '.join(entities)}\n\n"
        
        prompt += "Provide the decomposition as a JSON array following the specified format."
        
        return prompt
    
    def _parse_decomposition_response(self, response_content: str) -> List[Dict]:
        """Parse the LLM response to extract sub-queries"""
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\[.*\]', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                sub_queries_data = json.loads(json_str)
                
                # Validate structure
                if isinstance(sub_queries_data, list):
                    return sub_queries_data
            
            # Fallback: try to parse entire response as JSON
            sub_queries_data = json.loads(response_content)
            if isinstance(sub_queries_data, list):
                return sub_queries_data
            
            logger.error(f"Invalid decomposition response format: {response_content}")
            return []
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse decomposition JSON: {e}")
            logger.error(f"Response content: {response_content}")
            return []
    
    def _validate_dependencies(self, sub_queries: List[SubQuery]):
        """Validate and fix dependencies between sub-queries"""
        # Create a map of sub-query IDs to their order
        id_to_order = {sq.id: sq.order for sq in sub_queries}
        
        for sub_query in sub_queries:
            # Validate dependencies exist
            valid_deps = []
            for dep_id in sub_query.dependencies:
                if dep_id in id_to_order:
                    # Only keep dependencies that come before this sub-query
                    if id_to_order[dep_id] < sub_query.order:
                        valid_deps.append(dep_id)
                    else:
                        logger.warning(
                            f"Invalid dependency: {sub_query.id} depends on {dep_id} "
                            f"which comes after it"
                        )
                else:
                    logger.warning(f"Unknown dependency: {sub_query.id} depends on {dep_id}")
            
            sub_query.dependencies = valid_deps
    
    def _calculate_decomposition_confidence(
        self, 
        response_content: str, 
        sub_queries: List[SubQuery]
    ) -> float:
        """Calculate confidence in the decomposition quality"""
        # Base confidence
        confidence = 0.5
        
        try:
            # Check if we can parse valid JSON
            json_match = re.search(r'\[.*\]', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                sub_queries_data = json.loads(json_str)
                
                # Increase confidence based on structure
                if isinstance(sub_queries_data, list) and len(sub_queries_data) > 0:
                    confidence += 0.2
                
                # Check for required fields
                valid_count = 0
                for sq in sub_queries_data:
                    if all(key in sq for key in ['text', 'order', 'query_type']):
                        valid_count += 1
                
                if valid_count == len(sub_queries_data):
                    confidence += 0.2
                
                # Check for reasonable number of sub-queries
                if 2 <= len(sub_queries) <= 4:
                    confidence += 0.1
            
            # Additional confidence from sub-query quality
            if sub_queries:
                avg_confidence = sum(sq.confidence for sq in sub_queries) / len(sub_queries)
                confidence = confidence * 0.7 + avg_confidence * 0.3
            
        except:
            pass
        
        return min(confidence, 1.0)


class AnswerSynthesizer:
    """
    Synthesizes a comprehensive answer from multiple sub-query results.
    
    Combines sub-query answers into a coherent response while maintaining
    context and sources.
    """
    
    def __init__(self, llm_provider: str = "openai", llm_config: Dict = None):
        """
        Initialize the answer synthesizer.
        
        Args:
            llm_provider: LLM provider for synthesis (default: openai)
            llm_config: LLM configuration
        """
        self.llm_provider = llm_provider
        self.llm_config = llm_config or {}
        
        # Create LLM client for synthesis
        try:
            self.llm_client = LLMClientFactory.create(
                provider=llm_provider,
                config=self.llm_config,
                path="standard"  # Use standard model for quality synthesis
            )
            logger.info(f"Answer synthesizer initialized with {llm_provider}")
        except Exception as e:
            logger.error(f"Failed to initialize answer synthesizer: {e}")
            self.llm_client = None
    
    def synthesize_answer(
        self,
        original_query: str,
        sub_query_results: List[SubQueryResult],
        strategy: DecompositionStrategy = DecompositionStrategy.ENTITY_BASED
    ) -> Tuple[str, float]:
        """
        Synthesize a comprehensive answer from sub-query results.
        
        Args:
            original_query: The original complex query
            sub_query_results: Results from processing sub-queries
            strategy: Decomposition strategy used
            
        Returns:
            Tuple of (synthesized_answer, confidence)
        """
        if not sub_query_results:
            return "No information available to answer the query.", 0.0
        
        # If we have an LLM client, use it for intelligent synthesis
        if self.llm_client:
            return self._llm_synthesize(original_query, sub_query_results, strategy)
        else:
            # Fallback to simple concatenation
            return self._simple_synthesize(original_query, sub_query_results)
    
    def _llm_synthesize(
        self,
        original_query: str,
        sub_query_results: List[SubQueryResult],
        strategy: DecompositionStrategy
    ) -> Tuple[str, float]:
        """Use LLM to intelligently synthesize answers"""
        # Prepare synthesis prompt
        system_prompt = self._build_synthesis_prompt(strategy)
        user_prompt = self._build_synthesis_user_prompt(original_query, sub_query_results)
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        try:
            start_time = time.time()
            response = self.llm_client.generate(
                messages=messages,
                temperature=0.3,  # Moderate temperature for balanced synthesis
                max_tokens=2000  # Allow for comprehensive synthesis
            )
            latency_ms = (time.time() - start_time) * 1000
            
            # Calculate confidence based on sub-query results
            confidence = self._calculate_synthesis_confidence(sub_query_results)
            
            logger.info(
                f"LLM synthesis completed in {latency_ms:.1f}ms "
                f"(confidence: {confidence:.2f})"
            )
            
            return response.content, confidence
            
        except LLMError as e:
            logger.error(f"LLM synthesis failed: {e}")
            # Fallback to simple synthesis
            return self._simple_synthesize(original_query, sub_query_results)
    
    def _simple_synthesize(
        self,
        original_query: str,
        sub_query_results: List[SubQueryResult]
    ) -> Tuple[str, float]:
        """Simple synthesis without LLM"""
        answer_parts = [f"Answer to: {original_query}\n"]
        answer_parts.append("=" * 50 + "\n")
        
        for result in sub_query_results:
            answer_parts.append(f"\n{result.sub_query.text.upper()}:\n")
            answer_parts.append(result.answer)
            answer_parts.append("\n" + "-" * 30 + "\n")
        
        # Calculate average confidence
        if sub_query_results:
            confidence = sum(r.confidence for r in sub_query_results) / len(sub_query_results)
        else:
            confidence = 0.0
        
        return "\n".join(answer_parts), confidence
    
    def _build_synthesis_prompt(self, strategy: DecompositionStrategy) -> str:
        """Build the system prompt for answer synthesis based on strategy"""
        base_prompt = """You are an expert at synthesizing information from multiple sources to provide comprehensive answers.

Your task is to combine the answers from several sub-questions into a coherent, comprehensive response to the original query.

Guidelines:
1. Address all aspects of the original query
2. Maintain logical flow and connections between sub-topics
3. Avoid repetition between sub-answers
4. Provide a clear, well-structured response
5. Include key insights and relationships between different parts
6. Maintain factual accuracy based on the provided sub-answers

Structure your response as:
1. Brief overview addressing the main query
2. Detailed breakdown by topic/aspect
3. Summary or conclusion that ties everything together

Focus on clarity, completeness, and logical organization."""

        strategy_specific = {
            DecompositionStrategy.ENTITY_BASED: """
            
For ENTITY_BASED synthesis:
- Group information by entities
- Show relationships between entities
- Highlight interdependencies
- Provide entity-specific insights""",
            
            DecompositionStrategy.TEMPORAL: """
            
For TEMPORAL synthesis:
- Present information chronologically
- Highlight trends and changes over time
- Show cause-and-effect relationships across time
- Emphasize evolution and progression""",
            
            DecompositionStrategy.COMPARATIVE: """
            
For COMPARATIVE synthesis:
- Structure as a clear comparison
- Use parallel structure for compared items
- Highlight similarities and differences
- Provide balanced evaluation""",
            
            DecompositionStrategy.CAUSAL: """
            
For CAUSAL synthesis:
- Clearly separate causes from effects
- Show causal chains
- Identify root causes and downstream impacts
- Explain mechanisms and processes""",
            
            DecompositionStrategy.HIERARCHICAL: """
            
For HIERARCHICAL synthesis:
- Build from general to specific
- Maintain logical dependency chains
- Show how detailed information supports broader conclusions
- Provide layered analysis"""
        }
        
        return base_prompt + strategy_specific.get(strategy, "")
    
    def _build_synthesis_user_prompt(
        self,
        original_query: str,
        sub_query_results: List[SubQueryResult]
    ) -> str:
        """Build the user prompt with synthesis context"""
        prompt = f"Original Query: {original_query}\n\n"
        prompt += "Here are the answers to the sub-questions:\n\n"
        
        for i, result in enumerate(sub_query_results, 1):
            prompt += f"Sub-question {i}: {result.sub_query.text}\n"
            prompt += f"Answer: {result.answer}\n"
            prompt += f"Confidence: {result.confidence:.2f}\n"
            prompt += f"Sources: {', '.join(result.sources)}\n\n"
        
        prompt += "Please synthesize these into a comprehensive answer to the original query."
        
        return prompt
    
    def _calculate_synthesis_confidence(self, sub_query_results: List[SubQueryResult]) -> float:
        """Calculate confidence in the synthesized answer"""
        if not sub_query_results:
            return 0.0
        
        # Weight by sub-query confidence and order (earlier queries often more important)
        weights = []
        confidences = []
        
        for i, result in enumerate(sub_query_results):
            # Earlier sub-queries get slightly higher weight
            weight = 1.0 - (i * 0.1)
            weights.append(max(weight, 0.5))
            confidences.append(result.confidence)
        
        # Calculate weighted average
        total_weight = sum(weights)
        weighted_confidence = sum(c * w for c, w in zip(confidences, weights)) / total_weight
        
        # Factor in the number of successful sub-queries
        success_rate = len([r for r in sub_query_results if r.confidence > 0.5]) / len(sub_query_results)
        
        final_confidence = weighted_confidence * 0.7 + success_rate * 0.3
        
        return min(final_confidence, 1.0)


__all__ = [
    'QueryDecomposer',
    'QueryComplexityDetector',
    'LLMQueryDecomposer',
    'AnswerSynthesizer',
    'SubQuery',
    'SubQueryResult',
    'DecompositionResult',
    'QueryType',
    'DecompositionStrategy'
]