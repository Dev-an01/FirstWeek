"""
ReAct Tools for AI Officer

Implements tool integration framework and specific tools for ReAct reasoning.
Tools provide capabilities for hybrid search, entity retrieval, analysis, comparison, and finalization.

Based on Solution Manual section 6.2: ReAct Agentic Reasoning
"""

import logging
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from .react_reasoning import ToolResult, ReActState

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """Context provided to tools during execution"""
    query: str
    state: ReActState
    hybrid_retrieval_manager: Optional[Any] = None
    graph_context_provider: Optional[Any] = None
    executive_id: Optional[str] = None


class BaseTool:
    """
    Base class for ReAct tools.
    
    All tools should inherit from this class and implement the execute method.
    """
    
    def __init__(self, name: str, description: str):
        """
        Initialize tool.
        
        Args:
            name: Tool name (used for routing)
            description: Tool description for LLM
        """
        self.name = name
        self.description = description
    
    def __call__(self, query: str, context: ToolContext) -> ToolResult:
        """
        Make tool callable - delegates to execute method.
        
        Args:
            query: Tool-specific query
            context: Tool execution context
            
        Returns:
            ToolResult with observation and data
        """
        return self.execute(query, context)
    
    def execute(self, query: str, context: ToolContext) -> ToolResult:
        """
        Execute the tool.
        
        Args:
            query: Tool-specific query
            context: Tool execution context
            
        Returns:
            ToolResult with observation and data
        """
        raise NotImplementedError("Subclasses must implement execute method")
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get tool schema for LLM function calling.
        
        Returns:
            Tool schema dictionary
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific query for this tool"
                    }
                },
                "required": ["query"]
            }
        }


