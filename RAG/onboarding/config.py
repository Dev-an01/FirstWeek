"""
Onboarding Service Configuration.

Environment variables, model settings, and constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (ai officer/.env)
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# ============================================================================
# Database
# ============================================================================
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "ai_officer_dev"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
}

# ============================================================================
# Neo4j Configuration
# ============================================================================
NEO4J_CONFIG = {
    "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    "user": os.getenv("NEO4J_USER", "neo4j"),
    "password": os.getenv("NEO4J_PASSWORD", "12341234"),
}

# ============================================================================
# LLM Configuration (Groq - openai/gpt-oss-120b)
# Context: 131K tokens, but TPM limits vary by tier:
#   - on_demand tier: 8K TPM (need to chunk large docs)
#   - Developer tier: 250K TPM (can process full docs)
# ============================================================================
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.getenv("GROQ_EXTRACTION_MODEL", "openai/gpt-oss-120b")

GROQ_EXTRACTION_API_KEY = os.getenv("GROQ_EXTRACTION_API_KEY", "")
GROQ_SYNTHESIS_API_KEY = os.getenv("GROQ_SYNTHESIS_API_KEY", "")

LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 8000
LLM_RETRY_ATTEMPTS = 6
LLM_RETRY_BASE_DELAY = 15.0  # seconds, exponential backoff

# Token limit for input text (on_demand tier: 8K TPM, Developer: 250K TPM)
# Set based on your Groq tier. ~4 chars per token, leave room for prompts
LLM_MAX_INPUT_CHARS = int(os.getenv("LLM_MAX_INPUT_CHARS", "20000"))  # ~5K tokens for on_demand

# ============================================================================
# Service
# ============================================================================
SERVICE_NAME = "AI Officer Onboarding Service"
SERVICE_VERSION = "1.0.0"
SERVICE_HOST = "0.0.0.0"
SERVICE_PORT = int(os.getenv("ONBOARDING_SERVICE_PORT", "8002"))
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")

# ============================================================================
# Document Processing
# ============================================================================
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
MAX_TEXT_LENGTH = 100_000  # characters
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".json", ".png", ".jpg", ".jpeg", ".md"}

# ============================================================================
# Pipeline
# ============================================================================
EXTRACTION_WORKERS = 2  # reduced from 7 to avoid Groq rate limits (8000 TPM on free tier)

# ============================================================================
# Calibration Configuration
# ============================================================================
CALIBRATION_CONFIG = {
    "auto_on_document_change": os.getenv("CALIBRATION_AUTO_ON_DOC_CHANGE", "false").lower() == "true",
    "schedule": os.getenv("CALIBRATION_SCHEDULE", None),  # Cron expression for scheduled calibration (future)
    "default_mode": os.getenv("CALIBRATION_DEFAULT_MODE", "incremental"),  # full or incremental
}

# ============================================================================
# OCR Configuration (for scanned PDFs and images)
# ============================================================================
OCR_CONFIG = {
    # Backend selection: "mineru" (6GB VRAM) or "olmocr2" (32GB VRAM)
    "backend": os.getenv("OCR_BACKEND", "mineru"),

    # Quality thresholds - if pdfplumber extracts less than this, use OCR
    # min_text_length: absolute minimum chars (if less, definitely scanned)
    # min_text_ratio: chars per KB ratio (lower = more likely scanned)
    #   - Scanned PDFs: ~0-5 chars/KB
    #   - Image-heavy presentations: ~1-10 chars/KB
    #   - Text-based PDFs: ~50-200 chars/KB
    "min_text_length": int(os.getenv("OCR_MIN_TEXT_LENGTH", "100")),
    "min_text_ratio": float(os.getenv("OCR_MIN_TEXT_RATIO", "0.01")),  # 10 chars per KB threshold

    # MinerU settings (RTX 3060 6GB VRAM)
    "mineru": {
        "mode": os.getenv("MINERU_MODE", "pipeline"),  # pipeline, hybrid-auto-engine
        "output_format": "markdown",
        "timeout": int(os.getenv("MINERU_TIMEOUT", "600")),  # seconds (increased for large docs)
    },

    # olmOCR 2 settings (RTX 5090 32GB VRAM)
    "olmocr2": {
        "model": os.getenv("OLMOCR_MODEL", "allenai/olmOCR-2-7B-1025"),
        "vllm_server": os.getenv("OLMOCR_VLLM_SERVER", None),  # External server URL
        "timeout": 600,  # seconds
    },
}
