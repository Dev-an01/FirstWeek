"""
RAG Profile Refresh Notifier.

POSTs to the RAG service after onboarding, calibration, or deletion
so that cached profiles are refreshed. Non-fatal: failures are logged
but never block the calling operation.
"""

import logging
import os
import httpx

logger = logging.getLogger(__name__)

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8000")
RAG_REFRESH_ENDPOINT = "/api/v1/profiles/refresh"


async def notify_rag_profile_refresh(
    company_id: str,
    executive_id: str,
    reason: str = "onboarding",
) -> bool:
    """
    Notify the RAG service to refresh its cached profile for an executive.

    Args:
        company_id: Company ID.
        executive_id: Executive ID.
        reason: Why the refresh is needed (onboarding, calibration, deletion).

    Returns:
        True if notification succeeded, False otherwise (never raises).
    """
    url = f"{RAG_SERVICE_URL}{RAG_REFRESH_ENDPOINT}"
    payload = {
        "company_id": company_id,
        "executive_id": executive_id,
        "reason": reason,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info(
                f"RAG profile refresh notified: {company_id}/{executive_id} ({reason})"
            )
            return True

    except httpx.ConnectError:
        logger.warning(
            f"RAG service not reachable at {RAG_SERVICE_URL}, skipping refresh notification"
        )
        return False

    except Exception as e:
        logger.warning(f"RAG refresh notification failed (non-fatal): {e}")
        return False
