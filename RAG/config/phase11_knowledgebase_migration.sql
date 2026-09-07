-- ============================================================================
-- Phase 11: Knowledgebase vs Profile Document Separation
-- ============================================================================
-- This migration adds support for company-wide knowledgebase documents that
-- bypass the LLM extraction pipeline and go directly to embeddings.
--
-- PROFILE documents: Executive-specific (interviews, bios, speeches)
--   → Go through 7 LLM extractors → Profile + Voiceprint → Embed
--
-- KNOWLEDGEBASE documents: Company-wide (policies, procedures)
--   → Parse → Chunk → Embed directly (NO extraction)
--   → executive_id = NULL (shared by all executives in company)
--
-- This migration is IDEMPOTENT - safe to run multiple times
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Add doc_type column to executive_documents
-- ============================================================================
-- Values: 'profile' (default, executive-specific) or 'knowledgebase' (company-wide)
ALTER TABLE executive_documents
ADD COLUMN IF NOT EXISTS doc_type VARCHAR(20) DEFAULT 'profile';

COMMENT ON COLUMN executive_documents.doc_type IS
'Document type: profile (executive-specific, LLM extraction) or knowledgebase (company-wide, direct embedding)';

-- ============================================================================
-- 2. Make executive_id nullable (knowledgebase docs have NULL executive_id)
-- ============================================================================
-- First check if it has NOT NULL constraint
DO $$
BEGIN
    -- Check if column has NOT NULL constraint and remove it
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_documents'
        AND column_name = 'executive_id'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE executive_documents ALTER COLUMN executive_id DROP NOT NULL;
        RAISE NOTICE 'Made executive_id nullable';
    ELSE
        RAISE NOTICE 'executive_id is already nullable';
    END IF;
END $$;

-- ============================================================================
-- 3. Add indexes for efficient querying
-- ============================================================================

-- Index for filtering by doc_type
CREATE INDEX IF NOT EXISTS idx_exec_docs_doc_type
ON executive_documents(doc_type);

-- Index for company knowledgebase queries (where executive_id IS NULL)
CREATE INDEX IF NOT EXISTS idx_company_knowledgebase
ON executive_documents(company_id, doc_type)
WHERE executive_id IS NULL;

-- Index for profile documents per executive
CREATE INDEX IF NOT EXISTS idx_exec_profile_docs
ON executive_documents(company_id, executive_id, doc_type)
WHERE doc_type = 'profile';

-- ============================================================================
-- 4. Add check constraint to ensure consistency
-- ============================================================================
-- Knowledgebase docs must have NULL executive_id
-- Profile docs must have non-NULL executive_id
DO $$
BEGIN
    -- Drop existing constraint if it exists (to allow re-running)
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'chk_doc_type_executive_id'
        AND table_name = 'executive_documents'
    ) THEN
        ALTER TABLE executive_documents DROP CONSTRAINT chk_doc_type_executive_id;
    END IF;

    -- Add the constraint
    ALTER TABLE executive_documents ADD CONSTRAINT chk_doc_type_executive_id
    CHECK (
        (doc_type = 'profile' AND executive_id IS NOT NULL) OR
        (doc_type = 'knowledgebase' AND executive_id IS NULL)
    );

    RAISE NOTICE 'Added check constraint for doc_type/executive_id consistency';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Could not add constraint (may have existing data that violates it): %', SQLERRM;
END $$;

COMMIT;

-- ============================================================================
-- Verification
-- ============================================================================
DO $$
DECLARE
    has_doc_type BOOLEAN;
    exec_id_nullable BOOLEAN;
    has_doc_type_index BOOLEAN;
    has_kb_index BOOLEAN;
BEGIN
    -- Check doc_type column exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_documents' AND column_name = 'doc_type'
    ) INTO has_doc_type;

    -- Check executive_id is nullable
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_documents'
        AND column_name = 'executive_id'
        AND is_nullable = 'YES'
    ) INTO exec_id_nullable;

    -- Check indexes exist
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_exec_docs_doc_type'
    ) INTO has_doc_type_index;

    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_company_knowledgebase'
    ) INTO has_kb_index;

    RAISE NOTICE '============================================';
    RAISE NOTICE 'Phase 11 Migration Verification';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'doc_type column: %', CASE WHEN has_doc_type THEN '✓ EXISTS' ELSE '✗ MISSING' END;
    RAISE NOTICE 'executive_id nullable: %', CASE WHEN exec_id_nullable THEN '✓ YES' ELSE '✗ NO' END;
    RAISE NOTICE 'idx_exec_docs_doc_type: %', CASE WHEN has_doc_type_index THEN '✓ EXISTS' ELSE '✗ MISSING' END;
    RAISE NOTICE 'idx_company_knowledgebase: %', CASE WHEN has_kb_index THEN '✓ EXISTS' ELSE '✗ MISSING' END;
    RAISE NOTICE '============================================';

    IF has_doc_type AND exec_id_nullable AND has_doc_type_index AND has_kb_index THEN
        RAISE NOTICE '✓ Phase 11 migration completed successfully!';
    ELSE
        RAISE WARNING '✗ Some migration steps may have failed. Check above.';
    END IF;
END $$;
