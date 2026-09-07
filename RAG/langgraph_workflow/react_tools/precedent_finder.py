"""
Precedent Finder Tool

Finds similar past decisions using semantic similarity search.
Enables queries like "Have we approved discounts like this before?"

Usage:
    result = find_precedents(
        params=PrecedentFinderInput(scenario="15% discount for strategic client"),
        db_connection=postgres_connection,
        embedding_model=model
    )
"""

import logging
from typing import Dict, Any, List, Optional

from .schemas import PrecedentFinderInput, PrecedentFinderOutput

logger = logging.getLogger(__name__)


def find_precedents(
    params: PrecedentFinderInput,
    db_connection: Any,
    embedding_model: Any,
    company_id: Optional[str] = None
) -> PrecedentFinderOutput:
    """
    Find similar past decisions using semantic similarity.

    Uses pgvector to search the embeddings.decision_cases table
    and joins with public.decision_cases for full details.

    Args:
        params: PrecedentFinderInput with scenario, decision_type, threshold, top_k
        db_connection: PostgreSQL connection
        embedding_model: Model with generate_embedding() method

    Returns:
        PrecedentFinderOutput with matching precedents

    Example:
        Query: "15% discount for strategic A-tier client"
        Result: Similar past discount decisions with outcomes
    """
    try:
        logger.info(f"Finding precedents for: '{params.scenario[:50]}...'")

        # Generate embedding for the scenario
        scenario_embedding = embedding_model.generate_embedding(params.scenario)

        # Convert numpy array to list for PostgreSQL
        if hasattr(scenario_embedding, 'tolist'):
            embedding_list = scenario_embedding.tolist()
        else:
            embedding_list = list(scenario_embedding)

        # Search for similar decisions
        precedents = _search_similar_decisions(
            db_connection=db_connection,
            query_embedding=embedding_list,
            decision_type=params.decision_type,
            similarity_threshold=params.similarity_threshold,
            executive_id=None,  # Search across all executives within same company
            company_id=company_id,
            top_k=params.top_k,
            include_outcomes=params.include_outcomes
        )

        # Calculate average similarity
        avg_similarity = 0.0
        if precedents:
            avg_similarity = sum(p.get("similarity", 0) for p in precedents) / len(precedents)

        logger.info(f"Found {len(precedents)} precedents (avg similarity: {avg_similarity:.2f})")

        return PrecedentFinderOutput(
            success=True,
            precedents=precedents,
            count=len(precedents),
            avg_similarity=round(avg_similarity, 3)
        )

    except Exception as e:
        logger.error(f"Precedent search error: {e}")
        return PrecedentFinderOutput(
            success=False,
            error=str(e)
        )


