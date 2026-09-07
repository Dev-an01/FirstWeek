"""
Plain text and JSON file parser.
"""

import json
import logging

logger = logging.getLogger(__name__)


def parse_text(file_bytes: bytes) -> str:
    """Parse plain text file (UTF-8)."""
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("utf-8", errors="replace")


def parse_json(file_bytes: bytes) -> str:
    """
    Parse a JSON file and return a readable text representation.
    """
    try:
        data = json.loads(file_bytes.decode("utf-8"))
        return json.dumps(data, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"JSON parsing failed, treating as plain text: {e}")
        return parse_text(file_bytes)
