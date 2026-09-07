"""
Cognitive Profile Loader - Loads all cognitive data from PostgreSQL.

This is the foundation of the cognitive twin system. All cognitive data
(thinking patterns, red flags, decision cases, communication style, etc.)
comes from the database, NOT from hardcoded dictionaries.

Key principle: The database is the brain.

Enhancement: casual_responses are loaded from voiceprint JSON files and
merged into profile_data to support natural conversational responses.
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from .config import COGNITIVE_CONFIG

# Path to voiceprint JSON files
VOICEPRINT_DIR = Path(__file__).parent.parent / "test_data" / "voiceprints"

# Only explicitly registered profiles have voiceprints.
VOICEPRINT_FILES = {}

logger = logging.getLogger(__name__)


@dataclass
class ThinkingPatterns:
    """Executive's thinking patterns extracted from profile_data."""
    framework_examples: List[str] = field(default_factory=list)
    typical_questions: List[str] = field(default_factory=list)
    thought_organization: str = ""
    decision_approach: str = ""

    def to_dict(self) -> dict:
        return {
            "framework_examples": self.framework_examples,
            "typical_questions": self.typical_questions,
            "thought_organization": self.thought_organization,
            "decision_approach": self.decision_approach,
        }


@dataclass
class RedFlags:
    """Executive's red flags and guardrails."""
    never_approve: List[str] = field(default_factory=list)
    always_do: List[str] = field(default_factory=list)
    ai_should_escalate_when: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "never_approve": self.never_approve,
            "always_do": self.always_do,
            "ai_should_escalate_when": self.ai_should_escalate_when,
        }


@dataclass
class DecisionCase:
    """A single decision case from the executive's history."""
    id: str
    title: str
    situation: str
    options_considered: List[dict] = field(default_factory=list)
    decision_made: str = ""
    rationale: str = ""
    outcome: str = ""
    lessons_learned: str = ""
    category: str = ""
    date: Optional[datetime] = None
    confidence: float = 0.5
    is_precedent: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "situation": self.situation,
            "options_considered": self.options_considered,
            "decision_made": self.decision_made,
            "rationale": self.rationale,
            "outcome": self.outcome,
            "lessons_learned": self.lessons_learned,
            "category": self.category,
            "date": self.date.isoformat() if self.date else None,
            "confidence": self.confidence,
            "is_precedent": self.is_precedent,
        }


@dataclass
class CommunicationStyle:
    """Executive's communication style parameters."""
    formality_scale: int = 5
    directness_scale: int = 5
    warmth_scale: int = 5
    emoji_usage: str = "none"
    preferred_emojis: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "formality_scale": self.formality_scale,
            "directness_scale": self.directness_scale,
            "warmth_scale": self.warmth_scale,
            "emoji_usage": self.emoji_usage,
            "preferred_emojis": self.preferred_emojis,
        }


@dataclass
class DomainAffinity:
    """Executive's domain affinity for cognitive lens."""
    primary_domain: str = ""
    boost_keywords: List[str] = field(default_factory=list)
    domain_description: str = ""

    def to_dict(self) -> dict:
        return {
            "primary_domain": self.primary_domain,
            "boost_keywords": self.boost_keywords,
            "domain_description": self.domain_description,
        }


