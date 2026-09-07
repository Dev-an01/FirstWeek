"""
Executive Documents CRUD operations.

Handles persistent storage of executive documents (extracted text, not raw binary).
Supports soft delete for document history preservation.
"""

import logging
import uuid
from typing import Optional, List, Dict, Any
import asyncpg

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert asyncpg Record to dict, casting UUID fields to str."""
    d = dict(row)
    if "id" in d and isinstance(d["id"], uuid.UUID):
        d["id"] = str(d["id"])
    return d


async def create_document(
    pool: asyncpg.Pool,
    company_id: str,
    executive_id: Optional[str],
    filename: str,
    content_type: Optional[str],
    file_size: int,
    extracted_text: str,
    parsing_method: Optional[str] = None,
    ocr_applied: bool = False,
    doc_type: str = "profile",
    access_level: str = "internal",
) -> Dict[str, Any]:
    """
    Create a new document record.

    Args:
        pool: Database connection pool.
        company_id: Company ID for tenant isolation.
        executive_id: Executive ID this document belongs to. NULL for knowledgebase docs.
        filename: Original filename.
        content_type: MIME type of the uploaded file.
        file_size: Size in bytes of the original file.
        extracted_text: Parsed text content from the document.
        parsing_method: Method used for parsing (pdfplumber, mineru, olmocr2, docx, text, image).
        ocr_applied: Whether OCR was used for text extraction.
        doc_type: Document type - 'profile' (executive-specific) or 'knowledgebase' (company-wide).
        access_level: Access scope - 'public', 'internal', 'executive', or 'confidential'.

    Returns:
        Created document record.
    """
    doc_id = str(uuid.uuid4())
    row = await pool.fetchrow(
        """
        INSERT INTO executive_documents
            (id, company_id, executive_id, filename, content_type, file_size,
             extracted_text, parsing_method, ocr_applied, doc_type, access_level)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING
            id, company_id, executive_id, filename, content_type,
            file_size, LENGTH(extracted_text) as text_length, is_active,
            parsing_method, ocr_applied, doc_type, access_level, uploaded_at, updated_at
        """,
        doc_id,
        company_id,
        executive_id,
        filename,
        content_type,
        file_size,
        extracted_text,
        parsing_method or "pdfplumber",
        ocr_applied,
        doc_type,
        access_level,
    )
    target = executive_id if executive_id else f"company {company_id} knowledgebase"
    logger.info(
        f"Created {doc_type} document {doc_id} for {target} "
        f"(method: {parsing_method}, ocr: {ocr_applied})"
    )
    return _row_to_dict(row) if row else {}


async def create_documents_batch(
    pool: asyncpg.Pool,
    company_id: str,
    executive_id: str,
    documents: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Create multiple document records in a batch.

    Args:
        pool: Database connection pool.
        company_id: Company ID for tenant isolation.
        executive_id: Executive ID these documents belong to.
        documents: List of document dicts with filename, content_type, file_size, extracted_text.

    Returns:
        List of created document records.
    """
    results = []
    for doc in documents:
        result = await create_document(
            pool,
            company_id,
            executive_id,
            doc["filename"],
            doc.get("content_type"),
            doc.get("file_size", 0),
            doc["extracted_text"],
        )
        results.append(result)
    return results


