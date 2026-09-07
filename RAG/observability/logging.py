"""
Structured Logging
==================

Provides structured JSON logging with automatic context injection.

Key Features:
- JSON format for easy parsing
- Automatic request_id correlation
- PII redaction support
- Consistent log structure
- Multiple log levels
- Integration with Python logging

Usage:
    from observability.logging import StructuredLogger, setup_logging
    
    # Initialize at startup
    setup_logging(level="INFO")
    
    # In component
    logger = StructuredLogger(__name__)
    logger.info("Query processed", latency_ms=123, tokens=450)
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from .context import RequestContext


class StructuredLogger:
    """
    Structured JSON logger with automatic context injection.
    
    Wraps Python's logging module to provide structured logs in JSON format
    with automatic request_id and other context fields.
    """
    
    def __init__(self, name: str):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name (usually __name__ of the module)
        """
        self.logger = logging.getLogger(name)
        self.component = name
    
    def _build_log_entry(
        self,
        level: str,
        message: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Build structured log entry with context.
        
        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            message: Log message
            **kwargs: Additional fields to include
            
        Returns:
            Dictionary with complete log entry
        """
        entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'component': self.component,
            'message': message,
            'request_id': RequestContext.get_request_id(),
            'user_id': RequestContext.get_user_id(),
            'executive_id': RequestContext.get_executive_id(),
        }
        
        # Add additional fields
        entry.update(kwargs)
        
        # Remove None values to keep logs clean
        return {k: v for k, v in entry.items() if v is not None}
    
    def _log(self, level: str, message: str, **kwargs):
        """Internal log method"""
        entry = self._build_log_entry(level, message, **kwargs)
        log_line = json.dumps(entry, default=str)
        
        # Map to appropriate logging level
        if level == 'DEBUG':
            self.logger.debug(log_line)
        elif level == 'INFO':
            self.logger.info(log_line)
        elif level == 'WARNING':
            self.logger.warning(log_line)
        elif level == 'ERROR':
            self.logger.error(log_line)
        elif level == 'CRITICAL':
            self.logger.critical(log_line)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log('DEBUG', message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """
        Log info message.
        
        Example:
            logger.info("Query processed", latency_ms=123, results=5)
        """
        self._log('INFO', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """
        Log warning message.
        
        Example:
            logger.warning("Cache miss", cache_key="query_123")
        """
        self._log('WARNING', message, **kwargs)
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """
        Log error message.
        
        Args:
            message: Error message
            error: Optional exception object
            **kwargs: Additional fields
            
        Example:
            logger.error("LLM call failed", error=e, model="gpt-4o")
        """
        if error:
            kwargs['error'] = str(error)
            kwargs['error_type'] = type(error).__name__
        self._log('ERROR', message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """
        Log critical message.
        
        Example:
            logger.critical("Database connection lost", retry_count=3)
        """
        self._log('CRITICAL', message, **kwargs)


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for Python's logging module.
    
    Formats log records as JSON for structured logging systems.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        # Try to parse as JSON (already formatted by StructuredLogger)
        try:
            # If message is already JSON, return as-is
            json.loads(record.getMessage())
            return record.getMessage()
        except (json.JSONDecodeError, ValueError):
            # Not JSON, format as plain log
            log_data = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'level': record.levelname,
                'component': record.name,
                'message': record.getMessage(),
                'request_id': RequestContext.get_request_id(),
            }
            
            # Add exception info if present
            if record.exc_info:
                log_data['exception'] = self.formatException(record.exc_info)
            
            # Remove None values
            log_data = {k: v for k, v in log_data.items() if v is not None}
            
            return json.dumps(log_data, default=str)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = True
) -> None:
    """
    Set up logging configuration.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        json_format: Use JSON format (default: True)
        
    Example:
        setup_logging(level="INFO", log_file="logs/app.log")
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create handlers
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    handlers.append(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        handlers.append(file_handler)
    
    # Set formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    for handler in handlers:
        handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add new handlers
    for handler in handlers:
        root_logger.addHandler(handler)
    
    # Log initialization
    logger = StructuredLogger(__name__)
    logger.info(
        "Logging initialized",
        log_level=level,
        json_format=json_format,
        log_file=log_file
    )


def redact_pii(text: str) -> str:
    """
    Redact PII from text (basic implementation).
    
    For production, use a proper PII detection library like Presidio.
    
    Args:
        text: Text potentially containing PII
        
    Returns:
        Text with PII redacted
    """
    # TODO: Implement proper PII redaction
    # For now, just return as-is
    # In production, use: microsoft/presidio
    return text
