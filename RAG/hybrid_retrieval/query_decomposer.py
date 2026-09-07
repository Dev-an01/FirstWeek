"""
Query Decomposition Module
==========================

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
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from llm_integration.factory import LLMClientFactory
from llm_integration.base_client import LLMMessage, LLMError
from .config import HYBRID_RETRIEVAL_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class SubQuery:
    """Represents a decomposed sub-query"""
    id: str
    text: str
    order: int
    query_type: str  # factual, decision, comparison, etc.
    entities: List[str]
    context: Optional[str] = None


@dataclass
class SubQueryResult:
    """Result from processing a sub-query"""
    sub_query: SubQuery
    results: List[Dict]
    answer: str
    sources: List[str]
    confidence: float
    processing_time_ms: float


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


class QueryComplexityDetector:
    """
    Detects when a query needs decomposition based on various indicators.
    
    Indicators for decomposition:
    - Multiple conjunctions ("and", "but", "while")
    - Comparison words ("compare", "versus", "vs")
    - Multiple entities (>3 distinct)
    - Multiple question types mixed
    - Query length >150 characters
    """
    
    def __init__(self):
        """Initialize the complexity detector with patterns"""
        # Conjunction patterns indicating multiple parts
        self.conjunction_patterns = [
            r'\band\b.*\band\b',  # Multiple "and"s
            r'\bbut\b.*\bbut\b',  # Multiple "but"s
            r'\bwhile\b.*\bwhile\b',  # Multiple "while"s
            r'\balso\b.*\balso\b',  # Multiple "also"s
            r'\bplus\b.*\bplus\b',  # Multiple "plus"s
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
        self.compiled_questions = {k: re.compile(v, re.IGNORECASE) for k, v in self.question_patterns.items()}
    
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
            'question_types': [],
            'multiple_question_types': False,
            'needs_decomposition': False,
            'confidence': 0.0,
            'reasons': []
        }
        
        # Check query length
        if analysis['query_length'] > 150:
            analysis['reasons'].append('Query length > 150 characters')
            analysis['confidence'] += 0.2
        elif analysis['query_length'] > 80:
            analysis['reasons'].append('Query length > 80 characters')
            analysis['confidence'] += 0.1

        # Check word count (more sensitive)
        if analysis['word_count'] > 15:
            analysis['reasons'].append(f'High word count ({analysis["word_count"]} words)')
            analysis['confidence'] += 0.25
        elif analysis['word_count'] > 10:
            analysis['reasons'].append(f'Medium word count ({analysis["word_count"]} words)')
            analysis['confidence'] += 0.15

        # Check entity count
        if analysis['entity_count'] > 3:
            analysis['reasons'].append(f'More than 3 entities ({analysis["entity_count"]})')
            analysis['confidence'] += 0.3

        # Check conjunctions (count "and"s separately)
        and_count = len(re.findall(r'\band\b', query, re.IGNORECASE))
        if and_count >= 2:
            analysis['conjunction_count'] = and_count
            analysis['reasons'].append(f'Multiple "and" conjunctions ({and_count})')
            analysis['confidence'] += 0.3
        else:
            for pattern in self.compiled_conjunctions:
                if pattern.search(query):
                    analysis['conjunction_count'] += 1
            if analysis['conjunction_count'] > 0:
                analysis['reasons'].append(f'Multiple conjunctions detected ({analysis["conjunction_count"]})')
                analysis['confidence'] += 0.25

        # Check comparisons (higher weight)
        for pattern in self.compiled_comparisons:
            if pattern.search(query):
                analysis['has_comparison'] = True
                analysis['reasons'].append('Comparison keywords detected')
                analysis['confidence'] += 0.4  # Increased from 0.35
                break

        # Check for analysis/recommendation keywords
        analysis_keywords = ['analyze', 'analysis', 'recommend', 'recommendation', 'suggest', 'evaluate']
        for keyword in analysis_keywords:
            if keyword in query.lower():
                analysis['reasons'].append(f'Analysis/recommendation keyword: {keyword}')
                analysis['confidence'] += 0.3
                break

        # Check question types
        for qtype, pattern in self.compiled_questions.items():
            if pattern.search(query):
                analysis['question_types'].append(qtype)

        if len(analysis['question_types']) > 1:
            analysis['multiple_question_types'] = True
            analysis['reasons'].append(f'Multiple question types: {", ".join(analysis["question_types"])}')
            analysis['confidence'] += 0.2

        # Normalize confidence to 0-1 range
        analysis['confidence'] = min(analysis['confidence'], 1.0)

        # Make final decision (lowered threshold from 0.5 to 0.4)
        analysis['needs_decomposition'] = analysis['confidence'] >= 0.4

        # Add compatibility fields for tests
        analysis['is_complex'] = analysis['needs_decomposition']
        analysis['complexity_score'] = analysis['confidence']
        
        logger.info(
            f"Complexity analysis: confidence={analysis['confidence']:.2f}, "
            f"needs_decomp={analysis['needs_decomposition']}, "
            f"reasons={'; '.join(analysis['reasons'])}"
        )
        
        return analysis


class LLMQueryDecomposer:
    """
    Uses LLM to decompose complex queries into simpler sub-queries.
    
    Uses GPT-4o-mini for fast, efficient decomposition.
    Returns JSON array of ordered sub-queries.
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
    
    def decompose_query(self, query: str, entities: List[str] = None) -> Tuple[List[SubQuery], float]:
        """
        Decompose a complex query into simpler sub-queries.
        
        Args:
            query: The complex query to decompose
            entities: List of entities already extracted
            
        Returns:
            Tuple of (sub_queries, confidence)
        """
        if not self.llm_client:
            logger.error("LLM client not available for decomposition")
            return [], 0.0
        
        # Prepare the decomposition prompt
        system_prompt = self._build_decomposition_prompt()
        user_prompt = self._build_user_prompt(query, entities)
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        try:
            start_time = time.time()
            response = self.llm_client.generate(
                messages=messages,
                temperature=0.1,  # Low temperature for consistent decomposition
                max_tokens=1000
            )
            latency_ms = (time.time() - start_time) * 1000
            
            # Parse the JSON response
            sub_queries_data = self._parse_decomposition_response(response.content)
            
            # Convert to SubQuery objects
            sub_queries = []
            for i, sq_data in enumerate(sub_queries_data):
                sub_query = SubQuery(
                    id=f"subquery_{i+1}",
                    text=sq_data.get('text', ''),
                    order=sq_data.get('order', i+1),
                    query_type=sq_data.get('query_type', 'factual'),
                    entities=sq_data.get('entities', []),
                    context=sq_data.get('context')
                )
                sub_queries.append(sub_query)
            
            # Sort by order
            sub_queries.sort(key=lambda x: x.order)
            
            confidence = self._calculate_decomposition_confidence(response.content)
            
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
    
    def _build_decomposition_prompt(self) -> str:
        """Build the system prompt for query decomposition"""
        return """You are an expert at breaking down complex questions into simpler, focused sub-questions.

Your task is to decompose a complex query into 2-4 simpler sub-queries that can be answered independently.

Guidelines:
1. Each sub-query should focus on one specific aspect of the original query
2. Order sub-queries logically (general → specific, or chronological)
3. Preserve all important entities and context
4. Ensure sub-queries are answerable with available information
5. Avoid redundancy between sub-queries

Return your response as a JSON array with the following structure:
[
  {
    "text": "The sub-question text",
    "order": 1,
    "query_type": "factual|decision|comparison|analysis",
    "entities": ["entity1", "entity2"],
    "context": "Optional context for this sub-query"
  }
]

Example:
Input: "Compare the Q2 and Q3 financial performance and explain the impact of the new marketing strategy"
Output:
[
  {
    "text": "What was the Q2 financial performance?",
    "order": 1,
    "query_type": "factual",
    "entities": ["Q2"],
    "context": "Financial metrics and results"
  },
  {
    "text": "What was the Q3 financial performance?",
    "order": 2,
    "query_type": "factual",
    "entities": ["Q3"],
    "context": "Financial metrics and results"
  },
  {
    "text": "What was the new marketing strategy and its implementation?",
    "order": 3,
    "query_type": "analysis",
    "entities": ["marketing strategy"],
    "context": "Strategy details and execution"
  },
  {
    "text": "How did the marketing strategy impact Q3 performance compared to Q2?",
    "order": 4,
    "query_type": "comparison",
    "entities": ["Q2", "Q3", "marketing strategy"],
    "context": "Comparative analysis"
  }
]"""
    
    def _build_user_prompt(self, query: str, entities: List[str] = None) -> str:
        """Build the user prompt with the query to decompose"""
        prompt = f"Decompose this complex query into simpler sub-queries:\n\n{query}\n\n"
        
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
    
    def _calculate_decomposition_confidence(self, response_content: str) -> float:
        """Calculate confidence in the decomposition quality"""
        # Simple heuristic based on response structure
        confidence = 0.5  # Base confidence
        
        try:
            # Check if we can parse valid JSON
            json_match = re.search(r'\[.*\]', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                sub_queries_data = json.loads(json_str)
                
                # Increase confidence based on structure
                if isinstance(sub_queries_data, list) and len(sub_queries_data) > 0:
                    confidence += 0.3
                
                # Check for required fields
                valid_count = 0
                for sq in sub_queries_data:
                    if all(key in sq for key in ['text', 'order', 'query_type']):
                        valid_count += 1
                
                if valid_count == len(sub_queries_data):
                    confidence += 0.2
                
        except:
            pass
        
        return min(confidence, 1.0)


class SubQueryProcessor:
    """
    Processes individual sub-queries through the standard retrieval pipeline.
    
    Routes each sub-query through the hybrid retrieval manager and generates
    focused answers for each.
    """
    
    def __init__(self, retrieval_manager):
        """
        Initialize the sub-query processor.
        
        Args:
            retrieval_manager: HybridRetrievalManager instance
        """
        self.retrieval_manager = retrieval_manager
        logger.info("SubQueryProcessor initialized")
    
    def process_sub_queries(
        self,
        sub_queries: List[SubQuery],
        executive_id: str,
        user_context: Dict = None
    ) -> List[SubQueryResult]:
        """
        Process a list of sub-queries through the retrieval pipeline.
        
        Args:
            sub_queries: List of sub-queries to process
            executive_id: Executive context ID
            user_context: User context for RBAC
            
        Returns:
            List of SubQueryResult objects
        """
        results = []
        
        for sub_query in sub_queries:
            logger.info(f"Processing sub-query {sub_query.id}: {sub_query.text[:50]}...")
            
            start_time = time.time()
            
            try:
                # Retrieve relevant documents for this sub-query
                retrieval_response = self.retrieval_manager.retrieve(
                    query=sub_query.text,
                    executive_id=executive_id,
                    user_context=user_context,
                    top_k=5,  # Fewer results for focused sub-queries
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
                    processing_time_ms=processing_time_ms
                )
                
                results.append(sub_query_result)
                
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
                    processing_time_ms=(time.time() - start_time) * 1000
                )
                results.append(sub_query_result)
        
        return results
    
    def _generate_sub_query_answer(self, sub_query: SubQuery, retrieval_response: Dict) -> str:
        """
        Generate a focused answer for a sub-query based on retrieval results.
        
        Args:
            sub_query: The sub-query being answered
            retrieval_response: Results from the retrieval system
            
        Returns:
            Focused answer string
        """
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
        """
        Calculate confidence in the sub-query answer based on retrieval quality.
        
        Args:
            retrieval_response: Response from the retrieval system
            
        Returns:
            Confidence score between 0 and 1
        """
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
        sub_query_results: List[SubQueryResult]
    ) -> Tuple[str, float]:
        """
        Synthesize a comprehensive answer from sub-query results.
        
        Args:
            original_query: The original complex query
            sub_query_results: Results from processing sub-queries
            
        Returns:
            Tuple of (synthesized_answer, confidence)
        """
        if not sub_query_results:
            return "No information available to answer the query.", 0.0
        
        # If we have an LLM client, use it for intelligent synthesis
        if self.llm_client:
            return self._llm_synthesize(original_query, sub_query_results)
        else:
            # Fallback to simple concatenation
            return self._simple_synthesize(original_query, sub_query_results)
    
    def _llm_synthesize(
        self,
        original_query: str,
        sub_query_results: List[SubQueryResult]
    ) -> Tuple[str, float]:
        """Use LLM to intelligently synthesize answers"""
        # Prepare synthesis prompt
        system_prompt = self._build_synthesis_prompt()
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
                max_tokens=1500
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
    
    def _build_synthesis_prompt(self) -> str:
        """Build the system prompt for answer synthesis"""
        return """You are an expert at synthesizing information from multiple sources to provide comprehensive answers.

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
            prompt += f"Confidence: {result.confidence:.2f}\n\n"
        
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


class QueryDecomposer:
    """
    Main orchestrator for query decomposition functionality.
    
    Coordinates complexity detection, LLM decomposition, sub-query processing,
    and answer synthesis.
    """
    
    def __init__(
        self,
        retrieval_manager,
        llm_provider: str = "openai",
        llm_config: Dict = None
    ):
        """
        Initialize the query decomposer.
        
        Args:
            retrieval_manager: HybridRetrievalManager instance
            llm_provider: LLM provider for decomposition/synthesis
            llm_config: LLM configuration
        """
        self.retrieval_manager = retrieval_manager
        self.llm_provider = llm_provider
        self.llm_config = llm_config or {}
        
        # Initialize components
        self.complexity_detector = QueryComplexityDetector()
        self.llm_decomposer = LLMQueryDecomposer(llm_provider, llm_config)
        self.sub_query_processor = SubQueryProcessor(retrieval_manager)
        self.answer_synthesizer = AnswerSynthesizer(llm_provider, llm_config)
        
        logger.info("QueryDecomposer initialized with all components")
    
    def process_query(
        self,
        query: str,
        executive_id: str,
        user_context: Dict = None,
        entities: List[str] = None
    ) -> DecompositionResult:
        """
        Process a query with intelligent decomposition if needed.
        
        Args:
            query: The input query
            executive_id: Executive context ID
            user_context: User context for RBAC
            entities: Pre-extracted entities
            
        Returns:
            DecompositionResult with processing details
        """
        start_time = time.time()
        
        # Default values
        if entities is None:
            entities = []
        if user_context is None:
            user_context = {
                "user_id": "unknown",
                "role": "employee",
                "allowed_scopes": ["public", "internal"]
            }
        
        # Step 1: Detect complexity
        complexity_analysis = self.complexity_detector.detect_complexity(query, entities)
        needs_decomposition = complexity_analysis['needs_decomposition']
        decomposition_confidence = complexity_analysis['confidence']
        
        if not needs_decomposition:
            # Query doesn't need decomposition, return as-is
            logger.info(f"Query doesn't need decomposition (confidence: {decomposition_confidence:.2f})")
            
            return DecompositionResult(
                original_query=query,
                needs_decomposition=False,
                sub_queries=[],
                sub_query_results=[],
                synthesized_answer="",
                all_sources=[],
                total_processing_time_ms=(time.time() - start_time) * 1000,
                decomposition_confidence=decomposition_confidence
            )
        
        logger.info(f"Decomposing complex query (confidence: {decomposition_confidence:.2f})")
        
        # Step 2: Decompose query
        sub_queries, decomp_confidence = self.llm_decomposer.decompose_query(query, entities)
        
        if not sub_queries:
            logger.warning("LLM decomposition failed, proceeding without decomposition")
            return DecompositionResult(
                original_query=query,
                needs_decomposition=False,
                sub_queries=[],
                sub_query_results=[],
                synthesized_answer="",
                all_sources=[],
                total_processing_time_ms=(time.time() - start_time) * 1000,
                decomposition_confidence=0.0
            )
        
        # Step 3: Process sub-queries
        sub_query_results = self.sub_query_processor.process_sub_queries(
            sub_queries,
            executive_id,
            user_context
        )
        
        # Step 4: Synthesize answer
        synthesized_answer, synthesis_confidence = self.answer_synthesizer.synthesize_answer(
            query,
            sub_query_results
        )
        
        # Collect all sources
        all_sources = []
        for result in sub_query_results:
            all_sources.extend(result.sources)
        all_sources = list(set(all_sources))  # Deduplicate
        
        total_time_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"Query decomposition completed in {total_time_ms:.1f}ms "
            f"({len(sub_queries)} sub-queries, {len(all_sources)} sources)"
        )
        
        return DecompositionResult(
            original_query=query,
            needs_decomposition=True,
            sub_queries=sub_queries,
            sub_query_results=sub_query_results,
            synthesized_answer=synthesized_answer,
            all_sources=all_sources,
            total_processing_time_ms=total_time_ms,
            decomposition_confidence=decomposition_confidence
        )


__all__ = [
    'QueryDecomposer',
    'QueryComplexityDetector',
    'LLMQueryDecomposer',
    'SubQueryProcessor',
    'AnswerSynthesizer',
    'SubQuery',
    'SubQueryResult',
    'DecompositionResult'
]