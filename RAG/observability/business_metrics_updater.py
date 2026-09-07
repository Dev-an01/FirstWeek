"""
Business Metrics Updater
=========================

Periodically updates Prometheus business metrics from PostgreSQL.

Metrics updated:
- Daily Active Users (DAU)
- Monthly Active Users (MAU)
- User retention rate
- User satisfaction rate
- Queries per user

Usage:
    from observability.business_metrics_updater import BusinessMetricsUpdater

    updater = BusinessMetricsUpdater()
    await updater.start()  # Starts background task
"""

import asyncio
from datetime import date, timedelta
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

from .db_persistence import DB_CONFIG, get_db_connection
from .metrics import (
    daily_active_users,
    monthly_active_users,
    user_retention_rate,
    user_satisfaction_rate,
)
from .logging import StructuredLogger

logger = StructuredLogger(__name__)


class BusinessMetricsUpdater:
    """
    Updates Prometheus business metrics from PostgreSQL.

    Runs periodically in the background to sync database metrics
    to Prometheus gauges for real-time monitoring.
    """

    def __init__(self, update_interval_seconds: int = 60):
        """
        Initialize metrics updater.

        Args:
            update_interval_seconds: How often to update metrics (default: 60s)
        """
        self.update_interval = update_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the background update task"""
        if self._running:
            logger.warning("Metrics updater already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._update_loop())
        logger.info(
            "Business metrics updater started",
            update_interval_seconds=self.update_interval
        )

    async def stop(self):
        """Stop the background update task"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Business metrics updater stopped")

    async def _update_loop(self):
        """Main update loop"""
        while self._running:
            try:
                await self.update_metrics()
            except Exception as e:
                logger.error("Error updating business metrics", error=str(e))

            # Wait for next update
            await asyncio.sleep(self.update_interval)

    async def update_metrics(self):
        """Update all business metrics from database"""
        try:
            # Run in thread pool to avoid blocking
            await asyncio.to_thread(self._sync_update_metrics)

        except Exception as e:
            logger.error("Failed to update business metrics", error=str(e))

    def _sync_update_metrics(self):
        """Synchronous metrics update (runs in thread pool)"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # 1. Update DAU (Daily Active Users)
                today = date.today()
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as dau
                    FROM user_activity
                    WHERE activity_date = %s
                """, (today,))
                dau_result = cursor.fetchone()
                dau = dau_result['dau'] if dau_result else 0
                daily_active_users.set(dau)

                # 2. Update MAU (Monthly Active Users)
                thirty_days_ago = today - timedelta(days=30)
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as mau
                    FROM user_activity
                    WHERE activity_date >= %s
                """, (thirty_days_ago,))
                mau_result = cursor.fetchone()
                mau = mau_result['mau'] if mau_result else 0
                monthly_active_users.set(mau)

                # 3. Update 7-day retention rate
                seven_days_ago = today - timedelta(days=7)
                cursor.execute("""
                    WITH cohort AS (
                        SELECT DISTINCT user_id
                        FROM user_activity
                        WHERE activity_date = %s
                    ),
                    retained AS (
                        SELECT DISTINCT ua.user_id
                        FROM user_activity ua
                        JOIN cohort c ON ua.user_id = c.user_id
                        WHERE ua.activity_date > %s
                        AND ua.activity_date <= %s
                    )
                    SELECT
                        COALESCE(
                            (COUNT(DISTINCT retained.user_id)::FLOAT /
                             NULLIF(COUNT(DISTINCT cohort.user_id), 0)) * 100,
                            0
                        ) as retention_rate
                    FROM cohort
                    LEFT JOIN retained ON cohort.user_id = retained.user_id
                """, (seven_days_ago, seven_days_ago, today))
                retention_result = cursor.fetchone()
                retention = retention_result['retention_rate'] if retention_result else 0
                user_retention_rate.set(retention)

                # 4. Update user satisfaction rate
                cursor.execute("""
                    SELECT
                        COALESCE(
                            (COUNT(*) FILTER (WHERE feedback_type = 'thumbs_up')::FLOAT /
                             NULLIF(COUNT(*), 0)) * 100,
                            0
                        ) as satisfaction
                    FROM user_feedback
                    WHERE created_at >= %s
                """, (thirty_days_ago,))
                satisfaction_result = cursor.fetchone()
                satisfaction = satisfaction_result['satisfaction'] if satisfaction_result else 0
                user_satisfaction_rate.set(satisfaction)

                cursor.close()

                logger.info(
                    "Business metrics updated",
                    dau=dau,
                    mau=mau,
                    retention_rate=round(retention, 2),
                    satisfaction_rate=round(satisfaction, 2)
                )

        except Exception as e:
            logger.error("Failed to sync business metrics", error=str(e))
            raise


# Global instance
_updater: Optional[BusinessMetricsUpdater] = None


async def start_metrics_updater(update_interval_seconds: int = 60):
    """
    Start the global business metrics updater.

    Args:
        update_interval_seconds: How often to update metrics

    Returns:
        BusinessMetricsUpdater instance
    """
    global _updater

    if _updater is None:
        _updater = BusinessMetricsUpdater(update_interval_seconds)

    await _updater.start()
    return _updater


async def stop_metrics_updater():
    """Stop the global business metrics updater"""
    global _updater

    if _updater:
        await _updater.stop()
        _updater = None
