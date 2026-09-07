"""
Theme Classifier - Classifies queries into business themes.

Uses keyword/pattern matching for fast, deterministic classification.
Target latency: 1-2ms.
"""

import re
import logging
from typing import Tuple, List, Dict, Any

from ..models import Theme

logger = logging.getLogger(__name__)


class ThemeClassifier:
    """
    Classify query into business theme.

    Themes:
    - security: Security incidents, compliance, audits, breaches
    - budget: Financial decisions, costs, ROI, pricing
    - people: HR, team issues, performance, hiring, culture
    - strategy: Business strategy, market positioning, competition
    - technical: Architecture, technology decisions, systems
    - operations: Day-to-day operations, processes, logistics
    - customer: Customer issues, feedback, relationships
    - other: Catch-all for unclassified queries

    Thread-safe: No mutable state, can be shared across requests.
    """

    # Pattern dictionaries for each theme
    # Patterns are compiled on first use for performance
    THEME_PATTERNS: Dict[str, List[str]] = {
        "security": [
            r"\b(security|secure|breach|hack|hacked|incident)\b",
            r"\b(compliance|audit|auditing|vulnerability|attack)\b",
            r"\b(SOC2|GDPR|HIPAA|PCI|ISO\s*27001)\b",
            r"\b(penetration\s*test|pentest|security\s*review)\b",
            r"\b(password|authentication|auth|access\s*control)\b",
            r"\b(firewall|encryption|encrypted|malware|phishing)\b",
            r"\b(data\s*protection|privacy|confidential)\b",
        ],
        "budget": [
            r"\b(budget|budgeting|cost|costs|expense|expenses)\b",
            r"\b(revenue|profit|margin|ROI|return\s*on\s*investment)\b",
            r"\b(pricing|price|discount|discounts)\b",
            r"\b(financial|financials|forecast|forecasting)\b",
            r"\b(burn\s*rate|runway|valuation|funding)\b",
            r"\b(approve|approval).{0,20}(spend|purchase|investment|budget)\b",
            r"\b(invoice|billing|payment|accounts)\b",
            r"\b(quarterly|Q[1-4]|fiscal)\b",
        ],
        "people": [
            r"\b(hire|hiring|recruit|recruiting|candidate|interview)\b",
            r"\b(offer|onboard|onboarding|new\s*hire)\b",
            r"\b(performance|review|feedback|1:1|one-on-one|career)\b",
            r"\b(promotion|promoted|raise|compensation|salary)\b",
            r"\b(team|morale|culture|engagement|retention)\b",
            r"\b(attrition|turnover|resign|resignation|quit)\b",
            r"\b(HR|human\s*resources|PTO|leave|vacation)\b",
            r"\b(training|development|mentoring|coaching)\b",
            r"\b(layoff|layoffs|restructur|reorg)\b",
        ],
        "strategy": [
            r"\b(strategy|strategic|roadmap|vision|mission)\b",
            r"\b(market|markets|competition|competitor|competitors)\b",
            r"\b(positioning|differentiat|competitive\s*advantage)\b",
            r"\b(growth|expansion|scale|scaling)\b",
            r"\b(acquisition|acquire|merger|M&A|partnership)\b",
            r"\b(pivot|direction|priorities|priority)\b",
            r"\b(OKRs?|objectives|goals|KPIs?)\b",
            r"\b(long-term|long\s*term|5-year|three-year)\b",
        ],
        "technical": [
            r"\b(architecture|infrastructure|system|systems|platform)\b",
            r"\b(API|APIs|database|databases|server|servers)\b",
            r"\b(cloud|AWS|Azure|GCP|kubernetes|docker)\b",
            r"\b(code|coding|deploy|deployment|release)\b",
            r"\b(bug|bugs|feature|features|sprint|sprints)\b",
            r"\b(tech\s*debt|refactor|refactoring|migration)\b",
            r"\b(integration|integrations|microservice|monolith)\b",
            r"\b(latency|performance|scalability|reliability)\b",
            r"\b(frontend|backend|full-stack|devops)\b",
        ],
        "operations": [
            r"\b(process|processes|workflow|workflows|SOP)\b",
            r"\b(procedure|procedures|protocol|protocols)\b",
            r"\b(logistics|supply\s*chain|inventory|shipping)\b",
            r"\b(vendor|vendors|supplier|suppliers|procurement)\b",
            r"\b(contract|contracts|agreement|agreements)\b",
            r"\b(schedule|scheduling|timeline|timelines)\b",
            r"\b(deadline|deadlines|milestone|milestones)\b",
            r"\b(capacity|resource\s*allocation|workload)\b",
        ],
        "customer": [
            r"\b(customer|customers|client|clients|user|users)\b",
            r"\b(account|accounts|enterprise|deal|deals)\b",
            r"\b(NPS|CSAT|satisfaction|feedback|complaint)\b",
            r"\b(churn|churning|retention|renew|renewal)\b",
            r"\b(upsell|cross-sell|expansion|ARR|MRR)\b",
            r"\b(support|ticket|tickets|escalation|SLA)\b",
            r"\b(success|CSM|customer\s*success)\b",
            r"\b(demo|trial|POC|proof\s*of\s*concept)\b",
        ],
    }

    # Entity keywords that suggest specific themes
    ENTITY_THEME_HINTS: Dict[str, str] = {
        # Company/client names often indicate customer theme
        "corp": "customer",
        "inc": "customer",
        "ltd": "customer",
        "llc": "customer",
    }

    def __init__(self):
        """Initialize ThemeClassifier with compiled patterns."""
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()
        logger.debug("ThemeClassifier initialized with 8 themes")

    def _compile_patterns(self) -> None:
        """Compile all patterns for performance."""
        for theme, patterns in self.THEME_PATTERNS.items():
            self._compiled_patterns[theme] = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in patterns
            ]

    def classify(
        self,
        query: str,
        entities: List[str] = None,
    ) -> Tuple[Theme, float]:
        """
        Classify query into a business theme.

        Args:
            query: User's query text
            entities: Optional list of detected entities (e.g., company names)

        Returns:
            Tuple of (Theme, confidence)
            - Theme: Classified theme enum
            - confidence: 0.0 to 1.0
        """
        entities = entities or []
        query_lower = query.lower()

        scores: Dict[str, float] = {}
        matched_patterns: Dict[str, List[str]] = {}

        # Score each theme based on pattern matches
        for theme, patterns in self._compiled_patterns.items():
            matches = []
            for pattern in patterns:
                if pattern.search(query_lower):
                    matches.append(pattern.pattern)

            if matches:
                # Base score: proportion of patterns matched
                base_score = len(matches) / len(patterns)

                # Boost for multiple matches (stronger signal)
                if len(matches) >= 2:
                    base_score = min(base_score + 0.15, 1.0)
                if len(matches) >= 3:
                    base_score = min(base_score + 0.10, 1.0)

                scores[theme] = base_score
                matched_patterns[theme] = matches

        # Apply entity hints
        for entity in entities:
            entity_lower = entity.lower()
            for hint_keyword, hinted_theme in self.ENTITY_THEME_HINTS.items():
                if hint_keyword in entity_lower:
                    # Boost the hinted theme
                    current_score = scores.get(hinted_theme, 0.0)
                    scores[hinted_theme] = min(current_score + 0.2, 1.0)
                    break

        # Select best match
        if scores:
            best_theme = max(scores, key=scores.get)
            confidence = scores[best_theme]

            # Boost confidence if this theme scores significantly higher
            if len(scores) > 1:
                sorted_scores = sorted(scores.values(), reverse=True)
                if sorted_scores[0] > sorted_scores[1] * 1.5:
                    confidence = min(confidence + 0.1, 1.0)

            logger.debug(
                f"Theme classified as '{best_theme}' "
                f"(confidence: {confidence:.2f}, "
                f"patterns: {len(matched_patterns.get(best_theme, []))})"
            )

            return Theme(best_theme), confidence

        # No patterns matched - return OTHER
        logger.debug(f"No theme patterns matched, returning OTHER")
        return Theme.OTHER, 0.5

    def get_theme_keywords(self, theme: Theme) -> List[str]:
        """
        Get keywords associated with a theme.

        Useful for debugging and explanation.
        """
        patterns = self.THEME_PATTERNS.get(theme.value, [])
        # Extract readable keywords from patterns
        keywords = []
        for pattern in patterns:
            # Simple extraction: remove regex syntax
            clean = re.sub(r'\\b|\(|\)|\||\?|\\s\*|\[.*?\]|\{.*?\}', ' ', pattern)
            keywords.extend(clean.split())
        return list(set(keywords))


# Singleton instance for stateless use
_default_classifier: ThemeClassifier = None


def get_theme_classifier() -> ThemeClassifier:
    """Get singleton ThemeClassifier instance."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = ThemeClassifier()
    return _default_classifier
