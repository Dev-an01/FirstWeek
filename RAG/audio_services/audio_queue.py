"""
Audio Queue Management

In-memory queue for audio frames with 2-second block processing.
Thread-safe operations for producer-consumer pattern.
"""

import asyncio
import logging
from collections import deque
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime

from audio_services.config import AUDIO_QUEUE_CONFIG, AUDIO_SPECS

logger = logging.getLogger(__name__)


@dataclass
class AudioBlock:
    """2-second audio block for processing"""
    frames: List[bytes]
    frame_count: int
    created_at: datetime
    duration_ms: float

    @property
    def total_bytes(self) -> int:
        """Total bytes in block"""
        return sum(len(frame) for frame in self.frames)


class AudioQueue:
    """
    Thread-safe audio queue with 2-second block management.

    Features:
    - In-memory buffer using collections.deque
    - Accumulates frames into 2-second blocks (100 frames)
    - Thread-safe push/pop operations
    - Frame cache strategy (reserve buffer before stable push)
    - Automatic cleanup of processed frames
    """

    def __init__(self, block_size: Optional[int] = None):
        """
        Initialize audio queue.

        Args:
            block_size: Frames per block (default: 100 frames = 2 seconds @ 50 FPS)
        """
        self.block_size = block_size or AUDIO_QUEUE_CONFIG['block_size']
        self.max_queue_size = AUDIO_QUEUE_CONFIG['max_queue_size']
        self.frame_cache_size = AUDIO_QUEUE_CONFIG['frame_cache_size']

        # Main queue for incoming frames
        self.queue = deque(maxlen=self.max_queue_size)

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        # Metrics
        self.frames_received = 0
        self.frames_processed = 0
        self.blocks_created = 0

        logger.info(
            f"AudioQueue initialized: "
            f"block_size={self.block_size} frames, "
            f"max_queue_size={self.max_queue_size}"
        )

    async def push_frame(self, frame: bytes):
        """
        Add audio frame to queue.

        Args:
            frame: PCM audio frame (441 samples @ 22.05kHz = 20ms)
        """
        async with self._lock:
            if len(self.queue) >= self.max_queue_size:
                logger.warning("Audio queue full, dropping oldest frame")
                self.queue.popleft()

            self.queue.append(frame)
            self.frames_received += 1

    async def push_frames(self, frames: List[bytes]):
        """
        Add multiple audio frames to queue.

        Args:
            frames: List of PCM audio frames
        """
        async with self._lock:
            for frame in frames:
                if len(self.queue) >= self.max_queue_size:
                    logger.warning("Audio queue full, dropping oldest frame")
                    self.queue.popleft()

                self.queue.append(frame)
                self.frames_received += 1

    async def get_block(self) -> Optional[AudioBlock]:
        """
        Get a 2-second audio block if enough frames are available.

        Returns:
            AudioBlock with frames, or None if insufficient frames

        Strategy:
        - Check if at least block_size frames available
        - Reserve frame_cache_size frames for stability
        - Extract block_size frames
        - Return as AudioBlock
        """
        async with self._lock:
            # Need block_size + cache_size for stable push
            required_frames = self.block_size + self.frame_cache_size

            if len(self.queue) < required_frames:
                return None

            # Extract block_size frames
            frames = []
            for _ in range(self.block_size):
                frames.append(self.queue.popleft())
                self.frames_processed += 1

            self.blocks_created += 1

            block = AudioBlock(
                frames=frames,
                frame_count=len(frames),
                created_at=datetime.now(),
                duration_ms=len(frames) * AUDIO_SPECS['frame_duration_ms']
            )

            logger.debug(
                f"Created audio block: {block.frame_count} frames, "
                f"{block.duration_ms:.1f}ms, {block.total_bytes} bytes"
            )

            return block

    async def get_all_frames(self) -> List[bytes]:
        """
        Get all frames from queue (for immediate streaming without blocking).

        Returns:
            List of all frames in queue
        """
        async with self._lock:
            frames = list(self.queue)
            self.queue.clear()
            self.frames_processed += len(frames)
            return frames

    async def has_complete_block(self) -> bool:
        """Check if a complete block is available"""
        async with self._lock:
            required_frames = self.block_size + self.frame_cache_size
            return len(self.queue) >= required_frames

    async def get_frame_count(self) -> int:
        """Get current number of frames in queue"""
        async with self._lock:
            return len(self.queue)

    async def clear(self):
        """Clear all frames from queue"""
        async with self._lock:
            cleared = len(self.queue)
            self.queue.clear()
            logger.info(f"AudioQueue cleared: {cleared} frames removed")

    async def get_metrics(self) -> dict:
        """Get queue metrics"""
        async with self._lock:
            return {
                'queue_size': len(self.queue),
                'frames_received': self.frames_received,
                'frames_processed': self.frames_processed,
                'blocks_created': self.blocks_created,
                'block_size': self.block_size,
                'utilization': len(self.queue) / self.max_queue_size if self.max_queue_size > 0 else 0
            }

    def __len__(self) -> int:
        """Get queue size"""
        return len(self.queue)
