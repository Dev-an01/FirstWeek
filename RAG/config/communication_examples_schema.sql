-- ============================================
-- Communication Examples Schema
-- ============================================
-- Stores dynamic few-shot examples learned from successful interactions

-- Drop existing table if re-running
DROP TABLE IF EXISTS communication_examples CASCADE;

-- ============================================
-- Communication Examples Table
-- ============================================

CREATE TABLE communication_examples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Executive context
    executive_id VARCHAR(50) NOT NULL,
    
    -- Example content
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    
    -- Feedback and quality
    user_feedback INTEGER NOT NULL CHECK (user_feedback IN (-1, 0, 1)),
    quality_score DECIMAL(3,2) DEFAULT 0.5 CHECK (quality_score BETWEEN 0 AND 1),
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_bootstrap BOOLEAN DEFAULT false,
    example_type VARCHAR(50) DEFAULT 'general',
    query_type VARCHAR(50),
    context_sources JSONB DEFAULT '{}',
    
    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used TIMESTAMPTZ,
    success_rate DECIMAL(3,2) DEFAULT 0.0,
    
    -- Performance metrics
    avg_response_time_ms INTEGER,
    embedding vector(768),
    
    -- Expiration and freshness
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    
    -- Diversity management
    similarity_hash VARCHAR(64),
    diversity_cluster INTEGER,
    
    -- Constraints
    CONSTRAINT valid_executive_id CHECK (length(executive_id) > 0),
    CONSTRAINT valid_example_type CHECK (example_type IN ('email', 'slack', 'formal', 'casual', 'general')),
    CONSTRAINT valid_query_type CHECK (query_type IN ('approval', 'recommendation', 'information', 'decision', 'strategy', 'general'))
);

-- ============================================
-- Indexes for Performance
-- ============================================

-- Executive and timestamp for quick lookups
CREATE INDEX idx_comm_examples_executive ON communication_examples(executive_id, created_at DESC);

-- Active examples filter
CREATE INDEX idx_comm_examples_active ON communication_examples(executive_id, is_active) WHERE is_active = true;

-- Quality-based selection
CREATE INDEX idx_comm_examples_quality ON communication_examples(executive_id, quality_score DESC) WHERE is_active = true;

-- Usage-based selection
CREATE INDEX idx_comm_examples_usage ON communication_examples(executive_id, usage_count DESC) WHERE is_active = true;

-- Query type filtering
CREATE INDEX idx_comm_examples_query_type ON communication_examples(executive_id, query_type, quality_score DESC) WHERE is_active = true;

-- Bootstrap vs learned filtering
CREATE INDEX idx_comm_examples_bootstrap ON communication_examples(executive_id, is_bootstrap, created_at DESC);

-- Vector similarity search (HNSW index for cosine similarity)
CREATE INDEX idx_comm_examples_embedding ON communication_examples USING hnsw (embedding vector_cosine_ops) WHERE is_active = true;

-- Expiration cleanup
CREATE INDEX idx_comm_examples_expires ON communication_examples(expires_at) WHERE expires_at IS NOT NULL;

-- Diversity management
CREATE INDEX idx_comm_examples_diversity ON communication_examples(diversity_cluster, quality_score DESC) WHERE is_active = true;

-- ============================================
-- Helper Functions
-- ============================================

-- Function to update usage statistics
CREATE OR REPLACE FUNCTION update_example_usage(
    p_example_id UUID,
    p_success BOOLEAN DEFAULT true
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

-- Function to get best examples for executive
CREATE OR REPLACE FUNCTION get_best_examples(
    p_executive_id VARCHAR,
    p_query_type VARCHAR DEFAULT NULL,
    p_max_examples INTEGER DEFAULT 5,
    p_include_bootstrap BOOLEAN DEFAULT true,
    p_min_quality DECIMAL DEFAULT 0.3
)
RETURNS TABLE (
    id UUID,
    query TEXT,
    response TEXT,
    quality_score DECIMAL,
    usage_count INTEGER,
    success_rate DECIMAL,
    example_type VARCHAR,
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

-- Function to prune old examples
CREATE OR REPLACE FUNCTION prune_old_examples(
    p_executive_id VARCHAR,
    p_max_examples INTEGER DEFAULT 20,
    p_min_quality DECIMAL DEFAULT 0.2
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
-- Triggers
-- ============================================

-- Function to update quality score based on feedback
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

-- Apply trigger
CREATE TRIGGER update_quality_trigger
    BEFORE UPDATE OF user_feedback ON communication_examples
    FOR EACH ROW
    EXECUTE FUNCTION update_quality_from_feedback();

-- ============================================
-- Views
-- ============================================

-- Active examples view for easy querying
CREATE VIEW active_communication_examples AS
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
    -- Computed score for ranking
    (quality_score * 0.4 + success_rate * 0.3 + usage_count * 0.3) as ranking_score
FROM communication_examples
WHERE is_active = true
  AND (expires_at IS NULL OR expires_at > NOW());

-- ============================================
-- Verification
-- ============================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'communication_examples'
    ) THEN
        RAISE NOTICE '✓ Communication examples table created successfully!';
        
        -- Verify indexes
        DECLARE
            index_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO index_count
            FROM pg_indexes
            WHERE tablename = 'communication_examples'
              AND schemaname = 'public';
            
            RAISE NOTICE '✓ Created % indexes for communication_examples', index_count;
        END;
        
        -- Verify functions
        DECLARE
            func_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO func_count
            FROM information_schema.routines
            WHERE routine_schema = 'public'
              AND routine_name IN (
                  'update_example_usage',
                  'get_best_examples',
                  'prune_old_examples'
              );
            
            RAISE NOTICE '✓ Created % helper functions for example management', func_count;
        END;
        
    ELSE
        RAISE WARNING '✗ Failed to create communication_examples table';
    END IF;
END $$;