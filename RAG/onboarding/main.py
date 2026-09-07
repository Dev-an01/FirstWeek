"""
Onboarding Service - FastAPI application (port 8002).

Handles company registration, executive onboarding, document processing,
and LLM-powered profile + voiceprint generation.
"""

import sys
import os
import io
import asyncio
import logging
import json
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Fix Windows UTF-8 encoding
if sys.platform == "win32":
    os.environ["PYTHONUTF8"] = "1"
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Fix Windows asyncio event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from onboarding.config import SERVICE_NAME, SERVICE_VERSION, SERVICE_PORT, MAX_FILE_SIZE_BYTES
from onboarding.models import (
    CompanyCreate, CompanyResponse, CompanyDetailResponse, CompanyUpdate,
    ExecutiveCreate, ExecutiveResponse, ExecutiveDetailResponse, ExecutiveUpdate,
    ExecutiveListResponse, ExecutiveHierarchyItem,
    OnboardingStartRequest, JobStatusResponse, JobResultResponse,
    UploadResponse, UploadedDocument,
    HealthResponse, JobType,
)
from onboarding.db.connection import get_pool, close_pool
from onboarding.db import companies, executives, jobs, documents
from onboarding.parsers.dispatcher import parse_document
from onboarding.routes import documents_router, profiles_router, calibration_router, knowledgebase_router, voice_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# In-memory store for uploaded document texts per executive (cleared after pipeline run)
_uploaded_docs: Dict[str, List[Dict[str, Any]]] = {}


# ============================================================================
# Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info(f"STARTING {SERVICE_NAME} v{SERVICE_VERSION}")
    logger.info("=" * 60)

    pool = await get_pool()
    app.state.pool = pool
    logger.info("Database pool ready")

    yield

    logger.info("Shutting down onboarding service...")
    await close_pool()
    logger.info("Shutdown complete")


# ============================================================================
# App
# ============================================================================

app = FastAPI(
    title=SERVICE_NAME,
    version=SERVICE_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").strip()
if CORS_ORIGINS:
    _cors_origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
else:
    _cors_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:3003",
        "http://localhost:3004",
        "http://firstweek-frontend:5173",
        "http://frontend:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers from routes/ directory
app.include_router(documents_router)
app.include_router(profiles_router)
app.include_router(calibration_router)
app.include_router(knowledgebase_router)
app.include_router(voice_router)


# ============================================================================
# Health
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(request: Request):
    pool = request.app.state.pool
    db_status = "ok"
    try:
        await pool.fetchval("SELECT 1")
    except Exception:
        db_status = "error"
    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        service="onboarding",
        version=SERVICE_VERSION,
        database=db_status,
    )


# ============================================================================
# Companies
# ============================================================================

@app.post("/api/v1/companies", response_model=CompanyResponse, status_code=201, tags=["Companies"])
async def create_company_endpoint(body: CompanyCreate, request: Request):
    pool = request.app.state.pool
    try:
        result = await companies.create_company(pool, body.model_dump())
        return CompanyResponse(**result)
    except Exception as e:
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Company '{body.id}' already exists")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/companies", response_model=List[CompanyResponse], tags=["Companies"])
async def list_companies_endpoint(request: Request):
    pool = request.app.state.pool
    rows = await companies.list_companies(pool)
    return [CompanyResponse(**r) for r in rows]


