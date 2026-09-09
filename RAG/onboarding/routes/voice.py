"""
Voice Cloning Key Management API Routes.

Endpoints for validating voice samples via STT, generating per-executive
voice cloning keys via Google Chirp3 API, and managing stored keys.
"""

import base64
import difflib
import json
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
import google.auth
import google.auth.transport.requests

from onboarding.db import executives

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/companies/{company_id}/executives/{executive_id}/voice",
    tags=["Voice Cloning"],
)

# Consent scripts per language
CONSENT_SCRIPTS = {
    "en": "I am the owner of this voice and I consent to Google using this voice to create a synthetic voice model.",
    "ja": "私はこの音声の所有者であり、Googleがこの音声を使用して音声合成 モデルを作成することを承認します。",
}

# Language code mapping
LANGUAGE_CODE_MAP = {
    "en": "en-US",
    "ja": "ja-JP",
}

# RAG service URL (STT endpoint)
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8000")

# GCP config
GCP_PROJECT_ID = os.getenv("GCP_VOICE_CLONING_PROJECT_ID") or os.getenv("GCP_PROJECT_ID")


async def _validate_executive_company(pool, company_id: str, executive_id: str):
    """Validate that executive belongs to company."""
    exec_row = await executives.get_executive(pool, executive_id)
    if not exec_row:
        raise HTTPException(status_code=404, detail=f"Executive '{executive_id}' not found")
    if exec_row.get("company_id") != company_id:
        raise HTTPException(
            status_code=404,
            detail=f"Executive '{executive_id}' not found in company '{company_id}'",
        )
    return exec_row


def _get_gcp_access_token() -> str:
    """Get GCP access token using Application Default Credentials."""
    credentials, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


async def _transcribe_audio(audio_bytes: bytes, language: str, filename: str) -> dict:
    """Call RAG service STT endpoint to transcribe audio."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        files = {"file": (filename, audio_bytes, "audio/wav")}
        data = {"language": language}
        try:
            response = await client.post(
                f"{RAG_SERVICE_URL}/api/v1/stt/transcribe",
                files=files,
                data=data,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"STT request failed: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=502,
                detail=f"STT transcription failed: {e.response.text}",
            )
        except httpx.RequestError as e:
            logger.error(f"STT request error: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Could not reach STT service at {RAG_SERVICE_URL}: {e}",
            )


@router.post("/validate")
async def validate_voice_samples(
    company_id: str,
    executive_id: str,
    reference_audio: UploadFile = File(..., description="Reference voice sample"),
    consent_audio: UploadFile = File(..., description="Consent recording"),
    language: str = Form("en", description="Language: 'en' or 'ja'"),
    request: Request = None,
):
    """
    Validate voice samples via STT before key generation.

    Checks:
    - Reference audio has meaningful speech (transcript > 10 chars)
    - Consent audio matches expected consent script (fuzzy match > 0.75)
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    if language not in CONSENT_SCRIPTS:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}. Use 'en' or 'ja'.")

    # Read audio files
    ref_bytes = await reference_audio.read()
    consent_bytes = await consent_audio.read()

    # Transcribe both via STT
    ref_result = await _transcribe_audio(ref_bytes, language, reference_audio.filename or "reference.wav")
    consent_result = await _transcribe_audio(consent_bytes, language, consent_audio.filename or "consent.wav")

    ref_transcript = ref_result.get("transcript", "").strip()
    consent_transcript = consent_result.get("transcript", "").strip()

    # Validate reference: must have meaningful speech
    ref_valid = len(ref_transcript) > 10
    ref_message = "Valid speech detected" if ref_valid else "Too short or silent - please record a longer voice sample"

    # Validate consent: fuzzy match against expected script
    expected_script = CONSENT_SCRIPTS[language]
    similarity = difflib.SequenceMatcher(
        None,
        consent_transcript.lower(),
        expected_script.lower(),
    ).ratio()
    consent_valid = similarity > 0.75
    consent_message = (
        f"Matched ({similarity:.0%} similarity)"
        if consent_valid
        else f"Does not match consent script ({similarity:.0%} similarity). Please read the script exactly."
    )

    return {
        "valid": ref_valid and consent_valid,
        "reference": {
            "valid": ref_valid,
            "transcript": ref_transcript,
            "message": ref_message,
        },
        "consent": {
            "valid": consent_valid,
            "transcript": consent_transcript,
            "similarity": round(similarity, 3),
            "expected_script": expected_script,
            "message": consent_message,
        },
    }


