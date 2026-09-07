"""
Async PostgreSQL connection pool using asyncpg.
"""

import json
import logging
import asyncpg
from typing import Optional

from onboarding.config import POSTGRES_CONFIG

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn):
    """Set up JSON/JSONB codecs on each new connection."""
    await conn.set_type_codec(
        'jsonb',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog',
        format='text',
    )
    await conn.set_type_codec(
        'json',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog',
        format='text',
    )


async def get_pool() -> asyncpg.Pool:
    """Get or create the asyncpg connection pool."""
    global _pool
    if _pool is None or _pool._closed:
        _pool = await asyncpg.create_pool(
            host=POSTGRES_CONFIG["host"],
            port=POSTGRES_CONFIG["port"],
            database=POSTGRES_CONFIG["database"],
            user=POSTGRES_CONFIG["user"],
            password=POSTGRES_CONFIG["password"],
            min_size=2,
            max_size=10,
            init=_init_connection,
        )
        logger.info("asyncpg pool created for onboarding service")
    return _pool


async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool and not _pool._closed:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")