@dataclass
class CognitiveProfile:
    """Complete cognitive profile for an executive."""
    profile_id: str
    name: str
    title: str
    department: str

    # Cognitive data
    thinking_patterns: ThinkingPatterns = field(default_factory=ThinkingPatterns)
    red_flags: RedFlags = field(default_factory=RedFlags)
    decision_cases: List[DecisionCase] = field(default_factory=list)
    communication_style: CommunicationStyle = field(default_factory=CommunicationStyle)
    domain_affinity: DomainAffinity = field(default_factory=DomainAffinity)

    # Core values (for context-aware responses)
    core_values: List[dict] = field(default_factory=list)

    # Raw profile data for fallback
    raw_profile_data: dict = field(default_factory=dict)

    # Cache metadata
    loaded_at: datetime = field(default_factory=datetime.now)

    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if this profile has expired."""
        age = (datetime.now() - self.loaded_at).total_seconds()
        return age > ttl_seconds

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "title": self.title,
            "department": self.department,
            "thinking_patterns": self.thinking_patterns.to_dict(),
            "red_flags": self.red_flags.to_dict(),
            "decision_cases": [dc.to_dict() for dc in self.decision_cases],
            "communication_style": self.communication_style.to_dict(),
            "domain_affinity": self.domain_affinity.to_dict(),
            "core_values": self.core_values,
        }


class CognitiveProfileLoader:
    """
    Loads cognitive profiles from PostgreSQL.

    This is the foundation of the cognitive twin system. All cognitive data
    comes from the database's profile_data JSONB column.

    Thread-safe with connection pooling and caching.
    """

    # Singleton instance
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_config: Optional[dict] = None):
        """
        Initialize the CognitiveProfileLoader.

        Args:
            db_config: Database configuration dict. If None, uses default config.
        """
        # Only initialize once
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._db_config = db_config or self._get_default_config()
        self._connection_pool = None
        self._profile_cache: Dict[str, CognitiveProfile] = {}
        self._cache_ttl = COGNITIVE_CONFIG.get("cache", {}).get("profile_ttl_seconds", 3600)

        # Initialize connection pool
        self._init_connection_pool()

        logger.info("CognitiveProfileLoader initialized (singleton)")

    def _get_default_config(self) -> dict:
        """Get default database configuration."""
        import os
        return {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "database": os.getenv("POSTGRES_DB", "ai_officer"),
            "user": os.getenv("POSTGRES_USER", "postgres"),
            "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
        }

    def _init_connection_pool(self):
        """Initialize the connection pool."""
        try:
            self._connection_pool = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                host=self._db_config["host"],
                port=self._db_config["port"],
                database=self._db_config["database"],
                user=self._db_config["user"],
                password=self._db_config["password"],
            )
            logger.debug("CognitiveProfileLoader connection pool created")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            # Don't raise - allow fallback to cached data or defaults

    def _get_connection(self):
        """Get a connection from the pool."""
        if self._connection_pool is None:
            self._init_connection_pool()
        if self._connection_pool:
            return self._connection_pool.getconn()
        return None

    def _return_connection(self, conn):
        """Return a connection to the pool."""
        if self._connection_pool and conn:
            self._connection_pool.putconn(conn)

    def load_profile(self, profile_id: str, use_cache: bool = True, company_id: str = None) -> Optional[CognitiveProfile]:
        """
        Load cognitive profile for an executive.

        Args:
            profile_id: Executive profile ID (e.g., "exec_001_test")
            use_cache: Whether to use cached profile if available
            company_id: Optional company ID for tenant isolation

        Returns:
            CognitiveProfile or None if not found
        """
        # Check cache first
        if use_cache and profile_id in self._profile_cache:
            cached = self._profile_cache[profile_id]
            if not cached.is_expired(self._cache_ttl):
                logger.debug(f"Using cached cognitive profile for {profile_id}")
                return cached

        # Load from database
        profile = self._load_from_database(profile_id, company_id=company_id)

        if profile:
            # Cache it
            self._profile_cache[profile_id] = profile
            logger.info(f"Loaded cognitive profile for {profile_id}")

        return profile

    def _load_from_database(self, profile_id: str, company_id: str = None) -> Optional[CognitiveProfile]:
        """Load profile from PostgreSQL with optional company_id tenant filter."""
        conn = None
        try:
            conn = self._get_connection()
            if not conn:
                logger.warning(f"No database connection for profile {profile_id}")
                return None

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Load executive profile (including voiceprint_data for dynamic profiles)
                if company_id:
                    cur.execute("""
                        SELECT
                            id, name, title, department,
                            profile_data, voiceprint_data,
                            formality_scale, directness_scale, warmth_scale
                        FROM executive_profiles
                        WHERE id = %s AND company_id = %s
                    """, (profile_id, company_id))
                else:
                    cur.execute("""
                        SELECT
                            id, name, title, department,
                            profile_data, voiceprint_data,
                            formality_scale, directness_scale, warmth_scale
                        FROM executive_profiles
                        WHERE id = %s
                    """, (profile_id,))

                row = cur.fetchone()
                if not row:
                    logger.warning(f"Profile not found in database: {profile_id}")
                    return None

                # Load decision cases
                if company_id:
                    cur.execute("""
                        SELECT
                            id, title, date, category,
                            situation, decision_made, rationale,
                            outcome, lessons_learned,
                            confidence, precedent, full_content
                        FROM decision_cases
                        WHERE executive_id = %s AND company_id = %s
                        ORDER BY date DESC
                        LIMIT 20
                    """, (profile_id, company_id))
                else:
                    cur.execute("""
                        SELECT
                            id, title, date, category,
                            situation, decision_made, rationale,
                            outcome, lessons_learned,
                            confidence, precedent, full_content
                        FROM decision_cases
                        WHERE executive_id = %s
                        ORDER BY date DESC
                        LIMIT 20
                    """, (profile_id,))

                decision_rows = cur.fetchall()

            # Parse profile data
            profile_data = row.get("profile_data", {}) or {}

            # Merge voiceprint data: try DB voiceprint_data first, fall back to filesystem
            db_voiceprint = row.get("voiceprint_data")
            if isinstance(db_voiceprint, str):
                try:
                    db_voiceprint = json.loads(db_voiceprint)
                except (json.JSONDecodeError, TypeError):
                    db_voiceprint = None
            profile_data = self._merge_voiceprint_data(profile_id, profile_data, db_voiceprint)

            # Build CognitiveProfile
            return self._build_cognitive_profile(row, profile_data, decision_rows)

        except Exception as e:
            logger.error(f"Failed to load profile {profile_id} from database: {e}")
            return None
        finally:
            if conn:
                self._return_connection(conn)

    def _merge_voiceprint_data(self, profile_id: str, profile_data: dict, db_voiceprint_data: dict = None) -> dict:
        """
        Merge voiceprint data into profile_data.

        Priority order:
        1. Database voiceprint_data column (for dynamically onboarded executives)
        2. Filesystem JSON files (for legacy/hardcoded profiles like sample)

        This merges:
        - voiceprint (style_markers, signature_opener, sign_off, etc.)
        - casual_responses (greetings, acknowledgments, etc.)
        """
        voiceprint_data = None

        # Try DB voiceprint_data first (from onboarding pipeline)
        if db_voiceprint_data and isinstance(db_voiceprint_data, dict):
            voiceprint_data = db_voiceprint_data
            logger.debug(f"Using DB voiceprint_data for {profile_id}")
        else:
            # Fall back to filesystem JSON
            voiceprint_file = VOICEPRINT_FILES.get(profile_id)
            if voiceprint_file:
                voiceprint_path = VOICEPRINT_DIR / voiceprint_file
                if voiceprint_path.exists():
                    try:
                        with open(voiceprint_path, 'r', encoding='utf-8') as f:
                            voiceprint_data = json.load(f)
                        logger.debug(f"Using filesystem voiceprint for {profile_id}")
                    except Exception as e:
                        logger.warning(f"Failed to load voiceprint from {voiceprint_path}: {e}")

        if not voiceprint_data:
            logger.debug(f"No voiceprint data available for {profile_id}")
            return profile_data

        # Ensure voiceprint key exists in profile_data
        if "voiceprint" not in profile_data:
            profile_data["voiceprint"] = {}

        # Merge voiceprint structure (style_markers, signature_opener, etc.)
        voiceprint_structure = voiceprint_data.get("voiceprint", {})
        if voiceprint_structure:
            for key, value in voiceprint_structure.items():
                if key not in profile_data["voiceprint"]:
                    profile_data["voiceprint"][key] = value
            logger.debug(f"Merged voiceprint structure with {len(voiceprint_structure)} keys for {profile_id}")

        # Merge casual_responses (at root level in voiceprint data)
        casual_responses = voiceprint_data.get("casual_responses", {})
        if casual_responses:
            profile_data["voiceprint"]["casual_responses"] = casual_responses
            logger.debug(f"Merged {len(casual_responses)} casual response categories for {profile_id}")

        return profile_data

    def _build_cognitive_profile(
        self,
        row: dict,
        profile_data: dict,
        decision_rows: List[dict]
    ) -> CognitiveProfile:
        """Build CognitiveProfile from database data."""

        # Extract thinking patterns
        thinking_data = profile_data.get("thinking_patterns", {})
        thinking_patterns = ThinkingPatterns(
            framework_examples=thinking_data.get("framework_examples", []),
            typical_questions=thinking_data.get("typical_questions", []),
            thought_organization=thinking_data.get("thought_organization", ""),
            decision_approach=thinking_data.get("decision_approach", ""),
        )

        # Extract red flags
        red_flags_data = profile_data.get("red_flags", {})
        red_flags = RedFlags(
            never_approve=red_flags_data.get("never_approve", []),
            always_do=red_flags_data.get("always_do", []),
            ai_should_escalate_when=red_flags_data.get("ai_should_escalate_when", []),
        )

        # Build decision cases
        decision_cases = []
        for dc_row in decision_rows:
            full_content = dc_row.get("full_content", {}) or {}
            decision_cases.append(DecisionCase(
                id=dc_row.get("id", ""),
                title=dc_row.get("title", ""),
                situation=dc_row.get("situation", ""),
                options_considered=full_content.get("options_considered", []),
                decision_made=dc_row.get("decision_made", ""),
                rationale=dc_row.get("rationale", ""),
                outcome=dc_row.get("outcome", ""),
                lessons_learned=dc_row.get("lessons_learned", ""),
                category=dc_row.get("category", ""),
                date=dc_row.get("date"),
                confidence=float(dc_row.get("confidence", 0.5) or 0.5),
                is_precedent=dc_row.get("precedent", False),
            ))

        # Extract communication style
        comm_style_data = profile_data.get("communication_style", {})
        style_markers = profile_data.get("voiceprint", {}).get("style_markers", {})
        communication_style = CommunicationStyle(
            formality_scale=row.get("formality_scale") or style_markers.get("formality", 5),
            directness_scale=row.get("directness_scale") or style_markers.get("directness", 5),
            warmth_scale=row.get("warmth_scale") or style_markers.get("warmth", 5),
            emoji_usage=style_markers.get("emoji_usage", "none"),
            preferred_emojis=style_markers.get("preferred_emojis", []),
        )

        # Extract domain affinity
        domain_data = profile_data.get("domain_affinity", {})
        # Fallback: infer from title/department
        primary_domain = domain_data.get("primary_domain", "")
        if not primary_domain:
            title = row.get("title", "").lower()
            if "cfo" in title or "finance" in title:
                primary_domain = "finance"
            elif "cto" in title or "tech" in title or "engineer" in title:
                primary_domain = "technology"
            elif "cmo" in title or "marketing" in title:
                primary_domain = "marketing"
            elif "ceo" in title or "chief executive" in title:
                primary_domain = "strategy"
            else:
                primary_domain = "general"

        domain_affinity = DomainAffinity(
            primary_domain=primary_domain,
            boost_keywords=domain_data.get("boost_keywords", []),
            domain_description=domain_data.get("description", ""),
        )

        # Extract core values
        core_values = profile_data.get("core_values", [])

        return CognitiveProfile(
            profile_id=row.get("id", ""),
            name=row.get("name", ""),
            title=row.get("title", ""),
            department=row.get("department", ""),
            thinking_patterns=thinking_patterns,
            red_flags=red_flags,
            decision_cases=decision_cases,
            communication_style=communication_style,
            domain_affinity=domain_affinity,
            core_values=core_values,
            raw_profile_data=profile_data,
            loaded_at=datetime.now(),
        )

    def get_thinking_patterns(self, profile_id: str) -> Optional[ThinkingPatterns]:
        """Get thinking patterns for an executive."""
        profile = self.load_profile(profile_id)
        return profile.thinking_patterns if profile else None

    def get_red_flags(self, profile_id: str) -> Optional[RedFlags]:
        """Get red flags for an executive."""
        profile = self.load_profile(profile_id)
        return profile.red_flags if profile else None

    def get_decision_cases(self, profile_id: str) -> List[DecisionCase]:
        """Get decision cases for an executive."""
        profile = self.load_profile(profile_id)
        return profile.decision_cases if profile else []

    def get_communication_style(self, profile_id: str) -> Optional[CommunicationStyle]:
        """Get communication style for an executive."""
        profile = self.load_profile(profile_id)
        return profile.communication_style if profile else None

    def get_domain_affinity(self, profile_id: str) -> Optional[DomainAffinity]:
        """Get domain affinity for an executive."""
        profile = self.load_profile(profile_id)
        return profile.domain_affinity if profile else None

    def get_core_values(self, profile_id: str) -> List[dict]:
        """Get core values for an executive."""
        profile = self.load_profile(profile_id)
        return profile.core_values if profile else []

    def invalidate_cache(self, profile_id: Optional[str] = None):
        """
        Invalidate cached profiles.

        Args:
            profile_id: Specific profile to invalidate, or None for all
        """
        if profile_id:
            self._profile_cache.pop(profile_id, None)
            logger.debug(f"Invalidated cache for {profile_id}")
        else:
            self._profile_cache.clear()
            logger.debug("Invalidated all cached profiles")

    def preload_all_profiles(self) -> int:
        """
        Preload all executive profiles into cache.

        Returns:
            Number of profiles loaded
        """
        conn = None
        try:
            conn = self._get_connection()
            if not conn:
                logger.warning("No database connection for preloading profiles")
                return 0

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id FROM executive_profiles")
                rows = cur.fetchall()

            count = 0
            for row in rows:
                profile_id = row["id"]
                profile = self.load_profile(profile_id, use_cache=False)
                if profile:
                    count += 1

            logger.info(f"Preloaded {count} cognitive profiles")
            return count

        except Exception as e:
            logger.error(f"Failed to preload profiles: {e}")
            return 0
        finally:
            if conn:
                self._return_connection(conn)

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "profiles_cached": len(self._profile_cache),
            "cache_ttl_seconds": self._cache_ttl,
            "cached_profile_ids": list(self._profile_cache.keys()),
        }

    def close(self):
        """Close the connection pool."""
        if self._connection_pool:
            self._connection_pool.closeall()
            logger.info("CognitiveProfileLoader connection pool closed")


# Global singleton instance
_loader: Optional[CognitiveProfileLoader] = None


def get_cognitive_profile_loader() -> CognitiveProfileLoader:
    """Get the singleton CognitiveProfileLoader instance."""
    global _loader
    if _loader is None:
        _loader = CognitiveProfileLoader()
    return _loader
