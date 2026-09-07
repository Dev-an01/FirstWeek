-- ============================================================================
-- Phase 9: Multi-Tenant Enhancement Migration
-- Adds company_id to remaining tables for proper tenant isolation
-- Also adds calibration metadata columns to onboarding_jobs
-- ============================================================================

BEGIN;

-- ============================================================================
-- 0. Add calibration columns to onboarding_jobs
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'onboarding_jobs' AND column_name = 'calibration_mode'
    ) THEN
        ALTER TABLE onboarding_jobs ADD COLUMN calibration_mode VARCHAR(30);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'onboarding_jobs' AND column_name = 'extractors_run'
    ) THEN
        ALTER TABLE onboarding_jobs ADD COLUMN extractors_run JSONB DEFAULT '[]';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'onboarding_jobs' AND column_name = 'merge_strategy'
    ) THEN
        ALTER TABLE onboarding_jobs ADD COLUMN merge_strategy VARCHAR(30);
    END IF;
END $$;

-- ============================================================================
-- 1. Add company_id to decision_cases
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'decision_cases' AND column_name = 'company_id'
    ) THEN
        ALTER TABLE decision_cases ADD COLUMN company_id VARCHAR(50);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_decision_cases_company ON decision_cases(company_id);
CREATE INDEX IF NOT EXISTS idx_decision_cases_tenant ON decision_cases(company_id, executive_id);

-- ============================================================================
-- 2. Add company_id to policy_documents
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'policy_documents' AND column_name = 'company_id'
    ) THEN
        ALTER TABLE policy_documents ADD COLUMN company_id VARCHAR(50);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_policy_documents_company ON policy_documents(company_id);

-- ============================================================================
-- 3. Add company_id and executive_id to section_embeddings
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'section_embeddings' AND column_name = 'company_id'
    ) THEN
        ALTER TABLE section_embeddings ADD COLUMN company_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'section_embeddings' AND column_name = 'executive_id'
    ) THEN
        ALTER TABLE section_embeddings ADD COLUMN executive_id VARCHAR(50);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_section_embeddings_company ON section_embeddings(company_id);
CREATE INDEX IF NOT EXISTS idx_section_embeddings_tenant ON section_embeddings(company_id, executive_id);

-- ============================================================================
-- 4. Add company_id to episodic_memory
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'episodic_memory' AND column_name = 'company_id'
    ) THEN
        ALTER TABLE episodic_memory ADD COLUMN company_id VARCHAR(50);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_episodic_memory_company ON episodic_memory(company_id);
CREATE INDEX IF NOT EXISTS idx_episodic_memory_tenant ON episodic_memory(company_id, executive_id);

-- ============================================================================
-- 5. Add company_id to communication_examples
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'communication_examples' AND column_name = 'company_id'
    ) THEN
        ALTER TABLE communication_examples ADD COLUMN company_id VARCHAR(50);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_communication_examples_company ON communication_examples(company_id);
CREATE INDEX IF NOT EXISTS idx_communication_examples_tenant ON communication_examples(company_id, executive_id);

-- ============================================================================
-- 6. Add company_id to conversation_sessions
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'conversation_sessions' AND column_name = 'company_id'
    ) THEN
        ALTER TABLE conversation_sessions ADD COLUMN company_id VARCHAR(50);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_conversation_sessions_company ON conversation_sessions(company_id);

-- ============================================================================
-- 7. Backfill existing data with ai_talent_force company
-- ============================================================================

-- Backfill decision_cases
UPDATE decision_cases dc
SET company_id = ep.company_id
FROM executive_profiles ep
WHERE dc.executive_id = ep.id
  AND dc.company_id IS NULL
  AND ep.company_id IS NOT NULL;

-- Backfill policy_documents
UPDATE policy_documents pd
SET company_id = ep.company_id
FROM executive_profiles ep
WHERE pd.owner_executive = ep.id
  AND pd.company_id IS NULL
  AND ep.company_id IS NOT NULL;

-- Backfill document_sections
UPDATE document_sections ds
SET company_id = ep.company_id
FROM executive_profiles ep
WHERE ds.executive_id = ep.id
  AND ds.company_id IS NULL
  AND ep.company_id IS NOT NULL;

-- Backfill embeddings
UPDATE embeddings e
SET company_id = ep.company_id
FROM executive_profiles ep
WHERE e.executive_id = ep.id
  AND e.company_id IS NULL
  AND ep.company_id IS NOT NULL;

-- Backfill episodic_memory
UPDATE episodic_memory em
SET company_id = ep.company_id
FROM executive_profiles ep
WHERE em.executive_id = ep.id
  AND em.company_id IS NULL
  AND ep.company_id IS NOT NULL;

-- Backfill communication_examples
UPDATE communication_examples ce
SET company_id = ep.company_id
FROM executive_profiles ep
WHERE ce.executive_id = ep.id
  AND ce.company_id IS NULL
  AND ep.company_id IS NOT NULL;

-- Backfill conversation_sessions
UPDATE conversation_sessions cs
SET company_id = ep.company_id
FROM executive_profiles ep
WHERE cs.executive_id = ep.id
  AND cs.company_id IS NULL
  AND ep.company_id IS NOT NULL;

COMMIT;

-- ============================================================================
-- Verification
-- ============================================================================
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND column_name = 'company_id'
      AND table_name IN (
        'companies', 'executive_profiles', 'decision_cases', 'policy_documents',
        'document_sections', 'embeddings', 'section_embeddings', 'episodic_memory',
        'communication_examples', 'conversation_sessions', 'executive_documents',
        'onboarding_jobs'
      );

    RAISE NOTICE '============================================';
    RAISE NOTICE 'Phase 9 Multi-Tenant Migration Complete';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Tables with company_id: % (expected: 12)', col_count;
    RAISE NOTICE '============================================';
END $$;
