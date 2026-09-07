#!/bin/bash
set -e

echo "=========================================="
echo "PostgreSQL Initialization Script"
echo "=========================================="

# Wait for PostgreSQL to be ready
until pg_isready -h localhost -U "$POSTGRES_USER"; do
  echo "Waiting for PostgreSQL to be ready..."
  sleep 2
done

echo "✅ PostgreSQL is ready"

# Create vector extension
echo "📦 Creating pgvector extension..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "✅ pgvector extension created"

# Run main schema
if [ -f /docker-entrypoint-initdb.d/postgres_schema.sql ]; then
    echo "📋 Loading main schema..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/postgres_schema.sql
    echo "✅ Main schema loaded"
fi

# Run episodic memory schema
if [ -f /docker-entrypoint-initdb.d/episodic_memory_schema.sql ]; then
    echo "📋 Loading episodic memory schema..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/episodic_memory_schema.sql
    echo "✅ Episodic memory schema loaded"
fi

echo "=========================================="
echo "✅ PostgreSQL initialization complete"
echo "=========================================="
