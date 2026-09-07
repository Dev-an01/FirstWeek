-- ============================================================================
-- Phase 8 Migration: Document Management, Profile Editing & Calibration
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Executive Documents Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS executive_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id VARCHAR(50) NOT NULL REFERENCES companies(id),
    executive_id VARCHAR(50) NOT NULL REFERENCES executive_profiles(id),
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    file_size INTEGER,
    extracted_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exec_docs_company ON executive_documents(company_id);
CREATE INDEX IF NOT EXISTS idx_exec_docs_executive ON executive_documents(executive_id);
CREATE INDEX IF NOT EXISTS idx_exec_docs_active ON executive_documents(is_active);
CREATE INDEX IF NOT EXISTS idx_exec_docs_company_exec ON executive_documents(company_id, executive_id);

-- ============================================================================
-- 2. Executive Profile Additional Columns
-- ============================================================================
DO $$
BEGIN
    -- name_english: English version of the executive's name
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles' AND column_name = 'name_english'
    ) THEN
        ALTER TABLE executive_profiles ADD COLUMN name_english VARCHAR(255);
    END IF;

    -- email: Executive's email address
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles' AND column_name = 'email'
    ) THEN
        ALTER TABLE executive_profiles ADD COLUMN email VARCHAR(255);
    END IF;

    -- updated_at: Timestamp for tracking updates
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE executive_profiles ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;

    -- reports_to: Parent executive for org chart
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'executive_profiles' AND column_name = 'reports_to'
    ) THEN
        ALTER TABLE executive_profiles ADD COLUMN reports_to VARCHAR(50) REFERENCES executive_profiles(id);
    END IF;

    -- hierarchy_level: 0=CEO, 1=C-suite, 2=VP, 3=Director, 4=Manager, etc.
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
END $$;

CREATE INDEX IF NOT EXISTS idx_exec_profiles_reports_to ON executive_profiles(reports_to);
CREATE INDEX IF NOT EXISTS idx_exec_profiles_hierarchy ON executive_profiles(hierarchy_level);
CREATE INDEX IF NOT EXISTS idx_exec_profiles_company_hierarchy ON executive_profiles(company_id, hierarchy_level);

-- ============================================================================
-- 3. Calibration Jobs Enhancement
-- ============================================================================
-- Add calibration-specific fields to onboarding_jobs
DO $$
BEGIN
    -- calibration_mode: 'full' or 'incremental'
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'onboarding_jobs' AND column_name = 'calibration_mode'
    ) THEN
        ALTER TABLE onboarding_jobs ADD COLUMN calibration_mode VARCHAR(20);
    END IF;

    -- extractors_run: List of extractors that were run (for incremental)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'onboarding_jobs' AND column_name = 'extractors_run'
    ) THEN
        ALTER TABLE onboarding_jobs ADD COLUMN extractors_run JSONB DEFAULT '[]';
    END IF;

    -- merge_strategy: 'replace' or 'merge' (for incremental)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'onboarding_jobs' AND column_name = 'merge_strategy'
    ) THEN
        ALTER TABLE onboarding_jobs ADD COLUMN merge_strategy VARCHAR(20);
    END IF;
END $$;

-- ============================================================================
-- 4. Trigger for updated_at on executive_documents
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
-- 5. Trigger for updated_at on executive_profiles
-- ============================================================================
CREATE OR REPLACE FUNCTION update_executive_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_executive_profiles_updated_at ON executive_profiles;
CREATE TRIGGER trigger_update_executive_profiles_updated_at
    BEFORE UPDATE ON executive_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_executive_profiles_updated_at();

COMMIT;
