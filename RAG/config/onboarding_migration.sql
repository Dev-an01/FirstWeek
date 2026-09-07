-- ============================================================================
-- Onboarding Service Migration (COMPREHENSIVE)
-- Creates tables for multi-tenant company/executive onboarding pipeline
--
-- This migration is IDEMPOTENT - safe to run multiple times
-- Includes all changes needed for onboarding service to work
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Companies table
-- ============================================================================
CREATE TABLE IF NOT EXISTS companies (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_companies_industry ON companies(industry);

-- ============================================================================
-- 2. Onboarding jobs table
-- ============================================================================
CREATE TABLE IF NOT EXISTS onboarding_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id VARCHAR(50) REFERENCES companies(id),
    executive_id VARCHAR(50),
    job_type VARCHAR(50) NOT NULL DEFAULT 'full_onboarding',
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    progress REAL DEFAULT 0.0,
    input_documents JSONB DEFAULT '[]',
    extraction_results JSONB DEFAULT '{}',
    assembled_profile JSONB,
    assembled_voiceprint JSONB,
    validation_report JSONB,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_onboarding_jobs_company ON onboarding_jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_jobs_executive ON onboarding_jobs(executive_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_jobs_status ON onboarding_jobs(status);

-- ============================================================================
-- 3. Executive Documents table (stores uploaded documents)
-- ============================================================================
CREATE TABLE IF NOT EXISTS executive_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id VARCHAR(50) NOT NULL,
    executive_id VARCHAR(50),
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    file_size INTEGER,
    extracted_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    parsing_method VARCHAR(30) DEFAULT 'pdfplumber',
    ocr_applied BOOLEAN DEFAULT false,
    doc_type VARCHAR(30) DEFAULT 'profile',
    access_level VARCHAR(20) DEFAULT 'internal',
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exec_docs_company ON executive_documents(company_id);
CREATE INDEX IF NOT EXISTS idx_exec_docs_executive ON executive_documents(executive_id);
CREATE INDEX IF NOT EXISTS idx_exec_docs_active ON executive_documents(is_active);
CREATE INDEX IF NOT EXISTS idx_exec_docs_company_exec ON executive_documents(company_id, executive_id);
CREATE INDEX IF NOT EXISTS idx_exec_docs_parsing_method ON executive_documents(parsing_method);

-- Add doc_type column if not present (for existing databases)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_documents' AND column_name = 'doc_type'
    ) THEN
        ALTER TABLE executive_documents ADD COLUMN doc_type VARCHAR(30) DEFAULT 'profile';
    END IF;
END $$;

-- Allow NULL executive_id for knowledgebase documents (if column was created as NOT NULL)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_documents'
        AND column_name = 'executive_id'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE executive_documents ALTER COLUMN executive_id DROP NOT NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_exec_docs_doc_type ON executive_documents(doc_type);

-- Add access_level column if not present (for existing databases)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_documents' AND column_name = 'access_level'
    ) THEN
        ALTER TABLE executive_documents ADD COLUMN access_level VARCHAR(20) DEFAULT 'internal';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_exec_docs_access_level ON executive_documents(access_level);

-- ============================================================================
-- 4. Alter executive_profiles: add ALL onboarding columns
-- ============================================================================
DO $$
BEGIN
    -- company_id: Links executive to their company
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles' AND column_name = 'company_id'
    ) THEN
        ALTER TABLE executive_profiles ADD COLUMN company_id VARCHAR(50);
    END IF;

    -- voiceprint_data: Stores generated voiceprint JSON
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles' AND column_name = 'voiceprint_data'
    ) THEN
        ALTER TABLE executive_profiles ADD COLUMN voiceprint_data JSONB;
    END IF;

    -- name_english: English version of executive's name
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles' AND column_name = 'name_english'
    ) THEN
        ALTER TABLE executive_profiles ADD COLUMN name_english VARCHAR(255);
    END IF;

    -- reports_to: Parent executive for org chart
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles' AND column_name = 'reports_to'
    ) THEN
        ALTER TABLE executive_profiles ADD COLUMN reports_to VARCHAR(50);
    END IF;

    -- hierarchy_level: 0=CEO, 1=C-suite, 2=VP, 3=Director, 4=Manager
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles' AND column_name = 'hierarchy_level'
    ) THEN
        ALTER TABLE executive_profiles ADD COLUMN hierarchy_level INTEGER DEFAULT 0;
    END IF;

    -- sort_order: Custom ordering within same level
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles' AND column_name = 'sort_order'
    ) THEN
        ALTER TABLE executive_profiles ADD COLUMN sort_order INTEGER DEFAULT 0;
    END IF;

    -- voice_keys: Per-executive voice cloning keys (Chirp3) {"en-US": "<key>", "ja-JP": "<key>"}
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles' AND column_name = 'voice_keys'
    ) THEN
        ALTER TABLE executive_profiles ADD COLUMN voice_keys JSONB;
    END IF;
END $$;