class HybridSearchTool(BaseTool):
    """
    Tool for hybrid search across vector, graph, and memory sources.
    
    Searches for relevant documents using the hybrid retrieval manager.
    """
    
    def __init__(self):
        super().__init__(
            name="hybrid_search",
            description="Search for relevant documents using hybrid retrieval (vector + graph + memory)"
        )
    
    def execute(self, query: str, context: ToolContext) -> ToolResult:
        """
        Execute hybrid search.
        
        Args:
            query: Search query
            context: Tool execution context
            
        Returns:
            ToolResult with search results
        """
        try:
            if not context.hybrid_retrieval_manager:
                return ToolResult(
                    success=False,
                    data=None,
                    observation="Hybrid retrieval manager not available",
                    error="Missing hybrid_retrieval_manager"
                )
            
            # Execute hybrid search
            search_results = context.hybrid_retrieval_manager.retrieve(
                query=query,
                executive_id=context.executive_id or "default",
                top_k=10,
                strategy="auto"
            )
            
            # Extract results and sources
            results = search_results.get("results", [])
            sources = [result.get("id", "") for result in results]
            
            # Format observation
            if results:
                observation = self._format_search_results(results)
            else:
                observation = f"No results found for query: {query}"
            
            return ToolResult(
                success=True,
                data=search_results,
                observation=observation,
                sources_used=sources
            )
            
        except Exception as e:
            logger.error(f"HybridSearchTool failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                observation=f"Search failed: {str(e)}",
                error=str(e)
            )
    
    def _format_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Format search results for observation"""
        formatted = []
        for i, result in enumerate(results[:5], 1):  # Limit to top 5
            title = result.get("title", "Untitled")
            content = result.get("content", "")[:200]
            score = result.get("final_score", 0.0)
            formatted.append(f"{i}. {title} (relevance: {score:.2f})\n{content}...")
        
        return f"Found {len(results)} relevant results:\n" + "\n".join(formatted)


class GetEntityTool(BaseTool):
    """
    Tool for retrieving entity information from the knowledge graph.
    
    Extracts and provides detailed information about specific entities.
    """
    
    def __init__(self):
        super().__init__(
            name="get_entity",
            description="Get detailed information about a specific entity (person, company, project, etc.)"
        )
    
    def execute(self, query: str, context: ToolContext) -> ToolResult:
        """
        Execute entity retrieval.
        
        Args:
            query: Entity name or identifier
            context: Tool execution context
            
        Returns:
            ToolResult with entity information
        """
        try:
            if not context.graph_context_provider:
                return ToolResult(
                    success=False,
                    data=None,
                    observation="Graph context provider not available",
                    error="Missing graph_context_provider"
                )
            
            # Discover entity context
            entity_context = context.graph_context_provider.discover_context(
                query=f"Tell me about {query}",
                allowed_scopes=["public", "internal"]  # Default scopes
            )
            
            if entity_context.get("has_context"):
                entities = entity_context.get("entities", [])
                relationships = entity_context.get("relationships", [])
                
                # Format observation
                observation = self._format_entity_info(query, entities, relationships)
                
                return ToolResult(
                    success=True,
                    data=entity_context,
                    observation=observation,
                    sources_used=[e.get("node_id", "") for e in entities]
                )
            else:
                return ToolResult(
                    success=True,
                    data={},
                    observation=f"No information found about entity: {query}",
                    sources_used=[]
                )
                
        except Exception as e:
            logger.error(f"GetEntityTool failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                observation=f"Entity lookup failed: {str(e)}",
                error=str(e)
            )
    
    def _format_entity_info(self, query: str, entities: List[Dict], relationships: List[Dict]) -> str:
        """Format entity information for observation"""
        info = [f"Entity Information for: {query}"]
        
        for entity in entities:
            name = entity.get("matched_name", entity.get("text", "Unknown"))
            entity_type = entity.get("type", "Unknown")
            confidence = entity.get("confidence", 0.0)
            info.append(f"- {name} ({entity_type}, confidence: {confidence:.2f})")
        
        if relationships:
            info.append("\nRelated Information:")
            for rel in relationships[:5]:  # Limit to top 5
                source = rel.get("source", "Unknown")
                target = rel.get("target", "Unknown")
                distance = rel.get("distance", 0)
                info.append(f"- {source} → {target} (distance: {distance})")
        
        return "\n".join(info)


class AnalyzeTool(BaseTool):
    """
    Tool for analyzing existing information and context.
    
    Performs analysis on accumulated information from previous steps.
    """
    
    def __init__(self):
        super().__init__(
            name="analyze",
            description="Analyze existing information and context to extract insights"
        )
    
    def execute(self, query: str, context: ToolContext) -> ToolResult:
        """
        Execute analysis on accumulated context.
        
        Args:
            query: Analysis query
            context: Tool execution context
            
        Returns:
            ToolResult with analysis results
        """
        try:
            # Get accumulated findings
            findings = context.state.accumulated_context.get("intermediate_findings", [])
            tool_data = context.state.accumulated_context.get("tool_data", {})
            
            if not findings and not tool_data:
                return ToolResult(
                    success=True,
                    data={},
                    observation="No information available for analysis",
                    sources_used=[]
                )
            
            # Perform analysis based on query
            analysis_result = self._perform_analysis(query, findings, tool_data)
            
            # Extract sources from findings
            sources = []
            for finding in findings:
                sources.extend(finding.get("sources", []))
            sources = list(set(sources))  # Deduplicate
            
            return ToolResult(
                success=True,
                data=analysis_result,
                observation=analysis_result["observation"],
                sources_used=sources
            )
            
        except Exception as e:
            logger.error(f"AnalyzeTool failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                observation=f"Analysis failed: {str(e)}",
                error=str(e)
            )
    
    def _perform_analysis(self, query: str, findings: List[Dict], tool_data: Dict) -> Dict[str, Any]:
        """Perform analysis based on query and accumulated findings"""
        analysis_type = self._determine_analysis_type(query)
        
        if analysis_type == "summary":
            return self._analyze_summary(findings)
        elif analysis_type == "patterns":
            return self._analyze_patterns(findings, tool_data)
        elif analysis_type == "constraints":
            return self._analyze_constraints(findings)
        else:
            return self._analyze_general(query, findings)
    
    def _determine_analysis_type(self, query: str) -> str:
        """Determine type of analysis based on query keywords"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["summarize", "summary", "overview"]):
            return "summary"
        elif any(word in query_lower for word in ["pattern", "trend", "recurring"]):
            return "patterns"
        elif any(word in query_lower for word in ["constraint", "limitation", "restriction"]):
            return "constraints"
        else:
            return "general"
    
    def _analyze_summary(self, findings: List[Dict]) -> Dict[str, Any]:
        """Analyze and summarize findings"""
        if not findings:
            return {"observation": "No findings to summarize"}
        
        # Count action types
        action_counts = {}
        for finding in findings:
            action = finding.get("action", "unknown")
            action_counts[action] = action_counts.get(action, 0) + 1
        
        # Get unique sources
        all_sources = []
        for finding in findings:
            all_sources.extend(finding.get("sources", []))
        unique_sources = list(set(all_sources))
        
        observation = f"""
Summary of Findings:
- Total steps analyzed: {len(findings)}
- Actions taken: {dict(action_counts)}
- Unique sources consulted: {len(unique_sources)}
- Average confidence: {sum(f.get('confidence', 0) for f in findings) / len(findings):.2f}
"""
        
        return {
            "observation": observation.strip(),
            "action_counts": action_counts,
            "unique_sources": unique_sources,
            "total_findings": len(findings)
        }
    
    def _analyze_patterns(self, findings: List[Dict], tool_data: Dict) -> Dict[str, Any]:
        """Analyze patterns in findings"""
        patterns = []
        
        # Look for recurring themes
        all_queries = [f.get("query", "") for f in findings]
        common_words = self._find_common_words(all_queries)
        
        # Look for confidence trends
        confidences = [f.get("confidence", 0) for f in findings]
        if len(confidences) > 1:
            avg_confidence = sum(confidences) / len(confidences)
            trend = "improving" if confidences[-1] > avg_confidence else "declining"
        else:
            trend = "insufficient data"
        
        observation = f"""
Pattern Analysis:
- Common themes: {', '.join(common_words[:5])}
- Confidence trend: {trend}
- Total data points: {len(findings)}
"""
        
        return {
            "observation": observation.strip(),
            "common_themes": common_words,
            "confidence_trend": trend
        }
    
    def _analyze_constraints(self, findings: List[Dict]) -> Dict[str, Any]:
        """Analyze constraints mentioned in findings"""
        constraints = []
        
        for finding in findings:
            observation = finding.get("observation", "")
            query = finding.get("query", "")
            
            # Look for constraint keywords
            constraint_keywords = ["limit", "constraint", "restriction", "cannot", "unable", "maximum", "minimum"]
            text = (observation + " " + query).lower()
            
            for keyword in constraint_keywords:
                if keyword in text:
                    # Extract sentence containing keyword
                    sentences = text.split('.')
                    for sentence in sentences:
                        if keyword in sentence:
                            constraints.append(sentence.strip())
                            break
        
        observation = f"Constraints identified:\n" + "\n".join(f"- {c}" for c in constraints[:5])
        
        return {
            "observation": observation,
            "constraints": constraints
        }
    
    def _analyze_general(self, query: str, findings: List[Dict]) -> Dict[str, Any]:
        """Perform general analysis"""
        if not findings:
            return {"observation": "No findings available for analysis"}
        
        # Simple analysis based on most recent findings
        recent_findings = findings[-3:]  # Last 3 findings
        insights = []
        
        for finding in recent_findings:
            action = finding.get("action", "")
            confidence = finding.get("confidence", 0)
            if confidence > 0.7:
                insights.append(f"High confidence {action}: {finding.get('observation', '')[:100]}...")
        
        observation = f"Analysis Insights:\n" + "\n".join(f"- {i}" for i in insights)
        
        return {
            "observation": observation,
            "insights": insights
        }
    
    def _find_common_words(self, texts: List[str], min_freq: int = 2) -> List[str]:
        """Find common words across multiple texts"""
        if not texts:
            return []
        
        # Simple word frequency analysis
        word_counts = {}
        for text in texts:
            words = text.lower().split()
            for word in words:
                if len(word) > 3:  # Skip short words
                    word_counts[word] = word_counts.get(word, 0) + 1
        
        # Return words that appear in multiple texts
        common = [word for word, count in word_counts.items() if count >= min_freq]
        return sorted(common, key=lambda w: word_counts[w], reverse=True)


