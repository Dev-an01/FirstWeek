"""
Document Management API Routes.

Endpoints for uploading, listing, viewing, deleting, and restoring documents.
All routes are scoped by company_id and executive_id for multi-tenant isolation.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Query

from onboarding.models import (
    DocumentMetadata,
    DocumentDetail,
    DocumentListResponse,
    DocumentUploadResponse,
)
from onboarding.services.document_service import DocumentService
from onboarding.db import executives

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/companies/{company_id}/executives/{executive_id}/documents", tags=["Documents"])


async def _validate_executive_company(pool, company_id: str, executive_id: str):
    """Validate that executive belongs to company."""
    exec_row = await executives.get_executive(pool, executive_id)
    if not exec_row:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found")
    if exec_row.get("company_id") != company_id:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found in company '{company_id}'")
    return exec_row


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_documents(
    company_id: str,
    executive_id: str,
    files: List[UploadFile] = File(...),
    doc_type: str = Query("profile", description="Document type: 'profile' (default) for LLM extraction"),
    access_level: str = Query("internal", description="Access level: public, internal, executive, confidential"),
    auto_calibrate: bool = Query(False, description="Auto-trigger calibration after upload"),
    calibrate_mode: str = Query("incremental", description="Calibration mode if auto_calibrate=true"),
    request: Request = None,
):
    """
    Upload documents for an executive.

    Documents are parsed and their extracted text is stored in the database.
    Max 50MB per file. Supports PDF, DOCX, TXT, JSON.

    For company-wide knowledgebase documents (policies, procedures), use the
    /api/v1/companies/{company_id}/knowledgebase endpoint instead.

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
        files: List of files to upload.
        doc_type: Document type - 'profile' (default). Profile docs go through
                  LLM extraction pipeline to generate executive profiles.
        auto_calibrate: If true, start calibration job after upload.
        calibrate_mode: Calibration mode (full/incremental) if auto_calibrate.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    # Validate doc_type - only 'profile' is valid for executive documents
    # Knowledgebase docs must use the /knowledgebase endpoint
    if doc_type != "profile":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid doc_type '{doc_type}'. For knowledgebase documents, "
                   f"use POST /api/v1/companies/{company_id}/knowledgebase instead."
        )

    # Validate access_level
    valid_levels = ("public", "internal", "executive", "confidential")
    if access_level not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid access_level '{access_level}'. Must be one of: {valid_levels}"
        )

    service = DocumentService(pool)

    # Prepare file data
    file_data = []
    for file in files:
        content = await file.read()
        file_data.append({
            "filename": file.filename,
            "content": content,
            "content_type": file.content_type,
        })

    try:
        docs = await service.upload_documents(company_id, executive_id, file_data, doc_type=doc_type, access_level=access_level)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    total_text_length = sum(d.get("text_length", 0) for d in docs)

    # Optional auto-calibration
    job_id = None
    if auto_calibrate and docs:
        from onboarding.services.calibration_service import CalibrationService
        from onboarding.models import CalibrationMode, MergeStrategy

        cal_service = CalibrationService(pool)
        mode = CalibrationMode.FULL if calibrate_mode == "full" else CalibrationMode.INCREMENTAL
        job = await cal_service.start_calibration(
            company_id=company_id,
            executive_id=executive_id,
            mode=mode,
            extractors=None,
            merge_strategy=MergeStrategy.REPLACE,
            regenerate_embeddings=True,
        )
        job_id = job.get("id")

    return DocumentUploadResponse(
        company_id=company_id,
        executive_id=executive_id,
        documents=[DocumentMetadata(**d) for d in docs],
        total_text_length=total_text_length,
        job_id=job_id,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    company_id: str,
    executive_id: str,
    include_inactive: bool = Query(False, description="Include soft-deleted documents"),
    request: Request = None,
):
    """
    List all documents for an executive.

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
        include_inactive: If true, include soft-deleted documents.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    service = DocumentService(pool)
    docs = await service.list_documents(company_id, executive_id, include_inactive)

    return DocumentListResponse(
        company_id=company_id,
        executive_id=executive_id,
        total=len(docs),
        documents=[DocumentMetadata(**d) for d in docs],
    )


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(
    company_id: str,
    executive_id: str,
    doc_id: str,
    request: Request = None,
):
    """
    Get a single document with full extracted text.

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
        doc_id: Document UUID.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    service = DocumentService(pool)
    doc = await service.get_document(doc_id, company_id, executive_id)

    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    return DocumentDetail(**doc)


@router.delete("/{doc_id}")
async def delete_document(
    company_id: str,
    executive_id: str,
    doc_id: str,
    request: Request = None,
):
    """
    Soft delete a document.

    The document is marked as inactive but retained for history.

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
        doc_id: Document UUID.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    service = DocumentService(pool)
    result = await service.delete_document(doc_id, company_id, executive_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    return {
        "success": True,
        "message": f"Document '{doc_id}' deleted",
        "embeddings_deleted": result.get("embeddings_deleted", 0),
        "recalibration_needed": result.get("recalibration_needed", False),
    }


@router.post("/{doc_id}/restore")
async def restore_document(
    company_id: str,
    executive_id: str,
    doc_id: str,
    request: Request = None,
):
    """
    Restore a soft-deleted document.

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
        doc_id: Document UUID.
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    service = DocumentService(pool)
    restored = await service.restore_document(doc_id, company_id, executive_id)

    if not restored:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    return {"success": True, "message": f"Document '{doc_id}' restored"}
