"""Document parsers for PDF, DOCX, TXT, JSON, and image files with OCR support."""

from .dispatcher import parse_document
from .pdf_parser import parse_pdf
from .docx_parser import parse_docx
from .text_parser import parse_text, parse_json
from .image_parser import parse_image
from .ocr_parser import parse_pdf_with_ocr, parse_image_with_ocr, get_ocr_backend

__all__ = [
    "parse_document",
    "parse_pdf",
    "parse_docx",
    "parse_text",
    "parse_json",
    "parse_image",
    "parse_pdf_with_ocr",
    "parse_image_with_ocr",
    "get_ocr_backend",
]
