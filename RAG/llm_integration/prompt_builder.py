"""
Prompt Builder for LLM Integration

REFACTORED (2025-01-15): Now uses centralized rules from rules.py
- System prompts built via build_system_prompt_from_rules() (single source of truth)
- Word limits, anti-AI rules, identity oath all from rules.py
- No more deprecated ProfileManager.generate_system_prompt() usage

Constructs prompts from retrieval context and executive profiles.
Implements Template Method pattern for flexible prompt assembly.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

from profile_management.profile_manager import get_profile_manager
# Import from centralized rules - SINGLE SOURCE OF TRUTH
from conversation_engine.prompt.rules import get_word_limit

logger = logging.getLogger(__name__)


@dataclass
class RetrievalContext:
    """Container for retrieval results passed to prompt builder"""
    vector_results: List[Dict[str, Any]]
    graph_results: Optional[List[Dict[str, Any]]] = None
    precedents: Optional[List[Dict[str, Any]]] = None
    memory: Optional[List[Dict[str, Any]]] = None  # Episodic memory (past sessions)
    conversation_history: Optional[List[Dict[str, Any]]] = None  # Current session turns
    query: str = ""
    

class PromptBuilder:
    """
    Builds prompts for LLM generation.

    Combines:
    - Executive profile (personality, values, communication style)
    - Retrieval context (vector search, graph, precedents, memory)
    - Query-specific instructions
    - Path-specific formatting
    """

    def __init__(self, profile_id: str, path: str = "standard"):
        """
        Initialize prompt builder.

        Args:
            profile_id: Executive profile ID (e.g., 'akiko_tanaka')
            path: Processing path (fast/standard/agentic)
        """
        self.profile_id = profile_id
        self.path = path

        # Source mapping for citation validation
        self.source_mapping = {}  # {source_id: {title, doc_id, content}}

        # Load profile
        profile_manager = get_profile_manager()
        self.profile = profile_manager.get_profile(profile_id)

        if not self.profile:
            raise ValueError(f"Profile not found: {profile_id}")

        logger.debug(f"Initialized PromptBuilder for {profile_id}, path={path}")
    
    def build_system_prompt(self, language: str = "en") -> str:
        """
        Build system prompt with executive personality.

        REFACTORED (2025-01-15): Now uses centralized rules from rules.py
        - Uses build_system_prompt_from_rules() instead of deprecated ProfileManager.generate_system_prompt()
        - Word limits, anti-AI rules, and identity oath come from single source of truth
        - Path-specific citation instructions added here (specific to retrieval context)

        Args:
            language: Response language preference (en or ja)

        Returns:
            System prompt string
        """
        # Import from centralized rules - SINGLE SOURCE OF TRUTH
        from conversation_engine.prompt.rules import build_system_prompt_from_rules

        # Build base system prompt using centralized rules
        # This replaces the deprecated ProfileManager.generate_system_prompt()
        system_prompt = build_system_prompt_from_rules(
            profile_id=self.profile_id,
            path=self.path,
            language=language,
            include_examples=True,
        )

        # Add citation instructions (specific to retrieval/RAG context)
        citation_instructions = """
CITATION REQUIREMENTS (RETRIEVAL CONTEXT):

1. CITE sources using [Source: exact_name] format ONLY
   - Use EXACT source names from AVAILABLE SOURCES section
   - Do NOT use number format [1], [2], [3]
   - Every factual claim MUST have a citation

2. PRECEDENT CITATIONS:
   - Reference YOUR past decisions: DC_XXX_### format
   - "In DC_YUK_005, I decided to..."
   - Connect precedents to current query

3. INFORMATION BOUNDARIES:
   - FACTUAL CLAIMS: Use ONLY provided context with citations
   - OPINIONS/VALUES: Draw from your persona - no citation needed
   - If no data: "I don't have exact figures, but based on my experience..."

4. QUERY INTENT RECOGNITION:
   - "what did you implement AFTER" → Focus on OUTCOMES, RESULTS sections
   - "what measures/steps" → List SPECIFIC ACTIONS
   - "investment/budget" → Extract EXACT ¥ amounts
