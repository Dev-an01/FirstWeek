"""
DB Deployer - Writes assembled profile and voiceprint to PostgreSQL.

- UPSERT executive_profiles (profile_data JSONB, voiceprint_data JSONB, company_id, scales)
- INSERT decision_cases rows (one per case, linked by executive_id)
- Update onboarding_jobs status
"""

import json
import logging
from datetime import date, datetime
from typing import Dict, Any, List, Optional
import asyncpg

from onboarding.utils.id_generator import generate_case_id

logger = logging.getLogger(__name__)


async def deploy_to_database(
    pool: asyncpg.Pool,
    executive_id: str,
    company_id: str,
    profile: Dict[str, Any],
    voiceprint: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Deploy the assembled profile and voiceprint to the database.

    Args:
        pool: asyncpg connection pool.
        executive_id: Executive ID.
        company_id: Company ID.
        profile: Assembled profile dict.
        voiceprint: Assembled voiceprint dict.

    Returns:
        Deployment summary.
    """
    results = {"executive_updated": False, "decision_cases_inserted": 0, "errors": []}

    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. UPSERT executive_profiles
            try:
                comm_style = profile.get("communication_style", {})
                formality = comm_style.get("formality_scale", 5)
                directness = comm_style.get("directness_scale", 5)
                warmth = comm_style.get("warmth_scale", 5)

                await conn.execute(
                    """
                    UPDATE executive_profiles
                    SET profile_data = $2,
                        voiceprint_data = $3,
                        company_id = $4,
                        formality_scale = $5,
                        directness_scale = $6,
                        warmth_scale = $7
                    WHERE id = $1
                    """,
                    executive_id,
                    profile,
                    voiceprint,
                    company_id,
                    formality,
                    directness,
                    warmth,
                )
                results["executive_updated"] = True
                logger.info(f"Updated executive_profiles for {executive_id}")
            except Exception as e:
                msg = f"Failed to update executive_profiles: {e}"
                logger.error(msg)
                results["errors"].append(msg)
                raise

            # 2. INSERT decision_cases with deterministic IDs
            decision_cases = profile.get("decision_cases", [])
            if decision_cases:
                try:
                    # Delete existing cases for this executive (replace strategy)
                    await conn.execute(
                        "DELETE FROM decision_cases WHERE executive_id = $1 AND company_id = $2",
                        executive_id,
                        company_id,
                    )

                    for i, case in enumerate(decision_cases):
                        case_id = generate_case_id(executive_id, i)
                        full_content = {
                            "rationale": case.get("rationale", ""),
                            "lessons_learned": case.get("lessons_learned", ""),
                        }

                        # Parse date string to date object for asyncpg
                        raw_date = case.get("date")
                        case_date: Optional[date] = None
                        if raw_date:
                            try:
                                if isinstance(raw_date, str):
                                    case_date = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
                                elif isinstance(raw_date, date):
                                    case_date = raw_date
                            except (ValueError, TypeError):
                                case_date = None

                        # Fallback to today if date is still None
                        if case_date is None:
                            case_date = date.today()

                        await conn.execute(
                            """
                            INSERT INTO decision_cases (
                                id, executive_id, company_id, title, date, category,
                                situation, decision_made, rationale, outcome,
                                lessons_learned, confidence, precedent, full_content
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                            """,
                            case_id,
                            executive_id,
                            company_id,
                            case.get("title", "Untitled"),
                            case_date,
                            case.get("category", "general"),
                            case.get("situation", ""),
                            case.get("decision_made", ""),
                            case.get("rationale", ""),
                            case.get("outcome", ""),
                            case.get("lessons_learned", ""),
                            case.get("confidence", 0.7),
                            case.get("is_precedent", False),
                            full_content,
                        )
                        results["decision_cases_inserted"] += 1

                    logger.info(f"Inserted {results['decision_cases_inserted']} decision cases for {executive_id}")
                except Exception as e:
                    msg = f"Failed to insert decision_cases: {e}"
                    logger.error(msg)
                    results["errors"].append(msg)
                    raise

    return results
