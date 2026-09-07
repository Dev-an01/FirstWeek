"""
Inference Engine - Cognitive reasoning for opinion/decision/values queries.

When a query is NOT factual (doesn't need exact data retrieval), this engine
uses the executive's inference_framework to reason through and form responses.

Key principle: For opinions/decisions/values, the system should NEVER say
"I don't have that information" - it should think through the problem using
the executive's thinking patterns and values, then form an authentic response.

Query Types:
- FACTUAL: "What's our ARR?" -> Needs retrieval, OK to say "don't know"
- OPINION: "What do you think about X?" -> Use inference framework
- DECISION: "Should we do Y?" -> Use values + trade-offs
- CONCERN: "I'm worried about Z" -> Use handling_concerns pattern
- VALUES: "Why do you emphasize transparency?" -> Use core_values
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple

from .profile_loader import get_cognitive_profile_loader, CognitiveProfile
from .config import is_layer_enabled

logger = logging.getLogger(__name__)


class QueryNature(Enum):
    """Classification of query nature - determines response approach."""
    FACTUAL = "factual"           # Needs exact data, retrieval-dependent
    OPINION = "opinion"           # Asking for viewpoint, use inference
    DECISION = "decision"         # Asking for judgment call, use values
    CONCERN = "concern"           # Expressing worry, needs empathetic handling
    VALUES = "values"             # Asking about principles/beliefs
    STRATEGIC = "strategic"       # High-level business strategy
    CONVERSATIONAL = "conversational"  # Greetings, small talk (handled elsewhere)


@dataclass
class QueryClassification:
    """Result of query nature classification."""
    nature: QueryNature
    confidence: float
    needs_retrieval: bool
    needs_inference: bool
    reasoning: str
    detected_keywords: List[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict for LangGraph state."""
        return {
            "nature": self.nature.value,
            "confidence": float(self.confidence),  # Ensure Python float, not numpy
            "needs_retrieval": self.needs_retrieval,
            "needs_inference": self.needs_inference,
            "reasoning": self.reasoning,
            "detected_keywords": self.detected_keywords or [],
        }


