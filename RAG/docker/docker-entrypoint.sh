#!/bin/bash
set -e

echo "=========================================="
echo "AI Officer RAG System - Docker Startup"
echo "=========================================="

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL..."
POSTGRES_HOST=${POSTGRES_HOST:-postgres}
while ! pg_isready -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; do
  echo "  Waiting for PostgreSQL at $POSTGRES_HOST:${POSTGRES_PORT:-5432}..."
  sleep 2
done
echo "✅ PostgreSQL is ready"

# Wait for Neo4j (check HTTP port instead of cypher-shell)
echo "⏳ Waiting for Neo4j..."
MAX_RETRIES=60
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if curl -s http://neo4j:7474 > /dev/null 2>&1; then
    echo "✅ Neo4j is ready"
    break
  fi
  RETRY_COUNT=$((RETRY_COUNT + 1))
  sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "❌ Neo4j failed to start in time"
  exit 1
fi

echo ""
echo "=========================================="
echo "📦 Checking Models"
echo "=========================================="

# Function to download Kokoro models
download_kokoro_models() {
  echo "⬇️  Downloading Kokoro TTS models (first run only)..."
  mkdir -p /app/models/kokoro/voices

  echo "  → Downloading base model (327 MB)..."
  curl -sL -o /app/models/kokoro/kokoro-v1_0.pth \
    "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/kokoro-v1_0.pth"

  curl -sL -o /app/models/kokoro/config.json \
    "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/config.json"

  echo "  → Downloading English voices..."
  curl -sL -o /app/models/kokoro/voices/af_bella.pt \
    "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/af_bella.pt"

  curl -sL -o /app/models/kokoro/voices/af_heart.pt \
    "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/af_heart.pt"

  echo "  → Downloading Japanese voices..."
  curl -sL -o /app/models/kokoro/voices/jf_alpha.pt \
    "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/jf_alpha.pt"

  curl -sL -o /app/models/kokoro/voices/jf_gongitsune.pt \
    "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/jf_gongitsune.pt"

  echo "✅ Kokoro models downloaded successfully"
}

# Check if Kokoro models exist, download if missing
if [ ! -f "/app/models/kokoro/kokoro-v1_0.pth" ]; then
  download_kokoro_models
else
  echo "✅ Kokoro models already present (cached)"
fi

# Whisper models auto-download via faster-whisper library
echo "✅ Whisper models will auto-download on first use"

echo ""
echo "=========================================="
echo "📊 Checking Database Schema & Data"
echo "=========================================="

# Function to check embedding dimension
check_embedding_dimension() {
  echo "  → Checking embeddings table schema..."

  # Check if embeddings table exists
  TABLE_EXISTS=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='embeddings';" 2>/dev/null | tr -d ' ')

  if [ -z "$TABLE_EXISTS" ] || [ "$TABLE_EXISTS" -eq "0" ]; then
    echo "  ℹ️  No schema found - will initialize fresh"
    return 2  # No schema
  fi

  # Get embedding dimension from schema
  DIMENSION=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
    "SELECT atttypmod - 4 FROM pg_attribute WHERE attrelid = 'embeddings'::regclass AND attname = 'embedding';" 2>/dev/null | tr -d ' ')

  if [ -z "$DIMENSION" ]; then
    echo "  ⚠️  Could not detect dimension"
    return 2
  fi

  echo "  ℹ️  Current schema: vector($DIMENSION)"

  if [ "$DIMENSION" -eq "768" ]; then
    echo "  ⚠️  OLD SCHEMA DETECTED (768 dimensions)"
    echo "  🔄 Migration required: 768 → 1024 dimensions"
    return 0  # Old schema
  elif [ "$DIMENSION" -eq "1024" ]; then
    echo "  ✅ Correct schema (1024 dimensions)"
    return 1  # Correct schema
  else
    echo "  ⚠️  Non-standard dimension: $DIMENSION (need 1024)"
    echo "  🔄 Migration required: $DIMENSION → 1024 dimensions"
    return 0  # Treat as old schema → safe migration (preserves data)
  fi
}

