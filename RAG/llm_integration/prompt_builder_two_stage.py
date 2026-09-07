"""
TWO-STAGE Prompt Builder for LLM Integration

Implements intelligent compression between retrieval and generation:
Stage 1.5A: Smart content extraction (MMR-based compression) - RECOMMENDED
Stage 1.5B: Groq API fact extraction (disabled by default)
Stage 2: Compact prompt for API generation

RECOMMENDED CONFIGURATION (77% token reduction):
- enable_compression=True, enable_fact_extraction=False
- Uses Stage 1.5A only (smart compression with MMR)
- Achieves 77% token reduction reliably
- Fast, no timeouts, maintains quality

Test Results (7 documents, 44,394 chars):
- Original: 12,098 tokens → 16 requests/day
- Stage 1.5A only: 2,835 tokens → 70 requests/day (4.4x improvement)
- Processing time: ~4 seconds
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import json
import sys
import os

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from profile_management.profile_manager import get_profile_manager
from hybrid_retrieval.smart_content_extractor import SmartContentExtractor
from llm_integration.groq_fact_extractor import GroqFactExtractor
# Import from centralized rules - SINGLE SOURCE OF TRUTH
from conversation_engine.prompt.rules import get_word_limit, get_word_limit_instruction, build_system_prompt_from_rules

logger = logging.getLogger(__name__)


@dataclass
class RetrievalContext:
    """Container for retrieval results passed to prompt builder"""
    vector_results: List[Dict[str, Any]]
    graph_results: Optional[List[Dict[str, Any]]] = None
    precedents: Optional[List[Dict[str, Any]]] = None
    memory: Optional[List[Dict[str, Any]]] = None
    query: str = ""


class TwoStagePromptBuilder:
    """
    TWO-STAGE Prompt Builder with intelligent compression.

    Combines:
    - Executive profile (personality, values, communication style)
    - STAGE 1.5: Smart content extraction
      - Section-aware content selection (regex + MMR)
      - Groq API fact extraction (openai/gpt-oss-120b)
    - STAGE 2: Compact fact-based prompt (API)
    - Path-specific formatting
    """

    def __init__(
        self,
        profile_id: str,
        path: str = "standard",
        enable_compression: bool = True,
        enable_fact_extraction: bool = False,
        groq_model: str = "openai/gpt-oss-120b",
        groq_api_key: Optional[str] = None
    ):
        """
        Initialize two-stage prompt builder.

        Args:
            profile_id: Executive profile ID (e.g., 'exec_003_test')
            path: Processing path (fast/standard/agentic)
            enable_compression: Enable Stage 1.5A compression (default: True, RECOMMENDED)
            enable_fact_extraction: Enable Stage 1.5B fact extraction (default: False, uses Groq API)
            groq_model: Groq model name (default: openai/gpt-oss-120b)
            groq_api_key: Optional Groq API key (defaults to GROQ_FACT_EXTRACTION_API_KEY from env)

        RECOMMENDED: enable_compression=True, enable_fact_extraction=False
        This gives 77% token reduction without quality/timeout issues.
        """
        self.profile_id = profile_id
        self.path = path
        self.enable_compression = enable_compression
        self.enable_fact_extraction = enable_fact_extraction

        # Source mapping for citation validation
        self.source_mapping = {}  # {source_id: {title, doc_id, content}}

        # Load profile
        profile_manager = get_profile_manager()
        self.profile = profile_manager.get_profile(profile_id)

        if not self.profile:
            raise ValueError(f"Profile not found: {profile_id}")

        # Initialize content extractor (Stage 1.5A) - RECOMMENDED
        if self.enable_compression:
            try:
                self.content_extractor = SmartContentExtractor(model_name='BAAI/bge-m3')
                logger.info("[OK] TwoStagePromptBuilder: Stage 1.5A (compression) enabled")
            except Exception as e:
                logger.warning(f"[WARN] Could not initialize content extractor: {e}. Falling back.")
                self.enable_compression = False
                self.content_extractor = None
        else:
            self.content_extractor = None
            logger.info("[INFO] TwoStagePromptBuilder: Stage 1.5A disabled (using original prompts)")

        # Initialize fact extractor (Stage 1.5B) - Uses Groq API, disabled by default
        if self.enable_fact_extraction:
            try:
                self.fact_extractor = GroqFactExtractor(
                    api_key=groq_api_key,
                    model=groq_model
                )
                logger.info("[OK] TwoStagePromptBuilder: Stage 1.5B (Groq fact extraction) enabled")
                logger.info(f"[INFO] Using Groq API with model: {groq_model}")
            except Exception as e:
                logger.warning(f"[WARN] Could not initialize Groq fact extractor: {e}")
                self.enable_fact_extraction = False
                self.fact_extractor = None
        else:
            self.fact_extractor = None
            logger.info("[INFO] TwoStagePromptBuilder: Stage 1.5B disabled (using compressed content only)")

        logger.debug(f"Initialized TwoStagePromptBuilder for {profile_id}, path={path}")

    async def build_prompts(self, context: RetrievalContext) -> Tuple[str, str]:
        """
        Build system and user prompts with optional compression and/or fact extraction.

        Modes:
        1. Both disabled: Original prompts (5000 chars/doc)
        2. Compression only (RECOMMENDED): 77% token reduction, fast, reliable
        3. Compression + Fact extraction (EXPERIMENTAL): 92% reduction, slow, may timeout

        Args:
            context: Retrieval context with search results

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # System prompt (unchanged from original)
        system_prompt = self.build_system_prompt()

        # User prompt with selected processing mode
        if self.enable_compression:
            user_prompt = await self._build_user_prompt_two_stage(context)
        else:
            # Fallback to original method (no compression)
            user_prompt = self._build_user_prompt_original(context)

        return system_prompt, user_prompt

    def build_full_prompt(self, query: str, context: RetrievalContext, language: str = "en") -> Tuple[str, str]:
        """
        Synchronous wrapper for build_prompts - for backward compatibility.

        This method allows existing synchronous handlers to use TwoStagePromptBuilder
        without refactoring to async.

        Args:
            query: User's question
            context: RetrievalContext with vector_results, memory, etc.
            language: Language code (default: "en", currently ignored)

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        import asyncio

        # Set query in context
        context.query = query

        # Run async build_prompts in sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an event loop, create a new one
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(self.build_prompts(context))
            else:
                return asyncio.run(self.build_prompts(context))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.build_prompts(context))

    def build_system_prompt(self, language: str = "en") -> str:
        """
        Build system prompt with executive personality.

        REFACTORED (2025-01-15): Now uses centralized rules from rules.py
        - Uses build_system_prompt_from_rules() instead of deprecated ProfileManager.generate_system_prompt()
        - Word limits, anti-AI rules, and identity oath come from single source of truth

        Args:
            language: Response language preference (en or ja)

        Returns:
            System prompt string
        """
        # Build base system prompt using centralized rules
        # This replaces the deprecated ProfileManager.generate_system_prompt()
        system_prompt = build_system_prompt_from_rules(
            profile_id=self.profile_id,
            path=self.path,
            language=language,
            include_examples=True,
        )

        # Add two-stage-specific citation instructions (unique to retrieval context)
        citation_instructions = """
