"""
DualStreamPromptBuilder - Orchestrate fact, persona, and voiceprint streams

This module implements the dual-stream architecture that combines:
1. Fact Stream: Factual information from retrieval
2. Persona Stream: Persona-rich snippets from PersonaExtractor
3. Voiceprint Stream: Executive's communication style markers

The streams are executed in parallel and merged intelligently based on
query type classification for optimal token allocation.

Usage:
    builder = DualStreamPromptBuilder(
        voiceprint_cache=cache,
        hybrid_retrieval_manager=manager,
        query_classifier=classifier
    )

    system_prompt, user_prompt = await builder.build(
        query="What is Yuki's philosophy on technical debt?",
        executive_id="exec_003_test",
        retrieval_results=results
    )
"""

import asyncio
import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

from profile_management.voiceprint_cache import VoiceprintCache, Voiceprint
from hybrid_retrieval.persona_extractor import PersonaExtractor, PersonaSnippet
from hybrid_retrieval.query_type_classifier import QueryTypeClassifier
# Import from centralized rules - SINGLE SOURCE OF TRUTH
from conversation_engine.prompt.rules import get_word_limit_instruction

logger = logging.getLogger(__name__)


@dataclass
class TokenAllocation:
    """Token budget allocation across streams"""
    voiceprint: int
    facts: int
    persona: int

    @property
    def total(self) -> int:
        return self.voiceprint + self.facts + self.persona


