"""
VoiceprintCache - Cache executive voiceprints for fast persona access

Caches immutable persona characteristics including:
- Signature phrases and openers
- Decision-making patterns
- Risk language preferences
- Communication style markers
- Lexicon (unique phrases)

Uses Redis with in-memory fallback for development.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Voiceprint:
    """
    Executive voiceprint containing persona characteristics
    """
    executive_id: str
    name: str
    voiceprint: Dict  # 7 components (opener, decision_cadence, risk_language, etc.)
    lexicon: List[str]  # Unique phrases (30-50)
    total_token_count: int

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Voiceprint':
        """Load from dictionary"""
        return cls(**data)


class VoiceprintCache:
    """
    Cache for executive voiceprints with Redis backend and memory fallback

    Features:
    - Redis caching with 1-hour TTL
    - In-memory fallback for development
    - JSON file loading from test_data/voiceprints/
    - Lazy loading (load on first access)
    """

    def __init__(self, voiceprints_dir: Optional[str] = None, use_redis: bool = False):
        """
        Initialize voiceprint cache

        Args:
            voiceprints_dir: Directory containing voiceprint JSON files
            use_redis: Whether to use Redis (requires redis-py)
        """
        self.voiceprints_dir = Path(voiceprints_dir or "test_data/voiceprints")
        self.use_redis = use_redis
        self._memory_cache: Dict[str, Voiceprint] = {}
        self._redis_client = None

        # Initialize Redis if requested
        if self.use_redis:
            try:
                import redis
                self._redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=0,
                    decode_responses=True
                )
                # Test connection
                self._redis_client.ping()
                logger.info("[VoiceprintCache] Connected to Redis")
            except Exception as e:
                logger.warning(f"[VoiceprintCache] Redis unavailable ({e}), using memory fallback")
                self._redis_client = None
        else:
            logger.info("[VoiceprintCache] Using memory cache (Redis disabled)")

    def get(self, executive_id: str) -> Optional[Voiceprint]:
        """
        Get voiceprint for executive (with caching)

        Args:
            executive_id: Executive identifier (e.g., "exec_003_test")

        Returns:
            Voiceprint object or None if not found
        """
        # Check memory cache first
        if executive_id in self._memory_cache:
            logger.debug(f"[VoiceprintCache] Memory cache hit: {executive_id}")
            return self._memory_cache[executive_id]

        # Check Redis cache
        if self._redis_client:
            try:
                cached_json = self._redis_client.get(f"voiceprint:{executive_id}")
                if cached_json:
                    logger.debug(f"[VoiceprintCache] Redis cache hit: {executive_id}")
                    voiceprint = Voiceprint.from_dict(json.loads(cached_json))
                    self._memory_cache[executive_id] = voiceprint
                    return voiceprint
            except Exception as e:
                logger.warning(f"[VoiceprintCache] Redis get error: {e}")

        # Load from file
        voiceprint = self._load_from_file(executive_id)

        if voiceprint:
            # Cache in memory
            self._memory_cache[executive_id] = voiceprint

            # Cache in Redis
            if self._redis_client:
                try:
                    self._redis_client.setex(
                        f"voiceprint:{executive_id}",
                        3600,  # 1 hour TTL
                        json.dumps(voiceprint.to_dict())
                    )
                    logger.debug(f"[VoiceprintCache] Cached to Redis: {executive_id}")
                except Exception as e:
                    logger.warning(f"[VoiceprintCache] Redis set error: {e}")

        return voiceprint

    def _load_from_file(self, executive_id: str) -> Optional[Voiceprint]:
        """
        Load voiceprint from JSON file

        Args:
            executive_id: Executive identifier

        Returns:
            Voiceprint object or None if file not found
        """
        # Try exact match first
        file_path = self.voiceprints_dir / f"{executive_id}_voiceprint.json"

        if not file_path.exists():
            # Try fuzzy match by executive name
            # e.g., "exec_003_test" → "yuki_nakamura_voiceprint.json"
            for json_file in self.voiceprints_dir.glob("*_voiceprint.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get("executive_id") == executive_id:
                            file_path = json_file
                            break
                except Exception as e:
                    logger.warning(f"[VoiceprintCache] Error reading {json_file}: {e}")
                    continue

        if not file_path.exists():
            logger.warning(f"[VoiceprintCache] Voiceprint not found: {executive_id}")
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            voiceprint = Voiceprint.from_dict(data)
            logger.info(f"[VoiceprintCache] Loaded voiceprint from {file_path.name}")
            return voiceprint

        except Exception as e:
            logger.error(f"[VoiceprintCache] Error loading {file_path}: {e}")
            return None

    def list_available(self) -> List[str]:
        """
        List all available voiceprints

        Returns:
            List of executive IDs
        """
        executive_ids = []

        for json_file in self.voiceprints_dir.glob("*_voiceprint.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    exec_id = data.get("executive_id")
                    if exec_id:
                        executive_ids.append(exec_id)
            except Exception as e:
                logger.warning(f"[VoiceprintCache] Error reading {json_file}: {e}")
                continue

        return executive_ids

    def clear_cache(self):
        """Clear all caches (memory and Redis)"""
        self._memory_cache.clear()

        if self._redis_client:
            try:
                # Delete all voiceprint keys
                keys = self._redis_client.keys("voiceprint:*")
                if keys:
                    self._redis_client.delete(*keys)
                logger.info("[VoiceprintCache] Redis cache cleared")
            except Exception as e:
                logger.warning(f"[VoiceprintCache] Redis clear error: {e}")

        logger.info("[VoiceprintCache] Memory cache cleared")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    cache = VoiceprintCache()

    # Test loading
    voiceprint = cache.get("exec_003_test")

    if voiceprint:
        print(f"\nVoiceprint for {voiceprint.name}:")
        print(f"  Lexicon size: {len(voiceprint.lexicon)}")
        print(f"  Token count: {voiceprint.total_token_count}")
        print(f"  Components: {list(voiceprint.voiceprint.keys())}")
        print(f"\nSample lexicon phrases:")
        for phrase in voiceprint.lexicon[:5]:
            print(f"    - {phrase}")
    else:
        print("Voiceprint not found!")

    # List available
    available = cache.list_available()
    print(f"\nAvailable voiceprints: {available}")