"""

        return f"{system_prompt}\n\n{citation_instructions}"

    def build_context_prompt(self, context: RetrievalContext) -> str:
        """
        Build context section from retrieval results.
        
        Args:
            context: Retrieval context with search results
            
        Returns:
            Formatted context string
        """
        sections = []
        
        # Vector search results (always included)
        if context.vector_results:
            sections.append(self._format_vector_results(context.vector_results))
        
        # Graph context (standard/agentic paths)
        if context.graph_results and self.path in ["standard", "agentic"]:
            sections.append(self._format_graph_results(context.graph_results))
        
        # Precedents (standard/agentic paths)
        if context.precedents and self.path in ["standard", "agentic"]:
            sections.append(self._format_precedents(context.precedents))
        
        # Current conversation history (multi-turn context) - HIGHEST PRIORITY
        if context.conversation_history:
            sections.insert(0, self._format_conversation_history(context.conversation_history))

        # Episodic memory from past sessions (all paths)
        if context.memory:
            sections.append(self._format_memory(context.memory))

        # Join sections
        context_prompt = "\n\n".join(sections)
        
        return f"""
AVAILABLE CONTEXT:

{context_prompt}

Based on the above context, please answer the following query:
"{context.query}"
"""
    
    def _extract_document_title(self, result: Dict[str, Any], fallback_index: int = 1) -> str:
        """
        Extract meaningful document title from result.

        Tries multiple strategies:
        1. Use title/name if meaningful
        2. Extract from document_id if title is generic
        3. Fall back to indexed name

        Args:
            result: Document result dict
            fallback_index: Index for fallback naming

        Returns:
            Human-readable document title
        """
        # Try direct title or name
        title = result.get('title', '') or result.get('name', '')

        # Check if title is generic or missing
        generic_titles = ['Document', 'Untitled', '', None, 'doc', 'document']
        if not title or title.lower() in [t.lower() if t else '' for t in generic_titles]:
            # Try extracting from document_id
            doc_id = result.get('document_id', '') or result.get('id', '')
            if doc_id:
                # Extract meaningful part from document_id
                # e.g., "doc_2024-10-20_marketing_performance_q3" → "Marketing Performance Q3"
                # e.g., "chunk_doc_security_incident_response_2024_0" → "Security Incident Response 2024"
                parts = doc_id.replace('-', '_').split('_')

                # Filter out common prefixes, dates, and chunk indices
                meaningful_parts = []
                for p in parts:
                    p_lower = p.lower()
                    # Skip common prefixes
                    if p_lower in ['doc', 'chunk', 'document', 'file']:
                        continue
                    # Skip date patterns (2024, 2023, etc. or month-day patterns)
                    if p_lower.startswith('20') and len(p) == 4:
                        continue
                    if p_lower.isdigit() and len(p) <= 2:
                        continue
                    # Skip chunk indices at the end
                    if p.isdigit():
                        continue
                    meaningful_parts.append(p)

                if meaningful_parts:
                    # Capitalize each word nicely
                    title = ' '.join(word.capitalize() for word in meaningful_parts)

        # Final fallback
        if not title or title.lower() in [t.lower() if t else '' for t in generic_titles]:
            title = f"Document_{fallback_index}"

        return title

    def _format_vector_results(self, results: List[Dict[str, Any]]) -> str:
        """
        Format vector search results with actual source names for citation validation.

        Each document shows its actual name that the LLM must use for citations.
        This prevents hallucinated citations while being more readable.
        """
        # Limit results based on path (increased for more context)
        max_results = {"fast": 8, "standard": 15, "agentic": 20}.get(self.path, 15)
        limited_results = results[:max_results]

        # Clear previous source mapping and build new one
        self.source_mapping = {}

        formatted = ["AVAILABLE SOURCES:"]
        formatted.append("(You MUST cite these exact source names)\n")

        for i, result in enumerate(limited_results, 1):
            doc_id = result.get('id', f'doc_{i}')
            title = self._extract_document_title(result, fallback_index=i)
            content = result.get('content') or result.get('text') or result.get('text_content') or ''
            score = result.get('score', 0.0)
            # Handle None content gracefully
            if not content:
                content = f"[No content available for document {doc_id}]"
            # Store source mapping for validation (by exact title)
            self.source_mapping[title] = {
                'doc_id': doc_id,
                'content': content,
                'score': score,
                'index': i
            }

            # Format with actual source name prominently displayed
            # CRITICAL: Increased to 5000 chars to capture full Outcome sections in long docs
            formatted.append(f"""Source: {title} (Relevance: {score:.2f})
    Content: {content[:5000]}{"..." if len(content) > 5000 else ""}
