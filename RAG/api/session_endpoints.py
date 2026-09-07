"""
Session Management API Endpoints

REST API endpoints for session management including:
- Session creation and retrieval
- Session context and history
- Session statistics and monitoring
- Session extension and termination
"""

from fastapi import APIRouter

# Create router for session endpoints
router = APIRouter()

import logging
import time
from typing import Dict, List, Optional, Any

from fastapi import HTTPException, Depends, status
from fastapi.responses import JSONResponse

from api.models import (
    ErrorResponse,
    HealthResponse
)
from api.dependencies import get_db_pool
from memory.session_manager import SessionManager
from memory.conversation_sessions import ConversationSessions

logger = logging.getLogger(__name__)


# ============================================================
# Pydantic Models for Session Endpoints
# ============================================================

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SessionCreateRequest(BaseModel):
    """Request to create or get a session"""
    
    user_id: str = Field(..., description="User identifier")
    executive_id: str = Field(..., description="Executive profile ID")
    metadata: Optional[Dict[str, Any]] = Field(
        default={}, description="Optional session metadata"
    )


class SessionCreateResponse(BaseModel):
    """Response for session creation"""
    
    success: bool = True
    session_id: str = Field(..., description="Session UUID")
    user_id: str = Field(..., description="User ID")
    executive_id: str = Field(..., description="Executive ID")
    created_new: bool = Field(..., description="Whether new session was created")
    expires_at: datetime = Field(..., description="Session expiration time")


class SessionContextRequest(BaseModel):
    """Request to get session context"""
    
    session_id: str = Field(..., description="Session UUID")
    max_turns: Optional[int] = Field(
        default=5, description="Maximum turns to retrieve"
    )


class SessionContextResponse(BaseModel):
    """Response with session context"""
    
    success: bool = True
    session_id: str = Field(..., description="Session UUID")
    user_id: str = Field(..., description="User ID")
    executive_id: str = Field(..., description="Executive ID")
    turn_count: int = Field(..., description="Number of turns in session")
    turns: List[Dict[str, Any]] = Field(..., description="Conversation turns")
    session_age_minutes: float = Field(..., description="Session age in minutes")


class SessionUpdateRequest(BaseModel):
    """Request to update session"""
    
    session_id: str = Field(..., description="Session UUID")
    tokens_used: Optional[int] = Field(
        default=0, description="Tokens used in this turn"
    )
    response_time_ms: Optional[int] = Field(
        default=0, description="Response time in milliseconds"
    )


class SessionUpdateResponse(BaseModel):
    """Response for session update"""
    
    success: bool = True
    session_id: str = Field(..., description="Session UUID")
    updated: bool = Field(..., description="Whether update was successful")


class SessionExtendRequest(BaseModel):
    """Request to extend session"""
    
    session_id: str = Field(..., description="Session UUID")
    minutes: Optional[int] = Field(
        default=30, description="Minutes to extend"
    )


class SessionExtendResponse(BaseModel):
    """Response for session extension"""
    
    success: bool = True
    session_id: str = Field(..., description="Session UUID")
    extended: bool = Field(..., description="Whether extension was successful")
    new_expires_at: Optional[datetime] = Field(
        default=None, description="New expiration time"
    )


class SessionEndRequest(BaseModel):
    """Request to end session"""
    
    session_id: str = Field(..., description="Session UUID")


class SessionEndResponse(BaseModel):
    """Response for session ending"""
    
    success: bool = True
    session_id: str = Field(..., description="Session UUID")
    ended: bool = Field(..., description="Whether session was ended")


class SessionInfoResponse(BaseModel):
    """Response with detailed session information"""
    
    success: bool = True
    session_id: str = Field(..., description="Session UUID")
    user_id: str = Field(..., description="User ID")
    executive_id: str = Field(..., description="Executive ID")
    started_at: datetime = Field(..., description="Session start time")
    last_activity: datetime = Field(..., description="Last activity time")
    expires_at: datetime = Field(..., description="Expiration time")
    is_active: bool = Field(..., description="Whether session is active")
    turn_count: int = Field(..., description="Number of turns")
    total_tokens: int = Field(..., description="Total tokens used")
    avg_response_time_ms: int = Field(..., description="Average response time")
    metadata: Dict[str, Any] = Field(..., description="Session metadata")
    seconds_since_last_activity: int = Field(..., description="Seconds since last activity")
    seconds_until_expiry: int = Field(..., description="Seconds until expiry")


