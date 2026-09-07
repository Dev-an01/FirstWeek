"""
Connection Manager with State Machine

Manages streaming session lifecycle with formal state tracking,
interruption handling, and cleanup mechanisms.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session states for audio streaming"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    READY = "ready"
    STREAMING = "streaming"
    INTERRUPTED = "interrupted"
    ERROR = "error"


@dataclass
class SessionMetrics:
    """Session performance metrics"""
    session_id: str
    started_at: datetime
    frames_sent: int = 0
    text_tokens_sent: int = 0
    interruptions: int = 0
    errors: int = 0
    last_activity: Optional[datetime] = None

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()


class ConnectionManager:
    """
    Manages streaming session state and lifecycle.

    Features:
    - Formal state machine (READY → STREAMING → INTERRUPTED)
    - Interruption handling (clear buffers, stop generation)
    - Session metrics tracking
    - Cleanup on session end
    """

    def __init__(self, session_id: str):
        """
        Initialize connection manager.

        Args:
            session_id: Unique session identifier
        """
        self.session_id = session_id
        self.state = SessionState.DISCONNECTED
        self.metrics = SessionMetrics(
            session_id=session_id,
            started_at=datetime.now()
        )

        # Interruption control
        self.interrupt_flag = asyncio.Event()
        self.generation_task: Optional[asyncio.Task] = None

        # Audio buffers
        self.audio_buffer = []
        self.text_buffer = ""

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        logger.info(f"[{session_id}] ConnectionManager initialized")

    async def transition_to(self, new_state: SessionState):
        """
        Transition to a new state.

        Args:
            new_state: Target state
        """
        async with self._lock:
            old_state = self.state
            self.state = new_state
            self.metrics.update_activity()
            logger.info(f"[{self.session_id}] State transition: {old_state.value} → {new_state.value}")

    async def connect(self):
        """Initialize connection and transition to READY"""
        await self.transition_to(SessionState.CONNECTING)
        # Perform any connection setup here
        await self.transition_to(SessionState.READY)

    async def start_streaming(self):
        """Start streaming session"""
        if self.state != SessionState.READY:
            raise RuntimeError(f"Cannot start streaming from state: {self.state.value}")

        await self.transition_to(SessionState.STREAMING)
        self.interrupt_flag.clear()
        logger.info(f"[{self.session_id}] Streaming started")

    async def interrupt(self):
        """
        Handle user interruption.

        Actions:
        1. Set interrupt flag
        2. Cancel generation task
        3. Clear all buffers
        4. Transition to INTERRUPTED state
        5. Return to READY
        """
        logger.warning(f"[{self.session_id}] 🛑 INTERRUPTION REQUESTED")

        # Set interrupt flag immediately
        self.interrupt_flag.set()
        self.metrics.interruptions += 1

        # Cancel ongoing generation
        if self.generation_task and not self.generation_task.done():
            logger.info(f"[{self.session_id}] Cancelling generation task...")
            self.generation_task.cancel()
            try:
                await self.generation_task
            except asyncio.CancelledError:
                logger.info(f"[{self.session_id}] Generation task cancelled")

        # Clear all buffers
        await self.clear_buffers()

        # Transition states
        await self.transition_to(SessionState.INTERRUPTED)
        await asyncio.sleep(0.1)  # Brief pause
        await self.transition_to(SessionState.READY)

        logger.info(f"[{self.session_id}] ✅ Interruption complete, session ready")

    async def clear_buffers(self):
        """Clear all audio and text buffers"""
        async with self._lock:
            cleared_audio = len(self.audio_buffer)
            cleared_text = len(self.text_buffer)

            self.audio_buffer.clear()
            self.text_buffer = ""

            logger.info(
                f"[{self.session_id}] Buffers cleared: "
                f"{cleared_audio} audio frames, {cleared_text} text chars"
            )

    def is_interrupted(self) -> bool:
        """Check if session is interrupted"""
        return self.interrupt_flag.is_set()

    async def add_audio_frame(self, frame: bytes):
        """Add audio frame to buffer"""
        if not self.is_interrupted():
            async with self._lock:
                self.audio_buffer.append(frame)
                self.metrics.frames_sent += 1
                self.metrics.update_activity()

    async def add_text_token(self, token: str):
        """Add text token to buffer"""
        if not self.is_interrupted():
            async with self._lock:
                self.text_buffer += token
                self.metrics.text_tokens_sent += 1
                self.metrics.update_activity()

    async def get_audio_frames(self) -> list:
        """Get and clear audio frames"""
        async with self._lock:
            frames = self.audio_buffer.copy()
            self.audio_buffer.clear()
            return frames

    async def end_streaming(self):
        """End streaming session gracefully"""
        if self.state == SessionState.STREAMING:
            await self.transition_to(SessionState.READY)
            logger.info(f"[{self.session_id}] Streaming ended gracefully")

    async def disconnect(self):
        """Disconnect and cleanup"""
        await self.clear_buffers()
        await self.transition_to(SessionState.DISCONNECTED)

        duration = (datetime.now() - self.metrics.started_at).total_seconds()
        logger.info(
            f"[{self.session_id}] Session ended: "
            f"duration={duration:.1f}s, "
            f"frames={self.metrics.frames_sent}, "
            f"tokens={self.metrics.text_tokens_sent}, "
            f"interruptions={self.metrics.interruptions}"
        )

    async def handle_error(self, error: Exception):
        """Handle error state"""
        logger.error(f"[{self.session_id}] Error occurred: {error}", exc_info=True)
        self.metrics.errors += 1
        await self.transition_to(SessionState.ERROR)
        await self.clear_buffers()

    def get_state(self) -> SessionState:
        """Get current state"""
        return self.state

    def get_metrics(self) -> Dict[str, Any]:
        """Get session metrics"""
        return {
            'session_id': self.metrics.session_id,
            'state': self.state.value,
            'started_at': self.metrics.started_at.isoformat(),
            'frames_sent': self.metrics.frames_sent,
            'tokens_sent': self.metrics.text_tokens_sent,
            'interruptions': self.metrics.interruptions,
            'errors': self.metrics.errors,
            'last_activity': self.metrics.last_activity.isoformat() if self.metrics.last_activity else None
        }
