"""
TTS Service Manager - Singleton with GPU Semaphore

Manages a single shared TTS service instance across all requests with:
- GPU access control via asyncio.Semaphore
- Shared Kokoro pipelines (initialized once)
- Thread-safe concurrent access
- Resource-efficient design
"""

import asyncio
import logging
from typing import Optional, Dict, Any, AsyncGenerator
from pathlib import Path

logger = logging.getLogger(__name__)


class TTSServiceManager:
    """
    Singleton manager for TTS service with GPU semaphore.

    Ensures:
    1. Only ONE TTS service instance exists (shared pipelines)
    2. Only ONE request uses GPU at a time (via semaphore)
    3. Other requests queue up and wait their turn
    """

    _instance: Optional['TTSServiceManager'] = None
    _lock = asyncio.Lock()

    def __init__(self):
        """Private constructor - use get_instance() instead."""
        if TTSServiceManager._instance is not None:
            raise RuntimeError("Use TTSServiceManager.get_instance() instead of constructor")

        self._gpu_semaphore = asyncio.Semaphore(4)

        # Shared TTS service (initialized once)
        self._tts_service = None

        # Statistics
        self._active_requests = 0
        self._total_requests = 0
        self._queue_stats = {
            'max_queue_size': 0,
            'total_wait_time_ms': 0
        }

        logger.info("TTSServiceManager initialized with GPU semaphore (max_concurrent=4)")

    @classmethod
    async def get_instance(cls) -> 'TTSServiceManager':
        """Get or create the singleton instance (thread-safe)."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def _initialize_tts_service(self):
        """Initialize the shared TTS service based on DEFAULT_TTS_PROVIDER env variable."""
        if self._tts_service is None:
            import os
            provider = os.getenv('DEFAULT_TTS_PROVIDER', 'chirp3_instant')

            logger.info(f"🎙️ Initializing TTS provider: {provider}")

            if provider == 'chirp3_instant':
                from audio_services.chirp3_instant_service import GoogleChirp3InstantService
                self._tts_service = GoogleChirp3InstantService()
                self._current_provider = 'chirp3_instant'
                logger.info("✅ Google Chirp 3 Instant TTS initialized")

            elif provider == 'kokoro':
                from audio_services.realtime_tts_service import RealtimeTTSService
                self._tts_service = RealtimeTTSService(
                    primary_engine="kokoro",
                    voice_config={}
                )
                self._current_provider = 'kokoro'
                logger.info("✅ Kokoro TTS initialized")

            else:
                raise ValueError(
                    f"Unknown TTS provider: '{provider}'. "
                    "Valid options: 'kokoro' or 'chirp3_instant'"
                )

    async def warmup(self):
        """
        Trigger warmup of the underlying TTS service.
        """
        # Ensure service is initialized
        await self._initialize_tts_service()
        
        # Call warmup on the service if supported
        if hasattr(self._tts_service, 'warmup'):
            await self._tts_service.warmup()

    async def synthesize_with_gpu_lock(
        self,
        text: str,
        voice_config: Optional[Dict[str, Any]] = None,
        is_last_sentence: bool = True
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text with GPU semaphore protection.

        This method:
        1. Waits in queue if GPU is busy
        2. Acquires GPU lock
        3. Performs synthesis
        4. Releases GPU lock
        5. Next request proceeds

        Args:
            text: Text to synthesize
            voice_config: Voice configuration
            is_last_sentence: Whether this is the last sentence

        Yields:
            Audio frames (PCM bytes)
        """
        import time

        # Ensure TTS service is initialized
        await self._initialize_tts_service()

        # Track stats
        self._total_requests += 1
        request_id = self._total_requests

        # Queue position before acquiring semaphore
        queue_size = self._gpu_semaphore._value  # 0 if GPU busy, 1 if free
        waiting = 0 if queue_size > 0 else 1

        logger.info(f"[TTS-{request_id}] Waiting for GPU (queue position: {waiting})")

        wait_start = time.time()

        # Acquire GPU semaphore (blocks here if GPU is busy)
        async with self._gpu_semaphore:
            wait_time_ms = (time.time() - wait_start) * 1000

            self._active_requests += 1
            self._queue_stats['total_wait_time_ms'] += wait_time_ms

            if wait_time_ms > 10:
                logger.info(f"[TTS-{request_id}] GPU acquired after {wait_time_ms:.0f}ms wait")
            else:
                logger.info(f"[TTS-{request_id}] GPU acquired immediately")

            try:
                # Perform TTS synthesis with GPU
                async for audio_frame in self._tts_service.synthesize_stream(
                    text=text,
                    voice_config=voice_config,
                    is_last_sentence=is_last_sentence
                ):
                    yield audio_frame

            finally:
                self._active_requests -= 1
                logger.info(f"[TTS-{request_id}] GPU released (active: {self._active_requests})")

    def get_audio_format(self) -> Dict[str, Any]:
        """Get audio format from TTS service."""
        if self._tts_service:
            return self._tts_service.get_audio_format()
        return {
            'sample_rate': 24000,
            'encoding': 'LINEAR16',
            'channels': 1,
            'bits_per_sample': 16,
            'frame_size': 480
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            'active_requests': self._active_requests,
            'total_requests': self._total_requests,
            'gpu_available': self._gpu_semaphore._value > 0,
            'queue_stats': self._queue_stats
        }


# Global accessor function
async def get_tts_manager() -> TTSServiceManager:
    """Get the singleton TTS manager instance."""
    return await TTSServiceManager.get_instance()
