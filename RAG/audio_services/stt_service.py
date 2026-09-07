"""
Speech-to-Text Service using Faster Whisper

Provides real-time and batch speech transcription with support for:
- English and Japanese languages
- Real-time streaming with VAD (Voice Activity Detection)
- Batch file transcription
- Low VRAM usage (base model)
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, AsyncIterator
import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class STTServiceError(Exception):
    """Exception raised for STT service errors"""
    pass


class FasterWhisperSTT:
    """
    Faster Whisper STT Service
    
    Features:
    - Uses Whisper base model (lowest VRAM: ~1GB)
    - Real-time transcription with VAD
    - Support for English (en) and Japanese (ja)
    - Model loaded once and cached
    """
    
    _instance = None
    _model = None
    _model_path = "/app/models/whisper/base"
    
    def __new__(cls):
        """Singleton pattern - load model only once"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Faster Whisper STT service"""
        if self._model is None:
            self._load_model()
    
    def _load_model(self):
        """Load Whisper model (once per application lifecycle)"""
        try:
            logger.info(f"Loading Whisper base model...")

            # Determine device from environment (matches docker-compose EMBEDDING_DEVICE)
            device = os.environ.get("EMBEDDING_DEVICE", "cuda")

            if device == "cpu":
                compute_type = "int8"
                logger.info("Using CPU mode (EMBEDDING_DEVICE=cpu)")
            else:
                compute_type = "float16"
                logger.info("Using CUDA mode")

            self._model = WhisperModel(
                "base",                   # Model size
                device=device,
                compute_type=compute_type,
                cpu_threads=4,
                num_workers=1,            # Single worker for streaming
                download_root="/app/models/whisper"  # Where models are cached
            )

            logger.info("✅ Whisper base model loaded successfully")
            logger.info(f"   - Device: {device}")
            logger.info(f"   - Compute type: {compute_type}")
            logger.info("   - Processing time: ~50-100ms per utterance")
            logger.info("   - Supported languages: en (English), ja (Japanese)")

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise STTServiceError(f"Model loading failed: {e}")

    async def warmup(self):
        """Warm up the model with a dummy transcription to load into GPU/VRAM"""
        logger.info("🔥 Warming up STT model on GPU...")
        try:
            # Create 1 second of silence
            dummy_audio = np.zeros(16000, dtype=np.int16)
            await self.transcribe_stream(dummy_audio, language="en")
            logger.info("✅ STT model warmed up successfully")
        except Exception as e:
            logger.warning(f"⚠️ STT model warmup failed: {e}")
    
    async def transcribe_file(
        self,
        audio_path: str,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Transcribe audio file (batch mode)
        
        Args:
            audio_path: Path to audio file
            language: Language code ('en' or 'ja')
        
        Returns:
            Dict with transcript, language, and segments
        """
        try:
            logger.info(f"Transcribing file: {audio_path} (language: {language})")
            
            # Run transcription in thread pool to not block event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                audio_path,
                language
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise STTServiceError(f"Transcription failed: {e}")
    
    def _transcribe_sync(self, audio_path: str, language: str) -> Dict[str, Any]:
        """Synchronous transcription (called in thread pool)"""
        segments, info = self._model.transcribe(
            audio_path,
            language=language,
            beam_size=5,           # Good balance of speed/accuracy
            vad_filter=True,       # Remove silence
            vad_parameters=dict(
                min_silence_duration_ms=500
            ),
            temperature=0.0        # Deterministic output
        )
        
        # Collect all segments
        all_segments = []
        full_transcript = ""
        
        for segment in segments:
            all_segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            })
            full_transcript += segment.text + " "
        
        return {
            "transcript": full_transcript.strip(),
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
            "segments": all_segments
        }
    
    async def transcribe_stream(
        self,
        audio_segment: np.ndarray,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Transcribe audio segment (for real-time streaming)
        
        Args:
            audio_segment: Numpy array of audio samples (int16, 16kHz)
            language: Language code ('en' or 'ja')
        
        Returns:
            Dict with transcript and segments
        """
        try:
            # Run in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._transcribe_segment_sync,
                audio_segment,
                language
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Stream transcription failed: {e}")
            raise STTServiceError(f"Stream transcription failed: {e}")
    
    def _transcribe_segment_sync(
        self,
        audio_segment: np.ndarray,
        language: str
    ) -> Dict[str, Any]:
        """Transcribe audio segment synchronously"""
        # Convert int16 to float32 (Whisper expects float32)
        audio_float = audio_segment.astype(np.float32) / 32768.0
        
        segments, info = self._model.transcribe(
            audio_float,
            language=language,
            beam_size=1,           # Greedy decoding (fastest for streaming)
            vad_filter=True,
            temperature=0.0
        )
        
        # Collect segments
        transcript = ""
        for segment in segments:
            transcript += segment.text + " "
        
        return {
            "transcript": transcript.strip(),
            "language": language
        }
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "service": "faster_whisper",
            "model_size": "base",
            "vram_usage": "~1GB",
            "supported_languages": ["en", "ja"],
            "features": [
                "real_time_streaming",
                "batch_transcription",
                "vad_filtering",
                "japanese_support"
            ],
            "model_path": self._model_path
        }


# Global singleton instance
_stt_service: Optional[FasterWhisperSTT] = None


def get_stt_service() -> FasterWhisperSTT:
    """Get singleton STT service instance"""
    global _stt_service
    if _stt_service is None:
        _stt_service = FasterWhisperSTT()
    return _stt_service
