"""
FastAPI Middleware
==================

Provides middleware for automatic instrumentation of FastAPI application.

Features:
- Automatic request_id generation and injection
- Request/response logging
- Latency tracking
- Error tracking
- Context management

Usage:
    from fastapi import FastAPI
    from observability.middleware import ObservabilityMiddleware
    
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)
"""

import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .context import RequestContext
from .logging import StructuredLogger
from .metrics import (
    request_counter,
    request_latency,
    active_requests,
    error_counter,
)

logger = StructuredLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic observability instrumentation.
    
    Handles:
    - Request ID generation and injection
    - Request context setup/cleanup
    - Request/response logging
    - Latency metrics
    - Error tracking
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process request with observability instrumentation.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler
            
        Returns:
            HTTP response
        """
        # Generate request ID
        request_id = RequestContext.generate_request_id()
        
        # Set up request context
        RequestContext.set('request_id', request_id)
        RequestContext.set('method', request.method)
        RequestContext.set('path', request.url.path)
        
        # Extract user info from headers (if available)
        user_id = request.headers.get('X-User-ID')
        if user_id:
            RequestContext.set('user_id', user_id)
        
        # Increment active requests
        active_requests.inc()
        
        # Start timing
        start_time = time.time()
        
        # Log request
        logger.info(
            "Request received",
            method=request.method,
            path=request.url.path,
            user_agent=request.headers.get('user-agent'),
            client_ip=request.client.host if request.client else None
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate latency
            latency = time.time() - start_time
            
            # Get query path if available (set by endpoint)
            query_path = RequestContext.get('query_path', 'unknown')
            
            # Update metrics
            request_counter.labels(
                endpoint=request.url.path,
                method=request.method,
                status=response.status_code
            ).inc()
            
            request_latency.labels(
                endpoint=request.url.path,
                path=query_path
            ).observe(latency)
            
            # Add request ID to response headers
            response.headers['X-Request-ID'] = request_id
            
            # Log response
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=latency * 1000
            )
            
            return response
            
        except Exception as e:
            # Calculate latency
            latency = time.time() - start_time
            
            # Track error
            error_counter.labels(
                component="api",
                error_type=type(e).__name__
            ).inc()
            
            # Log error
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                latency_ms=latency * 1000,
                error=e
            )
            
            raise
            
        finally:
            # Decrement active requests
            active_requests.dec()
            
            # Clean up context
            RequestContext.clear()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Lightweight middleware for request/response logging only.
    
    Use this instead of ObservabilityMiddleware if you only need logging.
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process request with logging only"""
        request_id = RequestContext.generate_request_id()
        RequestContext.set('request_id', request_id)
        
        start_time = time.time()
        
        logger.info(
            "Request received",
            method=request.method,
            path=request.url.path
        )
        
        try:
            response = await call_next(request)
            
            latency = time.time() - start_time
            
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=latency * 1000
            )
            
            response.headers['X-Request-ID'] = request_id
            return response
            
        except Exception as e:
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=e
            )
            raise
            
        finally:
            RequestContext.clear()
