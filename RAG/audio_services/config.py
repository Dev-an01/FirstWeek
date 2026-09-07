"""
Audio Services Configuration

Configuration for TTS services (Kokoro, GCP Chirp 3), audio processing, and voice profiles.
"""

import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from project root .env file
load_dotenv(Path(__file__).parent.parent.parent / '.env')

# ============================================================================
# GCP TEXT-TO-SPEECH CONFIGURATION (For Future Chirp 3 Instant)
# ============================================================================

GCP_TTS_CONFIG: Dict[str, Any] = {
    # Authentication
    'credentials_path': os.getenv(
        'GOOGLE_APPLICATION_CREDENTIALS',
        None  # Will use default credentials if not specified
    ),

    # Voice Configuration
    'language_code': os.getenv('GCP_TTS_LANGUAGE_CODE', 'en-US'),
    'voice_name': os.getenv('GCP_TTS_VOICE_NAME', 'en-US-Neural2-C'),  # Female neural voice
    'speaking_rate': float(os.getenv('GCP_TTS_SPEAKING_RATE', '1.0')),  # 0.25 to 4.0
    'pitch': float(os.getenv('GCP_TTS_PITCH', '0.0')),  # -20.0 to 20.0
    'volume_gain_db': float(os.getenv('GCP_TTS_VOLUME_GAIN_DB', '0.0')),  # -96.0 to 16.0

    # Audio Configuration (must match architecture specs)
    'audio_encoding': 'LINEAR16',  # 16-bit PCM
    'sample_rate_hertz': 24000,    # 24kHz (matching Kokoro output)

    # Performance
    'timeout_seconds': int(os.getenv('GCP_TTS_TIMEOUT', '30')),
    'max_retries': int(os.getenv('GCP_TTS_MAX_RETRIES', '3')),
    'retry_delay_seconds': 2,

    # Streaming
    'enable_streaming': os.getenv('ENABLE_AUDIO_STREAMING', 'true').lower() == 'true',
    'chunk_size_bytes': 4096,
}

# Available GCP voices for easy switching
AVAILABLE_GCP_VOICES = {
    'en-US': {
        'neural2_c': 'en-US-Neural2-C',  # Female
        'neural2_d': 'en-US-Neural2-D',  # Male
        'neural2_f': 'en-US-Neural2-F',  # Female
        'neural2_j': 'en-US-Neural2-J',  # Male
        'studio_o': 'en-US-Studio-O',    # Female (high quality)
        'studio_q': 'en-US-Studio-Q',    # Male (high quality)
        # Chirp 3 Instant (when available)
        'chirp3': 'en-US-Chirp3-Instant',  # Ultra-low latency
    }
}

# ============================================================================
# AUDIO SPECIFICATIONS
# ============================================================================

AUDIO_SPECS: Dict[str, Any] = {
    # Format Requirements
    'sample_rate': 24000,           # 24kHz (Kokoro TTS output)
    'bit_depth': 16,                # 16-bit PCM
    'channels': 1,                  # Mono
    'format': 'LINEAR16',           # Uncompressed PCM

    # Frame Specifications (Critical for WebRTC compatibility)
    'frame_size': 480,              # 480 samples per frame @ 24kHz = 20ms
    'frame_duration_ms': 20,        # Exactly 20ms per frame
    'frame_rate': 50,               # 50 FPS (1000ms / 20ms)

    # Block Processing (for MuseTalk video generation)
    'block_duration_seconds': 2,    # 2-second blocks
    'frames_per_block': 100,        # 100 frames × 20ms = 2000ms

    # Validation Tolerances
    'sample_rate_tolerance': 0.01,  # 1% tolerance
    'frame_size_exact': True,       # Must be exactly 480 samples
}

# Calculate derived values
AUDIO_SPECS['bytes_per_sample'] = AUDIO_SPECS['bit_depth'] // 8
AUDIO_SPECS['bytes_per_frame'] = AUDIO_SPECS['frame_size'] * AUDIO_SPECS['bytes_per_sample']
AUDIO_SPECS['samples_per_block'] = AUDIO_SPECS['frame_size'] * AUDIO_SPECS['frames_per_block']

# ============================================================================
# VOICE PROFILE CONFIGURATION
# ============================================================================

VOICE_PROFILE_CONFIG: Dict[str, Any] = {
    # Database
    'connection_string': os.getenv('CHAT_DATABASE_URL', os.getenv('DATABASE_URL')),

    # Storage paths
    'samples_dir': os.getenv('VOICE_SAMPLES_DIR', '/app/voice_samples'),
    'models_dir': os.getenv('VOICE_MODELS_DIR', '/app/voice_models'),

    # Voice cloning requirements
    'min_sample_duration_seconds': 10,  # Minimum 10 seconds of audio
    'max_sample_duration_seconds': 300,  # Maximum 5 minutes
    'min_samples_required': 3,  # At least 3 samples for good quality

    # Audio format for samples
    'sample_format': {
        'sample_rate': 24000,
        'channels': 1,
        'bit_depth': 16,
    },
}

# ============================================================================
# AUDIO QUEUE CONFIGURATION
# ============================================================================

AUDIO_QUEUE_CONFIG: Dict[str, Any] = {
    # Queue Settings
    'max_queue_size': 1000,         # Maximum frames in queue
    'block_size': 100,              # Frames per block (2 seconds)
    'frame_cache_size': 10,         # Reserve frames for stability

    # Thread Safety
    'lock_timeout_seconds': 5,

    # Memory Management
    'auto_cleanup': True,
    'memory_warning_threshold': 800,

    # Performance Monitoring
    'enable_metrics': os.getenv('AUDIO_QUEUE_METRICS', 'false').lower() == 'true',
    'metrics_interval_seconds': 10,
}

# ============================================================================
# TTS SERVICE SELECTION
# ============================================================================

# Default TTS service ('kokoro' or 'gcp')
DEFAULT_TTS_SERVICE = os.getenv('DEFAULT_TTS_SERVICE', 'kokoro')

# Service priority (fallback order)
TTS_SERVICE_PRIORITY = ['kokoro', 'gcp']
