"""
Real-Time STT with Voice Activity Detection (VAD)

Processes continuous audio streams and detects when user finishes speaking.
"""

import asyncio
import logging
from collections import deque
from typing import AsyncIterator, Callable, Optional
import numpy as np
import webrtcvad

from audio_services.stt_service import get_stt_service, STTServiceError

logger = logging.getLogger(__name__)


class RealTimeSTT:
    """
    Real-time STT with VAD for detecting speech boundaries
    
    Features:
    - Continuous audio buffering
    - Voice Activity Detection (VAD)
    - Automatic utterance detection (silence = end of speech)
    - Async processing
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration_ms: int = 100,
        silence_threshold_ms: int = 500,
        vad_aggressiveness: int = 3  # Increased to 3 (most aggressive) to filter noise
    ):
        """
        Initialize real-time STT
        
        Args:
            sample_rate: Audio sample rate (16000 recommended)
            chunk_duration_ms: Duration of each audio chunk in milliseconds
            silence_threshold_ms: Silence duration to trigger transcription
            vad_aggressiveness: VAD sensitivity (0-3, higher = more aggressive)
        """
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.silence_threshold_ms = silence_threshold_ms
        
        # Initialize VAD
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        
        # Get STT service (singleton)
        self.stt_service = get_stt_service()
        
        logger.info(f"RealTimeSTT initialized:")
        logger.info(f"  - Sample rate: {sample_rate}Hz")
        logger.info(f"  - Chunk duration: {chunk_duration_ms}ms")
        logger.info(f"  - Silence threshold: {silence_threshold_ms}ms")
        logger.info(f"  - VAD aggressiveness: {vad_aggressiveness}")
    
    async def process_audio_stream(
        self,
        audio_stream: AsyncIterator[np.ndarray],
        on_transcript: Callable,
        language_getter: Callable = None
    ):
        """
        Process continuous audio stream with VAD
        
        Args:
            audio_stream: AsyncIterator yielding audio chunks (np.ndarray, int16)
            on_transcript: Callback function(transcript_dict) called on complete utterance
            language_getter: Callable that returns current language ('en' or 'ja')
        """
        audio_buffer = deque()
        silence_duration = 0
        
        # Default language getter
        if language_getter is None:
            language_getter = lambda: "en"
        
        logger.info(f"Starting audio stream processing")
        
        try:
            async for chunk in audio_stream:
                # Ensure chunk is int16
                if chunk.dtype != np.int16:
                    chunk = chunk.astype(np.int16)

                # Check for massive DC offset (all positive or all negative)
                # This fixes issues where some browsers/mics send rectified audio or large offsets
                # which confuse VAD into thinking it's constant speech.
                if chunk.size > 0:
                    min_val, max_val = chunk.min(), chunk.max()
                    if min_val >= 0 and max_val > 0:
                        # Rectified/Positive-only signal detected
                         # Center the signal
                        chunk = chunk - np.mean(chunk).astype(np.int16)
                        # logger.warning(f"Detected positive-only audio (DC offset). Centered from [{min_val}, {max_val}] to [{chunk.min()}, {chunk.max()}]")
                
                # Check if speech present using VAD
                is_speech = self._is_speech(chunk)
                
                if is_speech:
                    # User is speaking - buffer audio
                    audio_buffer.append(chunk)
                    silence_duration = 0
                    
                elif len(audio_buffer) > 0:
                    # Silence detected and we have buffered audio
                    silence_duration += self.chunk_duration_ms
                    
                    if silence_duration >= self.silence_threshold_ms:
                        # Utterance complete! Get current language and transcribe
                        current_language = language_getter()
                        complete_audio = np.concatenate(audio_buffer)
                        
                        logger.debug(f"Utterance detected: {len(complete_audio)} samples "
                                   f"({len(complete_audio)/self.sample_rate:.2f}s), language={current_language}")
                        
                        # Transcribe asynchronously
                        try:
                            result = await self.stt_service.transcribe_stream(
                                complete_audio,
                                language=current_language
                            )
                            
                            # Call callback with transcript
                            if result["transcript"].strip():
                                await on_transcript(result)
                                logger.info(f"📝 Transcript ({current_language}): {result['transcript']}")
                            
                        except Exception as e:
                            logger.error(f"Transcription error: {e}")
                        
                        # Clear buffer
                        audio_buffer.clear()
                        silence_duration = 0
        
        except Exception as e:
            logger.error(f"Audio stream processing error: {e}")
            raise
    
    def _is_speech(self, audio_chunk: np.ndarray) -> bool:
        """
        Check if audio chunk contains speech using VAD
        
        Args:
            audio_chunk: Audio samples (int16)
        
        Returns:
            True if speech detected, False otherwise
        """
        try:
            # VAD requires bytes
            audio_bytes = audio_chunk.tobytes()
            
            # Check speech (VAD expects specific frame sizes: 10, 20, or 30ms)
            # We're using 100ms chunks, so we check the first 30ms
            frame_size_30ms = int(self.sample_rate * 0.03)  # 480 samples at 16kHz
            
            if len(audio_chunk) >= frame_size_30ms:
                frame_bytes = audio_chunk[:frame_size_30ms].tobytes()
                return self.vad.is_speech(frame_bytes, self.sample_rate)
            else:
                # Chunk too small, assume not speech
                return False
                
        except Exception as e:
            logger.debug(f"VAD check failed: {e}")
            # On error, assume speech to be safe
            return True


# Global singleton
_realtime_stt: Optional[RealTimeSTT] = None


def get_realtime_stt() -> RealTimeSTT:
    """Get singleton RealTimeSTT instance"""
    global _realtime_stt
    if _realtime_stt is None:
        _realtime_stt = RealTimeSTT()
    return _realtime_stt
