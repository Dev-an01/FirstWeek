"""
API Routes for Onboarding Service.
"""

from .documents import router as documents_router
from .profiles import router as profiles_router
from .calibration import router as calibration_router
from .knowledgebase import router as knowledgebase_router
from .voice import router as voice_router

__all__ = ["documents_router", "profiles_router", "calibration_router", "knowledgebase_router", "voice_router"]
