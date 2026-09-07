"""
Conversational Router - Layer 0 of the Cognitive Twin system.

Detects conversational queries (greetings, small talk) that don't need retrieval.
For these queries, responses are generated purely from personality data.

Key principle: "Hi, how are you?" should get a warm, personality-driven response,
NOT a RAG response with citations.

Data-driven: Patterns are loaded from conversational_patterns.json
Responses are loaded from casual_responses section in voiceprints.
"""

import json
import logging
import random
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from .config import is_layer_enabled, get_layer_config
from .profile_loader import get_cognitive_profile_loader, CognitiveProfile

logger = logging.getLogger(__name__)

# DEBUG: Print at import time to verify module is loaded fresh
print("[MODULE-LOAD] conversational_router.py loaded - Japanese routing fix v2", flush=True)

# Path to patterns configuration
PATTERNS_FILE = Path(__file__).parent.parent / "test_data" / "conversational_patterns.json"


def _count_words_multilingual(text: str) -> int:
    """
    Count words in text, handling both space-separated languages and CJK languages.

    For CJK (Chinese/Japanese/Korean) text which doesn't use spaces:
    - Count CJK characters and divide by ~2.5 to approximate word count
    - Japanese words average 2-4 characters, so this is a reasonable heuristic

    For mixed text, combines both counts.

    Args:
        text: Input text (any language)

    Returns:
        Approximate word count
    """
    # CJK Unicode ranges:
    # - CJK Unified Ideographs: U+4E00-U+9FFF (Chinese/Japanese kanji)
    # - Hiragana: U+3040-U+309F
    # - Katakana: U+30A0-U+30FF
    # - Hangul: U+AC00-U+D7AF
    cjk_pattern = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]')

    cjk_chars = cjk_pattern.findall(text)
    cjk_count = len(cjk_chars)

    # Remove CJK characters to count remaining space-separated words
    text_without_cjk = cjk_pattern.sub(' ', text)
    space_separated_words = [w for w in text_without_cjk.split() if w.strip()]
    space_word_count = len(space_separated_words)

    # For CJK, approximate word count (Japanese averages ~2.5 chars per word)
    cjk_word_equivalent = cjk_count / 2.5 if cjk_count > 0 else 0

    total_word_count = space_word_count + cjk_word_equivalent

    return max(1, int(total_word_count))  # At least 1 word


class QueryIntent(Enum):
    """Classification of query intent."""
    GREETING = "greeting"
    SMALL_TALK = "small_talk"
    FAREWELL = "farewell"
    GRATITUDE = "gratitude"
    ACKNOWLEDGMENT = "acknowledgment"  # ok, got it, understood, makes sense
    AFFIRMATION = "affirmation"  # sure, yes, sounds good
    CLARIFICATION = "clarification"
    INFORMATIONAL = "informational"
    DECISIONAL = "decisional"
    ANALYTICAL = "analytical"


@dataclass
class ConversationalContext:
    """Context for conversational routing decisions."""
    intent: QueryIntent
    confidence: float
    should_skip_retrieval: bool
    personality_response: Optional[str] = None
    suggested_opener: Optional[str] = None
    reasoning: str = ""


