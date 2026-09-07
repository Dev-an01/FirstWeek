"""
Profile Manager

Singleton manager for executive profiles with caching and hot reload support.
Supports loading profiles from both filesystem (YAML/JSON) and database.
"""
import logging
import threading
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from .profile_loader import ProfileLoader
from .prompt_generator import PromptGenerator
from .example_selector import ExampleSelector
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.llm_config_loader import get_config

logger = logging.getLogger(__name__)


def _get_postgres_connection():
    """
    Get a synchronous PostgreSQL connection for loading profiles.
    Uses psycopg2 for synchronous access (ProfileManager is sync).
    """
    try:
        import psycopg2
        import psycopg2.extras

        # Get connection parameters from environment
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "ai_officer"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres123"),
            connect_timeout=5
        )
        return conn
    except ImportError:
        logger.warning("psycopg2 not installed - database profile loading disabled")
        return None
    except Exception as e:
        logger.warning(f"Failed to connect to PostgreSQL: {e}")
        return None


class ProfileManager:
    """
    Singleton manager for executive profiles.
    
    Provides:
    - In-memory profile caching
    - System prompt generation and caching
    - Hot reload support (future)
    - Thread-safe access
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Only initialize once
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._system_prompts_cache: Dict[str, str] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        
        # Get configuration
        config = get_config()
        profiles_config = config.profiles_config
        
        # Initialize components
        profiles_dir = config.profiles_directory
        self.loader = ProfileLoader(profiles_dir)
        
        max_bootstrap = profiles_config.get('bootstrap_examples_count', 3)
        max_learned = profiles_config.get('learned_examples_count', 2)
        self.example_selector = ExampleSelector(max_bootstrap, max_learned)
        
        self.prompt_generator = PromptGenerator(self.example_selector)
        
        # Cache settings
        cache_config = config.cache_config
        self.cache_ttl = cache_config.get('system_prompts', {}).get('ttl_seconds', 3600)
        
        logger.info("ProfileManager initialized (singleton)")
    
    def initialize(self):
        """
        Load all profiles into memory from both filesystem and database.

        Call this at application startup to warm up the cache.
        Database profiles override filesystem profiles with the same ID.
        """
        logger.info("Loading all executive profiles...")

        # Load filesystem profiles first
        self._profiles = self.loader.load_all_profiles()
        fs_count = len(self._profiles)
        logger.info(f"Loaded {fs_count} profiles from filesystem: {list(self._profiles.keys())}")

        # Load database profiles (these override filesystem profiles)
        db_profiles = self._load_database_profiles()
        db_count = len(db_profiles)

        if db_profiles:
            for profile_id, profile_data in db_profiles.items():
                if profile_id in self._profiles:
                    logger.info(f"Database profile overriding filesystem: {profile_id}")
                self._profiles[profile_id] = profile_data
            logger.info(f"Loaded {db_count} profiles from database: {list(db_profiles.keys())}")

        if not self._profiles:
            logger.warning("No profiles loaded!")
        else:
            logger.info(
                f"Total {len(self._profiles)} profiles loaded "
                f"(filesystem: {fs_count}, database: {db_count}): "
                f"{list(self._profiles.keys())}"
            )

        # Register all profile IDs with the validator for dynamic validation
        self._register_dynamic_profile_ids()

    def _register_dynamic_profile_ids(self):
        """
        Register all loaded profile IDs with the validator for dynamic validation.

        This allows the ProfileIDValidator to recognize database profiles.
        """
        try:
            from .profile_validator import register_dynamic_profile_ids
            register_dynamic_profile_ids(set(self._profiles.keys()))
        except ImportError:
            logger.warning("Could not import register_dynamic_profile_ids")

    def _load_database_profiles(self) -> Dict[str, Dict[str, Any]]:
        """
        Load executive profiles from PostgreSQL database.

        Queries executive_profiles table for profiles with profile_data.
        Combines profile_data and voiceprint_data into unified profile format.

        Returns:
            Dict mapping profile IDs to profile dicts
        """
        profiles = {}
        conn = _get_postgres_connection()

        if not conn:
            logger.info("Database connection not available - skipping database profiles")
            return profiles

        try:
            with conn.cursor() as cur:
                # Query profiles with profile_data
                cur.execute("""
                    SELECT
                        ep.id,
                        ep.name,
                        ep.title,
                        ep.department,
                        ep.email,
                        ep.profile_data,
                        ep.voiceprint_data,
                        c.name as company_name,
                        c.id as company_id
                    FROM executive_profiles ep
                    LEFT JOIN companies c ON ep.company_id = c.id
                    WHERE ep.profile_data IS NOT NULL
                """)

                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]

                for row in rows:
                    try:
                        row_dict = dict(zip(columns, row))
                        profile_id = row_dict['id']

                        # Parse profile_data (JSONB returns dict or string)
                        profile_data = row_dict.get('profile_data') or {}
                        if isinstance(profile_data, str):
                            profile_data = json.loads(profile_data)

                        # Parse voiceprint_data
                        voiceprint_data = row_dict.get('voiceprint_data') or {}
                        if isinstance(voiceprint_data, str):
                            voiceprint_data = json.loads(voiceprint_data)

                        # Build unified profile structure
                        # Start with profile_data as base
                        profile = dict(profile_data)

                        # Ensure required fields are set
                        profile['id'] = profile_id
                        profile['name'] = profile.get('name') or row_dict.get('name') or profile_id
                        profile['name_english'] = profile.get('name_english') or profile.get('name')
                        profile['title'] = profile.get('title') or row_dict.get('title') or ''
                        profile['department'] = profile.get('department') or row_dict.get('department') or ''
                        profile['email'] = profile.get('email') or row_dict.get('email') or ''

                        # Add company info
                        if row_dict.get('company_name'):
                            if 'company_info' not in profile:
                                profile['company_info'] = {}
                            profile['company_info']['name'] = row_dict['company_name']
                            profile['company_info']['id'] = row_dict.get('company_id')

                        # Merge voiceprint data if available
                        if voiceprint_data:
                            profile['voiceprint'] = voiceprint_data
                            # Also merge key voiceprint sections into profile for compatibility
                            if 'communication_style' not in profile and 'style_markers' in voiceprint_data:
                                profile['communication_style'] = voiceprint_data.get('style_markers', {})
                            if 'communication_examples' not in profile and 'communication_examples' in voiceprint_data:
                                profile['communication_examples'] = voiceprint_data.get('communication_examples', [])

                        # Mark as database-sourced
                        profile['_source'] = 'database'

                        profiles[profile_id] = profile
                        logger.debug(f"Loaded database profile: {profile_id}")

                    except Exception as row_err:
                        logger.error(f"Error processing database profile row: {row_err}")
                        continue

        except Exception as e:
            logger.error(f"Failed to load database profiles: {e}")
        finally:
            conn.close()

        return profiles

    def refresh_database_profiles(self):
        """
        Refresh profiles from database without reloading filesystem profiles.

        Call this after onboarding new executives to make them available.
        """
        logger.info("Refreshing database profiles...")

        db_profiles = self._load_database_profiles()

        for profile_id, profile_data in db_profiles.items():
            self._profiles[profile_id] = profile_data
            # Invalidate any cached prompts for this profile
            self._invalidate_prompt_cache(profile_id)

        # Re-register profile IDs with validator
        self._register_dynamic_profile_ids()

        logger.info(f"Refreshed {len(db_profiles)} database profiles: {list(db_profiles.keys())}")
    
    def get_profile(self, executive_id: str) -> Optional[Dict[str, Any]]:
        """
        Get executive profile by ID.
        
        Args:
            executive_id: Executive profile ID (current or legacy)
            
        Returns:
            Profile dict or None if not found
        """
        # Normalize ID first (handles legacy IDs)
        try:
            from .profile_validator import normalize_profile_id
            normalized_id = normalize_profile_id(executive_id)
            
            if not normalized_id:
                logger.warning(f"Invalid profile ID: {executive_id}")
                return None
            
            profile = self._profiles.get(normalized_id)
            
            if not profile:
                logger.warning(f"Profile not found: {normalized_id} (original: {executive_id})")
                return None
            
            return profile
            
        except ImportError:
            # Fallback if validator not available
            profile = self._profiles.get(executive_id)
            
            if not profile:
                logger.warning(f"Profile not found: {executive_id}")
                return None
            
            return profile
    
    def get_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all loaded profiles.
        
        Returns:
            Dict mapping profile IDs to profile dicts
        """
        return self._profiles.copy()
    
    def generate_system_prompt(
        self,
        executive_id: str,
        include_examples: bool = True,
        use_cache: bool = True
    ) -> str:
        """
        Generate system prompt for an executive.

        DEPRECATED (2025-01-15): Use ConversationEngine.generate() instead.
        This method uses the legacy monolithic PromptGenerator which:
        - Has hardcoded rules that may conflict with conversation_engine/prompt/rules.py
        - Does not include context-aware calibration
        - Does not support dynamic section assembly

        The ConversationEngine provides:
        - Centralized rules from rules.py (single source of truth)
        - Context-aware response calibration
        - Modular section builders
        - Profile-specific overrides

        Migration:
            # OLD (deprecated):
            prompt = profile_manager.generate_system_prompt(executive_id)

            # NEW (recommended):
            from conversation_engine import ConversationEngine
            engine = ConversationEngine(profile_manager)
            system_prompt, user_prompt = engine.generate(
                executive_id=executive_id,
                query=query,
                path="standard"
            )

        Args:
            executive_id: Executive profile ID
            include_examples: Whether to include few-shot examples
            use_cache: Whether to use cached prompt if available

        Returns:
            System prompt string

        Raises:
            ValueError: If profile not found
        """
        import warnings
        warnings.warn(
            "ProfileManager.generate_system_prompt() is deprecated. "
            "Use ConversationEngine.generate() instead for centralized rules.",
            DeprecationWarning,
            stacklevel=2
        )

        # Check cache first
        if use_cache:
            cached = self._get_cached_prompt(executive_id)
            if cached:
                logger.debug(f"Using cached system prompt for {executive_id}")
                return cached
        
        # Get profile
        profile = self.get_profile(executive_id)
        if not profile:
            raise ValueError(f"Profile not found: {executive_id}")
        
        # Generate prompt
        prompt = self.prompt_generator.generate_system_prompt(
            profile,
            include_examples=include_examples
        )
        
        # Cache it
        if use_cache:
            self._cache_prompt(executive_id, prompt)
        
        return prompt
    
    def reload_profile(self, executive_id: str):
        """
        Reload a specific profile from disk.
        
        Args:
            executive_id: Executive profile ID to reload
        """
        # Find profile file
        profile_files = list(self.loader.profiles_directory.glob("*.json"))
        
        for file_path in profile_files:
            try:
                profile = self.loader.load_profile(file_path)
                if profile['id'] == executive_id:
                    # Update in-memory cache
                    self._profiles[executive_id] = profile
                    
                    # Invalidate system prompt cache
                    self._invalidate_prompt_cache(executive_id)
                    
                    logger.info(f"Reloaded profile: {executive_id}")
                    return
                    
            except Exception as e:
                logger.error(f"Error reloading {file_path}: {e}")
                continue
        
        logger.warning(f"Profile file not found for reload: {executive_id}")
    
    def reload_all_profiles(self):
        """Reload all profiles from disk."""
        logger.info("Reloading all profiles...")
        
        self._profiles = self.loader.load_all_profiles()
        self._system_prompts_cache.clear()
        self._cache_timestamps.clear()
        
        logger.info(f"Reloaded {len(self._profiles)} profiles")
    
    def _get_cached_prompt(self, executive_id: str) -> Optional[str]:
        """
        Get cached system prompt if still valid.
        
        Args:
            executive_id: Executive profile ID
            
        Returns:
            Cached prompt or None if not available/expired
        """
        if executive_id not in self._system_prompts_cache:
            return None
        
        # Check if expired
        timestamp = self._cache_timestamps.get(executive_id)
        if not timestamp:
            return None
        
        age = (datetime.now() - timestamp).total_seconds()
        if age > self.cache_ttl:
            logger.debug(f"System prompt cache expired for {executive_id}")
            return None
        
        return self._system_prompts_cache[executive_id]
    
    def _cache_prompt(self, executive_id: str, prompt: str):
        """
        Cache system prompt.
        
        Args:
            executive_id: Executive profile ID
            prompt: System prompt to cache
        """
        self._system_prompts_cache[executive_id] = prompt
        self._cache_timestamps[executive_id] = datetime.now()
        
        logger.debug(f"Cached system prompt for {executive_id}")
    
    def _invalidate_prompt_cache(self, executive_id: str):
        """
        Invalidate cached prompt for an executive.
        
        Args:
            executive_id: Executive profile ID
        """
        self._system_prompts_cache.pop(executive_id, None)
        self._cache_timestamps.pop(executive_id, None)
        
        logger.debug(f"Invalidated prompt cache for {executive_id}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.
        
        Returns:
            Dict with cache stats
        """
        return {
            'profiles_loaded': len(self._profiles),
            'prompts_cached': len(self._system_prompts_cache),
            'cache_ttl_seconds': self.cache_ttl,
            'profile_ids': list(self._profiles.keys()),
        }


# Global singleton instance
_manager = None


def get_profile_manager() -> ProfileManager:
    """
    Get the singleton ProfileManager instance.
    
    Returns:
        ProfileManager instance
    """
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager
