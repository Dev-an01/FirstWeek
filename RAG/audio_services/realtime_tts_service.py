"""
RealtimeTTS Service - Ultra-Low Latency TTS with Kokoro-82M

Direct Kokoro library integration for TRUE real-time streaming:
- Kokoro TTS: 82M parameter model, 24kHz output
- Native Python generator API for streaming
- High-quality multilingual support (English, Japanese, and more)
- No subprocess overhead, direct audio generation
"""

import asyncio
import logging
import numpy as np
import torch
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, Any
import os

from audio_services.base_tts_service import BaseTTSService, TTSServiceError
from audio_services.config import AUDIO_SPECS

logger = logging.getLogger(__name__)


class RealtimeTTSService(BaseTTSService):
    """
    Real-time TTS service using Kokoro-82M for streaming audio.

    Uses native Python API with generator-based streaming for true real-time
    performance with high-quality multilingual voices.
    """

    def __init__(
        self,
        primary_engine: str = "kokoro",
        voice_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Kokoro TTS service.

        Args:
            primary_engine: Engine to use (only 'kokoro' supported)
            voice_config: Voice configuration (voice name, speed, etc.)
        """
        self.primary_engine_name = primary_engine
        self.voice_config = voice_config or {}

        # Audio format specs (24kHz for Kokoro)
        self.sample_rate = AUDIO_SPECS['sample_rate']  # 24000 Hz
        self.channels = AUDIO_SPECS['channels']  # 1 (mono)
        self.bit_depth = AUDIO_SPECS['bit_depth']  # 16
        self.frame_size = AUDIO_SPECS['frame_size']  # 480 samples
        self.frame_bytes = self.frame_size * (self.bit_depth // 8)  # 960 bytes

        # Kokoro model paths (support both Docker and local Windows)
        model_dir_env = os.getenv('KOKORO_MODEL_PATH', '/app/models/kokoro')
        # Convert to Windows path if needed (C:/app/models/kokoro for local testing)
        if model_dir_env.startswith('/app/') and os.name == 'nt':
            model_dir_env = 'C:' + model_dir_env
        self.model_dir = Path(model_dir_env)
        self.model_path = self.model_dir / "kokoro-v1_0.pth"
        self.voices_dir = self.model_dir / "voices"

        # Initialize shared model (loaded once, reused for all pipelines)
        self._shared_model = None

        # Initialize pipelines (lazy loading for efficiency)
        self._pipeline_en = None  # American English pipeline
        self._pipeline_ja = None  # Japanese pipeline

        # Voice mapping - default voices for each language
        self.default_voices = {
            'en': 'af_bella',      # Grade A- female voice (high quality)
            'ja': 'jf_alpha'       # Grade C+ female voice (best Japanese)
        }

        # Validate model and voice files exist
        if not self.model_path.exists():
            raise TTSServiceError(f"Kokoro model not found: {self.model_path}")

        # Check English voices
        en_voice_path = self.voices_dir / f"{self.default_voices['en']}.pt"
        if not en_voice_path.exists():
            raise TTSServiceError(f"English voice not found: {en_voice_path}")

        # Check Japanese voices
        ja_voice_path = self.voices_dir / f"{self.default_voices['ja']}.pt"
        self.has_japanese_voice = ja_voice_path.exists()
        if not self.has_japanese_voice:
            logger.warning(f"Japanese voice not found at {ja_voice_path}, will use English voice for Japanese text")

        logger.info(f"RealtimeTTS initialized with Kokoro-82M")
        logger.info(f"  Model: {self.model_path}")
        logger.info(f"  English voice: {self.default_voices['en']} (Grade A-)")
        logger.info(f"  Japanese voice: {self.default_voices['ja'] if self.has_japanese_voice else 'Not available (using English fallback)'}")
        logger.info(f"  Sample rate: {self.sample_rate} Hz")
        logger.info(f"  Format: {self.bit_depth}-bit PCM, {self.channels} channel(s)")
        logger.info(f"  Frame size: {self.frame_size} samples ({self.frame_bytes} bytes)")

    def _load_shared_model(self):
        """
        Load the shared Kokoro model (once, reused for all pipelines).

        Returns:
            KModel instance
        """
        if self._shared_model is None:
            from kokoro import KModel
            import time

            # Determine device (GPU if available)
            device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info(f"Loading shared Kokoro model from local path (device: {device})...")
            start = time.time()

            self._shared_model = KModel(
                repo_id="local",  # Prevent HF download attempts
                model=str(self.model_path),
                config=str(self.model_dir / "config.json")
            )

            # Move model to GPU if available with optimizations
            if device == "cuda":
                self._shared_model = self._shared_model.to(device)
                # Set model to eval mode for inference (no gradients needed)
                self._shared_model.eval()
                logger.info("✓ Model moved to GPU and set to eval mode")

            load_time = (time.time() - start) * 1000
            logger.info(f"✓ Shared Kokoro model loaded in {load_time:.0f}ms (fully offline, on {device})")

        return self._shared_model

    def _get_pipeline(self, language: str):
        """
        Get or create Kokoro pipeline for the specified language.

        Args:
            language: Language code ('en' or 'ja')

        Returns:
            KPipeline instance for the language
        """
        try:
            from kokoro import KPipeline
            import time

            # Determine device (GPU if available)
            device = "cuda" if torch.cuda.is_available() else "cpu"

            # Load shared model (only happens once)
            model = self._load_shared_model()

            if language == 'ja':
                if self._pipeline_ja is None:
                    logger.info("Initializing Japanese pipeline (using shared model)")
                    start = time.time()

                    self._pipeline_ja = KPipeline(
                        lang_code='j',
                        model=model,
                        repo_id="local",  # Prevent HF download attempts
                        device=device  # Explicitly set device
                    )

                    init_time = (time.time() - start) * 1000
                    logger.info(f"✓ Japanese pipeline ready in {init_time:.0f}ms (fully local, {device})")
                return self._pipeline_ja
            else:
                if self._pipeline_en is None:
                    logger.info("Initializing English pipeline (using shared model)")
                    start = time.time()

                    self._pipeline_en = KPipeline(
                        lang_code='a',
                        model=model,
                        repo_id="local",  # Prevent HF download attempts
                        device=device  # Explicitly set device
                    )

                    init_time = (time.time() - start) * 1000
                    logger.info(f"✓ English pipeline ready in {init_time:.0f}ms (fully local, {device})")
                return self._pipeline_en

        except Exception as e:
            logger.error(f"Failed to initialize Kokoro pipeline: {e}", exc_info=True)
            raise TTSServiceError(f"Failed to initialize Kokoro pipeline: {str(e)}")

    def _contains_japanese(self, text: str) -> bool:
        """
        Detect if text contains Japanese characters (Hiragana, Katakana, or Kanji).

        Args:
            text: Text to check

        Returns:
            True if Japanese characters found
        """
        import re
        # Japanese character ranges:
        # \u3040-\u309F: Hiragana
        # \u30A0-\u30FF: Katakana
        # \u4E00-\u9FFF: Kanji (CJK Unified Ideographs)
        return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))

    def _select_voice(self, text: str, language: Optional[str] = None) -> tuple:
        """
        Select appropriate pipeline and voice based on language parameter or text content.

        Args:
            text: Text to synthesize
            language: Optional language code (en, ja, jp)

        Returns:
            Tuple of (pipeline, voice_tensor, detected_language, voice_id)
        """
        # Determine language
        if language == "ja" or language == "jp":
            detected_lang = "ja"
        elif self._contains_japanese(text):
            detected_lang = "ja"
        else:
            detected_lang = "en"

        # Get pipeline for language
        pipeline = self._get_pipeline(detected_lang)

        # Get voice identifier
        voice_id = self.default_voices[detected_lang]
        voice_path = self.voices_dir / f"{voice_id}.pt"

        # Check if voice exists, fallback to English if needed
        if not voice_path.exists():
            logger.warning(f"Voice {voice_id} not found, falling back to English voice")
            detected_lang = "en"
            pipeline = self._get_pipeline("en")
            voice_id = self.default_voices["en"]
            voice_path = self.voices_dir / f"{voice_id}.pt"

        # Load voice tensor
        try:
            voice_tensor = torch.load(voice_path, weights_only=True)
            logger.debug(f"Loaded voice tensor: {voice_id} from {voice_path}")
        except Exception as e:
            logger.error(f"Failed to load voice {voice_id}: {e}")
            raise TTSServiceError(f"Failed to load voice file: {str(e)}")

        return (pipeline, voice_tensor, detected_lang, voice_id)

    async def synthesize_stream(
        self,
        text: str,
        voice_config: Optional[Dict[str, Any]] = None,
        is_last_sentence: bool = True
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to speech and stream PCM audio chunks in REAL-TIME.

        Uses Kokoro native generator API to stream audio as it's generated.
        Audio starts streaming within 50-200ms for true real-time performance.

        Args:
            text: Text to synthesize
            voice_config: Optional voice configuration (overrides init config)
            is_last_sentence: If False, don't pad the final frame (for smooth transitions between sentences)

        Yields:
            PCM audio frames (24kHz, 16-bit, mono, 480 samples per frame)

        Raises:
            TTSServiceError: If synthesis fails
        """
        if not text.strip():
            return

        try:
            # Extract language from voice_config if provided
            language = None
            if voice_config:
                language = voice_config.get('language')

            # Select appropriate pipeline and voice based on language and text content
            pipeline, voice_tensor, detected_lang, voice_id = self._select_voice(text, language)

            logger.info(f"Synthesizing with Kokoro: '{text[:50]}...' (length: {len(text)} chars, lang: {detected_lang}, voice: {voice_id})")
            logger.debug(f"Full text to synthesize: '{text}'")

            # Buffer for frame alignment
            buffer = bytearray()
            frame_count = 0

            # Run Kokoro generator
            # The generator yields tuples of (graphemes, phonemes, audio_array)
            # audio_array is numpy float32, range approximately [-1, 1], 24kHz
            try:
                # Use torch.no_grad() for inference - saves memory and improves speed
                with torch.no_grad():
                    generator = pipeline(text, voice=voice_tensor, speed=1.0)

                    # Process audio chunks from generator
                    for graphemes, phonemes, audio_array in generator:
                        # Convert float32 audio to int16 PCM
                        # Kokoro outputs float32 in range ~[-1, 1]
                        # Convert to int16 range [-32768, 32767]

                        # Check if audio_array is a torch tensor and convert to numpy
                        if torch.is_tensor(audio_array):
                            audio_array = audio_array.cpu().numpy()

                        audio_int16 = (audio_array * 32767).astype(np.int16)
                        audio_bytes = audio_int16.tobytes()

                        logger.debug(f"Received audio chunk: {len(audio_array)} samples, {len(audio_bytes)} bytes")

                        # Add to buffer
                        buffer.extend(audio_bytes)

                        # Yield complete frames immediately as they arrive
                        while len(buffer) >= self.frame_bytes:
                            frame = bytes(buffer[:self.frame_bytes])
                            yield frame
                            frame_count += 1
                            buffer = buffer[self.frame_bytes:]

                        # Allow other coroutines to run
                        await asyncio.sleep(0)

                # Yield remaining audio - always pad to complete frame (never drop audio!)
                if len(buffer) > 0:
                    # Always pad the final frame to complete it
                    padding_needed = self.frame_bytes - len(buffer)
                    if padding_needed > 0:
                        buffer.extend(b'\x00' * padding_needed)
                    yield bytes(buffer[:self.frame_bytes])
                    frame_count += 1

                    # Add a tiny gap between sentences (2 frames = 40ms) to avoid run-on
                    # This is much shorter than the previous padding but prevents audio blending
                    if not is_last_sentence:
                        silence_frames = 2  # 40ms of silence between sentences
                        silence = b'\x00' * self.frame_bytes
                        for _ in range(silence_frames):
                            yield silence
                            frame_count += 1

                logger.info(f"✓ Kokoro synthesis complete: {frame_count} frames ({frame_count * self.frame_bytes} bytes) for '{text[:30]}...'")

                # CRITICAL: Clear CUDA cache after synthesis to free GPU memory
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.debug("✓ CUDA cache cleared after synthesis")

            except Exception as e:
                logger.error(f"Kokoro generator failed: {e}", exc_info=True)
                # Clear CUDA cache even on error to prevent memory leaks
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                raise TTSServiceError(f"Kokoro synthesis failed: {str(e)}")

        except TTSServiceError:
            raise
        except Exception as e:
            logger.error(f"Synthesis failed: {e}", exc_info=True)
            raise TTSServiceError(f"Kokoro synthesis failed: {str(e)}")

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

        Kokoro currently doesn't support voice cloning out of the box.
        Would need custom voice tensor creation for this feature.
        """
        return False

    async def create_voice_profile(
        self,
        voice_audio_path: str,
        profile_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create voice profile (not currently supported for Kokoro).

        Future: Could potentially create custom voice tensors for Kokoro,
        or integrate with GCP TTS for voice cloning.
        """
        raise TTSServiceError(
            "Voice cloning not supported by Kokoro TTS. "
            "Use GCP TTS service with Chirp 3 instant voice cloning when available."
        )

    def get_service_info(self) -> Dict[str, Any]:
        """Get service information and capabilities."""
        supported_languages = ['en']  # English always supported
        if self.has_japanese_voice:
            supported_languages.append('ja')  # Japanese supported if voice available

        available_voices = {
            'en': ['af_bella (Grade A-)', 'af_heart (Grade A)'],
            'ja': ['jf_alpha (Grade C+)', 'jf_gongitsune (Grade C)'] if self.has_japanese_voice else []
        }

        return {
            'name': 'RealtimeTTS',
            'version': '3.0.0',  # Updated for Kokoro-82M
            'provider': 'Kokoro-82M (Local Neural, High-Quality Multilingual)',
            'model': 'Kokoro-82M (82M parameters)',
            'primary_engine': self.primary_engine_name,
            'available_engines': ['kokoro'],
            'true_streaming': True,
            'avg_latency_ms': 100,  # 50-200ms typical with Kokoro
            'max_text_length': 10000,  # Kokoro handles longer text well
            'supported_languages': supported_languages,
            'available_voices': available_voices,
            'japanese_voice_available': self.has_japanese_voice,
            'auto_language_detection': True,
            'supports_cloning': False,
            'cost': 'FREE (local engine)',
            'audio_quality': 'High (24kHz, 82M parameters)',
        }

    async def warmup(self):
        """
        Warm up the TTS service by loading models and running a dummy inference.
        This prevents the 6-7s delay on the first user request.
        """
        try:
            logger.info("Starting TTS service warmup...")
            import time
            start = time.time()

            # 1. Load shared model (this also moves it to GPU)
            self._load_shared_model()
            
            # 2. Initialize English pipeline (most commonly used)
            # This loads the English voice tensor too
            self._get_pipeline('en')
            
            # 3. Initialize Japanese pipeline if voice available
            if self.has_japanese_voice:
                self._get_pipeline('ja')

            # 4. Run a tiny dummy inference to force CUDA context creation and JIT compilation
            # Use a very short text to minimize time
            logger.info("Running dummy inference to warm CUDA context...")
            pipeline = self._pipeline_en
            voice_path = self.voices_dir / f"{self.default_voices['en']}.pt"
            if voice_path.exists():
                voice_tensor = torch.load(voice_path, weights_only=True)
                with torch.no_grad():
                    # Generate a single frame of silence/audio for "a"
                    generator = pipeline("a", voice=voice_tensor, speed=1.0)
                    for _ in generator:
                        break # Just need one iteration to trigger everything
            
            warmup_time = (time.time() - start) * 1000
            logger.info(f"✓ TTS service warmup complete in {warmup_time:.0f}ms")
            
        except Exception as e:
            logger.warning(f"TTS service warmup failed (non-critical): {e}")



# Register with factory
from audio_services.base_tts_service import TTSServiceFactory
TTSServiceFactory.register('kokoro', RealtimeTTSService)
logger.info("Kokoro TTS registered with TTSServiceFactory")
