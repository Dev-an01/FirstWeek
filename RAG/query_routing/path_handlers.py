"""
Path Handlers

Implements the three processing paths from Solution Manual section 4.2:
- Fast Path: Simple queries with direct retrieval and single LLM call
- Standard Path: Medium queries with precedent checking
- Agentic Path: Complex queries with ReAct reasoning
"""

import logging
import time
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import re

from .router import ProcessingPath

logger = logging.getLogger(__name__)


class BasePathHandler(ABC):
    """Base class for all path handlers."""
    
    def __init__(self, llm_client, profile_id: str, config: Dict[str, Any]):
        """
        Initialize path handler.
        
        Args:
            llm_client: LLM client instance
            profile_id: Executive profile ID
            config: Path-specific configuration
        """
        self.llm_client = llm_client
        self.profile_id = profile_id
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def handle(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Handle query using this path's strategy.
        
        Args:
            query: User's question
            **kwargs: Additional context (vector_results, graph_results, etc.)
            
        Returns:
            Dict with response, citations, metadata
        """
        pass


class FastPathHandler(BasePathHandler):
    """
    Fast Path Handler for simple factual queries.
    
    Target latency: 0.8-1.5 seconds
    Use cases: "What is...", "Who is...", "Define..."
    
    Strategy:
    1. Retrieve (single shot, no iteration)
       - Hybrid search with top_k=10
       - RBAC filtering applied
       - Return: Policy docs, definitions, facts
    2. Generate Response (single LLM call)
       - Model: GPT-4o-mini (faster, cheaper)
       - Temperature: 0.3 (factual)
       - Max tokens: 500 (concise answer)
       - Context: Retrieved docs + executive style
    3. Format and Return
       - Answer with citations
       - No complex reasoning trace needed
       - Cache aggressively (semantic cache)
    """
    
    def handle(self, query: str, vector_results: List[Dict[str, Any]] = None, 
             memory: List[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        Handle query using fast path strategy.
        
        Args:
            query: User's question
            vector_results: Vector search results
            memory: Recent conversation history
            **kwargs: Additional context
            
        Returns:
            Dict with response, citations, metadata
        """
        start_time = time.time()
        
        self.logger.info(f"Fast path handling query: {query[:50]}...")
        
        # 1. Prepare context (top 5 results only)
        max_results = self.config.get("max_results", 5)
        context_vector_results = (vector_results or [])[:max_results]
        context_memory = memory or []
        
        # 2. Build prompt for fast path
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(query, context_vector_results, context_memory)
        
        # 3. Generate response
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        llm_response = self.llm_client.generate(messages)
        
        # 4. Format response
        total_time = (time.time() - start_time) * 1000
        
        response = {
            "answer": llm_response.content,
            "citations": self._extract_citations(llm_response.content, context_vector_results),
            "sources": self._extract_sources(context_vector_results),
            "metadata": {
                "path": ProcessingPath.FAST.value,
                "total_latency_ms": total_time,
                "llm_latency_ms": llm_response.latency_ms,
                "llm_tokens": llm_response.usage,
                "llm_model": llm_response.model,
                "results_used": len(context_vector_results),
                "target_latency_ms": self.config.get("target_latency_ms", 1500)
            }
        }
        
        # Check latency target
        target = self.config.get("target_latency_ms", 1500)
        if total_time > target:
            self.logger.warning(
                f"Fast path exceeded target latency: {total_time:.0f}ms > {target}ms"
            )
        else:
            self.logger.info(
                f"Fast path completed in {total_time:.0f}ms (target: {target}ms)"
            )
        
        return response
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for fast path."""
        # This would normally use the profile manager to get the executive's style
        # For now, using a simplified version
        return f"""You are an executive assistant responding to a simple factual query.
        
        Guidelines:
        - Provide direct, concise answers
        - Focus on factual information from provided context
        - Use minimal elaboration
        - Cite sources for all factual claims
        - Maintain professional but approachable tone
        
        Context includes relevant documents and recent conversation history.
        Use only the information provided in context.
        """
    
    def _build_user_prompt(
        self, 
        query: str, 
        vector_results: List[Dict[str, Any]], 
        memory: List[Dict[str, Any]]
    ) -> str:
        """Build user prompt for fast path."""
        # Format context
        context_parts = []
        
        if vector_results:
            context_parts.append("RELEVANT DOCUMENTS:")
            for i, result in enumerate(vector_results[:5], 1):
                title = result.get('title', 'Untitled')
                content = result.get('content', '')[:300]  # First 300 chars
                score = result.get('score', 0.0)
                context_parts.append(
                    f"{i}. {title} (relevance: {score:.2f}):\n{content}..."
                )
        
        if memory:
            context_parts.append("\nRECENT CONVERSATION HISTORY:")
            for i, turn in enumerate(memory[-3:], 1):  # Last 3 turns
                turn_query = turn.get('query', '')
                turn_response = turn.get('response', '')[:200]  # First 200 chars
                context_parts.append(
                    f"{i}. Q: {turn_query}\n   A: {turn_response}..."
                )
        
        context_text = "\n\n".join(context_parts) if context_parts else "No specific context available."
        
        return f"""CONTEXT:
{context_text}

QUESTION: {query}

Please provide a direct, factual answer based on the context above.
Cite your sources using [Source: document_name] format.
"""
    
    def _extract_citations(self, response: str, vector_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract citations from response."""
        citations = []
        
        # Simple citation extraction - look for [Source: ...] patterns
        import re
        citation_pattern = r'\[Source:\s*([^\]]+)\]'
        matches = re.findall(citation_pattern, response)
        
        for match in matches:
            source_name = match.strip()
            citations.append({
                "source": source_name,
                "raw_text": f"[Source: {source_name}]",
                "position": response.find(match),
                "context": ""  # Would extract surrounding text in real implementation
            })
        
        # If no explicit citations, create implicit ones from top results
        if not citations and vector_results:
            for result in vector_results[:3]:  # Top 3 results
                title = result.get('title', 'Untitled')
                citations.append({
                    "source": title,
                    "raw_text": f"[Source: {title}]",
                    "position": 0,  # Would find actual position
                    "context": result.get('content', '')[:100]
                })
        
        return citations
    
    def _extract_sources(self, vector_results: List[Dict[str, Any]]) -> List[str]:
        """Extract unique source names from results."""
        sources = []
        seen = set()
        
        for result in vector_results:
            title = result.get('title', 'Untitled')
            if title not in seen:
                sources.append(title)
                seen.add(title)
        
        return sources


class StandardPathHandler(BasePathHandler):
    """
    Standard Path Handler for medium complexity queries.
    
    Target latency: 1.5-2.5 seconds
    Use cases: "Should we...", "Would you approve...", "Recommend..."
    
    Strategy:
    1. Retrieve Company Knowledge
       - Hybrid search with top_k=20
       - Entity extraction from query
       - Graph traversal around entities
       - Adaptive reranking (likely lightweight)
    2. Search Personal Memory
       - Query THIS executive's past decisions
       - Multi-signal scoring
       - Top 5 precedents
       - Include outcomes if available
    3. Generate Response (single LLM call)
       - Model: GPT-4o (higher quality)
       - Temperature: 0.5 (balanced)
       - Context: Retrieved docs + precedents + executive style
       - Structured output: Decision + reasoning + citations
       - Max tokens: 800
    4. Store in Memory and Return
       - Save to episodic_memory
       - Link to session
       - Return with interaction_id for feedback
    """
    
    def handle(
        self, 
        query: str, 
        vector_results: List[Dict[str, Any]] = None,
        graph_results: Optional[List[Dict[str, Any]]] = None,
        precedents: Optional[List[Dict[str, Any]]] = None,
        memory: List[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Handle query using standard path strategy.
        
        Args:
            query: User's question
            vector_results: Vector search results
            graph_results: Knowledge graph context
            precedents: Historical similar queries
            memory: Recent conversation history
            **kwargs: Additional context
            
        Returns:
            Dict with response, citations, metadata
        """
        start_time = time.time()
        
        self.logger.info(f"Standard path handling query: {query[:50]}...")
        
        # 1. Prepare context (top 10 results + graph + precedents)
        max_results = self.config.get("max_results", 10)
        context_vector_results = (vector_results or [])[:max_results]
        context_graph_results = (graph_results or [])[:5] if graph_results else []
        context_precedents = (precedents or [])[:3] if precedents else []
        context_memory = memory or []
        
        # 2. Build prompt for standard path
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            query, context_vector_results, context_graph_results, 
            context_precedents, context_memory
        )
        
        # 3. Generate response
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        llm_response = self.llm_client.generate(messages)
        
        # 4. Format response
        total_time = (time.time() - start_time) * 1000
        
        response = {
            "answer": llm_response.content,
            "citations": self._extract_citations(llm_response.content, context_vector_results),
            "sources": self._extract_sources(context_vector_results),
            "metadata": {
                "path": ProcessingPath.STANDARD.value,
                "total_latency_ms": total_time,
                "llm_latency_ms": llm_response.latency_ms,
                "llm_tokens": llm_response.usage,
                "llm_model": llm_response.model,
                "results_used": len(context_vector_results),
                "graph_context_used": len(context_graph_results),
                "precedents_used": len(context_precedents),
                "target_latency_ms": self.config.get("target_latency_ms", 2500)
            }
        }
        
        # Check latency target
        target = self.config.get("target_latency_ms", 2500)
        if total_time > target:
            self.logger.warning(
                f"Standard path exceeded target latency: {total_time:.0f}ms > {target}ms"
            )
        else:
            self.logger.info(
                f"Standard path completed in {total_time:.0f}ms (target: {target}ms)"
            )
        
        return response
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for standard path."""
        return f"""You are an executive assistant responding to a decision or recommendation query.
        
        Guidelines:
        - Provide thoughtful, balanced recommendations
        - Consider multiple perspectives and stakeholders
        - Reference precedents when relevant
        - Explain your reasoning clearly
        - Acknowledge uncertainties and assumptions
        - Cite sources for all factual claims
        - Maintain professional, executive tone
        
        Context includes relevant documents, graph relationships, precedents, and recent conversation history.
        Use only the information provided in context.
        """
    
    def _build_user_prompt(
        self, 
        query: str, 
        vector_results: List[Dict[str, Any]], 
        graph_results: List[Dict[str, Any]],
        precedents: List[Dict[str, Any]],
        memory: List[Dict[str, Any]]
    ) -> str:
        """Build user prompt for standard path."""
        # Format context
        context_parts = []
        
        if vector_results:
            context_parts.append("RELEVANT DOCUMENTS:")
            for i, result in enumerate(vector_results[:10], 1):
                title = result.get('title', 'Untitled')
                content = result.get('content', '')[:300]  # First 300 chars
                score = result.get('score', 0.0)
                context_parts.append(
                    f"{i}. {title} (relevance: {score:.2f}):\n{content}..."
                )
        
        if graph_results:
            context_parts.append("\nGRAPH RELATIONSHIPS:")
            for i, result in enumerate(graph_results[:5], 1):
                context_parts.append(
                    f"{i}. {result.get('title', 'Unknown')}: {result.get('summary', '')[:200]}"
                )
        
        if precedents:
            context_parts.append("\nRELEVANT PRECEDENTS:")
            for i, precedent in enumerate(precedents[:3], 1):
                situation = precedent.get('situation', '')[:150]
                decision = precedent.get('decision', '')[:150]
                outcome = precedent.get('outcome', '')[:100]
                context_parts.append(
                    f"{i}. Situation: {situation}\n   Decision: {decision}\n   Outcome: {outcome}"
                )
        
        if memory:
            context_parts.append("\nRECENT CONVERSATION HISTORY:")
            for i, turn in enumerate(memory[-3:], 1):  # Last 3 turns
                turn_query = turn.get('query', '')
                turn_response = turn.get('response', '')[:200]  # First 200 chars
                context_parts.append(
                    f"{i}. Q: {turn_query}\n   A: {turn_response}..."
                )
        
        context_text = "\n\n".join(context_parts) if context_parts else "No specific context available."
        
        return f"""CONTEXT:
{context_text}

QUESTION: {query}

Please provide a thoughtful recommendation based on the context above.
Include:
1. Clear decision or recommendation
2. Reasoning behind your recommendation
3. Consideration of relevant precedents
4. Acknowledgment of uncertainties
5. Cite your sources using [Source: document_name] format.
"""
    
    def _extract_citations(self, response: str, vector_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract citations from response."""
        citations = []
        
        # Simple citation extraction - look for [Source: ...] patterns
        import re
        citation_pattern = r'\[Source:\s*([^\]]+)\]'
        matches = re.findall(citation_pattern, response)
        
        for match in matches:
            source_name = match.strip()
            citations.append({
                "source": source_name,
                "raw_text": f"[Source: {source_name}]",
                "position": response.find(match),
                "context": ""  # Would extract surrounding text in real implementation
            })
        
        # If no explicit citations, create implicit ones from top results
        if not citations and vector_results:
            for result in vector_results[:5]:  # Top 5 results
                title = result.get('title', 'Untitled')
                citations.append({
                    "source": title,
                    "raw_text": f"[Source: {title}]",
                    "position": 0,  # Would find actual position
                    "context": result.get('content', '')[:100]
                })
        
        return citations
    
    def _extract_sources(self, vector_results: List[Dict[str, Any]]) -> List[str]:
        """Extract unique source names from results."""
        sources = []
        seen = set()
        
        for result in vector_results:
            title = result.get('title', 'Untitled')
            if title not in seen:
                sources.append(title)
                seen.add(title)
        
        return sources


class AgenticPathHandler(BasePathHandler):
    """
    Agentic Path Handler for complex analytical queries.
    
    Target latency: 3-5 seconds
    Use cases: "Compare...", "Analyze...", "Evaluate trade-offs..."
    
    Strategy:
    1. Detect Decomposition Need
       - Is query multi-part?
       - Does it require multiple information sources?
       - Would breaking down improve quality?
    2. Query Decomposition (if needed)
       - LLM breaks question into sub-queries
       - Example: "Compare A and B" → ["What is A?", "What is B?", "Compare them"]
       - Sub-queries answered independently
    3. ReAct Reasoning Loop (iterative)
       - Iteration 1: LLM Thought → Action → Observation
       - Iteration 2-N: Continue until confident
       - Final Answer: Synthesize all findings
    4. Synthesis (if decomposed)
       - Combine sub-query answers
       - Ensure coherence
       - Add executive's perspective
    5. Store Rich Context and Return
       - Save full reasoning trace
       - Tag as complex query
       - Higher importance score
       - Return with expandable reasoning
    """
    
    def __init__(self, llm_client, profile_id: str, config: Dict[str, Any]):
        """
        Initialize agentic path handler.
        
        Args:
            llm_client: LLM client instance
            profile_id: Executive profile ID
            config: Path-specific configuration
        """
        super().__init__(llm_client, profile_id, config)
        
        # ReAct loop configuration
        self.multi_hop_enabled = config.get("multi_hop_enabled", True)
        self.max_react_steps = config.get("max_react_steps", 5)
        self.react_confidence_threshold = config.get("react_confidence_threshold", 0.7)
        self.enable_tool_integration = config.get("enable_tool_integration", True)
        
        # Performance tracking
        self.react_metrics = {
            "total_queries": 0,
            "react_loops_executed": 0,
            "average_steps_per_query": 0,
            "average_confidence": 0
        }
    
    def handle(
        self, 
        query: str, 
        vector_results: List[Dict[str, Any]] = None,
        graph_results: Optional[List[Dict[str, Any]]] = None,
        precedents: Optional[List[Dict[str, Any]]] = None,
        memory: List[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Handle query using agentic path strategy.
        
        Args:
            query: User's question
            vector_results: Vector search results
            graph_results: Knowledge graph context
            precedents: Historical similar queries
            memory: Recent conversation history
            **kwargs: Additional context
            
        Returns:
            Dict with response, citations, metadata
        """
        start_time = time.time()
        
        self.logger.info(f"Agentic path handling query: {query[:50]}...")
        
        # 1. Prepare comprehensive context
        max_results = self.config.get("max_results", 15)
        context_vector_results = (vector_results or [])[:max_results]
        context_graph_results = (graph_results or [])[:10] if graph_results else []
        context_precedents = (precedents or [])[:5] if precedents else []
        context_memory = memory or []
        
        # 2. Check if query needs decomposition
        needs_decomposition = self._check_decomposition_need(query)
        
        if needs_decomposition:
            # Use decomposition strategy
            response = self._handle_with_decomposition(
                query, context_vector_results, context_graph_results, 
                context_precedents, context_memory
            )
        else:
            # Use ReAct reasoning loop
            response = self._handle_with_react(
                query, context_vector_results, context_graph_results, 
                context_precedents, context_memory
            )
        
        # 5. Add metadata
        total_time = (time.time() - start_time) * 1000
        response["metadata"].update({
            "path": ProcessingPath.AGENTIC.value,
            "total_latency_ms": total_time,
            "multi_hop_used": self.multi_hop_enabled,
            "target_latency_ms": self.config.get("target_latency_ms", 5000)
        })
        
        # Check latency target
        target = self.config.get("target_latency_ms", 5000)
        if total_time > target:
            self.logger.warning(
                f"Agentic path exceeded target latency: {total_time:.0f}ms > {target}ms"
            )
        else:
            self.logger.info(
                f"Agentic path completed in {total_time:.0f}ms (target: {target}ms)"
            )
        
        return response
    
    def _check_decomposition_need(self, query: str) -> bool:
        """Check if query needs decomposition."""
        # Check query length
        if len(query) > 150:
            return True
        
        # Check multiple conjunctions
        if re.search(r'\band\b.*\band\b', query, re.IGNORECASE):
            return True
        
        # Check comparison words
        if re.search(r'\b(compare|versus|vs|difference between|similarities)\b', query, re.IGNORECASE):
            return True
        
        return False
    
    def _handle_with_decomposition(
        self, 
        query: str, 
        vector_results: List[Dict[str, Any]], 
        graph_results: List[Dict[str, Any]],
        precedents: List[Dict[str, Any]],
        memory: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle query using decomposition strategy."""
        self.logger.info(f"Using decomposition strategy for query: {query[:50]}...")
        
        # Step 1: Decompose query into sub-queries
        sub_queries = self._decompose_query(query)
        
        # Step 2: Answer each sub-query independently
        sub_answers = []
        for sub_query in sub_queries:
            # For each sub-query, we would use the standard path handler
            # This is a simplified implementation - in reality, each sub-query
            # would go through the full routing and processing pipeline
            sub_answer = f"Answer to '{sub_query}': [This would be answered using the standard path handler]"
            sub_answers.append(sub_answer)
        
        # Step 3: Synthesize final answer
        synthesis_prompt = f"""
        Based on the following sub-query answers, provide a comprehensive answer to the original question:
        
        ORIGINAL QUESTION: {query}
        
        SUB-QUERIES AND ANSWERS:
        """
        
        for i, (sub_q, sub_a) in enumerate(zip(sub_queries, sub_answers), 1):
            synthesis_prompt += f"{i}. Q: {sub_q}\n   A: {sub_a}\n"
        
        synthesis_prompt += """
        Please synthesize a comprehensive answer that:
        1. Addresses all aspects of the original question
        2. Maintains logical consistency between sub-answers
        3. Provides clear reasoning and structure
        4. Cites relevant sources
        """
        
        # Generate synthesis
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": synthesis_prompt}
        ]
        
        llm_response = self.llm_client.generate(messages)
        
        return {
            "answer": llm_response.content,
            "citations": self._extract_citations(llm_response.content, vector_results),
            "sources": self._extract_sources(vector_results),
            "metadata": {
                "decomposition_used": True,
                "sub_queries": sub_queries,
                "sub_answers": sub_answers
            }
        }
    
    def _handle_with_react(
        self, 
        query: str, 
        vector_results: List[Dict[str, Any]], 
        graph_results: List[Dict[str, Any]],
        precedents: List[Dict[str, Any]],
        memory: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle query using ReAct reasoning loop."""
        self.logger.info(f"Using ReAct reasoning for query: {query[:50]}...")
        
        # Initialize ReAct state
        react_state = {
            "original_query": query,
            "current_step": 0,
            "max_steps": self.max_react_steps,
            "steps": [],
            "accumulated_context": {
                "vector_results": vector_results.copy(),
                "graph_results": graph_results.copy() if graph_results else [],
                "precedents": precedents.copy() if precedents else [],
                "memory": memory.copy() if memory else [],
                "intermediate_findings": []
            },
            "is_complete": False,
            "final_answer": None
        }
        
        # Main ReAct loop
        while not react_state["is_complete"] and react_state["current_step"] < react_state["max_steps"]:
            step_start = time.time()
            react_state["current_step"] += 1
            
            self.logger.debug(f"ReAct step {react_state['current_step']}/{react_state['max_steps']}")
            
            # Generate thought and determine action
            thought, action_type, action_query, confidence = self._generate_thought_and_action(react_state)
            
            # Execute action
            observation, sources_used = self._execute_react_action(action_type, action_query, react_state)
            
            # Create step record
            step = {
                "step_number": react_state["current_step"],
                "thought": thought,
                "action_type": action_type,
                "action_query": action_query,
                "observation": observation,
                "confidence": confidence,
                "sources_used": sources_used,
                "processing_time_ms": (time.time() - step_start) * 1000
            }
            
            react_state["steps"].append(step)
            
            # Update accumulated context
            self._update_accumulated_context(react_state, step)
            
            # Check if we should continue or finalize
            if confidence >= self.react_confidence_threshold:
                react_state["is_complete"] = True
        
        # Generate final answer
        final_response = self._generate_final_answer(react_state)
        
        # Update metrics
        self._update_react_metrics(react_state)
        
        return {
            "answer": final_response["content"],
            "citations": self._extract_citations(final_response["content"], vector_results),
            "sources": self._extract_sources(vector_results),
            "metadata": {
                "react_used": True,
                "react_steps": len(react_state["steps"]),
                "react_processing_time_ms": final_response.get("processing_time_ms", 0),
                "react_steps_detail": react_state["steps"]
            }
        }
    
    def _decompose_query(self, query: str) -> List[str]:
        """Decompose complex query into sub-queries."""
        # This is a simplified implementation - in reality, would use LLM
        # For demonstration, using simple pattern matching
        
        # Example patterns for decomposition
        if "compare" in query.lower():
            # Extract entities to compare
            entities = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query)
            if len(entities) >= 2:
                return [
                    f"What is {entities[0]}?",
                    f"What is {entities[1]}?",
                    f"Compare {entities[0]} and {entities[1]}"
                ]
        
        # Default: return as single sub-query
        return [query]
    
    def _generate_thought_and_action(self, react_state: Dict[str, Any]) -> tuple:
        """Generate thought and determine next action using LLM."""
        # This is a simplified implementation - in reality, would use LLM
        # For demonstration, using simple heuristics
        
        step = react_state["current_step"]
        max_steps = react_state["max_steps"]
        original_query = react_state["original_query"]
        
        # Simple heuristic for demonstration
        if step == 1:
            thought = f"I need to understand what information is available to answer: {original_query}"
            action_type = "analyze"
            action_query = original_query
            confidence = 0.5
        elif step == 2:
            thought = "Based on initial analysis, I need to gather more specific information."
            action_type = "search"
            action_query = "additional information related to the query"
            confidence = 0.6
        elif step == 3:
            thought = "I have sufficient information to provide a comprehensive answer."
            action_type = "finalize"
            action_query = ""
            confidence = 0.8
        else:
            thought = "I should finalize my answer based on available information."
            action_type = "finalize"
            action_query = ""
            confidence = 0.7
        
        return thought, action_type, action_query, confidence
    
    def _execute_react_action(self, action_type: str, action_query: str, react_state: Dict[str, Any]) -> tuple:
        """Execute the determined action using appropriate tools."""
        # This is a simplified implementation - in reality, would use actual tools
        # For demonstration, returning mock observations
        
        if action_type == "analyze":
            observation = "Analysis of available information shows relevant documents and context."
            sources_used = [r.get("id", "") for r in react_state["accumulated_context"]["vector_results"][:3]]
        elif action_type == "search":
            observation = f"Search for '{action_query}' would return additional relevant information."
            sources_used = []
        elif action_type == "finalize":
            observation = "Sufficient information gathered. Ready to generate final answer."
            sources_used = [r.get("id", "") for r in react_state["accumulated_context"]["vector_results"]]
        else:
            observation = f"Unknown action type: {action_type}"
            sources_used = []
        
        return observation, sources_used
    
    def _update_accumulated_context(self, react_state: Dict[str, Any], step: Dict[str, Any]):
        """Update accumulated context with new step information."""
        finding = {
            "step": step["step_number"],
            "action": step["action_type"],
            "query": step["action_query"],
            "observation": step["observation"],
            "sources": step["sources_used"]
        }
        react_state["accumulated_context"]["intermediate_findings"].append(finding)
    
    def _generate_final_answer(self, react_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final comprehensive answer based on all ReAct steps."""
        steps_summary = "\n\n".join([
            f"Step {step['step_number']}: {step['thought']}\n"
            f"Action: {step['action_type']} - {step['action_query']}\n"
            f"Observation: {step['observation']}\n"
            for step in react_state["steps"]
        ])
        
        final_prompt = f"""
        Based on the following multi-step analysis, provide a comprehensive answer to the original question:
        
        ORIGINAL QUESTION: {react_state['original_query']}
        
        ANALYSIS STEPS:
        {steps_summary}
        
        Please provide:
        1. Executive Summary (2-3 sentences)
        2. Detailed Analysis (with evidence from the steps above)
        3. Recommendations (if applicable)
        4. Key Considerations (risks, trade-offs, next steps)
        
        Cite your sources using [Source: document_name] format where appropriate.
        """
        
        # Generate final answer
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": final_prompt}
        ]
        
        llm_response = self.llm_client.generate(messages)
        
        return {
            "content": llm_response.content,
            "processing_time_ms": sum(s.get("processing_time_ms", 0) for s in react_state["steps"])
        }
    
    def _update_react_metrics(self, react_state: Dict[str, Any]):
        """Update ReAct performance metrics."""
        self.react_metrics["total_queries"] += 1
        self.react_metrics["react_loops_executed"] += 1
        
        if react_state["steps"]:
            avg_steps = self.react_metrics["average_steps_per_query"]
            total_queries = self.react_metrics["total_queries"]
            self.react_metrics["average_steps_per_query"] = (
                (avg_steps * (total_queries - 1) + len(react_state["steps"])) / total_queries
            )
            
            avg_confidence = self.react_metrics["average_confidence"]
            step_confidence = sum(s.get("confidence", 0) for s in react_state["steps"]) / len(react_state["steps"])
            self.react_metrics["average_confidence"] = (
                (avg_confidence * (total_queries - 1) + step_confidence) / total_queries
            )
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for agentic path."""
        return f"""You are an executive assistant responding to a complex analytical query.
        
        Guidelines:
        - Provide thorough, multi-dimensional analysis
        - Consider multiple perspectives and stakeholders
        - Evaluate trade-offs and implications
        - Present structured reasoning with evidence
        - Acknowledge uncertainties and assumptions
        - Provide actionable insights
        - Cite sources for all factual claims
        - Maintain professional, executive tone
        
        Context includes relevant documents, graph relationships, precedents, and recent conversation history.
        Use only the information provided in context.
        """
    
    def _extract_citations(self, response: str, vector_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract citations from response."""
        citations = []
        
        # Simple citation extraction - look for [Source: ...] patterns
        import re
        citation_pattern = r'\[Source:\s*([^\]]+)\]'
        matches = re.findall(citation_pattern, response)
        
        for match in matches:
            source_name = match.strip()
            citations.append({
                "source": source_name,
                "raw_text": f"[Source: {source_name}]",
                "position": response.find(match),
                "context": ""  # Would extract surrounding text in real implementation
            })
        
        # If no explicit citations, create implicit ones from top results
        if not citations and vector_results:
            for result in vector_results[:5]:  # Top 5 results
                title = result.get('title', 'Untitled')
                citations.append({
                    "source": title,
                    "raw_text": f"[Source: {title}]",
                    "position": 0,  # Would find actual position
                    "context": result.get('content', '')[:100]
                })
        
        return citations
    
    def _extract_sources(self, vector_results: List[Dict[str, Any]]) -> List[str]:
        """Extract unique source names from results."""
        sources = []
        seen = set()
        
        for result in vector_results:
            title = result.get('title', 'Untitled')
            if title not in seen:
                sources.append(title)
                seen.add(title)
        
        return sources