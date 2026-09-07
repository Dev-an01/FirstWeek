"""
Knowledgebase Service - Business logic for company-wide document management.

Handles knowledgebase document upload, storage, retrieval, and deletion.
Knowledgebase documents bypass the LLM extraction pipeline and go directly
to embeddings with executive_id=NULL (shared by all executives in company).
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

logger = logging.getLogger(__name__)

# Thread pool for CPU-bound parsing (OCR can take 5+ minutes for large PDFs)
_parse_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kb_parser")

# Chunking configuration for knowledgebase documents
CHUNK_SIZE = 1000  # characters per chunk
CHUNK_OVERLAP = 200  # overlap between chunks


def _parse_with_metadata(filename: str, content: bytes):
    """Wrapper to call parse_document with return_metadata=True in thread pool."""
    return parse_document(filename, content, return_metadata=True)


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks for better retrieval.

    Args:
        text: Full document text.
        chunk_size: Target size for each chunk.
        overlap: Overlap between consecutive chunks.

    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at sentence/paragraph boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind("\n\n", start + overlap, end)
            if para_break > start + overlap:
                end = para_break
            else:
                # Look for sentence break
                sentence_break = max(
                    text.rfind(". ", start + overlap, end),
                    text.rfind("。", start + overlap, end),  # Japanese period
                    text.rfind("! ", start + overlap, end),
                    text.rfind("? ", start + overlap, end),
                )
                if sentence_break > start + overlap:
                    end = sentence_break + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


class KnowledgebaseService:
    """Service for managing company-wide knowledgebase documents."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def upload_knowledgebase_documents(
        self,
        company_id: str,
        files: List[Dict[str, Any]],
        access_level: str = "internal",
    ) -> Dict[str, Any]:
        """
        Upload and store knowledgebase documents for a company.

        Documents are parsed, chunked, and sent to embedding service with
        source_type='policy' and executive_id=NULL (company-wide).

        Args:
            company_id: Company ID.
            files: List of file dicts with 'filename', 'content', 'content_type'.

        Returns:
            Upload result with document metadata and embedding status.

        Raises:
            ValueError: If file exceeds size limit or cannot be parsed.
        """
        results = []
        all_chunks = []
        total_text_length = 0
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
            logger.debug(f"Parsing knowledgebase document '{filename}' in thread pool")
            parse_func = functools.partial(_parse_with_metadata, filename, content)
            parse_result = await loop.run_in_executor(_parse_executor, parse_func)
            extracted_text, metadata = parse_result

            # Store in database with doc_type='knowledgebase', executive_id=NULL
            doc = await documents.create_document(
                self.pool,
                company_id,
                None,  # executive_id = NULL for knowledgebase
                filename,
                content_type,
                file_size,
                extracted_text,
                parsing_method=metadata.get("parsing_method"),
                ocr_applied=metadata.get("ocr_applied", False),
                doc_type="knowledgebase",
            )

            # Chunk the document for embedding
            chunks = _chunk_text(extracted_text)
            doc_id = doc["id"]

            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "source_id": f"{doc_id}_chunk_{i:04d}",
                    "source_type": "policy",
                    "content": chunk,
                    "metadata": {
                        "company_id": company_id,
                        "executive_id": None,  # NULL = shared by all executives
                        "document_id": doc_id,
                        "filename": filename,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "access_level": access_level,
                    },
                    "access_level": access_level,
                    "force_update": True,
                })

            doc["chunk_count"] = len(chunks)
            results.append(doc)
            total_text_length += len(extracted_text)

        # Trigger embeddings for all chunks
        embedding_status = await self._trigger_embeddings(company_id, all_chunks)

        # Deploy Policy nodes to Neo4j for graph-augmented retrieval
        neo4j_status = await self._deploy_neo4j_policies(company_id, results)

        logger.info(
            f"Uploaded {len(results)} knowledgebase documents for {company_id} "
            f"({len(all_chunks)} chunks, {total_text_length} chars)"
        )

        return {
            "company_id": company_id,
            "documents": results,
            "total_text_length": total_text_length,
            "total_chunks": len(all_chunks),
            "embedding_status": embedding_status,
            "neo4j_status": neo4j_status,
        }

    async def _deploy_neo4j_policies(
        self,
        company_id: str,
        documents: List[Dict[str, Any]],
    ) -> str:
        """
        Create Policy nodes in Neo4j for uploaded knowledgebase documents.

        Soft-failure: Neo4j issues do not block the upload.

        Args:
            company_id: Company ID.
            documents: List of document dicts with 'id', 'filename', 'extracted_text'.

        Returns:
            Status string: 'completed', 'unavailable', 'failed', 'skipped'
        """
        if not documents:
            return "skipped"

        try:
            from onboarding.deployer.neo4j_deployer import Neo4jDeployer
            from onboarding.config import NEO4J_CONFIG

            deployer = Neo4jDeployer(
                uri=NEO4J_CONFIG["uri"],
                user=NEO4J_CONFIG["user"],
                password=NEO4J_CONFIG["password"]
            )
            connected = await deployer.connect()

            if not connected:
                logger.warning("Neo4j not available, skipping policy node creation")
                return "unavailable"

            deployed = 0
            for doc in documents:
                doc_id = doc.get("id", "")
                filename = doc.get("filename", "")
                content_summary = ""
                extracted = doc.get("extracted_text", "")
                if isinstance(extracted, str):
                    content_summary = extracted[:500]

                policy_data = {
                    "id": f"{company_id}_policy_{doc_id}",
                    "name": filename,
                    "category": "knowledgebase",
                    "content_summary": content_summary,
                }

                success = await deployer.deploy_company_policy(
                    company_id=company_id,
                    policy_data=policy_data,
                )
                if success:
                    deployed += 1

            await deployer.close()

            logger.info(
                f"Deployed {deployed}/{len(documents)} Policy nodes to Neo4j "
                f"for company {company_id}"
            )
            return "completed"

        except Exception as e:
            logger.warning(f"Neo4j policy deployment failed (non-fatal): {e}")
            return "failed"

    async def _trigger_embeddings(
        self,
        company_id: str,
        chunks: List[Dict[str, Any]],
    ) -> str:
        """
        Send knowledgebase chunks to embedding service.

        Args:
            company_id: Company ID.
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
                        "batch_id": f"knowledgebase_{company_id}",
                    },
                    params={"async_processing": "false"},
                )
                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"Knowledgebase embedding complete for {company_id}: "
                    f"{len(chunks)} chunks sent"
                )
                return "completed"

        except httpx.ConnectError:
            logger.warning(
                f"Embedding service not reachable at {EMBEDDING_SERVICE_URL}"
            )
            return "unavailable"

        except Exception as e:
            logger.error(f"Knowledgebase embedding failed: {e}")
            return "failed"

    async def list_knowledgebase(
        self,
        company_id: str,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List all knowledgebase documents for a company.

        Args:
            company_id: Company ID.
            include_inactive: Include soft-deleted documents.

        Returns:
            List of knowledgebase document metadata.
        """
        return await documents.list_company_knowledgebase(
            self.pool, company_id, include_inactive
        )

    async def get_knowledgebase_document(
        self,
        company_id: str,
        doc_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single knowledgebase document with full text.

        Args:
            company_id: Company ID.
            doc_id: Document UUID.

        Returns:
            Document with extracted text, or None if not found.
        """
        return await documents.get_knowledgebase_document(
            self.pool, doc_id, company_id
        )

    async def delete_knowledgebase_document(
        self,
        company_id: str,
        doc_id: str,
    ) -> Dict[str, Any]:
        """
        Soft delete a knowledgebase document and clean up associated embeddings.

        Args:
            company_id: Company ID.
            doc_id: Document UUID.

        Returns:
            Dict with deletion details, or empty dict if not found.
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
                    WHERE source_type = 'policy'
                      AND metadata->>'document_id' = $1
                      AND company_id = $2
                    """,
                    doc_id,
                    company_id,
                )
                embeddings_deleted += int(result2.split()[-1]) if result2 else 0

                # Soft-delete the document record
                deleted = await documents.soft_delete_knowledgebase_document(
                    self.pool, doc_id, company_id
                )

        if not deleted:
            return {}

        # Notify RAG service to refresh cache
        try:
            from onboarding.utils.rag_notifier import notify_rag_profile_refresh
            await notify_rag_profile_refresh(company_id, "", reason="knowledgebase_deleted")
        except Exception as e:
            logger.warning(f"RAG notification failed (non-fatal): {e}")

        logger.info(
            f"Deleted knowledgebase document {doc_id}: {embeddings_deleted} embeddings removed"
        )
        return {
            "status": "deleted",
            "doc_id": doc_id,
            "embeddings_deleted": embeddings_deleted,
        }
