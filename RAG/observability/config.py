"""
Observability Configuration
============================

Central configuration for all observability components.
"""

import os
from typing import Optional

# ============================================================
# GENERAL SETTINGS
# ============================================================

# Environment (dev/staging/prod)
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

# Service name for tracing/metrics
SERVICE_NAME = os.getenv("SERVICE_NAME", "ai-officer-rag")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")

# ============================================================
# LOGGING SETTINGS
# ============================================================

# Log level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Log file path
LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")

# JSON format
LOG_JSON_FORMAT = os.getenv("LOG_JSON_FORMAT", "true").lower() == "true"

# ============================================================
# OPENTELEMETRY SETTINGS
# ============================================================

# Enable OpenTelemetry
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() == "true"

# OTLP Collector endpoint
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "http://localhost:4317"  # gRPC endpoint
)

# OTLP protocol (grpc or http/protobuf)
OTEL_EXPORTER_OTLP_PROTOCOL = os.getenv(
    "OTEL_EXPORTER_OTLP_PROTOCOL",
    "grpc"
)

# Trace sampling rate (0.0 to 1.0)
# 1.0 = trace all requests, 0.1 = trace 10% of requests
TRACE_SAMPLING_RATE = float(os.getenv("TRACE_SAMPLING_RATE", "1.0"))

# ============================================================
# PROMETHEUS SETTINGS
# ============================================================

# Enable Prometheus metrics
PROMETHEUS_ENABLED = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"

# Prometheus metrics port
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "8001"))

# Metrics prefix
METRICS_PREFIX = "ai_officer"

# ============================================================
# JAEGER SETTINGS (for development/debugging)
# ============================================================

# Jaeger agent endpoint (if using direct Jaeger export)
JAEGER_AGENT_HOST = os.getenv("JAEGER_AGENT_HOST", "localhost")
JAEGER_AGENT_PORT = int(os.getenv("JAEGER_AGENT_PORT", "6831"))

# ============================================================
# QUALITY METRICS SETTINGS
# ============================================================

# Enable automatic quality evaluation
QUALITY_EVAL_ENABLED = os.getenv("QUALITY_EVAL_ENABLED", "true").lower() == "true"

# Quality metrics sampling rate (0.0 to 1.0)
# For performance, may not want to evaluate every single response
QUALITY_EVAL_SAMPLING_RATE = float(os.getenv("QUALITY_EVAL_SAMPLING_RATE", "1.0"))

# ============================================================
# COST TRACKING SETTINGS
# ============================================================

# Enable cost tracking
COST_TRACKING_ENABLED = os.getenv("COST_TRACKING_ENABLED", "true").lower() == "true"

# LLM pricing (per 1K tokens) - can be overridden via env vars
# Format: MODEL_NAME_INPUT_PRICE, MODEL_NAME_OUTPUT_PRICE
DEFAULT_LLM_PRICING = {
    'gpt-4o': {
        'input': float(os.getenv("GPT4O_INPUT_PRICE", "0.005")),  # $5 per 1M tokens
        'output': float(os.getenv("GPT4O_OUTPUT_PRICE", "0.015")),  # $15 per 1M tokens
    },
    'gpt-3.5-turbo': {
        'input': float(os.getenv("GPT35_INPUT_PRICE", "0.0005")),
        'output': float(os.getenv("GPT35_OUTPUT_PRICE", "0.0015")),
    },
    'mixtral-8x7b-32768': {
        'input': float(os.getenv("MIXTRAL_INPUT_PRICE", "0.0003")),
        'output': float(os.getenv("MIXTRAL_OUTPUT_PRICE", "0.0006")),
    },
    'openai/gpt-oss-120b': {  # Groq model
        'input': float(os.getenv("GPT_OSS_INPUT_PRICE", "0.0003")),
        'output': float(os.getenv("GPT_OSS_OUTPUT_PRICE", "0.0006")),
    },
}

# Daily cost alert threshold (USD)
DAILY_COST_ALERT_THRESHOLD = float(os.getenv("DAILY_COST_ALERT_THRESHOLD", "200.0"))

# ============================================================
# ALERT SETTINGS
# ============================================================

# Enable alerts
ALERTS_ENABLED = os.getenv("ALERTS_ENABLED", "true").lower() == "true"

# Slack webhook for alerts
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# PagerDuty integration key
PAGERDUTY_INTEGRATION_KEY = os.getenv("PAGERDUTY_INTEGRATION_KEY", "")

# Alert thresholds (from Solution Manual)
ALERT_THRESHOLDS = {
    # Latency thresholds (seconds)
    'p95_latency_warning': float(os.getenv("ALERT_P95_LATENCY_WARNING", "2.5")),
    'p95_latency_critical': float(os.getenv("ALERT_P95_LATENCY_CRITICAL", "5.0")),
    
    # Error rate thresholds (percentage)
    'error_rate_warning': float(os.getenv("ALERT_ERROR_RATE_WARNING", "2.0")),
    'error_rate_critical': float(os.getenv("ALERT_ERROR_RATE_CRITICAL", "5.0")),
    
    # Cache hit rate threshold (percentage)
    'cache_hit_rate_warning': float(os.getenv("ALERT_CACHE_HIT_RATE_WARNING", "40.0")),
    
    # Quality thresholds (percentage)
    'decision_fidelity_warning': float(os.getenv("ALERT_DECISION_FIDELITY_WARNING", "75.0")),
    'user_satisfaction_warning': float(os.getenv("ALERT_USER_SATISFACTION_WARNING", "70.0")),
    
    # Cost thresholds (USD)
    'daily_cost_critical': float(os.getenv("ALERT_DAILY_COST_CRITICAL", "200.0")),
}

# ============================================================
# PERFORMANCE SETTINGS
# ============================================================

# Maximum async logging queue size
LOG_QUEUE_SIZE = int(os.getenv("LOG_QUEUE_SIZE", "1000"))

# Metrics aggregation interval (seconds)
METRICS_AGGREGATION_INTERVAL = int(os.getenv("METRICS_AGGREGATION_INTERVAL", "60"))

# Trace batch size (number of spans before export)
TRACE_BATCH_SIZE = int(os.getenv("TRACE_BATCH_SIZE", "512"))

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_otlp_headers() -> dict:
    """Get OTLP exporter headers (for authentication, etc.)"""
    headers = {}
    
    # Add custom headers from env var
    headers_env = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    if headers_env:
        for header in headers_env.split(","):
            if "=" in header:
                key, value = header.split("=", 1)
                headers[key.strip()] = value.strip()
    
    return headers


def is_production() -> bool:
    """Check if running in production environment"""
    return ENVIRONMENT.lower() == "prod"


def is_development() -> bool:
    """Check if running in development environment"""
    return ENVIRONMENT.lower() == "dev"
