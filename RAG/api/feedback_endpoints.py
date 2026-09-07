"""
User Feedback API Endpoints
============================

Provides endpoints for:
- Thumbs up/down feedback
- Star ratings
- User comments
- Feedback history

LangSmith Feedback Integration
- Sends feedback to LangSmith for trace analysis
- Links feedback to LangSmith run_id
- Stores feedback in local DB + LangSmith

Usage:
    POST /api/v1/feedback/thumbs-up
    POST /api/v1/feedback/thumbs-down
    POST /api/v1/feedback/rating
    POST /api/v1/feedback/comment
    GET /api/v1/feedback/{request_id}
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from observability.db_persistence import store_user_feedback
from observability.metrics import user_feedback_counter
from observability.logging import StructuredLogger
from observability.context import RequestContext

# LangSmith Feedback Integration
try:
    from langsmith import Client
    LANGSMITH_AVAILABLE = True
    langsmith_client = Client()
except ImportError:
    LANGSMITH_AVAILABLE = False
    langsmith_client = None

logger = StructuredLogger(__name__)

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


# ============================================================
# LANGSMITH FEEDBACK HELPER 
# ============================================================

def send_langsmith_feedback(
    run_id: str,
    feedback_key: str,
    score: float,
    comment: Optional[str] = None
) -> bool:
    """
    Send feedback to LangSmith for a specific run.
    
    Args:
        run_id: LangSmith run ID (from response.metadata.langsmith_run_id)
        feedback_key: Type of feedback ("thumbs_up", "thumbs_down", "rating")
        score: Numeric score (1.0 for thumbs up, 0.0 for thumbs down, 0-1 for ratings)
        comment: Optional user comment
        
    Returns:
        True if feedback sent successfully, False otherwise
    """
    if not LANGSMITH_AVAILABLE:
        logger.debug("LangSmith not available, skipping feedback submission")
        return False
    
    if not run_id:
        logger.debug("No run_id provided, skipping LangSmith feedback")
        return False
    
    try:
        # Send feedback to LangSmith
        langsmith_client.create_feedback(
            run_id=run_id,
            key=feedback_key,
            score=score,
            comment=comment
        )
        
        logger.info(
            "Sent feedback to LangSmith",
            run_id=run_id,
            feedback_key=feedback_key,
            score=score,
            has_comment=bool(comment)
        )
        return True
        
    except Exception as e:
        logger.error(
            "Failed to send feedback to LangSmith",
            run_id=run_id,
            feedback_key=feedback_key,
            error=str(e)
        )
        return False


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class FeedbackRequest(BaseModel):
    """Base feedback request model"""
    request_id: str = Field(..., description="Request ID to provide feedback for")
    executive_id: str = Field(..., description="Executive profile ID")
    user_id: Optional[str] = Field(None, description="User ID (optional)")
    
    # LangSmith Integration
    run_id: Optional[str] = Field(
        None, 
        description="LangSmith run ID for trace linkage (from response.metadata.langsmith_run_id)"
    )


class ThumbsFeedback(FeedbackRequest):
    """Thumbs up/down feedback"""
    pass


class RatingFeedback(FeedbackRequest):
    """Star rating feedback (1-5 stars)"""
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")


class CommentFeedback(FeedbackRequest):
    """User comment feedback"""
    comment: str = Field(..., min_length=1, max_length=5000, description="User comment")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Optional rating")


class FeedbackResponse(BaseModel):
    """Feedback submission response"""
    success: bool
    message: str
    request_id: str
    feedback_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("/thumbs-up", response_model=FeedbackResponse)
async def submit_thumbs_up(feedback: ThumbsFeedback):
    """
    Submit thumbs up feedback.

    This indicates the user found the response helpful.
    
    WEEK 1, DAY 4: Now sends feedback to LangSmith for trace analysis!

    Example:
        ```json
        {
            "request_id": "req_abc123",
            "executive_id": "exec_001_test",
            "user_id": "user_456",
            "run_id": "01234567-89ab-cdef-0123-456789abcdef"
        }
        ```
    """
    try:
        # Store in database
        success = store_user_feedback(
            request_id=feedback.request_id,
            executive_id=feedback.executive_id,
            user_id=feedback.user_id,
            feedback_type="thumbs_up"
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store feedback"
            )

        # Update Prometheus metric
        user_feedback_counter.labels(type="thumbs_up").inc()
        
        # Send feedback to LangSmith
        langsmith_success = send_langsmith_feedback(
            run_id=feedback.run_id,
            feedback_key="thumbs_up",
            score=1.0,
            comment=None
        )

        logger.info(
            "Thumbs up feedback received",
            request_id=feedback.request_id,
            executive_id=feedback.executive_id,
            user_id=feedback.user_id,
            run_id=feedback.run_id,
            langsmith_sent=langsmith_success
        )

        return FeedbackResponse(
            success=True,
            message="Thank you for your feedback!",
            request_id=feedback.request_id,
            feedback_type="thumbs_up"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to process thumbs up feedback",
            request_id=feedback.request_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process feedback: {str(e)}"
        )


@router.post("/thumbs-down", response_model=FeedbackResponse)
async def submit_thumbs_down(feedback: ThumbsFeedback):
    """
    Submit thumbs down feedback.

    This indicates the user found the response unhelpful.
    
    WEEK 1, DAY 4: Now sends feedback to LangSmith for trace analysis!

    Example:
        ```json
        {
            "request_id": "req_abc123",
            "executive_id": "exec_001_test",
            "user_id": "user_456",
            "run_id": "01234567-89ab-cdef-0123-456789abcdef"
        }
        ```
    """
    try:
        # Store in database
        success = store_user_feedback(
            request_id=feedback.request_id,
            executive_id=feedback.executive_id,
            user_id=feedback.user_id,
            feedback_type="thumbs_down"
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store feedback"
            )

        # Update Prometheus metric
        user_feedback_counter.labels(type="thumbs_down").inc()
        
        # Send feedback to LangSmith
        langsmith_success = send_langsmith_feedback(
            run_id=feedback.run_id,
            feedback_key="thumbs_down",
            score=0.0,
            comment=None
        )

        logger.info(
            "Thumbs down feedback received",
            request_id=feedback.request_id,
            executive_id=feedback.executive_id,
            user_id=feedback.user_id,
            run_id=feedback.run_id,
            langsmith_sent=langsmith_success
        )

        return FeedbackResponse(
            success=True,
            message="Thank you for your feedback! We'll work to improve.",
            request_id=feedback.request_id,
            feedback_type="thumbs_down"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to process thumbs down feedback",
            request_id=feedback.request_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process feedback: {str(e)}"
        )


@router.post("/rating", response_model=FeedbackResponse)
async def submit_rating(feedback: RatingFeedback):
    """
    Submit star rating feedback (1-5 stars).
    
    WEEK 1, DAY 4: Now sends feedback to LangSmith for trace analysis!
    Rating is normalized to 0-1 scale for LangSmith.

    Example:
        ```json
        {
            "request_id": "req_abc123",
            "executive_id": "exec_001_test",
            "user_id": "user_456",
            "rating": 5,
            "run_id": "01234567-89ab-cdef-0123-456789abcdef"
        }
        ```
    """
    try:
        # Store in database
        success = store_user_feedback(
            request_id=feedback.request_id,
            executive_id=feedback.executive_id,
            user_id=feedback.user_id,
            feedback_type="rating",
            rating=feedback.rating
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store feedback"
            )

        # Update Prometheus metric (convert rating to thumbs equivalent)
        if feedback.rating >= 4:
            user_feedback_counter.labels(type="thumbs_up").inc()
        elif feedback.rating <= 2:
            user_feedback_counter.labels(type="thumbs_down").inc()
        
        
        # Normalize rating to 0-1 scale (1 star = 0.0, 5 stars = 1.0)
        normalized_score = (feedback.rating - 1) / 4.0
        langsmith_success = send_langsmith_feedback(
            run_id=feedback.run_id,
            feedback_key="rating",
            score=normalized_score,
            comment=f"{feedback.rating} stars"
        )

        logger.info(
            "Rating feedback received",
            request_id=feedback.request_id,
            executive_id=feedback.executive_id,
            user_id=feedback.user_id,
            rating=feedback.rating,
            run_id=feedback.run_id,
            langsmith_sent=langsmith_success
        )

        return FeedbackResponse(
            success=True,
            message=f"Thank you for your {feedback.rating}-star rating!",
            request_id=feedback.request_id,
            feedback_type="rating"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to process rating feedback",
            request_id=feedback.request_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process feedback: {str(e)}"
        )


@router.post("/comment", response_model=FeedbackResponse)
async def submit_comment(feedback: CommentFeedback):
    """
    Submit comment feedback with optional rating.
    
    WEEK 1, DAY 4: Now sends feedback to LangSmith for trace analysis!

    Example:
        ```json
        {
            "request_id": "req_abc123",
            "executive_id": "exec_001_test",
            "user_id": "user_456",
            "comment": "This response was very helpful!",
            "rating": 5,
            "run_id": "01234567-89ab-cdef-0123-456789abcdef"
        }
        ```
    """
    try:
        # Store in database
        success = store_user_feedback(
            request_id=feedback.request_id,
            executive_id=feedback.executive_id,
            user_id=feedback.user_id,
            feedback_type="comment",
            comment=feedback.comment,
            rating=feedback.rating
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store feedback"
            )
        
       
        # If rating provided, use normalized score; otherwise neutral score
        score = (feedback.rating - 1) / 4.0 if feedback.rating else 0.5
        langsmith_success = send_langsmith_feedback(
            run_id=feedback.run_id,
            feedback_key="comment",
            score=score,
            comment=feedback.comment
        )

        logger.info(
            "Comment feedback received",
            request_id=feedback.request_id,
            executive_id=feedback.executive_id,
            user_id=feedback.user_id,
            comment_length=len(feedback.comment),
            rating=feedback.rating,
            run_id=feedback.run_id,
            langsmith_sent=langsmith_success
        )

        return FeedbackResponse(
            success=True,
            message="Thank you for your detailed feedback!",
            request_id=feedback.request_id,
            feedback_type="comment"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to process comment feedback",
            request_id=feedback.request_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process feedback: {str(e)}"
        )
