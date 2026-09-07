"""
Prometheus Metrics
==================

Provides Prometheus metrics for monitoring system performance.

Key Metrics:
- Request counters and histograms
- LLM token usage and costs
- Component latencies
- Cache hit rates
- Error rates
- Quality metrics

Usage:
    from observability.metrics import (
        request_counter,
        request_latency,
        llm_tokens_counter,
        track_request
    )
    
    # Track request
    request_counter.labels(endpoint="/api/v1/chat", method="POST").inc()
    request_latency.labels(endpoint="/api/v1/chat").observe(1.234)
"""

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from typing import Optional
import time
from contextlib import contextmanager

from .config import METRICS_PREFIX, PROMETHEUS_ENABLED

# Create custom registry (to avoid conflicts)
registry = CollectorRegistry()

# ============================================================
# API REQUEST METRICS
# ============================================================

# Request counter
request_counter = Counter(
    f'{METRICS_PREFIX}_http_requests_total',
    'Total HTTP requests',
    ['endpoint', 'method', 'status'],
    registry=registry
)

# Request latency histogram
request_latency = Histogram(
    f'{METRICS_PREFIX}_http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['endpoint', 'path'],  # path = fast/standard/agentic
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0),
    registry=registry
)

# Active requests gauge
active_requests = Gauge(
    f'{METRICS_PREFIX}_active_requests',
    'Number of active requests',
    registry=registry
)

# ============================================================
# LLM METRICS
# ============================================================

# LLM request counter
llm_requests_counter = Counter(
    f'{METRICS_PREFIX}_llm_requests_total',
    'Total LLM requests',
    ['model', 'path', 'status'],  # status = success/error
    registry=registry
)

# LLM token usage counter
llm_tokens_counter = Counter(
    f'{METRICS_PREFIX}_llm_tokens_used_total',
    'Total LLM tokens used',
    ['model', 'token_type'],  # token_type = prompt/completion
    registry=registry
)

# LLM cost counter
llm_cost_counter = Counter(
    f'{METRICS_PREFIX}_llm_cost_usd_total',
    'Total LLM cost in USD',
    ['model', 'path'],
    registry=registry
)

# LLM latency histogram
llm_latency = Histogram(
    f'{METRICS_PREFIX}_llm_latency_seconds',
    'LLM API latency in seconds',
    ['model'],
    buckets=(0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0, 15.0, 20.0),
    registry=registry
)

# ============================================================
# ORCHESTRATOR METRICS
# ============================================================

# Routing decisions counter
routing_decisions_counter = Counter(
    f'{METRICS_PREFIX}_routing_decisions_total',
    'Total routing decisions made',
    ['path', 'forced'],  # forced = true/false
    registry=registry
)

# Handler cache hits counter
handler_cache_hits_counter = Counter(
    f'{METRICS_PREFIX}_handler_cache_hits_total',
    'Total handler cache hits',
    ['path'],
    registry=registry
)

# ============================================================
# RETRIEVAL METRICS
# ============================================================

# Retrieval strategy counter
retrieval_strategy_counter = Counter(
    f'{METRICS_PREFIX}_retrieval_strategy_total',
    'Total retrieval requests by strategy',
    ['strategy'],  # strategy = vector_only/vector_graph/full_hybrid
    registry=registry
)

# Retrieval request counter (legacy, keeping for compatibility)
retrieval_requests_counter = Counter(
    f'{METRICS_PREFIX}_retrieval_requests_total',
    'Total retrieval requests',
    ['strategy'],  # strategy = vector_only/vector_graph/full_hybrid
    registry=registry
)

# Retrieval latency histogram
retrieval_latency = Histogram(
    f'{METRICS_PREFIX}_retrieval_latency_seconds',
    'Retrieval latency in seconds',
    ['component'],  # component = vector/graph/memory/fusion/reranking
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0),
    registry=registry
)

