"""
Vector Search Engine - Main API

Integrates all components to provide semantic search over executive content.
"""

import time
import logging
from typing import List, Dict, Any, Optional
import numpy as np

# Import components
from .postgres_client import PostgresVectorClient
from .embedding_cache import EmbeddingCache
from .query_processor import QueryProcessor
from .result_processor import ResultProcessor
from .response_builder import ResponseBuilder
from .rbac_filter import RBACFilter
from .config import (
    VECTOR_SEARCH_CONFIG,
    MODEL_NAME,
    EMBEDDING_DIMENSION,
    POSTGRES_CONFIG
)

# Import model manager
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from embedding_generation.model_manager import EmbeddingModel
from .embedding_client import get_embedding_client

# Observability imports
from observability.decorators import trace_function
from observability.logging import StructuredLogger
from observability.metrics import (
    vector_search_latency,
    retrieval_results_counter,
)

# WEEK 1, DAY 3: LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False

# Fallback: no-op decorator that handles keyword arguments
if not LANGSMITH_AVAILABLE:
    def traceable(*args, **kwargs):
        """No-op traceable decorator fallback."""
        def decorator(func):
            return func
        # Handle @traceable without parens and @traceable() with args/kwargs
        if args and callable(args[0]):
            return args[0]
        return decorator

logger = logging.getLogger('vector_search.search_engine')
obs_logger = StructuredLogger('vector_search')


