"""
Profile & Voiceprint API Routes.

Endpoints for viewing and editing executive profiles and voiceprints.
All routes are scoped by company_id and executive_id for multi-tenant isolation.
"""

import logging
from fastapi import APIRouter, HTTPException, Request

from onboarding.models import (
    ProfileEditRequest,
    ProfileEditResponse,
    VoiceprintEditRequest,
    VoiceprintEditResponse,
    ProfileViewResponse,
)
from onboarding.services.profile_service import ProfileService
from onboarding.db import executives

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/companies/{company_id}/executives/{executive_id}", tags=["Profiles"])


async def _validate_executive_company(pool, company_id: str, executive_id: str):
    """Validate that executive belongs to company."""
    exec_row = await executives.get_executive(pool, executive_id)
    if not exec_row:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found")
    if exec_row.get("company_id") != company_id:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found in company '{company_id}'")
    return exec_row


@router.get("/profile", response_model=ProfileViewResponse)
async def get_profile(
    company_id: str,
    executive_id: str,
    request: Request = None,
):
    """
    Get full profile with voiceprint and validation report.

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    service = ProfileService(pool)
    data = await service.get_profile_with_voiceprint(company_id, executive_id)
    validation = await service.get_validation_report(company_id, executive_id)

    return ProfileViewResponse(
        profile=data["profile"],
        voiceprint=data["voiceprint"],
        validation=validation,
    )


@router.patch("/profile", response_model=ProfileEditResponse)
async def edit_profile(
    company_id: str,
    executive_id: str,
    body: ProfileEditRequest,
    request: Request = None,
):
    """
    Edit profile sections.

    Supports dot notation for nested keys:
    - "core_values": [...] replaces entire section
    - "communication_style.formality_scale": 7 updates nested field

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
        body: ProfileEditRequest with sections to update.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    service = ProfileService(pool)
    success, updated_sections = await service.update_profile(
        company_id, executive_id, body.sections
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update profile")

    # Optional embedding regeneration
    regenerate_job_id = None
    if body.regenerate_embeddings and updated_sections:
        from onboarding.services.calibration_service import CalibrationService
        from onboarding.models import CalibrationMode, MergeStrategy

        cal_service = CalibrationService(pool)
        # Run embedding-only job (no re-extraction, just re-embed current profile)
        job = await cal_service.trigger_embeddings_only(company_id, executive_id)
        regenerate_job_id = job.get("id")

    return ProfileEditResponse(
        success=True,
        updated_sections=updated_sections,
        regenerate_job_id=regenerate_job_id,
    )


@router.get("/voiceprint")
async def get_voiceprint(
    company_id: str,
    executive_id: str,
    request: Request = None,
):
    """
    Get full voiceprint.

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    service = ProfileService(pool)
    voiceprint = await service.get_voiceprint(company_id, executive_id)

    if voiceprint is None:
        raise HTTPException(status_code=404, detail="Voiceprint not found")

    return {"voiceprint": voiceprint}


@router.patch("/voiceprint", response_model=VoiceprintEditResponse)
async def edit_voiceprint(
    company_id: str,
    executive_id: str,
    body: VoiceprintEditRequest,
    request: Request = None,
):
    """
    Edit voiceprint sections.

    Supports dot notation for nested keys:
    - "casual_responses.greetings": ["Hi!", "Hello!"]
    - "style_markers.formality": 8

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
        body: VoiceprintEditRequest with sections to update.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    service = ProfileService(pool)
    success, updated_sections = await service.update_voiceprint(
        company_id, executive_id, body.sections
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update voiceprint")

    # Optional embedding regeneration
    regenerate_job_id = None
    if body.regenerate_embeddings and updated_sections:
        from onboarding.services.calibration_service import CalibrationService

        cal_service = CalibrationService(pool)
        job = await cal_service.trigger_embeddings_only(company_id, executive_id)
        regenerate_job_id = job.get("id")

    return VoiceprintEditResponse(
        success=True,
        updated_sections=updated_sections,
        regenerate_job_id=regenerate_job_id,
    )