class ActiveSessionsResponse(BaseModel):
    """Response with list of active sessions"""
    
    success: bool = True
    sessions: List[Dict[str, Any]] = Field(..., description="Active sessions")
    count: int = Field(..., description="Number of active sessions")


class SessionStatsResponse(BaseModel):
    """Response with session statistics"""
    
    success: bool = True
    statistics: List[Dict[str, Any]] = Field(..., description="Session statistics")
    count: int = Field(..., description="Number of executives")


# ============================================================
# SESSION ENDPOINTS
# ============================================================

@router.post("/create", response_model=SessionCreateResponse, tags=["Sessions"])
async def create_session(
    request: SessionCreateRequest,
    db_pool = Depends(get_db_pool)
) -> SessionCreateResponse:
    """
    Create new session or get existing active session
    
    Creates a new session if no active session exists for the
    user-executive pair, otherwise returns existing session.
    """
    try:
        # Initialize session manager
        conversation_sessions = ConversationSessions(db_pool)
        session_manager = SessionManager(conversation_sessions)
        
        # Get or create session
        session_id = await session_manager.get_or_create_session(
            user_id=request.user_id,
            executive_id=request.executive_id,
            metadata=request.metadata
        )
        
        # Get session info to determine if new
        session_info = await session_manager.conversation_sessions.get_session_info(session_id)
        created_new = session_info and (
            time.time() - datetime.fromisoformat(
                session_info["started_at"].replace('Z', '+00:00')
            ).timestamp() < 60  # Created within last minute
        )
        
        return SessionCreateResponse(
            session_id=session_id,
            user_id=request.user_id,
            executive_id=request.executive_id,
            created_new=created_new,
            expires_at=session_info["expires_at"] if session_info else None
        )
        
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


async def get_session_context(
    request: SessionContextRequest,
    db_pool = Depends(get_db_pool)
) -> SessionContextResponse:
    """
    Get conversation context for a session
    
    Returns the conversation history for building LLM context.
    """
    try:
        # Initialize session manager
        conversation_sessions = ConversationSessions(db_pool)
        session_manager = SessionManager(conversation_sessions)
        
        # Get session context
        context = await session_manager.get_conversation_context(
            session_id=request.session_id,
            include_metadata=True
        )
        
        if not context or not context.get("session_id"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {request.session_id}"
            )
        
        return SessionContextResponse(
            session_id=context["session_id"],
            user_id=context["user_id"],
            executive_id=context["executive_id"],
            turn_count=context["turn_count"],
            turns=context["turns"][:request.max_turns],
            session_age_minutes=context["session_age_minutes"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session context: {str(e)}"
        )


async def update_session_activity(
    request: SessionUpdateRequest,
    db_pool = Depends(get_db_pool)
) -> SessionUpdateResponse:
    """
    Update session activity after a conversation turn
    
    Updates the session with token usage and response time.
    """
    try:
        # Initialize session manager
        conversation_sessions = ConversationSessions(db_pool)
        session_manager = SessionManager(conversation_sessions)
        
        # Update session activity
        updated = await session_manager.update_session_activity(
            session_id=request.session_id,
            tokens_used=request.tokens_used,
            response_time_ms=request.response_time_ms
        )
        
        return SessionUpdateResponse(
            session_id=request.session_id,
            updated=updated
        )
        
    except Exception as e:
        logger.error(f"Failed to update session activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session activity: {str(e)}"
        )


async def extend_session(
    request: SessionExtendRequest,
    db_pool = Depends(get_db_pool)
) -> SessionExtendResponse:
    """
    Extend session expiration time
    
    Extends the session by specified number of minutes.
    """
    try:
        # Initialize session manager
        conversation_sessions = ConversationSessions(db_pool)
        session_manager = SessionManager(conversation_sessions)
        
        # Extend session
        extended = await session_manager.extend_session(
            session_id=request.session_id,
            minutes=request.minutes
        )
        
        # Get new expiration time
        new_expires_at = None
        if extended:
            session_info = await session_manager.conversation_sessions.get_session_info(request.session_id)
            if session_info:
                new_expires_at = session_info["expires_at"]
        
        return SessionExtendResponse(
            session_id=request.session_id,
            extended=extended,
            new_expires_at=new_expires_at
        )
        
    except Exception as e:
        logger.error(f"Failed to extend session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extend session: {str(e)}"
        )


async def end_session(
    request: SessionEndRequest,
    db_pool = Depends(get_db_pool)
) -> SessionEndResponse:
    """
    Manually end a session
    
    Deactivates the session immediately.
    """
    try:
        # Initialize session manager
        conversation_sessions = ConversationSessions(db_pool)
        session_manager = SessionManager(conversation_sessions)
        
        # End session
        ended = await session_manager.end_session(request.session_id)
        
        return SessionEndResponse(
            session_id=request.session_id,
            ended=ended
        )
        
    except Exception as e:
        logger.error(f"Failed to end session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to end session: {str(e)}"
        )


async def get_session_info(
    session_id: str,
    db_pool = Depends(get_db_pool)
) -> SessionInfoResponse:
    """
    Get detailed information about a session
    
    Returns complete session information including statistics.
    """
    try:
        # Initialize session manager
        conversation_sessions = ConversationSessions(db_pool)
        session_manager = SessionManager(conversation_sessions)
        
        # Get session info
        session_info = await session_manager.conversation_sessions.get_session_info(session_id)
        
        if not session_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}"
            )
        
        return SessionInfoResponse(**session_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session info: {str(e)}"
        )


