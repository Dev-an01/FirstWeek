"""
Profile Assembler - Merges extraction outputs into a profile JSON.

Structure matches sample_profile.json (19 sections).
Supports both full assembly and incremental merge for calibration.
"""

import logging
from typing import Dict, Any, Optional, List
from copy import deepcopy

logger = logging.getLogger(__name__)


# Mapping from extractor name to profile sections it populates
EXTRACTOR_SECTION_MAP = {
    "background_identity": ["background", "company_info", "leadership_team"],
    "thinking_patterns": ["thinking_patterns"],
    "communication_style": ["communication_style"],
    "values_decisions": ["core_values", "decision_making", "decision_cases"],
    "domain_tech": ["domain_affinity", "tech_opinions"],
    "red_flags_inference": ["red_flags", "inference_framework"],
    "speaking_patterns": [],  # Speaking patterns populate voiceprint, not profile
}


def _get_sections_from_extraction(
    extractor_name: str,
    extraction: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract profile sections from a single extractor's output.

    Args:
        extractor_name: Name of the extractor.
        extraction: Extraction result dict.

    Returns:
        Dict of section_name -> section_data.
    """
    sections = {}

    if extractor_name == "background_identity":
        sections["background"] = extraction.get("background", {})
        sections["company_info"] = extraction.get("company_info", {})
        sections["leadership_team"] = extraction.get("leadership_team", [])

    elif extractor_name == "thinking_patterns":
        sections["thinking_patterns"] = extraction.get("thinking_patterns", {})

    elif extractor_name == "communication_style":
        sections["communication_style"] = extraction.get("communication_style", {})

    elif extractor_name == "values_decisions":
        sections["core_values"] = extraction.get("core_values", [])
        sections["decision_making"] = extraction.get("decision_making", {})
        sections["decision_cases"] = extraction.get("decision_cases", [])

    elif extractor_name == "domain_tech":
        sections["domain_affinity"] = extraction.get("domain_affinity", {})
        sections["tech_opinions"] = extraction.get("tech_opinions", {})

    elif extractor_name == "red_flags_inference":
        sections["red_flags"] = extraction.get("red_flags", {})
        sections["inference_framework"] = extraction.get("inference_framework", {})

    return sections


def merge_profiles(
    existing_profile: Dict[str, Any],
    extractions: Dict[str, Any],
    merge_strategy: str = "replace",
) -> Dict[str, Any]:
    """
    Merge new extractions into an existing profile.

    Args:
        existing_profile: Current profile data.
        extractions: New extraction results (may be partial).
        merge_strategy: How to merge - "replace" (default) or "merge".
            - "replace": Replace entire sections from new extractions
            - "merge": Deep merge new data into existing sections

    Returns:
        Merged profile.
    """
    result = deepcopy(existing_profile)

    for extractor_name, extraction in extractions.items():
        if "error" in extraction:
            logger.warning(f"Skipping failed extractor {extractor_name} during merge")
            continue

        sections = _get_sections_from_extraction(extractor_name, extraction)

        for section_name, section_data in sections.items():
            if merge_strategy == "replace":
                # Replace entire section
                result[section_name] = section_data
            else:
                # Deep merge
                if section_name not in result:
                    result[section_name] = section_data
                elif isinstance(result[section_name], dict) and isinstance(section_data, dict):
                    result[section_name] = {**result[section_name], **section_data}
                elif isinstance(result[section_name], list) and isinstance(section_data, list):
                    # For lists, replace (merging lists is ambiguous)
                    result[section_name] = section_data
                else:
                    result[section_name] = section_data

    # Update metadata
    if "metadata" not in result:
        result["metadata"] = {}

    result["metadata"]["last_calibration"] = {
        "extractors_run": list(extractions.keys()),
        "merge_strategy": merge_strategy,
    }

    logger.info(f"Merged {len(extractions)} extractions into profile using '{merge_strategy}' strategy")
    return result


def assemble_profile(
    executive_id: str,
    executive_info: Dict[str, Any],
    extractions: Dict[str, Any],
    existing_profile: Optional[Dict[str, Any]] = None,
    merge_strategy: str = "replace",
) -> Dict[str, Any]:
    """
    Assemble a complete executive profile from extraction results.

    For incremental calibration, pass existing_profile to merge new extractions.

    Args:
        executive_id: Executive ID (slug).
        executive_info: Basic executive info (name, title, department, company, etc.).
        extractions: Dict of extractor_name -> extraction result.
        existing_profile: Optional existing profile for incremental merge.
        merge_strategy: How to merge - "replace" or "merge" (for incremental).

    Returns:
        Complete profile JSON matching the reference structure.
    """
    # If we have an existing profile and this is incremental, merge
    if existing_profile is not None:
        return merge_profiles(existing_profile, extractions, merge_strategy)

    # Full assembly from scratch
    bg = extractions.get("background_identity", {})
    tp = extractions.get("thinking_patterns", {})
    cs = extractions.get("communication_style", {})
    vd = extractions.get("values_decisions", {})
    dt = extractions.get("domain_tech", {})
    rf = extractions.get("red_flags_inference", {})
    sp = extractions.get("speaking_patterns", {})

    # Build the profile matching sample_profile.json structure
    profile = {
        "id": executive_id,
        "name": executive_info.get("name", ""),
        "name_english": executive_info.get("name_english", ""),
        "title": executive_info.get("title", ""),
        "department": executive_info.get("department", ""),
        "company": executive_info.get("company", ""),
        "email": executive_info.get("email", ""),

        # From extractor 1
        "background": bg.get("background", {}),
        "company_info": bg.get("company_info", {}),
        "leadership_team": bg.get("leadership_team", []),

        # From extractor 2
        "thinking_patterns": tp.get("thinking_patterns", {}),

        # From extractor 3
        "communication_style": cs.get("communication_style", {}),

        # From extractor 4
        "core_values": vd.get("core_values", []),
        "decision_making": vd.get("decision_making", {}),
        "decision_cases": vd.get("decision_cases", []),

        # From extractor 5
        "domain_affinity": dt.get("domain_affinity", {}),
        "tech_opinions": dt.get("tech_opinions", {}),

        # From extractor 6
        "red_flags": rf.get("red_flags", {}),
        "inference_framework": rf.get("inference_framework", {}),

        # Will be filled by synthesis LLM
        "communication_examples": [],

        # Metadata
        "metadata": {
            "generated_by": "onboarding_service",
            "version": "1.0",
            "extractors_succeeded": [
                name for name, result in extractions.items()
                if "error" not in result
            ],
            "extractors_failed": [
                name for name, result in extractions.items()
                if "error" in result
            ],
        },
    }

    logger.info(f"Profile assembled for {executive_id} with {len(profile)} top-level keys")
    return profile


def get_affected_sections(extractor_names: List[str]) -> List[str]:
    """
    Get list of profile sections affected by given extractors.

    Args:
        extractor_names: List of extractor names.

    Returns:
        List of profile section names that would be updated.
    """
    sections = set()
    for name in extractor_names:
        if name in EXTRACTOR_SECTION_MAP:
            sections.update(EXTRACTOR_SECTION_MAP[name])
    return list(sections)
