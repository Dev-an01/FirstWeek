"""
Query Routing Module

Enhanced query routing system for the RAG application.
Implements the adaptive routing strategy from the Solution Manual.
"""

from .router import QueryRouter
from .path_handlers import FastPathHandler, StandardPathHandler, AgenticPathHandler

__all__ = [
    "QueryRouter",
    "FastPathHandler", 
    "StandardPathHandler",
    "AgenticPathHandler"
]