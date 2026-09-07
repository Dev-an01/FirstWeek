"""
LangGraph Workflow Package

Provides workflow orchestration for RAG system using LangGraph + LangSmith.

Key Components:
- state.py: RAGState TypedDict schema
- nodes.py: Node functions with dependency injection
- graph.py: Workflow graph assembly
- react_subgraph.py: ReAct multi-step reasoning (Week 2, Day 4)
- ab_testing.py: A/B testing router (TODO)
"""

from .state import RAGState, get_default_state, safe_get
from .graph import create_rag_workflow, visualize_workflow
from .react_subgraph import create_react_nodes, should_continue_react

__version__ = "0.1.0"

__all__ = [
    "RAGState",
    "get_default_state",
    "safe_get",
    "create_rag_workflow",
    "visualize_workflow",
    "create_react_nodes",
    "should_continue_react"
]
