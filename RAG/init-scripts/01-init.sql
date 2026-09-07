-- Initialize pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create schema for embeddings
CREATE SCHEMA IF NOT EXISTS embeddings;

-- Create schema for memory
CREATE SCHEMA IF NOT EXISTS memory;

-- Grant permissions
GRANT ALL ON SCHEMA embeddings TO postgres;
GRANT ALL ON SCHEMA memory TO postgres;
