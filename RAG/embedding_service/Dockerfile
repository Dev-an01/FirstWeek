# Embedding Service Dockerfile
# ============================
# Multi-stage build for production-ready embedding service
# Build context: RAG/ (parent directory)

# Build stage
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY embedding_service/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim AS production

# Create non-root user
RUN groupadd -r embeddinguser && useradd -r -g embeddinguser embeddinguser

# Set working directory
WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code - embedding_service module
COPY embedding_service/ ./embedding_service/

# Copy only required modules from parent directory
# (observability NOT needed - vector_search uses lazy imports now)
COPY embedding_generation/ ./embedding_generation/
COPY vector_search/ ./vector_search/

# Create necessary directories including model cache
RUN mkdir -p /app/logs /app/data /app/.cache/huggingface

# Set permissions
RUN chown -R embeddinguser:embeddinguser /app

# Switch to non-root user
USER embeddinguser

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV EMBEDDING_SERVICE_HOST=0.0.0.0
ENV EMBEDDING_SERVICE_PORT=8001
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose port
EXPOSE 8001

# Start command
CMD ["uvicorn", "embedding_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
