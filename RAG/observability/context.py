"""
Request Context Manager
========================

Manages request-scoped context for observability across the entire request lifecycle.
Uses Python's contextvars for async-safe context propagation.

Key Features:
- Automatic request_id generation
- Context propagation across async boundaries
- Thread-safe and async-safe
- Easy access from any component

Usage:
    from observability.context import RequestContext
    
    # In middleware/entry point
    request_id = RequestContext.generate_request_id()
    RequestContext.set('request_id', request_id)
    RequestContext.set('user_id', user_id)
    
    # Anywhere in code
    request_id = RequestContext.get_request_id()
    user_id = RequestContext.get('user_id')
"""

import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any
from datetime import datetime

# Context variable for request-scoped data
_request_context: ContextVar[Dict[str, Any]] = ContextVar('request_context', default={})


class RequestContext:
    """
    Request context manager for observability.
    
    Provides thread-safe and async-safe context storage using contextvars.
    All observability components use this for correlation.
    """
    
    @staticmethod
    def generate_request_id() -> str:
        """
        Generate unique request ID.
        
        Format: req_{timestamp}_{random}
        Example: req_1730495100_a3f2d8e1
        
        Returns:
            Unique request identifier string
        """
        timestamp = int(datetime.utcnow().timestamp())
        random_suffix = uuid.uuid4().hex[:8]
        return f"req_{timestamp}_{random_suffix}"
    
    @staticmethod
    def set(key: str, value: Any) -> None:
        """
        Set context value.
        
        Args:
            key: Context key
            value: Value to store
            
        Example:
            RequestContext.set('request_id', 'req_123')
            RequestContext.set('user_id', 'user_456')
        """
        ctx = _request_context.get().copy()
        ctx[key] = value
        _request_context.set(ctx)
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """
        Get context value.
        
        Args:
            key: Context key
            default: Default value if key not found
            
        Returns:
            Context value or default
            
        Example:
            user_id = RequestContext.get('user_id')
            role = RequestContext.get('user_role', 'guest')
        """
        return _request_context.get().get(key, default)
    
    @staticmethod
    def get_all() -> Dict[str, Any]:
        """
        Get all context values.
        
        Returns:
            Dictionary of all context key-value pairs
        """
        return _request_context.get().copy()
    
    @staticmethod
    def get_request_id() -> Optional[str]:
        """
        Get current request ID.
        
        Convenience method for most common context access.
        
        Returns:
            Request ID string or None if not set
        """
        return RequestContext.get('request_id')
    
    @staticmethod
    def get_user_id() -> Optional[str]:
        """
        Get current user ID.
        
        Returns:
            User ID string or None if not set
        """
        return RequestContext.get('user_id')
    
    @staticmethod
    def get_executive_id() -> Optional[str]:
        """
        Get current executive profile ID.
        
        Returns:
            Executive ID string or None if not set
        """
        return RequestContext.get('executive_id')
    
    @staticmethod
    def clear() -> None:
        """
        Clear all context values.
        
        Should be called at end of request to prevent memory leaks.
        Middleware handles this automatically.
        """
        _request_context.set({})
    
    @staticmethod
    def update(data: Dict[str, Any]) -> None:
        """
        Update multiple context values at once.
        
        Args:
            data: Dictionary of key-value pairs to set
            
        Example:
            RequestContext.update({
                'user_id': 'user_123',
                'user_role': 'manager',
                'session_id': 'session_456'
            })
        """
        ctx = _request_context.get().copy()
        ctx.update(data)
        _request_context.set(ctx)
    
    @staticmethod
    def remove(key: str) -> None:
        """
        Remove a context value.
        
        Args:
            key: Context key to remove
        """
        ctx = _request_context.get().copy()
        ctx.pop(key, None)
        _request_context.set(ctx)


# Convenience functions for common operations
def get_current_context() -> Dict[str, Any]:
    """Get all current context values"""
    return RequestContext.get_all()


def set_request_context(**kwargs) -> None:
    """Set multiple context values"""
    RequestContext.update(kwargs)