class CompareTool(BaseTool):
    """
    Tool for comparing multiple options or scenarios.
    
    Performs comparative analysis based on accumulated information.
    """
    
    def __init__(self):
        super().__init__(
            name="compare",
            description="Compare multiple options, scenarios, or alternatives based on available information"
        )
    
    def execute(self, query: str, context: ToolContext) -> ToolResult:
        """
        Execute comparison analysis.
        
        Args:
            query: Comparison query
            context: Tool execution context
            
        Returns:
            ToolResult with comparison results
        """
        try:
            # Extract options from query
            options = self._extract_options(query)
            
            if len(options) < 2:
                return ToolResult(
                    success=True,
                    data={},
                    observation="Need at least 2 options to compare. Please specify what to compare.",
                    sources_used=[]
                )
            
            # Get relevant findings for each option
            findings = context.state.accumulated_context.get("intermediate_findings", [])
            option_data = self._gather_option_data(options, findings)
            
            # Perform comparison
            comparison_result = self._perform_comparison(options, option_data)
            
            # Extract sources
            all_sources = []
            for data in option_data.values():
                all_sources.extend(data.get("sources", []))
            sources = list(set(all_sources))
            
            return ToolResult(
                success=True,
                data=comparison_result,
                observation=comparison_result["observation"],
                sources_used=sources
            )
            
        except Exception as e:
            logger.error(f"CompareTool failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                observation=f"Comparison failed: {str(e)}",
                error=str(e)
            )
    
    def _extract_options(self, query: str) -> List[str]:
        """Extract options to compare from query"""
        # Look for comparison patterns
        # Pattern 1: "compare A and B"
        match = re.search(r'compare\s+(.+?)\s+and\s+(.+?)(?:\s|$)', query, re.IGNORECASE)
        if match:
            return [match.group(1).strip(), match.group(2).strip()]
        
        # Pattern 2: "A vs B"
        match = re.search(r'(.+?)\s+vs\s+(.+?)(?:\s|$)', query, re.IGNORECASE)
        if match:
            return [match.group(1).strip(), match.group(2).strip()]
        
        # Pattern 3: "differences between A and B"
        match = re.search(r'differences?\s+between\s+(.+?)\s+and\s+(.+?)(?:\s|$)', query, re.IGNORECASE)
        if match:
            return [match.group(1).strip(), match.group(2).strip()]
        
        # Default: try to extract capitalized words as options
        words = re.findall(r'\b[A-Z][a-z]+\b', query)
        return list(set(words))[:5]  # Limit to 5 options
    
    def _gather_option_data(self, options: List[str], findings: List[Dict]) -> Dict[str, Dict]:
        """Gather relevant data for each option"""
        option_data = {opt: {"sources": [], "observations": [], "confidence": []} for opt in options}
        
        for finding in findings:
            observation = finding.get("observation", "")
            query = finding.get("query", "")
            sources = finding.get("sources", [])
            confidence = finding.get("confidence", 0)
            
            # Check if finding mentions any option
            for option in options:
                if option.lower() in observation.lower() or option.lower() in query.lower():
                    option_data[option]["observations"].append(observation)
                    option_data[option]["sources"].extend(sources)
                    option_data[option]["confidence"].append(confidence)
        
        # Deduplicate sources
        for opt in option_data:
            option_data[opt]["sources"] = list(set(option_data[opt]["sources"]))
        
        return option_data
    
    def _perform_comparison(self, options: List[str], option_data: Dict[str, Dict]) -> Dict[str, Any]:
        """Perform comparison between options"""
        comparison = []
        
        for option in options:
            data = option_data[option]
            obs_count = len(data["observations"])
            avg_confidence = sum(data["confidence"]) / len(data["confidence"]) if data["confidence"] else 0
            source_count = len(data["sources"])
            
            comparison.append({
                "option": option,
                "data_points": obs_count,
                "avg_confidence": avg_confidence,
                "sources": source_count
            })
        
        # Sort by data points (more information is better)
        comparison.sort(key=lambda x: x["data_points"], reverse=True)
        
        # Build observation
        observation = "Comparison Results:\n\n"
        for i, comp in enumerate(comparison, 1):
            observation += f"{i}. {comp['option']}:\n"
            observation += f"   - Data points: {comp['data_points']}\n"
            observation += f"   - Average confidence: {comp['avg_confidence']:.2f}\n"
            observation += f"   - Sources: {comp['sources']}\n\n"
        
        return {
            "observation": observation.strip(),
            "comparison_table": comparison,
            "ranked_options": [c["option"] for c in comparison]
        }


