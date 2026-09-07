"""
Base TTS Service Interface

Abstract base class defining the interface for all TTS services.
Supports Piper TTS (current) and GCP Chirp 3 Instant (future).
Includes voice cloning capabilities for executive voice profiles.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any


class TTSServiceError(Exception):
    """Base exception for TTS service errors"""
    pass


class BaseTTSService(ABC):
    """
    Abstract base class for TTS services.

    All TTS implementations must follow this interface to ensure
    easy switching between providers (Piper, GCP Chirp 3 Instant).
    """

    @abstractmethod
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
                - For Piper: {'voice': 'en_US-lessac-medium'}
                - For GCP: {'voice_name': 'en-US-Neural2-C', 'language_code': 'en-US'}
                - For Cloned Voice: {'profile_id': 'exec_001', 'use_cloned': True}

        Yields:
            Audio chunks as bytes (PCM format)

        Raises:
            TTSServiceError: If synthesis fails
        """
        pass

    @abstractmethod
    def get_audio_format(self) -> Dict[str, Any]:
        """
        Get audio format specifications.

        Returns:
            Dictionary with:
                - sample_rate: int (e.g., 22050)
                - encoding: str (e.g., 'LINEAR16', 'PCM')
                - channels: int (1 for mono, 2 for stereo)
                - bits_per_sample: int (e.g., 16)
                - frame_size: int (e.g., 441 samples)
        """
        pass

    @abstractmethod
    def supports_voice_cloning(self) -> bool:
        """
        Check if this service supports voice cloning.

        Returns:
            True if voice cloning is supported (for executive voice profiles)
        """
        pass

    @abstractmethod
    async def create_voice_profile(
        self,
        voice_audio_path: str,
        profile_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a voice profile from audio sample (for executive voices).

        Args:
            voice_audio_path: Path to voice sample audio file
            profile_name: Name for this voice profile (e.g., 'exec_001')
            metadata: Optional metadata (language, gender, description, etc.)

        Returns:
            Voice profile configuration that can be used in synthesize_stream:
            {
                'profile_id': str,
                'profile_name': str,
                'service': str,
                'config': dict,  # Service-specific config
                'created_at': str
            }

        Raises:
            TTSServiceError: If voice creation fails
        """
        pass

    @abstractmethod
    def get_service_info(self) -> Dict[str, Any]:
        """
        Get service information and capabilities.

        Returns:
            Dictionary with:
                - name: str (e.g., 'Piper', 'GCP Chirp3')
                - version: str
                - provider: str
                - avg_latency_ms: int (estimated)
                - max_text_length: int
                - supported_languages: list
                - supports_cloning: bool
                - cost: str
        """
        pass


class TTSServiceFactory:
    """
    Factory for creating TTS service instances.

    Allows easy switching between Piper TTS and GCP Chirp 3 Instant.
    """

    _services = {}

    @classmethod
    def register(cls, name: str, service_class):
        """
        Register a TTS service implementation.

        Args:
            name: Service name ('piper', 'gcp', 'gcp_chirp3')
            service_class: Service class implementing BaseTTSService
        """
        cls._services[name] = service_class

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseTTSService:
        """
        Create a TTS service instance.

        Args:
            name: Service name ('piper', 'gcp', 'gcp_chirp3')
            **kwargs: Service-specific configuration

        Returns:
            TTS service instance

        Raises:
            ValueError: If service name not registered

        Example:
            # Use Piper (current)
            tts = TTSServiceFactory.create('piper', primary_engine='piper')

            # Switch to GCP Chirp 3 (future)
            tts = TTSServiceFactory.create('gcp_chirp3', credentials_path='/path/to/key.json')
        """
        if name not in cls._services:
            available = ', '.join(cls._services.keys())
            raise ValueError(
                f"Unknown TTS service: {name}. "
                f"Available: {available}"
            )

        return cls._services[name](**kwargs)

    @classmethod
    def get_available_services(cls) -> list:
        """Get list of available TTS services"""
        return list(cls._services.keys())
