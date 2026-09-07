-- ============================================
-- Episodic Memory Schema
-- ============================================
-- Stores conversation history with embeddings for context retrieval
-- This table supports the memory_search.py module

-- Drop existing table if re-running
DROP TABLE IF EXISTS episodic_memory CASCADE;

-- ============================================
-- Episodic Memory Table
-- ============================================

CREATE TABLE episodic_memory (
    id SERIAL PRIMARY KEY,
    
    -- Executive context
    executive_id VARCHAR(50) NOT NULL,
    
    -- Conversation content
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    
    -- Vector embedding (768 dimensions for all-mpnet-base-v2)
    embedding vector(768) NOT NULL,
    
    -- User context
    user_id VARCHAR(100),
    role VARCHAR(50),
    
    -- Importance and metadata
    importance_score DECIMAL(3,2) DEFAULT 0.5 CHECK (importance_score BETWEEN 0 AND 1),
    context_sources JSONB,
    
    -- Timestamps
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    
    -- Indexing
    CONSTRAINT valid_executive_id CHECK (length(executive_id) > 0)
);

-- ============================================
-- Indexes for Performance
-- ============================================

-- Executive and timestamp for quick filtering
CREATE INDEX idx_episodic_executive ON episodic_memory(executive_id, timestamp DESC);

-- User queries
CREATE INDEX idx_episodic_user ON episodic_memory(user_id, timestamp DESC);

-- Importance for retrieval prioritization
CREATE INDEX idx_episodic_importance ON episodic_memory(importance_score DESC);

-- Vector similarity search (HNSW index for cosine similarity)
CREATE INDEX idx_episodic_embedding ON episodic_memory USING hnsw (embedding vector_cosine_ops);

-- Full-text search on queries
CREATE INDEX idx_episodic_query_text ON episodic_memory USING GIN(to_tsvector('english', query));

-- ============================================
-- Helper Functions
-- ============================================

-- Function to update access tracking
CREATE OR REPLACE FUNCTION update_episodic_access()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_accessed = CURRENT_TIMESTAMP;
    NEW.access_count = OLD.access_count + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Verification
-- ============================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'episodic_memory'
    ) THEN
        RAISE NOTICE '✓ Episodic memory table created successfully!';
    ELSE
        RAISE WARNING '✗ Failed to create episodic_memory table';
    END IF;
END $$;
