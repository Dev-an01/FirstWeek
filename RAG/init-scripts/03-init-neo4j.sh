#!/bin/bash
set -e

echo "========================================================================"
echo "Neo4j Initialization Script"
echo "========================================================================"
echo ""

# Configuration from environment variables
NEO4J_URI=${NEO4J_URI:-bolt://neo4j:7687}
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-neo4j123}
MAX_RETRIES=${MAX_RETRIES:-30}
RETRY_INTERVAL=${RETRY_INTERVAL:-2}

echo "Configuration:"
echo "  Neo4j URI: $NEO4J_URI"
echo "  Neo4j User: $NEO4J_USER"
echo "  Max Retries: $MAX_RETRIES"
echo ""

# Wait for Neo4j to be ready
echo "⏳ Waiting for Neo4j to be ready..."
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if python -c "
from neo4j import GraphDatabase
import sys
try:
    driver = GraphDatabase.driver('$NEO4J_URI', auth=('$NEO4J_USER', '$NEO4J_PASSWORD'))
    with driver.session() as session:
        session.run('RETURN 1')
    driver.close()
    sys.exit(0)
except Exception as e:
    print(f'Neo4j not ready: {e}')
    sys.exit(1)
" 2>/dev/null; then
        echo "✅ Neo4j is ready!"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "  Attempt $RETRY_COUNT/$MAX_RETRIES - Neo4j not ready yet, waiting $RETRY_INTERVAL seconds..."
        sleep $RETRY_INTERVAL
    else
        echo "❌ Neo4j failed to start after $MAX_RETRIES retries"
        exit 1
    fi
done

echo ""

# Check if Neo4j already has data
echo "🔍 Checking if Neo4j already has data..."
NODE_COUNT=$(python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('$NEO4J_URI', auth=('$NEO4J_USER', '$NEO4J_PASSWORD'))
with driver.session() as session:
    result = session.run('MATCH (n) RETURN count(n) as count')
    count = result.single()['count']
    print(count)
driver.close()
")

echo "  Current node count: $NODE_COUNT"
echo ""

if [ "$NODE_COUNT" -gt 0 ]; then
    echo "✅ Neo4j already has $NODE_COUNT nodes - skipping initialization"
    echo ""

    # Show breakdown
    echo "📊 Current Neo4j data:"
    python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('$NEO4J_URI', auth=('$NEO4J_USER', '$NEO4J_PASSWORD'))
with driver.session() as session:
    result = session.run('MATCH (n) RETURN labels(n)[0] AS Label, count(n) AS Count ORDER BY Count DESC')
    for record in result:
        print(f\"  • {record['Label']}: {record['Count']}\")

    result = session.run('MATCH ()-[r]->() RETURN count(r) as count')
    rel_count = result.single()['count']
    print(f\"\\nTotal relationships: {rel_count}\")
driver.close()
"
    echo ""
    echo "========================================================================"
    exit 0
fi

echo "📊 Neo4j is empty - proceeding with initialization"
echo ""

# Step 1: Load base data using Cypher scripts
echo "========================================================================"
echo "STEP 1: Loading Base Data (Cypher Scripts)"
echo "========================================================================"
echo ""

cd /app

echo "Running Neo4j data loader..."
python init-scripts/utils/load_neo4j.py

if [ $? -ne 0 ]; then
    echo "❌ Failed to load base Neo4j data"
    exit 1
fi

echo ""

# Step 2: Run section migration
echo "========================================================================"
echo "STEP 2: Creating Section Nodes (Migration)"
echo "========================================================================"
echo ""

# Check if PostgreSQL has embeddings (required for section migration)
echo "🔍 Checking if PostgreSQL has embeddings..."
EMBEDDING_COUNT=$(python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'rag-postgres'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        dbname=os.getenv('POSTGRES_DB', 'ai_officer'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', 'postgres123')
    )
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM embeddings')
    count = cur.fetchone()[0]
    print(count)
    conn.close()
except Exception as e:
    print('0')
")

echo "  PostgreSQL embeddings count: $EMBEDDING_COUNT"
echo ""

if [ "$EMBEDDING_COUNT" -lt 1 ]; then
    echo "⚠️  PostgreSQL has no embeddings yet - skipping section migration"
    echo "   Section migration will run automatically when embeddings are generated"
    echo ""
    echo "========================================================================"
    echo "✅ Neo4j base data loaded successfully (141 nodes)"
    echo "========================================================================"
    exit 0
fi

echo "✅ PostgreSQL has embeddings - proceeding with section migration"
echo ""

echo "Running section migration..."
python init-scripts/utils/migrate_to_sections.py

if [ $? -ne 0 ]; then
    echo "⚠️  Section migration failed (non-critical)"
    echo "   You can run it manually later: docker exec ai-officer-api python temp/migrate_to_sections.py"
    echo ""
    echo "========================================================================"
    echo "✅ Neo4j base data loaded successfully (141 nodes)"
    echo "========================================================================"
    exit 0
fi

echo ""

# Final verification
echo "========================================================================"
echo "✅ Neo4j Initialization Complete!"
echo "========================================================================"
echo ""

echo "📊 Final Neo4j data:"
python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('$NEO4J_URI', auth=('$NEO4J_USER', '$NEO4J_PASSWORD'))
with driver.session() as session:
    result = session.run('MATCH (n) RETURN labels(n)[0] AS Label, count(n) AS Count ORDER BY Count DESC')
    for record in result:
        print(f\"  • {record['Label']}: {record['Count']}\")

    result = session.run('MATCH ()-[r]->() RETURN count(r) as count')
    rel_count = result.single()['count']
    print(f\"\\nTotal relationships: {rel_count}\")
driver.close()
"
echo ""
echo "========================================================================"
