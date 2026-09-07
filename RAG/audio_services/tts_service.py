"""
Google Cloud Text-to-Speech Service

Provides text-to-speech conversion using GCP TTS API with streaming support.
Includes support for GCP Chirp 3 Instant (ultra-low latency, voice cloning).
"""

import os
import time
import logging
from typing import AsyncGenerator, Optional, Dict, Any
from pathlib import Path
import asyncio

from audio_services.base_tts_service import BaseTTSService, TTSServiceError
from audio_services.config import GCP_TTS_CONFIG, AUDIO_SPECS

try:
    from google.cloud import texttospeech
    GCP_TTS_AVAILABLE = True
except ImportError:
    GCP_TTS_AVAILABLE = False
    texttospeech = None

logger = logging.getLogger(__name__)


class GCPTextToSpeechService(BaseTTSService):
    """
    Google Cloud Text-to-Speech service with streaming and voice cloning support.

    Features:
    - Standard neural voices (Neural2, Studio)
    - GCP Chirp 3 Instant (ultra-low latency, voice cloning - when available)
    - 22.05kHz LINEAR16 mono format (matching Piper output)
    - Streaming audio synthesis
    - Executive voice cloning support (Chirp 3)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize GCP Text-to-Speech service.

        Args:
            config: Optional configuration overrides (credentials_path, voice_name, etc.)

        Raises:
            TTSServiceError: If google-cloud-texttospeech not installed or auth fails
        """
        if not GCP_TTS_AVAILABLE:
            raise TTSServiceError(
                "google-cloud-texttospeech package not installed. "
                "Install with: pip install google-cloud-texttospeech>=2.14.0"
            )

        self.config = {**GCP_TTS_CONFIG, **(config or {})}

        # Set credentials path if provided
        if self.config.get('credentials_path'):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.config['credentials_path']

        # Initialize GCP TTS client
        try:
            self.client = texttospeech.TextToSpeechAsyncClient()
            logger.info("GCP Text-to-Speech client initialized")
        except Exception as e:
            raise TTSServiceError(f"Failed to initialize GCP TTS client: {e}")

        # Audio format specs (matching AUDIO_SPECS)
        self.sample_rate = AUDIO_SPECS['sample_rate']  # 22050 Hz
        self.channels = AUDIO_SPECS['channels']  # 1 (mono)
        self.bit_depth = AUDIO_SPECS['bit_depth']  # 16
        self.frame_size = AUDIO_SPECS['frame_size']  # 441 samples
        self.frame_bytes = self.frame_size * (self.bit_depth // 8)

        logger.info(f"GCP TTS configured:")
        logger.info(f"  Voice: {self.config['voice_name']}")
        logger.info(f"  Language: {self.config['language_code']}")
        logger.info(f"  Sample rate: {self.sample_rate} Hz")
        logger.info(f"  Format: {self.bit_depth}-bit PCM, {self.channels} channel(s)")

    async def synthesize_stream(
        self,
        text: str,
        voice_config: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to speech and stream audio chunks.

        Args:
            text: Text to synthesize
            voice_config: Optional voice configuration:
                - voice_name: str (e.g., 'en-US-Neural2-C')
                - language_code: str (e.g., 'en-US')
                - profile_id: str (for voice cloning with Chirp 3)

        Yields:
            PCM audio frames (22050Hz, 16-bit, mono, 441 samples per frame)

        Raises:
            TTSServiceError: If synthesis fails
        """
        if not text.strip():
            return

        try:
            # Merge voice config
            voice_settings = {**self.config, **(voice_config or {})}

            # Build synthesis input
            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Build voice selection
            voice = texttospeech.VoiceSelectionParams(
                language_code=voice_settings['language_code'],
                name=voice_settings['voice_name']
            )

            # Build audio config
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.sample_rate,
                speaking_rate=voice_settings['speaking_rate'],
                pitch=voice_settings['pitch'],
                volume_gain_db=voice_settings['volume_gain_db']
            )

            logger.info(f"Synthesizing with GCP TTS: '{text[:50]}...'")

            # Call GCP TTS API
            response = await self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            # Stream audio in frames
            audio_content = response.audio_content
            offset = 0
            frame_count = 0

            while offset < len(audio_content):
                frame = audio_content[offset:offset + self.frame_bytes]

                # Pad last frame if necessary
                if len(frame) < self.frame_bytes:
                    frame += b'\x00' * (self.frame_bytes - len(frame))

                yield frame
                frame_count += 1
                offset += self.frame_bytes

            logger.info(f"✓ GCP TTS synthesis complete: {frame_count} frames")

        except Exception as e:
            logger.error(f"GCP TTS synthesis failed: {e}", exc_info=True)
            raise TTSServiceError(f"GCP TTS synthesis failed: {str(e)}")

    def get_audio_format(self) -> Dict[str, Any]:
        """Get audio format specifications."""
        return {
            'sample_rate': self.sample_rate,
            'encoding': 'LINEAR16',
            'channels': self.channels,
            'bits_per_sample': self.bit_depth,
            'frame_size': self.frame_size,
        }

    def supports_voice_cloning(self) -> bool:
        """
        Check if voice cloning is supported.

        GCP Chirp 3 Instant supports voice cloning (when available).
        Standard Neural2/Studio voices do not.
        """
        voice_name = self.config.get('voice_name', '')
        return 'chirp3' in voice_name.lower() or 'instant' in voice_name.lower()

    async def create_voice_profile(
        self,
        voice_audio_path: str,
        profile_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a voice profile using GCP Chirp 3 instant voice cloning.

        Args:
            voice_audio_path: Path to voice sample audio file (10-300 seconds)
            profile_name: Name for this voice profile (e.g., 'exec_001')
            metadata: Optional metadata (language, gender, description, etc.)

        Returns:
            Voice profile configuration:
            {
                'profile_id': str,
                'profile_name': str,
                'service': 'gcp_chirp3',
                'config': {
                    'voice_model_id': str,  # GCP voice model ID
                    'language_code': str
                },
                'created_at': str
            }

        Raises:
            TTSServiceError: If voice creation fails or Chirp 3 not available

        Note:
            This is a placeholder for future GCP Chirp 3 Instant voice cloning.
            Implementation depends on GCP API availability.
        """
        if not self.supports_voice_cloning():
            raise TTSServiceError(
                "Voice cloning not supported for this GCP voice. "
                "Use GCP Chirp 3 Instant (voice_name='en-US-Chirp3-Instant')"
            )

        # TODO: Implement GCP Chirp 3 voice cloning when API is available
        # This would typically involve:
        # 1. Upload voice sample to GCP
        # 2. Train/register voice model
        # 3. Get voice model ID
        # 4. Store configuration

        raise TTSServiceError(
            "GCP Chirp 3 Instant voice cloning not yet implemented. "
            "Waiting for API availability from Google Cloud."
        )

    def get_service_info(self) -> Dict[str, Any]:
        """Get service information and capabilities."""
        return {
            'name': 'GCP Text-to-Speech',
            'version': '2.14.0',
            'provider': 'Google Cloud Platform',
            'primary_voice': self.config['voice_name'],
            'true_streaming': False,  # Response generated, then streamed
            'avg_latency_ms': 800,  # 600-1200ms typical (cloud API)
            'max_text_length': 5000,
            'supported_languages': [
                'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko',
                'ar', 'hi', 'th', 'vi', 'id', 'nl', 'pl', 'tr', 'sv', 'da', 'no', 'fi'
            ],
            'supports_cloning': self.supports_voice_cloning(),
            'cost': 'PAID (GCP pricing)',
            'chirp3_ready': 'chirp3' in self.config['voice_name'].lower(),
        }


# Register with factory
from audio_services.base_tts_service import TTSServiceFactory
TTSServiceFactory.register('gcp', GCPTextToSpeechService)
TTSServiceFactory.register('gcp_chirp3', GCPTextToSpeechService)
logger.info("GCP TTS registered with TTSServiceFactory")
