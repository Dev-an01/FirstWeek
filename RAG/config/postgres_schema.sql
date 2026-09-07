-- ============================================
-- AI Officer PostgreSQL Schema - COMPLETE
-- ============================================
-- Production schema including all tables, views, functions, triggers, and indexes
-- Version: 2.1 (Non-destructive: uses IF NOT EXISTS / OR REPLACE)
-- Generated: 2025-11-14, Updated: 2026-02-12
--
-- IMPORTANT: This schema requires pgvector extension
-- Run: CREATE EXTENSION IF NOT EXISTS vector;
--
-- This schema is SAFE to re-run — it will NOT destroy existing data.
-- All tables use CREATE IF NOT EXISTS, views use CREATE OR REPLACE,
-- and triggers are dropped+recreated idempotently.
-- ============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- TABLES
-- ============================================

-- ============================================
-- Executive Profiles
-- ============================================
CREATE TABLE IF NOT EXISTS executive_profiles (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    department VARCHAR(100),
    email VARCHAR(255) UNIQUE NOT NULL,

    -- Profile data (comprehensive JSONB with voiceprint, values, decision cases, etc.)
    profile_data JSONB NOT NULL,

    -- Communication style scales (for quick filtering)
    formality_scale INTEGER CHECK (formality_scale BETWEEN 1 AND 10),
    directness_scale INTEGER CHECK (directness_scale BETWEEN 1 AND 10),
    warmth_scale INTEGER CHECK (warmth_scale BETWEEN 1 AND 10),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Full-text search vector (auto-generated)
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(name, '') || ' ' ||
            coalesce(title, '') || ' ' ||
            coalesce(department, '')
        )
    ) STORED
);

CREATE INDEX IF NOT EXISTS idx_exec_search ON executive_profiles USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_exec_dept ON executive_profiles(department);

-- ============================================
-- Decision Cases
-- ============================================
CREATE TABLE IF NOT EXISTS decision_cases (
    id VARCHAR(50) PRIMARY KEY,
    executive_id VARCHAR(50) REFERENCES executive_profiles(id) ON DELETE CASCADE,

    title VARCHAR(500) NOT NULL,
    date DATE NOT NULL,
    category VARCHAR(100),

    -- Decision content
    situation TEXT,
    decision_made TEXT NOT NULL,
    rationale TEXT NOT NULL,
    outcome TEXT,
    lessons_learned TEXT,

    -- Metadata
    confidence DECIMAL(3,2) CHECK (confidence BETWEEN 0 AND 1),
    precedent BOOLEAN DEFAULT FALSE,

    -- Full decision case (JSON)
    full_content JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Full-text search
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title, '') || ' ' ||
            coalesce(situation, '') || ' ' ||
            coalesce(decision_made, '') || ' ' ||
            coalesce(rationale, '')
        )
    ) STORED
);

CREATE INDEX IF NOT EXISTS idx_decision_exec ON decision_cases(executive_id);
CREATE INDEX IF NOT EXISTS idx_decision_date ON decision_cases(date DESC);
CREATE INDEX IF NOT EXISTS idx_decision_category ON decision_cases(category);
CREATE INDEX IF NOT EXISTS idx_decision_search ON decision_cases USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_decision_precedent ON decision_cases(precedent) WHERE precedent = TRUE;

-- ============================================
-- Policy Documents
-- ============================================
CREATE TABLE IF NOT EXISTS policy_documents (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(20),
    category VARCHAR(100),

    -- Content
    content_markdown TEXT NOT NULL,
    content_sections JSONB,

    -- Metadata
    effective_date DATE,
    owner_executive VARCHAR(50) REFERENCES executive_profiles(id),
    confidentiality VARCHAR(50),
    file_path VARCHAR(500),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Full-text search
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(name, '') || ' ' ||
            coalesce(content_markdown, '')
        )
    ) STORED
);

CREATE INDEX IF NOT EXISTS idx_policy_category ON policy_documents(category);
CREATE INDEX IF NOT EXISTS idx_policy_owner ON policy_documents(owner_executive);
CREATE INDEX IF NOT EXISTS idx_policy_search ON policy_documents USING GIN(search_vector);