@app.get("/api/v1/companies/{company_id}", response_model=CompanyDetailResponse, tags=["Companies"])
async def get_company_endpoint(company_id: str, request: Request):
    """Get company with all executives including hierarchy information."""
    pool = request.app.state.pool
    row = await companies.get_company_with_executives(pool, company_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")

    # Convert executives to hierarchy items
    exec_items = []
    for e in row.get("executives", []):
        exec_items.append(ExecutiveHierarchyItem(
            id=e["id"],
            name=e["name"],
            name_english=e.get("name_english"),
            title=e.get("title"),
            email=e.get("email"),
            hierarchy_level=e.get("hierarchy_level", 0),
            has_profile=e.get("has_profile", False),
            has_voiceprint=e.get("has_voiceprint", False),
            has_voice_keys=e.get("has_voice_keys", False),
            reports_to=e.get("reports_to"),
            direct_reports=e.get("direct_reports", []),
        ))

    return CompanyDetailResponse(
        id=row["id"],
        name=row["name"],
        industry=row.get("industry"),
        description=row.get("description"),
        metadata=row.get("metadata", {}),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        executives_count=row.get("executives_count", 0),
        executives=exec_items,
    )


@app.patch("/api/v1/companies/{company_id}", response_model=CompanyResponse, tags=["Companies"])
async def update_company_endpoint(company_id: str, body: CompanyUpdate, request: Request):
    """Update company info."""
    pool = request.app.state.pool

    # Check company exists
    existing = await companies.get_company(pool, company_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")

    result = await companies.update_company(pool, company_id, body.model_dump(exclude_unset=True))
    return CompanyResponse(**result)


@app.get("/api/v1/companies/{company_id}/executives", response_model=ExecutiveListResponse, tags=["Companies"])
async def list_company_executives_endpoint(
    company_id: str,
    hierarchy: bool = False,
    sort: str = "name",
    email: Optional[str] = None,
    request: Request = None,
):
    """
    List executives for a company with optional hierarchy grouping.

    Query params:
    - hierarchy: If true, group executives by hierarchy level
    - sort: Sort order - "hierarchy", "name", or "created"
    - email: Filter by email address
    """
    pool = request.app.state.pool

    # Check company exists
    company = await companies.get_company(pool, company_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")

    result = await companies.list_company_executives(
        pool, company_id, hierarchy=hierarchy, sort=sort, email=email
    )

    # Convert executives to hierarchy items
    exec_items = []
    for e in result.get("executives", []):
        exec_items.append(ExecutiveHierarchyItem(
            id=e["id"],
            name=e["name"],
            name_english=e.get("name_english"),
            title=e.get("title"),
            email=e.get("email"),
            hierarchy_level=e.get("hierarchy_level", 0),
            has_profile=e.get("has_profile", False),
            has_voiceprint=e.get("has_voiceprint", False),
            has_voice_keys=e.get("has_voice_keys", False),
            reports_to=e.get("reports_to"),
            direct_reports=e.get("direct_reports", []),
        ))

    # Convert by_level if present
    by_level = None
    if result.get("by_level"):
        by_level = {}
        for level, execs in result["by_level"].items():
            by_level[level] = [
                ExecutiveHierarchyItem(
                    id=e["id"],
                    name=e["name"],
                    name_english=e.get("name_english"),
                    title=e.get("title"),
                    email=e.get("email"),
                    hierarchy_level=e.get("hierarchy_level", 0),
                    has_profile=e.get("has_profile", False),
                    has_voiceprint=e.get("has_voiceprint", False),
                    reports_to=e.get("reports_to"),
                    direct_reports=e.get("direct_reports", []),
                )
                for e in execs
            ]

    return ExecutiveListResponse(
        company_id=company_id,
        total=result["total"],
        by_level=by_level,
        executives=exec_items,
    )


# ============================================================================
# Executives (legacy routes for backward compatibility)
# ============================================================================

@app.post("/api/v1/executives", response_model=ExecutiveResponse, status_code=201, tags=["Executives"])
async def create_executive_legacy(body: ExecutiveCreate, request: Request):
    """Create executive (legacy route - prefer company-scoped route)."""
    pool = request.app.state.pool
    # Verify company exists
    company = await companies.get_company(pool, body.company_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{body.company_id}' not found")
    try:
        result = await executives.create_executive(pool, body.model_dump())
        return ExecutiveResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/executives/{executive_id}", response_model=ExecutiveResponse, tags=["Executives"])
async def get_executive_legacy(executive_id: str, request: Request):
    """Get executive (legacy route - prefer company-scoped route)."""
    pool = request.app.state.pool
    row = await executives.get_executive(pool, executive_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found")
    return ExecutiveResponse(**row)


# ============================================================================
# Executives (company-scoped routes)
# ============================================================================

@app.post("/api/v1/companies/{company_id}/executives", response_model=ExecutiveResponse, status_code=201, tags=["Executives"])
async def create_executive_endpoint(company_id: str, body: ExecutiveCreate, request: Request):
    """Create executive within a company."""
    pool = request.app.state.pool

    # Verify company exists
    company = await companies.get_company(pool, company_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")

    # Ensure company_id matches
    if body.company_id != company_id:
        raise HTTPException(
            status_code=400,
            detail=f"company_id in body '{body.company_id}' does not match URL '{company_id}'"
        )

    try:
        result = await executives.create_executive(pool, body.model_dump())
        return ExecutiveResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/companies/{company_id}/executives/{executive_id}", response_model=ExecutiveDetailResponse, tags=["Executives"])
async def get_executive_endpoint(
    company_id: str,
    executive_id: str,
    include: str = "",
    request: Request = None,
):
    """
    Get executive with optional profile, voiceprint, and documents.

    Query params:
    - include: Comma-separated list of what to include: "profile", "voiceprint", "documents"
    """
    pool = request.app.state.pool

    # Parse include params
    include_parts = [p.strip().lower() for p in include.split(",") if p.strip()]
    include_profile = "profile" in include_parts
    include_voiceprint = "voiceprint" in include_parts
    include_docs = "documents" in include_parts

    # Get executive with optional data
    row = await executives.get_executive_with_data(
        pool, executive_id, company_id,
        include_profile=include_profile,
        include_voiceprint=include_voiceprint,
    )

    if not row:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found in company '{company_id}'")

    # Get direct reports
    direct_reports = await executives.get_direct_reports(pool, executive_id, company_id)

    # Get documents if requested
    docs_list = None
    if include_docs:
        from onboarding.services.document_service import DocumentService
        doc_service = DocumentService(pool)
        docs = await doc_service.list_documents(company_id, executive_id)
        docs_list = docs

    return ExecutiveDetailResponse(
        id=row["id"],
        name=row["name"],
        name_english=row.get("name_english"),
        title=row.get("title"),
        department=row.get("department"),
        company_id=row.get("company_id"),
        email=row.get("email"),
        has_profile=row.get("has_profile", False),
        has_voiceprint=row.get("has_voiceprint", False),
        has_voice_keys=row.get("has_voice_keys", False),
        embeddings_count=row.get("embeddings_count", 0),
        reports_to=row.get("reports_to"),
        hierarchy_level=row.get("hierarchy_level", 0),
        sort_order=row.get("sort_order", 0),
        profile=row.get("profile_data") if include_profile else None,
        voiceprint=row.get("voiceprint_data") if include_voiceprint else None,
        documents=docs_list,
        direct_reports=direct_reports,
    )


@app.patch("/api/v1/companies/{company_id}/executives/{executive_id}", response_model=ExecutiveResponse, tags=["Executives"])
async def update_executive_endpoint(
    company_id: str,
    executive_id: str,
    body: ExecutiveUpdate,
    request: Request = None,
):
    """Update executive basic info."""
    pool = request.app.state.pool

    # Verify executive exists in company
    exec_row = await executives.get_executive(pool, executive_id)
    if not exec_row:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found")
    if exec_row.get("company_id") != company_id:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found in company '{company_id}'")

    result = await executives.update_executive(pool, executive_id, company_id, body.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=500, detail="Failed to update executive")

    return ExecutiveResponse(**result)


@app.delete("/api/v1/companies/{company_id}/executives/{executive_id}", tags=["Executives"])
async def delete_executive_endpoint(
    company_id: str,
    executive_id: str,
    purge: bool = False,
    request: Request = None,
):
    """
    Delete an executive.

    Query params:
    - purge: If true, fully purge all data including embeddings and decision cases.
             If false (default), soft-delete only (clears profile/voiceprint).
    """
    pool = request.app.state.pool

    # Verify executive exists in company
    exec_row = await executives.get_executive(pool, executive_id)
    if not exec_row:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found")
    if exec_row.get("company_id") != company_id:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found in company '{company_id}'")

    if purge:
        purge_result = await _purge_executive(pool, executive_id, company_id)
        # Also soft-delete the executive record itself
        await executives.soft_delete_executive(pool, executive_id, company_id)
        return {
            "success": True,
            "message": f"Executive '{executive_id}' purged",
            **purge_result,
        }

    deleted = await executives.soft_delete_executive(pool, executive_id, company_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete executive")

    return {"success": True, "message": f"Executive '{executive_id}' deleted"}


# ============================================================================
# Document Upload (legacy route for backward compatibility)
# ============================================================================

@app.post("/api/v1/onboarding/{executive_id}/upload", response_model=UploadResponse, tags=["Onboarding"])
async def upload_documents_legacy(
    executive_id: str,
    files: List[UploadFile] = File(...),
    request: Request = None,
):
    """Upload documents for an executive (legacy route). Max 50MB per file."""
    pool = request.app.state.pool

    # Verify executive exists
    exec_row = await executives.get_executive(pool, executive_id)
    if not exec_row:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found")

    uploaded = []
    total_text_length = 0

    for file in files:
        # Read file bytes
        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File '{file.filename}' exceeds {MAX_FILE_SIZE_BYTES // (1024*1024)}MB limit",
            )

        # Parse to text
        try:
            text = parse_document(file.filename, file_bytes)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        doc_entry = {
            "filename": file.filename,
            "size": len(file_bytes),
            "content_type": file.content_type,
            "text": text,
            "text_length": len(text),
        }

        # Store in memory
        if executive_id not in _uploaded_docs:
            _uploaded_docs[executive_id] = []
        _uploaded_docs[executive_id].append(doc_entry)

        uploaded.append(UploadedDocument(
            filename=file.filename,
            size=len(file_bytes),
            content_type=file.content_type,
            text_length=len(text),
        ))
        total_text_length += len(text)

    logger.info(f"Uploaded {len(uploaded)} documents for {executive_id}, total text: {total_text_length} chars")

    return UploadResponse(
        executive_id=executive_id,
        documents=uploaded,
        total_text_length=total_text_length,
    )


# ============================================================================
# Company-Scoped Onboarding Routes
# ============================================================================

@app.post("/api/v1/companies/{company_id}/executives/{executive_id}/onboard", response_model=JobStatusResponse, tags=["Onboarding"])
async def start_onboarding_scoped(
    company_id: str,
    executive_id: str,
    body: OnboardingStartRequest = OnboardingStartRequest(),
    request: Request = None,
):
    """
    Start the onboarding pipeline for an executive (company-scoped).

    This is the preferred route. Uses persistent document storage.
    """
    pool = request.app.state.pool

    # Verify executive exists in company
    exec_row = await executives.get_executive(pool, executive_id)
    if not exec_row:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found")
    if exec_row.get("company_id") != company_id:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found in company '{company_id}'")

    # Check for documents - first check persistent storage, then in-memory
    from onboarding.services.document_service import DocumentService
    doc_service = DocumentService(pool)
    doc_count = await doc_service.get_document_count(company_id, executive_id)

    # Also check in-memory docs (for backward compatibility)
    in_memory_docs = _uploaded_docs.get(executive_id, [])

    if doc_count == 0 and not in_memory_docs:
        raise HTTPException(
            status_code=400,
            detail=f"No documents found for '{executive_id}'. Upload documents first.",
        )

    # Create job
    job = await jobs.create_job(pool, company_id, executive_id, body.job_type.value)
    job_id = str(job["id"])

    # Determine document source and prepare docs
    if in_memory_docs:
        # Use in-memory docs (legacy flow) and also store them persistently
        docs = in_memory_docs
        doc_meta = [{"filename": d["filename"], "size": d["size"], "text_length": d["text_length"]} for d in docs]
        await jobs.store_input_documents(pool, job_id, doc_meta)

        # Also store in persistent storage for future calibration
        for d in docs:
            await documents.create_document(
                pool, company_id, executive_id,
                d["filename"], d.get("content_type"), d.get("size", 0), d["text"]
            )
    else:
        # Use persistent storage - only PROFILE docs for LLM extraction
        # Knowledgebase docs go directly to embeddings, not through extraction
        docs_with_text = await documents.get_active_profile_documents_text(pool, company_id, executive_id)
        docs = [{"filename": d["filename"], "text": d["extracted_text"], "text_length": d["text_length"]} for d in docs_with_text]
        doc_meta = [{"filename": d["filename"], "text_length": d["text_length"]} for d in docs_with_text]
        await jobs.store_input_documents(pool, job_id, doc_meta)

    # Launch background pipeline
    asyncio.create_task(_run_pipeline(pool, job_id, executive_id, company_id, exec_row, docs))

    return JobStatusResponse(**job)


# ============================================================================
# Pipeline Start (legacy route for backward compatibility)
# ============================================================================

@app.post("/api/v1/onboarding/{executive_id}/start", response_model=JobStatusResponse, tags=["Onboarding"])
async def start_onboarding_legacy(
    executive_id: str,
    body: OnboardingStartRequest = OnboardingStartRequest(),
    request: Request = None,
):
    """Start the onboarding pipeline for an executive (legacy route)."""
    pool = request.app.state.pool

    # Verify executive exists
    exec_row = await executives.get_executive(pool, executive_id)
    if not exec_row:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found")

    # Check documents uploaded
    docs = _uploaded_docs.get(executive_id, [])
    if not docs:
        raise HTTPException(
            status_code=400,
            detail=f"No documents uploaded for '{executive_id}'. Upload documents first.",
        )

    company_id = exec_row.get("company_id", "")

    # Create job
    job = await jobs.create_job(pool, company_id, executive_id, body.job_type.value)
    job_id = str(job["id"])

    # Store document metadata on the job
    doc_meta = [{"filename": d["filename"], "size": d["size"], "text_length": d["text_length"]} for d in docs]
    await jobs.store_input_documents(pool, job_id, doc_meta)

    # Launch background pipeline
    asyncio.create_task(_run_pipeline(pool, job_id, executive_id, company_id, exec_row, docs))

    return JobStatusResponse(**job)


# ============================================================================
# Job Status
# ============================================================================

@app.get("/api/v1/onboarding/jobs/{job_id}", response_model=JobStatusResponse, tags=["Onboarding"])
async def get_job_status(job_id: str, request: Request):
    pool = request.app.state.pool
    job = await jobs.get_job(pool, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return JobStatusResponse(**job)


@app.get("/api/v1/onboarding/jobs/{job_id}/result", response_model=JobResultResponse, tags=["Onboarding"])
async def get_job_result(job_id: str, request: Request):
    pool = request.app.state.pool
    result = await jobs.get_job_result(pool, job_id)
    if not result:
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


# ============================================================================
# Background Pipeline
# ============================================================================

async def _run_pipeline(
    pool,
    job_id: str,
    executive_id: str,
    company_id: str,
    exec_info: Dict[str, Any],
    docs: List[Dict[str, Any]],
):
    """
    Full onboarding pipeline (runs in background):

    NOTE: This pipeline processes only PROFILE documents (interviews, bios, etc).
    KNOWLEDGEBASE documents (policies, procedures) bypass this pipeline and go
    directly to embeddings via the KnowledgebaseService.

    Steps:
    1. Parse documents -> raw text (already done at upload)
    2. 7 concurrent LLM extractions
    3. Assemble profile + voiceprint
    4. Synthesis LLM pass
    5. Validate
    6. Deploy to PostgreSQL
    7. Trigger embeddings
    """
    try:
        # ---- Step 1: Combine document text ----
        await jobs.update_job_status(pool, job_id, "parsing", 5.0)
        combined_text = "\n\n---\n\n".join(d["text"] for d in docs)
        logger.info(f"[{job_id}] Combined text: {len(combined_text)} chars from {len(docs)} documents")

        # ---- Step 2: Run 7 extractions concurrently ----
        await jobs.update_job_status(pool, job_id, "extracting", 10.0)

        loop = asyncio.get_event_loop()
        from onboarding.extractors.runner import run_all_extractions
        extractions = await loop.run_in_executor(None, run_all_extractions, combined_text, None)

        await jobs.update_job_extraction(pool, job_id, extractions)
        await jobs.update_job_status(pool, job_id, "assembling", 50.0)

        # ---- Step 3: Assemble profile + voiceprint ----
        from onboarding.assembler.profile_assembler import assemble_profile
        from onboarding.assembler.voiceprint_assembler import assemble_voiceprint

        profile = assemble_profile(executive_id, exec_info, extractions)
        voiceprint = assemble_voiceprint(executive_id, extractions)

        # ---- Step 4: Synthesis LLM pass ----
        from onboarding.assembler.synthesis_llm import run_synthesis, apply_synthesis
        synthesis_result = await loop.run_in_executor(None, run_synthesis, profile, voiceprint)
        profile, voiceprint = apply_synthesis(profile, voiceprint, synthesis_result)

        await jobs.update_job_assembled(pool, job_id, profile, voiceprint)
        await jobs.update_job_status(pool, job_id, "validating", 70.0)

        # ---- Step 5: Validate ----
        from onboarding.validator.profile_validator import validate_profile
        from onboarding.validator.schema_checker import check_profile_schema, check_voiceprint_schema

        validation_result = validate_profile(profile)
        schema_result = check_profile_schema(profile)
        vp_schema_result = check_voiceprint_schema(voiceprint)

        full_validation = {
            "profile_validation": validation_result,
            "profile_schema": schema_result,
            "voiceprint_schema": vp_schema_result,
        }
        await jobs.update_job_validation(pool, job_id, full_validation)

        # ---- Step 6: Deploy to PostgreSQL ----
        await jobs.update_job_status(pool, job_id, "deploying", 80.0)

        from onboarding.deployer.db_deployer import deploy_to_database
        deploy_result = await deploy_to_database(pool, executive_id, company_id, profile, voiceprint)
        logger.info(f"[{job_id}] Deploy result: {deploy_result}")

        # ---- Step 6b: Deploy to Neo4j graph ----
        # Soft-failure: Neo4j issues should not block the pipeline
        try:
            await jobs.update_job_status(pool, job_id, "deploying_graph", 83.0)

            from onboarding.deployer.neo4j_deployer import Neo4jDeployer
            from onboarding.config import NEO4J_CONFIG

            neo4j_deployer = Neo4jDeployer(
                uri=NEO4J_CONFIG["uri"],
                user=NEO4J_CONFIG["user"],
                password=NEO4J_CONFIG["password"]
            )
            connected = await neo4j_deployer.connect()

            if connected:
                company_data = {
                    "id": company_id,
                    "name": exec_info.get("company_name", company_id),
                }
                executive_data = {
                    "id": executive_id,
                    "name": exec_info.get("name", ""),
                    "name_english": exec_info.get("name_english", ""),
                    "title": exec_info.get("title", "Executive"),
                    "department": exec_info.get("department", ""),
                    "email": exec_info.get("email", ""),
                    "hierarchy_level": exec_info.get("hierarchy_level", 4),
                }

                neo4j_result = await neo4j_deployer.deploy_onboarding_result(
                    company_data=company_data,
                    executive_data=executive_data,
                    profile_data=profile
                )
                logger.info(f"[{job_id}] Neo4j deploy result: {neo4j_result}")

                # Deploy additional node types (Person, Product, Department)
                people_count = await neo4j_deployer.deploy_people(executive_id, company_id, profile)
                products_count = await neo4j_deployer.deploy_products(executive_id, company_id, profile)
                depts_count = await neo4j_deployer.deploy_departments(executive_id, company_id, profile)
                logger.info(
                    f"[{job_id}] Neo4j additional nodes: "
                    f"{people_count} people, {products_count} products, {depts_count} departments"
                )

                await neo4j_deployer.close()
            else:
                logger.warning(f"[{job_id}] Neo4j not available, skipping graph deployment")
        except Exception as e:
            logger.warning(f"[{job_id}] Neo4j deployment failed (non-fatal): {e}")

        # ---- Step 7: Trigger embedding generation ----
        await jobs.update_job_status(pool, job_id, "embedding", 90.0)

        from onboarding.deployer.embedding_trigger import trigger_embeddings
        embed_result = await trigger_embeddings(executive_id, company_id, profile, voiceprint)
        logger.info(f"[{job_id}] Embedding trigger: {embed_result.get('status', 'unknown')}")

        # ---- Step 7b: Notify RAG service to refresh cached profile ----
        try:
            from onboarding.utils.rag_notifier import notify_rag_profile_refresh
            await notify_rag_profile_refresh(company_id, executive_id, reason="onboarding")
        except Exception as e:
            logger.warning(f"[{job_id}] RAG notification failed (non-fatal): {e}")

        # ---- Done ----
        await jobs.update_job_status(pool, job_id, "completed", 100.0)
        logger.info(f"[{job_id}] Pipeline completed for {executive_id}")

        # Clean up uploaded docs from memory
        _uploaded_docs.pop(executive_id, None)

    except Exception as e:
        logger.error(f"[{job_id}] Pipeline failed: {e}", exc_info=True)
        await jobs.update_job_status(pool, job_id, "failed", error_message=str(e))


# ============================================================================
# Executive Purge (full cleanup including embeddings)
# ============================================================================

async def _purge_executive(pool, executive_id: str, company_id: str) -> Dict[str, Any]:
    """
    Fully purge an executive's data including all embeddings.

    This goes beyond soft-delete: removes embeddings, decision cases,
    documents, and the executive record itself.

    Args:
        pool: Database connection pool.
        executive_id: Executive ID.
        company_id: Company ID.

    Returns:
        Purge summary with counts of deleted items.
    """
    result = {
        "executive_id": executive_id,
        "company_id": company_id,
        "embeddings_deleted": 0,
        "decision_cases_deleted": 0,
        "documents_deleted": 0,
    }

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Delete all embeddings for this executive
            embed_result = await conn.execute(
                """
                DELETE FROM embeddings
                WHERE executive_id = $1 AND company_id = $2
                """,
                executive_id,
                company_id,
            )
            result["embeddings_deleted"] = int(embed_result.split()[-1]) if embed_result else 0

            # Delete decision cases
            cases_result = await conn.execute(
                "DELETE FROM decision_cases WHERE executive_id = $1",
                executive_id,
            )
            result["decision_cases_deleted"] = int(cases_result.split()[-1]) if cases_result else 0

            # Soft-delete all documents
            docs_result = await conn.execute(
                """
                UPDATE documents
                SET is_active = false
                WHERE executive_id = $1 AND company_id = $2 AND is_active = true
                """,
                executive_id,
                company_id,
            )
            result["documents_deleted"] = int(docs_result.split()[-1]) if docs_result else 0

            # Clear profile and voiceprint data
            await conn.execute(
                """
                UPDATE executive_profiles
                SET profile_data = NULL,
                    voiceprint_data = NULL
                WHERE id = $1
                """,
                executive_id,
            )

    # Notify RAG service
    try:
        from onboarding.utils.rag_notifier import notify_rag_profile_refresh
        await notify_rag_profile_refresh(company_id, executive_id, reason="purge")
    except Exception as e:
        logger.warning(f"RAG notification failed during purge (non-fatal): {e}")

    logger.info(f"Purged executive {executive_id}: {result}")
    result["status"] = "purged"
    return result


# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "onboarding.main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=True,
        log_level="info",
    )
