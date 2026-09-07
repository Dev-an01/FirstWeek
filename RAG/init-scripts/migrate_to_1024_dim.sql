-- ============================================================================
-- MIGRATION: vector(768) → vector(1024)
-- Purpose: Upgrade embedding dimensions for BAAI/bge-m3 multilingual model
-- Date: 2025-12-28
-- ============================================================================

-- Start transaction
BEGIN;

-- ============================================================================
-- PHASE 1: Drop existing HNSW indexes (they're tied to old dimension)
-- ============================================================================

DROP INDEX IF EXISTS idx_comm_examples_embedding;
DROP INDEX IF EXISTS idx_embedding_vector;
DROP INDEX IF EXISTS idx_episodic_embedding;
DROP INDEX IF EXISTS idx_section_emb_vector;

-- Also drop any potential executive_memory index
DROP INDEX IF EXISTS idx_executive_memory_embedding;

RAISE NOTICE 'Phase 1: Dropped existing HNSW indexes';

-- ============================================================================
-- PHASE 2: Clear existing embeddings (incompatible with new dimension)
-- ============================================================================

-- Set embeddings to NULL (they need to be regenerated with new model)
UPDATE communication_examples SET embedding = NULL WHERE embedding IS NOT NULL;
UPDATE embeddings SET embedding = NULL WHERE embedding IS NOT NULL;
UPDATE episodic_memory SET embedding = NULL WHERE embedding IS NOT NULL;
UPDATE executive_memory SET embedding = NULL WHERE embedding IS NOT NULL;
UPDATE section_embeddings SET embedding = NULL WHERE embedding IS NOT NULL;

RAISE NOTICE 'Phase 2: Cleared existing embeddings (will need regeneration)';

-- ============================================================================
-- PHASE 3: ALTER column types from vector(768) to vector(1024)
-- ============================================================================

ALTER TABLE communication_examples
    ALTER COLUMN embedding TYPE vector(1024);

ALTER TABLE embeddings
    ALTER COLUMN embedding TYPE vector(1024);

ALTER TABLE episodic_memory
    ALTER COLUMN embedding TYPE vector(1024);

ALTER TABLE executive_memory
    ALTER COLUMN embedding TYPE vector(1024);

ALTER TABLE section_embeddings
    ALTER COLUMN embedding TYPE vector(1024);

RAISE NOTICE 'Phase 3: Altered columns to vector(1024)';

-- ============================================================================
-- PHASE 4: Create optimized HNSW indexes for 1024-dim vectors
-- HNSW parameters optimized for 1024 dimensions:
--   m = 24 (connections per node, higher for larger dimensions)
--   ef_construction = 128 (build-time accuracy, higher = better quality)
-- ============================================================================

-- Index on communication_examples (only active examples)
CREATE INDEX idx_comm_examples_embedding
    ON communication_examples USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128)
    WHERE is_active = true;

-- Main embeddings index
CREATE INDEX idx_embedding_vector
    ON embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);

-- Episodic memory index
CREATE INDEX idx_episodic_embedding
    ON episodic_memory USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);

-- Executive memory index (new)
CREATE INDEX idx_executive_memory_embedding
    ON executive_memory USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);

-- Section embeddings index
CREATE INDEX idx_section_emb_vector
    ON section_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);

RAISE NOTICE 'Phase 4: Created HNSW indexes optimized for 1024-dim vectors';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Commit transaction
COMMIT;

-- Show updated schema
SELECT
    c.relname as table_name,
    a.attname as column_name,
    format_type(a.atttypid, a.atttypmod) as data_type
FROM pg_attribute a
JOIN pg_class c ON a.attrelid = c.oid
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE n.nspname = 'public'
AND format_type(a.atttypid, a.atttypmod) LIKE 'vector%'
AND a.attnum > 0
ORDER BY c.relname;

-- Show new indexes
SELECT
    t.relname as table_name,
    i.relname as index_name,
    am.amname as index_type
FROM pg_index ix
JOIN pg_class t ON t.oid = ix.indrelid
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_am am ON i.relam = am.oid
JOIN pg_namespace n ON t.relnamespace = n.oid
WHERE n.nspname = 'public'
AND am.amname = 'hnsw'
ORDER BY t.relname;
