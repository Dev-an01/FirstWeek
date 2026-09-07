"""
Query Type Classifier for Adaptive Retrieval Weighting

Classifies queries into 6 types to enable query-specific weight allocation:
1. factual_lookup - Simple fact retrieval
2. relationship - Entity relationships and connections
3. decision - Decision-making and recommendations
4. procedural - How-to and process questions
5. comparison - Comparing entities or options
6. conversational_context - Referring to past conversation
"""

import re
from typing import Dict, List, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueryClassification:
    """Result of query classification"""
    query_type: str
    confidence: float
    matching_patterns: List[str]
    fallback: bool
    description: str


class QueryTypeClassifier:
    """
    Classify queries into 6 types for adaptive weighting.

    Uses pattern-based matching for fast, accurate classification.
    Target accuracy: 87%+ on balanced test set.
    """

    QUERY_TYPES = {
        "factual_lookup": {
            "description": "Simple fact retrieval",
            "patterns": [
                r"^what is\b",
                r"^who is\b",
                r"^when (is|was|did)\b",
                r"^where (is|was)\b",
                r"\b(email|phone|address|title|name)\b"
            ],
            "examples": [
                "What is the CFO's email?",
                "Who is the current CTO?",
                "When did Project Pegasus start?"
            ]
        },

        "relationship": {
            "description": "Entity relationships and connections",
            "patterns": [
                r"\bconnect(s|ed|ion)?\b",
                r"\brelat(ed|ionship)\b",
                r"\bwork(ed)? with\b",
                r"\breport(s|ed)? to\b",
                r"^how (is|are) .* (related|connected)\b",
                r"\bpartner(s|ship)?\b",
                r"\bcollaborat(e|ed|ion)\b"
            ],
            "examples": [
                "Who worked with Tanaka on Project Pegasus?",
                "How are Acme Corp and Beta Corp related?",
                "What's the connection between X and Y?"
            ]
        },

        "decision": {
            "description": "Decision-making and recommendations",
            "patterns": [
                r"^should (we|I)\b",
                r"\b(recommend|suggest|advise)\b",
                r"\bapprove\b",
                r"^what (would|do) you (recommend|suggest)\b",
                r"\b(decision|choose|select)\b",
                r"^how would (you|I)\b",
                r"\bstrategy\b"
            ],
            "examples": [
                "Should we approve 15% discount?",
                "What do you recommend for Q4 strategy?",
                "How should we approach this?"
            ]
        },

        "procedural": {
            "description": "How-to and process questions",
            "patterns": [
                r"^how (do|does|can|to)\b",
                r"\bprocess\b",
                r"\bsteps?\b",
                r"\bprocedure\b",
                r"^what (is|are) the (process|steps)\b",
                r"\bworkflow\b",
                r"\bguidelines?\b"
            ],
            "examples": [
                "How do we submit expense reports?",
                "What's the process for approval?",
                "How can I access the system?"
            ]
        },

        "comparison": {
            "description": "Comparing entities or options",
            "patterns": [
                r"\bcompare\b",
                r"\b(difference|differ)\b",
                r"\bversus\b",
                r"\bvs\.?\b",
                r"^which (is|are) (better|best)\b",
                r"\balternative\b",
                r"\boption(s)?\b",
                r"\b(pros|cons)\b"
            ],
            "examples": [
                "Compare Acme Corp and Beta Corp",
                "What's the difference between Plan A and Plan B?",
                "Which option is better?"
            ]
        },

        "conversational_context": {
            "description": "Referring to past conversation",
            "patterns": [
                r"\b(yesterday|earlier|before|previously|last time)\b",
                r"^what did (we|I|you)\b",
                r"\bdiscuss(ed)?\b",
                r"\bmentioned\b",
                r"\btalked about\b",
                r"\bprevious conversation\b",
                r"\bas (we|I|you) (said|mentioned)\b"
            ],
            "examples": [
                "What did we discuss about discounts yesterday?",
                "As mentioned earlier...",
                "Following up on our previous conversation..."
            ]
        }
    }

    def __init__(self):
        """Initialize query type classifier"""
        logger.info("QueryTypeClassifier initialized with 6 query types")

    def classify(self, query: str) -> QueryClassification:
        """
        Classify query into one of 6 types using pattern matching.

        Args:
            query: User's natural language question

        Returns:
            QueryClassification with type, confidence, and metadata
        """
        query_lower = query.lower()

        scores = {}
        matched_patterns = {}

        # Score each type based on pattern matches
        for qtype, config in self.QUERY_TYPES.items():
            patterns = config["patterns"]
            matches = []

            for pattern in patterns:
                if re.search(pattern, query_lower):
                    matches.append(pattern)

            # Score = number of matches / total patterns
            # More matches = higher confidence
            score = len(matches) / len(patterns)

            if score > 0:
                scores[qtype] = score
                matched_patterns[qtype] = matches

        # Select best match
        if scores:
            best_type = max(scores, key=scores.get)
            confidence = scores[best_type]

            # Boost confidence if multiple patterns matched
            # (strong signal = high confidence)
            if len(matched_patterns[best_type]) > 1:
                confidence = min(confidence + 0.2, 1.0)

            # Also boost if this type scores significantly higher than others
            if len(scores) > 1:
                second_best_score = sorted(scores.values(), reverse=True)[1]
                if confidence > second_best_score * 1.5:
                    confidence = min(confidence + 0.1, 1.0)

            logger.debug(
                f"Query classified as '{best_type}' (confidence: {confidence:.2f}, "
                f"patterns matched: {len(matched_patterns[best_type])})"
            )

            return QueryClassification(
                query_type=best_type,
                confidence=confidence,
                matching_patterns=matched_patterns[best_type],
                fallback=False,
                description=self.QUERY_TYPES[best_type]["description"]
            )

        # Fallback: Default to "decision" (most common in executive context)
        logger.warning(
            f"No patterns matched for query: '{query[:50]}...' - falling back to 'decision'"
        )

        return QueryClassification(
            query_type="decision",
            confidence=0.5,
            matching_patterns=[],
            fallback=True,
            description=self.QUERY_TYPES["decision"]["description"]
        )

    def get_query_type_info(self, query_type: str) -> Dict[str, Any]:
        """
        Get information about a specific query type.

        Args:
            query_type: Type name (e.g., "factual_lookup")

        Returns:
            Type configuration dict
        """
        return self.QUERY_TYPES.get(query_type, {})

    def get_all_types(self) -> List[str]:
        """Get list of all supported query types"""
        return list(self.QUERY_TYPES.keys())

    def explain_classification(
        self,
        query: str,
        classification: QueryClassification
    ) -> str:
        """
        Generate human-readable explanation of classification.

        Args:
            query: Original query
            classification: Classification result

        Returns:
            Explanation string
        """
        explanation = []

        explanation.append(f"Query: '{query}'")
        explanation.append(f"Classified as: {classification.query_type}")
        explanation.append(f"Confidence: {classification.confidence:.0%}")
        explanation.append(f"Description: {classification.description}")

        if classification.fallback:
            explanation.append("⚠️ Fallback classification (no patterns matched)")
        else:
            explanation.append(f"Matched {len(classification.matching_patterns)} pattern(s):")
            for pattern in classification.matching_patterns:
                explanation.append(f"  - {pattern}")

        return "\n".join(explanation)


# Example usage
if __name__ == "__main__":
    # Test classifier
    logging.basicConfig(level=logging.DEBUG)

    classifier = QueryTypeClassifier()

    test_queries = [
        "What is the CFO's email address?",
        "Who worked with Tanaka on Project Pegasus?",
        "Should we approve a 15% discount?",
        "How do we submit expense reports?",
        "Compare Acme Corp and Beta Corp",
        "What did we discuss about discounts yesterday?",
        "What is Yuki's decision-making philosophy?",
        "Who reports to Sarah Kim?",
        "What is the process for hiring approval?"
    ]

    print("=" * 80)
    print("Query Type Classifier Test")
    print("=" * 80)

    for query in test_queries:
        classification = classifier.classify(query)
        print(f"\n{classifier.explain_classification(query, classification)}")
        print("-" * 80)
