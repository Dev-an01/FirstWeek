 Onboarding Service Implementation Plan

 Overview

 Build a NEW onboarding service (RAG/onboarding/) that handles company registration, executive onboarding, document processing, and LLM-powered 
  profile + voiceprint generation. Also modify existing code for multi-tenancy support.

 User Decisions

 - Fresh start (done - old code reverted)
 - LLM: openai/gpt-oss-120b via Groq. Two keys: extraction + synthesis (from .env)
 - Storage: Database-only (PostgreSQL executive_profiles table, no filesystem)
 - No admin UI (teammate handles)
 - Discovery: Read from DB on each request

 ---
 Phase 1: Database Migration + Environment

 1A: Create migration SQL (RAG/config/onboarding_migration.sql)

 New tables:
 - companies (id, name, industry, description, metadata JSONB, timestamps)
 - onboarding_jobs (id UUID, company_id FK, executive_id FK, job_type, status, progress, input_documents JSONB, extraction_results JSONB,       
 assembled_profile JSONB, assembled_voiceprint JSONB, validation_report JSONB, error_message, timestamps)

 Alter existing tables:
 - executive_profiles: ADD company_id VARCHAR(50) REFERENCES companies(id), ADD voiceprint_data JSONB
 - embeddings: ADD company_id VARCHAR(50), ADD executive_id VARCHAR(50) + indexes
 - document_sections: ADD company_id VARCHAR(50)

 Backfill: Create ai_talent_force company, link sample_profile to it.

 1B: Update .env (RAG/.env)

 Add:
 GROQ_EXTRACTION_API_KEY=your_groq_extraction_api_key_here
 GROQ_SYNTHESIS_API_KEY=your_groq_synthesis_api_key_here
 ONBOARDING_SERVICE_PORT=8002
 EMBEDDING_SERVICE_URL=http://localhost:8001

 ---
 Phase 2: Onboarding Service Foundation

 File structure:

 RAG/onboarding/
     __init__.py
     config.py                    # Env vars, model settings, constants
     main.py                      # FastAPI app (port 8002)
     models.py                    # Pydantic request/response schemas
     parsers/
         __init__.py
         pdf_parser.py            # pdfplumber
         docx_parser.py           # python-docx
         text_parser.py           # TXT/JSON
         dispatcher.py            # Routes to correct parser
     extractors/
         __init__.py
         base_extractor.py        # Groq client + shared LLM call logic
         background_identity.py   # Extractor 1
         thinking_patterns.py     # Extractor 2
         communication_style.py   # Extractor 3
         values_decisions.py      # Extractor 4
         domain_tech.py           # Extractor 5
         red_flags_inference.py   # Extractor 6
         speaking_patterns.py     # Extractor 7
         runner.py                # Orchestrates 7 concurrent extractions
     assembler/
         __init__.py
         profile_assembler.py     # Merges extractions -> profile JSON
         voiceprint_assembler.py  # Merges extractions -> voiceprint JSON
         synthesis_llm.py         # Final LLM pass for consistency + examples
     validator/
         __init__.py
         profile_validator.py     # Completeness & consistency checks
         schema_checker.py        # Compare against reference structure
     deployer/
         __init__.py
         db_deployer.py           # Writes to PostgreSQL
         embedding_trigger.py     # Calls embedding service (port 8001)
     db/
         __init__.py
         connection.py            # asyncpg pool
         companies.py             # Company CRUD
         executives.py            # Executive CRUD
         jobs.py                  # Job tracking CRUD

 API Endpoints (RAG/onboarding/main.py):

 POST   /api/v1/companies                          Create company
 GET    /api/v1/companies                          List companies
 GET    /api/v1/companies/{id}                     Get company
 GET    /api/v1/companies/{id}/executives          List company executives

 POST   /api/v1/executives                         Register executive
 GET    /api/v1/executives/{id}                    Get executive

 POST   /api/v1/onboarding/{executive_id}/upload   Upload documents (multipart)
 POST   /api/v1/onboarding/{executive_id}/start    Start pipeline
 GET    /api/v1/onboarding/jobs/{job_id}           Job status
 GET    /api/v1/onboarding/jobs/{job_id}/result    Get profile/voiceprint

 GET    /health                                     Health check

 ---
 Phase 3: Document Parsing

 - pdf_parser.py: Use pdfplumber (good Japanese support)
 - docx_parser.py: Use python-docx
 - text_parser.py: Plain text + JSON handling
 - dispatcher.py: Route by file extension (.pdf/.docx/.txt/.json)
 - Max 50MB per file, truncate at 100K chars

 ---
 Phase 4: LLM Extraction Pipeline

 Base extractor (extractors/base_extractor.py):

 - Uses GROQ_EXTRACTION_API_KEY via OpenAI-compatible client
 - Model: openai/gpt-oss-120b
 - Base URL: https://api.groq.com/openai/v1
 - JSON response format, temperature 0.3, retry with exponential backoff

 7 Extractors (each returns structured JSON):
 #: 1
 File: background_identity.py
 Extracts: education, roles, expertise, company_info, leadership_team
 Maps to profile section: background
 ────────────────────────────────────────
 #: 2
 File: thinking_patterns.py
 Extracts: problem_approach, frameworks, typical_questions
 Maps to profile section: thinking_patterns
 ────────────────────────────────────────
 #: 3
 File: communication_style.py
 Extracts: tone, scales (1-10), languages, core_principles, response_patterns
 Maps to profile section: communication_style
 ────────────────────────────────────────
 #: 4
 File: values_decisions.py
 Extracts: core_values, decision_making (15 trade-offs), decision_cases
 Maps to profile section: core_values, decision_making, decision_cases
 ────────────────────────────────────────
 #: 5
 File: domain_tech.py
 Extracts: primary/secondary domains, boost_keywords, ai_views, market_views
 Maps to profile section: domain_affinity, tech_opinions
 ────────────────────────────────────────
 #: 6
 File: red_flags_inference.py
 Extracts: never_approve, always_do, escalation triggers, inference framework
 Maps to profile section: red_flags, inference_framework
 ────────────────────────────────────────
 #: 7
 File: speaking_patterns.py
 Extracts: voiceprint sections, speaking patterns, casual responses, lexicon
 Maps to profile section: Full voiceprint JSON
 Runner (extractors/runner.py):

 - Runs all 7 concurrently via ThreadPoolExecutor(max_workers=7)
 - Reports progress per extractor
 - Collects errors without blocking other extractors

 ---
 Phase 5: Assembly + Validation

 Profile assembler (assembler/profile_assembler.py):

 - Merges 7 extraction outputs into single profile JSON
 - Structure matches sample_profile.json (19 sections)
 - Root fields: id, name, name_english, title, department, company, email
 - Sections: background, thinking_patterns, communication_style, core_values, decision_making, decision_cases, red_flags, tech_opinions,        
 domain_affinity, inference_framework, communication_examples, metadata

 Voiceprint assembler (assembler/voiceprint_assembler.py):

 - Takes extractor #7 output -> voiceprint JSON
 - Structure matches sample_profile_voiceprint.json (5 major sections)
 - Sections: voiceprint (14 subsections), speaking_patterns_video (7), casual_responses (9), lexicon, response_adaptation

 Synthesis LLM (assembler/synthesis_llm.py):

 - Uses GROQ_SYNTHESIS_API_KEY (separate key to avoid rate limits)
 - Cross-checks all 7 extractions for consistency
 - Generates communication_examples (5-10 Q&A pairs, bilingual)
 - Fills gaps from cross-referencing

 Validator (validator/profile_validator.py):

 - All required keys present
 - Scales within bounds (formality 1-10, confidence 0-1, priority 1-5)
 - No empty critical arrays
 - Returns: {valid, completeness_score, issues[], statistics}

 Schema checker (validator/schema_checker.py):

 - Compares against reference sample_profile.json structure
 - Reports missing keys, type mismatches

 ---
 Phase 6: Deployment

 DB deployer (deployer/db_deployer.py):

 - UPSERT executive_profiles (profile_data JSONB, voiceprint_data JSONB, company_id, scales)
 - INSERT decision_cases rows (one per case, linked by executive_id)
 - Update onboarding_jobs status

 Embedding trigger (deployer/embedding_trigger.py):

 - Call embedding service POST /embeddings/batch via httpx
 - Documents: profile text + each decision case + voiceprint text
 - Each document includes metadata: {company_id, executive_id} for tenant isolation

 ---
 Phase 7: Existing Code Modifications

 7A: RAG/cognitive_twin/profile_loader.py

 - Modify _merge_voiceprint_data(): Try DB voiceprint_data column first, fall back to filesystem
 - Support dynamic profiles (any ID in DB, not just hardcoded sample)

 7B: RAG/profile_management/profile_id_mapper.py

 - Add _dynamic_registry dict for runtime-registered profiles
 - Add refresh_from_db() classmethod: queries executive_profiles table, populates registry
 - Modify to_database_id(): check dynamic registry before defaulting to sample

 7C: RAG/vector_search/postgres_client.py

 - Add company_id and executive_id params to vector_search()
 - Add company_id and executive_id params to vector_search_sections()
 - Filter: WHERE company_id = $1 AND (executive_id = $2 OR executive_id IS NULL)
 - Backward-compatible: params default to None (no filter = existing behavior)

 7D: RAG/embedding_generation/storage_writer.py

 - Add company_id and executive_id params to store_embedding_postgres()
 - Include in INSERT + ON CONFLICT UPDATE

 7E: RAG/embedding_service/embedding_service.py

 - Extract company_id/executive_id from document.metadata
 - Pass through to storage writer

 7F: RAG/api/main.py

 - Call ProfileIDMapper.refresh_from_db() during startup lifespan

 7G: RAG/requirements.txt

 - Add: pdfplumber>=0.10.0, python-docx>=1.1.0, httpx>=0.27.0, python-multipart>=0.0.9

 ---
 Pipeline Flow (End-to-End)

 1. POST /companies          -> Register company
 2. POST /executives         -> Register executive (links to company)
 3. POST /onboarding/{id}/upload  -> Upload docs (PDF/DOCX/TXT/JSON)
 4. POST /onboarding/{id}/start   -> Kicks off background pipeline:
    a. Parse documents -> raw text
    b. 7 concurrent LLM extractions (Groq extraction key)
    c. Assemble profile + voiceprint (Groq synthesis key)
    d. Validate against reference schema
    e. Deploy to PostgreSQL (executive_profiles, decision_cases)
    f. Trigger embedding generation via port 8001
 5. GET /onboarding/jobs/{id}     -> Poll status
 6. Main RAG API auto-discovers new executive on next request

 Data Isolation

 Company docs:    company_id = X, executive_id = NULL  -> all execs see
 Executive docs:  company_id = X, executive_id = Y     -> only exec Y sees
 Query filter:    WHERE company_id = $1 AND (executive_id = $2 OR executive_id IS NULL)

 ---
 Verification Plan

 1. Run migration SQL against PostgreSQL
 2. Start onboarding service on port 8002, verify /health
 3. Create test company via POST /api/v1/companies
 4. Create test executive via POST /api/v1/executives
 5. Upload sample documents via POST /api/v1/onboarding/{id}/upload
 6. Start pipeline via POST /api/v1/onboarding/{id}/start
 7. Poll job status until completed
 8. Verify profile in executive_profiles table (profile_data + voiceprint_data)
 9. Verify decision_cases rows created
 10. Verify embeddings generated with correct company_id/executive_id
 11. Chat with new executive via main RAG API (port 8000) to confirm end-to-end
 12. Verify sample still works unchanged (backward compatibility)
 13. Verify tenant isolation: executive A cannot see executive B's personal documents
 