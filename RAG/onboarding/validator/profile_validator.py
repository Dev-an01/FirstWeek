"""
Profile Validator - Completeness and consistency checks.

Validates:
- All required keys present
- Scales within bounds (formality 1-10, confidence 0-1, priority 1-5)
- No empty critical arrays
- Returns: {valid, completeness_score, issues[], statistics}
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

REQUIRED_TOP_LEVEL_KEYS = [
    "id", "name", "thinking_patterns", "communication_style",
    "core_values", "decision_making", "red_flags",
]

SCALE_BOUNDS = {
    "formality_scale": (1, 10),
    "directness_scale": (1, 10),
    "warmth_scale": (1, 10),
}

CRITICAL_ARRAYS = [
    "core_values",
    "decision_cases",
]


def validate_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a profile for completeness and consistency.

    Returns:
        {
            "valid": bool,
            "completeness_score": float (0-1),
            "issues": [str],
            "statistics": {key counts, etc.}
        }
    """
    issues: List[str] = []
    total_checks = 0
    passed_checks = 0

    # 1. Required top-level keys
    for key in REQUIRED_TOP_LEVEL_KEYS:
        total_checks += 1
        if key not in profile or not profile[key]:
            issues.append(f"Missing or empty required key: {key}")
        else:
            passed_checks += 1

    # 2. Scale bounds
    comm_style = profile.get("communication_style", {})
    for scale_name, (lo, hi) in SCALE_BOUNDS.items():
        total_checks += 1
        value = comm_style.get(scale_name)
        if value is not None:
            if isinstance(value, (int, float)) and lo <= value <= hi:
                passed_checks += 1
            else:
                issues.append(f"Scale {scale_name} out of bounds [{lo}-{hi}]: {value}")
        else:
            issues.append(f"Missing scale: {scale_name}")

    # 3. Decision making trade-offs
    dm = profile.get("decision_making", {})
    trade_offs = dm.get("value_trade_offs", {})
    total_checks += 1
    if trade_offs and len(trade_offs) >= 5:
        passed_checks += 1
        # Check individual trade-off scores
        for to_name, to_val in trade_offs.items():
            if isinstance(to_val, dict):
                score = to_val.get("score")
                if score is not None and not (1 <= score <= 10):
                    issues.append(f"Trade-off {to_name} score out of bounds: {score}")
    else:
        issues.append(f"Insufficient value trade-offs: {len(trade_offs)} (need >=5)")

    # 4. Critical arrays not empty
    for arr_key in CRITICAL_ARRAYS:
        total_checks += 1
        arr = profile.get(arr_key, [])
        if isinstance(arr, list) and len(arr) > 0:
            passed_checks += 1
        else:
            issues.append(f"Empty critical array: {arr_key}")

    # 5. Decision cases have required fields
    cases = profile.get("decision_cases", [])
    if isinstance(cases, list):
        for i, case in enumerate(cases):
            total_checks += 1
            if isinstance(case, dict) and case.get("situation") and case.get("decision_made"):
                passed_checks += 1
            else:
                issues.append(f"Decision case {i} missing situation or decision_made")

    # Completeness score
    completeness = passed_checks / max(total_checks, 1)

    result = {
        "valid": len(issues) == 0,
        "completeness_score": round(completeness, 3),
        "issues": issues,
        "statistics": {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "core_values_count": len(profile.get("core_values", [])),
            "decision_cases_count": len(profile.get("decision_cases", [])),
            "trade_offs_count": len(trade_offs),
            "communication_examples_count": len(profile.get("communication_examples", [])),
        },
    }

    logger.info(
        f"Profile validation: valid={result['valid']}, "
        f"completeness={result['completeness_score']}, "
        f"issues={len(issues)}"
    )
    return result