class VectorSearchEngine:
    """
    Main vector search engine API.
    
    Features:
    - Semantic search using sentence transformers
    - Two-level embedding cache (memory + Redis)
    - PostgreSQL vector similarity with pgvector
    - Role-based access control
    - Metadata enrichment and citation generation
    
    Usage:
        engine = VectorSearchEngine()
        results = engine.search("What is our discount policy?")
        print(results['results'])
    """
    
    def __init__(
        self,
        model_name: str = None,
        postgres_config: Dict[str, Any] = None,
        neo4j_config: Dict[str, Any] = None,
        enable_cache: bool = True,
        enable_redis: bool = False,
        enable_graph_context: bool = True,
    ):
        """
        Initialize the vector search engine.
        
        Args:
            model_name: Sentence transformer model (defaults to config)
            postgres_config: PostgreSQL configuration (defaults to config)
            neo4j_config: Neo4j configuration for graph context (optional)
            enable_cache: Enable L1 memory cache
            enable_redis: Enable L2 Redis cache
            enable_graph_context: Enable graph-enhanced search (default: True)
        """
        logger.info("Initializing VectorSearchEngine...")
        
        # Configuration
        self.model_name = model_name or MODEL_NAME
        self.postgres_config = postgres_config or POSTGRES_CONFIG
        
        # Initialize embedding service client
        self.embedding_client = get_embedding_client()
        
        # Load embedding model as fallback
        # Load embedding model as fallback
        logger.info(f"Loading/Retrieving shared embedding model: {self.model_name}")
        from embedding_generation.model_manager import get_shared_embedding_model
        self.embedding_model = get_shared_embedding_model(model_name=self.model_name)
        
        # Initialize PostgreSQL vector client
        logger.info("Connecting to PostgreSQL...")
        self.vector_client = PostgresVectorClient(config=self.postgres_config)
        
        # Initialize embedding cache
        if enable_cache:
            cache_size = VECTOR_SEARCH_CONFIG['cache_size']
            logger.info(f"Initializing embedding cache (size={cache_size}, redis={enable_redis})")
            self.cache = EmbeddingCache(
                max_size=cache_size,
                enable_redis=enable_redis
            )
        else:
            logger.info("Cache disabled")
            self.cache = None
        
        # Initialize processors
        self.query_processor = QueryProcessor()
        self.result_processor = ResultProcessor()
        self.response_builder = ResponseBuilder()
        self.rbac_filter = RBACFilter()
        
        # NEW: Initialize graph context provider
        if enable_graph_context:
            try:
                from graph_context import GraphContextProvider
                logger.info("Initializing graph context provider...")
                self.graph_provider = GraphContextProvider(neo4j_config=neo4j_config)
                logger.info("✅ Graph context provider initialized")
            except Exception as e:
                logger.warning(f"Graph context provider initialization failed: {e}")
                logger.warning("Continuing with pure vector search (no graph enhancement)")
                self.graph_provider = None
        else:
            logger.info("Graph context disabled")
            self.graph_provider = None
        
        logger.info("✅ VectorSearchEngine initialized successfully")
    
    @trace_function("vector_search", "search")
    @traceable(name="vector_search", tags=["retrieval", "vector"])
    def search(
        self,
        query: str,
        source_types: Optional[List[str]] = None,
        top_k: int = None,
        min_score: float = None,
        role: str = None,
        company_id: Optional[str] = None,
        executive_id: Optional[str] = None,
        include_metadata: bool = True,
        include_citations: bool = True,
        use_graph_context: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute semantic search query with optional graph enhancement.
        
        Args:
            query: Natural language query
            source_types: Filter by source types (e.g., ['policy', 'decision'])
            top_k: Maximum results to return (default: 10)
            min_score: Minimum similarity score 0-1 (default: 0.4)
            role: User role for RBAC filtering (admin, executive, employee, guest)
            include_metadata: Include full metadata in results
            include_citations: Include citation snippets
            use_graph_context: Use graph enhancement if available (default: True)
        
        Returns:
            Structured response dictionary with results and metadata
        
        Example:
            >>> engine = VectorSearchEngine()
            >>> response = engine.search("What is our discount policy?", source_types=['policy'])
            >>> print(f"Found {response['metadata']['total_results']} results")
            >>> print(response['results'][0]['title'])
        """
        start_time = time.time()
        cache_hit = False
        graph_context_used = False
        
        # Log search started
        obs_logger.info(
            "Vector search started",
            query_length=len(query),
            top_k=top_k or 10,
            source_types=source_types,
            use_graph_context=use_graph_context
        )
        
        try:
            # Step 1: Process query
            logger.debug(f"Processing query: {query[:100]}...")
            processed = self.query_processor.process(
                query=query,
                source_types=source_types,
                top_k=top_k,
                min_score=min_score,
                role=role,
            )
            
            # Step 2: Generate query embedding (with caching)
            query_embedding = self._get_query_embedding(processed['query'])
            if self.cache and self.cache.get(processed['query']) is not None:
                cache_hit = True
            
            # NEW: Step 3: Try to get graph context
            graph_context = None
            candidate_ids = None
            
            if use_graph_context and self.graph_provider:
                try:
                    logger.debug("Discovering graph context...")
                    graph_context_start = time.time()
                    
                    # Get allowed scopes for RBAC
                    allowed_scopes = self.rbac_filter.get_allowed_scopes(processed['role'])
                    
                    # Discover graph context
                    graph_context = self.graph_provider.discover_context(
                        query=processed['query'],
                        allowed_scopes=allowed_scopes,
                        company_id=company_id,
                    )
                    
                    graph_context_time = (time.time() - graph_context_start) * 1000
                    logger.debug(f"Graph context discovery: {graph_context_time:.2f}ms")
                    
                    if graph_context['has_context']:
                        candidate_ids = graph_context['candidate_ids']
                        graph_context_used = True
                        logger.info(f"Graph context: {len(candidate_ids)} candidate documents")
                        logger.debug(f"Context: {graph_context['context_explanation']}")
                    else:
                        logger.debug("No graph context available, using pure vector search")
                        
                except Exception as e:
                    logger.warning(f"Graph context discovery failed: {e}")
                    logger.debug("Falling back to pure vector search")
            
            # Step 4: Execute vector search (constrained by graph context if available)
            # NEW: Detect person names for lexical boost strategy
            person_names = []
            sql_min_score = processed['min_score']  # Default: use configured min_score
            original_min_score = processed['min_score']  # Save original for post-boost filtering
            
            if self.graph_provider and hasattr(self.graph_provider, 'entity_extractor'):
                try:
                    entities = self.graph_provider.entity_extractor.extract(query)
                    person_names = [
                        e['text'] 
                        for e in entities 
                        if e.get('type') in ['PERSON', 'Executive'] or e.get('label') == 'PERSON'
                    ]
                    
                    if person_names:
                        # Lower SQL threshold to allow low-scoring results that will be boosted
                        sql_min_score = max(0.15, original_min_score - 0.20)  # e.g., 0.25 -> 0.15
                        logger.info(f"Person names detected: {person_names}")
                        logger.info(f"Lowering SQL min_score from {original_min_score:.2f} to {sql_min_score:.2f} for lexical boost")
                except Exception as e:
                    logger.debug(f"Entity extraction for boost strategy failed: {e}")
            
            logger.debug(f"Executing vector search (top_k={processed['top_k']}, "
                        f"min_score={sql_min_score}, "
                        f"constrained={candidate_ids is not None})")
            
            allowed_scopes = self.rbac_filter.get_allowed_scopes(processed['role'])
            search_results = self.vector_client.vector_search(
                query_embedding=query_embedding,
                source_types=processed['source_types'],
                candidate_ids=candidate_ids,  # NEW: Constrain to graph candidates
                top_k=processed['top_k'] * 2 if graph_context_used else processed['top_k'],  # Get more for reranking
                min_score=sql_min_score,  # NEW: Use lowered threshold if person names detected
                company_id=company_id,
                executive_id=executive_id,
                allowed_scopes=allowed_scopes,
            )
            
            if not search_results:
                logger.info("No results found")
                execution_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_success_response(
                    query=query,
                    results=[],
                    execution_time_ms=execution_time_ms,
                    top_k=processed['top_k'],
                    min_score=processed['min_score'],
                    source_types=processed['source_types'],
                    cache_hit=cache_hit,
                )
            
            # NEW: Step 4.5: Hybrid Lexical Boost for Person Names
            # Apply boost to results with exact person name matches
            if person_names:  # Already extracted earlier
                try:
                    logger.info(f"Applying lexical boost for person names: {person_names}")
                    
                    for result in search_results:
                        content = result.get('content', '').lower()
                        title = result.get('title', '').lower()
                        
                        # Check if any person name appears in content or title
                        for name in person_names:
                            name_lower = name.lower()
                            
                            # Exact match boost
                            if name_lower in content or name_lower in title:
                                original_score = result['similarity_score']
                                boost_factor = VECTOR_SEARCH_CONFIG.get('person_name_boost', 1.2)
                                
                                result['similarity_score'] = min(
                                    original_score * boost_factor, 
                                    1.0  # Cap at 1.0
                                )
                                result['lexical_boost_applied'] = True
                                result['boosted_for'] = name
                                
                                logger.debug(
                                    f"Boosted {result['source_id']}: "
                                    f"{original_score:.4f} → {result['similarity_score']:.4f} "
                                    f"(matched: {name})"
                                )
                                break  # Only boost once per result
                    
                    # Re-sort by updated scores
                    search_results.sort(key=lambda x: x['similarity_score'], reverse=True)
                    logger.debug("Results re-sorted after lexical boost")
                    
                    # Filter by original min_score after boosting
                    boosted_count = sum(1 for r in search_results if r.get('lexical_boost_applied'))
                    search_results = [r for r in search_results if r['similarity_score'] >= original_min_score]
                    logger.info(f"Applied boost to {boosted_count} results, {len(search_results)} pass final threshold {original_min_score:.2f}")
                
                except Exception as e:
                    logger.warning(f"Lexical boost failed: {e}")
                    # Continue without boost if it fails
            
            # NEW: Step 5: Hybrid scoring if graph context available
            if graph_context_used and graph_context:
                logger.debug("Calculating hybrid scores (60% vector + 40% graph)")
                
                # Calculate graph proximity scores
                document_ids = [r['source_id'] for r in search_results]
                graph_scores = self.graph_provider.calculate_graph_scores(
                    document_ids=document_ids,
                    anchor_entities=graph_context.get('entities', [])
                )
                
                # Combine vector and graph scores
                from graph_context.utils import combine_scores
                
                for result in search_results:
                    vector_score = result['similarity_score']
                    graph_score = graph_scores.get(result['source_id'], 0.0)
                    
                    result['graph_score'] = graph_score
                    result['hybrid_score'] = combine_scores(
                        vector_score=vector_score,
                        graph_score=graph_score,
                        vector_weight=0.6,
                        graph_weight=0.4
                    )
                
                # Sort by hybrid score
                search_results.sort(key=lambda x: x.get('hybrid_score', x['similarity_score']), reverse=True)
                
                # Trim to requested top_k
                search_results = search_results[:processed['top_k']]
            
            # Step 6: Retrieve metadata for results
            logger.debug(f"Retrieving metadata for {len(search_results)} results")
            source_items = [
                (result['source_id'], result['source_type'])
                for result in search_results
            ]
            metadata_dict = self.vector_client.batch_get_metadata(source_items)
            
            # Step 7: Process and enrich results
            logger.debug("Enriching results with metadata and citations")
            enriched_results = self.result_processor.process(
                search_results=search_results,
                metadata_dict=metadata_dict,
                include_metadata=include_metadata,
                include_citations=include_citations,
            )
            
            # NEW: Add graph context explanations if available
            if graph_context_used and graph_context:
                entities = graph_context.get('entities', [])
                if entities:
                    source_entity = entities[0].get('matched_name', entities[0].get('text', ''))
                    
                    for result in enriched_results:
                        try:
                            explanation = self.graph_provider.explain_relationship(
                                source_entity=source_entity,
                                target_document_id=result['source_id']
                            )
                            result['graph_context'] = explanation
                        except Exception as e:
                            logger.debug(f"Failed to explain relationship: {e}")
            
            # Step 8: Apply RBAC filtering
            logger.debug(f"Applying RBAC filter (role={processed['role']})")
            filtered_results = self.rbac_filter.filter_results(
                results=enriched_results,
                role=processed['role'],
            )
            
            # Step 9: Build response
            execution_time_ms = (time.time() - start_time) * 1000
            response = self.response_builder.build_success_response(
                query=query,
                results=filtered_results,
                execution_time_ms=execution_time_ms,
                top_k=processed['top_k'],
                min_score=processed['min_score'],
                source_types=processed['source_types'],
                cache_hit=cache_hit,
            )
            
            # Add graph context metadata
            if graph_context_used:
                response['metadata']['graph_enhanced'] = True
                response['metadata']['graph_context'] = {
                    'entities_found': len(graph_context.get('entities', [])),
                    'candidates_found': len(graph_context.get('candidate_ids', [])),
                    'explanation': graph_context.get('context_explanation', '')
                }
            else:
                response['metadata']['graph_enhanced'] = False
            
            logger.info(f"Search completed: {len(filtered_results)} results in {execution_time_ms:.2f}ms "
                       f"(graph_enhanced={graph_context_used})")
            
            # Track metrics
            vector_search_latency.observe(execution_time_ms / 1000)
            if len(filtered_results) > 0:
                retrieval_results_counter.labels(source='vector').observe(len(filtered_results))
            
            # Log completion
            obs_logger.info(
                "Vector search completed",
                latency_ms=execution_time_ms,
                results_count=len(filtered_results),
                cache_hit=cache_hit,
                graph_enhanced=graph_context_used
            )
            
            return response

        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            obs_logger.error(
                "Vector search failed",
                error=str(e),
                error_type=type(e).__name__
            )
            return self.response_builder.build_error_response(
                query=query,
                error_message=str(e),
                error_type=type(e).__name__,
            )

    @trace_function("vector_search", "search_sections")
    def search_sections(
        self,
        query: str,
        source_types: Optional[List[str]] = None,
        top_k: int = None,
        min_score: float = None,
        role: str = None,
        company_id: Optional[str] = None,
        executive_id: Optional[str] = None,
        candidate_doc_ids: Optional[List[str]] = None,
        group_by_document: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute semantic search at section level (NEW: semantic chunking).

        This method searches document sections instead of full documents,
        enabling higher precision retrieval by finding exact relevant sections.

        Args:
            query: Natural language query
            source_types: Filter by source types (e.g., ['policy', 'decision'])
            top_k: Maximum results to return (default: 10)
            min_score: Minimum similarity score 0-1 (default: 0.4)
            role: User role for RBAC filtering (admin, executive, employee, guest)
            candidate_doc_ids: Optional list of document IDs to constrain search (from graph)
            group_by_document: If True, group sections by parent document (default: True)

        Returns:
            Structured response dictionary with section results

        Example:
            >>> engine = VectorSearchEngine()
            >>> response = engine.search_sections("discount approval process", source_types=['policy'])
            >>> for result in response['results']:
            ...     print(f"Section: {result['section_title']}")
            ...     print(f"From: {result['parent_document_id']}")
        """
        start_time = time.time()
        cache_hit = False

        # Log search started
        obs_logger.info(
            "Section vector search started",
            query_length=len(query),
            top_k=top_k or 10,
            source_types=source_types,
            group_by_document=group_by_document
        )

        try:
            # Step 1: Process query
            logger.debug(f"Processing query for section search: {query[:100]}...")
            processed = self.query_processor.process(
                query=query,
                source_types=source_types,
                top_k=top_k,
                min_score=min_score,
                role=role,
            )

            # Step 2: Generate query embedding (with caching)
            query_embedding = self._get_query_embedding(processed['query'])
            if self.cache and self.cache.get(processed['query']) is not None:
                cache_hit = True

            # Step 3: Execute section vector search
            logger.debug(f"Executing section vector search (top_k={processed['top_k']}, "
                        f"min_score={processed['min_score']}, "
                        f"constrained={candidate_doc_ids is not None})")

            # Use the caller's original source_types (not processed) because
            # document_sections.parent_document_type uses different values
            # (e.g. 'presentation', 'meeting_notes') than the embeddings table.
            # Passing None skips the type filter so all sections are searched.
            section_results = self.vector_client.vector_search_sections(
                query_embedding=query_embedding,
                source_types=source_types,
                candidate_doc_ids=candidate_doc_ids,
                top_k=processed['top_k'],
                min_score=processed['min_score'],
                company_id=company_id,
                executive_id=executive_id,
            )

            if not section_results:
                logger.info("No section results found")
                execution_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_success_response(
                    query=query,
                    results=[],
                    execution_time_ms=execution_time_ms,
                    top_k=processed['top_k'],
                    min_score=processed['min_score'],
                    source_types=processed['source_types'],
                    cache_hit=cache_hit,
                )

            # Step 4: Process section results
            logger.debug(f"Processing {len(section_results)} section results")

            # Add source_id field for compatibility with result processor
            for result in section_results:
                result['source_id'] = result['section_id']
                result['source_type'] = result['parent_document_type']
                result['title'] = result['section_title']
                result['content'] = result['content']  # Already present

            # Step 5: Group sections by parent document if requested
            if group_by_document:
                logger.debug("Grouping sections by parent document")
                grouped = {}
                for result in section_results:
                    parent_id = result['parent_document_id']
                    if parent_id not in grouped:
                        grouped[parent_id] = {
                            'parent_document_id': parent_id,
                            'parent_document_type': result['parent_document_type'],
                            'sections': [],
                            'max_similarity_score': 0.0,
                            'section_count': 0
                        }

                    grouped[parent_id]['sections'].append(result)
                    grouped[parent_id]['max_similarity_score'] = max(
                        grouped[parent_id]['max_similarity_score'],
                        result['similarity_score']
                    )
                    grouped[parent_id]['section_count'] += 1

                # Sort documents by best section score
                grouped_results = sorted(
                    grouped.values(),
                    key=lambda x: x['max_similarity_score'],
                    reverse=True
                )

                logger.info(f"Grouped {len(section_results)} sections into {len(grouped_results)} documents")

                # Format for response
                final_results = []
                for doc in grouped_results:
                    # Sort sections within document by score
                    doc['sections'].sort(
                        key=lambda x: x['similarity_score'],
                        reverse=True
                    )

                    # Add to final results
                    final_results.append({
                        'parent_document_id': doc['parent_document_id'],
                        'parent_document_type': doc['parent_document_type'],
                        'max_similarity_score': doc['max_similarity_score'],
                        'section_count': doc['section_count'],
                        'sections': doc['sections'],
                        # For compatibility with response builder
                        'source_id': doc['parent_document_id'],
                        'source_type': doc['parent_document_type'],
                        'similarity_score': doc['max_similarity_score'],
                        'title': doc['sections'][0]['section_title'] if doc['sections'] else 'Unknown'
                    })
            else:
                # Return flat list of sections
                final_results = section_results

            # Step 6: Apply RBAC filtering
            filtered_results = self.rbac_filter.filter_results(
                results=final_results,
                role=processed['role'],
            )

            # Step 7: Section results already have all metadata from JOIN,
            # so we can skip the result processor and use them directly
            processed_results = filtered_results

            # Step 8: Build response
            execution_time_ms = (time.time() - start_time) * 1000

            response = self.response_builder.build_success_response(
                query=query,
                results=processed_results,
                execution_time_ms=execution_time_ms,
                top_k=processed['top_k'],
                min_score=processed['min_score'],
                source_types=processed['source_types'],
                cache_hit=cache_hit,
            )

            # Add section-specific metadata
            response['metadata']['search_type'] = 'section'
            response['metadata']['grouped_by_document'] = group_by_document
            if group_by_document:
                response['metadata']['total_sections'] = sum(
                    r.get('section_count', 0) for r in processed_results
                )
                response['metadata']['total_documents'] = len(processed_results)

            logger.info(f"Section search completed: {len(processed_results)} results "
                       f"in {execution_time_ms:.2f}ms")

            # Track metrics
            vector_search_latency.observe(execution_time_ms / 1000)
            if len(processed_results) > 0:
                retrieval_results_counter.labels(source='section').observe(len(processed_results))

            # Log completion
            obs_logger.info(
                "Section vector search completed",
                latency_ms=execution_time_ms,
                results_count=len(processed_results),
                cache_hit=cache_hit
            )

            return response

        except Exception as e:
            logger.error(f"Section search failed: {e}", exc_info=True)
            obs_logger.error(
                "Section vector search failed",
                error=str(e),
                error_type=type(e).__name__
            )
            return self.response_builder.build_error_response(
                query=query,
                error_message=str(e),
                error_type=type(e).__name__,
            )

    def search_by_type(
        self,
        query: str,
        source_type: str,
        top_k: int = 10,
        role: str = None,
        company_id: Optional[str] = None,
        executive_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Convenience method to search within a single source type.

        Args:
            query: Natural language query
            source_type: Single source type (policy, decision, executive)
            top_k: Maximum results
            role: User role
            company_id: Company ID for tenant isolation
            executive_id: Executive ID for tenant isolation

        Returns:
            Search results
        """
        return self.search(
            query=query,
            source_types=[source_type],
            top_k=top_k,
            role=role,
            company_id=company_id,
            executive_id=executive_id,
        )
    
    def find_similar(
        self,
        source_id: str,
        source_type: str,
        top_k: int = 5,
        exclude_self: bool = True,
        company_id: Optional[str] = None,
        executive_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Find similar documents to a given source.

        Args:
            source_id: ID of source document
            source_type: Type of source
            top_k: Number of similar documents to find
            exclude_self: Exclude the source document itself
            company_id: Company ID for tenant isolation
            executive_id: Executive ID for tenant isolation

        Returns:
            Search results with similar documents
        """
        # Get metadata for source document
        metadata = self.vector_client.get_source_metadata(source_id, source_type)
        if not metadata:
            return self.response_builder.build_error_response(
                query=f"find_similar:{source_id}",
                error_message=f"Source document not found: {source_id}",
                error_type="NotFoundError",
            )

        # Extract text content from metadata
        content = self._extract_content(metadata, source_type)

        # Search using the content
        results = self.search(
            query=content,
            top_k=top_k + 1 if exclude_self else top_k,  # +1 to account for self
            min_score=0.3,  # Lower threshold for similarity search
            company_id=company_id,
            executive_id=executive_id,
        )
        
        # Remove self if requested
        if exclude_self and results['success']:
            results['results'] = [
                r for r in results['results']
                if r['source_id'] != source_id
            ][:top_k]
            results['metadata']['total_results'] = len(results['results'])
        
        return results
    
    def batch_search(
        self,
        queries: List[str],
        source_types: Optional[List[str]] = None,
        top_k: int = 10,
        role: str = None,
        company_id: Optional[str] = None,
        executive_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute multiple searches efficiently.

        Args:
            queries: List of query strings
            source_types: Filter by source types
            top_k: Maximum results per query
            role: User role
            company_id: Company ID for tenant isolation
            executive_id: Executive ID for tenant isolation

        Returns:
            Batch response with results for each query
        """
        if len(queries) > VECTOR_SEARCH_CONFIG['batch_size']:
            return self.response_builder.build_error_response(
                query="batch_search",
                error_message=f"Too many queries ({len(queries)}). Maximum is {VECTOR_SEARCH_CONFIG['batch_size']}.",
                error_type="BatchSizeError",
            )
        
        start_time = time.time()
        results_list = []
        execution_times = []
        
        for query in queries:
            query_start = time.time()
            result = self.search(
                query=query,
                source_types=source_types,
                top_k=top_k,
                role=role,
                company_id=company_id,
                executive_id=executive_id,
            )
            query_time = (time.time() - query_start) * 1000
            
            results_list.append(result.get('results', []))
            execution_times.append(query_time)
        
        total_time = (time.time() - start_time) * 1000
        
        return self.response_builder.build_batch_response(
            queries=queries,
            results_list=results_list,
            execution_times_ms=execution_times,
            total_time_ms=total_time,
        )
    
    def _get_query_embedding(self, query: str) -> np.ndarray:
        """
        Get query embedding with caching.
        
        Args:
            query: Query text
        
        Returns:
            Query embedding vector
        """
        # Try cache first
        if self.cache:
            cached_embedding = self.cache.get(query)
            if cached_embedding is not None:
                logger.debug("Using cached embedding")
                return cached_embedding
        
        # Generate new embedding using service or fallback
        logger.debug("Generating new embedding")
        try:
            # Try embedding service first
            embedding = self.embedding_client.generate_embedding(
                text=query,
                source_id=f"query_{int(time.time())}",
                source_type="query"
            )
            logger.debug("Used embedding service for query")
        except Exception as e:
            logger.warning(f"Embedding service failed, using fallback: {e}")
            # Fallback to local model
            embedding = self.embedding_model.generate_embedding(query)
        
        # Store in cache
        if self.cache:
            self.cache.set(query, embedding)
        
        return embedding
    
    def _extract_content(self, metadata: Dict[str, Any], source_type: str) -> str:
        """
        Extract text content from metadata for similarity search.
        
        Args:
            metadata: Source metadata
            source_type: Type of source
        
        Returns:
            Extracted text content
        """
        if source_type == 'decision_case':
            parts = [
                metadata.get('title', ''),
                metadata.get('situation', ''),
                metadata.get('decision_made', ''),
            ]
        elif source_type == 'policy':
            parts = [
                metadata.get('name', ''),
                metadata.get('content_markdown', '')[:500],  # First 500 chars
            ]
        elif source_type == 'executive_profile':
            parts = [
                metadata.get('name', ''),
                metadata.get('title', ''),
            ]
            # Extract from profile_data JSON if available
            profile_data = metadata.get('profile_data')
            if profile_data:
                import json
                try:
                    if isinstance(profile_data, str):
                        profile = json.loads(profile_data)
                    else:
                        profile = profile_data
                    if 'background_summary' in profile:
                        parts.append(profile['background_summary'])
                except:
                    pass
        else:
            parts = []
        
        return ' '.join(filter(None, parts))
    
    def clear_cache(self):
        """Clear the embedding cache."""
        if self.cache:
            self.cache.clear()
            logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get search engine statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            'model_name': self.model_name,
            'embedding_dimension': self.embedding_model.embedding_dimension,
            'device': self.embedding_model.device,
        }
        
        # Cache stats
        if self.cache:
            stats['cache'] = self.cache.get_stats()
        
        # GPU stats
        gpu_info = self.embedding_model.get_gpu_info()
        if gpu_info.get('available'):
            stats['gpu'] = gpu_info
        
        return stats
    
    def close(self):
        """Clean up resources."""
        if self.vector_client:
            self.vector_client.close()
        logger.info("VectorSearchEngine closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __repr__(self):
        return f"VectorSearchEngine(model={self.model_name}, cache_enabled={self.cache is not None})"