CITATION REQUIREMENTS (TWO-STAGE CONTEXT):

1. CITE sources using [Source: exact_name] format ONLY
   - Use EXACT source names from AVAILABLE SOURCES section
   - Every factual claim MUST have a citation

2. PRECEDENT CITATIONS:
   - Reference YOUR past decisions: DC_XXX_### format
   - "In DC_YUK_005, I decided to..."

3. STRUCTURE (EXECUTIVES DON'T USE HEADERS):
   - NO section headers, NO numbered sections
   - Use flowing conversational paragraphs
   - Weave topics naturally: "On the security side..." "The key thing is..."
"""

        return f"{system_prompt}\n\n{citation_instructions}"

    def _get_path_instructions(self) -> str:
        """
        Get path-specific instructions using centralized word limits.

        REFACTORED (2025-01-15): Now uses get_word_limit_instruction() from rules.py
        """
        word_limit = get_word_limit_instruction(self.path)

        instructions = {
            "fast": f"""
RESPONSE MODE: Fast Direct Answer
- Provide a quick, direct answer to the question
- Use only the most relevant sources (top 1-3)
- {word_limit}
- Executives value brevity - get to the point
""",
            "standard": f"""
RESPONSE MODE: Standard Conversational Answer
- Provide a thorough answer in YOUR natural voice
- Draw from multiple sources but write conversationally
- {word_limit}
- Write like you're talking to a colleague
""",
            "agentic": f"""
RESPONSE MODE: Deep Conversational Analysis
- Provide comprehensive analysis in YOUR natural voice
- Consider all available context including graph relationships
- Include precedents naturally in narrative
- {word_limit}
- Write conversationally, not like a report
"""
        }

        return instructions.get(self.path, instructions["standard"])

    async def _build_user_prompt_two_stage(self, context: RetrievalContext) -> str:
        """
        Build user prompt with TWO-STAGE ARCHITECTURE.

        Stage 1.5: Smart Extraction
        - Compress 5000 chars/doc → 1200 chars/doc
        - Extract facts via Groq API → JSON
        - Token reduction: ~8,750 → ~700 tokens (92% reduction)

        Stage 2: Fact-Based Prompt (API)
        - Send query + extracted facts + profile
        - Total tokens: ~1,500 (vs ~9,600 original)

        Args:
            context: Retrieval context

        Returns:
            Formatted user prompt with extracted facts
        """
        query = context.query

        # ========== STAGE 1.5A: CONTENT COMPRESSION ==========
        logger.info(f"[STAGE 1.5A] Compressing content from {len(context.vector_results)} documents...")

        # Determine document limits based on path
        max_docs = {"fast": 5, "standard": 6, "agentic": 7}.get(self.path, 6)
        max_chars = {"fast": 1000, "standard": 1200, "agentic": 1500}.get(self.path, 1200)

        # Apply smart content extraction
        compressed_docs = self.content_extractor.extract_relevant_content(
            query=query,
            documents=context.vector_results,
            max_chars_per_doc=max_chars,
            max_docs=max_docs
        )

        # Log compression statistics
        original_total = sum(d.get('original_length', len(d['content'])) for d in compressed_docs)
        compressed_total = sum(len(d['content']) for d in compressed_docs)
        compression_ratio = original_total / max(compressed_total, 1)

        logger.info(
            f"[OK] Stage 1.5A complete: {original_total} -> {compressed_total} chars "
            f"({compression_ratio:.1f}x compression)"
        )

        # ========== STAGE 1.5B: FACT EXTRACTION (OPTIONAL) ==========
        if self.enable_fact_extraction and self.fact_extractor:
            logger.info(f"[STAGE 1.5B] Extracting facts via Groq API...")

            try:
                extracted_facts = await self.fact_extractor.extract_facts(
                    query=query,
                    compressed_docs=compressed_docs,
                    max_output_tokens=600,
                    batch_size=2  # Process 2 docs at a time to avoid timeouts
                )

                facts_json = json.dumps(extracted_facts, indent=2, ensure_ascii=False)
                facts_tokens = len(facts_json) // 4  # Rough token estimate

                logger.info(
                    f"[OK] Stage 1.5B complete: Extracted {len(extracted_facts.get('measures', []))} measures, "
                    f"{len(extracted_facts.get('actions', []))} actions (~{facts_tokens} tokens)"
                )

            except Exception as e:
                logger.error(f"[ERROR] Stage 1.5B failed: {e}. Falling back to compressed content.")
                # Fallback: use compressed content instead of extracted facts
                return self._build_user_prompt_from_compressed_docs(query, compressed_docs, context)
        else:
            # Stage 1.5B disabled - use compressed content directly (RECOMMENDED mode)
            logger.info(f"[STAGE 1.5B] Skipped (disabled) - using compressed content directly")
            return self._build_user_prompt_from_compressed_docs(query, compressed_docs, context)

        # ========== STAGE 2: FACT-BASED PROMPT ==========
        logger.info(f"[STAGE 2] Building compact fact-based prompt...")

        # Build source list for citations
        source_list = self._build_source_list(compressed_docs)

        # Get length limit from single source of truth
        max_words = get_word_limit(self.path)

        # Format facts as clean JSON
        facts_json_formatted = json.dumps(extracted_facts, indent=2, ensure_ascii=False)

        user_prompt = f"""

AVAILABLE SOURCES:
(You MUST cite these exact source names for all factual claims)

{source_list}

───────────────────────────────────────────────────────────────

EXTRACTED FACTS FROM DOCUMENTS:

The following facts were extracted from the above sources. Use these facts to construct your response.
All numbers, dates, and metrics are preserved exactly as they appear in the source documents.

```json
{facts_json_formatted}
```

───────────────────────────────────────────────────────────────

QUERY:
"{query}"

───────────────────────────────────────────────────────────────

INSTRUCTIONS:
Speak naturally. Include specific metrics with citations. You ARE the executive.

★★★ SPEAK NATURALLY ★★★
✓ NATURAL: "Singapore? I think it can wait. We need to get the core product right first."
✗ ROBOTIC: "We should focus on core, evaluate markets, and then consider expansion."
~{max_words} words. Warm and direct.

Response:"""

        # Calculate token savings
        old_estimate = original_total // 4  # Old system token estimate
        new_estimate = len(user_prompt) // 4  # New system token estimate
        savings_pct = 100 - int(new_estimate / old_estimate * 100) if old_estimate > 0 else 0

        logger.info(
            f"[OK] Stage 2 complete: Token reduction {old_estimate} -> {new_estimate} "
            f"({savings_pct}% savings)"
        )

        return user_prompt

    def _build_source_list(self, documents: List[Dict]) -> str:
        """
        Build a list of source names for citation.

        Args:
            documents: List of documents

        Returns:
            Formatted source list
        """
        sources = []
        self.source_mapping = {}

        for i, doc in enumerate(documents, 1):
            doc_id = doc.get('id', f'doc_{i}')
            title = doc.get('title', 'Untitled')
            score = doc.get('score', 0.0)

            # Store for validation
            self.source_mapping[title] = {
                'doc_id': doc_id,
                'content': doc.get('content', ''),
                'score': score,
                'index': i
            }

            sources.append(f"{i}. {title} (Relevance: {score:.2f})")

        return "\n".join(sources)

    def _build_user_prompt_from_compressed_docs(
        self,
        query: str,
        compressed_docs: List[Dict],
        context: Optional[RetrievalContext] = None
    ) -> str:
        """
        Build prompt from compressed docs (Stage 1.5A only).

        This is the RECOMMENDED mode:
        - 77% token reduction via smart compression
        - Fast processing (~4 seconds)
        - No quality loss
        - No timeouts

        Args:
            query: User query
            compressed_docs: List of compressed documents
            context: Optional RetrievalContext with graph_results and precedents

        Returns:
            Formatted user prompt
        """
        logger.info("[STAGE 2] Building prompt from compressed content (77% token reduction)")

        formatted_docs = []
        self.source_mapping = {}

        for i, doc in enumerate(compressed_docs, 1):
            doc_id = doc.get('id', f'doc_{i}')
            title = doc.get('title', 'Untitled')
            content = doc.get('content', '')
            score = doc.get('score', 0.0)

            self.source_mapping[title] = {
                'doc_id': doc_id,
                'content': content,
                'score': score,
                'index': i
            }

            formatted_docs.append(f"""
Source: {title} (Relevance: {score:.2f})
Content: {content}
""")

        docs_text = "\n\n".join(formatted_docs)

        # Build graph context section if available (minimal to save tokens)
        graph_section = ""
        try:
            if (context and
                context.graph_results and
                isinstance(context.graph_results, list) and
                len(context.graph_results) > 0):

                graph_items = []
                for gr in context.graph_results[:3]:  # Limit to top 3 to save tokens
                    if isinstance(gr, dict):
                        # Format based on graph result structure
                        relationship = gr.get('relationship', gr.get('type', ''))
                        source_node = gr.get('source', gr.get('from', ''))
                        target_node = gr.get('target', gr.get('to', ''))

                        if relationship and source_node and target_node:
                            graph_items.append(f"- {source_node} → {relationship} → {target_node}")

                if graph_items:
                    graph_section = f"""

RELATIONSHIPS:
{chr(10).join(graph_items)}
"""
                    logger.info(f"[STAGE 2] Added {len(graph_items)} graph relationships")
        except Exception as e:
            logger.warning(f"[STAGE 2] Could not format graph_results: {e}")
            graph_section = ""

        # NOTE: Precedents disabled for standard path to save tokens (8000 TPM limit)
        # Precedents are already in the vector results if relevant
        # Only agentic path should use explicit precedents section

        # Get word limit for reminder
        word_limit = get_word_limit(self.path)

        user_prompt = f"""
AVAILABLE SOURCES:
{docs_text}
{graph_section}
QUESTION:
"{query}"

★★★ SPEAK NATURALLY ★★★
✓ NATURAL: "Singapore? I think it can wait. We need to get the core product right first."
✗ ROBOTIC: "We should focus on core, evaluate markets, and then consider expansion."
~{word_limit} words. Warm and direct.
"""
        # DEBUG: Log that we're using the updated prompt builder
        logger.info(f"[DEBUG] TwoStagePromptBuilder user prompt includes SPEAK NATURALLY marker")
        return user_prompt

    def _build_user_prompt_original(self, context: RetrievalContext) -> str:
        """
        Original prompt building method (fallback if extraction disabled).

        Args:
            context: Retrieval context

        Returns:
            Formatted user prompt
        """
        logger.info("Using original prompt building method (no extraction)")

        # Format results with full 5000 char content (original behavior)
        formatted_docs = []
        self.source_mapping = {}

        max_results = {"fast": 8, "standard": 15, "agentic": 20}.get(self.path, 15)

        for i, result in enumerate(context.vector_results[:max_results], 1):
            doc_id = result.get('id', f'doc_{i}')
            title = result.get('title', 'Untitled')
            content = result.get('content', result.get('text', ''))
            score = result.get('score', 0.0)

            self.source_mapping[title] = {
                'doc_id': doc_id,
                'content': content,
                'score': score,
                'index': i
            }

            # Original 5000 char limit
            formatted_docs.append(f"""
Source: {title} (Relevance: {score:.2f})
Content: {content[:5000]}{"..." if len(content) > 5000 else ""}
""")

        docs_text = "\n\n".join(formatted_docs)

        # Get word limit for reminder
        word_limit = get_word_limit(self.path)

        return f"""
AVAILABLE SOURCES:
{docs_text}

QUESTION:
"{context.query}"

★★★ SPEAK NATURALLY ★★★
✓ NATURAL: "Singapore? I think it can wait. We need to get the core product right first."
✗ ROBOTIC: "We should focus on core, evaluate markets, and then consider expansion."
~{word_limit} words. Warm and direct.
"""
