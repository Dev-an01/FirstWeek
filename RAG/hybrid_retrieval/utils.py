"""
Hybrid Retrieval Utilities
===========================

Helper functions for the hybrid retrieval pipeline.
"""

import logging
import time
import functools
from typing import Dict, List, Any, Optional
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def timing_decorator(func):
    """
    Decorator to measure and log function execution time
    
    Usage:
        @timing_decorator
        def my_function():
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
        logger.debug(f"{func.__name__} completed in {elapsed_time:.1f}ms")
        return result
    return wrapper


def normalize_scores(scores: List[float], method: str = "minmax") -> List[float]:
    """
    Normalize scores to 0-1 range
    
    Args:
        scores: List of scores to normalize
        method: "minmax" or "zscore"
    
    Returns:
        List of normalized scores (0-1 range)
    """
    if not scores:
        return []
    
    scores_array = np.array(scores)
    
    if method == "minmax":
        min_score = scores_array.min()
        max_score = scores_array.max()
        
        if max_score == min_score:
            # All scores are the same
            return [1.0] * len(scores)
        
        normalized = (scores_array - min_score) / (max_score - min_score)
        return normalized.tolist()
    
    elif method == "zscore":
        mean = scores_array.mean()
        std = scores_array.std()
        
        if std == 0:
            return [0.5] * len(scores)
        
        # Z-score normalization, then sigmoid to 0-1
        zscore = (scores_array - mean) / std
        normalized = 1 / (1 + np.exp(-zscore))
        return normalized.tolist()
    
    else:
        raise ValueError(f"Unknown normalization method: {method}")


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate simple text similarity (Levenshtein-based)
    
    Args:
        text1: First text
        text2: Second text
    
    Returns:
        Similarity score (0-1)
    """
    # Simple implementation - can be enhanced with better algorithms
    text1_lower = text1.lower()
    text2_lower = text2.lower()
    
    # Exact match
    if text1_lower == text2_lower:
        return 1.0
    
    # Contains check
    if text1_lower in text2_lower or text2_lower in text1_lower:
        return 0.75
    
    # Word overlap
    words1 = set(text1_lower.split())
    words2 = set(text2_lower.split())
    
    if not words1 or not words2:
        return 0.0
    
    overlap = len(words1 & words2)
    union = len(words1 | words2)
    
    return overlap / union if union > 0 else 0.0


def deduplicate_results(results: List[Dict], id_key: str = "id") -> List[Dict]:
    """
    Remove duplicate results based on ID
    
    Args:
        results: List of result dictionaries
        id_key: Key to use for deduplication (default: "id")
    
    Returns:
        Deduplicated list (keeps first occurrence)
    """
    seen_ids = set()
    deduplicated = []
    
    for result in results:
        result_id = result.get(id_key)
        if result_id and result_id not in seen_ids:
            seen_ids.add(result_id)
            deduplicated.append(result)
    
    return deduplicated


def merge_metadata(metadata_list: List[Dict]) -> Dict:
    """
    Merge multiple metadata dictionaries
    
    Args:
        metadata_list: List of metadata dicts
    
    Returns:
        Merged metadata dictionary
    """
    merged = {}
    
    for metadata in metadata_list:
        if not metadata:
            continue
        
        for key, value in metadata.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(value, list):
                # Merge lists
                existing = merged[key] if isinstance(merged[key], list) else [merged[key]]
                merged[key] = existing + value
            elif isinstance(value, dict):
                # Merge dictionaries
                existing = merged[key] if isinstance(merged[key], dict) else {}
                merged[key] = {**existing, **value}
            else:
                # Keep first value for scalars
                pass
    
    return merged


def format_time_ms(time_seconds: float) -> str:
    """
    Format time in seconds to milliseconds string
    
    Args:
        time_seconds: Time in seconds
    
    Returns:
        Formatted string like "123.4ms"
    """
    return f"{time_seconds * 1000:.1f}ms"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
    
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def safe_get(dictionary: Dict, *keys, default=None) -> Any:
    """
    Safely get nested dictionary values
    
    Args:
        dictionary: Dictionary to query
        *keys: Sequence of keys to traverse
        default: Default value if key not found
    
    Returns:
        Value at nested path or default
    
    Example:
        safe_get(data, "metadata", "performance", "total_time_ms", default=0)
    """
    current = dictionary
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    
    return current


def calculate_percentile(values: List[float], percentile: int) -> float:
    """
    Calculate percentile of values
    
    Args:
        values: List of values
        percentile: Percentile to calculate (0-100)
    
    Returns:
        Percentile value
    """
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    index = int(len(sorted_values) * (percentile / 100))
    index = min(index, len(sorted_values) - 1)
    
    return sorted_values[index]


def format_json_compact(data: Dict, max_width: int = 80) -> str:
    """
    Format JSON compactly for logging
    
    Args:
        data: Dictionary to format
        max_width: Maximum width before truncation
    
    Returns:
        Compact JSON string
    """
    import json
    json_str = json.dumps(data, separators=(',', ':'))
    
    if len(json_str) > max_width:
        return json_str[:max_width - 3] + "..."
    
    return json_str


def validate_config(config: Dict, required_keys: List[str]) -> bool:
    """
    Validate configuration dictionary has required keys
    
    Args:
        config: Configuration dictionary
        required_keys: List of required keys
    
    Returns:
        True if valid, raises ValueError otherwise
    """
    missing_keys = [key for key in required_keys if key not in config]
    
    if missing_keys:
        raise ValueError(f"Configuration missing required keys: {missing_keys}")
    
    return True


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


__all__ = [
    'timing_decorator',
    'normalize_scores',
    'calculate_similarity',
    'deduplicate_results',
    'merge_metadata',
    'format_time_ms',
    'truncate_text',
    'safe_get',
    'calculate_percentile',
    'format_json_compact',
    'validate_config',
    'get_logger',
    'logger'
]
