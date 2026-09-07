"""
Routes files to the correct parser based on extension.
Includes OCR fallback for scanned PDFs and image support.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Union, overload

from onboarding.config import MAX_TEXT_LENGTH, ALLOWED_EXTENSIONS, OCR_CONFIG

logger = logging.getLogger(__name__)

# Image extensions that require OCR
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

# Parsing method identifiers
PARSING_METHOD_PDFPLUMBER = "pdfplumber"
PARSING_METHOD_DOCX = "docx"
PARSING_METHOD_TEXT = "text"
PARSING_METHOD_JSON = "json"
PARSING_METHOD_IMAGE = "image"


def parse_document(
    filename: str,
    file_bytes: bytes,
    return_metadata: bool = False
) -> Union[str, Tuple[str, Dict[str, Any]]]:
    """
    Parse a document by dispatching to the appropriate parser.
    For PDFs, includes OCR fallback if text extraction is poor quality.

    Args:
        filename: Original filename (used for extension detection).
        file_bytes: Raw file bytes.
        return_metadata: If True, returns (text, metadata) tuple with parsing info.

    Returns:
        If return_metadata=False: Extracted text content, truncated to MAX_TEXT_LENGTH.
        If return_metadata=True: Tuple of (text, metadata) where metadata includes:
            - parsing_method: str (pdfplumber, mineru, olmocr2, docx, text, json, image)
            - ocr_applied: bool

    Raises:
        ValueError: If the file extension is unsupported.
    """
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")

    # Initialize metadata
    metadata: Dict[str, Any] = {
        "parsing_method": PARSING_METHOD_TEXT,
        "ocr_applied": False
    }

    # Route to appropriate parser
    if ext == ".pdf":
        text, used_ocr = _parse_pdf_with_fallback(file_bytes, filename)
        if used_ocr:
            metadata["parsing_method"] = OCR_CONFIG.get("backend", "mineru")
            metadata["ocr_applied"] = True
        else:
            metadata["parsing_method"] = PARSING_METHOD_PDFPLUMBER
    elif ext == ".docx":
        from .docx_parser import parse_docx
        text = parse_docx(file_bytes)
        metadata["parsing_method"] = PARSING_METHOD_DOCX
    elif ext == ".json":
        from .text_parser import parse_json
        text = parse_json(file_bytes)
        metadata["parsing_method"] = PARSING_METHOD_JSON
    elif ext in IMAGE_EXTENSIONS:
        from .image_parser import parse_image
        text = parse_image(file_bytes, filename)
        metadata["parsing_method"] = OCR_CONFIG.get("backend", "mineru")
        metadata["ocr_applied"] = True
    elif ext in {".txt", ".md"}:  # Plain text and markdown
        from .text_parser import parse_text
        text = parse_text(file_bytes)
        metadata["parsing_method"] = PARSING_METHOD_TEXT
    else:  # fallback
        from .text_parser import parse_text
        text = parse_text(file_bytes)
        metadata["parsing_method"] = PARSING_METHOD_TEXT

    # Truncate if too long
    text = _truncate(text, filename)

    if return_metadata:
        return text, metadata
    return text


def _parse_pdf_with_fallback(file_bytes: bytes, filename: str) -> Tuple[str, bool]:
    """
    Parse PDF with OCR fallback for scanned documents.

    1. Try pdfplumber first (fast, text-based)
    2. Check if extraction quality is sufficient
    3. If poor quality, use OCR backend

    Args:
        file_bytes: Raw PDF bytes
        filename: Original filename

    Returns:
        Tuple of (extracted_text, ocr_was_used)
    """
    from .pdf_parser import parse_pdf

    # Try pdfplumber first
    text = parse_pdf(file_bytes)

    # Check if OCR is needed
    if _needs_ocr(text, file_bytes):
        logger.info(f"PDF '{filename}' appears scanned (low text quality), trying OCR...")
        try:
            from .ocr_parser import parse_pdf_with_ocr
            ocr_text = parse_pdf_with_ocr(file_bytes, filename)

            # Only use OCR result if it's better
            if len(ocr_text.strip()) > len(text.strip()):
                logger.info(
                    f"OCR improved extraction: {len(text)} -> {len(ocr_text)} chars"
                )
                return ocr_text, True
            else:
                logger.info("OCR did not improve extraction, keeping pdfplumber result")

        except ValueError as e:
            # No OCR backend available
            logger.warning(f"OCR not available for '{filename}': {e}")
        except Exception as e:
            logger.warning(f"OCR failed for '{filename}': {e}")
            # Keep original pdfplumber result as fallback

    return text, False


def _needs_ocr(text: str, file_bytes: bytes) -> bool:
    """
    Determine if OCR is needed based on extraction quality.

    Checks:
    1. Absolute minimum text length - if below, definitely needs OCR
    2. Sufficient text threshold - if above, pdfplumber worked fine
    3. Text ratio (only if between min and sufficient)

    Args:
        text: Text extracted by pdfplumber
        file_bytes: Original PDF bytes

    Returns:
        True if OCR should be attempted
    """
    min_length = OCR_CONFIG.get("min_text_length", 100)
    min_ratio = OCR_CONFIG.get("min_text_ratio", 0.01)

    stripped_text = text.strip()
    text_length = len(stripped_text)

    # Check 1: Absolute minimum - definitely needs OCR
    if text_length < min_length:
        logger.debug(
            f"Text length {text_length} below minimum {min_length}, OCR needed"
        )
        return True

    # Check 2: Sufficient text extracted - pdfplumber worked fine
    # For presentation-style PDFs with lots of images but some text,
    # if we got substantial text (>500 chars), pdfplumber is working
    sufficient_length = 500
    if text_length >= sufficient_length:
        logger.debug(
            f"Text length {text_length} is sufficient (>={sufficient_length}), no OCR needed"
        )
        return False

    # Check 3: Ratio check for edge cases (between 100-500 chars)
    file_size_kb = len(file_bytes) / 1024
    if file_size_kb > 0:
        chars_per_kb = text_length / file_size_kb
        threshold = min_ratio * 1000  # Convert ratio to chars per KB

        if chars_per_kb < threshold:
            logger.debug(
                f"Chars per KB ({chars_per_kb:.1f}) below threshold ({threshold}), OCR needed"
            )
            return True

    return False


def _truncate(text: str, filename: str) -> str:
    """Truncate text to MAX_TEXT_LENGTH with warning."""
    if len(text) > MAX_TEXT_LENGTH:
        logger.warning(
            f"Document '{filename}' truncated from {len(text)} to {MAX_TEXT_LENGTH} chars"
        )
        return text[:MAX_TEXT_LENGTH]
    return text
