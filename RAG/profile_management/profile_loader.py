"""
Profile Loader

Reads and validates executive profile JSON files.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ProfileLoadError(Exception):
    """Raised when profile loading fails."""
    pass


class ProfileLoader:
    """
    Loads executive profiles from JSON files.

    Handles JSON parsing, schema validation, error handling,
    and merging of voiceprint data for authentic voice generation.
    """

    def __init__(self, profiles_directory: Path):
        """
        Initialize ProfileLoader.

        Args:
            profiles_directory: Path to directory containing profile JSON files
        """
        self.profiles_directory = Path(profiles_directory)

        if not self.profiles_directory.exists():
            raise ProfileLoadError(
                f"Profiles directory not found: {self.profiles_directory}"
            )

        # Voiceprints directory is sibling to profiles directory
        self.voiceprints_directory = self.profiles_directory.parent / "voiceprints"
        if self.voiceprints_directory.exists():
            logger.info(f"Voiceprints directory found: {self.voiceprints_directory}")
        else:
            logger.warning(f"Voiceprints directory not found: {self.voiceprints_directory}")
    
    def load_profile(self, file_path: Path) -> Dict[str, Any]:
        """
        Load a single profile from JSON file and merge voiceprint data.

        Args:
            file_path: Path to profile JSON file

        Returns:
            Profile dict with voiceprint data merged

        Raises:
            ProfileLoadError: If loading or validation fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                profile = json.load(f)

            # Validate required fields
            self._validate_profile(profile, file_path)

            # CRITICAL: Merge voiceprint data for authentic voice generation
            profile = self._merge_voiceprint_data(profile, file_path)

            # Add metadata
            profile['_loaded_at'] = datetime.now().isoformat()
            profile['_file_path'] = str(file_path)

            logger.info(f"Loaded profile: {profile.get('name_english', 'Unknown')} from {file_path.name}")

            return profile

        except json.JSONDecodeError as e:
            raise ProfileLoadError(f"Invalid JSON in {file_path}: {e}")
        except Exception as e:
            raise ProfileLoadError(f"Error loading profile {file_path}: {e}")

    def _merge_voiceprint_data(self, profile: Dict[str, Any], profile_path: Path) -> Dict[str, Any]:
        """
        Merge voiceprint data into profile for authentic voice generation.

        VoicePrism architecture requires voiceprint data (signature openers, sign-offs,
        style markers, emojis, etc.) to be in the profile for PromptGenerator to use.

        Args:
            profile: Base profile dict
            profile_path: Path to profile file (used to find matching voiceprint)

        Returns:
            Profile dict with voiceprint data merged
        """
        if not self.voiceprints_directory or not self.voiceprints_directory.exists():
            logger.debug("No voiceprints directory - skipping voiceprint merge")
            return profile

        # Try to find matching voiceprint file
        # Profile: akiko_tanaka.json -> Voiceprint: akiko_tanaka_voiceprint.json
        profile_name = profile_path.stem  # e.g., "akiko_tanaka"
        voiceprint_file = self.voiceprints_directory / f"{profile_name}_voiceprint.json"

        if not voiceprint_file.exists():
            logger.warning(
                f"No voiceprint file found for {profile_name} at {voiceprint_file}. "
                "Voice DNA section will be limited."
            )
            return profile

        try:
            with open(voiceprint_file, 'r', encoding='utf-8') as f:
                voiceprint_data = json.load(f)

            # Merge voiceprint into profile
            if 'voiceprint' in voiceprint_data:
                profile['voiceprint'] = voiceprint_data['voiceprint']
                logger.info(
                    f"✓ Merged voiceprint data for {profile_name}: "
                    f"opener='{voiceprint_data['voiceprint'].get('signature_opener', {}).get('text', 'N/A')[:30]}...'"
                )

            # Also merge lexicon if present
            if 'lexicon' in voiceprint_data:
                profile['lexicon'] = voiceprint_data['lexicon']
                logger.debug(f"  Merged {len(voiceprint_data['lexicon'])} lexicon items")

            # Merge speaking_patterns_video for audio mode (natural speech)
            if 'speaking_patterns_video' in voiceprint_data:
                profile['speaking_patterns_video'] = voiceprint_data['speaking_patterns_video']
                logger.debug(f"  Merged speaking_patterns_video for audio mode")

            # Merge response_adaptation if present
            if 'response_adaptation' in voiceprint_data:
                profile['response_adaptation'] = voiceprint_data['response_adaptation']
                logger.debug(f"  Merged response_adaptation")

            return profile

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in voiceprint file {voiceprint_file}: {e}")
            return profile
        except Exception as e:
            logger.error(f"Error loading voiceprint {voiceprint_file}: {e}")
            return profile
    
    def load_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all profiles from the profiles directory.
        
        Returns:
            Dict mapping profile IDs to profile dicts
        """
        profiles = {}
        profile_files = list(self.profiles_directory.glob("*.json"))
        
        if not profile_files:
            logger.warning(f"No profile files found in {self.profiles_directory}")
            return profiles
        
        for file_path in profile_files:
            try:
                profile = self.load_profile(file_path)
                profile_id = profile['id']
                profiles[profile_id] = profile
                
            except ProfileLoadError as e:
                logger.error(f"Failed to load {file_path.name}: {e}")
                continue
        
        logger.info(f"Loaded {len(profiles)} profiles total")
        return profiles
    
    def _validate_profile(self, profile: Dict[str, Any], file_path: Path):
        """
        Validate profile has required fields.
        
        Args:
            profile: Profile dict to validate
            file_path: Path for error messages
            
        Raises:
            ProfileLoadError: If validation fails
        """
        required_fields = [
            'id',
            'name_english',
            'title',
            'communication_style',
            'core_values',
            'decision_making',
        ]
        
        missing = [field for field in required_fields if field not in profile]
        
        if missing:
            raise ProfileLoadError(
                f"Profile {file_path.name} missing required fields: {missing}"
            )
        
        # Validate communication_style structure
        comm_style = profile.get('communication_style', {})
        if not isinstance(comm_style, dict):
            raise ProfileLoadError(
                f"Profile {file_path.name}: communication_style must be a dict"
            )
        
        # Validate core_values structure
        core_values = profile.get('core_values', [])
        if not isinstance(core_values, list) or not core_values:
            raise ProfileLoadError(
                f"Profile {file_path.name}: core_values must be a non-empty list"
            )
    
    def get_profile_file_mtime(self, file_path: Path) -> float:
        """
        Get file modification time for hot reload detection.
        
        Args:
            file_path: Path to profile file
            
        Returns:
            Modification timestamp
        """
        return file_path.stat().st_mtime if file_path.exists() else 0.0
