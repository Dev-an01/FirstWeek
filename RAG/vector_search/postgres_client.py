"""
PostgreSQL Vector Search Client

Executes vector similarity queries using pgvector extension.
Implements connection pooling and metadata retrieval.
"""

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import logging

from .config import (
    POSTGRES_CONFIG,
    VECTOR_SEARCH_CONFIG,
    VALID_SOURCE_TYPES,
    METADATA_FIELDS
)

logger = logging.getLogger('vector_search.postgres_client')


class PostgresVectorClient:
    """
    Client for executing vector similarity searches on PostgreSQL with pgvector.
    
    Features:
    - Connection pooling for performance
    - Cosine similarity search using <=> operator
    - Metadata enrichment from source tables
    - Flexible filtering by source type and score threshold
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize PostgreSQL vector client with connection pooling.
        
        Args:
            config: Optional database configuration (defaults to POSTGRES_CONFIG)
        """
        self.config = config or POSTGRES_CONFIG
        self.pool_size = VECTOR_SEARCH_CONFIG['connection_pool_size']
        self.pool_max = VECTOR_SEARCH_CONFIG['connection_pool_max']
        
        # Initialize connection pool
        self.connection_pool = None
        self._init_connection_pool()
        
        logger.info(f"PostgresVectorClient initialized with pool size {self.pool_size}")
    
    def _init_connection_pool(self):
        """Initialize the connection pool."""
        try:
            self.connection_pool = pool.ThreadedConnectionPool(
                minconn=self.pool_size,
                maxconn=self.pool_max,
                host=self.config['host'],
                port=self.config['port'],
                database=self.config['database'],
                user=self.config['user'],
                password=self.config['password']
            )
            logger.debug("Connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise
    
    def get_connection(self):
        """Get a connection from the pool."""
        if self.connection_pool is None:
            self._init_connection_pool()
        return self.connection_pool.getconn()
    
    def return_connection(self, conn):
        """Return a connection to the pool."""
        if self.connection_pool:
            self.connection_pool.putconn(conn)
    
    def vector_search(
        self,
        query_embedding: np.ndarray,
        source_types: Optional[List[str]] = None,
        candidate_ids: Optional[List[str]] = None,
        top_k: int = 10,
        min_score: float = 0.0,
        company_id: Optional[str] = None,
        executive_id: Optional[str] = None,
        allowed_scopes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute vector similarity search using cosine distance.

        Args:
            query_embedding: Query vector (768-dimensional)
            source_types: Filter by source types (decision_case, policy, executive_profile)
            candidate_ids: Optional list of specific document IDs to search within (graph constraint)
            top_k: Maximum number of results to return
            min_score: Minimum similarity score threshold (0-1)
            company_id: Optional tenant filter - only return results for this company
            executive_id: Optional tenant filter - only return results for this executive (or shared)
            allowed_scopes: Optional RBAC scope filter (e.g. ['public', 'internal', 'executive'])

        Returns:
            List of search results with metadata and similarity scores
        """
        # Validate source types
        if source_types:
            invalid_types = set(source_types) - set(VALID_SOURCE_TYPES)
            if invalid_types:
                raise ValueError(f"Invalid source types: {invalid_types}. "
                               f"Valid types: {VALID_SOURCE_TYPES}")
        else:
            source_types = VALID_SOURCE_TYPES

        # Convert embedding to list for PostgreSQL
        embedding_list = query_embedding.tolist()

        # Format as PostgreSQL vector string
        embedding_str = '[' + ','.join(map(str, embedding_list)) + ']'

        # Build tenant filter clause
        tenant_clause = ""
        tenant_params = []
        if company_id:
            tenant_clause += " AND (company_id = %s OR company_id IS NULL)"
            tenant_params.append(company_id)
        if executive_id:
            tenant_clause += " AND (executive_id = %s OR executive_id IS NULL)"
            tenant_params.append(executive_id)

        # Build RBAC scope filter clause
        scope_clause = ""
        scope_params = []
        if allowed_scopes:
            scope_clause = " AND (access_level = ANY(%s) OR access_level IS NULL)"
            scope_params.append(allowed_scopes)

        # Query the embeddings table
        if candidate_ids:
            # Graph-constrained search
            sql = f"""
                SELECT
                    id,
                    source_id,
                    source_type,
                    text_content,
                    access_level,
                    embedding <=> %s::vector AS distance,
                    1 - (embedding <=> %s::vector) AS similarity_score,
                    created_at
                FROM embeddings
                WHERE
                    source_type = ANY(%s)
                    AND source_id = ANY(%s)
                    AND (1 - (embedding <=> %s::vector)) >= %s
                    {tenant_clause}
                    {scope_clause}
                ORDER BY embedding <=> %s ASC
                LIMIT %s
            """
            params = (
                embedding_str,   # For distance calculation
                embedding_str,   # For similarity score
                source_types,    # Source type filter
                candidate_ids,   # Candidate IDs constraint (from graph)
                embedding_str,   # For score threshold
                min_score,       # Minimum score
                *tenant_params,  # Tenant filters
                *scope_params,   # RBAC scope filters
                embedding_str,   # For ordering
                top_k           # Limit
            )
        else:
            # Standard unconstrained search
            sql = f"""
                SELECT
                    id,
                    source_id,
                    source_type,
                    text_content,
                    access_level,
                    embedding <=> %s::vector AS distance,
                    1 - (embedding <=> %s::vector) AS similarity_score,
                    created_at
                FROM embeddings
                WHERE
                    source_type = ANY(%s)
                    AND (1 - (embedding <=> %s::vector)) >= %s
                    {tenant_clause}
                    {scope_clause}
                ORDER BY embedding <=> %s ASC
                LIMIT %s
            """
            params = (
                embedding_str,   # For distance calculation
                embedding_str,   # For similarity score
                source_types,    # Source type filter
                embedding_str,   # For score threshold
                min_score,       # Minimum score
                *tenant_params,  # Tenant filters
                *scope_params,   # RBAC scope filters
                embedding_str,   # For ordering
                top_k           # Limit
            )
        
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                logger.debug(f"Executing vector search with source_types={source_types}, top_k={top_k}, min_score={min_score}")
                logger.debug(f"SQL: {sql[:200]}...")
                cur.execute(sql, params)
                results = cur.fetchall()
            
            # Convert to list of dicts
            results = [dict(row) for row in results]
            
            constraint_msg = f" (constrained to {len(candidate_ids)} candidates)" if candidate_ids else ""
            logger.info(f"Vector search returned {len(results)} results{constraint_msg}")
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def get_source_metadata(
        self,
        source_id: str,
        source_type: str,
        company_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve full metadata from the source table.

        Args:
            source_id: ID of the source document
            source_type: Type of source (decision_case, policy_document, executive_profile)
            company_id: Company ID for tenant isolation

        Returns:
            Dictionary with full metadata or None if not found
        """
        # Build optional company filter for tables that support it
        company_filter = ""
        extra_params = ()
        if company_id:
            company_filter = " AND company_id = %s"
            extra_params = (company_id,)

        # Map source_type to table and key fields
        source_queries = {
            'executive_profile': (
                f"""
                SELECT id as source_id, 'executive_profile' as source_type,
                       name
                FROM executive_profiles
                WHERE id = %s{company_filter}
                """,
                (source_id,) + extra_params
            ),
            'policy': (
                """
                SELECT id as source_id, 'policy' as source_type,
                       name
                FROM policy_documents
                WHERE id = %s
                """,
                (source_id,)
            ),
            'decision_case': (
                f"""
                SELECT id as source_id, 'decision_case' as source_type,
                       title
                FROM decision_cases
                WHERE id = %s{company_filter}
                """,
                (source_id,) + extra_params
            ),
            'voiceprint': (
                f"""
                SELECT e.id as source_id, 'voiceprint' as source_type,
                       e.name, e.title as executive_title,
                       emb.text_content as voiceprint_text
                FROM executive_profiles e
                LEFT JOIN embeddings emb ON emb.source_id = e.id AND emb.source_type = 'voiceprint'
                WHERE e.id = %s{' AND e.company_id = %s' if company_id else ''}
                """,
                (source_id,) + extra_params
            ),
            'document': (
                f"""
                SELECT
                    COALESCE(ds.id, emb.source_id) as source_id,
                    'document' as source_type,
                    COALESCE(ds.section_title, 'Document') as title,
                    ds.parent_document_id,
                    ds.parent_document_type,
                    COALESCE(ds.content, emb.text_content) as content,
                    ds.section_type
                FROM embeddings emb
                LEFT JOIN document_sections ds ON ds.id = emb.source_id
                WHERE emb.source_id = %s AND emb.source_type = 'document'
                    {' AND emb.company_id = %s' if company_id else ''}
                LIMIT 1
                """,
                (source_id,) + extra_params
            )
        }

        # Get the appropriate query
        query_info = source_queries.get(source_type)
        if not query_info:
            logger.warning(f"Unknown source_type: {source_type}")
            return None

        sql, params = query_info

        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                result = cur.fetchone()

            if result:
                metadata = dict(result)
                title_or_name = metadata.get('title') or metadata.get('name', 'NO_TITLE_OR_NAME')
                logger.info(f"✓ Retrieved metadata for {source_type}:{source_id} - title/name: {title_or_name}")
                return metadata
            else:
                logger.warning(f"✗ No metadata found for {source_type}:{source_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to retrieve metadata for {source_type}:{source_id}: {e}")
            return None
        finally:
            if conn:
                self.return_connection(conn)
    
    def batch_get_metadata(
        self,
        source_items: List[Tuple[str, str]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve metadata for multiple sources efficiently.

        Args:
            source_items: List of (source_id, source_type) tuples

        Returns:
            Dictionary mapping source_id to metadata
        """
        # Group by source type
        grouped = {}
        for source_id, source_type in source_items:
            if source_type not in grouped:
                grouped[source_type] = []
            grouped[source_type].append(source_id)

        # Fetch in batches by type
        results = {}
        for source_type, source_ids in grouped.items():
            for source_id in source_ids:
                metadata = self.get_source_metadata(source_id, source_type)
                if metadata:
                    results[source_id] = metadata

        logger.debug(f"Retrieved metadata for {len(results)}/{len(source_items)} sources")
        return results

    def vector_search_sections(
        self,
        query_embedding: np.ndarray,
        source_types: Optional[List[str]] = None,
        candidate_section_ids: Optional[List[str]] = None,
        candidate_doc_ids: Optional[List[str]] = None,
        top_k: int = 10,
        min_score: float = 0.0,
        company_id: Optional[str] = None,
        executive_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute vector similarity search on document sections.

        This is the NEW section-level search method that enables semantic chunking.

        Args:
            query_embedding: Query vector (768-dimensional)
            source_types: Filter by parent document types (decision, policy)
            candidate_section_ids: Optional list of specific section IDs to search within
            candidate_doc_ids: Optional list of parent document IDs to constrain search
            top_k: Maximum number of results to return
            min_score: Minimum similarity score threshold (0-1)

        Returns:
            List of section search results with metadata and similarity scores
            Each result includes:
            - section_id: Section ID
            - parent_document_id: Parent document ID
            - parent_document_type: Document type
            - section_number: Section order
            - section_title: Section heading
            - section_type: Section classification
            - content: Section text
            - word_count: Section length
            - similarity_score: Cosine similarity score
        """
        # Validate source types
        if source_types:
            # Map common names to database values
            type_mapping = {
                'decision_case': 'decision',
                'policy_document': 'policy',
                'policy': 'policy',
                'decision': 'decision'
            }
            source_types = [type_mapping.get(t, t) for t in source_types]

        # Convert embedding to list for PostgreSQL
        embedding_list = query_embedding.tolist()

        # Format as PostgreSQL vector string
        embedding_str = '[' + ','.join(map(str, embedding_list)) + ']'

        # Build tenant filter clause for document_sections
        tenant_clause = ""
        tenant_params = []
        if company_id:
            tenant_clause += " AND (ds.company_id = %s OR ds.company_id IS NULL)"
            tenant_params.append(company_id)
        if executive_id:
            tenant_clause += " AND (ds.executive_id = %s OR ds.executive_id IS NULL)"
            tenant_params.append(executive_id)

        # Build query with section metadata join
        if candidate_section_ids:
            # Constrained search by specific section IDs
            sql = f"""
                SELECT
                    se.id,
                    se.section_id,
                    ds.parent_document_id,
                    ds.parent_document_type,
                    ds.section_number,
                    ds.section_title,
                    ds.section_type,
                    ds.content,
                    ds.word_count,
                    ds.boundary_type,
                    ds.executive_id,
                    ds.document_category,
                    se.embedding <=> %s::vector AS distance,
                    1 - (se.embedding <=> %s::vector) AS similarity_score,
                    se.created_at
                FROM section_embeddings se
                JOIN document_sections ds ON se.section_id = ds.id
                WHERE
                    se.section_id = ANY(%s)
                    AND (1 - (se.embedding <=> %s::vector)) >= %s
                    {tenant_clause}
                ORDER BY se.embedding <=> %s ASC
                LIMIT %s
            """
            params = (
                embedding_str,
                embedding_str,
                candidate_section_ids,
                embedding_str,
                min_score,
                *tenant_params,
                embedding_str,
                top_k
            )
        elif candidate_doc_ids:
            # Constrained search by parent document IDs (from graph context)
            if source_types:
                sql = f"""
                    SELECT
                        se.id,
                        se.section_id,
                        ds.parent_document_id,
                        ds.parent_document_type,
                        ds.section_number,
                        ds.section_title,
                        ds.section_type,
                        ds.content,
                        ds.word_count,
                        ds.boundary_type,
                        ds.executive_id,
                        ds.document_category,
                        se.embedding <=> %s::vector AS distance,
                        1 - (se.embedding <=> %s::vector) AS similarity_score,
                        se.created_at
                    FROM section_embeddings se
                    JOIN document_sections ds ON se.section_id = ds.id
                    WHERE
                        ds.parent_document_id = ANY(%s)
                        AND ds.parent_document_type = ANY(%s)
                        AND (1 - (se.embedding <=> %s::vector)) >= %s
                        {tenant_clause}
                    ORDER BY se.embedding <=> %s ASC
                    LIMIT %s
                """
                params = (
                    embedding_str,
                    embedding_str,
                    candidate_doc_ids,
                    source_types,
                    embedding_str,
                    min_score,
                    *tenant_params,
                    embedding_str,
                    top_k
                )
            else:
                sql = f"""
                    SELECT
                        se.id,
                        se.section_id,
                        ds.parent_document_id,
                        ds.parent_document_type,
                        ds.section_number,
                        ds.section_title,
                        ds.section_type,
                        ds.content,
                        ds.word_count,
                        ds.boundary_type,
                        ds.executive_id,
                        ds.document_category,
                        se.embedding <=> %s::vector AS distance,
                        1 - (se.embedding <=> %s::vector) AS similarity_score,
                        se.created_at
                    FROM section_embeddings se
                    JOIN document_sections ds ON se.section_id = ds.id
                    WHERE
                        ds.parent_document_id = ANY(%s)
                        AND (1 - (se.embedding <=> %s::vector)) >= %s
                        {tenant_clause}
                    ORDER BY se.embedding <=> %s ASC
                    LIMIT %s
                """
                params = (
                    embedding_str,
                    embedding_str,
                    candidate_doc_ids,
                    embedding_str,
                    min_score,
                    *tenant_params,
                    embedding_str,
                    top_k
                )
        else:
            # Standard unconstrained section search
            if source_types:
                sql = f"""
                    SELECT
                        se.id,
                        se.section_id,
                        ds.parent_document_id,
                        ds.parent_document_type,
                        ds.section_number,
                        ds.section_title,
                        ds.section_type,
                        ds.content,
                        ds.word_count,
                        ds.boundary_type,
                        ds.executive_id,
                        ds.document_category,
                        se.embedding <=> %s::vector AS distance,
                        1 - (se.embedding <=> %s::vector) AS similarity_score,
                        se.created_at
                    FROM section_embeddings se
                    JOIN document_sections ds ON se.section_id = ds.id
                    WHERE
                        ds.parent_document_type = ANY(%s)
                        AND (1 - (se.embedding <=> %s::vector)) >= %s
                        {tenant_clause}
                    ORDER BY se.embedding <=> %s ASC
                    LIMIT %s
                """
                params = (
                    embedding_str,
                    embedding_str,
                    source_types,
                    embedding_str,
                    min_score,
                    *tenant_params,
                    embedding_str,
                    top_k
                )
            else:
                sql = f"""
                    SELECT
                        se.id,
                        se.section_id,
                        ds.parent_document_id,
                        ds.parent_document_type,
                        ds.section_number,
                        ds.section_title,
                        ds.section_type,
                        ds.content,
                        ds.word_count,
                        ds.boundary_type,
                        ds.executive_id,
                        ds.document_category,
                        se.embedding <=> %s::vector AS distance,
                        1 - (se.embedding <=> %s::vector) AS similarity_score,
                        se.created_at
                    FROM section_embeddings se
                    JOIN document_sections ds ON se.section_id = ds.id
                    WHERE
                        (1 - (se.embedding <=> %s::vector)) >= %s
                        {tenant_clause}
                    ORDER BY se.embedding <=> %s ASC
                    LIMIT %s
                """
                params = (
                    embedding_str,
                    embedding_str,
                    embedding_str,
                    min_score,
                    *tenant_params,
                    embedding_str,
                    top_k
                )

        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                logger.debug(f"Executing section vector search with source_types={source_types}, top_k={top_k}, min_score={min_score}")
                cur.execute(sql, params)
                results = cur.fetchall()

            # Convert to list of dicts
            results = [dict(row) for row in results]

            constraint_msg = ""
            if candidate_section_ids:
                constraint_msg = f" (constrained to {len(candidate_section_ids)} sections)"
            elif candidate_doc_ids:
                constraint_msg = f" (constrained to {len(candidate_doc_ids)} documents)"

            logger.info(f"Section vector search returned {len(results)} results{constraint_msg}")
            return results

        except Exception as e:
            logger.error(f"Section vector search failed: {e}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def close(self):
        """Close all connections in the pool."""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Connection pool closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