-- ============================================
-- Document Sections (Semantic Chunking)
-- ============================================
CREATE TABLE IF NOT EXISTS document_sections (
    id VARCHAR(100) PRIMARY KEY,
    parent_document_id VARCHAR(50) NOT NULL,
    parent_document_type VARCHAR(50) NOT NULL, -- 'policy' or 'decision'
    section_number INTEGER NOT NULL CHECK (section_number >= 0),
    section_title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    word_count INTEGER NOT NULL CHECK (word_count > 0),

    -- Semantic chunking metadata
    section_type VARCHAR(50), -- 'introduction', 'methodology', 'results', 'body', etc.
    boundary_type VARCHAR(50), -- 'explicit_heading', 'semantic_break', etc.
    boundary_confidence DECIMAL(3,2) CHECK (boundary_confidence BETWEEN 0 AND 1),

    -- Denormalized metadata for faster queries
    executive_id VARCHAR(50),
    document_category VARCHAR(100),
    document_date DATE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure unique sections per document
    UNIQUE(parent_document_id, section_number)
);

CREATE INDEX IF NOT EXISTS idx_section_parent ON document_sections(parent_document_id);
CREATE INDEX IF NOT EXISTS idx_section_parent_type ON document_sections(parent_document_type);
CREATE INDEX IF NOT EXISTS idx_section_type ON document_sections(section_type);
CREATE INDEX IF NOT EXISTS idx_section_exec ON document_sections(executive_id) WHERE executive_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_section_category ON document_sections(document_category) WHERE document_category IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_section_date ON document_sections(document_date DESC) WHERE document_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_section_content_fts ON document_sections USING GIN(to_tsvector('english', content));

