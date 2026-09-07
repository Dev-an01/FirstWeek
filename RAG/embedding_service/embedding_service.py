"""
Core Embedding Service with Incremental Processing

Handles document embedding generation, change detection, version management,
and storage with queue-based processing capabilities.
"""

import logging
import time
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
from dataclasses import dataclass
from psycopg2.extras import Json

# Import existing components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from embedding_generation.model_manager import EmbeddingModel, get_shared_embedding_model
from vector_search.postgres_client import PostgresVectorClient

# Local imports
from .config import (
    POSTGRES_CONFIG,
    MODEL_NAME,
    EMBEDDING_DIMENSION,
    DEVICE,
    BATCH_SIZE,
    NORMALIZE_EMBEDDINGS,
    CHANGE_DETECTION,
    PROCESSING_CONFIG,
    VERSION_TABLE,
    VERSION_RETENTION_DAYS,
    MAX_VERSIONS_PER_DOCUMENT
)
from .models import (
    DocumentRequest,
    EmbeddingResult,
    ProcessingStatus,
    SourceType
)

logger = logging.getLogger(__name__)


@dataclass
class ChangeDetectionResult:
    """Result of change detection analysis"""
    has_changed: bool
    similarity_score: float
    previous_version: Optional[str]
    change_reason: str


