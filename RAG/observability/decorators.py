"""
Instrumentation Decorators
===========================

Provides decorators for easy component instrumentation.

Key Decorators:
- @trace_function: Add distributed tracing
- @track_performance: Track latency metrics
- @track_errors: Track error rates

Usage:
    from observability.decorators import trace_function, track_performance
    
    @trace_function("my_component", "my_operation")
    @track_performance("my_component")
    def my_function(arg1, arg2):
        # Do work
        return result
"""

import time
import functools
from typing import Callable, Optional
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from .context import RequestContext
from .logging import StructuredLogger
from .metrics import retrieval_latency, error_counter

# Get tracer
tracer = trace.get_tracer(__name__)


def trace_function(component: str, operation: str):
    """
    Decorator to add distributed tracing to a function.
    
    Creates a span for the function execution with automatic error handling
    and attribute injection.
    
    Args:
        component: Component name (e.g., "llm_orchestrator")
        operation: Operation name (e.g., "generate_response")
        
    Example:
        @trace_function("vector_search", "search")
        def search(query: str, top_k: int):
            # Function code
            pass
    """
    def decorator(func: Callable):
        logger = StructuredLogger(component)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request_id = RequestContext.get_request_id()
            
            # Start span
            with tracer.start_as_current_span(
                f"{component}.{operation}",
                attributes={
                    "request_id": request_id,
                    "component": component,
                    "operation": operation,
                    "user_id": RequestContext.get_user_id(),
                    "executive_id": RequestContext.get_executive_id(),
                }
            ) as span:
                start_time = time.time()
                
                try:
                    # Log start
                    logger.info(
                        f"{operation} started",
                        operation=operation
                    )
                    
                    # Execute function
                    result = func(*args, **kwargs)
                    
                    # Calculate latency
                    latency_ms = (time.time() - start_time) * 1000
                    
                    # Log success
                    logger.info(
                        f"{operation} completed",
                        operation=operation,
                        latency_ms=latency_ms
                    )
                    
                    # Add span attributes
                    span.set_attribute("latency_ms", latency_ms)
                    span.set_attribute("success", True)
                    span.set_status(Status(StatusCode.OK))
                    
                    return result
                    
                except Exception as e:
                    # Calculate latency
                    latency_ms = (time.time() - start_time) * 1000
                    
                    # Log error
                    logger.error(
                        f"{operation} failed",
                        operation=operation,
                        latency_ms=latency_ms,
                        error=e
                    )
                    
                    # Add span attributes
                    span.set_attribute("latency_ms", latency_ms)
                    span.set_attribute("success", False)
                    span.set_attribute("error", str(e))
                    span.set_attribute("error_type", type(e).__name__)
                    
                    # Record exception in span
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR), str(e))
                    
                    # Track error metric
                    error_counter.labels(
                        component=component,
                        error_type=type(e).__name__
                    ).inc()
                    
                    raise
        
        return wrapper
    return decorator


def track_performance(component: str, metric_name: Optional[str] = None):
    """
    Decorator to track function performance metrics.
    
    Records latency in Prometheus histogram.
    
    Args:
        component: Component name for metric label
        metric_name: Optional custom metric name
        
    Example:
        @track_performance("vector_search")
        def search(query: str):
            # Function code
            pass
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Record latency
                duration = time.time() - start_time
                retrieval_latency.labels(component=component).observe(duration)
                
                return result
                
            except Exception:
                # Still record latency on error
                duration = time.time() - start_time
                retrieval_latency.labels(component=component).observe(duration)
                raise
        
        return wrapper
    return decorator


def track_errors(component: str):
    """
    Decorator to track error rates.
    
    Increments error counter when function raises exception.
    
    Args:
        component: Component name for metric label
        
    Example:
        @track_errors("llm_client")
        def call_llm(prompt: str):
            # Function code that might fail
            pass
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Track error
                error_counter.labels(
                    component=component,
                    error_type=type(e).__name__
                ).inc()
                raise
        
        return wrapper
    return decorator


def log_execution(component: str, level: str = "INFO"):
    """
    Decorator to log function execution.
    
    Logs function entry and exit with timing.
    
    Args:
        component: Component name for logger
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        
    Example:
        @log_execution("query_router")
        def route_query(query: str):
            # Function code
            pass
    """
    def decorator(func: Callable):
        logger = StructuredLogger(component)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Log entry
            logger.info(f"Entering {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                
                # Log exit
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Exiting {func.__name__}",
                    duration_ms=duration_ms
                )
                
                return result
                
            except Exception as e:
                # Log error
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Error in {func.__name__}",
                    error=e,
                    duration_ms=duration_ms
                )
                raise
        
        return wrapper
    return decorator


def inject_context(**context_kwargs):
    """
    Decorator to inject context values before function execution.
    
    Args:
        **context_kwargs: Key-value pairs to inject into context
        
    Example:
        @inject_context(component="retrieval")
        def retrieve(query: str):
            # RequestContext now has 'component' set
            pass
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Inject context
            RequestContext.update(context_kwargs)
            
            try:
                return func(*args, **kwargs)
            finally:
                # Clean up injected context
                for key in context_kwargs:
                    RequestContext.remove(key)
        
        return wrapper
    return decorator


def retry_with_logging(
    component: str,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0
):
    """
    Decorator to retry function with exponential backoff and logging.
    
    Args:
        component: Component name for logging
        max_retries: Maximum number of retries
        delay: Initial delay between retries (seconds)
        backoff: Backoff multiplier
        
    Example:
        @retry_with_logging("llm_client", max_retries=3)
        def call_api():
            # API call that might fail
            pass
    """
    def decorator(func: Callable):
        logger = StructuredLogger(component)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries",
                            error=e,
                            attempts=attempt + 1
                        )
                        raise
                    
                    logger.warning(
                        f"{func.__name__} failed, retrying",
                        error=e,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=current_delay
                    )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
        
        return wrapper
    return decorator
