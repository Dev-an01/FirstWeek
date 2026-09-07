"""
ReAct Reasoning System for AI Officer

Implements the ReAct (Reasoning and Acting) pattern for complex queries.
Provides iterative thought-action-observe loops with tool integration.

Based on Solution Manual section 6.2: ReAct Agentic Reasoning
"""

import logging
import time
import json
import re
from typing import Dict, Any, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from .base_client import BaseLLMClient, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class ReActActionType(Enum):
    """Types of actions in ReAct loop"""
    SEARCH = "search"
    ANALYZE = "analyze"
    COMPARE = "compare"
    FINALIZE = "finalize"


@dataclass
class ReActStep:
    """Single step in ReAct reasoning process"""
    step_number: int
    thought: str
    action_type: ReActActionType
    action_query: str
    observation: str
    confidence: float
    sources_used: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    tool_result: Optional[Dict[str, Any]] = None


@dataclass
class ReActState:
    """State tracking for ReAct loop"""
    original_query: str
    current_step: int = 0
    max_steps: int = 5
    steps: List[ReActStep] = field(default_factory=list)
    accumulated_context: Dict[str, Any] = field(default_factory=dict)
    is_complete: bool = False
    final_answer: Optional[str] = None
    total_processing_time_ms: float = 0.0
    confidence_threshold: float = 0.7
    context_window_limit: int = 8000  # Token limit for context


@dataclass
class ToolResult:
    """Result from tool execution"""
    success: bool
    data: Any
    observation: str
    sources_used: List[str] = field(default_factory=list)
    error: Optional[str] = None