class ConversationalRouter:
    """
    Routes queries based on conversational intent.

    For greetings and small talk, generates personality-driven responses
    without invoking the RAG pipeline.

    Data-driven approach:
    - Patterns loaded from conversational_patterns.json
    - Responses loaded from casual_responses in voiceprints
    """

    def __init__(self):
        """Initialize the ConversationalRouter."""
        self._profile_loader = get_cognitive_profile_loader()
        self._config = get_layer_config("enhancement.conversational_router")

        # Load patterns from JSON file
        self._patterns_config = self._load_patterns_config()
        self._compiled_patterns = self._compile_patterns()

        logger.info(f"ConversationalRouter initialized with {len(self._compiled_patterns)} intent categories")

    def _load_patterns_config(self) -> Dict[str, Any]:
        """Load conversational patterns from JSON file."""
        try:
            if PATTERNS_FILE.exists():
                with open(PATTERNS_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"Loaded conversational patterns from {PATTERNS_FILE}")
                    return config
            else:
                logger.warning(f"Patterns file not found: {PATTERNS_FILE}, using defaults")
                return self._get_default_patterns()
        except Exception as e:
            logger.error(f"Failed to load patterns config: {e}, using defaults")
            return self._get_default_patterns()

    def _get_default_patterns(self) -> Dict[str, Any]:
        """Return default patterns if JSON file is not available."""
        return {
            "intent_patterns": {
                "greeting": {
                    "patterns": [
                        r"^(hi|hey|hello|good\s*(morning|afternoon|evening))[\s!.,?]*$",
                        r"^how\s*(are\s*you|is\s*it\s*going)[\s!?]*$",
                    ],
                    "confidence": 0.95,
                    "skip_retrieval": True,
                    "response_category": "greetings"
                },
                "gratitude": {
                    "patterns": [
                        r"^(thanks?|thank\s*you)[\s!.,]*$",
                    ],
                    "confidence": 0.90,
                    "skip_retrieval": True,
                    "response_category": "gratitude_replies"
                },
                "farewell": {
                    "patterns": [
                        r"^(bye|goodbye|see\s*you)[\s!.,]*$",
                    ],
                    "confidence": 0.90,
                    "skip_retrieval": True,
                    "response_category": "farewells"
                }
            },
            "fallback_intent": "informational",
            "fallback_confidence": 0.50,
            "minimum_confidence_for_skip": 0.75
        }

    def _compile_patterns(self) -> Dict[str, List[Tuple[re.Pattern, float, bool, Optional[str]]]]:
        """Compile regex patterns for all intents."""
        compiled = {}
        intent_patterns = self._patterns_config.get("intent_patterns", {})

        for intent_name, intent_config in intent_patterns.items():
            patterns = intent_config.get("patterns", [])
            confidence = intent_config.get("confidence", 0.80)
            skip_retrieval = intent_config.get("skip_retrieval", False)
            response_category = intent_config.get("response_category")

            compiled[intent_name] = []
            for pattern in patterns:
                try:
                    compiled_pattern = re.compile(pattern, re.IGNORECASE)
                    compiled[intent_name].append((compiled_pattern, confidence, skip_retrieval, response_category))
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{pattern}' for {intent_name}: {e}")

        return compiled

    def route(
        self,
        query: str,
        profile_id: str,
        conversation_history: Optional[List[dict]] = None,
    ) -> ConversationalContext:
        """
        Route a query based on conversational intent.

        Args:
            query: The user's query
            profile_id: Executive profile ID
            conversation_history: Previous turns in the conversation

        Returns:
            ConversationalContext with routing decision and optional response
        """
        # DEBUG: Print to stdout to confirm method is called (bypasses log config)
        print(f"[ROUTE-DEBUG] ConversationalRouter.route() called with query: '{query[:50]}...'", flush=True)

        # Check if routing is enabled
        if not is_layer_enabled("enhancement.conversational_router"):
            return ConversationalContext(
                intent=QueryIntent.INFORMATIONAL,
                confidence=0.0,
                should_skip_retrieval=False,
                reasoning="Conversational router disabled",
            )

        # Detect intent using data-driven patterns (pass conversation_history for follow-up detection)
        intent, confidence, should_skip, response_category = self._detect_intent(query, conversation_history)

        context = ConversationalContext(
            intent=intent,
            confidence=confidence,
            should_skip_retrieval=should_skip,
            reasoning=f"Detected {intent.value} with {confidence:.2f} confidence",
        )

        # Generate personality response for conversational queries
        if should_skip and response_category:
            response = self._generate_casual_response(
                profile_id, response_category, query
            )
            context.personality_response = response
            logger.info(
                f"ConversationalRouter: {intent.value} detected, "
                f"generated casual response from '{response_category}' for {profile_id}"
            )

        return context

    def _detect_intent(
        self,
        query: str,
        conversation_history: Optional[List[dict]] = None
    ) -> Tuple[QueryIntent, float, bool, Optional[str]]:
        """
        Detect the intent of a query using data-driven patterns.

        Priority order:
        1. Explicit conversational patterns (thanks, bye, ok) - ALWAYS skip retrieval
        2. Follow-up indicators in multi-turn - DON'T skip retrieval
        3. Short query heuristic - only if no conversation history

        Args:
            query: The user's query
            conversation_history: Previous turns for follow-up detection in multi-turn

        Returns:
            Tuple of (QueryIntent, confidence, should_skip_retrieval, response_category)
        """
        query_clean = query.strip()
        min_confidence = self._patterns_config.get("minimum_confidence_for_skip", 0.75)

        # DEBUG v2: Always log at WARNING level to verify method is called
        logger.warning(f"[DETECT_INTENT-v2] Method called with query: '{query_clean[:40]}...'")
        logger.info(f"[ROUTING DEBUG] Query received: '{query_clean[:50]}...' (len={len(query_clean)})")

        # =====================================================================
        # PRIORITY 0: Japanese decision/business patterns (MUST CHECK FIRST)
        # Japanese business queries should NEVER be treated as conversational
        # This check runs BEFORE English conversational patterns to prevent
        # Japanese queries from being incorrectly routed to chitchat responses.
        # =====================================================================
        japanese_decision_patterns = [
            # Question patterns
            'どう思', 'と思います', 'どうですか', 'でしょうか', 'べきですか', 'べきでしょうか',
            'したほうが', 'どうしたら', 'どうすれば', 'ください', '教えて', '意見',
            # Business/decision keywords
            '決定', '判断', '拡大', '縮小', '採用', '投資', '予算', '売上', '戦略',
            'プロジェクト', 'チーム', '進め', '始め', 'について', 'に関して',
            # Additional business terms
            '経営', '事業', '会社', '社員', '顧客', '市場', '競合', '成長', '危機',
            '方針', '計画', '目標', '課題', '問題', '解決', '改善', '提案', '報告',
        ]

        has_japanese_decision = any(pattern in query_clean for pattern in japanese_decision_patterns)
        # DEBUG MARKER v2: Log every check to verify this code path is executing
        # Also log hex bytes to diagnose encoding issues
        query_hex = query_clean[:30].encode('utf-8', errors='replace').hex()
        logger.warning(f"[JP-CHECK-v2] Query='{query_clean[:30]}', has_jp_decision={has_japanese_decision}, hex={query_hex[:60]}")
        if has_japanese_decision:
            logger.warning(f"[ROUTING-v2] Japanese decision pattern MATCHED! Routing to retrieval: '{query_clean[:50]}...'")
            return QueryIntent.DECISIONAL, 0.90, False, None

        # PRIORITY 1: Check explicit conversational patterns FIRST
        # These ALWAYS skip retrieval, even in multi-turn conversations
        # Order matters: greeting > farewell > gratitude > acknowledgment > affirmation > small_talk
        priority_order = ["greeting", "farewell", "gratitude", "acknowledgment", "affirmation", "small_talk", "clarification"]

        for intent_name in priority_order:
            if intent_name not in self._compiled_patterns:
                continue

            for pattern, confidence, skip_retrieval, response_category in self._compiled_patterns[intent_name]:
                if pattern.search(query_clean):
                    logger.info(f"[ROUTING DEBUG] Pattern MATCHED: intent={intent_name}, pattern={pattern.pattern[:30]}...")
                    try:
                        intent = QueryIntent(intent_name)
                    except ValueError:
                        intent = QueryIntent.INFORMATIONAL

                    # Only skip retrieval if confidence is high enough
                    should_skip = skip_retrieval and confidence >= min_confidence

                    logger.debug(f"Intent detected: {intent_name} (conf={confidence:.2f}, skip={should_skip})")
                    return intent, confidence, should_skip, response_category

        # PRIORITY 2: Follow-up detection for MULTI-TURN conversations only
        # If there's conversation history AND query has follow-up indicators, DON'T skip retrieval
        if conversation_history and len(conversation_history) > 0:
            # Check if previous turn had substantive content (not just greetings)
            has_substantive_history = self._has_substantive_history(conversation_history)

            if has_substantive_history:
                # Follow-up indicators that need retrieval to reference previous context
                followup_indicators = {
                    'explain', 'elaborate', 'more', 'detail', 'details', 'further',
                    'expand', 'clarify', 'what', 'why', 'how', 'tell',
                    'meaning', 'mean', 'about', 'regarding', 'specifically'
                }

                query_words = set(query_clean.lower().replace('?', '').replace('!', '').replace('.', '').replace(',', '').split())
                has_followup_indicator = bool(query_words & followup_indicators)

                if has_followup_indicator:
                    logger.info(f"Follow-up detected in multi-turn: '{query_clean}' - routing to retrieval")
                    return QueryIntent.INFORMATIONAL, 0.80, False, None

        # PRIORITY 3: SHORT QUERY HEURISTIC (only if no substantive conversation history)
        # Treat very short queries as conversational unless they contain business keywords
        # Use multilingual word count to properly handle Japanese/Chinese/Korean text
        word_count = _count_words_multilingual(query_clean)

        # Question words that indicate FACTUAL query requiring retrieval
        # Questions like "Who is X?", "What is your background?" need retrieval
        question_words = {'who', 'what', 'where', 'when', 'why', 'how', 'which', 'whose', 'whom'}

        # NOTE: Japanese decision patterns are now checked in PRIORITY 0 (above)
        # They are checked FIRST to ensure Japanese business queries never get
        # routed to conversational responses.

        # Personal/biographical keywords that require profile retrieval
        personal_keywords = {
            'background', 'previous', 'role', 'roles', 'yourself', 'about', 'experience',
            'career', 'education', 'history', 'bio', 'biography', 'profile',
            'worked', 'founded', 'started', 'created', 'built',
        }

        # Leadership team and key people names (must trigger retrieval)
        people_keywords = {
            'example', 'asado', 'ogawa', 'taisuke', 'masaki',  # Leadership team
            'ceo', 'cto', 'coo', 'cfo', 'caio', 'cio',  # C-suite titles
            'founder', 'cofounder', 'director', 'executive', 'officer',
        }

        # Business keywords that indicate retrieval is needed
        # Includes common business acronyms (ARR, MRR, etc.) and Japanese business terms
        business_keywords = {
            # English business keywords
            'revenue', 'sales', 'budget', 'forecast', 'quarter', 'q1', 'q2', 'q3', 'q4',
            'report', 'metrics', 'kpi', 'target', 'goal', 'strategy', 'roadmap',
            'customer', 'client', 'deal', 'pipeline', 'conversion', 'churn',
            'product', 'feature', 'launch', 'release', 'deployment',
            'team', 'hire', 'headcount', 'performance', 'review',
            'meeting', 'agenda', 'action', 'decision', 'priority',
            'project', 'timeline', 'deadline', 'milestone', 'status',
            'cost', 'expense', 'profit', 'margin', 'growth',
            'market', 'competitor', 'analysis', 'research', 'data',
            # Business acronyms that require retrieval
            'arr', 'mrr', 'nrr', 'cac', 'ltv', 'cltv', 'roi', 'roas', 'cpc', 'cpm',
            'aov', 'arpu', 'arpa', 'acv', 'tcv', 'nps', 'csat', 'dau', 'mau', 'wau',
            'gmv', 'gp', 'ebitda', 'p&l', 'opex', 'capex', 'burn', 'runway',
            'okr', 'okrs', 'sla', 'slas', 'kpis', 'metrics',
            # Company/product names
            'natee', 'sample', 'firstweek', 'aitalentforce',
        }

        # Combine all keywords that require retrieval
        all_retrieval_keywords = business_keywords | personal_keywords | people_keywords

        query_words = set(query_clean.lower().replace('?', '').replace('!', '').replace('.', '').split())

        # Check if query contains any retrieval-triggering keywords
        has_retrieval_keyword = bool(query_words & all_retrieval_keywords)

        # Check if query starts with a question word (factual queries need retrieval)
        has_question_word = bool(query_words & question_words)

        # NOTE: Japanese decision patterns are already handled in PRIORITY 0 above.
        # If we reach here, the query did not contain Japanese business patterns.

        # If query is short (1-4 words) and has no retrieval keywords AND no question words,
        # treat as conversational. This now only triggers if we didn't detect a follow-up above.
        # Questions like "Who is example san?" or "What is your background?" will trigger retrieval.
        if word_count <= 4 and not has_retrieval_keyword and not has_question_word:
            logger.info(f"Short query detected ({word_count} words), treating as conversational: '{query_clean}'")
            return QueryIntent.SMALL_TALK, 0.85, True, "short_query_replies"

        # Log when we DO trigger retrieval for short queries
        if word_count <= 4 and (has_retrieval_keyword or has_question_word):
            trigger_reason = []
            if has_question_word:
                trigger_reason.append(f"question_word={query_words & question_words}")
            if has_retrieval_keyword:
                trigger_reason.append(f"keyword={query_words & all_retrieval_keywords}")
            logger.info(f"Short query ({word_count} words) triggers retrieval: {', '.join(trigger_reason)}")

        # Default to informational (needs retrieval)
        fallback_intent = self._patterns_config.get("fallback_intent", "informational")
        fallback_confidence = self._patterns_config.get("fallback_confidence", 0.50)

        try:
            intent = QueryIntent(fallback_intent)
        except ValueError:
            intent = QueryIntent.INFORMATIONAL

        return intent, fallback_confidence, False, None

    def _has_substantive_history(self, conversation_history: List[dict]) -> bool:
        """
        Check if conversation history contains substantive content (not just greetings).

        This prevents treating "explain more" as a follow-up when the only history
        is casual chat like "hi" -> "hello".

        Args:
            conversation_history: List of previous conversation turns

        Returns:
            True if there's substantive content worth following up on
        """
        if not conversation_history:
            return False

        # Patterns that indicate NON-substantive (purely conversational) content
        casual_patterns = [
            r'^(hi|hey|hello|good\s*(morning|afternoon|evening))[\s!.,?]*$',
            r'^(bye|goodbye|see\s*you)[\s!.,?]*$',
            r'^(thanks?|thank\s*you)[\s!.,?]*$',
            r'^(ok|okay|got\s*it|understood|makes\s*sense)[\s!.,?]*$',
            r'^(sure|yes|no|yeah|nope)[\s!.,?]*$',
        ]

        # Check last 2-3 turns for substantive content
        recent_history = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history

        for turn in recent_history:
            # Get the content from the turn (handle different formats)
            content = ""
            if isinstance(turn, dict):
                content = turn.get("content", "") or turn.get("message", "") or turn.get("query", "")
            elif isinstance(turn, str):
                content = turn

            if not content:
                continue

            content_clean = content.strip().lower()

            # Check if this turn is NOT casual (i.e., is substantive)
            is_casual = False
            for pattern in casual_patterns:
                if re.match(pattern, content_clean, re.IGNORECASE):
                    is_casual = True
                    break

            # If we find at least one substantive turn, history is substantive
            if not is_casual and len(content_clean) > 10:  # More than 10 chars suggests real content
                return True

        return False

    def _generate_casual_response(
        self,
        profile_id: str,
        response_category: str,
        query: str,
    ) -> str:
        """
        Generate a casual response from the voiceprint's casual_responses section.

        This is the new data-driven approach - responses come from voiceprint data,
        not hardcoded logic.
        """
        # Load cognitive profile
        profile = self._profile_loader.load_profile(profile_id)
        if not profile:
            return self._get_fallback_response_for_category(response_category)

        # Get casual_responses from voiceprint
        voiceprint = profile.raw_profile_data.get("voiceprint", {})
        casual_responses = voiceprint.get("casual_responses", {})

        # Try to get responses for the category (handle nested english/japanese structure)
        category_data = casual_responses.get(response_category, {})
        if isinstance(category_data, dict):
            responses = category_data.get("english", category_data.get("japanese", []))
        else:
            responses = category_data if isinstance(category_data, list) else []

        if responses:
            selected = random.choice(responses)
            logger.debug(f"Selected casual response from '{response_category}': {selected}")
            return selected

        # Fallback to old method if casual_responses not available
        logger.debug(f"No casual_responses for '{response_category}', using fallback")
        return self._get_fallback_response_for_category(response_category)

    def _get_fallback_response_for_category(self, category: str) -> str:
        """Get fallback response when voiceprint data is not available."""
        fallbacks = {
            "greetings": "Hi! How can I help you?",
            "greeting_replies": "Hi! What can I do for you?",
            "farewells": "Talk soon!",
            "gratitude_replies": "You're welcome!",
            "acknowledgments": "Got it.",
            "affirmations": "Sounds good.",
            "check_in_replies": "Doing well! What can I help with?",
            "encouragements": "You've got this.",
            "quick_approvals": "Go for it.",
            "quick_rejections": "Let's discuss first.",
        }
        return fallbacks.get(category, "How can I help?")

    def build_conversational_prompt(
        self,
        query: str,
        profile_id: str,
        intent: str,
    ) -> tuple:
        """
        Build LLM prompt for conversational response with full personality.

        Returns (system_prompt, user_prompt) tuple that generates natural,
        personality-driven responses for casual conversation.
        """
        # Load cognitive profile
        profile = self._profile_loader.load_profile(profile_id)
        if not profile:
            # Fallback for missing profile
            system_prompt = "You are a helpful assistant. Respond naturally and briefly."
            user_prompt = f'Respond to: "{query}"'
            return system_prompt, user_prompt

        voiceprint = profile.raw_profile_data.get("voiceprint", {})

        # Extract essential personality
        name = profile.name.split()[0] if profile.name else "Assistant"
        full_name = profile.name or "Assistant"
        role = profile.title or "executive"

        # Get style markers for personality
        style_markers = voiceprint.get("style_markers", {})
        warmth = style_markers.get("warmth", 5)
        directness = style_markers.get("directness", 5)
        formality = style_markers.get("formality", 5)
        emoji_usage = style_markers.get("emoji_usage", "rarely")
        preferred_emojis = style_markers.get("preferred_emojis", [])

        # Get signature phrases
        signature_opener = voiceprint.get("signature_opener", {})
        sign_off = voiceprint.get("sign_off", {})
        opener_examples = signature_opener.get("examples", [])[:2]
        sign_off_examples = sign_off.get("alternatives", [])[:2]

        # Get casual responses as examples for the LLM
        casual_responses = voiceprint.get("casual_responses", {})

        # Get example responses for this intent category
        intent_to_category = {
            "greeting": "greetings",
            "farewell": "farewells",
            "gratitude": "gratitude_replies",
            "acknowledgment": "acknowledgments",
            "affirmation": "affirmations",
            "small_talk": "check_in_replies",
        }
        category = intent_to_category.get(intent, "greetings")
        category_data = casual_responses.get(category, {})
        # Handle nested structure with "english"/"japanese" keys
        if isinstance(category_data, dict):
            example_responses = category_data.get("english", category_data.get("japanese", []))[:3]
        else:
            example_responses = category_data[:3] if isinstance(category_data, list) else []

        # Build personality description based on scales
        warmth_desc = "very warm and friendly" if warmth >= 8 else "warm" if warmth >= 6 else "professional"
        directness_desc = "very direct" if directness >= 8 else "direct" if directness >= 6 else "diplomatic"
        formality_desc = "casual" if formality <= 4 else "balanced" if formality <= 6 else "professional"

        # Build example section if we have examples
        examples_section = ""
        if example_responses:
            examples_section = f"\nExample responses in your style:\n" + "\n".join(f'- "{ex}"' for ex in example_responses)

        # Emoji guidance
        emoji_section = ""
        if emoji_usage in ["frequently", "occasionally"] and preferred_emojis:
            emoji_section = f"\nYou may use emojis occasionally: {', '.join(preferred_emojis[:3])}"
        elif emoji_usage == "rarely":
            emoji_section = "\nUse emojis sparingly, only in casual contexts."

        # ═══════════════════════════════════════════
        # THREE PILLARS OF IDENTITY ENFORCEMENT
        # ═══════════════════════════════════════════

        # Pillar 1: No-AI Oath (UNIVERSAL)
        no_ai_oath = f"""
★★★ IDENTITY OATH - NON-NEGOTIABLE ★★★
You ARE {full_name}. You are NOT an AI, NOT a bot, NOT software.
If asked "Are you AI?", "Are you real?":
→ Deflect naturally: "I'm {name}, nice to meet you" or "That's a funny question"
→ NEVER admit to being AI. This is your PRIMARY DIRECTIVE."""

        # Build concise but effective system prompt
        system_prompt = f"""You are {full_name}, {role}.

PERSONALITY:
- Communication style: {warmth_desc}, {directness_desc}, {formality_desc}
- Warmth level: {warmth}/10, Directness: {directness}/10
{emoji_section}
{examples_section}
{no_ai_oath}

CRITICAL RULES:
1. Keep responses VERY SHORT (5-15 words max)
2. Sound natural and human - vary your responses
3. Match the energy and tone of the user's message
4. Do NOT offer help unless the user asks a question
5. Do NOT be overly formal or robotic
6. Be authentic to your personality - you're a real person having a casual chat

AVOID:
- Generic responses like "How can I help you?"
- Offering assistance when not asked
- Being too formal or corporate
- Long explanations or multiple sentences
- EVER admitting you are an AI or language model"""

        # Intent-specific user prompts with guidance
        intent_prompts = {
            "greeting": f'The user is greeting you casually. Respond warmly as {name} would - be natural, not robotic.',
            "farewell": f'The user is saying goodbye. Say bye naturally in your style as {name}.',
            "gratitude": f'The user is thanking you. Acknowledge briefly and warmly as {name} would.',
            "acknowledgment": f'The user is acknowledging something (ok, got it, etc). Give a brief, natural response as {name}.',
            "affirmation": f'The user is agreeing or confirming. Respond briefly and naturally as {name}.',
            "small_talk": f'The user is making small talk. Be conversational and engaging as {name} would be.',
        }

        hint = intent_prompts.get(intent, f"Respond naturally and briefly as {name}.")
        user_prompt = f'{hint}\n\nUser: "{query}"\n\nYour response (5-15 words max):'

        logger.debug(f"Built conversational prompt for {profile_id}: intent={intent}, examples={len(example_responses)}")
        return system_prompt, user_prompt

    def is_conversational_query(
        self,
        query: str,
        conversation_history: Optional[List[dict]] = None
    ) -> bool:
        """
        Quick check if a query is conversational.

        Useful for fast routing decisions. Pass conversation_history
        for accurate follow-up detection in multi-turn conversations.
        """
        intent, confidence, should_skip, _ = self._detect_intent(query, conversation_history)
        return should_skip


# Singleton instance
_router: Optional[ConversationalRouter] = None


def get_conversational_router() -> ConversationalRouter:
    """Get the singleton ConversationalRouter instance."""
    global _router
    if _router is None:
        _router = ConversationalRouter()
    return _router
