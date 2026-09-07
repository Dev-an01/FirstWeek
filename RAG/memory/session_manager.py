"""
Session Manager - Core Session Management Logic

Orchestrates session lifecycle, context preservation, and integration
with the broader RAG system including episodic memory and query routing.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import uuid

from .conversation_sessions import ConversationSessions

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Core session management logic
    
    Handles:
    - Session creation and tracking
    - Multi-turn conversation context
    - Session expiration and cleanup
    - Integration with episodic memory
    - Context preservation across turns
    """
    
    def __init__(
        self,
        conversation_sessions: ConversationSessions,
        session_timeout_minutes: int = 30,
        max_context_turns: int = 5,
        cleanup_interval_minutes: int = 5
    ):
        """
        Initialize session manager
        
        Args:
            conversation_sessions: Database operations handler
            session_timeout_minutes: Minutes of inactivity before expiration
            max_context_turns: Maximum turns to preserve in context
            cleanup_interval_minutes: Interval for running cleanup job
        """
        self.conversation_sessions = conversation_sessions
        self.session_timeout_minutes = session_timeout_minutes
        self.max_context_turns = max_context_turns
        self.cleanup_interval_minutes = cleanup_interval_minutes
        
        self.logger = logging.getLogger(__name__)
        
        # Background task reference
        self._cleanup_task = None
        
        # Session cache for performance (optional)
        self._session_cache = {}
        self._cache_ttl = timedelta(minutes=1)
    
    async def initialize(self):
        """
        Initialize session manager and start background tasks
        """
        self.logger.info("Initializing Session Manager")
        
        # Start background cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("Session Manager initialized successfully")
    
    async def shutdown(self):
        """
        Shutdown session manager and cleanup resources
        """
        self.logger.info("Shutting down Session Manager")
        
        # Cancel background task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Session Manager shutdown complete")
    
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
        # Check cache first
        _company = metadata.get("company_id", "") if metadata else ""
        cache_key = f"{_company}:{user_id}:{executive_id}"
        cached_session = self._get_from_cache(cache_key)
        
        if cached_session and await self._is_session_valid(cached_session):
            self.logger.debug(f"Using cached session {cached_session}")
            return cached_session
        
        # Get or create from database
        session_id = await self.conversation_sessions.get_or_create_session(
            user_id=user_id,
            executive_id=executive_id,
            metadata=metadata
        )
        
        # Cache the result
        self._add_to_cache(cache_key, session_id)
        
        return session_id
    
    async def update_session_activity(
        self,
        session_id: str,
        tokens_used: int = 0,
        response_time_ms: int = 0
    ) -> bool:
        """
        Update session activity after a turn
        
        Args:
            session_id: Session UUID
            tokens_used: Number of tokens used in this turn
            response_time_ms: Response time in milliseconds
            
        Returns:
            success: Whether update was successful
        """
        success = await self.conversation_sessions.update_session_activity(
            session_id=session_id,
            tokens_used=tokens_used,
            response_time_ms=response_time_ms
        )
        
        if success:
            # Invalidate cache for this session
            self._invalidate_session_cache(session_id)
        
        return success
    
    async def get_conversation_context(
        self,
        session_id: str,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Get conversation context for LLM prompt building
        
        Args:
            session_id: Session UUID
            include_metadata: Whether to include session metadata
            
        Returns:
            Context dictionary with conversation history
        """
        # Get session info
        session_info = await self.conversation_sessions.get_session_info(session_id)
        
        if not session_info:
            self.logger.warning(f"Session {session_id} not found")
            return {"session_id": session_id, "turns": []}
        
        # Get conversation turns
        turns = await self.conversation_sessions.get_session_context(
            session_id=session_id,
            max_turns=self.max_context_turns
        )
        
        # Build context
        context = {
            "session_id": session_id,
            "user_id": session_info["user_id"],
            "executive_id": session_info["executive_id"],
            "turn_count": session_info["turn_count"],
            "turns": turns,
            "session_age_minutes": session_info["seconds_since_last_activity"] / 60
        }
        
        if include_metadata:
            context["session_metadata"] = session_info["metadata"]
            context["session_started_at"] = session_info["started_at"]
            context["last_activity"] = session_info["last_activity"]
            context["expires_at"] = session_info["expires_at"]
        
        return context
    
    async def build_llm_messages(
        self,
        session_id: str,
        current_query: str,
        system_prompt: str
    ) -> List[Dict[str, str]]:
        """
        Build LLM messages with conversation context
        
        Args:
            session_id: Session UUID
            current_query: Current user query
            system_prompt: System prompt for the executive
            
        Returns:
            List of messages for LLM API call
        """
        # Get conversation context
        context = await self.get_conversation_context(session_id)
        
        # Start with system prompt
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        for turn in context["turns"]:
            messages.append({"role": "user", "content": turn["query"]})
            messages.append({"role": "assistant", "content": turn["response"]})
        
        # Add current query
        messages.append({"role": "user", "content": current_query})
        
        self.logger.debug(
            f"Built {len(messages)} messages for session {session_id} "
            f"({len(context['turns'])} turns in context)"
        )
        
        return messages
    
    async def store_conversation_turn(
        self,
        session_id: str,
        query: str,
        response: str,
        sources_used: Optional[List[Dict[str, Any]]] = None,
        reasoning_trace: Optional[Dict[str, Any]] = None,
        importance_score: float = 0.5,
        embedding: Optional[List[float]] = None
    ) -> bool:
        """
        Store a conversation turn in episodic memory
        
        Args:
            session_id: Session UUID
            query: User query
            response: AI response
            sources_used: Sources referenced in response
            reasoning_trace: LLM reasoning steps
            importance_score: Importance score (0-1)
            embedding: Query embedding vector
            
        Returns:
            success: Whether storage was successful
        """
        try:
            # Get session info for turn number
            session_info = await self.conversation_sessions.get_session_info(session_id)
            if not session_info:
                self.logger.error(f"Cannot store turn: session {session_id} not found")
                return False
            
            turn_number = session_info["turn_count"] + 1
            
            # Store in episodic memory
            # Note: This would integrate with the existing episodic memory system
            # For now, we'll simulate the storage
            await self._store_in_episodic_memory(
                session_id=session_id,
                executive_id=session_info["executive_id"],
                user_id=session_info["user_id"],
                turn_number=turn_number,
                query=query,
                response=response,
                sources_used=sources_used,
                reasoning_trace=reasoning_trace,
                importance_score=importance_score,
                embedding=embedding
            )
            
            # Update session activity
            await self.update_session_activity(session_id)
            
            self.logger.debug(f"Stored turn {turn_number} for session {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store conversation turn: {e}")
            return False
    
    async def end_session(self, session_id: str) -> bool:
        """
        Manually end a session
        
        Args:
            session_id: Session UUID to end
            
        Returns:
            success: Whether session was ended
        """
        success = await self.conversation_sessions.end_session(session_id)
        
        if success:
            # Invalidate cache
            self._invalidate_session_cache(session_id)
            self.logger.info(f"Manually ended session {session_id}")
        
        return success
    
    async def extend_session(self, session_id: str, minutes: int = None) -> bool:
        """
        Extend session expiration time
        
        Args:
            session_id: Session UUID to extend
            minutes: Number of minutes to extend (default: session timeout)
            
        Returns:
            success: Whether session was extended
        """
        if minutes is None:
            minutes = self.session_timeout_minutes
        
        success = await self.conversation_sessions.extend_session(session_id, minutes)
        
        if success:
            # Invalidate cache
            self._invalidate_session_cache(session_id)
            self.logger.info(f"Extended session {session_id} by {minutes} minutes")
        
        return success
    
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
            company_id: Optional company filter for tenant isolation

        Returns:
            List of active session information
        """
        return await self.conversation_sessions.get_active_sessions(
            user_id=user_id,
            executive_id=executive_id,
            company_id=company_id
        )
    
    async def get_session_statistics(
        self,
        executive_id: Optional[str] = None,
        company_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get session statistics by executive

        Args:
            executive_id: Optional executive filter
            company_id: Optional company filter for tenant isolation

        Returns:
            List of session statistics
        """
        return await self.conversation_sessions.get_session_statistics(
            executive_id=executive_id,
            company_id=company_id
        )
    
    async def _cleanup_loop(self):
        """
        Background task to clean up expired sessions
        """
        self.logger.info("Starting session cleanup loop")
        
        while True:
            try:
                # Wait for cleanup interval
                await asyncio.sleep(self.cleanup_interval_minutes * 60)
                
                # Run cleanup
                expired_count = await self.conversation_sessions.expire_inactive_sessions()
                
                if expired_count > 0:
                    self.logger.info(f"Cleaned up {expired_count} expired sessions")
                
                # Clear cache periodically
                self._clear_cache()
                
            except asyncio.CancelledError:
                self.logger.info("Session cleanup loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                # Continue the loop despite errors
    
    async def _is_session_valid(self, session_id: str) -> bool:
        """
        Check if a session is still valid and active
        
        Args:
            session_id: Session UUID to check
            
        Returns:
            Whether session is valid
        """
        try:
            session_info = await self.conversation_sessions.get_session_info(session_id)
            
            if not session_info:
                return False
            
            return (
                session_info["is_active"] and
                session_info["seconds_until_expiry"] > 0
            )
            
        except Exception:
            return False
    
    async def _store_in_episodic_memory(
        self,
        session_id: str,
        executive_id: str,
        user_id: str,
        turn_number: int,
        query: str,
        response: str,
        sources_used: Optional[List[Dict[str, Any]]],
        reasoning_trace: Optional[Dict[str, Any]],
        importance_score: float,
        embedding: Optional[List[float]]
    ):
        """
        Store conversation turn in episodic memory
        
        This would integrate with the existing episodic memory system.
        For now, we'll simulate the storage.
        """
        # TODO: Integrate with actual episodic memory system
        # This would involve calling the episodic memory storage methods
        
        self.logger.debug(
            f"Storing in episodic memory: session={session_id}, "
            f"turn={turn_number}, executive={executive_id}"
        )
        
        # Simulate storage delay
        await asyncio.sleep(0.01)
    
    def _get_from_cache(self, key: str) -> Optional[str]:
        """
        Get session ID from cache
        
        Args:
            key: Cache key (user_id:executive_id)
            
        Returns:
            Cached session ID or None
        """
        if key in self._session_cache:
            cached_time, session_id = self._session_cache[key]
            
            if datetime.utcnow() - cached_time < self._cache_ttl:
                return session_id
            else:
                # Expired, remove from cache
                del self._session_cache[key]
        
        return None
    
    def _add_to_cache(self, key: str, session_id: str):
        """
        Add session ID to cache
        
        Args:
            key: Cache key
            session_id: Session UUID
        """
        self._session_cache[key] = (datetime.utcnow(), session_id)
    
    def _invalidate_session_cache(self, session_id: str):
        """
        Invalidate cache entries for a session
        
        Args:
            session_id: Session UUID to invalidate
        """
        # Find and remove cache entries for this session
        keys_to_remove = []
        
        for key, (_, cached_session_id) in self._session_cache.items():
            if cached_session_id == session_id:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._session_cache[key]
    
    def _clear_cache(self):
        """Clear expired cache entries"""
        keys_to_remove = []
        
        for key, (cached_time, _) in self._session_cache.items():
            if datetime.utcnow() - cached_time > self._cache_ttl:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._session_cache[key]
        
        if keys_to_remove:
            self.logger.debug(f"Cleared {len(keys_to_remove)} expired cache entries")