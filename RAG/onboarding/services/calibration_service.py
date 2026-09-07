"""
Calibration Service - Orchestrates profile re-extraction and calibration.

Supports full calibration (re-run everything) and incremental calibration
(specific extractors only with merge strategy).
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
import asyncpg

from onboarding.models import CalibrationMode, MergeStrategy, JobType
from onboarding.db import jobs, executives, documents
from onboarding.services.document_service import DocumentService
from onboarding.services.profile_service import ProfileService

logger = logging.getLogger(__name__)


class CalibrationService:
    """Service for calibrating executive profiles."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def start_calibration(
        self,
        company_id: str,
        executive_id: str,
        mode: CalibrationMode = CalibrationMode.FULL,
        extractors: Optional[List[str]] = None,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        regenerate_embeddings: bool = True,
    ) -> Dict[str, Any]:
        """
        Start a calibration job.

        Args:
            company_id: Company ID.
            executive_id: Executive ID.
            mode: Calibration mode - FULL or INCREMENTAL.
            extractors: For incremental mode, list of extractors to run.
            merge_strategy: For incremental mode, how to merge results.
            regenerate_embeddings: Whether to regenerate embeddings after.

        Returns:
            Job dict with id and status.
        """
        # Get combined PROFILE document text (public + internal only)
        # Executive/confidential docs are excluded to prevent data leaks via profile_data
        doc_service = DocumentService(self.pool)
        combined_text = await doc_service.get_combined_extractable_text(company_id, executive_id)

        if not combined_text:
            raise ValueError(
                f"No extractable documents found for executive '{executive_id}'. "
                f"Upload documents with 'public' or 'internal' access level for profile extraction."
            )

        # Get executive info
        exec_row = await executives.get_executive(self.pool, executive_id)
        if not exec_row:
            raise ValueError(f"Executive '{executive_id}' not found")

        # Create calibration job
        job = await jobs.create_job(
            self.pool,
            company_id,
            executive_id,
            JobType.CALIBRATION.value,
        )
        job_id = str(job["id"])

        # Store calibration metadata on job
        await self._update_calibration_meta(
            job_id,
            mode.value,
            [e.value if hasattr(e, 'value') else e for e in (extractors or [])],
            merge_strategy.value,
        )

        # Launch background calibration
        asyncio.create_task(
            self._run_calibration(
                job_id=job_id,
                company_id=company_id,
                executive_id=executive_id,
                exec_info=exec_row,
                document_text=combined_text,
                mode=mode,
                extractors=extractors,
                merge_strategy=merge_strategy,
                regenerate_embeddings=regenerate_embeddings,
            )
        )

        return {
            "id": job_id,
            "status": "started",
            "mode": mode.value,
            "extractors": [e.value if hasattr(e, 'value') else e for e in (extractors or [])] if extractors else None,
        }

    async def _update_calibration_meta(
        self,
        job_id: str,
        mode: str,
        extractors: List[str],
        merge_strategy: str,
    ):
        """Store calibration-specific metadata on the job."""
        # Pass list directly - asyncpg's jsonb codec handles serialization
        await self.pool.execute(
            """
            UPDATE onboarding_jobs
            SET calibration_mode = $2,
                extractors_run = $3,
                merge_strategy = $4,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            job_id,
            mode,
            extractors,
            merge_strategy,
        )

    async def _run_calibration(
        self,
        job_id: str,
        company_id: str,
        executive_id: str,
        exec_info: Dict[str, Any],
        document_text: str,
        mode: CalibrationMode,
        extractors: Optional[List[str]],
        merge_strategy: MergeStrategy,
        regenerate_embeddings: bool,
    ):
        """
        Run calibration pipeline (background task).

        Similar to full onboarding but supports incremental mode.
        """
        try:
            # ---- Step 1: Prepare ----
            await jobs.update_job_status(self.pool, job_id, "extracting", 10.0)

            # Determine which extractors to run
            extractors_to_run = None
            if mode == CalibrationMode.INCREMENTAL and extractors:
                extractors_to_run = [
                    e.value if hasattr(e, 'value') else e for e in extractors
                ]

            # ---- Step 2: Run extractions ----
            loop = asyncio.get_event_loop()
            from onboarding.extractors.runner import run_all_extractions

            extraction_results = await loop.run_in_executor(
                None,
                run_all_extractions,
                document_text,
                None,  # progress_callback
                extractors_to_run,
            )

            await jobs.update_job_extraction(self.pool, job_id, extraction_results)
            await jobs.update_job_status(self.pool, job_id, "assembling", 50.0)

            # ---- Step 3: Assemble profile ----
            from onboarding.assembler.profile_assembler import assemble_profile
            from onboarding.assembler.voiceprint_assembler import assemble_voiceprint

            # For incremental mode, get existing profile
            existing_profile = None
            existing_voiceprint = None

            if mode == CalibrationMode.INCREMENTAL:
                profile_service = ProfileService(self.pool)
                existing_profile = await profile_service.get_profile(company_id, executive_id)
                existing_voiceprint = await profile_service.get_voiceprint(company_id, executive_id)

            # Assemble profile (with merge for incremental)
            profile = assemble_profile(
                executive_id,
                exec_info,
                extraction_results,
                existing_profile=existing_profile,
                merge_strategy=merge_strategy.value,
            )

            # Assemble voiceprint (only if speaking_patterns extractor ran)
            if extractors_to_run is None or "speaking_patterns" in extractors_to_run:
                voiceprint = assemble_voiceprint(executive_id, extraction_results)
                # Merge with existing if incremental
                if mode == CalibrationMode.INCREMENTAL and existing_voiceprint:
                    voiceprint = {**existing_voiceprint, **voiceprint}
            else:
                voiceprint = existing_voiceprint or {}

            # ---- Step 4: Synthesis LLM pass (only for full calibration) ----
            if mode == CalibrationMode.FULL:
                from onboarding.assembler.synthesis_llm import run_synthesis, apply_synthesis
                synthesis_result = await loop.run_in_executor(None, run_synthesis, profile, voiceprint)
                profile, voiceprint = apply_synthesis(profile, voiceprint, synthesis_result)

            await jobs.update_job_assembled(self.pool, job_id, profile, voiceprint)
            await jobs.update_job_status(self.pool, job_id, "validating", 70.0)

            # ---- Step 5: Validate ----
            from onboarding.validator.profile_validator import validate_profile
            from onboarding.validator.schema_checker import check_profile_schema, check_voiceprint_schema

            validation_result = validate_profile(profile)
            schema_result = check_profile_schema(profile)
            vp_schema_result = check_voiceprint_schema(voiceprint)

            full_validation = {
                "profile_validation": validation_result,
                "profile_schema": schema_result,
                "voiceprint_schema": vp_schema_result,
                "calibration_mode": mode.value,
            }
            await jobs.update_job_validation(self.pool, job_id, full_validation)

            # ---- Step 6: Deploy to PostgreSQL ----
            await jobs.update_job_status(self.pool, job_id, "deploying", 80.0)

            from onboarding.deployer.db_deployer import deploy_to_database
            deploy_result = await deploy_to_database(self.pool, executive_id, company_id, profile, voiceprint)
            logger.info(f"[{job_id}] Deploy result: {deploy_result}")

            # ---- Step 6b: Deploy to Neo4j (graph database) ----
            try:
                from onboarding.deployer.neo4j_deployer import get_neo4j_deployer
                from onboarding.db.companies import get_company

                logger.info(f"[{job_id}] Starting Neo4j deployment...")
                logger.info(f"[{job_id}] exec_info keys: {list(exec_info.keys()) if exec_info else 'None'}")

                neo4j_deployer = await get_neo4j_deployer()
                logger.info(f"[{job_id}] Neo4j deployer connected: {neo4j_deployer.is_connected}")

                company_data = await get_company(self.pool, company_id)
                logger.info(f"[{job_id}] Company data: {company_data.get('id') if company_data else 'None'}")

                if company_data and neo4j_deployer.is_connected:
                    # Ensure exec_info has required fields
                    neo4j_exec_data = {
                        "id": exec_info.get("id", executive_id),
                        "name": exec_info.get("name", ""),
                        "name_english": exec_info.get("name_english", ""),
                        "title": exec_info.get("title", ""),
                        "department": exec_info.get("department", ""),
                        "email": exec_info.get("email", ""),
                        "hierarchy_level": exec_info.get("hierarchy_level", 4),
                    }
                    logger.info(f"[{job_id}] Neo4j exec data: {neo4j_exec_data}")

                    neo4j_result = await neo4j_deployer.deploy_onboarding_result(
                        company_data=company_data,
                        executive_data=neo4j_exec_data,
                        profile_data=profile,
                    )
                    logger.info(f"[{job_id}] Neo4j deploy result: {neo4j_result}")
                else:
                    reason = "not connected" if not neo4j_deployer.is_connected else "no company data"
                    logger.info(f"[{job_id}] Neo4j skipped ({reason})")
            except Exception as neo4j_err:
                # Neo4j failure should not fail the whole pipeline
                import traceback
                logger.warning(f"[{job_id}] Neo4j deploy failed (non-critical): {neo4j_err}")
                logger.warning(f"[{job_id}] Neo4j traceback: {traceback.format_exc()}")

            # ---- Step 7: Trigger embedding generation (optional) ----
            if regenerate_embeddings:
                await jobs.update_job_status(self.pool, job_id, "embedding", 90.0)

                from onboarding.deployer.embedding_trigger import trigger_embeddings
                embed_result = await trigger_embeddings(executive_id, company_id, profile, voiceprint, self.pool)
                logger.info(f"[{job_id}] Embedding trigger: {embed_result.get('status', 'unknown')}")

            # ---- Done ----
            await jobs.update_job_status(self.pool, job_id, "completed", 100.0)
            logger.info(f"[{job_id}] Calibration completed for {executive_id} (mode: {mode.value})")

            # Notify RAG API to refresh cached profile
            try:
                from onboarding.utils.rag_notifier import notify_rag_profile_refresh
                await notify_rag_profile_refresh(company_id, executive_id, reason="calibration")
            except Exception as notify_err:
                logger.warning(f"[{job_id}] RAG refresh notification failed (non-fatal): {notify_err}")

        except Exception as e:
            logger.error(f"[{job_id}] Calibration failed: {e}", exc_info=True)
            await jobs.update_job_status(self.pool, job_id, "failed", error_message=str(e))

    async def trigger_embeddings_only(
        self,
        company_id: str,
        executive_id: str,
    ) -> Dict[str, Any]:
        """
        Trigger embedding regeneration without re-extraction.

        Used after profile/voiceprint edits.

        Args:
            company_id: Company ID.
            executive_id: Executive ID.

        Returns:
            Job dict with id and status.
        """
        # Get current profile and voiceprint
        profile_service = ProfileService(self.pool)
        data = await profile_service.get_profile_with_voiceprint(company_id, executive_id)

        if not data["profile"]:
            raise ValueError(f"No profile found for executive '{executive_id}'")

        # Create a minimal job for tracking
        job = await jobs.create_job(
            self.pool,
            company_id,
            executive_id,
            "embedding_only",
        )
        job_id = str(job["id"])

        # Launch background embedding task
        asyncio.create_task(
            self._run_embeddings_only(
                job_id=job_id,
                company_id=company_id,
                executive_id=executive_id,
                profile=data["profile"],
                voiceprint=data["voiceprint"],
            )
        )

        return {
            "id": job_id,
            "status": "started",
            "mode": "embedding_only",
        }

    async def _run_embeddings_only(
        self,
        job_id: str,
        company_id: str,
        executive_id: str,
        profile: Dict[str, Any],
        voiceprint: Optional[Dict[str, Any]],
    ):
        """Run embedding generation only (background task)."""
        try:
            await jobs.update_job_status(self.pool, job_id, "embedding", 50.0)

            from onboarding.deployer.embedding_trigger import trigger_embeddings
            embed_result = await trigger_embeddings(
                executive_id,
                company_id,
                profile,
                voiceprint or {},
                self.pool,
            )

            logger.info(f"[{job_id}] Embedding result: {embed_result.get('status', 'unknown')}")

            await jobs.update_job_status(self.pool, job_id, "completed", 100.0)

            # Notify RAG API to refresh cached profile (embeddings changed)
            try:
                from onboarding.utils.rag_notifier import notify_rag_profile_refresh
                await notify_rag_profile_refresh(company_id, executive_id, reason="embedding_refresh")
            except Exception as notify_err:
                logger.warning(f"[{job_id}] RAG refresh notification failed (non-fatal): {notify_err}")

        except Exception as e:
            logger.error(f"[{job_id}] Embedding failed: {e}", exc_info=True)
            await jobs.update_job_status(self.pool, job_id, "failed", error_message=str(e))