# Retrieval results counter
retrieval_results_counter = Histogram(
    f'{METRICS_PREFIX}_retrieval_results_count',
    'Number of results retrieved',
    ['source'],  # source = vector/graph/memory
    buckets=(1, 3, 5, 10, 15, 20, 30, 50),
    registry=registry
)

# Vector search latency
vector_search_latency = Histogram(
    f'{METRICS_PREFIX}_vector_search_seconds',
    'Vector search latency in seconds',
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
    registry=registry
)

# Graph query latency
graph_query_latency = Histogram(
    f'{METRICS_PREFIX}_graph_query_seconds',
    'Graph query latency in seconds',
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
    registry=registry
)

# Memory search latency
memory_search_latency = Histogram(
    f'{METRICS_PREFIX}_memory_search_seconds',
    'Memory search latency in seconds',
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=registry
)

# Fusion/reranking latency
fusion_latency = Histogram(
    f'{METRICS_PREFIX}_fusion_seconds',
    'Fusion/reranking latency in seconds',
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
    registry=registry
)

# ============================================================
# CACHE METRICS
# ============================================================

# Cache operations counter
cache_operations_counter = Counter(
    f'{METRICS_PREFIX}_cache_operations_total',
    'Total cache operations',
    ['cache_type', 'operation', 'result'],  # result = hit/miss
    registry=registry
)

# Cache hit rate gauge
cache_hit_rate = Gauge(
    f'{METRICS_PREFIX}_cache_hit_rate',
    'Cache hit rate (0-1)',
    ['cache_type'],
    registry=registry
)

# Cache memory usage gauge
cache_memory_bytes = Gauge(
    f'{METRICS_PREFIX}_cache_memory_bytes',
    'Cache memory usage in bytes',
    ['cache_type'],
    registry=registry
)

# ============================================================
# QUALITY METRICS
# ============================================================

# Decision fidelity histogram
decision_fidelity_score = Histogram(
    f'{METRICS_PREFIX}_decision_fidelity_score',
    'Decision fidelity score (0-1)',
    ['executive_id'],
    buckets=(0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0),
    registry=registry
)

# Citation coverage gauge
citation_coverage = Gauge(
    f'{METRICS_PREFIX}_citation_coverage_percentage',
    'Citation coverage percentage',
    ['executive_id'],
    registry=registry
)

# Factual grounding rate gauge
factual_grounding_rate = Gauge(
    f'{METRICS_PREFIX}_factual_grounding_rate',
    'Factual grounding rate (0-100)',
    ['executive_id'],
    registry=registry
)

# User feedback counter
user_feedback_counter = Counter(
    f'{METRICS_PREFIX}_user_feedback_total',
    'Total user feedback events',
    ['type'],  # type = thumbs_up/thumbs_down
    registry=registry
)

# ============================================================
# BUSINESS METRICS
# ============================================================

# Daily Active Users (DAU)
daily_active_users = Gauge(
    f'{METRICS_PREFIX}_daily_active_users',
    'Daily active users count',
    registry=registry
)

# Monthly Active Users (MAU)
monthly_active_users = Gauge(
    f'{METRICS_PREFIX}_monthly_active_users',
    'Monthly active users count',
    registry=registry
)

# User retention rate (7-day)
user_retention_rate = Gauge(
    f'{METRICS_PREFIX}_user_retention_rate',
    '7-day user retention rate (0-100)',
    registry=registry
)

# User satisfaction rate
user_satisfaction_rate = Gauge(
    f'{METRICS_PREFIX}_user_satisfaction_rate',
    'User satisfaction rate based on feedback (0-100)',
    registry=registry
)

# Queries per user per day
queries_per_user = Histogram(
    f'{METRICS_PREFIX}_queries_per_user',
    'Queries per user per day',
    buckets=(1, 2, 3, 5, 10, 15, 20, 30, 50),
    registry=registry
)

# ============================================================
# SYSTEM METRICS
# ============================================================

