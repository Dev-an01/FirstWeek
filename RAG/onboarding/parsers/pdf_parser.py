"""
PDF document parser using pdfplumber (good Japanese support).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def parse_pdf(file_bytes: bytes) -> str:
    """
    Extract text from a PDF file.

    Args:
        file_bytes: Raw PDF file bytes.

    Returns:
        Extracted text content.
    """
    import pdfplumber
    import io

    text_parts = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as e:
        logger.error(f"PDF parsing failed: {e}")
        raise ValueError(f"Failed to parse PDF: {e}")

    return "\n\n".join(text_parts)
