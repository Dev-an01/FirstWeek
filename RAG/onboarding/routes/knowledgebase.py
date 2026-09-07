"""
Knowledgebase API Routes.

Endpoints for uploading, listing, viewing, and deleting company-wide
knowledgebase documents. Knowledgebase documents bypass the LLM extraction
pipeline and go directly to embeddings with executive_id=NULL.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Query

from onboarding.models import (
    KnowledgebaseDocumentMetadata,
    KnowledgebaseUploadResponse,
    KnowledgebaseListResponse,
    DocumentDetail,
)
from onboarding.services.knowledgebase_service import KnowledgebaseService
from onboarding.db import companies

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/companies/{company_id}/knowledgebase",
    tags=["Knowledgebase"]
)


async def _validate_company(pool, company_id: str):
    """Validate that company exists."""
    company = await companies.get_company(pool, company_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")
    return company


@router.post("", response_model=KnowledgebaseUploadResponse, status_code=201)
async def upload_knowledgebase_documents(
    company_id: str,
    files: List[UploadFile] = File(...),
    access_level: str = Query("internal", description="Access level: public, internal, executive, confidential"),
    request: Request = None,
):
    """
    Upload knowledgebase documents for a company.

    Knowledgebase documents are company-wide resources (policies, procedures,
    guidelines) that are shared by all executives. They bypass the LLM
    extraction pipeline and go directly to embeddings.

    - Documents are parsed and chunked (1000 chars, 200 overlap)
    - Chunks are embedded with source_type='policy' and executive_id=NULL
    - All executives in the company can access these via RAG queries

    Args:
        company_id: Company ID.
        files: List of files to upload (PDF, DOCX, TXT, JSON supported).

    Returns:
        Upload result with document metadata and embedding status.
    """
    pool = request.app.state.pool
    await _validate_company(pool, company_id)

    # Validate access_level
    valid_levels = ("public", "internal", "executive", "confidential")
    if access_level not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid access_level '{access_level}'. Must be one of: {valid_levels}"
        )

    service = KnowledgebaseService(pool)

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
        result = await service.upload_knowledgebase_documents(company_id, file_data, access_level=access_level)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Convert to response model
    doc_metadata = []
    for doc in result["documents"]:
        doc_metadata.append(KnowledgebaseDocumentMetadata(
            id=doc["id"],
            company_id=doc["company_id"],
            filename=doc["filename"],
            content_type=doc.get("content_type"),
            file_size=doc.get("file_size", 0),
            text_length=doc.get("text_length", 0),
            chunk_count=doc.get("chunk_count", 0),
            is_active=doc.get("is_active", True),
            uploaded_at=doc.get("uploaded_at"),
            updated_at=doc.get("updated_at"),
        ))

    return KnowledgebaseUploadResponse(
        company_id=company_id,
        documents=doc_metadata,
        total_text_length=result["total_text_length"],
        total_chunks=result["total_chunks"],
        embedding_status=result["embedding_status"],
    )


@router.get("", response_model=KnowledgebaseListResponse)
async def list_knowledgebase_documents(
    company_id: str,
    include_inactive: bool = Query(False, description="Include soft-deleted documents"),
    request: Request = None,
):
    """
    List all knowledgebase documents for a company.

    Args:
        company_id: Company ID.
        include_inactive: If true, include soft-deleted documents.

    Returns:
        List of knowledgebase document metadata.
    """
    pool = request.app.state.pool
    await _validate_company(pool, company_id)

    service = KnowledgebaseService(pool)
    docs = await service.list_knowledgebase(company_id, include_inactive)

    # Convert to response model
    doc_metadata = []
    for doc in docs:
        doc_metadata.append(KnowledgebaseDocumentMetadata(
            id=doc["id"],
            company_id=doc["company_id"],
            filename=doc["filename"],
            content_type=doc.get("content_type"),
            file_size=doc.get("file_size", 0),
            text_length=doc.get("text_length", 0),
            chunk_count=0,  # Not stored, would need to count embeddings
            is_active=doc.get("is_active", True),
            uploaded_at=doc.get("uploaded_at"),
            updated_at=doc.get("updated_at"),
        ))

    return KnowledgebaseListResponse(
        company_id=company_id,
        total=len(doc_metadata),
        documents=doc_metadata,
    )


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_knowledgebase_document(
    company_id: str,
    doc_id: str,
    request: Request = None,
):
    """
    Get a single knowledgebase document with full extracted text.

    Args:
        company_id: Company ID.
        doc_id: Document UUID.

    Returns:
        Document with extracted text.
    """
    pool = request.app.state.pool
    await _validate_company(pool, company_id)

    service = KnowledgebaseService(pool)
    doc = await service.get_knowledgebase_document(company_id, doc_id)

    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Knowledgebase document '{doc_id}' not found"
        )

    return DocumentDetail(
        id=doc["id"],
        company_id=doc["company_id"],
        executive_id=None,  # Knowledgebase docs have no executive_id
        filename=doc["filename"],
        content_type=doc.get("content_type"),
        file_size=doc.get("file_size", 0),
        extracted_text=doc["extracted_text"],
        text_length=doc.get("text_length", 0),
        doc_type="knowledgebase",
        is_active=doc.get("is_active", True),
        uploaded_at=doc.get("uploaded_at"),
        updated_at=doc.get("updated_at"),
    )


@router.delete("/{doc_id}")
async def delete_knowledgebase_document(
    company_id: str,
    doc_id: str,
    request: Request = None,
):
    """
    Soft delete a knowledgebase document and its embeddings.

    The document is marked as inactive but retained for history.
    Associated embeddings are deleted in the same transaction.

    Args:
        company_id: Company ID.
        doc_id: Document UUID.

    Returns:
        Success message with embeddings_deleted count.
    """
    pool = request.app.state.pool
    await _validate_company(pool, company_id)

    service = KnowledgebaseService(pool)
    result = await service.delete_knowledgebase_document(company_id, doc_id)

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Knowledgebase document '{doc_id}' not found"
        )

    return {
        "success": True,
        "message": f"Knowledgebase document '{doc_id}' deleted",
        "embeddings_deleted": result.get("embeddings_deleted", 0),
    }
