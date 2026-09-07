-- Phase 12b: Fix legacy schema to match onboarding service expectations
--
-- The original postgres_schema.sql created tables with different column names
-- than the onboarding service expects:
--   - companies: used 'company_id' as PK instead of 'id'
--   - executive_documents: missing extracted_text, is_active, parsing_method, etc.
--
-- This migration is IDEMPOTENT - safe to run multiple times.
-- Run BEFORE onboarding_migration.sql if your database was created from
-- the original postgres_schema.sql.

BEGIN;

-- ============================================================================
-- 1. Fix companies table: rename company_id -> id, add missing columns
-- ============================================================================
DO $$
BEGIN
    -- Rename company_id to id if needed
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'companies' AND column_name = 'company_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'companies' AND column_name = 'id'
    ) THEN
        ALTER TABLE companies RENAME COLUMN company_id TO id;
    END IF;
END $$;

ALTER TABLE companies ADD COLUMN IF NOT EXISTS industry VARCHAR(100);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- ============================================================================
-- 2. Fix executive_documents table: add missing columns
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='extracted_text') THEN
        ALTER TABLE executive_documents ADD COLUMN extracted_text TEXT NOT NULL DEFAULT '';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='is_active') THEN
        ALTER TABLE executive_documents ADD COLUMN is_active BOOLEAN DEFAULT true;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='parsing_method') THEN
        ALTER TABLE executive_documents ADD COLUMN parsing_method VARCHAR(30) DEFAULT 'pdfplumber';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='ocr_applied') THEN
        ALTER TABLE executive_documents ADD COLUMN ocr_applied BOOLEAN DEFAULT false;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='doc_type') THEN
        ALTER TABLE executive_documents ADD COLUMN doc_type VARCHAR(30) DEFAULT 'profile';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='uploaded_at') THEN
        ALTER TABLE executive_documents ADD COLUMN uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='updated_at') THEN
        ALTER TABLE executive_documents ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='filename') THEN
        ALTER TABLE executive_documents ADD COLUMN filename VARCHAR(255);
        -- Backfill from original_filename if it exists
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='original_filename') THEN
            UPDATE executive_documents SET filename = original_filename WHERE filename IS NULL;
        END IF;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='content_type') THEN
        ALTER TABLE executive_documents ADD COLUMN content_type VARCHAR(100);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='file_size') THEN
        ALTER TABLE executive_documents ADD COLUMN file_size INTEGER;
        -- Backfill from size_bytes if it exists
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='executive_documents' AND column_name='size_bytes') THEN
            UPDATE executive_documents SET file_size = size_bytes WHERE file_size IS NULL;
        END IF;
    END IF;
END $$;

-- ============================================================================
-- 3. Fix executive_documents constraints from legacy schema
-- ============================================================================
-- document_type: legacy column, make nullable with default
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_documents'
          AND column_name = 'document_type'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE executive_documents ALTER COLUMN document_type DROP NOT NULL;
        ALTER TABLE executive_documents ALTER COLUMN document_type SET DEFAULT 'profile';
    END IF;

    -- executive_id: must be nullable for knowledgebase docs (company-wide, no executive)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_documents'
          AND column_name = 'executive_id'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE executive_documents ALTER COLUMN executive_id DROP NOT NULL;
    END IF;
END $$;

COMMIT;
