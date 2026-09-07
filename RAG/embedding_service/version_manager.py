"""
Version Manager for Embedding Service

Handles version tracking, rollback operations, and snapshot management
with support for incremental updates and safe rollbacks.
"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor, Json

# Local imports
from .config import (
    POSTGRES_CONFIG,
    VERSION_TABLE,
    VERSION_RETENTION_DAYS,
    MAX_VERSIONS_PER_DOCUMENT,
    ROLLBACK_TIMEOUT_SECONDS,
    ROLLBACK_BATCH_SIZE
)
from .models import (
    VersionInfo,
    RollbackResponse,
    ProcessingStatus
)

logger = logging.getLogger(__name__)


class VersionManager:
    """
    Manages embedding versions with rollback capability.
    
    Features:
    - Version snapshots with metadata
    - Safe rollback operations
    - Version history tracking
    - Automatic cleanup of old versions
    - Document-level version tracking
    """
    
    def __init__(self):
        """Initialize version manager."""
        logger.info("Initializing VersionManager...")
        
        # Initialize database connection
        self.config = POSTGRES_CONFIG
        self._init_version_table()
        self._init_document_version_table()
        
        logger.info("✅ VersionManager initialized successfully")
    
    def _init_version_table(self):
        """Initialize version tracking table if it doesn't exist."""
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
                expires_at TIMESTAMP WITH TIME ZONE,
                rollback_info JSONB DEFAULT '{{}}'
            );
            
            CREATE INDEX IF NOT EXISTS idx_{VERSION_TABLE}_version ON {VERSION_TABLE}(version);
            CREATE INDEX IF NOT EXISTS idx_{VERSION_TABLE}_created_at ON {VERSION_TABLE}(created_at);
            CREATE INDEX IF NOT EXISTS idx_{VERSION_TABLE}_is_current ON {VERSION_TABLE}(is_current);
            CREATE INDEX IF NOT EXISTS idx_{VERSION_TABLE}_parent_version ON {VERSION_TABLE}(parent_version);
        """
        
        self._execute_sql(sql)
        logger.debug(f"Version table {VERSION_TABLE} initialized")
    
    def _init_document_version_table(self):
        """Initialize document version tracking table."""
        doc_version_table = 'document_versions'
        sql = f"""
            CREATE TABLE IF NOT EXISTS {doc_version_table} (
                id SERIAL PRIMARY KEY,
                source_id VARCHAR(255) NOT NULL,
                source_type VARCHAR(50) NOT NULL,
                version VARCHAR(100) NOT NULL,
                embedding_id VARCHAR(255) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                is_current BOOLEAN DEFAULT FALSE,
                metadata JSONB DEFAULT '{{}}',
                UNIQUE(source_id, source_type, version)
            );
            
            CREATE INDEX IF NOT EXISTS idx_{doc_version_table}_source ON {doc_version_table}(source_id, source_type);
            CREATE INDEX IF NOT EXISTS idx_{doc_version_table}_version ON {doc_version_table}(version);
            CREATE INDEX IF NOT EXISTS idx_{doc_version_table}_is_current ON {doc_version_table}(is_current);
            CREATE INDEX IF NOT EXISTS idx_{doc_version_table}_created_at ON {doc_version_table}(created_at);
        """
        
        self._execute_sql(sql)
        logger.debug(f"Document version table {doc_version_table} initialized")
    
    def _execute_sql(self, sql: str, params: Optional[Tuple] = None):
        """Execute SQL with connection management."""
        conn = None
        try:
            conn = psycopg2.connect(**self.config)
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"SQL execution failed: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _execute_query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Execute query and return results."""
        conn = None
        try:
            conn = psycopg2.connect(**self.config)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params or ())
                results = cur.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def create_snapshot(
        self,
        description: str = "",
        parent_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a version snapshot of current embeddings.
        
        Args:
            description: Description of this version
            parent_version: Parent version identifier
            metadata: Additional version metadata
        
        Returns:
            New version identifier
        """
        start_time = time.time()
        
        try:
            # Generate version identifier
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            version = f"v{timestamp}_{uuid.uuid4().hex[:8]}"
            
            # Count current embeddings
            count_sql = "SELECT COUNT(*) FROM embeddings"
            count_result = self._execute_query(count_sql)
            doc_count = count_result[0]['count'] if count_result else 0
            
            # Clear current flag for all versions
            clear_current_sql = f"UPDATE {VERSION_TABLE} SET is_current = FALSE WHERE is_current = TRUE"
            self._execute_sql(clear_current_sql)
            
            # Insert new version
            expires_at = datetime.utcnow() + timedelta(days=VERSION_RETENTION_DAYS)
            insert_sql = f"""
                INSERT INTO {VERSION_TABLE} (
                    version, description, parent_version, 
                    document_count, is_current, expires_at, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            version_metadata = metadata or {}
            version_metadata.update({
                'created_by': 'embedding_service',
                'snapshot_type': 'manual' if description else 'automatic'
            })
            
            self._execute_sql(insert_sql, (
                version, description, parent_version,
                doc_count, True, expires_at,
                Json(version_metadata)
            ))
            
            # Update document version tracking
            self._update_document_versions(version)
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.info(f"✅ Created version snapshot: {version} ({doc_count} documents, {processing_time:.1f}ms)")
            
            return version
            
        except Exception as e:
            logger.error(f"Failed to create version snapshot: {e}")
            raise
    
    def _update_document_versions(self, version: str):
        """Update document version tracking for current embeddings."""
        sql = """
            INSERT INTO document_versions (source_id, source_type, version, embedding_id, is_current)
            SELECT e.source_id, e.source_type, %s, e.id, TRUE
            FROM embeddings e
            ON CONFLICT (source_id, source_type, version) 
            DO UPDATE SET
                embedding_id = EXCLUDED.embedding_id,
                is_current = EXCLUDED.is_current,
                created_at = NOW()
        """
        
        # Clear current flags for existing documents
        clear_current_sql = """
            UPDATE document_versions 
            SET is_current = FALSE 
            WHERE is_current = TRUE
        """
        
        try:
            self._execute_sql(clear_current_sql)
            self._execute_sql(sql, (version,))
            logger.debug(f"Updated document versions for {version}")
            
        except Exception as e:
            logger.error(f"Failed to update document versions: {e}")
            raise
    
    def get_version_history(self, limit: int = 20) -> List[VersionInfo]:
        """Get version history."""
        sql = f"""
            SELECT version, created_at, description, parent_version,
                   document_count, is_current, metadata, rollback_info
            FROM {VERSION_TABLE}
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        try:
            results = self._execute_query(sql, (limit,))
            
            return [
                VersionInfo(
                    version=row['version'],
                    created_at=row['created_at'],
                    description=row['description'],
                    parent_version=row['parent_version'],
                    document_count=row['document_count'],
                    is_current=row['is_current'],
                    metadata=row['metadata'] or {}
                )
                for row in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to get version history: {e}")
            return []
    
    def get_version_info(self, version: str) -> Optional[VersionInfo]:
        """Get detailed information about a specific version."""
        sql = f"""
            SELECT version, created_at, description, parent_version,
                   document_count, is_current, metadata, rollback_info
            FROM {VERSION_TABLE}
            WHERE version = %s
        """
        
        try:
            results = self._execute_query(sql, (version,))
            
            if not results:
                return None
            
            row = results[0]
            return VersionInfo(
                version=row['version'],
                created_at=row['created_at'],
                description=row['description'],
                parent_version=row['parent_version'],
                document_count=row['document_count'],
                is_current=row['is_current'],
                metadata=row['metadata'] or {}
            )
            
        except Exception as e:
            logger.error(f"Failed to get version info: {e}")
            return None
    
    def rollback_to_version(
        self,
        target_version: str,
        source_ids: Optional[List[str]] = None
    ) -> RollbackResponse:
        """
        Rollback embeddings to a previous version.
        
        Args:
            target_version: Target version to rollback to
            source_ids: Specific document IDs to rollback (None = all)
        
        Returns:
            RollbackResponse with rollback details
        """
        start_time = time.time()
        
        try:
            # Validate target version exists
            target_info = self.get_version_info(target_version)
            if not target_info:
                raise ValueError(f"Target version not found: {target_version}")
            
            # Get current version for response
            current_versions = self.get_version_history(limit=1)
            current_version = current_versions[0].version if current_versions else "unknown"
            
            # Get documents to rollback
            if source_ids:
                # Specific documents
                documents_sql = """
                    SELECT dv.source_id, dv.source_type, dv.embedding_id, e.text_content
                    FROM document_versions dv
                    JOIN embeddings e ON dv.embedding_id = e.id
                    WHERE dv.version = %s AND dv.source_id = ANY(%s)
                """
                params = (target_version, source_ids)
            else:
                # All documents in version
                documents_sql = """
                    SELECT dv.source_id, dv.source_type, dv.embedding_id, e.text_content
                    FROM document_versions dv
                    JOIN embeddings e ON dv.embedding_id = e.id
                    WHERE dv.version = %s
                """
                params = (target_version,)
            
            target_documents = self._execute_query(documents_sql, params)
            
            if not target_documents:
                raise ValueError(f"No documents found in version: {target_version}")
            
            # Perform rollback in batches
            total_rolled_back = 0
            batch_size = ROLLBACK_BATCH_SIZE
            
            for i in range(0, len(target_documents), batch_size):
                batch = target_documents[i:i + batch_size]
                self._rollback_batch(batch, target_version)
                total_rolled_back += len(batch)
                
                # Check timeout
                if (time.time() - start_time) > ROLLBACK_TIMEOUT_SECONDS:
                    raise TimeoutError("Rollback operation timed out")
            
            # Create new version for rollback
            rollback_version = self.create_snapshot(
                description=f"Rollback to {target_version}",
                parent_version=current_version,
                metadata={
                    'rollback_from': current_version,
                    'rollback_to': target_version,
                    'documents_rolled_back': total_rolled_back,
                    'rollback_type': 'partial' if source_ids else 'full'
                }
            )
            
            # Update rollback info in target version
            rollback_info = {
                'rolled_back_at': datetime.utcnow().isoformat(),
                'rolled_back_to': rollback_version,
                'documents_rolled_back': total_rolled_back,
                'rollback_type': 'partial' if source_ids else 'full'
            }
            
            update_rollback_sql = f"""
                UPDATE {VERSION_TABLE}
                SET rollback_info = %s
                WHERE version = %s
            """
            self._execute_sql(update_rollback_sql, (Json(rollback_info), target_version))
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.info(f"✅ Rollback completed: {current_version} → {target_version} "
                       f"({total_rolled_back} documents, {processing_time:.1f}ms)")
            
            return RollbackResponse(
                success=True,
                target_version=target_version,
                previous_version=current_version,
                documents_rolled_back=total_rolled_back,
                rollback_time_ms=processing_time,
                new_version=rollback_version,
                request_id=f"rollback_{uuid.uuid4().hex[:8]}"
            )
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            error_msg = f"Rollback failed: {str(e)}"
            logger.error(error_msg)
            
            return RollbackResponse(
                success=False,
                target_version=target_version,
                previous_version="unknown",
                documents_rolled_back=0,
                rollback_time_ms=processing_time,
                new_version="",
                request_id=f"rollback_{uuid.uuid4().hex[:8]}"
            )
    
    def _rollback_batch(self, batch: List[Dict[str, Any]], target_version: str):
        """Rollback a batch of documents."""
        try:
            conn = psycopg2.connect(**self.config)
            with conn.cursor() as cur:
                for doc in batch:
                    # Update embeddings table
                    update_embedding_sql = """
                        UPDATE embeddings 
                        SET text_content = %s, created_at = NOW()
                        WHERE id = %s
                    """
                    cur.execute(update_embedding_sql, (doc['text_content'], doc['embedding_id']))
                    
                    # Update document versions
                    update_version_sql = """
                        UPDATE document_versions 
                        SET is_current = FALSE 
                        WHERE source_id = %s AND source_type = %s AND is_current = TRUE
                    """
                    cur.execute(update_version_sql, (doc['source_id'], doc['source_type']))
                    
                    # Set current version for rollback
                    set_current_sql = """
                        UPDATE document_versions 
                        SET is_current = TRUE 
                        WHERE source_id = %s AND source_type = %s AND version = %s
                    """
                    cur.execute(set_current_sql, (doc['source_id'], doc['source_type'], target_version))
                
                conn.commit()
                logger.debug(f"Rolled back batch of {len(batch)} documents")
                
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Batch rollback failed: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def cleanup_expired_versions(self) -> Dict[str, Any]:
        """Clean up expired versions and maintain version limits."""
        start_time = time.time()
        
        try:
            # Delete expired versions
            cutoff_date = datetime.utcnow() - timedelta(days=VERSION_RETENTION_DAYS)
            delete_expired_sql = f"""
                DELETE FROM {VERSION_TABLE}
                WHERE expires_at < %s AND is_current = FALSE
            """
            
            self._execute_sql(delete_expired_sql, (cutoff_date,))
            
            # Maintain version limits per document
            self._cleanup_document_versions()
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.info(f"✅ Cleanup completed in {processing_time:.1f}ms")
            
            return {
                'success': True,
                'processing_time_ms': processing_time,
                'cutoff_date': cutoff_date.isoformat(),
                'message': 'Cleanup completed successfully'
            }
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            error_msg = f"Cleanup failed: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'processing_time_ms': processing_time,
                'error': error_msg
            }
    
    def _cleanup_document_versions(self):
        """Maintain version limits per document."""
        # Get documents with too many versions
        check_sql = """
            SELECT source_id, source_type, COUNT(*) as version_count
            FROM document_versions
            GROUP BY source_id, source_type
            HAVING COUNT(*) > %s
        """
        
        try:
            over_limit_docs = self._execute_query(check_sql, (MAX_VERSIONS_PER_DOCUMENT,))
            
            for doc in over_limit_docs:
                # Get versions to delete (keep most recent)
                versions_to_delete_sql = """
                    SELECT version FROM document_versions
                    WHERE source_id = %s AND source_type = %s
                    ORDER BY created_at DESC
                    OFFSET %s
                """
                
                versions_to_delete = self._execute_query(
                    versions_to_delete_sql,
                    (doc['source_id'], doc['source_type'], MAX_VERSIONS_PER_DOCUMENT)
                )
                
                # Delete old versions
                for version_info in versions_to_delete:
                    delete_sql = """
                        DELETE FROM document_versions
                        WHERE source_id = %s AND source_type = %s AND version = %s
                    """
                    self._execute_sql(delete_sql, (
                        doc['source_id'], 
                        doc['source_type'], 
                        version_info['version']
                    ))
                
                if versions_to_delete:
                    logger.debug(f"Cleaned up {len(versions_to_delete)} old versions for "
                               f"{doc['source_id']} ({doc['source_type']})")
                    
        except Exception as e:
            logger.error(f"Document version cleanup failed: {e}")
    
    def get_current_version(self) -> Optional[str]:
        """Get the current active version."""
        sql = f"""
            SELECT version FROM {VERSION_TABLE}
            WHERE is_current = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        try:
            results = self._execute_query(sql)
            return results[0]['version'] if results else None
            
        except Exception as e:
            logger.error(f"Failed to get current version: {e}")
            return None
    
    def get_document_versions(self, source_id: str, source_type: str) -> List[Dict[str, Any]]:
        """Get version history for a specific document."""
        sql = """
            SELECT version, embedding_id, created_at, is_current, metadata
            FROM document_versions
            WHERE source_id = %s AND source_type = %s
            ORDER BY created_at DESC
        """
        
        try:
            return self._execute_query(sql, (source_id, source_type))
            
        except Exception as e:
            logger.error(f"Failed to get document versions: {e}")
            return []