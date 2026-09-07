"""
DOCX document parser using python-docx.
"""

import logging

logger = logging.getLogger(__name__)


def parse_docx(file_bytes: bytes) -> str:
    """
    Extract text from a DOCX file.

    Args:
        file_bytes: Raw DOCX file bytes.

    Returns:
        Extracted text content.
    """
    from docx import Document
    import io

    try:
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.error(f"DOCX parsing failed: {e}")
        raise ValueError(f"Failed to parse DOCX: {e}")