-- Make profile_data, title, email nullable (required for onboarding - profile is generated later)
DO $$
BEGIN
    -- profile_data: Generated after calibration
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles'
        AND column_name = 'profile_data'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE executive_profiles ALTER COLUMN profile_data DROP NOT NULL;
    END IF;

    -- title: Optional during executive creation
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles'
        AND column_name = 'title'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE executive_profiles ALTER COLUMN title DROP NOT NULL;
    END IF;

    -- email: Optional during executive creation
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles'
        AND column_name = 'email'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE executive_profiles ALTER COLUMN email DROP NOT NULL;
    END IF;
END $$;

-- Remove unique constraint on email (executives may not have emails initially)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'executive_profiles_email_key'
    ) THEN
        ALTER TABLE executive_profiles DROP CONSTRAINT executive_profiles_email_key;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_executive_profiles_company ON executive_profiles(company_id);
CREATE INDEX IF NOT EXISTS idx_exec_profiles_reports_to ON executive_profiles(reports_to);
CREATE INDEX IF NOT EXISTS idx_exec_profiles_hierarchy ON executive_profiles(hierarchy_level);
CREATE INDEX IF NOT EXISTS idx_exec_profiles_company_hierarchy ON executive_profiles(company_id, hierarchy_level);

-- ============================================================================
-- 5. Alter embeddings: add multi-tenant columns
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'embeddings' AND column_name = 'company_id'
    ) THEN
        ALTER TABLE embeddings ADD COLUMN company_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'embeddings' AND column_name = 'executive_id'
    ) THEN
        ALTER TABLE embeddings ADD COLUMN executive_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'embeddings' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE embeddings ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb;
    END IF;
END $$;

-- Add access_level column for RBAC scope filtering
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'embeddings' AND column_name = 'access_level'
    ) THEN
        ALTER TABLE embeddings ADD COLUMN access_level VARCHAR(20) DEFAULT 'internal'
            CHECK (access_level IN ('public', 'internal', 'executive', 'confidential'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_embeddings_company ON embeddings(company_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_executive ON embeddings(executive_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_tenant ON embeddings(company_id, executive_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_access_level ON embeddings(access_level);

-- ============================================================================
-- 6. Alter document_sections: add company_id
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'document_sections' AND column_name = 'company_id'
    ) THEN
        ALTER TABLE document_sections ADD COLUMN company_id VARCHAR(50);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_document_sections_company ON document_sections(company_id);

-- ============================================================================
-- 7. Alter onboarding_jobs: add calibration columns
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
-- 8. Add triggers for updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_executive_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_executive_documents_updated_at ON executive_documents;
CREATE TRIGGER trigger_update_executive_documents_updated_at
    BEFORE UPDATE ON executive_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_executive_documents_updated_at();

-- ============================================================================
-- 9. Backfill: Create ai_talent_force company and link sample_profile
-- ============================================================================
INSERT INTO companies (id, name, industry, description, metadata)
VALUES (
    'ai_talent_force',
    'Example Company株式会社',
    'AI/Technology',
    'AI-powered talent management and recruitment company',
    '{"founded": "2023", "headquarters": "Tokyo, Japan"}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

-- Link existing sample_profile to company (if exists and not already linked)
UPDATE executive_profiles
SET company_id = 'ai_talent_force'
WHERE id = 'sample_profile' AND (company_id IS NULL OR company_id = '');

COMMIT;

-- ============================================================================
-- Verification
-- ============================================================================
DO $$
DECLARE
    companies_exists BOOLEAN;
    jobs_exists BOOLEAN;
    docs_exists BOOLEAN;
    embeddings_has_company BOOLEAN;
    profiles_has_voiceprint BOOLEAN;
BEGIN
    -- Check tables exist
    SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'companies') INTO companies_exists;
    SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'onboarding_jobs') INTO jobs_exists;
    SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'executive_documents') INTO docs_exists;

    -- Check columns exist
    SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'embeddings' AND column_name = 'company_id') INTO embeddings_has_company;
    SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'executive_profiles' AND column_name = 'voiceprint_data') INTO profiles_has_voiceprint;

    RAISE NOTICE '============================================';
    RAISE NOTICE 'Onboarding Migration Verification';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'companies table: %', CASE WHEN companies_exists THEN '✓ EXISTS' ELSE '✗ MISSING' END;
    RAISE NOTICE 'onboarding_jobs table: %', CASE WHEN jobs_exists THEN '✓ EXISTS' ELSE '✗ MISSING' END;
    RAISE NOTICE 'executive_documents table: %', CASE WHEN docs_exists THEN '✓ EXISTS' ELSE '✗ MISSING' END;
    RAISE NOTICE 'embeddings.company_id: %', CASE WHEN embeddings_has_company THEN '✓ EXISTS' ELSE '✗ MISSING' END;
    RAISE NOTICE 'executive_profiles.voiceprint_data: %', CASE WHEN profiles_has_voiceprint THEN '✓ EXISTS' ELSE '✗ MISSING' END;
    RAISE NOTICE '============================================';

    IF companies_exists AND jobs_exists AND docs_exists AND embeddings_has_company AND profiles_has_voiceprint THEN
        RAISE NOTICE '✓ All onboarding schema objects created successfully!';
    ELSE
        RAISE WARNING '✗ Some schema objects may be missing. Check above.';
    END IF;
END $$;