# Error counter
error_counter = Counter(
    f'{METRICS_PREFIX}_errors_total',
    'Total errors',
    ['component', 'error_type'],
    registry=registry
)

# Component health gauge
component_health = Gauge(
    f'{METRICS_PREFIX}_component_health',
    'Component health status (1=healthy, 0=unhealthy)',
    ['component'],
    registry=registry
)

# Memory usage gauge
memory_usage_bytes = Gauge(
    f'{METRICS_PREFIX}_memory_usage_bytes',
    'Memory usage in bytes',
    registry=registry
)

# CPU usage gauge
cpu_usage_percentage = Gauge(
    f'{METRICS_PREFIX}_cpu_usage_percentage',
    'CPU usage percentage',
    registry=registry
)

# ============================================================
# HELPER FUNCTIONS
# ============================================================

@contextmanager
def track_request(endpoint: str, path: Optional[str] = None):
    """
    Context manager to track request metrics.
    
    Args:
        endpoint: API endpoint
        path: Query path (fast/standard/agentic)
        
    Usage:
        with track_request("/api/v1/chat", "standard"):
            # Process request
            pass
    """
    if not PROMETHEUS_ENABLED:
        yield
        return
    
    active_requests.inc()
    start_time = time.time()
    
    try:
        yield
    finally:
        duration = time.time() - start_time
        request_latency.labels(endpoint=endpoint, path=path or "unknown").observe(duration)
        active_requests.dec()


@contextmanager
def track_llm_request(model: str, path: str):
    """
    Context manager to track LLM request metrics.
    
    Args:
        model: LLM model name
        path: Query path
        
    Usage:
        with track_llm_request("gpt-4o", "standard") as tracker:
            # Call LLM
            tracker.record_success(prompt_tokens=450, completion_tokens=320, cost=0.023)
    """
    if not PROMETHEUS_ENABLED:
        yield None
        return
    
    start_time = time.time()
    
    class LLMTracker:
        def __init__(self, model: str, path: str):
            self.model = model
            self.path = path
        
        def record_success(self, prompt_tokens: int, completion_tokens: int, cost: float):
            """Record successful LLM call"""
            llm_requests_counter.labels(model=self.model, path=self.path, status="success").inc()
            llm_tokens_counter.labels(model=self.model, token_type="prompt").inc(prompt_tokens)
            llm_tokens_counter.labels(model=self.model, token_type="completion").inc(completion_tokens)
            llm_cost_counter.labels(model=self.model, path=self.path).inc(cost)
            
            duration = time.time() - start_time
            llm_latency.labels(model=self.model).observe(duration)
        
        def record_error(self):
            """Record failed LLM call"""
            llm_requests_counter.labels(model=self.model, path=self.path, status="error").inc()
            
            duration = time.time() - start_time
            llm_latency.labels(model=self.model).observe(duration)
    
    tracker = LLMTracker(model, path)
    try:
        yield tracker
    except Exception:
        tracker.record_error()
        raise


def get_metrics() -> bytes:
    """
    Get current metrics in Prometheus format.
    
    Returns:
        Metrics in Prometheus text format
        
    Usage in FastAPI:
        @app.get("/metrics")
        async def metrics():
            return Response(content=get_metrics(), media_type=CONTENT_TYPE_LATEST)
    """
    return generate_latest(registry)


def update_system_metrics():
    """
    Update system resource metrics (CPU, memory).
    
    Should be called periodically (e.g., every 60 seconds).
    """
    if not PROMETHEUS_ENABLED:
        return
    
    try:
        import psutil
        
        # Memory usage
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_usage_bytes.set(memory_info.rss)
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_usage_percentage.set(cpu_percent)
        
    except ImportError:
        # psutil not installed, skip system metrics
        pass
    except Exception as e:
        # Error getting system metrics, log and skip
        import logging
        logging.getLogger(__name__).warning(f"Failed to update system metrics: {e}")
