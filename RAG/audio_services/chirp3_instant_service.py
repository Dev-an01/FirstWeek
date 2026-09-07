"""
Google Chirp 3 Instant TTS Service with TRUE Streaming
Follows Kokoro TTS language selection pattern exactly

Supports per-executive voice cloning keys loaded from DB with LRU cache,
falling back to default sample keys from Assets/ when unavailable.
"""

import json
import os
import re
import asyncio
from collections import OrderedDict
from typing import Optional, Dict, Any, AsyncGenerator
from pathlib import Path

from google.cloud import texttospeech_v1beta1 as texttospeech
import google.auth
from google.oauth2 import service_account

from .base_tts_service import BaseTTSService, TTSServiceError
from .config import AUDIO_SPECS
from observability.decorators import trace_function

import logging
logger = logging.getLogger(__name__)


class LRUVoiceKeyCache:
    """LRU cache for per-executive voice cloning keys.
    Only executives currently being chatted with consume memory."""

    def __init__(self, max_size=20):
        self._cache = OrderedDict()  # {executive_id: {"en-US": key, "ja-JP": key}}
        self._max_size = max_size

    def get(self, executive_id):
        if executive_id in self._cache:
            self._cache.move_to_end(executive_id)
            return self._cache[executive_id]
        return None

    def put(self, executive_id, keys):
        self._cache[executive_id] = keys
        self._cache.move_to_end(executive_id)
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def invalidate(self, executive_id=None):
        if executive_id:
            self._cache.pop(executive_id, None)
        else:
            self._cache.clear()