class DualStreamPromptBuilder:
    """
    Dual-stream prompt builder orchestrating fact, persona, and voiceprint streams
    """

    # Token allocation strategies based on query type
    ALLOCATIONS = {
        "persona_heavy": TokenAllocation(voiceprint=350, facts=150, persona=400),  # 900 total
        "fact_heavy": TokenAllocation(voiceprint=350, facts=350, persona=150),     # 850 total
        "mixed": TokenAllocation(voiceprint=350, facts=250, persona=250)           # 850 total
    }

    # Query type to allocation strategy mapping
    QUERY_TYPE_TO_STRATEGY = {
        "factual_lookup": "fact_heavy",
        "relationship": "fact_heavy",
        "decision": "persona_heavy",
        "procedural": "mixed",
        "comparison": "mixed",
        "conversational_context": "persona_heavy"
    }

    def __init__(
        self,
        profile_id: str,
        voiceprint_cache: Optional[VoiceprintCache] = None,
        query_classifier: Optional[QueryTypeClassifier] = None,
        path: str = "standard",  # NEW: Track path for constraints
        **kwargs  # Accept extra args for compatibility
    ):
        """
        Initialize DualStreamPromptBuilder

        Args:
            profile_id: Executive profile ID (for compatibility with TwoStagePromptBuilder)
            voiceprint_cache: Cache for loading executive voiceprints (optional, will create if None)
            query_classifier: Query type classifier for token allocation (optional, will create if None)
            path: Query path (fast/standard/agentic) for applying constraints
            **kwargs: Additional arguments for compatibility
        """
        self.profile_id = profile_id
        self.path = path  # NEW: Store path for constraint selection

        # Initialize components if not provided
        if voiceprint_cache is None:
            from profile_management.voiceprint_cache import VoiceprintCache as VPC
            voiceprint_cache = VPC()

        if query_classifier is None:
            from hybrid_retrieval.query_type_classifier import QueryTypeClassifier as QTC
            query_classifier = QTC()

        self.voiceprint_cache = voiceprint_cache
        self.persona_extractor = PersonaExtractor(voiceprint_cache)
        self.query_classifier = query_classifier

        # Initialize SmartContentExtractor for pre-compression (Stage 1.5A)
        try:
            from hybrid_retrieval.smart_content_extractor import SmartContentExtractor
            self.content_extractor = SmartContentExtractor(model_name='BAAI/bge-m3')
            logger.info(f"[DualStreamPromptBuilder] SmartContentExtractor initialized (Stage 1.5A)")
        except Exception as e:
            logger.warning(f"[DualStreamPromptBuilder] Could not initialize SmartContentExtractor: {e}")
            self.content_extractor = None

        # Initialize LocalExtractorClient for JSON fact extraction (Stage 1.5B)
        # Using Local LLM because:
        # - Map-Reduce processes ONE document at a time (~500 tokens each)
        # - No API rate limits or costs
        # - Sequential processing avoids overwhelming local LLM
        # - Expected: ~18s per document (vs 180s timeout with batched approach)
        try:
            from llm_integration.local_extractor_client import LocalExtractorClient
            self.fact_extractor = LocalExtractorClient(
                timeout=60  # 60s timeout per document (was 180s for batches)
                # Connects to LM Studio at http://localhost:1234
            )
            logger.info(f"[DualStreamPromptBuilder] LocalExtractorClient initialized (Stage 1.5B)")
        except Exception as e:
            logger.warning(f"[DualStreamPromptBuilder] Could not initialize LocalExtractorClient: {e}")
            self.fact_extractor = None

        logger.info(f"[DualStreamPromptBuilder] Initialized for {profile_id} (path={path})")

    def build_full_prompt(
        self,
        query: str,
        context: 'RetrievalContext',  # Forward reference for compatibility
        language: str = "en"  # For compatibility with path handlers
    ) -> Tuple[str, str]:
        """
        Sync wrapper for build() - compatible with existing path handlers

        Args:
            query: User's question
            context: RetrievalContext object containing vector_results
            language: Language code (default: "en", currently ignored)

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Extract data from context
        retrieval_results = context.vector_results if hasattr(context, 'vector_results') else []

        # Run async build in sync context
        import asyncio
        import nest_asyncio

        # Allow nested event loops (for FastAPI compatibility)
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            pass  # nest_asyncio not available, will use fallback

        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running (e.g., in FastAPI), create task and wait
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.build(
                            query=query,
                            executive_id=self.profile_id,
                            retrieval_results=retrieval_results
                        )
                    )
                    return future.result()
            else:
                # Loop exists but not running, use it
                return loop.run_until_complete(
                    self.build(
                        query=query,
                        executive_id=self.profile_id,
                        retrieval_results=retrieval_results
                    )
                )
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(
                self.build(
                    query=query,
                    executive_id=self.profile_id,
                    retrieval_results=retrieval_results
                )
            )

    async def build(
        self,
        query: str,
        executive_id: str,
        retrieval_results: List[Dict],
        executive_name: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Build system and user prompts using dual-stream architecture

        Args:
            query: User's question
            executive_id: Executive identifier
            retrieval_results: Results from hybrid retrieval
            executive_name: Executive's name (optional, will load from voiceprint if not provided)

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        start_time = asyncio.get_event_loop().time()

        # Determine allocation strategy based on query type
        allocation = self._determine_allocation(query)

        logger.info(f"[DualStreamPromptBuilder] Query: {query[:50]}...")
        logger.info(f"[DualStreamPromptBuilder] Allocation strategy: {allocation}")

        # Execute 3 streams in parallel
        voiceprint_task = asyncio.create_task(
            self._load_voiceprint_stream(executive_id)
        )
        facts_task = asyncio.create_task(
            self._build_facts_stream(
                retrieval_results=retrieval_results,
                max_tokens=allocation.facts,
                query=query  # Pass query for fact extraction context
            )
        )
        persona_task = asyncio.create_task(
            self._build_persona_stream(
                retrieval_results=retrieval_results,
                executive_id=executive_id,
                max_tokens=allocation.persona
            )
        )

        # Await all streams
        voiceprint, facts_json, persona_examples = await asyncio.gather(
            voiceprint_task,
            facts_task,
            persona_task
        )

        # Build prompts
        if not executive_name:
            executive_name = voiceprint.name if voiceprint else "Executive"

        system_prompt = self._build_system_prompt(voiceprint, executive_name)
        user_prompt = self._build_user_prompt(
            query=query,
            executive_name=executive_name,
            voiceprint_pack=self._format_voiceprint_pack(voiceprint),
            facts_json=facts_json,
            persona_examples=persona_examples
        )

        # Log performance
        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"[DualStreamPromptBuilder] Built prompts in {elapsed:.2f}s")
        logger.info(f"[DualStreamPromptBuilder] System prompt: {len(system_prompt)} chars")
        logger.info(f"[DualStreamPromptBuilder] User prompt: {len(user_prompt)} chars")

        return system_prompt, user_prompt

    def _determine_allocation(self, query: str) -> TokenAllocation:
        """
        Determine token allocation strategy based on query type

        Args:
            query: User's question

        Returns:
            TokenAllocation for this query
        """
        if not self.query_classifier:
            # Default to mixed allocation if no classifier
            return self.ALLOCATIONS["mixed"]

        # Classify query
        classification = self.query_classifier.classify(query)

        # Map to allocation strategy
        strategy_key = self.QUERY_TYPE_TO_STRATEGY.get(
            classification.query_type,
            "mixed"
        )

        allocation = self.ALLOCATIONS[strategy_key]

        logger.info(f"[DualStreamPromptBuilder] Query type: {classification.query_type} ({classification.confidence:.2f})")
        logger.info(f"[DualStreamPromptBuilder] Strategy: {strategy_key}")
        logger.info(f"[DualStreamPromptBuilder] Allocation: VP={allocation.voiceprint}, F={allocation.facts}, P={allocation.persona}")

        return allocation

    async def _load_voiceprint_stream(self, executive_id: str) -> Optional[Voiceprint]:
        """
        Load voiceprint (Stream 1: Voiceprint)

        Args:
            executive_id: Executive identifier

        Returns:
            Voiceprint or None if not found
        """
        # Simulate async I/O (voiceprint cache is sync but wrapped in async)
        voiceprint = self.voiceprint_cache.get(executive_id)

        if voiceprint:
            logger.info(f"[DualStreamPromptBuilder] Loaded voiceprint for {voiceprint.name}")
        else:
            logger.warning(f"[DualStreamPromptBuilder] No voiceprint found for {executive_id}")

        return voiceprint

    async def _extract_facts_from_single_doc(
        self,
        doc: Dict,
        query: str,
        max_output_tokens: int = 300
    ) -> Dict[str, Any]:
        """
        MAP STEP: Extract facts from a single document.

        This is the core of the Map-Reduce pattern. Each document is processed
        individually with its full content (no destructive compression).

        Args:
            doc: Single document with full content (~2,000 chars)
            query: User query for context
            max_output_tokens: Max tokens for this single extraction

        Returns:
            Dict with extracted facts: {"measures": [...], "actions": [...], "compliance": [...]}
        """
        try:
            # Process single document with full content (no compression!)
            # This replicates the successful standalone test conditions
            single_doc_list = [doc]

            extracted = await self.fact_extractor.extract_facts(
                query=query,
                compressed_docs=single_doc_list,  # Single doc, full content
                max_output_tokens=max_output_tokens,
                batch_size=1  # Process just this one document
            )

            return extracted

        except Exception as e:
            logger.warning(f"[MAP] Failed to extract from document {doc.get('id', 'unknown')}: {e}")
            return {"measures": [], "actions": [], "compliance": [], "outcomes": []}

    async def _build_facts_stream(
        self,
        retrieval_results: List[Dict],
        max_tokens: int,
        query: str = ""
    ) -> str:
        """
        Build facts stream using MAP-REDUCE pattern (Gemini's solution).

        **KEY CHANGE:** No more aggressive compression that destroys data!

        MAP STEP: Process each document individually with full content
        REDUCE STEP: Aggregate all extracted facts

        Why this works:
        1. Each API call gets a full, coherent document (~2,000 chars)
        2. No fragmentation - LLM has context to extract meaningful facts
        3. Parallel processing keeps latency low (<2s total)
        4. Fault-tolerant: One failure doesn't stop others

        Args:
            retrieval_results: Results from hybrid retrieval
            max_tokens: Maximum tokens to allocate (now used for output, not compression!)
            query: User query (for fact extraction context)

        Returns:
            JSON string of aggregated facts
        """
        if not retrieval_results:
            logger.warning("[DualStreamPromptBuilder] No retrieval results for facts stream")
            return "{}"

        if not self.fact_extractor:
            logger.warning("[Facts Stream] No fact extractor available")
            return "{}"

        # ========== MAP-REDUCE PATTERN: PROCESS EACH DOCUMENT SEQUENTIALLY ==========
        # IMPORTANT: Sequential processing for Local LLM to avoid overwhelming it
        # - Local LLM can handle ~500 tokens per document in ~18s
        # - Processing in parallel causes connection issues and timeouts
        # - Sequential ensures stable connection to LM Studio
        logger.info(f"[MAP-REDUCE] Processing {len(retrieval_results)} documents sequentially (Local LLM)...")

        try:
            # MAP STEP: Process documents ONE AT A TIME
            # Each document gets its full content (~2,000 chars), not 105-char fragments!
            results = []

            for i, doc in enumerate(retrieval_results[:7]):  # Limit to 7 docs max
                logger.info(f"[MAP] Processing document {i+1}/{min(7, len(retrieval_results))}...")
                try:
                    result = await self._extract_facts_from_single_doc(
                        doc=doc,
                        query=query,
                        max_output_tokens=300  # Per document, not total
                    )
                    results.append(result)
                    logger.info(f"[MAP] ✅ Document {i+1} completed")
                except Exception as e:
                    logger.warning(f"[MAP] ❌ Document {i+1} failed: {e}")
                    results.append(e)

            # REDUCE STEP: Aggregate all facts
            all_measures = []
            all_actions = []
            all_compliance = []
            all_outcomes = []
            successful_docs = 0

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"[REDUCE] Document {i+1} failed: {result}")
                    continue

                if result and isinstance(result, dict):
                    all_measures.extend(result.get('measures', []))
                    all_actions.extend(result.get('actions', []))
                    all_compliance.extend(result.get('compliance', []))
                    all_outcomes.extend(result.get('outcomes', []))
                    successful_docs += 1

            # Build final aggregated result
            aggregated_facts = {
                "measures": all_measures,
                "actions": all_actions,
                "compliance": all_compliance,
                "outcomes": all_outcomes,
                "_metadata": {
                    "query": query,
                    "documents_processed": successful_docs,
                    "total_documents": len(retrieval_results),
                    "extraction_method": "map_reduce_parallel"
                }
            }

            facts_json = json.dumps(aggregated_facts, indent=2, ensure_ascii=False)
            facts_tokens = len(facts_json) // 4

            logger.info(
                f"[MAP-REDUCE] ✅ Extracted {len(all_measures)} measures, "
                f"{len(all_actions)} actions, {len(all_compliance)} compliance "
                f"from {successful_docs}/{len(retrieval_results)} docs (~{facts_tokens} tokens)"
            )

            return facts_json

        except Exception as e:
            logger.error(f"[MAP-REDUCE] Fact extraction failed: {e}")
            return json.dumps({"measures": [], "actions": [], "compliance": [], "outcomes": []})

    async def _build_persona_stream(
        self,
        retrieval_results: List[Dict],
        executive_id: str,
        max_tokens: int
    ) -> str:
        """
        Build persona stream (Stream 3: Persona Examples)

        Args:
            retrieval_results: Results from hybrid retrieval
            executive_id: Executive identifier
            max_tokens: Maximum tokens to allocate

        Returns:
            Formatted persona examples string
        """
        # Extract persona snippets
        # Estimate top_k based on max_tokens (assume ~100 tokens per snippet)
        top_k = min(5, max_tokens // 100)

        snippets = self.persona_extractor.extract(
            results=retrieval_results,
            executive_id=executive_id,
            top_k=top_k
        )

        # Format persona examples
        if not snippets:
            logger.warning("[DualStreamPromptBuilder] No persona snippets extracted")
            return ""

        persona_examples = []
        for i, snippet in enumerate(snippets, 1):
            example = f"""
Example {i} (persona score: {snippet.score:.2f}):
"{snippet.text}"

Context: {snippet.source_doc} - {snippet.source_section}
Matched phrases: {', '.join(snippet.matched_phrases[:3])}
""".strip()
            persona_examples.append(example)

        formatted = "\n\n".join(persona_examples)

        logger.info(f"[DualStreamPromptBuilder] Persona stream: {len(snippets)} snippets, ~{len(formatted)//4} tokens")

        return formatted

    def _format_voiceprint_pack(self, voiceprint: Optional[Voiceprint]) -> str:
        """
        Format voiceprint into compact pack for prompt

        Args:
            voiceprint: Executive voiceprint

        Returns:
            Formatted voiceprint string
        """
        if not voiceprint:
            return "No voiceprint available."

        vp = voiceprint.voiceprint

        pack = f"""
**Communication Style:**
- Signature opener: {vp.get('signature_opener', {}).get('text', 'N/A')}
- Decision cadence: {vp.get('decision_cadence', {}).get('pattern', 'N/A')}
- Sign-off: {vp.get('sign_off', {}).get('text', 'N/A')}

**Style Markers:**
- Formality: {vp.get('style_markers', {}).get('formality', 'N/A')}/10
- Directness: {vp.get('style_markers', {}).get('directness', 'N/A')}/10
- Emoji usage: {vp.get('style_markers', {}).get('emoji_usage', 'N/A')}

**Lexicon (sample):**
{', '.join(voiceprint.lexicon[:10])}
""".strip()

        return pack

    def _build_system_prompt(
        self,
        voiceprint: Optional[Voiceprint],
        executive_name: str
    ) -> str:
        """
        Build system prompt with voiceprint persona

        Args:
            voiceprint: Executive voiceprint
            executive_name: Executive's name

        Returns:
            System prompt string
        """
        if not voiceprint:
            return f"""You are answering as {executive_name}, an executive.
Be professional and helpful."""

        vp = voiceprint.voiceprint
        style_markers = vp.get('style_markers', {})

        system_prompt = f"""You are answering as {executive_name}, based on their documented communication style and decisions.

**Your Communication Style:**
- Formality level: {style_markers.get('formality', 'N/A')}/10
- Directness level: {style_markers.get('directness', 'N/A')}/10
- Warmth level: {style_markers.get('warmth', 7)}/10

**How You Typically Open:**
{vp.get('signature_opener', {}).get('text', 'Hi,')}

**How You Typically Close:**
{vp.get('sign_off', {}).get('text', 'Thanks')}

**Your Unique Phrases:**
{', '.join(voiceprint.lexicon[:15])}

Respond authentically in {executive_name}'s voice, using their communication patterns and lexicon.
"""

        return system_prompt.strip()

    def _build_user_prompt(
        self,
        query: str,
        executive_name: str,
        voiceprint_pack: str,
        facts_json: str,
        persona_examples: str
    ) -> str:
        """
        Build user prompt with all 3 streams merged

        Args:
            query: User's question
            executive_name: Executive's name
            voiceprint_pack: Formatted voiceprint pack
            facts_json: Factual information JSON
            persona_examples: Persona examples string

        Returns:
            User prompt string
        """
        # Path-specific constraints using centralized rules
        # REFACTORED (2025-01-15): Word limits now come from rules.py
        word_limit = get_word_limit_instruction(self.path)

        constraints = {
            "fast": f"""
RESPONSE REQUIREMENTS:
- {word_limit}
- Provide a quick, direct answer to the question
- Use only the most relevant sources (top 1-3)
- MANDATORY: Every factual claim MUST have a citation [Source: document_name]
""",
            "standard": f"""
RESPONSE REQUIREMENTS:
- {word_limit}
- Write in YOUR natural voice, like talking to a colleague
- Draw from multiple sources but weave them naturally
- MANDATORY: Every factual claim MUST have a citation [Source: document_name]
""",
            "agentic": f"""
RESPONSE REQUIREMENTS:
- {word_limit}
- Provide comprehensive analysis in YOUR natural voice
- Write conversationally, NOT like a formal report
- MANDATORY: Every factual claim MUST have a citation [Source: document_name]
"""
        }

        constraint_text = constraints.get(self.path, constraints["standard"])

        user_prompt = f"""Question: {query}

Answer as {executive_name} based on the following information:

---

## VOICEPRINT (Your Authentic Voice Template)

{voiceprint_pack}

---

## EXTRACTED FACTS (Structured JSON from Documents)

The following facts were extracted from source documents. Use these facts to construct your response.
All numbers, dates, and metrics are preserved exactly as they appear in the sources.

```json
{facts_json}
```

---

## PERSONA EXAMPLES (How {executive_name} Actually Communicates)

{persona_examples}

---

{constraint_text}

Provide a response that:
1. Answers the question accurately using the extracted facts JSON above
2. Communicates in {executive_name}'s authentic voice using their lexicon phrases and style
3. Maintains their typical formality, directness, and warmth levels
4. INCLUDES CITATIONS for every factual claim in format [Source: document_name]
5. Reference specific facts from the JSON structure when applicable

Your response:"""

        return user_prompt.strip()


# Test function
async def test_dual_stream():
    """Test the DualStreamPromptBuilder"""
    import sys
    sys.path.insert(0, '.')

    from profile_management.voiceprint_cache import VoiceprintCache
    from hybrid_retrieval.query_type_classifier import QueryTypeClassifier

    logging.basicConfig(level=logging.INFO)

    # Initialize components
    cache = VoiceprintCache()
    classifier = QueryTypeClassifier()
    builder = DualStreamPromptBuilder(cache, classifier)

    # Test retrieval results
    test_results = [
        {
            "document_name": "engineering_decision.txt",
            "section_title": "Technical Debt Philosophy",
            "content": "Quick thought: I'm concerned about the technical debt. We need to refactor. I committed to ¥8M for this.",
            "score": 0.95
        },
        {
            "document_name": "engineering_update.txt",
            "section_title": "Q3 Review",
            "content": "Let me nerd out for a sec - our architecture won't scale past 10k users. Bottom line: Quality over speed.",
            "score": 0.88
        }
    ]

    # Build prompts
    system_prompt, user_prompt = await builder.build(
        query="What is Yuki's philosophy on technical debt?",
        executive_id="exec_003_test",
        retrieval_results=test_results
    )

    print("\n=== SYSTEM PROMPT ===\n")
    print(system_prompt)
    print("\n=== USER PROMPT ===\n")
    print(user_prompt[:500] + "...\n")


if __name__ == "__main__":
    asyncio.run(test_dual_stream())
