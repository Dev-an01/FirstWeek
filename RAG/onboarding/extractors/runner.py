"""
Extraction Runner - Orchestrates concurrent extractions.

Runs extractors via ThreadPoolExecutor, reports progress,
collects errors without blocking other extractors.
Supports selective extraction for calibration.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Callable, Optional, List

from onboarding.config import EXTRACTION_WORKERS
from .background_identity import BackgroundIdentityExtractor
from .thinking_patterns import ThinkingPatternsExtractor
from .communication_style import CommunicationStyleExtractor
from .values_decisions import ValuesDecisionsExtractor
from .domain_tech import DomainTechExtractor
from .red_flags_inference import RedFlagsInferenceExtractor
from .speaking_patterns import SpeakingPatternsExtractor

logger = logging.getLogger(__name__)

# All 7 extractors in order
EXTRACTORS = [
    ("background_identity", BackgroundIdentityExtractor),
    ("thinking_patterns", ThinkingPatternsExtractor),
    ("communication_style", CommunicationStyleExtractor),
    ("values_decisions", ValuesDecisionsExtractor),
    ("domain_tech", DomainTechExtractor),
    ("red_flags_inference", RedFlagsInferenceExtractor),
    ("speaking_patterns", SpeakingPatternsExtractor),
]

# Mapping for quick lookup
EXTRACTOR_MAP = {name: cls for name, cls in EXTRACTORS}

# All extractor names for validation
ALL_EXTRACTOR_NAMES = [name for name, _ in EXTRACTORS]


def run_all_extractions(
    document_text: str,
    progress_callback: Optional[Callable[[str, str], None]] = None,
    extractors_to_run: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run extractors concurrently.

    Args:
        document_text: Combined text from all uploaded documents.
        progress_callback: Optional callback(extractor_name, status) for progress.
        extractors_to_run: Optional list of extractor names to run.
            If None, runs all 7 extractors.
            Valid names: background_identity, thinking_patterns, communication_style,
                        values_decisions, domain_tech, red_flags_inference, speaking_patterns

    Returns:
        Dict mapping extractor name to its extraction result (or error dict).
    """
    # Determine which extractors to run
    if extractors_to_run is None:
        extractors = EXTRACTORS
    else:
        # Validate extractor names
        invalid_names = [n for n in extractors_to_run if n not in EXTRACTOR_MAP]
        if invalid_names:
            logger.warning(f"Invalid extractor names ignored: {invalid_names}")

        extractors = [
            (name, EXTRACTOR_MAP[name])
            for name in extractors_to_run
            if name in EXTRACTOR_MAP
        ]

        if not extractors:
            logger.error("No valid extractors to run")
            return {}

    results: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    def _run_one(name: str, cls):
        if progress_callback:
            progress_callback(name, "started")
        extractor = cls()
        result = extractor.extract(document_text)
        if progress_callback:
            status = "failed" if "error" in result else "completed"
            progress_callback(name, status)
        return name, result

    with ThreadPoolExecutor(max_workers=EXTRACTION_WORKERS) as executor:
        futures = {
            executor.submit(_run_one, name, cls): name
            for name, cls in extractors
        }

        for future in as_completed(futures):
            ext_name = futures[future]
            try:
                name, result = future.result()
                results[name] = result
                if "error" in result:
                    errors[name] = result["error"]
                    logger.warning(f"Extractor {name} returned error: {result['error']}")
                else:
                    logger.info(f"Extractor {name} completed successfully")
            except Exception as e:
                logger.error(f"Extractor {ext_name} raised exception: {e}")
                results[ext_name] = {"error": str(e), "extractor": ext_name}
                errors[ext_name] = str(e)

    logger.info(
        f"Extraction complete: {len(results) - len(errors)}/{len(extractors)} succeeded, "
        f"{len(errors)} errors"
    )
    return results


def get_available_extractors() -> List[str]:
    """Return list of all available extractor names."""
    return ALL_EXTRACTOR_NAMES.copy()
