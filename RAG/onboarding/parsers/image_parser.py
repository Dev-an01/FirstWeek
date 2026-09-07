"""
Image Parser - Extract text from image files using OCR.

Supports: PNG, JPG, JPEG
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_image(file_bytes: bytes, filename: str) -> str:
    """
    Extract text from an image file using OCR.

    Args:
        file_bytes: Raw image bytes
        filename: Original filename (used for extension detection)

    Returns:
        Extracted text from OCR

    Raises:
        ValueError: If no OCR backend is available or unsupported format
    """
    ext = Path(filename).suffix.lower()
    supported = {".png", ".jpg", ".jpeg"}

    if ext not in supported:
        raise ValueError(f"Unsupported image format: {ext}. Supported: {supported}")

    from .ocr_parser import parse_image_with_ocr

    logger.info(f"Parsing image '{filename}' with OCR")
    text = parse_image_with_ocr(file_bytes, filename)

    if not text:
        logger.warning(f"OCR extracted no text from image '{filename}'")

    return text