class FinalizeTool(BaseTool):
    """
    Tool for finalizing the reasoning process and generating a comprehensive answer.
    
    Synthesizes all accumulated information into a final response.
    """
    
    def __init__(self):
        super().__init__(
            name="finalize",
            description="Finalize the reasoning process and generate a comprehensive answer based on all accumulated information"
        )
    
    def execute(self, query: str, context: ToolContext) -> ToolResult:
        """
        Execute finalization.
        
        Args:
            query: Finalization query (usually empty)
            context: Tool execution context
            
        Returns:
            ToolResult with final synthesized answer
        """
        try:
            # Get all accumulated information
            findings = context.state.accumulated_context.get("intermediate_findings", [])
            tool_data = context.state.accumulated_context.get("tool_data", {})
            
            # Synthesize final answer
            synthesis = self._synthesize_final_answer(
                original_query=context.state.original_query,
                findings=findings,
                tool_data=tool_data
            )
            
            # Collect all sources
            all_sources = []
            for finding in findings:
                all_sources.extend(finding.get("sources", []))
            sources = list(set(all_sources))
            
            return ToolResult(
                success=True,
                data={"synthesis": synthesis},
                observation=synthesis["observation"],
                sources_used=sources
            )
            
        except Exception as e:
            logger.error(f"FinalizeTool failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                observation=f"Finalization failed: {str(e)}",
                error=str(e)
            )
    
    def _synthesize_final_answer(self, original_query: str, findings: List[Dict], tool_data: Dict) -> Dict[str, Any]:
        """Synthesize final answer from all accumulated information"""
        # Count actions and confidence
        action_counts = {}
        total_confidence = 0
        for finding in findings:
            action = finding.get("action", "unknown")
            action_counts[action] = action_counts.get(action, 0) + 1
            total_confidence += finding.get("confidence", 0)
        
        avg_confidence = total_confidence / len(findings) if findings else 0
        
        # Extract key insights
        insights = []
        for finding in findings:
            if finding.get("confidence", 0) > 0.7:  # High confidence findings
                insights.append(finding.get("observation", "")[:200])
        
        # Build synthesis
        observation = f"""
FINAL SYNTHESIS for query: {original_query}

Analysis Summary:
- Total reasoning steps: {len(findings)}
- Actions taken: {dict(action_counts)}
- Average confidence: {avg_confidence:.2f}
- High-confidence insights: {len(insights)}

Key Findings:
{chr(10).join(f"- {insight}" for insight in insights[:5])}

Ready to provide comprehensive answer based on this analysis.
"""
        
        return {
            "observation": observation.strip(),
            "action_counts": action_counts,
            "average_confidence": avg_confidence,
            "key_insights": insights,
            "total_steps": len(findings)
        }


