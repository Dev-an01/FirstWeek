"""
Embedding Trigger - Calls embedding service to generate embeddings for new executive.

Sends profile text + decision cases + voiceprint text to the embedding service
with company_id and executive_id metadata for tenant isolation.
"""

import json
import logging
from typing import Dict, Any, List

import asyncpg
import httpx

from onboarding.config import EMBEDDING_SERVICE_URL

logger = logging.getLogger(__name__)

EMBEDDING_BATCH_URL = f"{EMBEDDING_SERVICE_URL}/embeddings/batch"
EMBEDDING_SINGLE_URL = f"{EMBEDDING_SERVICE_URL}/embeddings/documents"


async def trigger_embeddings(
    executive_id: str,
    company_id: str,
    profile: Dict[str, Any],
    voiceprint: Dict[str, Any],
    pool: asyncpg.Pool = None,
) -> Dict[str, Any]:
    """
    Trigger embedding generation for the new executive's content.

    Sends documents to the embedding service (port 8001) with metadata
    including company_id and executive_id for tenant isolation.

    Args:
        executive_id: Executive ID.
        company_id: Company ID.
        profile: Full assembled profile.
        voiceprint: Full assembled voiceprint.
        pool: Optional asyncpg pool to query uploaded documents for embedding.

    Returns:
        Summary of embedding trigger results.
    """
    documents = []

    # 1. Executive profile text
    profile_text = _profile_to_text(profile)
    if profile_text:
        documents.append({
            "source_id": executive_id,
            "source_type": "executive_profile",
            "content": profile_text,
            "metadata": {
                "company_id": company_id,
                "executive_id": executive_id,
                "type": "profile",
            },
            "force_update": True,
        })

    # 2. Decision cases (one per case)
    for i, case in enumerate(profile.get("decision_cases", [])):
        case_text = _decision_case_to_text(case)
        if case_text:
            documents.append({
                "source_id": f"{executive_id}_case_{i:03d}",
                "source_type": "decision_case",
                "content": case_text,
                "metadata": {
                    "company_id": company_id,
                    "executive_id": executive_id,
                    "type": "decision_case",
                    "case_index": i,
                },
                "force_update": True,
            })

    # 3. Voiceprint text
    vp_text = _voiceprint_to_text(voiceprint)
    if vp_text:
        documents.append({
            "source_id": f"{executive_id}_voiceprint",
            "source_type": "executive_profile",
            "content": vp_text,
            "metadata": {
                "company_id": company_id,
                "executive_id": executive_id,
                "type": "voiceprint",
            },
            "force_update": True,
        })

    # 4. Uploaded executive documents (chunked)
    if pool is not None:
        try:
            from onboarding.services.knowledgebase_service import _chunk_text

            exec_docs = await pool.fetch(
                """SELECT id, filename, extracted_text, access_level
                   FROM executive_documents
                   WHERE executive_id = $1 AND company_id = $2 AND is_active = true""",
                executive_id, company_id,
            )
            for doc in exec_docs:
                text = doc["extracted_text"]
                if not text:
                    continue
                chunks = _chunk_text(text)
                for i, chunk in enumerate(chunks):
                    documents.append({
                        "source_id": f"{doc['id']}_chunk_{i:04d}",
                        "source_type": "document",
                        "content": chunk,
                        "metadata": {
                            "company_id": company_id,
                            "executive_id": executive_id,
                            "document_id": str(doc["id"]),
                            "filename": doc["filename"],
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "access_level": doc["access_level"],
                        },
                        "access_level": doc["access_level"],
                        "force_update": True,
                    })
            logger.info(
                f"Added {sum(1 for d in documents if d.get('source_type') == 'document')} "
                f"document chunks from {len(exec_docs)} uploaded files for {executive_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to fetch uploaded documents for embedding: {e}")

    if not documents:
        return {"status": "skipped", "reason": "no content to embed"}

    # Send to embedding service
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                EMBEDDING_BATCH_URL,
                json={
                    "documents": documents,
                    "priority": "high",
                    "batch_id": f"onboarding_{executive_id}",
                },
                params={"async_processing": "false"},
            )
            response.raise_for_status()
            result = response.json()

            logger.info(
                f"Embedding trigger complete for {executive_id}: "
                f"{len(documents)} documents sent"
            )
            return {
                "status": "completed",
                "documents_sent": len(documents),
                "response": result,
            }

    except httpx.ConnectError:
        msg = f"Embedding service not reachable at {EMBEDDING_SERVICE_URL}"
        logger.warning(msg)
        return {"status": "unavailable", "error": msg, "documents_queued": len(documents)}

    except Exception as e:
        msg = f"Embedding trigger failed: {e}"
        logger.error(msg)
        return {"status": "failed", "error": msg}


def _profile_to_text(profile: Dict[str, Any]) -> str:
    """Convert profile to embeddable text."""
    parts = []
    parts.append(f"Executive: {profile.get('name', '')} ({profile.get('name_english', '')})")
    parts.append(f"Title: {profile.get('title', '')}")
    parts.append(f"Company: {profile.get('company', '')}")

    # Thinking patterns
    tp = profile.get("thinking_patterns", {})
    if tp.get("problem_approach"):
        parts.append(f"Problem approach: {tp['problem_approach']}")

    # Core values
    for val in profile.get("core_values", []):
        if isinstance(val, dict):
            parts.append(f"Core value: {val.get('name', '')} - {val.get('behavior', '')}")

    # Communication style
    cs = profile.get("communication_style", {})
    if cs.get("overall_tone"):
        parts.append(f"Communication tone: {cs['overall_tone']}")

    # Red flags
    rf = profile.get("red_flags", {})
    for item in rf.get("never_approve", []):
        parts.append(f"Never approve: {item}")
    for item in rf.get("always_do", []):
        parts.append(f"Always do: {item}")

    return "\n".join(parts)


def _decision_case_to_text(case: Dict[str, Any]) -> str:
    """Convert a decision case to embeddable text."""
    parts = [
        f"Decision: {case.get('title', '')}",
        f"Category: {case.get('category', '')}",
        f"Situation: {case.get('situation', '')}",
        f"Decision made: {case.get('decision_made', '')}",
        f"Rationale: {case.get('rationale', '')}",
        f"Outcome: {case.get('outcome', '')}",
        f"Lessons: {case.get('lessons_learned', '')}",
    ]
    return "\n".join(p for p in parts if p.split(": ", 1)[-1])


def _voiceprint_to_text(voiceprint: Dict[str, Any]) -> str:
    """Convert voiceprint to embeddable text."""
    parts = []
    vp = voiceprint.get("voiceprint", {})
    for key, value in vp.items():
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, str) and v:
                    parts.append(f"{key}.{k}: {v}")
                elif isinstance(v, list):
                    parts.append(f"{key}.{k}: {', '.join(str(x) for x in v)}")

    casual = voiceprint.get("casual_responses", {})
    for category, phrases in casual.items():
        if isinstance(phrases, list):
            parts.append(f"Casual {category}: {', '.join(str(p) for p in phrases)}")

    return "\n".join(parts)
