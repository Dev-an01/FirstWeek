"""
Onboarding job tracking CRUD.
"""

import logging
import uuid
from typing import Optional, Dict, Any
import asyncpg

logger = logging.getLogger(__name__)


async def create_job(
    pool: asyncpg.Pool,
    company_id: str,
    executive_id: str,
    job_type: str = "full_onboarding",
) -> Dict[str, Any]:
    """Create a new onboarding job."""
    job_id = str(uuid.uuid4())
    row = await pool.fetchrow(
        """
        INSERT INTO onboarding_jobs (id, company_id, executive_id, job_type, status, progress)
        VALUES ($1::uuid, $2, $3, $4, 'pending', 0.0)
        RETURNING id::text, company_id, executive_id, job_type, status, progress,
                  error_message, created_at, updated_at
        """,
        job_id,
        company_id,
        executive_id,
        job_type,
    )
    return dict(row) if row else {}


async def get_job(pool: asyncpg.Pool, job_id: str) -> Optional[Dict[str, Any]]:
    """Get a job by ID."""
    row = await pool.fetchrow(
        """
        SELECT id::text, company_id, executive_id, job_type, status, progress,
               error_message, created_at, updated_at
        FROM onboarding_jobs
        WHERE id = $1::uuid
        """,
        job_id,
    )
    return dict(row) if row else None


async def get_job_result(pool: asyncpg.Pool, job_id: str) -> Optional[Dict[str, Any]]:
    """Get the full job result including assembled profile/voiceprint."""
    row = await pool.fetchrow(
        """
        SELECT id::text, status, assembled_profile, assembled_voiceprint, validation_report
        FROM onboarding_jobs
        WHERE id = $1::uuid
        """,
        job_id,
    )
    return dict(row) if row else None


async def update_job_status(
    pool: asyncpg.Pool,
    job_id: str,
    status: str,
    progress: float = 0.0,
    error_message: Optional[str] = None,
):
    """Update job status and progress."""
    await pool.execute(
        """
        UPDATE onboarding_jobs
        SET status = $2, progress = $3, error_message = $4, updated_at = NOW()
        WHERE id = $1::uuid
        """,
        job_id,
        status,
        progress,
        error_message,
    )


async def update_job_extraction(pool: asyncpg.Pool, job_id: str, extraction_results: dict):
    """Store extraction results."""
    # Pass dict directly - asyncpg's jsonb codec handles serialization
    await pool.execute(
        """
        UPDATE onboarding_jobs
        SET extraction_results = $2, updated_at = NOW()
        WHERE id = $1::uuid
        """,
        job_id,
        extraction_results,
    )


async def update_job_assembled(
    pool: asyncpg.Pool,
    job_id: str,
    profile: dict,
    voiceprint: dict,
):
    """Store assembled profile and voiceprint."""
    # Pass dicts directly - asyncpg's jsonb codec handles serialization
    await pool.execute(
        """
        UPDATE onboarding_jobs
        SET assembled_profile = $2,
            assembled_voiceprint = $3,
            updated_at = NOW()
        WHERE id = $1::uuid
        """,
        job_id,
        profile,
        voiceprint,
    )


async def update_job_validation(pool: asyncpg.Pool, job_id: str, report: dict):
    """Store validation report."""
    # Pass dict directly - asyncpg's jsonb codec handles serialization
    await pool.execute(
        """
        UPDATE onboarding_jobs
        SET validation_report = $2, updated_at = NOW()
        WHERE id = $1::uuid
        """,
        job_id,
        report,
    )


async def store_input_documents(pool: asyncpg.Pool, job_id: str, documents: list):
    """Store input document metadata on the job."""
    # Pass list directly - asyncpg's jsonb codec handles serialization
    await pool.execute(
        """
        UPDATE onboarding_jobs
        SET input_documents = $2, updated_at = NOW()
        WHERE id = $1::uuid
        """,
        job_id,
        documents,
    )
