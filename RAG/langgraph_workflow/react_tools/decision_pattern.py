"""
Decision Pattern Analyzer Tool

Analyzes an executive's decision-making patterns based on historical decisions.
Enables queries like "How does this executive typically approach pricing decisions?"

Usage:
    result = analyze_decision_pattern(
        params=DecisionPatternInput(executive_id="exec_001_test"),
        db_connection=postgres_connection
    )
"""

import logging
import re
from typing import Dict, Any, List, Optional
from collections import Counter

from .schemas import DecisionPatternInput, DecisionPatternOutput

logger = logging.getLogger(__name__)


def analyze_decision_pattern(
    params: DecisionPatternInput,
    db_connection: Any,
    profile_manager: Optional[Any] = None,
    company_id: Optional[str] = None
) -> DecisionPatternOutput:
    """
    Analyze an executive's decision-making patterns.

    Combines:
    - Historical decisions from decision_cases table
    - Profile data (if available) for additional context
    - Pattern extraction from rationales and outcomes

    Args:
        params: DecisionPatternInput with executive_id, decision_domain, include_examples
        db_connection: PostgreSQL connection
        profile_manager: Optional ProfileManager for enrichment

    Returns:
        DecisionPatternOutput with patterns, distributions, and statistics

    Example:
        Query: "How does exec_001_test approach pricing decisions?"
        Result: Patterns around risk tolerance, key factors considered, success rate
    """
    try:
        logger.info(f"Analyzing decision patterns for: {params.executive_id}")

        # Fetch historical decisions
        decisions = _fetch_executive_decisions(
            db_connection=db_connection,
            executive_id=params.executive_id,
            decision_domain=params.decision_domain,
            company_id=company_id
        )

        if not decisions:
            return DecisionPatternOutput(
                success=True,
                executive_id=params.executive_id,
                patterns={"note": "No historical decisions found for this executive"},
                total_decisions_analyzed=0
            )

        # Analyze decision distribution by category
        decision_distribution = _analyze_category_distribution(decisions)

        # Analyze outcome statistics
        outcome_stats = _analyze_outcomes(decisions)

        # Extract decision-making patterns
        patterns = _extract_patterns(decisions)

        # Get profile-based patterns if available
        if profile_manager:
            profile_patterns = _get_profile_patterns(profile_manager, params.executive_id)
            if profile_patterns:
                patterns["profile_based"] = profile_patterns

        # Get example decisions if requested
        examples = []
        if params.include_examples:
            examples = _get_example_decisions(decisions, top_k=3)

        logger.info(
            f"Pattern analysis complete: {len(decisions)} decisions, "
            f"{len(decision_distribution)} categories"
        )

        return DecisionPatternOutput(
            success=True,
            executive_id=params.executive_id,
            patterns=patterns,
            decision_distribution=decision_distribution,
            outcome_stats=outcome_stats,
            examples=examples,
            total_decisions_analyzed=len(decisions)
        )

    except Exception as e:
        logger.error(f"Decision pattern analysis error: {e}")
        return DecisionPatternOutput(
            success=False,
            executive_id=params.executive_id,
            error=str(e)
        )