class ReActReasoner:
    """
    ReAct reasoning system for complex analytical queries.
    
    Implements the Thought-Act-Observe pattern:
    1. Generate thought about what information is needed
    2. Select and execute appropriate tool
    3. Observe results and update context
    4. Determine if more information is needed
    5. Continue until confident or max steps reached
    6. Generate final comprehensive answer
    
    Features:
    - Tool integration (hybrid_search, get_entity, analyze, compare, finalize)
    - Context accumulation across steps
    - Confidence-based continuation logic
    - Multi-hop reasoning capabilities
    - Context window management
    - Comprehensive logging and tracing
    """
    
    def __init__(
        self,
        llm_client: BaseLLMClient,
        tools: Dict[str, Callable],
        config: Dict[str, Any] = None
    ):
        """
        Initialize ReAct reasoner.
        
        Args:
            llm_client: LLM client for generating thoughts and actions
            tools: Dictionary of available tools
            config: Configuration parameters
        """
        self.llm_client = llm_client
        self.tools = tools
        
        # Configuration with defaults
        self.config = config or {}
        self.max_steps = self.config.get("max_steps", 5)
        self.confidence_threshold = self.config.get("confidence_threshold", 0.7)
        self.context_window_limit = self.config.get("context_window_limit", 8000)
        self.enable_tracing = self.config.get("enable_tracing", True)
        
        # Performance tracking
        self.metrics = {
            "total_queries": 0,
            "average_steps": 0,
            "average_confidence": 0,
            "average_time_ms": 0
        }
        
        logger.info(f"ReActReasoner initialized with {len(tools)} tools")
        logger.info(f"Config: max_steps={self.max_steps}, confidence_threshold={self.confidence_threshold}")
    
    def reason(
        self,
        query: str,
        initial_context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Execute ReAct reasoning loop for a query.

        Args:
            query: User's original query
            initial_context: Initial context from retrieval
            system_prompt: Executive system prompt to use for final answer generation

        Returns:
            Tuple of (final_answer, metadata)
        """
        # Store system prompt for final answer generation
        self._executive_system_prompt = system_prompt
        start_time = time.time()
        
        logger.info(f"Starting ReAct reasoning for query: {query[:100]}...")
        
        # Initialize ReAct state
        state = ReActState(
            original_query=query,
            max_steps=self.max_steps,
            confidence_threshold=self.confidence_threshold,
            context_window_limit=self.context_window_limit
        )
        
        # Add initial context if provided
        if initial_context:
            state.accumulated_context.update(initial_context)
        
        # Main ReAct loop
        while not state.is_complete and state.current_step < state.max_steps:
            step_start = time.time()
            state.current_step += 1
            
            logger.debug(f"ReAct step {state.current_step}/{state.max_steps}")
            
            # Generate thought and determine action
            thought, action_type, action_query, confidence = self._generate_thought_and_action(state)
            
            # Execute action
            observation, sources_used, tool_result = self._execute_action(
                action_type, action_query, state
            )
            
            # Create step record
            step = ReActStep(
                step_number=state.current_step,
                thought=thought,
                action_type=action_type,
                action_query=action_query,
                observation=observation,
                confidence=confidence,
                sources_used=sources_used,
                processing_time_ms=(time.time() - step_start) * 1000,
                tool_result=tool_result
            )
            
            state.steps.append(step)
            
            # Update accumulated context
            self._update_accumulated_context(state, step)
            
            # Check if we should continue or finalize
            should_continue = self._should_continue(state, confidence)
            if not should_continue:
                state.is_complete = True
                break
        
        # Generate final answer
        final_answer, final_metadata = self._generate_final_answer(state)
        
        # Update metrics
        state.total_processing_time_ms = (time.time() - start_time) * 1000
        self._update_metrics(state)
        
        logger.info(
            f"ReAct completed in {state.current_step} steps, "
            f"{state.total_processing_time_ms:.0f}ms total"
        )
        
        return final_answer, final_metadata
    
    def _generate_thought_and_action(
        self,
        state: ReActState
    ) -> Tuple[str, ReActActionType, str, float]:
        """
        Generate thought and determine next action using LLM.
        
        Args:
            state: Current ReAct state
            
        Returns:
            Tuple of (thought, action_type, action_query, confidence)
        """
        # Build context for LLM
        context_summary = self._build_context_summary(state)
        
        # Create ReAct prompt
        react_prompt = f"""
You are an analytical AI assistant using the ReAct (Reasoning and Acting) framework.

ORIGINAL QUERY: {state.original_query}

CURRENT STEP: {state.current_step}/{state.max_steps}

PREVIOUS STEPS:
{context_summary}

Based on the current context, provide your next thought and action in this format:

THOUGHT: [Your reasoning about what information you still need and why]

ACTION: [One of: search, analyze, compare, finalize]

ACTION_QUERY: [Specific query or analysis to perform]

CONFIDENCE: [0.0-1.0 confidence level that this action will help answer the original query]

Guidelines:
- Use 'search' for specific information gaps (e.g., "search for European market regulations")
- Use 'analyze' to examine existing information (e.g., "analyze current capacity constraints")  
- Use 'compare' to evaluate multiple options (e.g., "compare market entry strategies")
- Use 'finalize' only when you have sufficient information to answer comprehensively
- Be specific and focused in your action queries
- Consider what a business executive would need to make a decision
- If you have gathered substantial information and can provide a comprehensive answer, use 'finalize'
"""
        
        messages = [
            LLMMessage(role="system", content="You are an analytical AI assistant using ReAct reasoning."),
            LLMMessage(role="user", content=react_prompt)
        ]
        
        # Generate response
        response = self.llm_client.generate(
            messages,
            temperature=0.3,  # Lower temperature for consistent reasoning
            max_tokens=500   # Limit response length
        )
        
        # Parse response
        thought, action_type, action_query, confidence = self._parse_react_response(response.content)
        
        return thought, action_type, action_query, confidence
    
    def _execute_action(
        self,
        action_type: ReActActionType,
        action_query: str,
        state: ReActState
    ) -> Tuple[str, List[str], Optional[ToolResult]]:
        """
        Execute the determined action using appropriate tool.
        
        Args:
            action_type: Type of action to execute
            action_query: Query for the action
            state: Current ReAct state
            
        Returns:
            Tuple of (observation, sources_used, tool_result)
        """
        tool_name = action_type.value
        sources_used = []
        
        if tool_name in self.tools:
            try:
                # Execute tool
                tool_func = self.tools[tool_name]
                tool_result = tool_func(action_query, state)
                
                if isinstance(tool_result, ToolResult):
                    observation = tool_result.observation
                    sources_used = tool_result.sources_used
                elif isinstance(tool_result, dict):
                    observation = tool_result.get("observation", "Tool executed")
                    sources_used = tool_result.get("sources_used", [])
                else:
                    observation = str(tool_result)
                    sources_used = []
                
                logger.debug(f"Tool {tool_name} executed successfully")
                
            except Exception as e:
                logger.error(f"Tool {tool_name} failed: {e}")
                observation = f"Error executing {tool_name}: {str(e)}"
                tool_result = ToolResult(
                    success=False,
                    data=None,
                    observation=observation,
                    error=str(e)
                )
        else:
            observation = f"Unknown tool: {tool_name}. Available tools: {list(self.tools.keys())}"
            tool_result = ToolResult(
                success=False,
                data=None,
                observation=observation,
                error=f"Tool {tool_name} not found"
            )
        
        return observation, sources_used, tool_result
    
    def _parse_react_response(self, response: str) -> Tuple[str, ReActActionType, str, float]:
        """
        Parse LLM response to extract thought, action, action_query, and confidence.
        
        Args:
            response: LLM response text
            
        Returns:
            Tuple of (thought, action_type, action_query, confidence)
        """
        # Default values
        thought = "Need to analyze the query further"
        action_type = ReActActionType.ANALYZE
        action_query = ""
        confidence = 0.5
        
        # Extract thought
        thought_match = re.search(r'THOUGHT:\s*(.+?)(?=ACTION:|$)', response, re.IGNORECASE | re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
        
        # Extract action
        action_match = re.search(r'ACTION:\s*(\w+)', response, re.IGNORECASE)
        if action_match:
            action_str = action_match.group(1).lower()
            action_map = {
                'search': ReActActionType.SEARCH,
                'analyze': ReActActionType.ANALYZE,
                'compare': ReActActionType.COMPARE,
                'finalize': ReActActionType.FINALIZE
            }
            action_type = action_map.get(action_str, ReActActionType.ANALYZE)
        
        # Extract action query
        query_match = re.search(r'ACTION_QUERY:\s*(.+?)(?=CONFIDENCE:|$)', response, re.IGNORECASE | re.DOTALL)
        if query_match:
            action_query = query_match.group(1).strip()
        
        # Extract confidence
        confidence_match = re.search(r'CONFIDENCE:\s*([0-9.]+)', response, re.IGNORECASE)
        if confidence_match:
            try:
                confidence = float(confidence_match.group(1))
                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0,1]
            except ValueError:
                pass
        
        return thought, action_type, action_query, confidence
    
    def _build_context_summary(self, state: ReActState) -> str:
        """Build a summary of ReAct context for the LLM"""
        if not state.steps:
            return "No previous steps. This is the initial analysis."
        
        summary_lines = []
        for step in state.steps[-3:]:  # Show last 3 steps
            summary_lines.append(
                f"Step {step.step_number}: {step.thought}\n"
                f"Action: {step.action_type.value} - {step.action_query}\n"
                f"Observation: {step.observation[:200]}...\n"
                f"Confidence: {step.confidence:.2f}\n"
            )
        
        return "\n".join(summary_lines)
    
    def _update_accumulated_context(self, state: ReActState, step: ReActStep):
        """Update accumulated context with new step information"""
        # Add to intermediate findings
        finding = {
            "step": step.step_number,
            "action": step.action_type.value,
            "query": step.action_query,
            "observation": step.observation,
            "sources": step.sources_used,
            "confidence": step.confidence
        }
        
        if "intermediate_findings" not in state.accumulated_context:
            state.accumulated_context["intermediate_findings"] = []
        
        state.accumulated_context["intermediate_findings"].append(finding)
        
        # Add tool result data if available
        if step.tool_result and hasattr(step.tool_result, 'data'):
            if "tool_data" not in state.accumulated_context:
                state.accumulated_context["tool_data"] = {}
            state.accumulated_context["tool_data"][f"step_{step.step_number}"] = step.tool_result.data
        
        logger.debug(f"Updated accumulated context with step {step.step_number}")
    
    def _should_continue(self, state: ReActState, confidence: float) -> bool:
        """Determine if ReAct loop should continue"""
        # Stop if we reached max steps
        if state.current_step >= state.max_steps:
            logger.info("ReAct stopping: reached max steps")
            return False
        
        # Stop if last action was finalize
        if state.steps and state.steps[-1].action_type == ReActActionType.FINALIZE:
            logger.info("ReAct stopping: finalize action executed")
            return False
        
        # Stop if confidence is high enough
        if confidence >= state.confidence_threshold:
            logger.info(f"ReAct stopping: confidence {confidence:.2f} >= threshold {state.confidence_threshold}")
            return False
        
        # Check context window limit
        estimated_context_size = self._estimate_context_size(state)
        if estimated_context_size > state.context_window_limit:
            logger.info(f"ReAct stopping: context window limit reached ({estimated_context_size} > {state.context_window_limit})")
            return False
        
        # Continue otherwise
        return True
    
    def _estimate_context_size(self, state: ReActState) -> int:
        """Estimate the size of accumulated context in tokens"""
        # Rough estimation: 1 token ≈ 4 characters
        context_text = json.dumps(state.accumulated_context, default=str)
        return len(context_text) // 4
    
    def _generate_final_answer(self, state: ReActState) -> Tuple[str, Dict[str, Any]]:
        """Generate final comprehensive answer based on all ReAct steps"""
        # Build comprehensive context (limit to last 3 steps to save tokens)
        recent_steps = state.steps[-3:] if len(state.steps) > 3 else state.steps
        steps_summary = "\n\n".join([
            f"Step {step.step_number}: {step.thought}\n"
            f"Action: {step.action_type.value} - {step.action_query}\n"
            f"Observation: {step.observation[:500]}..."  # Truncate observations
            for step in recent_steps
        ])
        
        # Create final prompt
        final_prompt = f"""
Based on the following multi-step analysis, provide a comprehensive answer to the original query.

ORIGINAL QUERY: {state.original_query}

ANALYSIS STEPS:
{steps_summary}

ACCUMULATED FINDINGS:
{json.dumps(state.accumulated_context, indent=2, default=str)[:2000]}...

Synthesize these findings into a conversational response. Cite sources using [Source: document_name] format.

════════════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL FORMATTING REQUIREMENT - MANDATORY - YOUR RESPONSE WILL BE REJECTED IF VIOLATED ⚠️
════════════════════════════════════════════════════════════════════════════════

FORBIDDEN (DO NOT USE):
✗ **Bold headers** like "**What happened**" or "**Analysis**"
✗ Numbered bold lists like "1. **First point**"
✗ Emoji headers like "🔍 **Section**"
✗ Report-style sections

REQUIRED FORMAT:
✓ Natural paragraphs like a Slack message or email
✓ Plain text with simple bullets (- item) only if listing
✓ Conversational flow, not report structure

EXAMPLE OF WRONG FORMAT:
"**Summary** Here's what I found. **Key Points** 1. **First**... 2. **Second**..."

EXAMPLE OF CORRECT FORMAT:
"Let me walk you through this. The main thing I noticed is... When I looked at the data, it showed... I'd recommend..."

YOUR RESPONSE MUST LOOK LIKE A REAL PERSON'S MESSAGE, NOT A STRUCTURED REPORT.
════════════════════════════════════════════════════════════════════════════════
"""

        # Generate final response using executive system prompt if available
        if hasattr(self, '_executive_system_prompt') and self._executive_system_prompt:
            # Use the full executive persona prompt with anti-formatting rules
            system_content = self._executive_system_prompt
            logger.info("[ReAct] Using executive system prompt for final answer")
        else:
            # Fallback to simple prompt
            system_content = "You are the executive speaking in first person. Respond conversationally, not like a formal report. DO NOT use bold headers like **Section** or emoji headers."
            logger.warning("[ReAct] No executive system prompt provided, using fallback")

        messages = [
            LLMMessage(role="system", content=system_content),
            LLMMessage(role="user", content=final_prompt)
        ]
        
        final_response = self.llm_client.generate(
            messages,
            temperature=0.5,  # Balanced temperature
            max_tokens=400   # Reduced to fit within 8k token budget
        )
        
        # Build metadata
        metadata = {
            "react_steps": len(state.steps),
            "react_processing_time_ms": state.total_processing_time_ms,
            "react_confidence": sum(s.confidence for s in state.steps) / len(state.steps) if state.steps else 0,
            "react_actions": [step.action_type.value for step in state.steps],
            "accumulated_findings": state.accumulated_context.get("intermediate_findings", []),
            "sources_used": list(set(source for step in state.steps for source in step.sources_used))
        }
        
        return final_response.content, metadata
    
    def _update_metrics(self, state: ReActState):
        """Update ReAct performance metrics"""
        self.metrics["total_queries"] += 1
        
        if state.steps:
            avg_steps = self.metrics["average_steps"]
            total_queries = self.metrics["total_queries"]
            self.metrics["average_steps"] = (
                (avg_steps * (total_queries - 1) + len(state.steps)) / total_queries
            )
            
            avg_confidence = self.metrics["average_confidence"]
            step_confidence = sum(s.confidence for s in state.steps) / len(state.steps)
            self.metrics["average_confidence"] = (
                (avg_confidence * (total_queries - 1) + step_confidence) / total_queries
            )
            
            avg_time = self.metrics["average_time_ms"]
            self.metrics["average_time_ms"] = (
                (avg_time * (total_queries - 1) + state.total_processing_time_ms) / total_queries
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get ReAct performance metrics"""
        return self.metrics.copy()
    
    def reset_metrics(self):
        """Reset performance metrics"""
        self.metrics = {
            "total_queries": 0,
            "average_steps": 0,
            "average_confidence": 0,
            "average_time_ms": 0
        }


__all__ = [
    'ReActReasoner',
    'ReActActionType',
    'ReActStep',
    'ReActState',
    'ToolResult'
]