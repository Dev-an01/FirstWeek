"""
Database client for scheduled meetings
Provides persistent storage across service restarts
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Dict, List, Optional
import os

logger = logging.getLogger(__name__)


class MeetingsDB:
    """PostgreSQL database client for meetings"""

    def __init__(self):
        """Initialize database connection"""
        self.conn_params = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'database': os.getenv('POSTGRES_DB', 'ai_officer'),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', 'postgres123')
        }
        self._ensure_table()
        logger.info("✅ MeetingsDB initialized")

    def _get_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.conn_params)

    def _ensure_table(self):
        """Create meetings table if it doesn't exist"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS scheduled_meetings (
            meeting_id VARCHAR(255) PRIMARY KEY,
            meeting_url TEXT NOT NULL,
            scheduled_time TIMESTAMP NOT NULL,
            profile_id VARCHAR(100) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            bot_id VARCHAR(255),
            executive VARCHAR(100),
            platform VARCHAR(100),
            language VARCHAR(10) DEFAULT 'en',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_meetings_status ON scheduled_meetings(status);
        CREATE INDEX IF NOT EXISTS idx_meetings_scheduled_time ON scheduled_meetings(scheduled_time);
        CREATE INDEX IF NOT EXISTS idx_meetings_created_at ON scheduled_meetings(created_at);
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(create_table_sql)
                    
                    # Migration: Add language column if it doesn't exist
                    try:
                        cur.execute("ALTER TABLE scheduled_meetings ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en'")
                    except Exception as e:
                        logger.warning(f"Column migration warning (might already exist): {e}")
                        
                conn.commit()
            logger.info("✅ Meetings table ensured")
        except Exception as e:
            logger.error(f"Failed to create meetings table: {e}", exc_info=True)
            raise

    def create_meeting(self, meeting_data: dict) -> dict:
        """Create a new meeting"""
        sql = """
        INSERT INTO scheduled_meetings
        (meeting_id, meeting_url, scheduled_time, profile_id, status, bot_id, executive, platform, language, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, (
                        meeting_data['meeting_id'],
                        meeting_data['meeting_url'],
                        meeting_data['scheduled_time'],
                        meeting_data['profile_id'],
                        meeting_data.get('status', 'pending'),
                        meeting_data.get('bot_id'),
                        meeting_data.get('executive'),
                        meeting_data.get('platform'),
                        meeting_data.get('language', 'en'),
                        meeting_data.get('created_at', datetime.utcnow())
                    ))
                    result = dict(cur.fetchone())
                conn.commit()
            logger.info(f"✅ Meeting created in DB: {meeting_data['meeting_id']}")
            return result
        except Exception as e:
            logger.error(f"Failed to create meeting: {e}", exc_info=True)
            raise

    def get_meeting(self, meeting_id: str) -> Optional[dict]:
        """Get a meeting by ID"""
        sql = "SELECT * FROM scheduled_meetings WHERE meeting_id = %s"

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, (meeting_id,))
                    result = cur.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to get meeting: {e}", exc_info=True)
            return None

    def list_meetings(self, status: Optional[str] = None) -> List[dict]:
        """List meetings, optionally filtered by status"""
        if status:
            sql = "SELECT * FROM scheduled_meetings WHERE status = %s ORDER BY scheduled_time"
            params = (status,)
        else:
            sql = "SELECT * FROM scheduled_meetings ORDER BY scheduled_time"
            params = ()

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, params)
                    results = cur.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to list meetings: {e}", exc_info=True)
            return []

    def update_meeting(self, meeting_id: str, updates: dict) -> Optional[dict]:
        """Update a meeting"""
        # Build UPDATE query dynamically
        set_clauses = []
        values = []
        for key, value in updates.items():
            set_clauses.append(f"{key} = %s")
            values.append(value)

        # Always update updated_at
        set_clauses.append("updated_at = NOW()")
        values.append(meeting_id)

        sql = f"""
        UPDATE scheduled_meetings
        SET {', '.join(set_clauses)}
        WHERE meeting_id = %s
        RETURNING *
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, values)
                    result = cur.fetchone()
                conn.commit()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to update meeting: {e}", exc_info=True)
            return None

    def delete_meeting(self, meeting_id: str) -> bool:
        """Delete a meeting"""
        sql = "DELETE FROM scheduled_meetings WHERE meeting_id = %s"

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (meeting_id,))
                    deleted = cur.rowcount > 0
                conn.commit()
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete meeting: {e}", exc_info=True)
            return False


# Global singleton
_meetings_db: Optional[MeetingsDB] = None


def get_meetings_db() -> MeetingsDB:
    """Get or create the global MeetingsDB instance"""
    global _meetings_db
    if _meetings_db is None:
        _meetings_db = MeetingsDB()
    return _meetings_db
