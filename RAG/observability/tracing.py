"""
Distributed Tracing with OpenTelemetry
=======================================

Provides distributed tracing functionality using OpenTelemetry.

Key Features:
- Automatic span creation and management
- Request correlation across components
- OTLP export to collector
- Sampling support
- Attribute injection

Usage:
    from observability.tracing import setup_tracing, get_tracer
    
    # Initialize at startup
    setup_tracing()
    
    # In component
    tracer = get_tracer(__name__)
    
    with tracer.start_as_current_span("operation_name") as span:
        span.set_attribute("key", "value")
        # Do work
"""

import logging
from typing import Optional
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from .config import (
    OTEL_ENABLED,
    SERVICE_NAME as SVC_NAME,
    SERVICE_VERSION as SVC_VERSION,
    OTEL_EXPORTER_OTLP_ENDPOINT,
    TRACE_SAMPLING_RATE,
    TRACE_BATCH_SIZE,
    get_otlp_headers,
)

logger = logging.getLogger(__name__)

# Global tracer provider
_tracer_provider: Optional[TracerProvider] = None


def setup_tracing() -> None:
    """
    Initialize OpenTelemetry tracing.
    
    Sets up:
    - TracerProvider with service resource
    - OTLP exporter to collector
    - Batch span processor
    - Sampling based on config
    
    Should be called once at application startup.
    """
    global _tracer_provider
    
    if not OTEL_ENABLED:
        logger.info("OpenTelemetry tracing disabled (OTEL_ENABLED=false)")
        return
    
    try:
        # Create resource with service information
        resource = Resource(attributes={
            SERVICE_NAME: SVC_NAME,
            SERVICE_VERSION: SVC_VERSION,
        })
        
        # Create sampler
        sampler = TraceIdRatioBased(TRACE_SAMPLING_RATE)
        
        # Create tracer provider
        _tracer_provider = TracerProvider(
            resource=resource,
            sampler=sampler
        )
        
        # Create OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
            headers=get_otlp_headers()
        )
        
        # Create batch span processor
        span_processor = BatchSpanProcessor(
            otlp_exporter,
            max_queue_size=2048,
            max_export_batch_size=TRACE_BATCH_SIZE
        )
        
        # Add span processor to provider
        _tracer_provider.add_span_processor(span_processor)
        
        # Set as global tracer provider
        trace.set_tracer_provider(_tracer_provider)
        
        logger.info(
            "OpenTelemetry tracing initialized",
            extra={
                'service_name': SVC_NAME,
                'endpoint': OTEL_EXPORTER_OTLP_ENDPOINT,
                'sampling_rate': TRACE_SAMPLING_RATE
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry tracing: {e}")
        raise


def get_tracer(name: str) -> trace.Tracer:
    """
    Get a tracer instance.
    
    Args:
        name: Tracer name (usually __name__ of module)
        
    Returns:
        OpenTelemetry Tracer instance
        
    Example:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("my_operation") as span:
            span.set_attribute("foo", "bar")
    """
    return trace.get_tracer(name)


def shutdown_tracing() -> None:
    """
    Shutdown tracing and flush remaining spans.
    
    Should be called at application shutdown.
    """
    global _tracer_provider
    
    if _tracer_provider:
        try:
            _tracer_provider.shutdown()
            logger.info("OpenTelemetry tracing shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down tracing: {e}")


def add_span_attributes(span: trace.Span, **kwargs) -> None:
    """
    Add multiple attributes to a span.
    
    Args:
        span: OpenTelemetry span
        **kwargs: Attributes to add (key=value)
        
    Example:
        add_span_attributes(span, user_id="123", query_type="simple")
    """
    for key, value in kwargs.items():
        if value is not None:
            span.set_attribute(key, value)


def record_exception_in_span(span: trace.Span, exception: Exception) -> None:
    """
    Record an exception in a span.
    
    Args:
        span: OpenTelemetry span
        exception: Exception to record
        
    Example:
        try:
            do_something()
        except Exception as e:
            record_exception_in_span(span, e)
            raise
    """
    span.record_exception(exception)
    span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))
