"""
Database Client for Voice Profile Management

Manages executive voice profiles in the chat-service PostgreSQL database.
Stores voice samples, metadata, and service-specific configurations.
"""

import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncpg

logger = logging.getLogger(__name__)


class VoiceProfileDBClient:
    """
    Database client for voice profile management.

    Connects to chat-service PostgreSQL database to store and retrieve
    executive voice profiles for voice cloning/personalization.
    """

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize database client.

        Args:
            connection_string: PostgreSQL connection string
                             If None, reads from CHAT_DATABASE_URL or DATABASE_URL env var
        """
        self.connection_string = connection_string or os.getenv(
            'CHAT_DATABASE_URL',
            os.getenv('DATABASE_URL')
        )

        if not self.connection_string:
            raise ValueError("Database connection string not provided")

        self.pool = None
        logger.info("VoiceProfileDBClient initialized")

    async def connect(self):
        """Create database connection pool"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connection pool created")

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")

    async def create_profile(
        self,
        profile_id: str,
        profile_name: str,
        service: str,
        config: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new voice profile.

        Args:
            profile_id: Unique profile identifier (e.g., 'exec_001')
            profile_name: Human-readable name (e.g., 'John Doe - CEO')
            service: TTS service ('piper', 'gcp', 'gcp_chirp3')
            config: Service-specific configuration
            metadata: Optional metadata (language, gender, description, etc.)

        Returns:
            Created voice profile dictionary

        Example:
            await db.create_profile(
                profile_id='exec_001',
                profile_name='John Doe - CEO',
                service='gcp_chirp3',
                config={'voice_model_path': '/models/exec_001'},
                metadata={'language': 'en-US', 'gender': 'male'}
            )
        """
        await self.connect()

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO voice_profiles (
                    profile_id, profile_name, service, config, metadata, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING *
            """, profile_id, profile_name, service, config, metadata or {}, datetime.utcnow(), datetime.utcnow())

            return dict(row)

    async def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a voice profile by ID.

        Args:
            profile_id: Profile identifier

        Returns:
            Voice profile dictionary or None if not found
        """
        await self.connect()

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM voice_profiles WHERE profile_id = $1
            """, profile_id)

            return dict(row) if row else None

    async def list_profiles(
        self,
        service: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List voice profiles.

        Args:
            service: Optional filter by TTS service
            limit: Maximum number of profiles to return

        Returns:
            List of voice profile dictionaries
        """
        await self.connect()

        async with self.pool.acquire() as conn:
            if service:
                rows = await conn.fetch("""
                    SELECT * FROM voice_profiles
                    WHERE service = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, service, limit)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM voice_profiles
                    ORDER BY created_at DESC
                    LIMIT $1
                """, limit)

            return [dict(row) for row in rows]

    async def update_profile(
        self,
        profile_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update a voice profile.

        Args:
            profile_id: Profile identifier
            updates: Dictionary of fields to update (config, metadata, etc.)

        Returns:
            Updated voice profile dictionary or None if not found
        """
        await self.connect()

        allowed_fields = ['profile_name', 'service', 'config', 'metadata']
        set_clauses = []
        values = []
        param_idx = 1

        for field, value in updates.items():
            if field in allowed_fields:
                set_clauses.append(f"{field} = ${param_idx}")
                values.append(value)
                param_idx += 1

        if not set_clauses:
            return await self.get_profile(profile_id)

        set_clauses.append(f"updated_at = ${param_idx}")
        values.append(datetime.utcnow())
        param_idx += 1

        values.append(profile_id)

        query = f"""
            UPDATE voice_profiles
            SET {', '.join(set_clauses)}
            WHERE profile_id = ${param_idx}
            RETURNING *
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)
            return dict(row) if row else None

    async def delete_profile(self, profile_id: str) -> bool:
        """
        Delete a voice profile.

        Args:
            profile_id: Profile identifier

        Returns:
            True if deleted, False if not found
        """
        await self.connect()

        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM voice_profiles WHERE profile_id = $1
            """, profile_id)

            return result == "DELETE 1"

    async def add_sample(
        self,
        profile_id: str,
        sample_path: str,
        duration_seconds: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a voice sample to a profile.

        Args:
            profile_id: Profile identifier
            sample_path: Path to audio sample file
            duration_seconds: Duration of the sample
            metadata: Optional sample metadata

        Returns:
            Created voice sample dictionary
        """
        await self.connect()

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO voice_samples (
                    profile_id, sample_path, duration_seconds, metadata, created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
            """, profile_id, sample_path, duration_seconds, metadata or {}, datetime.utcnow())

            return dict(row)

    async def get_samples(self, profile_id: str) -> List[Dict[str, Any]]:
        """
        Get all voice samples for a profile.

        Args:
            profile_id: Profile identifier

        Returns:
            List of voice sample dictionaries
        """
        await self.connect()

        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM voice_samples
                WHERE profile_id = $1
                ORDER BY created_at DESC
            """, profile_id)

            return [dict(row) for row in rows]
