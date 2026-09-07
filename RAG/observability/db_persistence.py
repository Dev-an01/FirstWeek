"""
Database Persistence for Observability
=======================================

Stores quality metrics, user feedback, and business metrics in PostgreSQL.

Usage:
    from observability.db_persistence import store_quality_metrics, store_user_feedback

    store_quality_metrics(
        request_id="req_123",
        executive_id="exec_001",
        quality_metrics={...}
    )
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional
import os
from contextlib import contextmanager
from datetime import date

from .logging import StructuredLogger

logger = StructuredLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'database': os.getenv('POSTGRES_DB', 'ai_officer_dev'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}


@contextmanager
def get_db_connection():
    """Get database connection context manager"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Database connection error", error=str(e))
        raise
    finally:
        if conn:
            conn.close()


def store_quality_metrics(
    request_id: str,
    executive_id: str,
    user_id: Optional[str],
    query_text: str,
    response_text: str,
    quality_metrics: Dict[str, Any],
    path: str,
    model: str,
    sources_count: int
) -> bool:
    """
    Store quality metrics in database.

    Args:
        request_id: Unique request identifier
        executive_id: Executive profile ID
        user_id: User ID (optional)
        query_text: Original query
        response_text: Generated response
        quality_metrics: Dictionary with quality scores
        path: Query path (fast/standard/agentic)
        model: LLM model used
        sources_count: Number of sources provided

    Returns:
        True if stored successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO quality_metrics (
                    request_id,
                    executive_id,
                    user_id,
                    query_text,
                    response_text,
                    citation_coverage,
                    factual_grounding_rate,
                    total_claims,
                    grounded_claims,
                    decision_fidelity_score,
                    model,
                    path,
                    sources_count,
                    citations_count
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                request_id,
                executive_id,
                user_id,
                query_text,
                response_text,
                quality_metrics.get('citation_coverage'),
                quality_metrics.get('grounding_rate', 0) * 100,  # Convert to percentage
                quality_metrics.get('total_claims'),
                quality_metrics.get('grounded_claims'),
                quality_metrics.get('decision_fidelity_score'),
                model,
                path,
                sources_count,
                len(quality_metrics.get('citations', []))
            ))

            cursor.close()

            logger.info(
                "Quality metrics stored",
                request_id=request_id,
                executive_id=executive_id,
                citation_coverage=quality_metrics.get('citation_coverage')
            )

            return True

    except Exception as e:
        logger.error(
            "Failed to store quality metrics",
            request_id=request_id,
            error=str(e)
        )
        return False


def store_user_feedback(
    request_id: str,
    executive_id: str,
    user_id: Optional[str],
    feedback_type: str,
    query_text: Optional[str] = None,
    response_text: Optional[str] = None,
    path: Optional[str] = None,
    rating: Optional[int] = None,
    comment: Optional[str] = None
) -> bool:
    """
    Store user feedback in database.

    Args:
        request_id: Request identifier
        executive_id: Executive profile ID
        user_id: User ID
        feedback_type: Type (thumbs_up, thumbs_down, comment)
        query_text: Original query (optional)
        response_text: Generated response (optional)
        path: Query path (optional)
        rating: 1-5 star rating (optional)
        comment: User comment (optional)

    Returns:
        True if stored successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO user_feedback (
                    request_id,
                    executive_id,
                    user_id,
                    feedback_type,
                    rating,
                    comment,
                    query_text,
                    response_text,
                    path
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                request_id,
                executive_id,
                user_id,
                feedback_type,
                rating,
                comment,
                query_text,
                response_text,
                path
            ))

            cursor.close()

            logger.info(
                "User feedback stored",
                request_id=request_id,
                feedback_type=feedback_type
            )

            return True

    except Exception as e:
        logger.error(
            "Failed to store user feedback",
            request_id=request_id,
            error=str(e)
        )
        return False


def track_user_activity(
    user_id: str,
    activity_type: str,
    executive_id: Optional[str] = None,
    session_id: Optional[str] = None,
    path: Optional[str] = None,
    success: bool = True
) -> bool:
    """
    Track user activity for DAU/MAU calculation.

    Args:
        user_id: User ID
        activity_type: Type (query, feedback, login)
        executive_id: Executive profile ID (optional)
        session_id: Session ID (optional)
        path: Query path (optional)
        success: Whether activity succeeded

    Returns:
        True if stored successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Use INSERT ... ON CONFLICT to handle duplicate user/date entries
            cursor.execute("""
                INSERT INTO user_activity (
                    user_id,
                    executive_id,
                    session_id,
                    activity_type,
                    activity_date,
                    path,
                    success
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (user_id, activity_date)
                DO UPDATE SET
                    activity_type = EXCLUDED.activity_type,
                    created_at = CURRENT_TIMESTAMP
            """, (
                user_id,
                executive_id,
                session_id,
                activity_type,
                date.today(),
                path,
                success
            ))

            cursor.close()

            return True

    except Exception as e:
        logger.error(
            "Failed to track user activity",
            user_id=user_id,
            error=str(e)
        )
        return False


def get_daily_metrics(target_date: date) -> Optional[Dict[str, Any]]:
    """
    Get daily business metrics for a specific date.

    Args:
        target_date: Date to get metrics for

    Returns:
        Dictionary with business metrics or None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT * FROM business_metrics
                WHERE date = %s
            """, (target_date,))

            result = cursor.fetchone()
            cursor.close()

            return dict(result) if result else None

    except Exception as e:
        logger.error(
            "Failed to get daily metrics",
            date=str(target_date),
            error=str(e)
        )
        return None


def update_daily_business_metrics(target_date: date) -> bool:
    """
    Update business metrics for a specific date.

    Calls the PostgreSQL function update_business_metrics().

    Args:
        target_date: Date to update metrics for

    Returns:
        True if updated successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT update_business_metrics(%s)",
                (target_date,)
            )

            cursor.close()

            logger.info(
                "Business metrics updated",
                date=str(target_date)
            )

            return True

    except Exception as e:
        logger.error(
            "Failed to update business metrics",
            date=str(target_date),
            error=str(e)
        )
        return False
