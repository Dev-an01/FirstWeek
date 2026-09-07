"""
Meeting API Endpoints
Handles meeting scheduling and bot management
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional
import uuid
import logging

from services.scheduler_service import get_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["meetings"])


class MeetingCreate(BaseModel):
    """Meeting creation request"""
    executive: str  # Executive name/profile
    platform: str  # Google Meet, Zoom, Teams
    language: Optional[str] = "en"  # Language code (en, ja)
    link: HttpUrl  # Meeting URL
    date: str  # YYYY-MM-DD
    time: str  # HH:MM


class InstantMeetingCreate(BaseModel):
    """Instant meeting creation request - no scheduling needed"""
    executive: str  # Executive name/profile
    platform: str  # Google Meet, Zoom, Teams
    language: Optional[str] = "en"  # Language code (en, ja)
    link: HttpUrl  # Meeting URL


class MeetingResponse(BaseModel):
    """Meeting creation response"""
    success: bool
    meeting_id: str
    message: str
    scheduled_time: str
    bot_join_time: str
    status: str


class InstantBotResponse(BaseModel):
    """Instant meeting response"""
    success: bool
    meeting_id: str
    bot_id: Optional[str] = None
    message: str
    status: str


@router.post("/", response_model=MeetingResponse)
async def create_meeting(meeting: MeetingCreate):
    """
    Create a scheduled meeting and automatically join with bot

    The bot will automatically join 3 minutes before the scheduled time.

    Note: Date and time should be in UTC timezone.
    """
    try:
        # Parse datetime (expects UTC)
        scheduled_time = datetime.strptime(
            f"{meeting.date} {meeting.time}",
            "%Y-%m-%d %H:%M"
        )

        # Validate future time (use UTC)
        if scheduled_time <= datetime.utcnow():
            raise HTTPException(
                status_code=400,
                detail="Meeting time must be in the future"
            )
        
        # Generate meeting ID
        meeting_id = str(uuid.uuid4())
        
        # Schedule with scheduler service
        scheduler = get_scheduler()
        meeting_data = scheduler.schedule_meeting(
            meeting_id=meeting_id,
            meeting_url=str(meeting.link),
            scheduled_time=scheduled_time,
            profile_id=meeting.executive,  # Use selected executive's ID
            executive=meeting.executive,
            platform=meeting.platform,
            language=meeting.language
        )
        
        # Calculate bot join time (3 minutes before)
        from datetime import timedelta
        bot_join_time = scheduled_time - timedelta(minutes=3)
        
        logger.info(f"✅ Meeting created: {meeting_id}")
        logger.info(f"   Platform: {meeting.platform}")
        logger.info(f"   Scheduled: {scheduled_time}")
        
        return MeetingResponse(
            success=True,
            meeting_id=meeting_id,
            message=f"Meeting scheduled successfully! Bot will join at {bot_join_time.strftime('%I:%M %p')}",
            scheduled_time=scheduled_time.isoformat(),
            bot_join_time=bot_join_time.isoformat(),
            status="pending"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date/time format: {e}")
    except Exception as e:
        logger.error(f"Failed to create meeting: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str):
    """Get meeting details and status"""
    scheduler = get_scheduler()
    meeting = scheduler.get_meeting(meeting_id)
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    return {
        "success": True,
        "meeting": meeting
    }


@router.get("/")
async def list_meetings(status: Optional[str] = None):
    """
    List all scheduled meetings
    
    Query params:
    - status: Filter by status (pending, active, completed, failed)
    """
    scheduler = get_scheduler()
    meetings = scheduler.list_meetings(status=status)
    
    return {
        "success": True,
        "count": len(meetings),
        "meetings": meetings
    }


@router.post("/instant", response_model=InstantBotResponse)
async def create_instant_meeting(meeting: InstantMeetingCreate):
    """
    Create an instant meeting - bot joins immediately
    
    No scheduling needed. The bot is created and joins the meeting right away,
    bypassing the cronjob scheduler entirely.
    
    This is ideal for "join now" scenarios where you don't want to wait
    for the scheduler to check for upcoming meetings.
    """
    try:
        # Generate meeting ID
        meeting_id = str(uuid.uuid4())
        
        # Get scheduler instance
        scheduler = get_scheduler()
        
        # Create meeting record with current time
        meeting_data = {
            'meeting_id': meeting_id,
            'meeting_url': str(meeting.link),
            'scheduled_time': datetime.utcnow(),  # Current time (instant)
            'profile_id': meeting.executive,
            'executive': meeting.executive,
            'platform': meeting.platform,
            'language': meeting.language,
            'status': 'pending',
            'created_at': datetime.utcnow(),
        }
        
        # Store in database
        scheduler.db.create_meeting(meeting_data)
        
        # Create bot immediately (bypass scheduler)
        logger.info(f"🚀 Creating instant meeting bot: {meeting_id}")
        logger.info(f"   Platform: {meeting.platform}")
        logger.info(f"   URL: {meeting.link}")
        
        bot_data = await scheduler.create_bot_for_meeting(meeting_id, meeting_data)
        
        return InstantBotResponse(
            success=True,
            meeting_id=meeting_id,
            bot_id=bot_data.get('bot_id'),
            message="Bot is joining the meeting now!",
            status="active"
        )
        
    except Exception as e:
        logger.error(f"Failed to create instant meeting: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create instant meeting: {str(e)}"
        )


@router.delete("/{meeting_id}")
async def cancel_meeting(meeting_id: str):
    """
    Cancel a scheduled meeting
    
    Sets meeting status to 'cancelled' to prevent bot from joining.
    """
    scheduler = get_scheduler()
    meeting = scheduler.get_meeting(meeting_id)
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Only allow cancelling pending meetings
    if meeting['status'] != 'pending':
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel meeting with status: {meeting['status']}"
        )

    # Update status to cancelled in database
    updated_meeting = scheduler.db.update_meeting(meeting_id, {'status': 'cancelled'})

    if not updated_meeting:
        raise HTTPException(status_code=500, detail="Failed to cancel meeting")

    logger.info(f"🚫 Meeting cancelled: {meeting_id}")

    return {
        "success": True,
        "message": "Meeting cancelled successfully",
        "meeting_id": meeting_id
    }
