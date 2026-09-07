"""
Calibration API Routes.

Endpoints for calibrating/re-extracting executive profiles.
All routes are scoped by company_id and executive_id for multi-tenant isolation.
"""

import logging
from fastapi import APIRouter, HTTPException, Request

from onboarding.models import (
    CalibrationRequest,
    CalibrationResponse,
    CalibrationMode,
    MergeStrategy,
    JobStatusResponse,
    JobResultResponse,
)
from onboarding.services.calibration_service import CalibrationService
from onboarding.db import executives, jobs
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/companies/{company_id}/executives/{executive_id}", tags=["Calibration"])


async def _validate_executive_company(pool, company_id: str, executive_id: str):
    """Validate that executive belongs to company."""
    exec_row = await executives.get_executive(pool, executive_id)
    if not exec_row:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found")
    if exec_row.get("company_id") != company_id:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found in company '{company_id}'")
    return exec_row


@router.post("/calibrate", response_model=CalibrationResponse)
async def calibrate_profile(
    company_id: str,
    executive_id: str,
    body: CalibrationRequest,
    request: Request = None,
):
    """
    Run calibration to re-extract and update executive profile.

    **Full calibration** (mode="full"):
    - Re-runs all 7 extractors on stored documents
    - Replaces entire profile and voiceprint
    - Runs synthesis LLM for consistency check

    **Incremental calibration** (mode="incremental"):
    - Runs only specified extractors
    - Merges results into existing profile
    - Faster for targeted updates

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
        body: CalibrationRequest with mode, extractors, merge_strategy.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    service = CalibrationService(pool)

    try:
        # Convert extractors enum values to strings if needed
        extractors = None
        if body.extractors:
            extractors = [e.value if hasattr(e, 'value') else e for e in body.extractors]

        result = await service.start_calibration(
            company_id=company_id,
            executive_id=executive_id,
            mode=body.mode,
            extractors=extractors,
            merge_strategy=body.merge_strategy,
            regenerate_embeddings=body.regenerate_embeddings,
        )

        return CalibrationResponse(
            job_id=result["id"],
            status=result["status"],
            mode=result["mode"],
            extractors=result.get("extractors"),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    company_id: str,
    executive_id: str,
    job_id: str,
    request: Request = None,
):
    """
    Get status of a calibration or onboarding job.

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
        job_id: Job UUID.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    job = await jobs.get_job(pool, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Verify job belongs to this company/executive
    if job.get("company_id") != company_id or job.get("executive_id") != executive_id:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return JobStatusResponse(**job)


@router.get("/jobs/{job_id}/result", response_model=JobResultResponse)
async def get_job_result(
    company_id: str,
    executive_id: str,
    job_id: str,
    request: Request = None,
):
    """
    Get result of a completed calibration or onboarding job.

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
        job_id: Job UUID.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    result = await jobs.get_job_result(pool, job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Verify job belongs to this company/executive (need to fetch full job)
    job = await jobs.get_job(pool, job_id)
    if job.get("company_id") != company_id or job.get("executive_id") != executive_id:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    def _parse_json(val):
        if val is None:
            return None
        if isinstance(val, str):
            return json.loads(val)
        return val

    return JobResultResponse(
        id=str(result["id"]),
        status=result["status"],
        profile=_parse_json(result.get("assembled_profile")),
        voiceprint=_parse_json(result.get("assembled_voiceprint")),
        validation_report=_parse_json(result.get("validation_report")),
    )