-- ============================================
-- Conversation Sessions (Session Management)
-- ============================================
CREATE TABLE IF NOT EXISTS conversation_sessions (
    session_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    executive_id VARCHAR(50) NOT NULL CHECK (executive_id ~ '^[a-zA-Z0-9_-]+$'),
    user_id VARCHAR(100) NOT NULL CHECK (user_id ~ '^[a-zA-Z0-9_@.-]+$'),

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ, -- Auto-calculated by trigger
    is_active BOOLEAN DEFAULT TRUE,

    metadata JSONB DEFAULT '{}'::jsonb,

    -- Session metrics
    turn_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    avg_response_time_ms INTEGER DEFAULT 0,

    -- Session timing constraints
    CHECK (last_activity >= started_at)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_history ON conversation_sessions(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_executive_history ON conversation_sessions(executive_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_active_lookup ON conversation_sessions(user_id, executive_id, is_active, last_activity DESC) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_sessions_expiration ON conversation_sessions(is_active, expires_at) WHERE is_active = true;

-- ============================================
-- Conversations (Legacy Chat History)
-- ============================================
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,

    -- User info
    user_id VARCHAR(100),
    session_id VARCHAR(100),

    -- Executive context
    executive_id VARCHAR(50) REFERENCES executive_profiles(id),

    -- Conversation
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,

    -- Context used
    context_sources JSONB,  -- Which docs/decisions were retrieved

    -- Metadata
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_time_ms INTEGER,
    tokens_used INTEGER
);

CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_conv_exec ON conversations(executive_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id, timestamp DESC);

-- ============================================
-- Communication Examples (Adaptive Learning)
-- ============================================
CREATE TABLE IF NOT EXISTS communication_examples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    executive_id VARCHAR(50) NOT NULL CHECK (executive_id ~ '^[a-zA-Z0-9_-]+$'),

    query TEXT NOT NULL,
    response TEXT NOT NULL,
    user_feedback INTEGER NOT NULL, -- 1 = thumbs up, -1 = thumbs down, 0 = neutral

    -- Quality & Usage Tracking
    quality_score NUMERIC DEFAULT 0.5 CHECK (quality_score BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_bootstrap BOOLEAN DEFAULT FALSE,
    example_type VARCHAR(50) DEFAULT 'general' CHECK (example_type IN ('general', 'decision', 'policy', 'strategic', 'tactical')),
    query_type VARCHAR(50) CHECK (query_type IN ('factual', 'opinion', 'comparison', 'strategic', 'tactical', 'analytical')),
    context_sources JSONB DEFAULT '{}'::jsonb,

    usage_count INTEGER DEFAULT 0,
    last_used TIMESTAMPTZ,
    success_rate NUMERIC DEFAULT 0.0 CHECK (success_rate BETWEEN 0 AND 1),
    avg_response_time_ms INTEGER,

    -- Vector embedding for semantic search (BAAI/bge-m3 uses 1024 dimensions)
    embedding vector(1024),

    -- Lifecycle management
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,

    -- Diversity management
    similarity_hash VARCHAR(64),
    diversity_cluster INTEGER
);

CREATE INDEX IF NOT EXISTS idx_comm_examples_executive ON communication_examples(executive_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comm_examples_active ON communication_examples(executive_id, is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_comm_examples_quality ON communication_examples(executive_id, quality_score DESC) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_comm_examples_usage ON communication_examples(executive_id, usage_count DESC) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_comm_examples_query_type ON communication_examples(executive_id, query_type, quality_score DESC) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_comm_examples_bootstrap ON communication_examples(executive_id, is_bootstrap, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comm_examples_expires ON communication_examples(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_comm_examples_diversity ON communication_examples(diversity_cluster, quality_score DESC) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_comm_examples_embedding ON communication_examples USING hnsw (embedding vector_cosine_ops) WHERE is_active = true;

-- ============================================
-- Episodic Memory (Conversation History with Embeddings)
-- ============================================
CREATE TABLE IF NOT EXISTS episodic_memory (
    id SERIAL PRIMARY KEY,
    executive_id VARCHAR(50) NOT NULL CHECK (executive_id ~ '^[a-zA-Z0-9_-]+$'),

    query TEXT NOT NULL,
    response TEXT NOT NULL,
    embedding vector(1024) NOT NULL,  -- BAAI/bge-m3 uses 1024 dimensions

    user_id VARCHAR(100),
    role VARCHAR(50),

    importance_score NUMERIC DEFAULT 0.5 CHECK (importance_score BETWEEN 0 AND 1),
    context_sources JSONB,

    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    feedback VARCHAR(20) CHECK (feedback IN ('positive', 'negative', 'neutral'))
);

CREATE INDEX IF NOT EXISTS idx_episodic_executive ON episodic_memory(executive_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_episodic_user ON episodic_memory(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_episodic_importance ON episodic_memory(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_episodic_embedding ON episodic_memory USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_episodic_query_text ON episodic_memory USING GIN(to_tsvector('english', query));

-- ============================================
-- Executive Memories (Legacy)
-- ============================================
CREATE TABLE IF NOT EXISTS executive_memories (
    id SERIAL PRIMARY KEY,
    executive_id VARCHAR(50) REFERENCES executive_profiles(id) ON DELETE CASCADE,

    memory_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,

    importance INTEGER CHECK (importance BETWEEN 1 AND 10) DEFAULT 5,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memory_exec ON executive_memories(executive_id);
CREATE INDEX IF NOT EXISTS idx_memory_type ON executive_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_importance ON executive_memories(importance DESC);

-- ============================================
-- Embeddings (Vector Storage)
-- ============================================
CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,

    -- What this embedding represents
    source_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,

    -- Text that was embedded
    text_content TEXT NOT NULL,
    chunk_index INTEGER DEFAULT 0,

    -- Vector embedding (1024 dimensions - BAAI/bge-m3)
    embedding vector(1024),

    -- Metadata
    model VARCHAR(50) DEFAULT 'text-embedding-ada-002',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(source_type, source_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_embedding_source ON embeddings(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_embedding_vector ON embeddings USING hnsw (embedding vector_cosine_ops);

-- ============================================
-- Section Embeddings (Dedicated for Document Sections)
-- ============================================
CREATE TABLE IF NOT EXISTS section_embeddings (
    id SERIAL PRIMARY KEY,
    section_id VARCHAR(100) NOT NULL UNIQUE REFERENCES document_sections(id) ON DELETE CASCADE,

    text_content TEXT NOT NULL,
    embedding vector(1024) NOT NULL,  -- BAAI/bge-m3 uses 1024 dimensions

    model VARCHAR(100) DEFAULT 'BAAI/bge-m3',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_section_emb_section ON section_embeddings(section_id);
CREATE INDEX IF NOT EXISTS idx_section_emb_vector ON section_embeddings USING hnsw (embedding vector_cosine_ops);

-- ============================================
-- FUNCTIONS
-- ============================================

-- ============================================
-- Timestamp Update Function
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Session Expiration Auto-Calculator
-- ============================================
CREATE OR REPLACE FUNCTION update_expires_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.expires_at = NEW.last_activity + INTERVAL '30 minutes';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Quality Score Update from Feedback
-- ============================================
CREATE OR REPLACE FUNCTION update_quality_from_feedback()
RETURNS TRIGGER AS $$
BEGIN
    -- Update quality score based on user feedback
    IF NEW.user_feedback = 1 THEN  -- Thumbs up
        NEW.quality_score = LEAST(1.0, NEW.quality_score + 0.1);
    ELSIF NEW.user_feedback = -1 THEN  -- Thumbs down
        NEW.quality_score = GREATEST(0.0, NEW.quality_score - 0.2);
    END IF;

    -- Set expiration for low-quality examples
    IF NEW.quality_score < 0.3 THEN
        NEW.expires_at = NOW() + INTERVAL '30 days';
    ELSIF NEW.quality_score < 0.5 THEN
        NEW.expires_at = NOW() + INTERVAL '90 days';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Episodic Memory Access Tracker
-- ============================================
CREATE OR REPLACE FUNCTION update_episodic_access()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_accessed = CURRENT_TIMESTAMP;
    NEW.access_count = OLD.access_count + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Get or Create Session
-- ============================================
CREATE OR REPLACE FUNCTION get_or_create_session(
    p_user_id VARCHAR(100),
    p_executive_id VARCHAR(50),
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS TEXT AS $$
DECLARE
    existing_session_id TEXT;
    new_session_id TEXT;
BEGIN
    -- Check for existing active session
    SELECT session_id INTO existing_session_id
    FROM conversation_sessions
    WHERE user_id = p_user_id
      AND executive_id = p_executive_id
      AND is_active = true
      AND last_activity > NOW() - INTERVAL '30 minutes'
    ORDER BY last_activity DESC
    LIMIT 1;

    -- Return existing session if found
    IF existing_session_id IS NOT NULL THEN
        RETURN existing_session_id;
    END IF;

    -- Create new session
    INSERT INTO conversation_sessions(
        user_id,
        executive_id,
        metadata
    ) VALUES (
        p_user_id,
        p_executive_id,
        p_metadata
    ) RETURNING session_id INTO new_session_id;

    RETURN new_session_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Update Session Activity
-- ============================================
CREATE OR REPLACE FUNCTION update_session_activity(
    p_session_id TEXT,
    p_tokens_used INTEGER DEFAULT 0,
    p_response_time_ms INTEGER DEFAULT 0
)
RETURNS VOID AS $$
BEGIN
    UPDATE conversation_sessions
    SET
        last_activity = NOW(),
        turn_count = turn_count + 1,
        total_tokens = total_tokens + p_tokens_used,
        avg_response_time_ms = (
            (avg_response_time_ms * (turn_count - 1) + p_response_time_ms) / turn_count
        )
    WHERE session_id = p_session_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Expire Inactive Sessions
-- ============================================
CREATE OR REPLACE FUNCTION expire_inactive_sessions()
RETURNS INTEGER AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE conversation_sessions
    SET is_active = false
    WHERE is_active = true
      AND expires_at < NOW();

    GET DIAGNOSTICS expired_count = ROW_COUNT;
    RETURN expired_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Get Best Communication Examples
-- ============================================
CREATE OR REPLACE FUNCTION get_best_examples(
    p_executive_id VARCHAR(50),
    p_query_type VARCHAR(50) DEFAULT NULL,
    p_max_examples INTEGER DEFAULT 5,
    p_include_bootstrap BOOLEAN DEFAULT TRUE,
    p_min_quality NUMERIC DEFAULT 0.3
)
RETURNS TABLE(
    id UUID,
    query TEXT,
    response TEXT,
    quality_score NUMERIC,
    usage_count INTEGER,
    success_rate NUMERIC,
    example_type VARCHAR(50),
    is_bootstrap BOOLEAN,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ce.id,
        ce.query,
        ce.response,
        ce.quality_score,
        ce.usage_count,
        ce.success_rate,
        ce.example_type,
        ce.is_bootstrap,
        ce.created_at
    FROM communication_examples ce
    WHERE ce.executive_id = p_executive_id
      AND ce.is_active = true
      AND ce.quality_score >= p_min_quality
      AND (p_include_bootstrap = true OR ce.is_bootstrap = false)
      AND (p_query_type IS NULL OR ce.query_type = p_query_type)
      AND (ce.expires_at IS NULL OR ce.expires_at > NOW())
    ORDER BY
        -- Prioritize high quality and successful examples
        (ce.quality_score * 0.4 + ce.success_rate * 0.3 + ce.usage_count * 0.3) DESC,
        -- Then by recency (favor recent examples)
        ce.created_at DESC
    LIMIT p_max_examples;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Update Example Usage
-- ============================================
CREATE OR REPLACE FUNCTION update_example_usage(
    p_example_id UUID,
    p_success BOOLEAN DEFAULT TRUE
)
RETURNS VOID AS $$
BEGIN
    UPDATE communication_examples
    SET
        usage_count = usage_count + 1,
        last_used = NOW(),
        success_rate = CASE
            WHEN p_success THEN
                (success_rate * usage_count + 1.0) / (usage_count + 1)
            ELSE
                (success_rate * usage_count + 0.0) / (usage_count + 1)
        END
    WHERE id = p_example_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Prune Old Examples
-- ============================================
CREATE OR REPLACE FUNCTION prune_old_examples(
    p_executive_id VARCHAR(50),
    p_max_examples INTEGER DEFAULT 20,
    p_min_quality NUMERIC DEFAULT 0.2
)
RETURNS INTEGER AS $$
DECLARE
    pruned_count INTEGER;
BEGIN
    -- Mark low-quality examples as inactive
    UPDATE communication_examples
    SET is_active = false
    WHERE executive_id = p_executive_id
      AND quality_score < p_min_quality;

    GET DIAGNOSTICS pruned_count = ROW_COUNT;

    -- If still too many examples, keep only the best ones
    IF (SELECT COUNT(*) FROM communication_examples
         WHERE executive_id = p_executive_id AND is_active = true) > p_max_examples THEN

        UPDATE communication_examples
        SET is_active = false
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (ORDER BY quality_score DESC, usage_count DESC, created_at DESC) as rn
                FROM communication_examples
                WHERE executive_id = p_executive_id
                  AND is_active = true
            ) ranked
            WHERE rn > p_max_examples
        );
    END IF;

    RETURN pruned_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Find Similar Sections
-- ============================================
CREATE OR REPLACE FUNCTION find_similar_sections(
    query_embedding vector(1024),  -- BAAI/bge-m3 uses 1024 dimensions
    result_limit INTEGER DEFAULT 10,
    min_similarity NUMERIC DEFAULT 0.5
)
RETURNS TABLE(
    section_id VARCHAR(100),
    section_title VARCHAR(500),
    content TEXT,
    similarity_score NUMERIC,
    parent_document_id VARCHAR(50),
    section_type VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id,
        s.section_title,
        s.content,
        (1 - (se.embedding <=> query_embedding))::DECIMAL as similarity,
        s.parent_document_id,
        s.section_type
    FROM section_embeddings se
    JOIN document_sections s ON se.section_id = s.id
    WHERE (1 - (se.embedding <=> query_embedding)) >= min_similarity
    ORDER BY se.embedding <=> query_embedding ASC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Get Document Sections
-- ============================================
CREATE OR REPLACE FUNCTION get_document_sections(doc_id VARCHAR(50))
RETURNS TABLE(
    section_id VARCHAR(100),
    section_number INTEGER,
    section_title VARCHAR(500),
    content TEXT,
    word_count INTEGER,
    section_type VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id,
        s.section_number,
        s.section_title,
        s.content,
        s.word_count,
        s.section_type
    FROM document_sections s
    WHERE s.parent_document_id = doc_id
    ORDER BY s.section_number ASC;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Validate Section References
-- ============================================
CREATE OR REPLACE FUNCTION validate_section_references()
RETURNS TABLE(
    invalid_section_id VARCHAR(100),
    parent_document_id VARCHAR(50),
    parent_document_type VARCHAR(50),
    issue TEXT
) AS $$
BEGIN
    -- Check decision sections
    RETURN QUERY
    SELECT
        s.id,
        s.parent_document_id,
        s.parent_document_type,
        'Parent decision not found'::TEXT
    FROM document_sections s
    WHERE s.parent_document_type = 'decision'
    AND NOT EXISTS (
        SELECT 1 FROM decision_cases d WHERE d.id = s.parent_document_id
    );

    -- Check policy sections
    RETURN QUERY
    SELECT
        s.id,
        s.parent_document_id,
        s.parent_document_type,
        'Parent policy not found'::TEXT
    FROM document_sections s
    WHERE s.parent_document_type = 'policy'
    AND NOT EXISTS (
        SELECT 1 FROM policy_documents p WHERE p.id = s.parent_document_id
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Compute Recency Score
-- ============================================
CREATE OR REPLACE FUNCTION compute_recency_score(interaction_timestamp TIMESTAMP)
RETURNS NUMERIC AS $$
DECLARE
    days_ago INTEGER;
BEGIN
    days_ago := EXTRACT(DAY FROM (CURRENT_TIMESTAMP - interaction_timestamp));
    RETURN GREATEST(0, 1.0 - (days_ago / 365.0));  -- Linear decay over 1 year
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- TRIGGERS
-- ============================================

-- Timestamp update triggers
DROP TRIGGER IF EXISTS update_exec_timestamp ON executive_profiles;
CREATE TRIGGER update_exec_timestamp
BEFORE UPDATE ON executive_profiles
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_decision_timestamp ON decision_cases;
CREATE TRIGGER update_decision_timestamp
BEFORE UPDATE ON decision_cases
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_policy_timestamp ON policy_documents;
CREATE TRIGGER update_policy_timestamp
BEFORE UPDATE ON policy_documents
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_section_timestamp ON document_sections;
CREATE TRIGGER update_section_timestamp
BEFORE UPDATE ON document_sections
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Session expiration trigger
DROP TRIGGER IF EXISTS trigger_update_expires_at ON conversation_sessions;
CREATE TRIGGER trigger_update_expires_at
BEFORE INSERT OR UPDATE ON conversation_sessions
FOR EACH ROW EXECUTE FUNCTION update_expires_at();

-- Communication quality trigger
DROP TRIGGER IF EXISTS update_quality_trigger ON communication_examples;
CREATE TRIGGER update_quality_trigger
BEFORE UPDATE ON communication_examples
FOR EACH ROW EXECUTE FUNCTION update_quality_from_feedback();

-- ============================================
-- VIEWS
-- ============================================

-- ============================================
-- Decisions by Executive
-- ============================================
CREATE OR REPLACE VIEW decisions_by_executive AS
SELECT
    e.id as executive_id,
    e.name as executive_name,
    e.title,
    d.id as decision_id,
    d.title as decision_title,
    d.date as decision_date,
    d.category,
    d.outcome,
    d.precedent
FROM executive_profiles e
LEFT JOIN decision_cases d ON e.id = d.executive_id
ORDER BY e.name, d.date DESC;

-- ============================================
-- Active Sessions
-- ============================================
CREATE OR REPLACE VIEW active_sessions AS
SELECT
    session_id,
    user_id,
    executive_id,
    started_at,
    last_activity,
    expires_at,
    turn_count,
    total_tokens,
    avg_response_time_ms,
    metadata,
    EXTRACT(EPOCH FROM (NOW() - last_activity))::INTEGER as seconds_since_last_activity,
    EXTRACT(EPOCH FROM (expires_at - NOW()))::INTEGER as seconds_until_expiry
FROM conversation_sessions
WHERE is_active = true
ORDER BY last_activity DESC;

-- ============================================
-- Active Communication Examples
-- ============================================
CREATE OR REPLACE VIEW active_communication_examples AS
SELECT
    id,
    executive_id,
    query,
    response,
    quality_score,
    usage_count,
    success_rate,
    example_type,
    query_type,
    is_bootstrap,
    created_at,
    last_used,
    (quality_score * 0.4 + success_rate * 0.3 + usage_count * 0.3) as ranking_score
FROM communication_examples
WHERE is_active = true
  AND (expires_at IS NULL OR expires_at > NOW());

-- ============================================
-- Session Statistics
-- ============================================
CREATE OR REPLACE VIEW session_statistics AS
SELECT
    executive_id,
    COUNT(*) as total_sessions,
    COUNT(CASE WHEN is_active THEN 1 END) as active_sessions,
    AVG(turn_count) as avg_turns_per_session,
    AVG(total_tokens) as avg_tokens_per_session,
    AVG(avg_response_time_ms) as avg_response_time_ms,
    MAX(started_at) as last_session_date
FROM conversation_sessions
GROUP BY executive_id;

-- ============================================
-- Section Statistics
-- ============================================
CREATE OR REPLACE VIEW section_statistics AS
WITH doc_section_counts AS (
    SELECT
        parent_document_id,
        parent_document_type,
        COUNT(*) as section_count
    FROM document_sections
    GROUP BY parent_document_id, parent_document_type
)
SELECT
    s.parent_document_type,
    COUNT(*) as total_sections,
    AVG(s.word_count) as avg_words_per_section,
    MIN(s.word_count) as min_words,
    MAX(s.word_count) as max_words,
    COUNT(DISTINCT s.parent_document_id) as total_documents,
    AVG(dsc.section_count) as avg_sections_per_doc
FROM document_sections s
JOIN doc_section_counts dsc ON s.parent_document_id = dsc.parent_document_id
GROUP BY s.parent_document_type;

-- ============================================
-- Sections with Parent Info
-- ============================================
CREATE OR REPLACE VIEW sections_with_parent AS
SELECT
    s.id,
    s.parent_document_id,
    s.parent_document_type,
    s.section_number,
    s.section_title,
    s.word_count,
    s.section_type,
    s.boundary_type,
    s.executive_id,
    s.document_category,
    s.document_date,
    -- Decision info
    d.title as decision_title,
    d.category as decision_category,
    d.date as decision_date,
    -- Policy info
    p.name as policy_name,
    p.category as policy_category,
    p.effective_date as policy_date,
    -- Executive info
    e.name as executive_name,
    e.title as executive_title
FROM document_sections s
LEFT JOIN decision_cases d ON s.parent_document_id = d.id AND s.parent_document_type = 'decision'
LEFT JOIN policy_documents p ON s.parent_document_id = p.id AND s.parent_document_type = 'policy'
LEFT JOIN executive_profiles e ON s.executive_id = e.id;

-- ============================================
-- Executive Memory (Alias for Episodic Memory)
-- ============================================
CREATE OR REPLACE VIEW executive_memory AS
SELECT
    id,
    executive_id,
    query,
    response,
    embedding,
    user_id,
    role,
    importance_score,
    context_sources,
    timestamp,
    last_accessed,
    access_count
FROM episodic_memory;

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
DECLARE
    table_count INTEGER;
    view_count INTEGER;
    function_count INTEGER;
    trigger_count INTEGER;
BEGIN
    -- Count tables
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND table_name IN (
        'executive_profiles',
        'decision_cases',
        'policy_documents',
        'document_sections',
        'conversation_sessions',
        'conversations',
        'communication_examples',
        'episodic_memory',
        'executive_memories',
        'embeddings',
        'section_embeddings'
    );

    -- Count views
    SELECT COUNT(*) INTO view_count
    FROM information_schema.views
    WHERE table_schema = 'public';

    -- Count custom functions
    SELECT COUNT(*) INTO function_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'public'
      AND p.proname IN (
        'update_updated_at',
        'update_expires_at',
        'update_quality_from_feedback',
        'update_episodic_access',
        'get_or_create_session',
        'update_session_activity',
        'expire_inactive_sessions',
        'get_best_examples',
        'update_example_usage',
        'prune_old_examples',
        'find_similar_sections',
        'get_document_sections',
        'validate_section_references',
        'compute_recency_score'
      );

    -- Count triggers
    SELECT COUNT(*) INTO trigger_count
    FROM pg_trigger t
    JOIN pg_class c ON t.tgrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'public'
      AND NOT t.tgisinternal;

    RAISE NOTICE '============================================';
    RAISE NOTICE 'Schema Verification Summary (non-destructive)';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Tables created: % (expected: 11)', table_count;
    RAISE NOTICE 'Views created: % (expected: 7)', view_count;
    RAISE NOTICE 'Functions created: % (expected: 14)', function_count;
    RAISE NOTICE 'Triggers created: % (expected: 6)', trigger_count;
    RAISE NOTICE '============================================';

    IF table_count = 11 AND view_count = 7 AND function_count = 14 AND trigger_count = 6 THEN
        RAISE NOTICE '✓ All schema objects created successfully!';
    ELSE
        RAISE WARNING '✗ Some schema objects may be missing. Please verify.';
    END IF;
END $$;