def _fetch_executive_decisions(
    db_connection: Any,
    executive_id: str,
    decision_domain: Optional[str] = None,
    company_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch all decisions for an executive from the database.
    """
    sql = """
        SELECT
            id,
            title,
            date,
            category,
            situation,
            decision_made,
            rationale,
            outcome,
            lessons_learned,
            confidence
        FROM public.decision_cases
        WHERE executive_id = %s
    """
    params = [executive_id]

    if company_id:
        sql += " AND company_id = %s"
        params.append(company_id)

    if decision_domain:
        sql += " AND category ILIKE %s"
        params.append(f"%{decision_domain}%")

    sql += " ORDER BY date DESC"

    decisions = []
    try:
        cursor = db_connection.cursor()
        cursor.execute(sql, params)

        for row in cursor.fetchall():
            decisions.append({
                "id": row[0],
                "title": row[1],
                "date": row[2].isoformat() if row[2] else None,
                "category": row[3],
                "situation": row[4],
                "decision": row[5],
                "rationale": row[6],
                "outcome": row[7],
                "lessons_learned": row[8],
                "confidence": float(row[9]) if row[9] else None
            })

        cursor.close()

    except Exception as e:
        logger.error(f"Error fetching decisions: {e}")
        raise

    return decisions


def _analyze_category_distribution(decisions: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Count decisions by category.
    """
    categories = [d.get("category", "unknown") for d in decisions]
    return dict(Counter(categories))


def _analyze_outcomes(decisions: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Analyze outcome patterns (positive, negative, neutral).
    """
    outcome_counts = {"positive": 0, "negative": 0, "neutral": 0}

    positive_keywords = ["success", "better", "exceeded", "improved", "excellent", "achieved"]
    negative_keywords = ["fail", "worse", "missed", "lost", "problem", "issue", "negative"]

    for d in decisions:
        outcome = (d.get("outcome") or "").lower()

        if any(kw in outcome for kw in positive_keywords):
            outcome_counts["positive"] += 1
        elif any(kw in outcome for kw in negative_keywords):
            outcome_counts["negative"] += 1
        else:
            outcome_counts["neutral"] += 1

    return outcome_counts


def _extract_patterns(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract decision-making patterns from historical decisions.

    Analyzes:
    - Risk tolerance based on decision descriptions
    - Key factors mentioned in rationales
    - Common themes across decisions
    """
    patterns = {}

    # Collect all rationales and decisions for analysis
    all_rationales = " ".join([d.get("rationale", "") or "" for d in decisions])
    all_decisions = " ".join([d.get("decision", "") or "" for d in decisions])
    all_text = (all_rationales + " " + all_decisions).lower()

    # --- Risk Tolerance Analysis ---
    risk_indicators = {
        "conservative": ["cautious", "conservative", "safe", "low risk", "minimize risk", "careful"],
        "moderate": ["balanced", "measured", "considered", "reasonable", "pragmatic"],
        "aggressive": ["bold", "aggressive", "ambitious", "high risk", "disruptive", "innovative"]
    }

    risk_scores = {}
    for risk_level, keywords in risk_indicators.items():
        score = sum(1 for kw in keywords if kw in all_text)
        risk_scores[risk_level] = score

    max_risk = max(risk_scores.values()) if risk_scores.values() else 0
    if max_risk > 0:
        dominant_risk = [k for k, v in risk_scores.items() if v == max_risk]
        patterns["risk_tolerance"] = dominant_risk[0] if len(dominant_risk) == 1 else "moderate"
    else:
        patterns["risk_tolerance"] = "moderate"  # Default

    # --- Key Decision Factors ---
    factor_keywords = {
        "data_driven": ["data", "metrics", "analysis", "evidence", "numbers", "quantitative"],
        "relationship_focused": ["relationship", "partnership", "trust", "collaborate", "team"],
        "cost_conscious": ["cost", "budget", "roi", "investment", "savings", "efficiency"],
        "customer_centric": ["customer", "client", "user", "satisfaction", "experience"],
        "innovation_focused": ["innovation", "new", "creative", "novel", "disruption"],
        "quality_focused": ["quality", "excellence", "standard", "best practice"]
    }

    key_factors = []
    for factor, keywords in factor_keywords.items():
        if any(kw in all_text for kw in keywords):
            key_factors.append(factor)

    patterns["key_factors"] = key_factors if key_factors else ["balanced_approach"]

    # --- Decision Speed ---
    speed_indicators = {
        "quick": ["immediate", "quickly", "fast", "urgent", "asap", "rapid"],
        "deliberate": ["careful", "thorough", "consider", "evaluate", "analyze", "review"]
    }

    speed_scores = {}
    for speed, keywords in speed_indicators.items():
        speed_scores[speed] = sum(1 for kw in keywords if kw in all_text)

    if speed_scores.get("quick", 0) > speed_scores.get("deliberate", 0):
        patterns["decision_speed"] = "quick_decisive"
    elif speed_scores.get("deliberate", 0) > speed_scores.get("quick", 0):
        patterns["decision_speed"] = "methodical"
    else:
        patterns["decision_speed"] = "context_dependent"

    # --- Success Rate ---
    total = len(decisions)
    if total > 0:
        # Count positive outcomes
        positive_outcomes = sum(1 for d in decisions
            if any(kw in (d.get("outcome") or "").lower()
                   for kw in ["success", "better", "exceeded", "improved"]))
        patterns["success_rate"] = f"{(positive_outcomes / total) * 100:.0f}%"
    else:
        patterns["success_rate"] = "N/A"

    # --- Common Themes ---
    themes = []
    theme_patterns = {
        "stakeholder_alignment": r"stakeholder|align|consensus|buy-in",
        "long_term_thinking": r"long.term|strategic|future|sustainable",
        "transparency": r"transparent|honest|open|clear communication",
        "accountability": r"accountable|responsible|ownership|commit"
    }

    for theme, pattern in theme_patterns.items():
        if re.search(pattern, all_text):
            themes.append(theme)

    patterns["common_themes"] = themes if themes else ["pragmatic_results"]

    return patterns


def _get_profile_patterns(profile_manager: Any, executive_id: str) -> Optional[Dict[str, Any]]:
    """
    Extract decision-related patterns from executive profile.
    """
    try:
        profile = profile_manager.get_profile(executive_id)
        if not profile:
            return None

        profile_patterns = {}

        # Extract relevant fields
        if "decision_making" in profile:
            profile_patterns["stated_approach"] = profile["decision_making"]

        if "risk_tolerance" in profile:
            profile_patterns["stated_risk_tolerance"] = profile["risk_tolerance"]

        if "values" in profile:
            profile_patterns["core_values"] = profile["values"]

        return profile_patterns if profile_patterns else None

    except Exception as e:
        logger.warning(f"Could not load profile patterns: {e}")
        return None


def _get_example_decisions(
    decisions: List[Dict[str, Any]],
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """
    Get representative example decisions.

    Selects diverse examples across different categories.
    """
    examples = []
    seen_categories = set()

    # First, get one example from each unique category
    for d in decisions:
        category = d.get("category", "unknown")
        if category not in seen_categories and len(examples) < top_k:
            examples.append({
                "id": d["id"],
                "category": category,
                "situation": _truncate(d.get("situation", ""), 150),
                "decision": _truncate(d.get("decision", ""), 150),
                "outcome": _truncate(d.get("outcome", ""), 100),
                "date": d.get("date")
            })
            seen_categories.add(category)

    # If we need more, add from the beginning
    for d in decisions:
        if len(examples) >= top_k:
            break
        if d["id"] not in [e["id"] for e in examples]:
            examples.append({
                "id": d["id"],
                "category": d.get("category", "unknown"),
                "situation": _truncate(d.get("situation", ""), 150),
                "decision": _truncate(d.get("decision", ""), 150),
                "outcome": _truncate(d.get("outcome", ""), 100),
                "date": d.get("date")
            })

    return examples[:top_k]


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to max length with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_for_observation(result: DecisionPatternOutput) -> str:
    """
    Format the decision pattern analysis for ReAct observation.

    Returns a concise string suitable for the ReAct loop.
    """
    if not result.success:
        return f"Decision pattern analysis failed: {result.error}"

    if result.total_decisions_analyzed == 0:
        return (
            f"No historical decisions found for {result.executive_id}. "
            f"Unable to analyze decision-making patterns. "
            f"Try using SEARCH to find relevant context."
        )

    lines = [
        f"Decision Pattern Analysis for {result.executive_id}:",
        f"Based on {result.total_decisions_analyzed} historical decision(s):"
    ]

    # Patterns
    if result.patterns:
        lines.append("\nKey Patterns:")
        if "risk_tolerance" in result.patterns:
            lines.append(f"  - Risk Tolerance: {result.patterns['risk_tolerance']}")
        if "decision_speed" in result.patterns:
            lines.append(f"  - Decision Style: {result.patterns['decision_speed']}")
        if "success_rate" in result.patterns:
            lines.append(f"  - Success Rate: {result.patterns['success_rate']}")
        if "key_factors" in result.patterns:
            factors = ", ".join(result.patterns["key_factors"][:3])
            lines.append(f"  - Key Factors: {factors}")

    # Decision Distribution
    if result.decision_distribution:
        lines.append("\nDecision Categories:")
        for category, count in sorted(result.decision_distribution.items(),
                                      key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"  - {category}: {count}")

    # Outcome Stats
    if result.outcome_stats:
        total = sum(result.outcome_stats.values())
        if total > 0:
            positive = result.outcome_stats.get("positive", 0)
            lines.append(f"\nOutcome Track Record: {positive}/{total} positive outcomes")

    # Examples
    if result.examples:
        lines.append("\nRepresentative Decisions:")
        for i, ex in enumerate(result.examples[:2], 1):
            lines.append(f"  {i}. [{ex['category']}] {ex['decision'][:60]}...")

    return "\n".join(lines)


def extract_domain_from_query(query: str) -> Optional[str]:
    """
    Extract decision domain from a natural language query.

    Examples:
    - "How does Yuki approach pricing decisions" -> "pricing"
    - "What is their hiring pattern" -> "personnel"
    - "technical decision style" -> "technical"

    Returns:
        Domain string or None if not detected
    """
    query_lower = query.lower()

    domain_keywords = {
        "pricing": ["pricing", "discount", "price", "rate", "fee", "deal"],
        "personnel": ["hiring", "firing", "promotion", "team", "personnel", "employee", "staff"],
        "technical": ["technical", "architecture", "infrastructure", "engineering", "code"],
        "investment": ["investment", "budget", "funding", "spend", "allocation"],
        "crisis": ["crisis", "emergency", "incident", "outage", "problem"],
        "marketing": ["marketing", "campaign", "brand", "content", "promotion"],
        "strategy": ["strategy", "strategic", "planning", "growth", "expansion"]
    }

    for domain, keywords in domain_keywords.items():
        if any(kw in query_lower for kw in keywords):
            return domain

    return None
