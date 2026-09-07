"""
Conversation Sessions Database Operations

Handles all database operations for conversation sessions,
including creation, updates, expiration, and context retrieval.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import uuid

import asyncpg
from asyncpg import Connection

logger = logging.getLogger(__name__)


class ConversationSessions:
    """
    Database operations for conversation sessions
    
    Manages session lifecycle including:
    - Session creation and retrieval
    - Activity tracking and expiration
    - Context preservation across turns
    - Session statistics and cleanup
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize with database connection pool
        
        Args:
            db_pool: AsyncPG connection pool
        """
        self.db_pool = db_pool
        self.logger = logging.getLogger(__name__)
    
    async def get_or_create_session(
        self,
        user_id: str,
        executive_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get existing active session or create new one
        
        Args:
            user_id: User identifier
            executive_id: Executive profile ID
            metadata: Optional session metadata
            
        Returns:
            session_id: UUID string of the session
        """
        async with self.db_pool.acquire() as conn:
            try:
                # Use the database function for atomic get-or-create
                session_id = await conn.fetchval(
                    "SELECT get_or_create_session($1, $2, $3)",
                    user_id,
                    executive_id,
                    json.dumps(metadata or {})
                )
                
                self.logger.info(
                    f"Session {'retrieved' if await self._is_existing_session(session_id, conn) else 'created'}: "
                    f"{session_id} for user {user_id} with executive {executive_id}"
                )
                
                return str(session_id)
                
            except Exception as e:
                self.logger.error(f"Failed to get or create session: {e}")
                raise
    
    async def update_session_activity(
        self,
        session_id: str,
        tokens_used: int = 0,
        response_time_ms: int = 0
    ) -> bool:
        """
        Update session activity and statistics
        
        Args:
            session_id: Session UUID
            tokens_used: Number of tokens used in this turn
            response_time_ms: Response time in milliseconds
            
        Returns:
            success: Whether update was successful
        """
        async with self.db_pool.acquire() as conn:
            try:
                await conn.execute(
                    "SELECT update_session_activity($1, $2, $3)",
                    session_id,
                    tokens_used,
                    response_time_ms
                )
                
                self.logger.debug(f"Updated activity for session {session_id}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to update session activity: {e}")
                return False
    
    async def get_session_context(
        self,
        session_id: str,
        max_turns: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversation context for a session
        
        Args:
            session_id: Session UUID
            max_turns: Maximum number of recent turns to retrieve
            
        Returns:
            List of conversation turns with query/response pairs
        """
        async with self.db_pool.acquire() as conn:
            try:
                # Query episodic memory for session context
                query = """
                    SELECT 
                        query,
                        response,
                        timestamp,
                        turn_number,
                        importance_score,
                        context_sources
                    FROM episodic_memory
                    WHERE session_id = $1
                    ORDER BY turn_number ASC
                    LIMIT $2
                """
                
                rows = await conn.fetch(query, session_id, max_turns)
                
                context = []
                for row in rows:
                    context.append({
                        "query": row["query"],
                        "response": row["response"],
                        "timestamp": row["timestamp"].isoformat(),
                        "turn_number": row["turn_number"],
                        "importance_score": float(row["importance_score"]),
                        "context_sources": row["context_sources"] or {}
                    })
                
                self.logger.debug(f"Retrieved {len(context)} turns for session {session_id}")
                return context
                
            except Exception as e:
                self.logger.error(f"Failed to get session context: {e}")
                return []
    
    async def get_active_sessions(
        self,
        user_id: Optional[str] = None,
        executive_id: Optional[str] = None,
        company_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all active sessions, optionally filtered
        
        Args:
            user_id: Optional user filter
            executive_id: Optional executive filter
            
        Returns:
            List of active session information
        """
        async with self.db_pool.acquire() as conn:
            try:
                query = """
                    SELECT 
                        session_id,
                        user_id,
                        executive_id,
                        started_at,
                        last_activity,
                        expires_at,
                        turn_count,
                        total_tokens,
                        avg_response_time_ms,
                        metadata,
                        EXTRACT(EPOCH FROM (NOW() - last_activity))::INTEGER as seconds_since_last_activity,
                        EXTRACT(EPOCH FROM (expires_at - NOW()))::INTEGER as seconds_until_expiry
                    FROM conversation_sessions
                    WHERE is_active = true
                """
                params = []
                
                # Add filters if provided
                if user_id:
                    query += " AND user_id = $" + str(len(params) + 1)
                    params.append(user_id)
                
                if executive_id:
                    query += " AND executive_id = $" + str(len(params) + 1)
                    params.append(executive_id)

                if company_id:
                    query += " AND company_id = $" + str(len(params) + 1)
                    params.append(company_id)

                query += " ORDER BY last_activity DESC"
                
                rows = await conn.fetch(query, *params)
                
                sessions = []
                for row in rows:
                    sessions.append({
                        "session_id": str(row["session_id"]),
                        "user_id": row["user_id"],
                        "executive_id": row["executive_id"],
                        "started_at": row["started_at"].isoformat(),
                        "last_activity": row["last_activity"].isoformat(),
                        "expires_at": row["expires_at"].isoformat(),
                        "turn_count": row["turn_count"],
                        "total_tokens": row["total_tokens"],
                        "avg_response_time_ms": row["avg_response_time_ms"],
                        "metadata": row["metadata"] or {},
                        "seconds_since_last_activity": row["seconds_since_last_activity"],
                        "seconds_until_expiry": row["seconds_until_expiry"]
                    })
                
                return sessions
                
            except Exception as e:
                self.logger.error(f"Failed to get active sessions: {e}")
                return []
    
    async def expire_inactive_sessions(self) -> int:
        """
        Expire all inactive sessions (cleanup job)
        
        Returns:
            Number of sessions expired
        """
        async with self.db_pool.acquire() as conn:
            try:
                expired_count = await conn.fetchval(
                    "SELECT expire_inactive_sessions()"
                )
                
                self.logger.info(f"Expired {expired_count} inactive sessions")
                return expired_count
                
            except Exception as e:
                self.logger.error(f"Failed to expire inactive sessions: {e}")
                return 0
    
    async def get_session_statistics(
        self,
        executive_id: Optional[str] = None,
        company_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get session statistics by executive
        
        Args:
            executive_id: Optional executive filter
            
        Returns:
            List of session statistics
        """
        async with self.db_pool.acquire() as conn:
            try:
                query = """
                    SELECT * FROM session_statistics
                """
                params = []
                
                where_clauses = []
                if executive_id:
                    where_clauses.append(f"executive_id = ${len(params) + 1}")
                    params.append(executive_id)
                if company_id:
                    where_clauses.append(f"company_id = ${len(params) + 1}")
                    params.append(company_id)
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)

                query += " ORDER BY last_session_date DESC"
                
                rows = await conn.fetch(query, *params)
                
                stats = []
                for row in rows:
                    stats.append({
                        "executive_id": row["executive_id"],
                        "total_sessions": row["total_sessions"],
                        "active_sessions": row["active_sessions"],
                        "avg_turns_per_session": float(row["avg_turns_per_session"]),
                        "avg_tokens_per_session": float(row["avg_tokens_per_session"]),
                        "avg_response_time_ms": float(row["avg_response_time_ms"]),
                        "last_session_date": row["last_session_date"].isoformat() if row["last_session_date"] else None
                    })
                
                return stats
                
            except Exception as e:
                self.logger.error(f"Failed to get session statistics: {e}")
                return []
    
    async def end_session(self, session_id: str) -> bool:
        """
        Manually end a session
        
        Args:
            session_id: Session UUID to end
            
        Returns:
            success: Whether session was ended
        """
        async with self.db_pool.acquire() as conn:
            try:
                result = await conn.execute(
                    "UPDATE conversation_sessions SET is_active = false WHERE session_id = $1",
                    session_id
                )
                
                success = "UPDATE 1" in result
                if success:
                    self.logger.info(f"Manually ended session {session_id}")
                
                return success
                
            except Exception as e:
                self.logger.error(f"Failed to end session {session_id}: {e}")
                return False
    
    async def extend_session(self, session_id: str, minutes: int = 30) -> bool:
        """
        Extend session expiration time
        
        Args:
            session_id: Session UUID to extend
            minutes: Number of minutes to extend
            
        Returns:
            success: Whether session was extended
        """
        async with self.db_pool.acquire() as conn:
            try:
                result = await conn.execute(
                    """
                    UPDATE conversation_sessions 
                    SET last_activity = NOW(),
                        expires_at = NOW() + INTERVAL '%s minutes'
                    WHERE session_id = $1 AND is_active = true
                    """,
                    minutes,
                    session_id
                )
                
                success = "UPDATE 1" in result
                if success:
                    self.logger.info(f"Extended session {session_id} by {minutes} minutes")
                
                return success
                
            except Exception as e:
                self.logger.error(f"Failed to extend session {session_id}: {e}")
                return False
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific session
        
        Args:
            session_id: Session UUID
            
        Returns:
            Session information or None if not found
        """
        async with self.db_pool.acquire() as conn:
            try:
                query = """
                    SELECT 
                        s.*,
                        EXTRACT(EPOCH FROM (NOW() - s.last_activity))::INTEGER as seconds_since_last_activity,
                        EXTRACT(EPOCH FROM (s.expires_at - NOW()))::INTEGER as seconds_until_expiry
                    FROM conversation_sessions s
                    WHERE s.session_id = $1
                """
                
                row = await conn.fetchrow(query, session_id)
                
                if not row:
                    return None
                
                return {
                    "session_id": str(row["session_id"]),
                    "user_id": row["user_id"],
                    "executive_id": row["executive_id"],
                    "started_at": row["started_at"].isoformat(),
                    "last_activity": row["last_activity"].isoformat(),
                    "expires_at": row["expires_at"].isoformat(),
                    "is_active": row["is_active"],
                    "turn_count": row["turn_count"],
                    "total_tokens": row["total_tokens"],
                    "avg_response_time_ms": row["avg_response_time_ms"],
                    "metadata": row["metadata"] or {},
                    "seconds_since_last_activity": row["seconds_since_last_activity"],
                    "seconds_until_expiry": row["seconds_until_expiry"]
                }
                
            except Exception as e:
                self.logger.error(f"Failed to get session info {session_id}: {e}")
                return None
    
    async def _is_existing_session(self, session_id: str, conn: Connection) -> bool:
        """
        Helper to check if session existed before this call
        
        Args:
            session_id: Session UUID to check
            conn: Database connection
            
        Returns:
            Whether session existed before
        """
        # This is a simple heuristic - in production, you might want
        # a more sophisticated way to determine if session is new vs existing
        try:
            row = await conn.fetchrow(
                "SELECT started_at FROM conversation_sessions WHERE session_id = $1",
                session_id
            )
            
            if not row:
                return False
            
            # If session was started within the last 5 seconds, consider it new
            started_at = row["started_at"]
            now = datetime.utcnow()
            time_diff = (now - started_at).total_seconds()
            
            return time_diff > 5  # Existing if older than 5 seconds
            
        except Exception:
            return False
    
    async def cleanup_old_sessions(self, days: int = 30) -> int:
        """
        Clean up old inactive sessions permanently
        
        Args:
            days: Age in days to delete
            
        Returns:
            Number of sessions deleted
        """
        async with self.db_pool.acquire() as conn:
            try:
                result = await conn.execute(
                    """
                    DELETE FROM conversation_sessions 
                    WHERE is_active = false 
                      AND last_activity < NOW() - INTERVAL '%s days'
                    """,
                    days
                )
                
                # Extract count from result string like "DELETE 5"
                deleted_count = int(result.split()[-1]) if result.split() else 0
                
                self.logger.info(f"Cleaned up {deleted_count} old sessions (older than {days} days)")
                return deleted_count
                
            except Exception as e:
                self.logger.error(f"Failed to cleanup old sessions: {e}")
                return 0