""")

        # Add citation reminder with extracted source names
        formatted.append("\nCITATION REQUIREMENT:")
        formatted.append(f"- You have access to {len(limited_results)} sources above")
        # Use the extracted titles from source_mapping (already processed)
        source_names = list(self.source_mapping.keys())
        formatted.append("- Available sources: " + ", ".join([f'"{name}"' for name in source_names]))
        formatted.append("- Cite format: [Source: exact_name_here]")
        # Use a real example from our extracted titles
        example_source = source_names[0] if source_names else "Marketing_Performance_Q3"
        formatted.append(f"- Example: [Source: {example_source}]")
        formatted.append("- Do NOT cite sources not in the list above")
        formatted.append("- Do NOT invent or modify source names")
        formatted.append("- Use the EXACT source name as shown")

        return "\n".join(formatted)

    def get_source_mapping(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the source name to document mapping for citation validation.

        Returns:
            Dict mapping source names (titles) to document metadata
        """
        return self.source_mapping
    
    def _format_graph_results(self, results: List[Dict[str, Any]]) -> str:
        """Format graph context results"""
        if not results:
            return ""
        
        formatted = ["RELATED CONTEXT (Knowledge Graph):"]
        
        for i, result in enumerate(results[:5], 1):  # Limit to top 5
            relationship = result.get('relationship', 'relates to')
            entity = result.get('entity', 'unknown')
            context = result.get('context', '')
            
            formatted.append(f"""
{i}. {relationship.upper()}: {entity}
   {context[:300]}{"..." if len(context) > 300 else ""}
""")
        
        return "\n".join(formatted)
    
    def _format_precedents(self, precedents: List[Dict[str, Any]]) -> str:
        """Format historical precedents"""
        if not precedents:
            return ""
        
        formatted = ["HISTORICAL PRECEDENTS:"]
        
        for i, prec in enumerate(precedents[:3], 1):  # Limit to top 3
            query = prec.get('query', '')
            response = prec.get('response', '')
            date = prec.get('timestamp', 'unknown date')
            
            formatted.append(f"""
Precedent {i} (from {date}):
Query: {query}
Response: {response[:400]}{"..." if len(response) > 400 else ""}
""")
        
        return "\n".join(formatted)
    
    def _format_memory(self, memory: List[Dict[str, Any]]) -> str:
        """Format episodic memory (past sessions)"""
        if not memory:
            return ""

        formatted = ["RELEVANT PAST INTERACTIONS (from previous sessions):"]

        for i, mem in enumerate(memory[-3:], 1):  # Last 3 interactions
            query = mem.get('query', '')
            response_summary = mem.get('response', '')[:200]

            formatted.append(f"""
{i}. Previous query: {query}
   Response: {response_summary}...
""")

        return "\n".join(formatted)

    def _format_conversation_history(self, conversation_history: List[Dict[str, Any]]) -> str:
        """
        Format current session conversation history for multi-turn context.

        Args:
            conversation_history: List of {role: "user"|"assistant", content: str}

        Returns:
            Formatted conversation history string
        """
        if not conversation_history:
            return ""

        # Take last 5 turns (10 messages) to keep context manageable
        recent_history = conversation_history[-10:]

        if not recent_history:
            return ""

        formatted = ["CURRENT CONVERSATION (this session):"]
        formatted.append("The following is your conversation with the user in this session. Use this context to understand follow-up questions and maintain consistency.\n")

        for msg in recent_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            # Truncate long messages
            if len(content) > 300:
                content = content[:300] + "..."

            if role == 'user':
                formatted.append(f"User: {content}")
            else:
                formatted.append(f"You (Executive): {content}")

        formatted.append("")  # Empty line at end

        return "\n".join(formatted)
    
    def build_user_prompt(self, query: str) -> str:
        """
        Build the user query prompt.
        
        Args:
            query: User's question
            
        Returns:
            Formatted user prompt
        """
        # Simple wrapper for now - could add query enhancement later
        return query
    
    def build_full_prompt(self, query: str, context: RetrievalContext, language: str = "en") -> tuple:
        """
        Build complete prompt with system + context + user message.

        Args:
            query: User's question
            context: Retrieval context
            language: Response language preference (en or ja)

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Build system prompt with language preference
        system_prompt = self.build_system_prompt(language=language)

        # Build user prompt with context
        context.query = query
        context_section = self.build_context_prompt(context)

        # Get path-specific length limit from centralized rules.py
        max_words = get_word_limit(self.path)

        user_prompt = f"""{context_section}

Please provide your response following the guidelines above.

CRITICAL REMINDER: Your response MUST NOT exceed {max_words} words. Count carefully. Executives are busy - be concise and direct."""

        return system_prompt, user_prompt