class ToolRegistry:
    """
    Registry for managing ReAct tools.
    
    Provides tool discovery and execution interface.
    """
    
    def __init__(self):
        """Initialize tool registry"""
        self.tools = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register default ReAct tools"""
        self.register_tool(HybridSearchTool())
        self.register_tool(GetEntityTool())
        self.register_tool(AnalyzeTool())
        self.register_tool(CompareTool())
        self.register_tool(FinalizeTool())
    
    def register_tool(self, tool: BaseTool):
        """
        Register a tool.
        
        Args:
            tool: Tool instance to register
        """
        self.tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        return self.tools.get(name)
    
    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Get all registered tools"""
        return self.tools.copy()
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all registered tools"""
        return [tool.get_schema() for tool in self.tools.values()]
    
    def execute_tool(
        self,
        name: str,
        query: str,
        context: ToolContext
    ) -> ToolResult:
        """
        Execute a tool by name.
        
        Args:
            name: Tool name
            query: Tool query
            context: Tool execution context
            
        Returns:
            ToolResult from tool execution
        """
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                observation=f"Tool not found: {name}",
                error=f"Unknown tool: {name}"
            )
        
        return tool.execute(query, context)


# Create global tool registry instance
tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance"""
    return tool_registry


def get_available_tools() -> Dict[str, BaseTool]:
    """
    Get all available tools as a dictionary.

    Returns:
        Dict mapping tool names to tool instances
    """
    return tool_registry.get_all_tools()


def create_tool_context(
    query: str,
    state: ReActState,
    hybrid_retrieval_manager: Optional[Any] = None,
    graph_context_provider: Optional[Any] = None,
    executive_id: Optional[str] = None
) -> ToolContext:
    """
    Create tool context for tool execution.
    
    Args:
        query: Tool query
        state: ReAct state
        hybrid_retrieval_manager: Hybrid retrieval manager
        graph_context_provider: Graph context provider
        executive_id: Executive ID
        
    Returns:
        ToolContext instance
    """
    return ToolContext(
        query=query,
        state=state,
        hybrid_retrieval_manager=hybrid_retrieval_manager,
        graph_context_provider=graph_context_provider,
        executive_id=executive_id
    )


__all__ = [
    'BaseTool',
    'HybridSearchTool',
    'GetEntityTool',
    'AnalyzeTool',
    'CompareTool',
    'FinalizeTool',
    'ToolRegistry',
    'ToolContext',
    'get_tool_registry',
    'get_available_tools',
    'create_tool_context'
]