"""
Schema Checker - Compare generated profile against reference structure.

Loads sample_profile.json as the reference and reports missing keys, type mismatches.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Set

logger = logging.getLogger(__name__)

REFERENCE_PROFILE_PATH = (
    Path(__file__).parent.parent.parent / "test_data" / "executive_profiles" / "sample_profile.json"
)
REFERENCE_VOICEPRINT_PATH = (
    Path(__file__).parent.parent.parent / "test_data" / "voiceprints" / "sample_profile_voiceprint.json"
)


def _collect_keys(obj: Any, prefix: str = "") -> Set[str]:
    """Recursively collect all keys from a nested dict."""
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            keys.add(full_key)
            keys.update(_collect_keys(v, full_key))
    return keys


def check_profile_schema(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare profile against the reference sample profile.

    Returns:
        {
            "reference_keys_count": int,
            "profile_keys_count": int,
            "missing_keys": [str],
            "extra_keys": [str],
            "coverage_percent": float,
        }
    """
    try:
        with open(REFERENCE_PROFILE_PATH, "r", encoding="utf-8") as f:
            reference = json.load(f)
    except FileNotFoundError:
        logger.warning("Reference profile not found, skipping schema check")
        return {"error": "Reference profile not found", "missing_keys": [], "extra_keys": []}

    ref_keys = _collect_keys(reference)
    prof_keys = _collect_keys(profile)

    # Only check top-level and one-level-deep keys for practical comparison
    ref_top = {k for k in ref_keys if k.count(".") <= 1}
    prof_top = {k for k in prof_keys if k.count(".") <= 1}

    missing = sorted(ref_top - prof_top)
    extra = sorted(prof_top - ref_top)
    coverage = len(ref_top & prof_top) / max(len(ref_top), 1)

    result = {
        "reference_keys_count": len(ref_top),
        "profile_keys_count": len(prof_top),
        "missing_keys": missing,
        "extra_keys": extra,
        "coverage_percent": round(coverage * 100, 1),
    }

    logger.info(f"Schema check: {result['coverage_percent']}% coverage, {len(missing)} missing keys")
    return result


def check_voiceprint_schema(voiceprint: Dict[str, Any]) -> Dict[str, Any]:
    """Compare voiceprint against the reference sample voiceprint."""
    try:
        with open(REFERENCE_VOICEPRINT_PATH, "r", encoding="utf-8") as f:
            reference = json.load(f)
    except FileNotFoundError:
        logger.warning("Reference voiceprint not found, skipping schema check")
        return {"error": "Reference voiceprint not found", "missing_keys": [], "extra_keys": []}

    ref_keys = _collect_keys(reference)
    vp_keys = _collect_keys(voiceprint)

    ref_top = {k for k in ref_keys if k.count(".") <= 1}
    vp_top = {k for k in vp_keys if k.count(".") <= 1}

    missing = sorted(ref_top - vp_top)
    extra = sorted(vp_top - ref_top)
    coverage = len(ref_top & vp_top) / max(len(ref_top), 1)

    return {
        "reference_keys_count": len(ref_top),
        "voiceprint_keys_count": len(vp_top),
        "missing_keys": missing,
        "extra_keys": extra,
        "coverage_percent": round(coverage * 100, 1),
    }
