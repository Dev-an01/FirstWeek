"""
Observability Module
====================

Provides comprehensive monitoring, logging, and tracing for AI Officer RAG system.

Components:
- context: Request context management (request_id propagation)
- logging: Structured JSON logging
- metrics: Prometheus metrics collectors
- tracing: OpenTelemetry distributed tracing
- decorators: Instrumentation decorators
- cost_tracker: LLM cost tracking
- quality_evaluator: Response quality metrics
- middleware: FastAPI middleware for auto-instrumentation

Usage:
    from observability import RequestContext, StructuredLogger, trace_function
    
    logger = StructuredLogger(__name__)
    
    @trace_function("my_component", "my_operation")
    def my_function():
        request_id = RequestContext.get_request_id()
        logger.info("Processing request", foo="bar")
"""

__version__ = "1.0.0"

# Core imports for easy access
from .context import RequestContext
from .logging import StructuredLogger, setup_logging
from .decorators import trace_function, track_performance
from .cost_tracker import CostTracker

__all__ = [
    "RequestContext",
    "StructuredLogger",
    "setup_logging",
    "trace_function",
    "track_performance",
    "CostTracker",
]