class EmbeddingService:
    """
    Core embedding service with incremental processing capabilities.
    
    Features:
    - Incremental embedding updates with change detection
    - Version management and rollback capability
    - Batch processing for efficiency
    - Error handling and retry mechanisms
    - Integration with PostgreSQL and Neo4j storage
    """
    
    def __init__(self):
        """Initialize the embedding service."""
        logger.info("Initializing EmbeddingService...")
        
        # Initialize embedding model
        logger.info(f"Loading shared embedding model: {MODEL_NAME}")
        self.embedding_model = get_shared_embedding_model(
            model_name=MODEL_NAME,
            device=DEVICE
        )
        
        # Ensure model is on correct device (if shared instance was created on CPU fallback)
        if self.embedding_model.device != DEVICE and DEVICE == 'cuda':
             logger.warning(f"Shared model is on {self.embedding_model.device}, but config requested {DEVICE}")
        
        # Initialize database clients
        logger.info("Connecting to PostgreSQL...")
        self.postgres_client = PostgresVectorClient(config=POSTGRES_CONFIG)
        
        # Initialize version management
        self._init_version_table()
        
        logger.info("✅ EmbeddingService initialized successfully")
    
    def _init_version_table(self):
        """Initialize the version tracking table if it doesn't exist."""
        sql = f"""
            CREATE TABLE IF NOT EXISTS {VERSION_TABLE} (
                id SERIAL PRIMARY KEY,
                version VARCHAR(100) NOT NULL UNIQUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                description TEXT,
                parent_version VARCHAR(100),
                document_count INTEGER DEFAULT 0,
                metadata JSONB DEFAULT '{{}}',
                is_current BOOLEAN DEFAULT FALSE,
                expires_at TIMESTAMP WITH TIME ZONE
            );
            
            CREATE INDEX IF NOT EXISTS idx_{VERSION_TABLE}_version ON {VERSION_TABLE}(version);
            CREATE INDEX IF NOT EXISTS idx_{VERSION_TABLE}_created_at ON {VERSION_TABLE}(created_at);
            CREATE INDEX IF NOT EXISTS idx_{VERSION_TABLE}_is_current ON {VERSION_TABLE}(is_current);
        """
        
        conn = None
        try:
            conn = self.postgres_client.get_connection()
            with conn.cursor() as cur:
                cur.execute(sql)
                conn.commit()
                logger.debug(f"Version table {VERSION_TABLE} initialized")
        except Exception as e:
            logger.error(f"Failed to initialize version table: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.postgres_client.return_connection(conn)
    
    def process_single_document(
        self,
        document: DocumentRequest,
        detect_changes: bool = True
    ) -> EmbeddingResult:
        """
        Process a single document for embedding.
        
        Args:
            document: Document request with content and metadata
            detect_changes: Whether to perform change detection
        
        Returns:
            EmbeddingResult with processing status and details
        """
        start_time = time.time()
        
        try:
            logger.debug(f"Processing document: {document.source_id} ({document.source_type})")
            
            # Validate document
            self._validate_document(document)
            
            # Change detection (if enabled and not forced)
            change_result = None
            if detect_changes and not document.force_update:
                change_result = self._detect_changes(document)
                if not change_result.has_changed:
                    logger.info(f"No changes detected for {document.source_id}, skipping")
                    return EmbeddingResult(
                        source_id=document.source_id,
                        source_type=document.source_type,
                        status=ProcessingStatus.COMPLETED,
                        similarity_score=change_result.similarity_score,
                        processing_time_ms=(time.time() - start_time) * 1000,
                        metadata={"skipped": "no_changes", "reason": change_result.change_reason}
                    )
            
            # Generate embedding
            logger.debug(f"Generating embedding for {document.source_id}")
            embedding = self.embedding_model.generate_embedding(
                document.content,
                normalize=NORMALIZE_EMBEDDINGS
            )
            
            # Store embedding
            embedding_id = self._store_embedding(document, embedding)
            
            # Update version tracking
            version = self._update_document_version(document, change_result)
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.info(f"✅ Processed {document.source_id} in {processing_time:.1f}ms")
            
            return EmbeddingResult(
                source_id=document.source_id,
                source_type=document.source_type,
                status=ProcessingStatus.COMPLETED,
                embedding_id=embedding_id,
                version=version,
                similarity_score=change_result.similarity_score if change_result else None,
                processing_time_ms=processing_time,
                metadata=document.metadata
            )
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            error_msg = f"Failed to process {document.source_id}: {str(e)}"
            logger.error(error_msg)
            
            return EmbeddingResult(
                source_id=document.source_id,
                source_type=document.source_type,
                status=ProcessingStatus.FAILED,
                error_message=error_msg,
                processing_time_ms=processing_time
            )
    
    def process_batch(
        self,
        documents: List[DocumentRequest],
        detect_changes: bool = True
    ) -> List[EmbeddingResult]:
        """
        Process multiple documents in batch for efficiency.
        
        Args:
            documents: List of document requests
            detect_changes: Whether to perform change detection
        
        Returns:
            List of embedding results
        """
        if not documents:
            return []
        
        start_time = time.time()
        logger.info(f"Processing batch of {len(documents)} documents")
        
        results = []
        
        # Process in sub-batches for memory efficiency
        batch_size = PROCESSING_CONFIG['batch_processing_size']
        for i in range(0, len(documents), batch_size):
            sub_batch = documents[i:i + batch_size]
            logger.debug(f"Processing sub-batch {i//batch_size + 1}: {len(sub_batch)} documents")
            
            # Process each document in sub-batch
            for document in sub_batch:
                result = self.process_single_document(document, detect_changes)
                results.append(result)
        
        total_time = (time.time() - start_time) * 1000
        successful = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
        failed = len(results) - successful
        
        logger.info(f"✅ Batch completed: {successful}/{len(documents)} successful in {total_time:.1f}ms")
        
        return results
    
    def _validate_document(self, document: DocumentRequest):
        """Validate document request."""
        if not document.content or not document.content.strip():
            raise ValueError("Document content cannot be empty")
        
        if len(document.content) < CHANGE_DETECTION['min_content_length']:
            raise ValueError(f"Document too short: {len(document.content)} chars")
        
        if len(document.content) > CHANGE_DETECTION['max_content_length']:
            raise ValueError(f"Document too long: {len(document.content)} chars")
        
        if document.source_type not in SourceType:
            raise ValueError(f"Invalid source type: {document.source_type}")
    
    def _detect_changes(self, document: DocumentRequest) -> ChangeDetectionResult:
        """
        Detect if document content has changed significantly.
        
        Args:
            document: Document request to check
        
        Returns:
            ChangeDetectionResult with analysis
        """
        try:
            # Get existing embedding
            existing = self._get_existing_embedding(document.source_id, document.source_type)
            
            if not existing:
                return ChangeDetectionResult(
                    has_changed=True,
                    similarity_score=0.0,
                    previous_version=None,
                    change_reason="new_document"
                )
            
            # Generate embedding for new content
            new_embedding = self.embedding_model.generate_embedding(
                document.content,
                normalize=NORMALIZE_EMBEDDINGS
            )
            
            # Calculate similarity with existing embedding
            existing_embedding = np.array(existing['embedding'])
            similarity = float(np.dot(new_embedding, existing_embedding))
            
            threshold = CHANGE_DETECTION['content_similarity_threshold']
            has_changed = similarity < threshold
            
            change_reason = "content_changed" if has_changed else "content_unchanged"
            if has_changed:
                change_reason += f" (similarity: {similarity:.3f} < {threshold})"
            
            return ChangeDetectionResult(
                has_changed=has_changed,
                similarity_score=similarity,
                previous_version=existing.get('version'),
                change_reason=change_reason
            )
            
        except Exception as e:
            logger.warning(f"Change detection failed for {document.source_id}: {e}")
            # Default to processing if detection fails
            return ChangeDetectionResult(
                has_changed=True,
                similarity_score=0.0,
                previous_version=None,
                change_reason="detection_failed"
            )
    
    def _get_existing_embedding(
        self,
        source_id: str,
        source_type: str,
        company_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get existing embedding for a document."""
        if company_id:
            sql = """
                SELECT embedding, created_at
                FROM embeddings
                WHERE source_id = %s AND source_type = %s AND company_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = (source_id, source_type, company_id)
        else:
            sql = """
                SELECT embedding, created_at
                FROM embeddings
                WHERE source_id = %s AND source_type = %s
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = (source_id, source_type)

        conn = None
        try:
            conn = self.postgres_client.get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                result = cur.fetchone()

                if result:
                    return {
                        'embedding': result[0],
                        'version': None,
                        'created_at': result[1]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to get existing embedding: {e}")
            return None
        finally:
            if conn:
                self.postgres_client.return_connection(conn)
    
    def _store_embedding(
        self,
        document: DocumentRequest,
        embedding: np.ndarray
    ) -> str:
        """
        Store embedding in PostgreSQL.

        Args:
            document: Document request
            embedding: Generated embedding vector

        Returns:
            Embedding record ID
        """
        # Convert numpy array to list (same as RAG pipeline)
        embedding_list = embedding.tolist()

        # Extract tenant metadata if available
        meta = document.metadata or {}
        company_id = meta.get("company_id")
        executive_id = meta.get("executive_id")
        access_level = document.access_level or meta.get("access_level")

        # Use same pattern as RAG pipeline storage_writer.py
        sql = """
            INSERT INTO embeddings (
                source_type, source_id, text_content, embedding,
                chunk_index, metadata, company_id, executive_id, access_level, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (source_type, source_id, chunk_index)
            DO UPDATE SET
                text_content = EXCLUDED.text_content,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                executive_id = EXCLUDED.executive_id,
                access_level = EXCLUDED.access_level,
                created_at = NOW()
            RETURNING id
        """

        conn = None
        try:
            conn = self.postgres_client.get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, (
                    document.source_type.value,
                    document.source_id,
                    document.content,
                    embedding_list,
                    0,  # chunk_index default
                    Json(meta),
                    company_id,
                    executive_id,
                    access_level,
                ))
                result = cur.fetchone()
                conn.commit()

                logger.debug(f"Stored embedding for {document.source_id} (company={company_id}, exec={executive_id}, access={access_level})")
                return str(result[0]) if result else document.source_id

        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.postgres_client.return_connection(conn)
    
    def _update_document_version(
        self,
        document: DocumentRequest,
        change_result: Optional[ChangeDetectionResult]
    ) -> str:
        """
        Update version tracking for a document.
        
        Args:
            document: Document request
            change_result: Change detection result
        
        Returns:
            New version identifier
        """
        # Generate version identifier
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        content_hash = hashlib.md5(document.content.encode()).hexdigest()[:8]
        version = f"v{timestamp}_{content_hash}"
        
        # Store version info in metadata
        version_metadata = {
            "document_version": document.version or version,
            "change_detected": change_result.has_changed if change_result else True,
            "similarity_score": change_result.similarity_score if change_result else None,
            "previous_version": change_result.previous_version if change_result else None,
            "change_reason": change_result.change_reason if change_result else "new_document"
        }
        
        # Update document metadata with version info
        if document.metadata:
            document.metadata.update(version_metadata)
        else:
            document.metadata = version_metadata
        
        return version
    
    def create_version_snapshot(
        self,
        description: str = "",
        parent_version: Optional[str] = None
    ) -> str:
        """
        Create a version snapshot of current embeddings.
        
        Args:
            description: Description of this version
            parent_version: Parent version identifier
        
        Returns:
            New version identifier
        """
        version = f"snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Count current embeddings
        sql_count = "SELECT COUNT(*) FROM embeddings"
        
        # Insert version record
        sql_insert = f"""
            INSERT INTO {VERSION_TABLE} (
                version, description, parent_version, 
                document_count, is_current, expires_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        # Update current flag
        sql_update_current = f"""
            UPDATE {VERSION_TABLE} 
            SET is_current = FALSE 
            WHERE is_current = TRUE
        """
        
        conn = None
        try:
            conn = self.postgres_client.get_connection()
            with conn.cursor() as cur:
                # Get document count
                cur.execute(sql_count)
                doc_count = cur.fetchone()[0]
                
                # Clear current flag
                cur.execute(sql_update_current)
                
                # Insert new version
                expires_at = datetime.utcnow() + timedelta(days=VERSION_RETENTION_DAYS)
                cur.execute(sql_insert, (
                    version, description, parent_version,
                    doc_count, True, expires_at
                ))
                
                conn.commit()
                
                logger.info(f"Created version snapshot: {version} ({doc_count} documents)")
                return version
                
        except Exception as e:
            logger.error(f"Failed to create version snapshot: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.postgres_client.return_connection(conn)
    
    def get_version_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get version history."""
        sql = f"""
            SELECT version, created_at, description, parent_version,
                   document_count, is_current, metadata
            FROM {VERSION_TABLE}
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        conn = None
        try:
            conn = self.postgres_client.get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, (limit,))
                results = cur.fetchall()
                
                return [
                    {
                        'version': row[0],
                        'created_at': row[1],
                        'description': row[2],
                        'parent_version': row[3],
                        'document_count': row[4],
                        'is_current': row[5],
                        'metadata': row[6]
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Failed to get version history: {e}")
            return []
        finally:
            if conn:
                self.postgres_client.return_connection(conn)
    
    def cleanup_old_versions(self):
        """Clean up expired versions."""
        cutoff_date = datetime.utcnow() - timedelta(days=VERSION_RETENTION_DAYS)
        
        sql = f"""
            DELETE FROM {VERSION_TABLE}
            WHERE expires_at < %s AND is_current = FALSE
        """
        
        conn = None
        try:
            conn = self.postgres_client.get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, (cutoff_date,))
                deleted_count = cur.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired versions")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup old versions: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self.postgres_client.return_connection(conn)
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        try:
            # Get embedding counts
            sql_counts = """
                SELECT source_type, COUNT(*) as count
                FROM embeddings
                GROUP BY source_type
            """
            
            # Get version info
            sql_versions = f"""
                SELECT COUNT(*) as total_versions,
                       COUNT(CASE WHEN is_current = TRUE THEN 1 END) as current_versions
                FROM {VERSION_TABLE}
            """
            
            conn = None
            try:
                conn = self.postgres_client.get_connection()
                with conn.cursor() as cur:
                    # Get counts by type
                    cur.execute(sql_counts)
                    type_counts = dict(cur.fetchall())
                    
                    # Get version info
                    cur.execute(sql_versions)
                    version_info = cur.fetchone()
                    
                    return {
                        'total_embeddings': sum(type_counts.values()),
                        'embeddings_by_type': type_counts,
                        'total_versions': version_info[0],
                        'current_versions': version_info[1],
                        'model_name': MODEL_NAME,
                        'embedding_dimension': EMBEDDING_DIMENSION,
                        'device': self.embedding_model.device,
                        'batch_size': BATCH_SIZE
                    }
                    
            finally:
                if conn:
                    self.postgres_client.return_connection(conn)
                    
        except Exception as e:
            logger.error(f"Failed to get service stats: {e}")
            return {'error': str(e)}
    
    def close(self):
        """Clean up resources."""
        if self.postgres_client:
            self.postgres_client.close()
        logger.info("EmbeddingService closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()