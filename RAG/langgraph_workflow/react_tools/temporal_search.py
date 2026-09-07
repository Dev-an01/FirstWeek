"""
Temporal Context Search Tool

Searches episodic memory within specific time ranges.
Enables queries like "What did we discuss last week about discounts?"

Usage:
    result = temporal_context_search(
        params=TemporalSearchInput(query="discounts", time_range="last_week"),
        db_connection=postgres_connection
    )
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from .schemas import TemporalSearchInput, TemporalSearchOutput

logger = logging.getLogger(__name__)


def temporal_context_search(
    params: TemporalSearchInput,
    db_connection: Any,
    company_id: Optional[str] = None
) -> TemporalSearchOutput:
    """
    Search episodic memory within a specific time range.

    Supports:
    - Relative ranges: last_week, last_month, last_quarter, this_year
    - Quarterly: Q1, Q2, Q3, Q4 (current year by default)
    - Custom: YYYY-MM-DD:YYYY-MM-DD format

    Args:
        params: TemporalSearchInput with query, time_range, executive_id, top_k
        db_connection: PostgreSQL connection (psycopg2 or similar)

    Returns:
        TemporalSearchOutput with results and time range info

    Example:
        Query: "What did we discuss last week about discounts?"
        Result: Conversations about discounts from the past 7 days
    """
    try:
        logger.info(f"Temporal search: '{params.query}' in '{params.time_range}'")

        # Parse time range to start/end dates
        start_date, end_date = _parse_time_range(params.time_range)

        if not start_date or not end_date:
            return TemporalSearchOutput(
                success=False,
                error=f"Invalid time range: '{params.time_range}'. Use formats like 'last_week', 'Q1', or 'YYYY-MM-DD:YYYY-MM-DD'"
            )

        # Calculate days span
        days_span = (end_date - start_date).days

        logger.info(f"Time range resolved: {start_date.date()} to {end_date.date()} ({days_span} days)")

        # Execute search query
        results = _search_episodic_memory(
            db_connection=db_connection,
            query_text=params.query,
            start_date=start_date,
            end_date=end_date,
            executive_id=params.executive_id,
            company_id=company_id,
            top_k=params.top_k
        )

        logger.info(f"Found {len(results)} results in time range")

        return TemporalSearchOutput(
            success=True,
            results=results,
            time_range_resolved={
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": str(days_span),
                "original_input": params.time_range
            },
            count=len(results)
        )

    except Exception as e:
        logger.error(f"Temporal search error: {e}")
        return TemporalSearchOutput(
            success=False,
            error=str(e)
        )


def _parse_time_range(time_range: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse time range string to start/end datetime.

    Supported formats:
    - last_week, last_month, last_quarter, this_year
    - yesterday, today, last_N_days (e.g., last_30_days)
    - Q1, Q2, Q3, Q4 (current year), Q1_2024 (specific year)
    - YYYY-MM-DD:YYYY-MM-DD (custom range)

    Returns:
        Tuple of (start_datetime, end_datetime) or (None, None) if invalid
    """
    now = datetime.now()
    time_range_lower = time_range.lower().strip()

    # === Relative ranges ===
    if time_range_lower == "last_week":
        start = now - timedelta(days=7)
        return (start, now)

    if time_range_lower == "last_month":
        start = now - timedelta(days=30)
        return (start, now)

    if time_range_lower == "last_quarter":
        start = now - timedelta(days=90)
        return (start, now)

    if time_range_lower == "this_year":
        start = datetime(now.year, 1, 1)
        return (start, now)

    if time_range_lower == "yesterday":
        start = datetime(now.year, now.month, now.day) - timedelta(days=1)
        end = datetime(now.year, now.month, now.day)
        return (start, end)

    if time_range_lower == "today":
        start = datetime(now.year, now.month, now.day)
        return (start, now)

    # === last_N_days pattern ===
    last_n_match = re.match(r'last_(\d+)_days?', time_range_lower)
    if last_n_match:
        days = int(last_n_match.group(1))
        start = now - timedelta(days=days)
        return (start, now)

    # === Quarterly ranges ===
    quarter_match = re.match(r'q([1-4])(?:_(\d{4}))?', time_range_lower)
    if quarter_match:
        quarter = int(quarter_match.group(1))
        year = int(quarter_match.group(2)) if quarter_match.group(2) else now.year

        quarter_starts = {
            1: (1, 1),   # Jan 1
            2: (4, 1),   # Apr 1
            3: (7, 1),   # Jul 1
            4: (10, 1),  # Oct 1
        }
        quarter_ends = {
            1: (3, 31),  # Mar 31
            2: (6, 30),  # Jun 30
            3: (9, 30),  # Sep 30
            4: (12, 31), # Dec 31
        }

        start_month, start_day = quarter_starts[quarter]
        end_month, end_day = quarter_ends[quarter]

        start = datetime(year, start_month, start_day)
        end = datetime(year, end_month, end_day, 23, 59, 59)
        return (start, end)

    # === Custom date range: YYYY-MM-DD:YYYY-MM-DD ===
    custom_match = re.match(r'(\d{4}-\d{2}-\d{2}):(\d{4}-\d{2}-\d{2})', time_range)
    if custom_match:
        try:
            start = datetime.strptime(custom_match.group(1), '%Y-%m-%d')
            end = datetime.strptime(custom_match.group(2), '%Y-%m-%d')
            end = end.replace(hour=23, minute=59, second=59)
            return (start, end)
        except ValueError:
            return (None, None)

    # === Month names (e.g., "november", "nov_2024") ===
    month_names = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12,
    }

    month_match = re.match(r'(\w+)(?:_(\d{4}))?', time_range_lower)
    if month_match and month_match.group(1) in month_names:
        month = month_names[month_match.group(1)]
        year = int(month_match.group(2)) if month_match.group(2) else now.year

        start = datetime(year, month, 1)
        # Calculate last day of month
        if month == 12:
            end = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = datetime(year, month + 1, 1) - timedelta(days=1)
        end = end.replace(hour=23, minute=59, second=59)
        return (start, end)

    # Unknown format
    logger.warning(f"Unknown time range format: '{time_range}'")
    return (None, None)