# Function to update schema for new embedding dimensions
# IMPORTANT: Preserves onboarding data (companies, executives, documents)
recreate_schema() {
  echo "  🔄 Updating schema for 1024-dim embeddings..."
  echo "  ⚠️  Preserving onboarding data (companies, executives, documents)"

  # Only drop and recreate embedding-related tables, preserve onboarding data
  PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
    -- Clear old embeddings (wrong dimensions)
    TRUNCATE TABLE embeddings CASCADE;
    TRUNCATE TABLE section_embeddings CASCADE;
    TRUNCATE TABLE episodic_memory CASCADE;
    TRUNCATE TABLE communication_examples CASCADE;

    -- Update embedding column dimensions if needed
    ALTER TABLE embeddings DROP COLUMN IF EXISTS embedding;
    ALTER TABLE embeddings ADD COLUMN embedding vector(1024);

    ALTER TABLE section_embeddings DROP COLUMN IF EXISTS embedding;
    ALTER TABLE section_embeddings ADD COLUMN embedding vector(1024) NOT NULL;

    ALTER TABLE episodic_memory DROP COLUMN IF EXISTS embedding;
    ALTER TABLE episodic_memory ADD COLUMN embedding vector(1024) NOT NULL;

    ALTER TABLE communication_examples DROP COLUMN IF EXISTS embedding;
    ALTER TABLE communication_examples ADD COLUMN embedding vector(1024);

    -- Recreate HNSW indexes
    DROP INDEX IF EXISTS idx_embedding_vector;
    CREATE INDEX idx_embedding_vector ON embeddings USING hnsw (embedding vector_cosine_ops);

    DROP INDEX IF EXISTS idx_section_emb_vector;
    CREATE INDEX idx_section_emb_vector ON section_embeddings USING hnsw (embedding vector_cosine_ops);

    DROP INDEX IF EXISTS idx_episodic_embedding;
    CREATE INDEX idx_episodic_embedding ON episodic_memory USING hnsw (embedding vector_cosine_ops);

    DROP INDEX IF EXISTS idx_comm_examples_embedding;
    CREATE INDEX idx_comm_examples_embedding ON communication_examples USING hnsw (embedding vector_cosine_ops) WHERE is_active = true;
EOSQL

  echo "  ✅ Schema updated to 1024 dimensions (onboarding data preserved)"
}

# Function to check if database has data
check_database_data() {
  echo "  → Checking if database has sample data..."

  # Check if executive_profiles table has data
  DATA_COUNT=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
    "SELECT COUNT(*) FROM executive_profiles WHERE id='sample_profile';" 2>/dev/null | tr -d ' ')

  if [ -z "$DATA_COUNT" ] || [ "$DATA_COUNT" -eq "0" ]; then
    return 1  # No data
  else
    return 0  # Has data
  fi
}

# Step 1: Check schema dimension
schema_status=1
check_embedding_dimension || schema_status=$?

# Step 2: Handle schema migration if needed
if [ $schema_status -eq 0 ]; then
  # Old 768-dim schema detected
  echo ""
  echo "  ⚙️  AUTO-MIGRATION: Upgrading schema to 1024 dimensions..."
  recreate_schema
  NEEDS_DATA_LOAD=true
elif [ $schema_status -eq 2 ]; then
  echo ""
  # Check if onboarding data exists that will be preserved
  EXEC_COUNT=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
    "SELECT COUNT(*) FROM executive_profiles;" 2>/dev/null | tr -d ' ')

  if [ -n "$EXEC_COUNT" ] && [ "$EXEC_COUNT" -gt "0" ]; then
    echo "  ⚙️  PARTIAL INSTALL: Creating missing tables (preserving $EXEC_COUNT executives)..."
  else
    echo "  ⚙️  FRESH INSTALL: Loading schema (1024 dimensions)..."
  fi

  PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /app/config/postgres_schema.sql
  echo "  ✅ Schema loaded"
  NEEDS_DATA_LOAD=true
else
  # Correct 1024-dim schema exists
  NEEDS_DATA_LOAD=false
fi

# Step 2.5: Always run onboarding migrations to ensure multi-tenant support
echo ""
echo "  📋 Running onboarding migrations..."
for migration in /app/config/onboarding_migration.sql /app/config/phase8_migration.sql /app/config/phase9_multitenant_migration.sql /app/config/phase10_ocr_metadata_migration.sql; do
  if [ -f "$migration" ]; then
    PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$migration" > /dev/null 2>&1 || true
    echo "    ✓ $(basename $migration)"
  fi
done
echo "  ✅ Migrations complete"

# Curated knowledge is managed through the FirstWeek index; no bundled persona seed.

# Step 4: Check for orphaned section embeddings (always runs)
echo ""
echo "  🔍 Checking for document sections without embeddings..."
ORPHAN_COUNT=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
  "SELECT COUNT(*) FROM document_sections ds LEFT JOIN section_embeddings se ON ds.id = se.section_id WHERE se.id IS NULL;" 2>/dev/null | tr -d ' ')

if [ -n "$ORPHAN_COUNT" ] && [ "$ORPHAN_COUNT" -gt "0" ]; then
  echo "  ⬇️  Found $ORPHAN_COUNT sections without embeddings — generating..."
  python3 /app/init-scripts/generate_embeddings.py --docker --sections-only || {
    echo "  ⚠️  Warning: Section embedding generation had issues (check logs)"
  }
  echo "  ✅ Section embeddings up to date"
else
  echo "  ✅ All document sections have embeddings"
fi

echo ""
echo "=========================================="
echo "🚀 Starting RAG API"
echo "=========================================="
echo ""

# Start the application
exec "$@"