class GoogleChirp3InstantService(BaseTTSService):
    """
    Google Chirp 3 Instant Custom Voice TTS Service

    Language selection follows Kokoro TTS pattern:
    1. Explicit 'language' parameter in voice_config (highest priority)
    2. Auto-detect from text content (fallback)
    3. Default to English (final fallback)

    Features:
    - TRUE streaming synthesis via streaming_synthesize()
    - Pre-loaded voice keys (en-US, ja-JP)
    - Automatic Japanese character detection
    - 24kHz PCM output (matches Kokoro)
    """

    # Language mapping: Kokoro format → Google Cloud format
    LANGUAGE_MAP = {
        'en': 'en-US',
        'ja': 'ja-JP',
        'jp': 'ja-JP'  # Accept both 'ja' and 'jp'
    }

    def __init__(self):
        """Initialize Chirp 3 Instant service with pre-existing voice keys"""

        # GCP Configuration
        self.project_id = os.getenv('GCP_PROJECT_ID', 'firstweek-ai-firstweek')

        # Initialize GCP TTS client using Application Default Credentials (ADC)
        # The client will automatically find credentials from:
        # 1. GOOGLE_APPLICATION_CREDENTIALS environment variable
        # 2. gcloud auth application-default credentials
        # 3. Compute Engine/GKE service account
        try:
            self.client = texttospeech.TextToSpeechClient()
            logger.info(f"✅ GCP TTS client initialized with ADC (project: {self.project_id})")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize GCP client with ADC: {e}")
            
            # Fallback: Try loading from Assets/key.json
            key_path = Path(__file__).parent.parent / 'Assets' / 'key.json'
            if key_path.exists():
                try:
                    # Load credentials from file (supports both Service Account and Authorized User)
                    creds, project = google.auth.load_credentials_from_file(str(key_path))
                    
                    # Initialize client with loaded credentials
                    self.client = texttospeech.TextToSpeechClient(credentials=creds)
                    
                    logger.info(f"✅ GCP TTS client initialized with key.json fallback (Project: {project or self.project_id})")
                except Exception as key_err:
                     raise TTSServiceError(
                        f"Failed to initialize GCP client with fallback key.json: {key_err}\n"
                        f"Original ADC error: {e}"
                    )
            else:
                raise TTSServiceError(
                    f"Failed to initialize GCP client: {e}\n"
                    "Make sure GOOGLE_APPLICATION_CREDENTIALS points to valid ADC file "
                    "or run: gcloud auth application-default login\n"
                    f"Also checked for fallback key at {key_path} but not found."
                )

        # Voice keys must belong to the explicitly selected executive.
        self.voice_keys = {}

        # Per-executive voice key LRU cache (max 20 executives x ~340KB = ~7MB)
        self._executive_voice_cache = LRUVoiceKeyCache(max_size=20)
        self._db_pool = None  # Set lazily from app state

        logger.info(f"✅ Chirp 3 Instant initialized")
        logger.info(f"🔑 Loaded default languages: {list(self.voice_keys.keys())}")

    def _load_voice_keys(self):
        """Load pre-existing voice cloning keys from Assets folder"""

        # Path to Assets folder (relative to this file: RAG/audio_services/ -> RAG/)
        assets_dir = Path(__file__).parent.parent / 'Assets'

        # Load English voice key
        en_key_file = assets_dir / 'custom_voice_key.txt'
        if en_key_file.exists():
            with open(en_key_file, 'r') as f:
                self.voice_keys['en-US'] = f.read().strip()
            logger.info(f"📁 Loaded English voice key ({len(self.voice_keys['en-US'])} chars)")
        else:
            logger.warning(f"⚠️ English voice key not found: {en_key_file}")

        # Load Japanese voice key
        jp_key_file = assets_dir / 'custom_voice_key_jp.txt'
        if jp_key_file.exists():
            with open(jp_key_file, 'r') as f:
                self.voice_keys['ja-JP'] = f.read().strip()
            logger.info(f"📁 Loaded Japanese voice key ({len(self.voice_keys['ja-JP'])} chars)")
        else:
            logger.warning(f"⚠️ Japanese voice key not found: {jp_key_file}")

        if not self.voice_keys:
            raise TTSServiceError(
                f"No voice keys found in {assets_dir}. "
                "Expected: custom_voice_key.txt, custom_voice_key_jp.txt"
            )

    def _contains_japanese(self, text: str) -> bool:
        """
        Detect if text contains Japanese characters.

        Matches Kokoro's _contains_japanese() method exactly.

        Checks for:
        - Hiragana (U+3040-U+309F)
        - Katakana (U+30A0-U+30FF)
        - Kanji (U+4E00-U+9FFF)

        Args:
            text: Text to check

        Returns:
            True if Japanese characters detected, False otherwise
        """
        japanese_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
        return bool(japanese_pattern.search(text))

    def _select_language(
        self,
        text: str,
        voice_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Select language using EXACT same logic as Kokoro TTS _select_voice().

        Priority order (same as Kokoro):
        1. Explicit 'language' parameter in voice_config
        2. Auto-detect from text content (Japanese character check)
        3. Default to English

        Args:
            text: Text to synthesize (used for auto-detection)
            voice_config: Optional config with 'language' key

        Returns:
            Google Cloud locale code ('en-US' or 'ja-JP')
        """
        voice_config = voice_config or {}
        language = voice_config.get('language')

        # Priority 1: Explicit language parameter (highest priority)
        if language == "ja" or language == "jp":
            detected_lang = "ja"
            logger.debug("Language: explicit 'ja' parameter")

        # Priority 2: Auto-detect from text content (fallback)
        elif language == "en":
            detected_lang = "en"
            logger.debug("Language: explicit 'en' parameter")

        elif self._contains_japanese(text):
            detected_lang = "ja"
            logger.debug("Language: auto-detected Japanese from text")

        # Priority 3: Default to English (final fallback)
        else:
            detected_lang = "en"
            logger.debug("Language: defaulted to English")

        # Map to Google Cloud locale code
        locale_code = self.LANGUAGE_MAP.get(detected_lang, 'en-US')

        logger.debug(f"Language selection: '{detected_lang}' → '{locale_code}'")
        return locale_code

    async def _get_voice_key(self, executive_id: Optional[str], language_code: str) -> Optional[str]:
        """Get voice key for an executive, with LRU cache and DB fallback.

        Priority:
        1. No executive_id -> return default sample key
        2. LRU cache hit -> return cached key for language
        3. Cache miss -> load from DB, cache, return key
        4. Executive has no key for language -> fall back to default
        """
        if not executive_id:
            return self.voice_keys.get(language_code)

        # Check LRU cache
        cached = self._executive_voice_cache.get(executive_id)
        if cached is not None:
            key = cached.get(language_code)
            if key:
                return key
            # Executive has keys but not for this language -> fall back
            return self.voice_keys.get(language_code)

        # Cache miss -> try loading from DB
        try:
            keys = await self._load_voice_keys_from_db(executive_id)
            if keys:
                self._executive_voice_cache.put(executive_id, keys)
                key = keys.get(language_code)
                if key:
                    return key
        except Exception as e:
            logger.warning(f"Failed to load voice keys for {executive_id} from DB: {e}")

        # Fall back to default
        return self.voice_keys.get(language_code)

    def set_db_pool(self, pool):
        """Set the database pool reference (called from app startup)."""
        self._db_pool = pool

    async def _load_voice_keys_from_db(self, executive_id: str, company_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Load voice keys from database for an executive, optionally scoped by company."""
        if not self._db_pool:
            return None
        try:
            if company_id:
                row = await self._db_pool.fetchrow(
                    "SELECT voice_keys FROM executive_profiles WHERE id = $1 AND company_id = $2",
                    executive_id,
                    company_id,
                )
            else:
                row = await self._db_pool.fetchrow(
                    "SELECT voice_keys FROM executive_profiles WHERE id = $1",
                    executive_id,
                )
            if row and row["voice_keys"]:
                data = row["voice_keys"]
                return json.loads(data) if isinstance(data, str) else data
        except Exception as e:
            logger.warning(f"DB query for voice keys failed: {e}")
        return None

    def invalidate_cache(self, executive_id: Optional[str] = None):
        """Invalidate voice key cache entry."""
        self._executive_voice_cache.invalidate(executive_id)
        if executive_id:
            logger.info(f"Voice key cache invalidated for {executive_id}")
        else:
            logger.info("Voice key cache fully cleared")

    async def reload_executive_keys(self, db_pool, executive_id: str, company_id: Optional[str] = None):
        """Reload voice keys from DB into LRU cache for a specific executive."""
        self._executive_voice_cache.invalidate(executive_id)
        try:
            if company_id:
                row = await db_pool.fetchrow(
                    "SELECT voice_keys FROM executive_profiles WHERE id = $1 AND company_id = $2",
                    executive_id,
                    company_id,
                )
            else:
                row = await db_pool.fetchrow(
                    "SELECT voice_keys FROM executive_profiles WHERE id = $1",
                    executive_id,
                )
            if row and row["voice_keys"]:
                data = row["voice_keys"]
                keys = json.loads(data) if isinstance(data, str) else data
                self._executive_voice_cache.put(executive_id, keys)
                logger.info(f"Reloaded voice keys for {executive_id}: {list(keys.keys())}")
            else:
                logger.info(f"No voice keys in DB for {executive_id}")
        except Exception as e:
            logger.error(f"Failed to reload voice keys for {executive_id}: {e}")

    @trace_function("chirp3_instant", "synthesize_stream")
    async def synthesize_stream(
        self,
        text: str,
        voice_config: Optional[Dict[str, Any]] = None,
        is_last_sentence: bool = True
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize audio using TRUE streaming synthesis.

        Based on Google's official example with streaming_synthesize().
        Language selection follows Kokoro TTS pattern exactly.

        Args:
            text: Text to synthesize
            voice_config: Optional config with 'language' key
            is_last_sentence: Whether this is the last sentence (matches Kokoro signature)

        Yields:
            PCM audio frames (480 samples, 16-bit, 24kHz, mono)
        """

        # Select language using Kokoro's pattern
        language_code = self._select_language(text, voice_config)

        # Get per-executive voice key, falling back to default
        executive_id = (voice_config or {}).get('executive_id')
        voice_key = await self._get_voice_key(executive_id, language_code)
        if not voice_key:
            raise TTSServiceError(
                f"No voice key for language '{language_code}'. "
                f"Available: {list(self.voice_keys.keys())}"
            )

        key_source = f"executive:{executive_id}" if executive_id and self._executive_voice_cache.get(executive_id) else "default"
        logger.info(f"🎙️ Chirp 3 streaming synthesis: {language_code} (key: {key_source})")
        logger.debug(f"📝 Text: {text[:50]}{'...' if len(text) > 50 else ''}")

        try:
            # Configure voice cloning
            voice_clone_params = texttospeech.VoiceCloneParams(
                voice_cloning_key=voice_key
            )

            # Streaming configuration (from official Google example)
            streaming_config = texttospeech.StreamingSynthesizeConfig(
                voice=texttospeech.VoiceSelectionParams(
                    language_code=language_code,
                    voice_clone=voice_clone_params
                ),
                streaming_audio_config=texttospeech.StreamingAudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.PCM,
                    sample_rate_hertz=24000,  # Matches Kokoro's 24kHz
                ),
            )

            # Request generator (config first, then text)
            def request_generator():
                # First request: configuration
                yield texttospeech.StreamingSynthesizeRequest(
                    streaming_config=streaming_config
                )
                # Second request: text input
                yield texttospeech.StreamingSynthesizeRequest(
                    input=texttospeech.StreamingSynthesisInput(text=text)
                )

            # Call streaming API (blocking call, so use asyncio.to_thread)
            logger.debug("🔄 Calling GCP streaming_synthesize()...")
            streaming_responses = await asyncio.to_thread(
                self.client.streaming_synthesize,
                request_generator()
            )

            # Process streaming responses
            total_bytes = 0
            chunk_count = 0

            for response in streaming_responses:
                if response.audio_content:
                    chunk_size = len(response.audio_content)
                    total_bytes += chunk_size
                    chunk_count += 1

                    logger.debug(f"📦 Chunk {chunk_count}: {chunk_size} bytes")

                    # Convert variable-sized chunks to standard 480-sample frames
                    # (matches Kokoro's frame size)
                    audio_data = response.audio_content
                    frame_size_bytes = AUDIO_SPECS['frame_size'] * 2  # 480 samples * 2 bytes = 960

                    for i in range(0, len(audio_data), frame_size_bytes):
                        frame = audio_data[i:i + frame_size_bytes]

                        # Pad last frame if needed (to maintain consistent frame size)
                        if len(frame) < frame_size_bytes:
                            frame = frame + b'\x00' * (frame_size_bytes - len(frame))

                        yield frame

            logger.info(f"✅ Streaming complete: {total_bytes} bytes in {chunk_count} chunks")

        except Exception as e:
            logger.error(f"❌ Chirp 3 streaming synthesis failed: {e}")
            raise TTSServiceError(f"Chirp 3 synthesis error: {e}")

    def get_audio_format(self) -> Dict[str, Any]:
        """Return standardized audio format (matches Kokoro exactly)"""
        return {
            'sample_rate': AUDIO_SPECS['sample_rate'],  # 24000
            'encoding': 'LINEAR16',
            'channels': AUDIO_SPECS['channels'],  # 1
            'bits_per_sample': AUDIO_SPECS['bit_depth'],  # 16
            'frame_size': AUDIO_SPECS['frame_size']  # 480
        }

    def supports_voice_cloning(self) -> bool:
        """Voice keys already exist and loaded"""
        return True

    async def create_voice_profile(
        self,
        voice_audio_path: str,
        profile_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Voice cloning keys already pre-loaded - registration not needed.

        Raises:
            TTSServiceError: Always raises, as keys are pre-loaded
        """
        raise TTSServiceError(
            "Voice cloning keys already exist in Assets/ folder "
            "(custom_voice_key.txt, custom_voice_key_jp.txt). "
            "Voice registration not needed for this implementation."
        )

    def get_service_info(self) -> Dict[str, Any]:
        """Return service capabilities and metadata"""
        return {
            'name': 'Google Chirp 3 Instant',
            'provider': 'google_cloud',
            'model': 'chirp3-instant',
            'project_id': self.project_id,
            'capabilities': {
                'voice_cloning': True,
                'streaming': True,  # TRUE streaming via streaming_synthesize()
                'multilingual': True,
                'auto_language_detection': True,  # Like Kokoro
                'languages': ['en-US', 'ja-JP']
            },
            'supported_languages': list(self.voice_keys.keys()),
            'audio_format': self.get_audio_format(),
            'latency_estimate_ms': {
                'first_chunk': 400,  # To be measured in production
                'total': 1000
            },
            'language_selection_pattern': 'kokoro_compatible'
        }
