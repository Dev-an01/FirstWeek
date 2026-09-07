"""
Meeting Scheduler Service
Automatically creates Recall.ai bots for scheduled meetings
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services.meetings_db import get_meetings_db

logger = logging.getLogger(__name__)


class MeetingScheduler:
    """Handles automatic bot creation for scheduled meetings"""

    def __init__(self, recall_service_url: str = "http://recall-service:3003"):
        self.recall_service_url = recall_service_url
        self.scheduler = AsyncIOScheduler()
        self.join_advance_minutes = 3  # Join 3 minutes before meeting
        self.db = get_meetings_db()  # Database client

        logger.info(f"MeetingScheduler initialized with Recall service: {recall_service_url}")
    
    def start(self):
        """Start the scheduler"""
        # Run every minute to check for upcoming meetings
        self.scheduler.add_job(
            self.check_upcoming_meetings,
            trigger=CronTrigger(minute='*'),  # Every minute
            id='check_meetings',
            name='Check upcoming meetings',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("✅ Meeting scheduler started (runs every minute)")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Meeting scheduler stopped")
    
    async def check_upcoming_meetings(self):
        """
        Check for meetings starting soon and create bots
        Runs every minute via cron trigger
        """
        try:
            now = datetime.utcnow()  # Use UTC consistently
            target_time = now + timedelta(minutes=self.join_advance_minutes)

            # Get all pending meetings from database
            pending_meetings = self.db.list_meetings(status='pending')

            # Find meetings that need bots created
            meetings_to_join = []
            for meeting in pending_meetings:
                scheduled_time = meeting['scheduled_time']

                # Check if meeting is within join window (0-5 minutes from now)
                # This allows catching meetings scheduled close to current time
                time_until_meeting = (scheduled_time - now).total_seconds() / 60

                if 0 <= time_until_meeting <= 5:
                    meetings_to_join.append((meeting['meeting_id'], meeting))
            
            # Create bots for meetings
            if meetings_to_join:
                logger.info(f"🤖 Creating bots for {len(meetings_to_join)} upcoming meetings")
                
                for meeting_id, meeting in meetings_to_join:
                    await self.create_bot_for_meeting(meeting_id, meeting)
                    
        except Exception as e:
            logger.error(f"Error in check_upcoming_meetings: {e}", exc_info=True)
    
    async def create_bot_for_meeting(self, meeting_id: str, meeting: dict) -> dict:
        """Create Recall.ai bot for a specific meeting
        
        Returns:
            dict: Bot data including bot_id
        """
        try:
            logger.info(f"Creating bot for meeting: {meeting_id}")
            logger.info(f"   Meeting URL: {meeting['meeting_url']}")
            logger.info(f"   Scheduled time: {meeting['scheduled_time']}")
            
            # Call Recall service to create bot
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "meeting_url": meeting['meeting_url'],
                    "profile_id": meeting.get('profile_id', 'exec_001_test'),
                    "options": {
                        "language": meeting.get('language', 'en')
                    }
                }
                
                response = await client.post(
                    f"{self.recall_service_url}/api/bot/create",
                    json=payload
                )
                
                response.raise_for_status()
                bot_data = response.json()

                # Update meeting status in database
                self.db.update_meeting(meeting_id, {
                    'status': 'active',
                    'bot_id': bot_data.get('bot_id')
                })

                logger.info(f"✅ Bot created successfully!")
                logger.info(f"   Bot ID: {bot_data.get('bot_id')}")
                logger.info(f"   Meeting: {meeting_id}")
                
                return bot_data  # Return bot data for instant meetings

        except httpx.HTTPError as e:
            logger.error(f"Failed to create bot for meeting {meeting_id}: {e}")
            self.db.update_meeting(meeting_id, {
                'status': 'failed'
            })
            raise  # Re-raise for instant meetings to handle
        except Exception as e:
            logger.error(f"Unexpected error creating bot: {e}", exc_info=True)
            self.db.update_meeting(meeting_id, {
                'status': 'failed'
            })
            raise  # Re-raise for instant meetings to handle
    
    def schedule_meeting(
        self,
        meeting_id: str,
        meeting_url: str,
        scheduled_time: datetime,
        profile_id: str = "exec_001_test",
        **kwargs
    ) -> dict:
        """
        Schedule a new meeting for bot joining
        
        Args:
            meeting_id: Unique meeting identifier
            meeting_url: Google Meet/Zoom/Teams URL
            scheduled_time: When the meeting starts
            profile_id: Executive profile ID
            **kwargs: Additional meeting metadata
        
        Returns:
            Meeting data dictionary
        """
        meeting_data = {
            'meeting_id': meeting_id,
            'meeting_url': meeting_url,
            'scheduled_time': scheduled_time,
            'profile_id': profile_id,
            'status': 'pending',  # pending, active, completed, failed
            'bot_id': None,
            'created_at': datetime.utcnow(),
            **kwargs
        }

        # Store in database
        result = self.db.create_meeting(meeting_data)

        logger.info(f"📅 Meeting scheduled: {meeting_id}")
        logger.info(f"   URL: {meeting_url}")
        logger.info(f"   Time: {scheduled_time}")
        logger.info(f"   Bot will join at: {scheduled_time - timedelta(minutes=self.join_advance_minutes)}")

        return result

    def get_meeting(self, meeting_id: str) -> Optional[dict]:
        """Get meeting details"""
        return self.db.get_meeting(meeting_id)

    def list_meetings(self, status: Optional[str] = None) -> List[dict]:
        """List all meetings, optionally filtered by status"""
        return self.db.list_meetings(status=status)


# Global singleton
_scheduler: Optional[MeetingScheduler] = None


def get_scheduler() -> MeetingScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = MeetingScheduler()
    return _scheduler


def start_scheduler():
    """Start the global scheduler"""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None
