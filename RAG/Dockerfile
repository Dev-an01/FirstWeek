# Multi-stage build for optimized image
FROM python:3.11-slim-bookworm as builder

# Set working directory
WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    build-essential \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Install heavy ML dependencies FIRST (these rarely change, so cache them)
# This layer will be cached and reused unless we explicitly change these versions
RUN set -ex && \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir cmake && \
    echo "Installing NumPy first..." && \
    pip install --no-cache-dir numpy==1.26.4 && \
    echo "Installing PyTorch with CUDA 12.4 support..." && \
    pip install --no-cache-dir \
        torch==2.5.1 \
        --index-url https://download.pytorch.org/whl/cu124 && \
    echo "Installing transformers and sentence-transformers..." && \
    pip install --no-cache-dir \
        transformers==4.46.0 \
        sentence-transformers==3.3.0 && \
    echo "✓ Heavy ML dependencies installed"

# Copy requirements for remaining dependencies
COPY requirements.txt .

# Install remaining dependencies (lighter, app-specific)
RUN echo "Installing app-specific dependencies..." && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir psycopg2-binary asyncpg neo4j && \
    echo "✓ All dependencies installed successfully"

# Download spaCy models directly via pip (more reliable than spacy download)
RUN pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/en_core_web_lg-3.7.1-py3-none-any.whl

# Install MinerU (magic-pdf) for OCR support on scanned PDFs
# This provides the 'mineru' CLI tool for document parsing
RUN echo "Installing MinerU OCR..." && \
    pip install --no-cache-dir \
        magic-pdf[full]>=1.3.0 \
        PyMuPDF>=1.24.0 && \
    echo "✓ MinerU OCR installed"

# Production stage
FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Install runtime dependencies (including audio libraries for Kokoro TTS)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    ffmpeg \
    libsndfile1 \
    libportaudio2 \
    espeak-ng \
    libespeak-ng1 \
    espeak-ng-data \
    gnupg2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install cuDNN for GPU-accelerated STT (faster-whisper)
# This enables GPU support for Whisper transcription (~2-3x faster)
# Made optional as NVIDIA repos may have signing issues
RUN apt-get update && \
    apt-get install -y wget && \
    (wget https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/cuda-keyring_1.1-1_all.deb && \
    dpkg -i cuda-keyring_1.1-1_all.deb && \
    apt-get update -o Acquire::AllowInsecureRepositories=true && \
    apt-get install -y --allow-unauthenticated libcudnn9-cuda-12 && \
    rm -f cuda-keyring_1.1-1_all.deb && \
    echo "✓ cuDNN 9 installed for GPU-accelerated STT") || \
    echo "⚠️  cuDNN installation skipped (will use CPU for STT)" && \
    rm -rf /var/lib/apt/lists/*

# Ensure CTranslate2 can find cuDNN libraries
ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/lib/x86_64-linux-gnu

# ============================================================
# CRITICAL: UTF-8 Encoding for Japanese Input Support
# ============================================================
# Force UTF-8 encoding throughout the container to properly handle
# Japanese characters in API requests and responses
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUTF8=1

# Create espeak-ng-data symlink (Kokoro expects it at /usr/share/espeak-ng-data)
RUN mkdir -p /usr/share && \
    ln -sf /usr/lib/x86_64-linux-gnu/espeak-ng-data /usr/share/espeak-ng-data

# Copy Python packages from builder INCLUDING spaCy data
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Copy docker scripts
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh

# Convert line endings and make entrypoint executable
# Using sed instead of dos2unix to avoid apt-get issues with NVIDIA repo
RUN sed -i 's/\r$//' /docker-entrypoint.sh && \
    chmod +x /docker-entrypoint.sh

# Initialize pyopenjtalk dictionary (required for Kokoro Japanese pipeline)
# This downloads the Japanese dictionary data (~100MB) for Japanese TTS support
# Made optional with retries to avoid build failures on network issues
RUN echo "Initializing pyopenjtalk for Japanese support..." && \
    (python3 -c "import pyopenjtalk; pyopenjtalk.g2p('こんにちは')" && \
    echo "✓ pyopenjtalk dictionary initialized") || \
    (echo "⚠️  pyopenjtalk dictionary initialization failed (will retry at runtime)" && \
    echo "   This is not critical - Japanese TTS will initialize on first use")

# Install Kokoro TTS with Japanese and English support
# Using kokoro from PyPI (high-quality multilingual TTS)
# Complete Japanese dependency chain for misaki[ja]:
#   - Second gen: pyopenjtalk, scipy
#   - First gen: fugashi, unidic-lite, jaconv, mojimoji
#   - Common: num2words
RUN echo "Installing Kokoro TTS with complete Japanese support..." && \
    pip install --no-cache-dir \
        kokoro>=0.9.4 \
        soundfile>=0.12.1 \
        pyopenjtalk>=0.3.0 \
        fugashi>=1.3.0 \
        unidic-lite>=1.0.8 \
        jaconv>=0.3.0 \
        mojimoji>=0.0.12 \
        scipy>=1.10.0 \
        num2words>=0.5.10 && \
    echo "✓ Kokoro TTS installed with ALL Japanese dependencies"

# Create model directories (models will be downloaded to persistent volume on first run)
# This avoids re-downloading 600MB+ of models on every rebuild
RUN mkdir -p /app/models/kokoro/voices /app/models/whisper && \
    echo "✓ Model directories created" && \
    echo "  Models will be downloaded on first run to persistent volume" && \
    echo "  - Kokoro TTS: ~315MB (base model + voices)" && \
    echo "  - Whisper STT: ~140MB (base model)"


# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chown appuser:appuser /docker-entrypoint.sh

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Use entrypoint for auto-initialization (downloads models on first run)
ENTRYPOINT ["/docker-entrypoint.sh"]

# Default command (passed to entrypoint)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