async def get_document(
    pool: asyncpg.Pool,
    doc_id: str,
    company_id: Optional[str] = None,
    executive_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get a single document by ID with optional tenant filtering.

    Args:
        pool: Database connection pool.
        doc_id: Document UUID.
        company_id: Optional company filter for tenant isolation.
        executive_id: Optional executive filter.

    Returns:
        Document record with full extracted_text, or None if not found.
    """
    query = """
        SELECT
            id, company_id, executive_id, filename, content_type,
            file_size, extracted_text, LENGTH(extracted_text) as text_length,
            is_active, parsing_method, ocr_applied, doc_type, access_level,
            uploaded_at, updated_at
        FROM executive_documents
        WHERE id = $1
    """
    params = [doc_id]

    if company_id:
        query += " AND company_id = $2"
        params.append(company_id)
        if executive_id:
            query += " AND executive_id = $3"
            params.append(executive_id)
    elif executive_id:
        query += " AND executive_id = $2"
        params.append(executive_id)

    row = await pool.fetchrow(query, *params)
    return _row_to_dict(row) if row else None


async def list_documents(
    pool: asyncpg.Pool,
    company_id: str,
    executive_id: str,
    include_inactive: bool = False,
    doc_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List all documents for an executive.

    Args:
        pool: Database connection pool.
        company_id: Company ID for tenant isolation.
        executive_id: Executive ID to list documents for.
        include_inactive: If True, include soft-deleted documents.
        doc_type: Optional filter by document type ('profile' or 'knowledgebase').

    Returns:
        List of document records (without full extracted_text for efficiency).
    """
    query = """
        SELECT
            id, company_id, executive_id, filename, content_type,
            file_size, LENGTH(extracted_text) as text_length,
            is_active, parsing_method, ocr_applied, doc_type, access_level,
            uploaded_at, updated_at
        FROM executive_documents
        WHERE company_id = $1 AND executive_id = $2
    """
    params = [company_id, executive_id]

    if not include_inactive:
        query += " AND is_active = true"

    if doc_type:
        query += f" AND doc_type = ${len(params) + 1}"
        params.append(doc_type)

    query += " ORDER BY uploaded_at DESC"

    rows = await pool.fetch(query, *params)
    return [_row_to_dict(r) for r in rows]


async def get_active_documents_text(
    pool: asyncpg.Pool,
    company_id: str,
    executive_id: str,
) -> List[Dict[str, Any]]:
    """
    Get all active documents with their extracted text for processing.
    Used for calibration and re-extraction. Includes both profile and knowledgebase docs.

    Args:
        pool: Database connection pool.
        company_id: Company ID for tenant isolation.
        executive_id: Executive ID.

    Returns:
        List of document records with extracted_text included.
    """
    rows = await pool.fetch(
        """
        SELECT
            id, filename, content_type, file_size, extracted_text,
            LENGTH(extracted_text) as text_length, doc_type, uploaded_at
        FROM executive_documents
        WHERE company_id = $1 AND executive_id = $2 AND is_active = true
        ORDER BY uploaded_at ASC
        """,
        company_id,
        executive_id,
    )
    return [_row_to_dict(r) for r in rows]


async def get_active_profile_documents_text(
    pool: asyncpg.Pool,
    company_id: str,
    executive_id: str,
) -> List[Dict[str, Any]]:
    """
    Get only active PROFILE documents with their extracted text.
    Used for LLM extraction pipeline (excludes knowledgebase docs).

    Args:
        pool: Database connection pool.
        company_id: Company ID for tenant isolation.
        executive_id: Executive ID.

    Returns:
        List of profile document records with extracted_text included.
    """
    rows = await pool.fetch(
        """
        SELECT
            id, filename, content_type, file_size, extracted_text,
            LENGTH(extracted_text) as text_length, doc_type, uploaded_at
        FROM executive_documents
        WHERE company_id = $1
          AND executive_id = $2
          AND is_active = true
          AND doc_type = 'profile'
        ORDER BY uploaded_at ASC
        """,
        company_id,
        executive_id,
    )
    return [_row_to_dict(r) for r in rows]


async def get_extractable_profile_documents_text(
    pool: asyncpg.Pool,
    company_id: str,
    executive_id: str,
) -> List[Dict[str, Any]]:
    """
    Get profile documents safe for LLM extraction (public + internal only).
    Executive/confidential docs are excluded to prevent data leaks via profile_data.
    """
    rows = await pool.fetch(
        """
        SELECT
            id, filename, content_type, file_size, extracted_text,
            LENGTH(extracted_text) as text_length, doc_type, access_level, uploaded_at
        FROM executive_documents
        WHERE company_id = $1
          AND executive_id = $2
          AND is_active = true
          AND doc_type = 'profile'
          AND access_level IN ('public', 'internal')
        ORDER BY uploaded_at ASC
        """,
        company_id,
        executive_id,
    )
    return [_row_to_dict(r) for r in rows]


async def list_company_knowledgebase(
    pool: asyncpg.Pool,
    company_id: str,
    include_inactive: bool = False,
) -> List[Dict[str, Any]]:
    """
    List all knowledgebase documents for a company.

    Args:
        pool: Database connection pool.
        company_id: Company ID.
        include_inactive: If True, include soft-deleted documents.

    Returns:
        List of knowledgebase document records.
    """
    query = """
        SELECT
            id, company_id, filename, content_type,
            file_size, LENGTH(extracted_text) as text_length,
            is_active, parsing_method, ocr_applied, doc_type, uploaded_at, updated_at
        FROM executive_documents
        WHERE company_id = $1
          AND executive_id IS NULL
          AND doc_type = 'knowledgebase'
    """

    if not include_inactive:
        query += " AND is_active = true"

    query += " ORDER BY uploaded_at DESC"

    rows = await pool.fetch(query, company_id)
    return [_row_to_dict(r) for r in rows]


async def get_knowledgebase_document(
    pool: asyncpg.Pool,
    doc_id: str,
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get a single knowledgebase document by ID.

    Args:
        pool: Database connection pool.
        doc_id: Document UUID.
        company_id: Company ID for tenant isolation.

    Returns:
        Document record with full extracted_text, or None if not found.
    """
    row = await pool.fetchrow(
        """
        SELECT
            id, company_id, filename, content_type,
            file_size, extracted_text, LENGTH(extracted_text) as text_length,
            is_active, parsing_method, ocr_applied, doc_type, uploaded_at, updated_at
        FROM executive_documents
        WHERE id = $1
          AND company_id = $2
          AND executive_id IS NULL
          AND doc_type = 'knowledgebase'
        """,
        doc_id,
        company_id,
    )
    return _row_to_dict(row) if row else None


async def soft_delete_knowledgebase_document(
    pool: asyncpg.Pool,
    doc_id: str,
    company_id: str,
) -> bool:
    """
    Soft delete a knowledgebase document.

    Args:
        pool: Database connection pool.
        doc_id: Document UUID.
        company_id: Company ID for tenant isolation.

    Returns:
        True if document was found and deleted, False otherwise.
    """
    result = await pool.execute(
        """
        UPDATE executive_documents
        SET is_active = false, updated_at = NOW()
        WHERE id = $1
          AND company_id = $2
          AND executive_id IS NULL
          AND doc_type = 'knowledgebase'
        """,
        doc_id,
        company_id,
    )
    deleted = result == "UPDATE 1"
    if deleted:
        logger.info(f"Soft-deleted knowledgebase document {doc_id}")
    return deleted


async def soft_delete_document(
    pool: asyncpg.Pool,
    doc_id: str,
    company_id: str,
    executive_id: str,
) -> bool:
    """
    Soft delete a document (set is_active = false).

    Args:
        pool: Database connection pool.
        doc_id: Document UUID.
        company_id: Company ID for tenant isolation.
        executive_id: Executive ID for validation.

    Returns:
        True if document was found and deleted, False otherwise.
    """
    result = await pool.execute(
        """
        UPDATE executive_documents
        SET is_active = false, updated_at = NOW()
        WHERE id = $1 AND company_id = $2 AND executive_id = $3
        """,
        doc_id,
        company_id,
        executive_id,
    )
    deleted = result == "UPDATE 1"
    if deleted:
        logger.info(f"Soft-deleted document {doc_id}")
    return deleted


async def restore_document(
    pool: asyncpg.Pool,
    doc_id: str,
    company_id: str,
    executive_id: str,
) -> bool:
    """
    Restore a soft-deleted document (set is_active = true).

    Args:
        pool: Database connection pool.
        doc_id: Document UUID.
        company_id: Company ID for tenant isolation.
        executive_id: Executive ID for validation.

    Returns:
        True if document was found and restored, False otherwise.
    """
    result = await pool.execute(
        """
        UPDATE executive_documents
        SET is_active = true, updated_at = NOW()
        WHERE id = $1 AND company_id = $2 AND executive_id = $3
        """,
        doc_id,
        company_id,
        executive_id,
    )
    restored = result == "UPDATE 1"
    if restored:
        logger.info(f"Restored document {doc_id}")
    return restored


async def hard_delete_document(
    pool: asyncpg.Pool,
    doc_id: str,
    company_id: str,
    executive_id: str,
) -> bool:
    """
    Permanently delete a document (use with caution).

    Args:
        pool: Database connection pool.
        doc_id: Document UUID.
        company_id: Company ID for tenant isolation.
        executive_id: Executive ID for validation.

    Returns:
        True if document was found and deleted, False otherwise.
    """
    result = await pool.execute(
        """
        DELETE FROM executive_documents
        WHERE id = $1 AND company_id = $2 AND executive_id = $3
        """,
        doc_id,
        company_id,
        executive_id,
    )
    deleted = result == "DELETE 1"
    if deleted:
        logger.info(f"Hard-deleted document {doc_id}")
    return deleted


async def count_documents(
    pool: asyncpg.Pool,
    company_id: str,
    executive_id: str,
    active_only: bool = True,
) -> int:
    """
    Count documents for an executive.

    Args:
        pool: Database connection pool.
        company_id: Company ID for tenant isolation.
        executive_id: Executive ID.
        active_only: If True, only count active documents.

    Returns:
        Document count.
    """
    query = """
        SELECT COUNT(*) FROM executive_documents
        WHERE company_id = $1 AND executive_id = $2
    """
    if active_only:
        query += " AND is_active = true"

    count = await pool.fetchval(query, company_id, executive_id)
    return count or 0
