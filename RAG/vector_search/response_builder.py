"""
Response Builder

Formats search results into structured JSON responses.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger('vector_search.response_builder')


class ResponseBuilder:
    """
    Builds structured JSON responses from processed results.
    
    Response format:
    {
        "success": true,
        "query": "...",
        "results": [...],
        "metadata": {
            "total_results": 5,
            "top_k": 10,
            "min_score": 0.4,
            "execution_time_ms": 123.45,
            ...
        }
    }
    """
    
    def __init__(self):
        """Initialize response builder."""
        logger.info("ResponseBuilder initialized")
    
    def build_success_response(
        self,
        query: str,
        results: List[Dict[str, Any]],
        execution_time_ms: float,
        top_k: int,
        min_score: float,
        source_types: List[str],
        cache_hit: bool = False,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build a successful search response.
        
        Args:
            query: Original query text
            results: Processed search results
            execution_time_ms: Total execution time
            top_k: Maximum results requested
            min_score: Minimum score threshold
            source_types: Source types searched
            cache_hit: Whether result came from cache
            additional_metadata: Optional extra metadata
        
        Returns:
            Structured response dictionary
        """
        response = {
            'success': True,
            'query': query,
            'results': results,
            'metadata': {
                'total_results': len(results),
                'top_k': top_k,
                'min_score': min_score,
                'source_types': source_types,
                'execution_time_ms': round(execution_time_ms, 2),
                'cache_hit': cache_hit,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
            }
        }
        
        # Add additional metadata if provided
        if additional_metadata:
            response['metadata'].update(additional_metadata)
        
        logger.debug(f"Built success response with {len(results)} results")
        return response
    
    def build_error_response(
        self,
        query: str,
        error_message: str,
        error_type: str = 'SearchError',
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build an error response.
        
        Args:
            query: Original query text
            error_message: Error description
            error_type: Type of error
            additional_info: Optional additional error information
        
        Returns:
            Error response dictionary
        """
        response = {
            'success': False,
            'query': query,
            'error': {
                'type': error_type,
                'message': error_message,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
            }
        }
        
        if additional_info:
            response['error'].update(additional_info)
        
        logger.warning(f"Built error response: {error_type} - {error_message}")
        return response
    
    def build_batch_response(
        self,
        queries: List[str],
        results_list: List[List[Dict[str, Any]]],
        execution_times_ms: List[float],
        total_time_ms: float,
    ) -> Dict[str, Any]:
        """
        Build a batch search response.
        
        Args:
            queries: List of queries
            results_list: List of result lists (one per query)
            execution_times_ms: Execution time for each query
            total_time_ms: Total batch execution time
        
        Returns:
            Batch response dictionary
        """
        batch_results = []
        
        for query, results, exec_time in zip(queries, results_list, execution_times_ms):
            batch_results.append({
                'query': query,
                'results': results,
                'execution_time_ms': round(exec_time, 2),
                'total_results': len(results),
            })
        
        response = {
            'success': True,
            'batch_size': len(queries),
            'results': batch_results,
            'metadata': {
                'total_execution_time_ms': round(total_time_ms, 2),
                'average_time_ms': round(total_time_ms / len(queries) if queries else 0, 2),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
            }
        }
        
        logger.debug(f"Built batch response for {len(queries)} queries")
        return response
    
    def format_result_summary(self, results: List[Dict[str, Any]]) -> str:
        """
        Create a text summary of results.
        
        Args:
            results: Processed results
        
        Returns:
            Human-readable summary
        """
        if not results:
            return "No results found."
        
        lines = [f"Found {len(results)} results:\n"]
        
        for result in results:
            rank = result.get('rank', '?')
            title = result.get('title', 'Unknown')
            score = result.get('similarity_score', 0.0)
            source_type = result.get('source_type', 'unknown')
            
            lines.append(f"{rank}. [{source_type}] {title} (score: {score:.3f})")
        
        return '\n'.join(lines)
    
    def format_result_table(self, results: List[Dict[str, Any]]) -> str:
        """
        Create a formatted table of results.
        
        Args:
            results: Processed results
        
        Returns:
            ASCII table string
        """
        if not results:
            return "No results found."
        
        # Table header
        header = f"{'Rank':<6} {'Score':<8} {'Type':<18} {'Title':<50}"
        separator = '-' * 82
        
        lines = [header, separator]
        
        for result in results:
            rank = str(result.get('rank', '?'))
            score = f"{result.get('similarity_score', 0.0):.4f}"
            source_type = result.get('source_type', 'unknown')
            title = result.get('title', 'Unknown')
            
            # Truncate title if too long
            if len(title) > 47:
                title = title[:44] + '...'
            
            line = f"{rank:<6} {score:<8} {source_type:<18} {title:<50}"
            lines.append(line)
        
        return '\n'.join(lines)