def _search_episodic_memory(
    db_connection: Any,
    query_text: str,
    start_date: datetime,
    end_date: datetime,
    executive_id: Optional[str] = None,
    company_id: Optional[str] = None,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    Search episodic_memory table within time range.

    Uses text search (ILIKE) for keyword matching within the time range.
    Results are ordered by timestamp (most recent first).
    """
    results = []

    # Build SQL query with optional executive filter
    sql = """
        SELECT
            id,
            query,
            response,
            timestamp,
            executive_id,
            importance_score,
            context_sources
        FROM episodic_memory
        WHERE timestamp >= %s
          AND timestamp <= %s
          AND (query ILIKE %s OR response ILIKE %s)
    """
    params = [start_date, end_date, f'%{query_text}%', f'%{query_text}%']

    if company_id:
        sql += " AND company_id = %s"
        params.append(company_id)

    if executive_id:
        sql += " AND executive_id = %s"
        params.append(executive_id)

    sql += " ORDER BY timestamp DESC LIMIT %s"
    params.append(top_k)

    try:
        cursor = db_connection.cursor()
        cursor.execute(sql, params)

        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "query": row[1],
                "response": row[2][:500] if row[2] else "",  # Truncate long responses
                "timestamp": row[3].isoformat() if row[3] else None,
                "executive_id": row[4],
                "importance_score": float(row[5]) if row[5] else 0.0,
                "context_sources": row[6] or []
            })

        cursor.close()

    except Exception as e:
        logger.error(f"Database query error: {e}")
        raise

    return results


def format_for_observation(result: TemporalSearchOutput) -> str:
    """
    Format the temporal search result for ReAct observation.

    Returns a concise string suitable for the ReAct loop.
    """
    if not result.success:
        return f"Temporal search failed: {result.error}"

    if result.count == 0:
        time_info = result.time_range_resolved
        return (
            f"No conversations found matching query in the specified time range "
            f"({time_info.get('start', 'unknown')} to {time_info.get('end', 'unknown')}, "
            f"{time_info.get('days', '?')} days). "
            f"Try a broader time range or different search terms."
        )

    lines = []
    time_info = result.time_range_resolved
    lines.append(
        f"Found {result.count} conversation(s) from {time_info.get('original_input', 'specified period')} "
        f"({time_info.get('days', '?')} days):"
    )

    for i, item in enumerate(result.results[:5], 1):
        timestamp = item.get("timestamp", "unknown")[:10]  # Just date part
        query = item.get("query", "")[:80]
        importance = item.get("importance_score", 0)

        lines.append(f"\n{i}. [{timestamp}] {query}...")

        # Add brief response excerpt
        response = item.get("response", "")[:150]
        if response:
            lines.append(f"   Response: {response}...")

    if result.count > 5:
        lines.append(f"\n... and {result.count - 5} more results")

    return "\n".join(lines)


def parse_time_range_from_query(query: str) -> Optional[str]:
    """
    Extract time range indicators from natural language query.

    Examples:
    - "what did we discuss last week" -> "last_week"
    - "decisions from Q3" -> "Q3"
    - "conversations in November" -> "november"
    - "yesterday's meetings" -> "yesterday"

    Returns:
        Time range string or None if not detected
    """
    query_lower = query.lower()

    # Direct matches
    time_patterns = [
        (r'\blast\s*week\b', 'last_week'),
        (r'\blast\s*month\b', 'last_month'),
        (r'\blast\s*quarter\b', 'last_quarter'),
        (r'\bthis\s*year\b', 'this_year'),
        (r'\byesterday\b', 'yesterday'),
        (r'\btoday\b', 'today'),
        (r'\blast\s*(\d+)\s*days?\b', lambda m: f'last_{m.group(1)}_days'),
        (r'\bq([1-4])\b', lambda m: f'Q{m.group(1)}'),
        (r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
         lambda m: m.group(1)),
        (r'\b(jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\b',
         lambda m: m.group(1)),
    ]

    for pattern, result in time_patterns:
        match = re.search(pattern, query_lower)
        if match:
            if callable(result):
                return result(match)
            return result

    return None
