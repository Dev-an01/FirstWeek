"""
Observability Utilities
=======================

Helper functions for observability operations.
"""

import psutil
import os
from typing import Dict, Any, Optional
from datetime import datetime

from .logging import StructuredLogger

logger = StructuredLogger(__name__)


def get_system_info() -> Dict[str, Any]:
    """
    Get system information.
    
    Returns:
        Dictionary with system metrics
    """
    try:
        process = psutil.Process()
        
        return {
            'cpu_percent': process.cpu_percent(interval=0.1),
            'memory_mb': process.memory_info().rss / 1024 / 1024,
            'num_threads': process.num_threads(),
            'num_fds': process.num_fds() if hasattr(process, 'num_fds') else None,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
    except Exception as e:
        logger.warning("Failed to get system info", error=e)
        return {}


def get_gpu_info() -> Optional[Dict[str, Any]]:
    """
    Get GPU information (if available).
    
    Returns:
        Dictionary with GPU metrics or None
    """
    try:
        import torch
        
        if torch.cuda.is_available():
            return {
                'gpu_available': True,
                'gpu_count': torch.cuda.device_count(),
                'gpu_name': torch.cuda.get_device_name(0),
                'gpu_memory_allocated_mb': torch.cuda.memory_allocated(0) / 1024 / 1024,
                'gpu_memory_reserved_mb': torch.cuda.memory_reserved(0) / 1024 / 1024,
            }
        else:
            return {'gpu_available': False}
            
    except ImportError:
        return None
    except Exception as e:
        logger.warning("Failed to get GPU info", error=e)
        return None


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes into human-readable string.
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def format_duration(seconds: float) -> str:
    """
    Format duration into human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "1.5s", "123ms")
    """
    if seconds < 0.001:
        return f"{seconds * 1000000:.0f}µs"
    elif seconds < 1.0:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def sanitize_pii(text: str) -> str:
    """
    Sanitize PII from text (basic implementation).
    
    For production, use proper PII detection library.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text
    """
    # TODO: Implement proper PII redaction
    # For now, just return as-is
    return text


def truncate_string(text: str, max_length: int = 100) -> str:
    """
    Truncate string to maximum length.
    
    Args:
        text: String to truncate
        max_length: Maximum length
        
    Returns:
        Truncated string with "..." suffix if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
