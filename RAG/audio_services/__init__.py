"""
Audio Services Module

Provides text-to-speech, speech-to-text, audio processing, voice profile management,
and audio streaming functionality for the Digital Human real-time system.

Components:
- base_tts_service: Abstract TTS interface with factory pattern
- realtime_tts_service: Piper TTS (local, fast, current)
- tts_service: GCP TTS including Chirp 3 Instant (future)
- stt_service: Faster Whisper STT (local, EN/JA support)
- realtime_stt_service: Real-time STT with VAD
- audio_processor: PCM frame conversion and validation
- db_client: Voice profile database management
- config: Configuration for all audio services

Switching between TTS services:
    # Use Piper (current - fast, local, free)
    from audio_services.base_tts_service import TTSServiceFactory
    tts = TTSServiceFactory.create('piper')

    # Switch to GCP Chirp 3 (future - voice cloning)
    tts = TTSServiceFactory.create('gcp_chirp3', credentials_path='/path/to/key.json')

Using STT:
    # Singleton pattern - model loaded once
    from audio_services.stt_service import get_stt_service
    stt = get_stt_service()
    result = await stt.transcribe_file('audio.wav', language='en')
"""

from .config import (
    GCP_TTS_CONFIG,
    AUDIO_SPECS,
    AUDIO_QUEUE_CONFIG,
    VOICE_PROFILE_CONFIG,
    AVAILABLE_GCP_VOICES,
    DEFAULT_TTS_SERVICE,
    TTS_SERVICE_PRIORITY
)
from .base_tts_service import BaseTTSService, TTSServiceError, TTSServiceFactory
from .realtime_tts_service import RealtimeTTSService
from .audio_processor import AudioProcessor, AudioProcessingError, AudioFormatError
from .db_client import VoiceProfileDBClient

# Conditionally import GCP TTS (requires google-cloud-texttospeech)
try:
    from .tts_service import GCPTextToSpeechService
    GCP_TTS_AVAILABLE = True
except ImportError:
    GCP_TTS_AVAILABLE = False
    GCPTextToSpeechService = None

# Import STT services (Faster Whisper - local, free)
from .stt_service import FasterWhisperSTT, get_stt_service, STTServiceError
from .realtime_stt_service import RealTimeSTT, get_realtime_stt

__all__ = [
    # Config
    'GCP_TTS_CONFIG',
    'AUDIO_SPECS',
    'AUDIO_QUEUE_CONFIG',
    'VOICE_PROFILE_CONFIG',
    'AVAILABLE_GCP_VOICES',
    'DEFAULT_TTS_SERVICE',
    'TTS_SERVICE_PRIORITY',
    # Base classes
    'BaseTTSService',
    'TTSServiceError',
    'TTSServiceFactory',
    # TTS Services
    'RealtimeTTSService',
    'GCPTextToSpeechService',
    'GCP_TTS_AVAILABLE',
    # STT Services
    'FasterWhisperSTT',
    'get_stt_service',
    'STTServiceError',
    'RealTimeSTT',
    'get_realtime_stt',
    # Audio processing
    'AudioProcessor',
    'AudioProcessingError',
    'AudioFormatError',
    # Voice profiles
    'VoiceProfileDBClient',
]

__version__ = '2.0.0'
