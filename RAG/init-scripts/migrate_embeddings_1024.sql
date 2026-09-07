-- ============================================
-- Embedding Dimension Migration: 768 -> 1024
-- ============================================
-- Run this script to migrate vector columns from 768 to 1024 dimensions
-- Required when upgrading from sentence-transformers to BAAI/bge-m3
--
-- IMPORTANT: This will DELETE all existing embeddings!
-- You must re-run embedding generation after this migration.
-- ============================================

-- Step 1: Drop existing HNSW indexes (required before altering column type)
DROP INDEX IF EXISTS idx_comm_examples_embedding;
DROP INDEX IF EXISTS idx_episodic_embedding;
DROP INDEX IF EXISTS idx_embedding_vector;
DROP INDEX IF EXISTS idx_section_emb_vector;

-- Step 2: Clear existing embeddings (they're incompatible with new model)
UPDATE communication_examples SET embedding = NULL;
DELETE FROM episodic_memory;
DELETE FROM embeddings;
DELETE FROM section_embeddings;

-- Step 3: Alter column types from vector(768) to vector(1024)
ALTER TABLE communication_examples
    ALTER COLUMN embedding TYPE vector(1024);

ALTER TABLE episodic_memory
    ALTER COLUMN embedding TYPE vector(1024);

ALTER TABLE embeddings
    ALTER COLUMN embedding TYPE vector(1024);

ALTER TABLE section_embeddings
    ALTER COLUMN embedding TYPE vector(1024);

-- Step 4: Recreate HNSW indexes with new dimension
CREATE INDEX idx_comm_examples_embedding ON communication_examples
    USING hnsw (embedding vector_cosine_ops) WHERE is_active = true;

CREATE INDEX idx_episodic_embedding ON episodic_memory
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_embedding_vector ON embeddings
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_section_emb_vector ON section_embeddings
    USING hnsw (embedding vector_cosine_ops);

-- Step 5: Update the find_similar_sections function to use 1024 dimensions
CREATE OR REPLACE FUNCTION find_similar_sections(
    query_embedding vector(1024),
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

-- Step 6: Verify migration
DO $$
DECLARE
    v_comm_dim INTEGER;
    v_episodic_dim INTEGER;
    v_embed_dim INTEGER;
    v_section_dim INTEGER;
BEGIN
    -- Check dimensions
    SELECT atttypmod INTO v_comm_dim
    FROM pg_attribute a
    JOIN pg_class c ON a.attrelid = c.oid
    WHERE c.relname = 'communication_examples' AND a.attname = 'embedding';

    SELECT atttypmod INTO v_episodic_dim
    FROM pg_attribute a
    JOIN pg_class c ON a.attrelid = c.oid
    WHERE c.relname = 'episodic_memory' AND a.attname = 'embedding';

    SELECT atttypmod INTO v_embed_dim
    FROM pg_attribute a
    JOIN pg_class c ON a.attrelid = c.oid
    WHERE c.relname = 'embeddings' AND a.attname = 'embedding';

    SELECT atttypmod INTO v_section_dim
    FROM pg_attribute a
    JOIN pg_class c ON a.attrelid = c.oid
    WHERE c.relname = 'section_embeddings' AND a.attname = 'embedding';

    RAISE NOTICE '============================================';
    RAISE NOTICE 'Embedding Migration Complete';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'communication_examples.embedding: vector(%)' , v_comm_dim;
    RAISE NOTICE 'episodic_memory.embedding: vector(%)', v_episodic_dim;
    RAISE NOTICE 'embeddings.embedding: vector(%)', v_embed_dim;
    RAISE NOTICE 'section_embeddings.embedding: vector(%)', v_section_dim;
    RAISE NOTICE '============================================';
    RAISE NOTICE 'IMPORTANT: Run embedding regeneration script next!';
    RAISE NOTICE '============================================';
END $$;