def _search_similar_decisions(
    db_connection: Any,
    query_embedding: List[float],
    decision_type: Optional[str] = None,
    similarity_threshold: float = 0.70,
    executive_id: Optional[str] = None,
    company_id: Optional[str] = None,
    top_k: int = 5,
    include_outcomes: bool = True
) -> List[Dict[str, Any]]:
    """
    Search for similar decisions using pgvector cosine similarity.

    Queries embeddings.decision_cases and joins with public.decision_cases
    for full decision details.
    """
    results = []

    # Build the SQL query
    # Note: pgvector uses <=> for cosine distance (1 - similarity)
    # So similarity = 1 - (embedding <=> query_embedding)
    sql = """
        SELECT
            e.id,
            e.decision_id,
            e.executive_id,
            e.title,
            e.content,
            1 - (e.embedding <=> %s::vector) AS similarity,
            p.category,
            p.situation,
            p.decision_made,
            p.outcome,
            p.rationale,
            p.lessons_learned,
            p.date,
            p.confidence
        FROM embeddings.decision_cases e
        LEFT JOIN public.decision_cases p ON e.id = p.id
        WHERE 1 - (e.embedding <=> %s::vector) >= %s
    """

    params = [query_embedding, query_embedding, similarity_threshold]

    # Optional filters
    if decision_type:
        sql += " AND p.category = %s"
        params.append(decision_type)

    if company_id:
        sql += " AND e.company_id = %s"
        params.append(company_id)

    if executive_id:
        sql += " AND e.executive_id = %s"
        params.append(executive_id)

    sql += " ORDER BY similarity DESC LIMIT %s"
    params.append(top_k)

    try:
        cursor = db_connection.cursor()
        cursor.execute(sql, params)

        for row in cursor.fetchall():
            precedent = {
                "case_id": row[0],
                "decision_id": row[1],
                "executive_id": row[2],
                "title": row[3] or "Untitled Decision",
                "scenario": _truncate(row[4], 300) if row[4] else "",  # content
                "similarity": round(float(row[5]), 3) if row[5] else 0.0,
                "category": row[6],
                "date": row[12].isoformat() if row[12] else None,
            }

            if include_outcomes:
                precedent.update({
                    "situation": _truncate(row[7], 200) if row[7] else "",
                    "decision": _truncate(row[8], 200) if row[8] else "",
                    "outcome": _truncate(row[9], 200) if row[9] else "",
                    "rationale": _truncate(row[10], 200) if row[10] else "",
                    "lessons_learned": _truncate(row[11], 200) if row[11] else "",
                    "confidence": float(row[13]) if row[13] else None
                })

            results.append(precedent)

        cursor.close()

    except Exception as e:
        logger.error(f"Database query error: {e}")
        raise

    return results


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to max length with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_for_observation(result: PrecedentFinderOutput) -> str:
    """
    Format the precedent search result for ReAct observation.

    Returns a concise string suitable for the ReAct loop.
    """
    if not result.success:
        return f"Precedent search failed: {result.error}"

    if result.count == 0:
        return (
            "No similar precedents found above the similarity threshold. "
            "This may be a novel situation without historical precedent. "
            "Consider using SEARCH to find related policies or guidelines."
        )

    lines = [
        f"Found {result.count} similar precedent(s) (avg similarity: {result.avg_similarity:.0%}):"
    ]

    for i, p in enumerate(result.precedents[:5], 1):
        similarity_pct = p.get("similarity", 0) * 100
        lines.append(f"\n{i}. [{p.get('case_id', 'unknown')}] ({similarity_pct:.0f}% similar)")
        lines.append(f"   Category: {p.get('category', 'N/A')}")

        if p.get("title") and p["title"] != "Untitled Decision":
            lines.append(f"   Title: {p['title'][:60]}...")

        if p.get("decision"):
            lines.append(f"   Decision: {p['decision'][:80]}...")

        if p.get("outcome"):
            outcome = p["outcome"][:60]
            lines.append(f"   Outcome: {outcome}...")

    if result.count > 5:
        lines.append(f"\n... and {result.count - 5} more precedents")

    return "\n".join(lines)


def extract_decision_type_from_query(query: str) -> Optional[str]:
    """
    Extract decision type/category from a natural language query.

    Examples:
    - "have we approved discounts before" -> "pricing"
    - "past hiring decisions" -> "personnel"
    - "investment precedents" -> "investment"

    Returns:
        Category string or None if not detected
    """
    query_lower = query.lower()

    # Map keywords to decision categories
    category_keywords = {
        "pricing_strategy": ["discount", "pricing", "price", "rate", "fee", "cost"],
        "pricing_negotiation": ["negotiate", "negotiation", "deal", "contract"],
        "product_investment": ["investment", "invest", "funding", "budget", "spend"],
        "personnel": ["hiring", "hire", "fire", "termination", "promotion", "personnel", "employee"],
        "personnel_crisis": ["crisis", "emergency", "urgent personnel"],
        "market_expansion": ["expansion", "new market", "growth", "scale"],
        "crisis_management": ["crisis", "emergency", "incident", "outage"],
        "technical": ["technical", "architecture", "infrastructure", "migration"],
    }

    for category, keywords in category_keywords.items():
        if any(kw in query_lower for kw in keywords):
            return category

    return None