@router.post("/generate-key")
async def generate_voice_key(
    company_id: str,
    executive_id: str,
    reference_audio: UploadFile = File(..., description="Reference voice sample"),
    consent_audio: UploadFile = File(..., description="Consent recording"),
    language: str = Form("en", description="Language: 'en' or 'ja'"),
    request: Request = None,
):
    """
    Generate a voice cloning key via Google Chirp3 API and store in database.

    Re-validates via STT, then calls Google's generateVoiceCloningKey endpoint.
    Merges the new key with any existing keys (preserves other language's key).
    """
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    if not GCP_PROJECT_ID:
        raise HTTPException(status_code=503, detail="Voice cloning is not configured: set GCP_VOICE_CLONING_PROJECT_ID or GCP_PROJECT_ID.")

    if language not in CONSENT_SCRIPTS:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}. Use 'en' or 'ja'.")

    language_code = LANGUAGE_CODE_MAP[language]

    # Read audio files
    ref_bytes = await reference_audio.read()
    consent_bytes = await consent_audio.read()

    # Re-validate via STT
    ref_result = await _transcribe_audio(ref_bytes, language, reference_audio.filename or "reference.wav")
    consent_result = await _transcribe_audio(consent_bytes, language, consent_audio.filename or "consent.wav")

    ref_transcript = ref_result.get("transcript", "").strip()
    consent_transcript = consent_result.get("transcript", "").strip()

    if len(ref_transcript) <= 10:
        raise HTTPException(
            status_code=400,
            detail="Reference audio validation failed: too short or silent.",
        )

    expected_script = CONSENT_SCRIPTS[language]
    similarity = difflib.SequenceMatcher(
        None, consent_transcript.lower(), expected_script.lower()
    ).ratio()
    if similarity <= 0.75:
        raise HTTPException(
            status_code=400,
            detail=f"Consent audio validation failed: {similarity:.0%} similarity (need >75%).",
        )

    # Call Google Chirp3 generateVoiceCloningKey API
    try:
        access_token = _get_gcp_access_token()
    except Exception as e:
        logger.error(f"Failed to get GCP access token: {e}")
        raise HTTPException(status_code=500, detail=f"GCP authentication failed: {e}")

    ref_b64 = base64.b64encode(ref_bytes).decode("ascii")
    consent_b64 = base64.b64encode(consent_bytes).decode("ascii")

    api_url = "https://texttospeech.googleapis.com/v1beta1/voices:generateVoiceCloningKey"
    payload = {
        "reference_audio": {
            "audio_config": {"audio_encoding": "LINEAR16", "sample_rate_hertz": 24000},
            "content": ref_b64,
        },
        "voice_talent_consent": {
            "audio_config": {"audio_encoding": "LINEAR16", "sample_rate_hertz": 24000},
            "content": consent_b64,
        },
        "consent_script": expected_script,
        "language_code": language_code,
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-goog-user-project": GCP_PROJECT_ID,
        "Content-Type": "application/json; charset=utf-8",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Chirp3 API error: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=502,
                detail=f"Google voice cloning API failed: {e.response.text}",
            )
        except httpx.RequestError as e:
            logger.error(f"Chirp3 API request error: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Could not reach Google voice cloning API: {e}",
            )

    voice_cloning_key = result.get("voiceCloningKey")
    if not voice_cloning_key:
        raise HTTPException(
            status_code=502,
            detail="Google API did not return a voiceCloningKey.",
        )

    # Merge with existing keys (preserve other language)
    existing_keys = await executives.get_voice_keys(pool, executive_id, company_id=company_id) or {}
    existing_keys[language_code] = voice_cloning_key
    await executives.update_voice_keys(pool, executive_id, company_id, existing_keys)

    logger.info(
        f"Voice key generated for {executive_id} ({language_code}): {len(voice_cloning_key)} chars"
    )

    # Invalidate TTS cache on RAG service
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{RAG_SERVICE_URL}/api/v1/voice/reload-keys/{executive_id}"
            )
    except Exception as e:
        logger.warning(f"Failed to invalidate TTS cache (non-fatal): {e}")

    return {
        "success": True,
        "language": language_code,
        "key_length": len(voice_cloning_key),
    }


@router.get("/keys")
async def get_voice_keys_status(
    company_id: str,
    executive_id: str,
    request: Request = None,
):
    """Get voice key status for an executive."""
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    keys = await executives.get_voice_keys(pool, executive_id, company_id=company_id) or {}

    return {
        "executive_id": executive_id,
        "keys": {
            "en-US": {
                "exists": "en-US" in keys,
                "key_length": len(keys["en-US"]) if "en-US" in keys else 0,
            },
            "ja-JP": {
                "exists": "ja-JP" in keys,
                "key_length": len(keys["ja-JP"]) if "ja-JP" in keys else 0,
            },
        },
    }


@router.delete("/keys/{language}")
async def delete_voice_key(
    company_id: str,
    executive_id: str,
    language: str,
    request: Request = None,
):
    """Delete a specific language's voice key."""
    pool = request.app.state.pool
    await _validate_executive_company(pool, company_id, executive_id)

    language_code = LANGUAGE_CODE_MAP.get(language, language)
    if language_code not in ("en-US", "ja-JP"):
        raise HTTPException(status_code=400, detail=f"Invalid language: {language}")

    keys = await executives.get_voice_keys(pool, executive_id, company_id=company_id) or {}

    if language_code not in keys:
        raise HTTPException(
            status_code=404,
            detail=f"No voice key for {language_code}",
        )

    del keys[language_code]

    if keys:
        await executives.update_voice_keys(pool, executive_id, company_id, keys)
    else:
        # No keys left - set to NULL
        await pool.execute(
            "UPDATE executive_profiles SET voice_keys = NULL, updated_at = NOW() WHERE id = $1 AND company_id = $2",
            executive_id,
            company_id,
        )

    # Invalidate TTS cache
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{RAG_SERVICE_URL}/api/v1/voice/reload-keys/{executive_id}"
            )
    except Exception as e:
        logger.warning(f"Failed to invalidate TTS cache (non-fatal): {e}")

    return {"success": True, "deleted": language_code}