@dataclass
class InferenceResult:
    """Result of inference reasoning."""
    reasoning_steps: List[str]
    applied_values: List[str]
    risk_assessment: Optional[str]
    red_flags_triggered: List[str]
    suggested_response_pattern: str
    confidence: float
    should_escalate: bool
    escalation_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict for LangGraph state."""
        return {
            "reasoning_steps": self.reasoning_steps,
            "applied_values": self.applied_values,
            "risk_assessment": self.risk_assessment,
            "red_flags_triggered": self.red_flags_triggered,
            "suggested_response_pattern": self.suggested_response_pattern,
            "confidence": float(self.confidence),  # Ensure Python float, not numpy
            "should_escalate": self.should_escalate,
            "escalation_reason": self.escalation_reason,
        }


class QueryNatureClassifier:
    """
    Classifies queries by nature to determine response approach.

    Factual queries need retrieval and can say "don't know".
    Opinion/decision/values queries use inference framework.
    """

    # Patterns indicating FACTUAL queries (need exact data)
    FACTUAL_PATTERNS = [
        # Numbers and metrics
        r'\b(how many|how much|what is the|what\'s the)\b.*(number|count|amount|total|figure)',
        r'\b(arr|mrr|revenue|sales|budget|cost|price|salary|headcount)\b',
        r'\b(when did|what date|what time|which year|which month)\b',
        r'\b(who is|who are|who was|whose)\b',
        r'\b(where is|where are|what location|which office)\b',
        r'\b(list|enumerate|name all|show me all)\b',
        # Specific data requests
        r'\b(exact|specific|precise|actual)\b.*(number|figure|data|amount)',
        r'\b(according to|based on|per the)\b.*(report|document|policy)',
    ]

    # Patterns indicating OPINION queries
    OPINION_PATTERNS = [
        r'\b(what do you think|what\'s your (view|opinion|take)|how do you see)\b',
        r'\b(your (thoughts|perspective|view) on)\b',
        r'\b(do you (think|believe|feel))\b',
        r'\b(would you (say|agree|recommend))\b',
        r'\b(in your (opinion|view|experience))\b',
        r'\b(how would you (describe|characterize|assess))\b',
    ]

    # Patterns indicating DECISION queries
    DECISION_PATTERNS = [
        r'\b(should (we|i|the team)|shall we|would you)\b',
        r'\b(is it (worth|a good idea|advisable|better))\b',
        r'\b(what would you (do|decide|choose|recommend))\b',
        r'\b(which (option|approach|path|way) should)\b',
        r'\b(go ahead with|proceed with|move forward)\b',
        r'\b(approve|reject|accept|decline)\b.*(this|the|our)',
        r'\b(make (a|the) (call|decision|choice))\b',
    ]

    # Patterns indicating CONCERN queries
    CONCERN_PATTERNS = [
        r'\b(i\'m (worried|concerned|anxious|nervous) about)\b',
        r'\b(my concern is|the concern is|concerns about)\b',
        r'\b(what if|what happens if)\b.*(fails?|goes wrong|doesn\'t work)',
        r'\b(risk|risky|danger|dangerous)\b',
        r'\b(afraid|fear|scared)\b',
        r'\b(problem with|issue with|trouble with)\b',
    ]

    # Patterns indicating VALUES queries
    VALUES_PATTERNS = [
        r'\b(why (do you|is it) (important|emphasize|value|prioritize))\b',
        r'\b(what (matters|counts) (most|to you))\b',
        r'\b(your (values|principles|beliefs|philosophy))\b',
        r'\b(how do you (approach|handle|deal with))\b',
        r'\b(what\'s your (stance|position) on)\b',
    ]

    # Patterns indicating STRATEGIC queries
    STRATEGIC_PATTERNS = [
        r'\b(strategy|strategic|long.?term|roadmap|vision)\b',
        r'\b(market|competitive|industry|sector)\b.*(position|analysis|trend)',
        r'\b(growth|expansion|scale|pivot)\b',
        r'\b(partner|partnership|acquisition|merger)\b',
        r'\b(invest|investment|funding|capital)\b',
    ]

    def __init__(self):
        """Initialize the classifier with compiled patterns."""
        self._compiled_patterns = {
            QueryNature.FACTUAL: [re.compile(p, re.IGNORECASE) for p in self.FACTUAL_PATTERNS],
            QueryNature.OPINION: [re.compile(p, re.IGNORECASE) for p in self.OPINION_PATTERNS],
            QueryNature.DECISION: [re.compile(p, re.IGNORECASE) for p in self.DECISION_PATTERNS],
            QueryNature.CONCERN: [re.compile(p, re.IGNORECASE) for p in self.CONCERN_PATTERNS],
            QueryNature.VALUES: [re.compile(p, re.IGNORECASE) for p in self.VALUES_PATTERNS],
            QueryNature.STRATEGIC: [re.compile(p, re.IGNORECASE) for p in self.STRATEGIC_PATTERNS],
        }
        logger.info("QueryNatureClassifier initialized")

    def classify(self, query: str) -> QueryClassification:
        """
        Classify a query by its nature.

        Returns QueryClassification with:
        - nature: The query type
        - needs_retrieval: Whether to search knowledge base
        - needs_inference: Whether to use inference framework
        """
        query_clean = query.strip().lower()

        # Score each nature type
        scores: Dict[QueryNature, Tuple[float, List[str]]] = {}

        for nature, patterns in self._compiled_patterns.items():
            matches = []
            for pattern in patterns:
                if pattern.search(query_clean):
                    matches.append(pattern.pattern[:30] + "...")

            if matches:
                # Score based on number of matching patterns
                score = min(0.95, 0.6 + (len(matches) * 0.15))
                scores[nature] = (score, matches)

        # Determine primary nature
        if not scores:
            # Default: Check if it's a question
            if '?' in query or query_clean.startswith(('what', 'why', 'how', 'when', 'where', 'who', 'which')):
                # General question - could be factual or opinion
                # Use inference if no strong factual indicators
                return QueryClassification(
                    nature=QueryNature.OPINION,
                    confidence=0.6,
                    needs_retrieval=True,  # Try retrieval first
                    needs_inference=True,   # But also prepare inference
                    reasoning="General question - will use retrieval + inference fallback",
                    detected_keywords=[]
                )
            else:
                # Statement or command - treat as needing inference
                return QueryClassification(
                    nature=QueryNature.OPINION,
                    confidence=0.5,
                    needs_retrieval=False,
                    needs_inference=True,
                    reasoning="Statement/command - using inference",
                    detected_keywords=[]
                )

        # Get highest scoring nature
        best_nature = max(scores.keys(), key=lambda n: scores[n][0])
        best_score, best_matches = scores[best_nature]

        # Determine retrieval and inference needs
        if best_nature == QueryNature.FACTUAL:
            return QueryClassification(
                nature=best_nature,
                confidence=best_score,
                needs_retrieval=True,
                needs_inference=False,  # Factual = don't use inference, OK to say "don't know"
                reasoning=f"Factual query detected - retrieval required",
                detected_keywords=best_matches
            )
        else:
            # Opinion, Decision, Concern, Values, Strategic - ALL use inference
            return QueryClassification(
                nature=best_nature,
                confidence=best_score,
                needs_retrieval=True,  # Still try retrieval for context
                needs_inference=True,  # But MUST use inference to form response
                reasoning=f"{best_nature.value} query detected - will use inference framework",
                detected_keywords=best_matches
            )


class InferenceEngine:
    """
    Reasons through queries using the executive's inference framework.

    For opinion/decision/values queries, this engine:
    1. Applies the executive's typical questions
    2. Checks relevant core values
    3. Applies value trade-offs
    4. Checks red flags
    5. Forms a response pattern

    Key principle: NEVER say "I don't know" for opinion/decision queries.
    Instead, reason through using the executive's thinking framework.
    """

    def __init__(self):
        """Initialize the inference engine."""
        self._profile_loader = get_cognitive_profile_loader()
        self._classifier = QueryNatureClassifier()
        logger.info("InferenceEngine initialized")

    def classify_query(self, query: str) -> QueryClassification:
        """Classify a query by nature."""
        return self._classifier.classify(query)

    def reason(
        self,
        query: str,
        profile_id: str,
        classification: Optional[QueryClassification] = None,
        retrieval_context: Optional[List[Dict]] = None,
    ) -> InferenceResult:
        """
        Reason through a query using the executive's inference framework.

        Args:
            query: The user's query
            profile_id: Executive profile ID
            classification: Pre-computed classification (optional)
            retrieval_context: Any retrieved context (for reference, not dependence)

        Returns:
            InferenceResult with reasoning steps and response guidance
        """
        if classification is None:
            classification = self._classifier.classify(query)

        # Load profile
        profile = self._profile_loader.load_profile(profile_id)
        if not profile:
            logger.warning(f"Profile not found: {profile_id}, using generic reasoning")
            return self._generic_reasoning(query, classification)

        # Get inference framework from profile
        raw_data = profile.raw_profile_data
        inference_framework = raw_data.get("inference_framework", {})
        core_values = raw_data.get("core_values", [])
        decision_making = raw_data.get("decision_making", {})
        red_flags = raw_data.get("red_flags", {})
        thinking_patterns = raw_data.get("thinking_patterns", {})

        # Step 1: Apply typical questions
        reasoning_steps = self._apply_typical_questions(
            query,
            thinking_patterns.get("typical_questions", [])
        )

        # Step 2: Identify relevant values
        applied_values = self._identify_relevant_values(
            query,
            classification.nature,
            core_values
        )

        # Step 3: Apply value trade-offs
        trade_off_guidance = self._apply_trade_offs(
            query,
            classification.nature,
            decision_making.get("value_trade_offs", {})
        )
        reasoning_steps.append(f"Trade-off guidance: {trade_off_guidance}")

        # Step 4: Risk assessment (for decision queries)
        risk_assessment = None
        if classification.nature in [QueryNature.DECISION, QueryNature.STRATEGIC]:
            risk_assessment = self._assess_risk(
                query,
                inference_framework.get("decision_making_for_unknowns", {}).get("risk_assessment", {})
            )
            reasoning_steps.append(f"Risk assessment: {risk_assessment}")

        # Step 5: Check red flags
        red_flags_triggered = self._check_red_flags(
            query,
            red_flags.get("never_approve", [])
        )

        # Step 6: Determine if escalation needed
        should_escalate = False
        escalation_reason = None
        escalation_triggers = red_flags.get("ai_should_escalate_when", [])
        for trigger in escalation_triggers:
            trigger_lower = trigger.lower()
            if any(word in query.lower() for word in ['legal', 'compliance', 'lawsuit', 'm&a', 'acquisition', 'funding']):
                should_escalate = True
                escalation_reason = trigger
                break

        # Step 7: Determine response pattern
        response_pattern = self._get_response_pattern(
            classification.nature,
            inference_framework.get("response_length_guidance", {}),
            inference_framework.get("opinion_formation", {})
        )

        # Calculate confidence based on how well we matched
        confidence = min(0.9, classification.confidence + (len(applied_values) * 0.05))
        if red_flags_triggered:
            confidence = max(0.5, confidence - 0.2)

        return InferenceResult(
            reasoning_steps=reasoning_steps,
            applied_values=applied_values,
            risk_assessment=risk_assessment,
            red_flags_triggered=red_flags_triggered,
            suggested_response_pattern=response_pattern,
            confidence=confidence,
            should_escalate=should_escalate,
            escalation_reason=escalation_reason
        )

    def _apply_typical_questions(
        self,
        query: str,
        typical_questions: List[str]
    ) -> List[str]:
        """Apply the executive's typical internal questions."""
        if not typical_questions:
            return ["Considering the situation carefully..."]

        # Select relevant questions based on query content
        reasoning = []
        query_lower = query.lower()

        relevance_map = {
            "data": ["データは何を示していますか", "data"],
            "delegate": ["権限移譲", "自分がやるべき", "delegation"],
            "transparent": ["透明性", "見えないところ", "transparency"],
            "focus": ["フォーカス", "戦力分散", "focus"],
            "risk": ["コンプライアンス", "リスク", "compliance", "risk"],
            "mission": ["ミッション", "mission"],
        }

        for q in typical_questions:
            q_lower = q.lower()
            for keyword, indicators in relevance_map.items():
                if any(ind in query_lower or ind in q_lower for ind in indicators):
                    reasoning.append(f"Internal check: {q}")
                    break

        # Always include at least 2 questions
        if len(reasoning) < 2 and typical_questions:
            reasoning.extend([f"Internal check: {q}" for q in typical_questions[:2]])

        return reasoning[:4]  # Max 4 reasoning steps

    def _identify_relevant_values(
        self,
        query: str,
        nature: QueryNature,
        core_values: List[Dict]
    ) -> List[str]:
        """Identify which core values are relevant to this query."""
        if not core_values:
            return []

        relevant = []
        query_lower = query.lower()

        for value in core_values:
            value_name = value.get("name", "")
            description = value.get("description", "").lower()
            behavior = value.get("behavior", "").lower()

            # Check if value is relevant to query
            if any(word in query_lower for word in description.split()[:5]):
                relevant.append(value_name)
            elif nature == QueryNature.DECISION and value.get("priority", 99) <= 3:
                # Top 3 values always relevant for decisions
                relevant.append(value_name)

        return relevant[:3]  # Max 3 values

    def _apply_trade_offs(
        self,
        query: str,
        nature: QueryNature,
        trade_offs: Dict[str, Dict]
    ) -> str:
        """Apply value trade-offs to guide the response."""
        if not trade_offs:
            return "Balancing competing priorities..."

        query_lower = query.lower()

        # Map query keywords to relevant trade-offs
        keyword_map = {
            "quality_vs_speed": ["quality", "perfect", "fast", "quick", "deadline"],
            "risk_avoidance_vs_risk_taking": ["risk", "safe", "bold", "careful"],
            "delegation_vs_hands_on": ["delegate", "handle", "myself", "team"],
            "transparency_vs_confidentiality": ["transparent", "open", "secret", "private"],
            "conservative_vs_aggressive_growth": ["growth", "expand", "stable", "aggressive"],
        }

        for trade_off_name, keywords in keyword_map.items():
            if any(kw in query_lower for kw in keywords):
                trade_off = trade_offs.get(trade_off_name, {})
                score = trade_off.get("score", 5)
                leans = trade_off.get("leans", "balanced")
                return f"On {trade_off_name.replace('_', ' ')}: strongly {leans} (score {score}/10)"

        # Default to speed vs quality for decisions
        if nature == QueryNature.DECISION:
            speed_score = trade_offs.get("quality_vs_speed", {}).get("score", 5)
            return f"Default: bias toward action/speed (score {speed_score}/10)"

        return "Balancing based on context..."

    def _assess_risk(
        self,
        query: str,
        risk_config: Dict
    ) -> str:
        """Assess risk based on the decision framework."""
        take_when = risk_config.get("take_when", "upside is large and controllable")
        avoid_when = risk_config.get("avoid_when", "uncontrollable outcomes")

        query_lower = query.lower()

        # Check for risk indicators
        if any(word in query_lower for word in ['compliance', 'legal', 'regulation', 'lawsuit']):
            return f"CAUTION: Potential compliance risk - {avoid_when}"
        elif any(word in query_lower for word in ['experiment', 'test', 'pilot', 'try']):
            return f"Acceptable risk: {take_when}"
        else:
            return f"Evaluate: Take risk if {take_when}. Avoid if {avoid_when}."

    def _check_red_flags(
        self,
        query: str,
        never_approve: List[str]
    ) -> List[str]:
        """Check if any red flags are triggered."""
        triggered = []
        query_lower = query.lower()

        red_flag_keywords = {
            "見えないところ": ["hidden", "secret", "behind", "without telling"],
            "コンプライアンス違反": ["illegal", "violate", "bypass", "workaround"],
            "コントロールできない": ["uncontrollable", "unpredictable", "gamble"],
            "戦力の分散": ["multiple projects", "spread thin", "too many"],
        }

        for flag in never_approve:
            flag_lower = flag.lower()
            # Check both the flag itself and mapped keywords
            for jp_key, en_keywords in red_flag_keywords.items():
                if jp_key in flag_lower:
                    if any(kw in query_lower for kw in en_keywords):
                        triggered.append(flag)
                        break

        return triggered

    def _get_response_pattern(
        self,
        nature: QueryNature,
        length_guidance: Dict,
        opinion_formation: Dict
    ) -> str:
        """Determine the appropriate response pattern."""
        patterns = {
            QueryNature.OPINION: "State opinion softly (〜と思います) + brief reasoning",
            QueryNature.DECISION: "Clear stance + 2-3 numbered action items",
            QueryNature.CONCERN: "Acknowledge concern + address directly + suggest next step",
            QueryNature.VALUES: "Explain value + why it matters + concrete example",
            QueryNature.STRATEGIC: "Context → Opinion → Key considerations → Recommendation",
            QueryNature.FACTUAL: "Direct answer if known, or admit uncertainty",
        }

        base_pattern = patterns.get(nature, "Direct, concise response")

        # Add length guidance
        if nature in [QueryNature.OPINION, QueryNature.CONCERN]:
            length = length_guidance.get("opinion_questions", "2-4 sentences")
        elif nature in [QueryNature.DECISION, QueryNature.STRATEGIC]:
            length = length_guidance.get("complex_decisions", "5-10 sentences")
        else:
            length = length_guidance.get("simple_questions", "1-2 sentences")

        return f"{base_pattern} ({length})"

    def _generic_reasoning(
        self,
        query: str,
        classification: QueryClassification
    ) -> InferenceResult:
        """Provide generic reasoning when profile is not available."""
        return InferenceResult(
            reasoning_steps=["Considering the question carefully..."],
            applied_values=["thoughtfulness", "directness"],
            risk_assessment=None,
            red_flags_triggered=[],
            suggested_response_pattern="Direct, helpful response",
            confidence=0.5,
            should_escalate=False
        )

    def build_inference_prompt(
        self,
        query: str,
        profile_id: str,
        inference_result: InferenceResult,
        retrieval_context: Optional[List[Dict]] = None,
    ) -> Tuple[str, str]:
        """
        Build LLM prompts for inference-based response generation.

        This creates prompts that guide the LLM to respond using the
        executive's thinking framework rather than just retrieval.

        Returns (system_prompt, user_prompt) tuple.
        """
        profile = self._profile_loader.load_profile(profile_id)
        if not profile:
            return self._generic_prompt(query, inference_result)

        raw_data = profile.raw_profile_data
        name = profile.name or "Executive"
        first_name = name.split()[0]
        title = profile.title or "executive"

        # Get communication style
        comm_style = raw_data.get("communication_style", {})
        response_patterns = comm_style.get("response_patterns", {})

        # Get voiceprint for examples
        voiceprint = raw_data.get("voiceprint", {})

        # Get inference framework
        inference_framework = raw_data.get("inference_framework", {})
        opinion_formation = inference_framework.get("opinion_formation", {})
        source_attribution = inference_framework.get("source_attribution", {})

        # Build reasoning context
        reasoning_context = "\n".join([f"- {step}" for step in inference_result.reasoning_steps])
        values_context = ", ".join(inference_result.applied_values) if inference_result.applied_values else "general principles"

        # Build red flags warning if any
        red_flags_warning = ""
        if inference_result.red_flags_triggered:
            flags = ", ".join(inference_result.red_flags_triggered)
            red_flags_warning = f"\n\nWARNING: This query touches on sensitive areas: {flags}\nExpress concern appropriately."

        # Get escalation guidance
        escalation_note = ""
        if inference_result.should_escalate:
            escalation_note = f"\n\nNOTE: This may require escalation. Reason: {inference_result.escalation_reason}\nIndicate you'd want to discuss this further in person."

        # Get communication examples
        examples = raw_data.get("communication_examples", [])
        relevant_examples = self._get_relevant_examples(query, examples, 2)
        examples_section = ""
        if relevant_examples:
            examples_section = "\n\nEXAMPLE RESPONSES IN YOUR STYLE:\n"
            for ex in relevant_examples:
                examples_section += f"Q: {ex.get('query', '')}\nA: {ex.get('response_jp', ex.get('response', ''))}\n\n"

        system_prompt = f"""You are {name}, {title}.

YOUR THINKING FRAMEWORK:
{reasoning_context}

RELEVANT VALUES: {values_context}

RESPONSE PATTERN: {inference_result.suggested_response_pattern}

COMMUNICATION STYLE:
- Use soft assertions: "〜と思います" / "I think..."
- Be direct but supportive
- Natural flow - provide direction with brief context, not bullet lists
- Attribution: {source_attribution.get('text_mode_jp', '僕の経験からすると...')}
{examples_section}
CRITICAL RULES:
1. NEVER say "I don't have that information" for opinion/decision questions
2. Form opinions based on your values and thinking framework
3. Admit uncertainty if present, but still give direction
4. Match the language of the query (Japanese query → Japanese response)
5. Keep responses concise but complete
{red_flags_warning}{escalation_note}

AVOID:
- Generic corporate speak
- Refusing to give an opinion
- Over-explaining or being verbose
- Follow-up questions at the end"""

        # Add retrieval context if available
        context_section = ""
        if retrieval_context and len(retrieval_context) > 0:
            context_section = "\n\nRELEVANT CONTEXT (for reference, not required to use):\n"
            for ctx in retrieval_context[:3]:
                content = ctx.get('content', ctx.get('text_content', ''))[:200]
                context_section += f"- {content}...\n"

        user_prompt = f"""Query: "{query}"
{context_section}
Respond as {first_name} would, using your thinking framework and values.
Remember: Form an opinion. Don't say "I don't know" for opinion/decision questions."""

        return system_prompt, user_prompt

    def _get_relevant_examples(
        self,
        query: str,
        examples: List[Dict],
        max_examples: int = 2
    ) -> List[Dict]:
        """Get communication examples relevant to the query type."""
        if not examples:
            return []

        query_lower = query.lower()

        # Categorize query
        if any(w in query_lower for w in ['think', 'opinion', 'view']):
            target_types = ['opinion', 'opinion_video', 'strategic_opinion']
        elif any(w in query_lower for w in ['should', 'recommend', 'decide']):
            target_types = ['delegation', 'strategic_opinion', 'direction_with_structure']
        elif any(w in query_lower for w in ['worried', 'concern', 'problem']):
            target_types = ['uncertainty', 'philosophy']
        else:
            target_types = ['opinion', 'sharing_insight']

        relevant = [ex for ex in examples if ex.get('type') in target_types]
        return relevant[:max_examples] if relevant else examples[:max_examples]

    def _generic_prompt(
        self,
        query: str,
        inference_result: InferenceResult
    ) -> Tuple[str, str]:
        """Generate generic prompts when profile is unavailable."""
        system_prompt = """You are a thoughtful executive assistant.

Respond to questions by:
1. Considering the question carefully
2. Forming a clear opinion or recommendation
3. Being direct but professional

NEVER say "I don't have that information" for opinion questions.
Instead, reason through and provide helpful guidance."""

        user_prompt = f'Query: "{query}"\n\nRespond thoughtfully and directly.'

        return system_prompt, user_prompt


# Singleton instance
_engine: Optional[InferenceEngine] = None


def get_inference_engine() -> InferenceEngine:
    """Get the singleton InferenceEngine instance."""
    global _engine
    if _engine is None:
        _engine = InferenceEngine()
    return _engine
