"""
Context Analysis Module

Stage 1 of the Conversation Engine pipeline.
Classifies queries by theme, urgency, emotion, and turn type.
"""

# Models
from .models import (
    Theme,
    Urgency,
    UserEmotion,
    TurnType,
    QueryType,
    AnalyzedContext,
)

# Analyzer and classifiers
from .analyzer import ContextAnalyzer, create_context_analyzer, get_context_analyzer
from .classifiers import (
    ThemeClassifier,
    UrgencyClassifier,
    EmotionClassifier,
    TurnTypeClassifier,
    get_theme_classifier,
    get_urgency_classifier,
    get_emotion_classifier,
    get_turn_type_classifier,
)

__all__ = [
    # Models
    "Theme",
    "Urgency",
    "UserEmotion",
    "TurnType",
    "QueryType",
    "AnalyzedContext",
    # Analyzer
    "ContextAnalyzer",
    "create_context_analyzer",
    "get_context_analyzer",
    # Individual classifiers
    "ThemeClassifier",
    "UrgencyClassifier",
    "EmotionClassifier",
    "TurnTypeClassifier",
    "get_theme_classifier",
    "get_urgency_classifier",
    "get_emotion_classifier",
    "get_turn_type_classifier",
]
