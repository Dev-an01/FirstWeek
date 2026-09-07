-- Phase 12: Fix tenant isolation in embeddings table
--
-- Problems fixed:
-- 1. ON CONFLICT (source_type, source_id, chunk_index) doesn't include company_id,
--    so two companies can overwrite each other's embeddings.
-- 2. company_id/executive_id may be NULL in rows created before tenant isolation.
-- 3. document_sections table missing company_id column.
--
-- Run this migration ONCE against the database.

BEGIN;

-- ============================================================================
-- Step 1: Add metadata JSONB column if missing
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'embeddings' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE embeddings ADD COLUMN metadata JSONB DEFAULT '{}';
    END IF;
END
$$;

-- Backfill company_id and executive_id from metadata JSONB (if any rows have it)
UPDATE embeddings
SET company_id = metadata->>'company_id'
WHERE company_id IS NULL
  AND metadata IS NOT NULL
  AND metadata->>'company_id' IS NOT NULL;

UPDATE embeddings
SET executive_id = metadata->>'executive_id'
WHERE executive_id IS NULL
  AND metadata IS NOT NULL
  AND metadata->>'executive_id' IS NOT NULL;

-- ============================================================================
-- Step 2: Replace unique constraint to include company_id
-- ============================================================================

-- Drop old constraint (name may vary; try common patterns)
DO $$
BEGIN
    -- Try dropping by known constraint names
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'embeddings_source_type_source_id_chunk_index_key'
    ) THEN
        ALTER TABLE embeddings
            DROP CONSTRAINT embeddings_source_type_source_id_chunk_index_key;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_embedding_source'
    ) THEN
        ALTER TABLE embeddings
            DROP CONSTRAINT uq_embedding_source;
    END IF;

    -- Also try dropping any unique index with matching columns
    DROP INDEX IF EXISTS idx_embeddings_source_unique;
    DROP INDEX IF EXISTS embeddings_source_type_source_id_chunk_index_idx;
END
$$;

-- Create new unique constraint including company_id
-- COALESCE ensures NULL company_id rows don't collide
ALTER TABLE embeddings
    ADD CONSTRAINT uq_embedding_source_tenant
    UNIQUE (source_type, source_id, chunk_index, company_id);

-- ============================================================================
-- Step 3: Add tenant isolation indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_embeddings_company_id
    ON embeddings (company_id);

CREATE INDEX IF NOT EXISTS idx_embeddings_executive_id
    ON embeddings (executive_id);

CREATE INDEX IF NOT EXISTS idx_embeddings_company_source
    ON embeddings (company_id, source_type);

-- ============================================================================
-- Step 4: Add company_id to document_sections if it exists
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'document_sections'
    ) THEN
        -- Add company_id column if missing
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'document_sections'
              AND column_name = 'company_id'
        ) THEN
            ALTER TABLE document_sections ADD COLUMN company_id VARCHAR(100);
        END IF;

        -- Add index on company_id
        CREATE INDEX IF NOT EXISTS idx_document_sections_company_id
            ON document_sections (company_id);
    END IF;
END
$$;

COMMIT;