async def get_active_sessions(
    user_id: Optional[str] = None,
    executive_id: Optional[str] = None,
    company_id: Optional[str] = None,
    db_pool = Depends(get_db_pool)
) -> ActiveSessionsResponse:
    """
    Get all active sessions, optionally filtered

    Returns list of all active sessions with optional filtering.
    """
    try:
        # Initialize session manager
        conversation_sessions = ConversationSessions(db_pool)
        session_manager = SessionManager(conversation_sessions)

        # Get active sessions (scoped by company_id if provided)
        sessions = await session_manager.get_active_sessions(
            user_id=user_id,
            executive_id=executive_id,
            company_id=company_id
        )
        
        return ActiveSessionsResponse(
            sessions=sessions,
            count=len(sessions)
        )
        
    except Exception as e:
        logger.error(f"Failed to get active sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active sessions: {str(e)}"
        )


async def get_session_statistics(
    executive_id: Optional[str] = None,
    company_id: Optional[str] = None,
    db_pool = Depends(get_db_pool)
) -> SessionStatsResponse:
    """
    Get session statistics by executive

    Returns aggregated session statistics, scoped by company_id if provided.
    """
    try:
        # Initialize session manager
        conversation_sessions = ConversationSessions(db_pool)
        session_manager = SessionManager(conversation_sessions)

        # Get session statistics (scoped by company_id if provided)
        statistics = await session_manager.get_session_statistics(
            executive_id=executive_id,
            company_id=company_id
        )
        
        return SessionStatsResponse(
            statistics=statistics,
            count=len(statistics)
        )
        
    except Exception as e:
        logger.error(f"Failed to get session statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session statistics: {str(e)}"
        )


async def cleanup_expired_sessions(
    db_pool = Depends(get_db_pool)
) -> JSONResponse:
    """
    Clean up expired sessions (admin endpoint)
    
    Manually triggers cleanup of expired sessions.
    """
    try:
        # Initialize session manager
        conversation_sessions = ConversationSessions(db_pool)
        session_manager = SessionManager(conversation_sessions)
        
        # Expire inactive sessions
        expired_count = await session_manager.conversation_sessions.expire_inactive_sessions()
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "expired_sessions": expired_count,
                "message": f"Expired {expired_count} inactive sessions"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup expired sessions: {str(e)}"
        )