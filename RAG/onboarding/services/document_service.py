"""
Document Service - Business logic for document management.

Handles document upload, storage, retrieval, and deletion.
Uses ThreadPoolExecutor to run parsing in background threads to avoid
blocking the FastAPI event loop during long-running OCR operations.
"""

import asyncio
import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
import httpx
import asyncpg

from onboarding.db import documents
from onboarding.parsers.dispatcher import parse_document
from onboarding.config import MAX_FILE_SIZE_BYTES, EMBEDDING_SERVICE_URL
from onboarding.services.knowledgebase_service import _chunk_text

logger = logging.getLogger(__name__)

# Thread pool for CPU-bound parsing (OCR can take 5+ minutes for large PDFs)
# max_workers=2 to avoid overloading the system with concurrent OCR operations
_parse_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="doc_parser")


def _parse_with_metadata(filename: str, content: bytes):
    """Wrapper to call parse_document with return_metadata=True in thread pool."""
    return parse_document(filename, content, return_metadata=True)


class DocumentService:
    """Service for managing executive documents."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def upload_documents(
        self,
        company_id: str,
        executive_id: str,
        files: List[Dict[str, Any]],
        doc_type: str = "profile",
        access_level: str = "internal",
    ) -> List[Dict[str, Any]]:
        """
        Upload and store documents for an executive.

        Parsing is done in a thread pool to avoid blocking the FastAPI event loop
        during long-running OCR operations (can take 5+ minutes for large PDFs).

        Args:
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.
            files: List of file dicts with 'filename', 'content', 'content_type'.
            doc_type: Document type - 'profile' (default) or 'knowledgebase'.

        Returns:
            List of created document metadata.

        Raises:
            ValueError: If file exceeds size limit or cannot be parsed.
        """
        results = []
        loop = asyncio.get_event_loop()

        for file_info in files:
            filename = file_info["filename"]
            content = file_info["content"]  # bytes
            content_type = file_info.get("content_type")

            # Check file size
            file_size = len(content)
            if file_size > MAX_FILE_SIZE_BYTES:
                raise ValueError(
                    f"File '{filename}' exceeds {MAX_FILE_SIZE_BYTES // (1024*1024)}MB limit"
                )

            # Parse in thread pool to avoid blocking event loop during OCR
            # Use return_metadata=True to get parsing method info
            logger.debug(f"Parsing '{filename}' in thread pool")
            parse_func = functools.partial(_parse_with_metadata, filename, content)
            parse_result = await loop.run_in_executor(_parse_executor, parse_func)
            extracted_text, metadata = parse_result

            # Store in database with parsing metadata
            doc = await documents.create_document(
                self.pool,
                company_id,
                executive_id,
                filename,
                content_type,
                file_size,
                extracted_text,
                parsing_method=metadata.get("parsing_method"),
                ocr_applied=metadata.get("ocr_applied", False),
                doc_type=doc_type,
                access_level=access_level,
            )

            # Chunk and embed the raw document text
            doc_id = doc["id"]
            chunks = _chunk_text(extracted_text)
            all_chunks = []
            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "source_id": f"{doc_id}_chunk_{i:04d}",
                    "source_type": "document",
                    "content": chunk,
                    "metadata": {
                        "company_id": company_id,
                        "executive_id": executive_id,
                        "document_id": doc_id,
                        "filename": filename,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "access_level": access_level,
                    },
                    "access_level": access_level,
                    "force_update": True,
                })

            if all_chunks:
                embed_status = await self._trigger_embeddings(
                    company_id, executive_id, all_chunks
                )
                doc["embedding_status"] = embed_status
                doc["chunk_count"] = len(chunks)

            results.append(doc)

        logger.info(
            f"Uploaded {len(results)} {doc_type} documents for {company_id}/{executive_id}"
        )
        return results

    async def _trigger_embeddings(
        self,
        company_id: str,
        executive_id: str,
        chunks: List[Dict[str, Any]],
    ) -> str:
        """
        Send document chunks to embedding service.

        Args:
            company_id: Company ID.
            executive_id: Executive ID.
            chunks: List of chunk dicts for embedding.

        Returns:
            Status string: 'completed', 'unavailable', 'failed'
        """
        if not chunks:
            return "skipped"

        embedding_batch_url = f"{EMBEDDING_SERVICE_URL}/embeddings/batch"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    embedding_batch_url,
                    json={
                        "documents": chunks,
                        "priority": "normal",
                        "batch_id": f"document_{company_id}_{executive_id}",
                    },
                    params={"async_processing": "false"},
                )
                response.raise_for_status()

                logger.info(
                    f"Document embedding complete for {company_id}/{executive_id}: "
                    f"{len(chunks)} chunks sent"
                )
                return "completed"

        except httpx.ConnectError:
            logger.warning(
                f"Embedding service not reachable at {EMBEDDING_SERVICE_URL}"
            )
            return "unavailable"

        except Exception as e:
            logger.error(f"Document embedding failed: {e}")
            return "failed"

    async def list_documents(
        self,
        company_id: str,
        executive_id: str,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List all documents for an executive.

        Args:
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.
            include_inactive: Include soft-deleted documents.

        Returns:
            List of document metadata (without extracted text).
        """
        return await documents.list_documents(
            self.pool, company_id, executive_id, include_inactive
        )

    async def get_document(
        self,
        doc_id: str,
        company_id: str,
        executive_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single document with full extracted text.

        Args:
            doc_id: Document UUID.
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.

        Returns:
            Document with extracted text, or None if not found.
        """
        return await documents.get_document(
            self.pool, doc_id, company_id, executive_id
        )

    async def delete_document(
        self,
        doc_id: str,
        company_id: str,
        executive_id: str,
    ) -> Dict[str, Any]:
        """
        Soft delete a document and clean up associated embeddings.

        Args:
            doc_id: Document UUID.
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.

        Returns:
            Dict with deletion details, or empty dict if document not found.
        """
        embeddings_deleted = 0

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Delete embeddings matching this document's chunks
                result = await conn.execute(
                    """
                    DELETE FROM embeddings
                    WHERE source_id LIKE $1 || '_chunk_%'
                      AND company_id = $2
                    """,
                    doc_id,
                    company_id,
                )
                embeddings_deleted += int(result.split()[-1]) if result else 0

                # Belt-and-suspenders: also delete by document_id in metadata
                result2 = await conn.execute(
                    """
                    DELETE FROM embeddings
                    WHERE source_type = 'document'
                      AND metadata->>'document_id' = $1
                      AND company_id = $2
                    """,
                    doc_id,
                    company_id,
                )
                embeddings_deleted += int(result2.split()[-1]) if result2 else 0

                # Soft-delete the document record (inline to use same transaction)
                soft_result = await conn.execute(
                    """
                    UPDATE executive_documents
                    SET is_active = false, updated_at = NOW()
                    WHERE id = $1 AND company_id = $2 AND executive_id = $3
                    """,
                    doc_id,
                    company_id,
                    executive_id,
                )
                deleted = soft_result == "UPDATE 1"

        if not deleted:
            return {}

        logger.info(
            f"Deleted document {doc_id}: {embeddings_deleted} embeddings removed"
        )
        return {
            "status": "deleted",
            "doc_id": doc_id,
            "embeddings_deleted": embeddings_deleted,
            "recalibration_needed": True,
        }

    async def restore_document(
        self,
        doc_id: str,
        company_id: str,
        executive_id: str,
    ) -> bool:
        """
        Restore a soft-deleted document.

        Args:
            doc_id: Document UUID.
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.

        Returns:
            True if restored successfully.
        """
        return await documents.restore_document(
            self.pool, doc_id, company_id, executive_id
        )

    async def get_combined_text(
        self,
        company_id: str,
        executive_id: str,
    ) -> str:
        """
        Get combined text from all active documents (both profile and knowledgebase).
        Used for general text retrieval.

        Args:
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.

        Returns:
            Combined text from all active documents.
        """
        docs = await documents.get_active_documents_text(
            self.pool, company_id, executive_id
        )
        if not docs:
            return ""

        texts = [d["extracted_text"] for d in docs]
        return "\n\n---\n\n".join(texts)

    async def get_combined_profile_text(
        self,
        company_id: str,
        executive_id: str,
    ) -> str:
        """
        Get combined text from PROFILE documents only.
        Used for calibration and LLM extraction (excludes knowledgebase docs).

        Args:
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.

        Returns:
            Combined text from profile documents only.
        """
        docs = await documents.get_active_profile_documents_text(
            self.pool, company_id, executive_id
        )
        if not docs:
            return ""

        texts = [d["extracted_text"] for d in docs]
        return "\n\n---\n\n".join(texts)

    async def get_combined_extractable_text(
        self,
        company_id: str,
        executive_id: str,
    ) -> str:
        """
        Get combined text from public+internal profile docs only (for calibration).
        Executive/confidential docs are excluded to prevent data leaks via profile_data.
        """
        docs = await documents.get_extractable_profile_documents_text(
            self.pool, company_id, executive_id
        )
        if not docs:
            return ""

        return "\n\n---\n\n".join(d["extracted_text"] for d in docs)

    async def get_document_count(
        self,
        company_id: str,
        executive_id: str,
        active_only: bool = True,
    ) -> int:
        """
        Get document count for an executive.

        Args:
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.
            active_only: Count only active documents.

        Returns:
            Document count.
        """
        return await documents.count_documents(
            self.pool, company_id, executive_id, active_only
        )
