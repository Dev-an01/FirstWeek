"""
Migration Script: Convert Documents to Semantic Sections

This script:
1. Reads existing documents from PostgreSQL (decision_cases, policy_documents)
2. Uses SemanticChunker to split them into sections
3. Stores sections in PostgreSQL (document_sections + section_embeddings)
4. Stores sections in Neo4j (Section nodes with relationships)
5. Provides rollback capability if anything fails

Run this AFTER:
- PostgreSQL document_sections_schema.sql has been executed
- Neo4j 07_create_section_schema.cypher has been executed

Expected Results:
- ~20 decision cases → ~60-80 sections
- ~12 policy documents → ~30-40 sections
- Total: ~90-120 sections
"""

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
import psycopg2
from psycopg2.extras import execute_batch
from neo4j import GraphDatabase
import traceback
from dotenv import load_dotenv

# Add app directory to path (for imports like hybrid_retrieval)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / '.env')

# Database configurations
POSTGRES_CONFIG = {
    'dbname': os.getenv('POSTGRES_DB', 'ai_officer'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres123'),
    'host': os.getenv('POSTGRES_HOST', 'rag-postgres'),
    'port': int(os.getenv('POSTGRES_PORT', '5432'))
}

NEO4J_CONFIG = {
    'uri': os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    'user': os.getenv('NEO4J_USER', 'neo4j'),
    'password': os.getenv('NEO4J_PASSWORD', '12341234')
}

from hybrid_retrieval.semantic_chunker import create_semantic_chunker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler('migration_to_sections.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SectionMigration:
    """
    Manages the migration of documents to semantic sections.
    """

    def __init__(
        self,
        postgres_config: Dict = None,
        neo4j_config: Dict = None,
        dry_run: bool = False
    ):
        """
        Initialize migration manager.

        Args:
            postgres_config: PostgreSQL connection config
            neo4j_config: Neo4j connection config
            dry_run: If True, don't actually write to databases
        """
        self.postgres_config = postgres_config or POSTGRES_CONFIG
        self.neo4j_config = neo4j_config or NEO4J_CONFIG
        self.dry_run = dry_run

        self.pg_conn = None
        self.neo4j_driver = None
        self.chunker = None

        logger.info("="  * 70)
        logger.info("Semantic Section Migration")
        logger.info("=" * 70)
        if dry_run:
            logger.warning("🔍 DRY RUN MODE - No changes will be written")

    def connect_databases(self):
        """Connect to PostgreSQL and Neo4j."""
        logger.info("\n📡 Connecting to databases...")

        # PostgreSQL
        try:
            self.pg_conn = psycopg2.connect(**self.postgres_config)
            logger.info("✅ PostgreSQL connected")
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            raise

        # Neo4j
        try:
            self.neo4j_driver = GraphDatabase.driver(
                self.neo4j_config['uri'],
                auth=(self.neo4j_config['user'], self.neo4j_config['password'])
            )
            # Test connection
            with self.neo4j_driver.session() as session:
                session.run("RETURN 1")
            logger.info("✅ Neo4j connected")
        except Exception as e:
            logger.error(f"❌ Neo4j connection failed: {e}")
            raise

    def initialize_chunker(self):
        """Initialize semantic chunker with embedding model."""
        logger.info("\n🔧 Initializing semantic chunker...")
        try:
            self.chunker = create_semantic_chunker(
                model_name='BAAI/bge-m3',  # MIGRATED: multilingual model
                min_section_words=50,
                max_section_words=1000
            )
            logger.info("✅ Semantic chunker initialized")
        except Exception as e:
            logger.error(f"❌ Chunker initialization failed: {e}")
            raise

    def verify_schemas(self) -> bool:
        """Verify that required tables and nodes exist."""
        logger.info("\n🔍 Verifying database schemas...")

        # Check PostgreSQL tables
        cursor = self.pg_conn.cursor()
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('document_sections', 'section_embeddings')
        """)
        pg_tables = [row[0] for row in cursor.fetchall()]

        if 'document_sections' not in pg_tables:
            logger.error("❌ PostgreSQL: document_sections table not found")
            logger.error("   Run: config/document_sections_schema.sql first")
            return False

        if 'section_embeddings' not in pg_tables:
            logger.error("❌ PostgreSQL: section_embeddings table not found")
            logger.error("   Run: config/document_sections_schema.sql first")
            return False

        logger.info("✅ PostgreSQL: Required tables exist")

        # Check Neo4j constraints
        with self.neo4j_driver.session() as session:
            result = session.run("""
                SHOW CONSTRAINTS
                WHERE entityType = "NODE" AND labelsOrTypes CONTAINS "Section"
            """)
            constraints = list(result)

        if not constraints:
            logger.warning("⚠️  Neo4j: Section constraints not found")
            logger.warning("   Run: test_data/graph_data/cypher/07_create_section_schema.cypher first")
            logger.warning("   Continuing anyway, but indexes may not be optimal")
        else:
            logger.info("✅ Neo4j: Section schema exists")

        return True

    def fetch_documents(self) -> Tuple[List[Dict], List[Dict]]:
        """Fetch decision cases and policy documents from PostgreSQL."""
        logger.info("\n📚 Fetching documents from PostgreSQL...")

        cursor = self.pg_conn.cursor()

        # Fetch decision cases
        cursor.execute("""
            SELECT id, title, situation, decision_made, rationale, outcome, lessons_learned,
                   'decision' as doc_type, executive_id, date, category
            FROM decision_cases
            ORDER BY id
        """)
        decision_rows = cursor.fetchall()
        decisions = []
        for row in decision_rows:
            # Concatenate all text fields
            full_text = '\n\n'.join(filter(None, [
                f"# {row[1]}",  # title
                f"## Situation\n{row[2]}" if row[2] else None,
                f"## Decision\n{row[3]}" if row[3] else None,
                f"## Rationale\n{row[4]}" if row[4] else None,
                f"## Outcome\n{row[5]}" if row[5] else None,
                f"## Lessons Learned\n{row[6]}" if row[6] else None
            ]))

            decisions.append({
                'id': row[0],
                'title': row[1],
                'text': full_text,
                'doc_type': row[7],
                'executive_id': row[8],
                'created_at': row[9],
                'category': row[10]
            })

        logger.info(f"  📄 Found {len(decisions)} decision cases")

        # Fetch policy documents
        cursor.execute("""
            SELECT id, name, content_markdown, 'policy' as doc_type,
                   owner_executive, effective_date, category
            FROM policy_documents
            ORDER BY id
        """)
        policy_rows = cursor.fetchall()
        policies = []
        for row in policy_rows:
            policies.append({
                'id': row[0],
                'title': row[1],
                'text': row[2],
                'doc_type': row[3],
                'executive_id': row[4],
                'created_at': row[5],
                'category': row[6]
            })

        logger.info(f"  📄 Found {len(policies)} policy documents")

        return decisions, policies

    def chunk_documents(self, documents: List[Dict]) -> List[Dict]:
        """Chunk documents into sections using SemanticChunker."""
        logger.info(f"\n✂️  Chunking {len(documents)} documents...")

        all_sections = []
        for doc in documents:
            try:
                sections = self.chunker.chunk_document(doc, doc['text'])
                all_sections.extend(sections)
                logger.info(f"  ✓ {doc['id']}: {len(sections)} sections")
            except Exception as e:
                logger.error(f"  ✗ {doc['id']}: Failed to chunk - {e}")
                continue

        logger.info(f"✅ Created {len(all_sections)} sections total")
        return all_sections

    def store_sections_postgresql(self, sections: List[Dict]):
        """Store sections in PostgreSQL tables."""
        if self.dry_run:
            logger.info(f"\n💾 [DRY RUN] Would store {len(sections)} sections in PostgreSQL")
            return

        logger.info(f"\n💾 Storing {len(sections)} sections in PostgreSQL...")

        cursor = self.pg_conn.cursor()

        # Insert into document_sections
        section_values = []
        for s in sections:
            section_values.append((
                s['id'],
                s['parent_document_id'],
                s['parent_metadata']['doc_type'],
                s['section_number'],
                s['section_title'],
                s['content'],
                s['word_count'],
                s['section_type'],
                s['boundary_type'],
                s['boundary_confidence'],
                s['parent_metadata'].get('executive_id'),
                s['parent_metadata'].get('doc_type'),
                s.get('created_at')
            ))

        execute_batch(cursor, """
            INSERT INTO document_sections (
                id, parent_document_id, parent_document_type, section_number,
                section_title, content, word_count, section_type,
                boundary_type, boundary_confidence, executive_id,
                document_category, document_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                content = EXCLUDED.content,
                updated_at = CURRENT_TIMESTAMP
        """, section_values)

        logger.info(f"  ✓ Inserted {len(section_values)} sections")

        # Insert into section_embeddings
        embedding_values = []
        for s in sections:
            if s['embedding'] is not None:
                embedding_values.append((
                    s['id'],
                    s['content'],
                    s['embedding']
                ))

        if embedding_values:
            execute_batch(cursor, """
                INSERT INTO section_embeddings (section_id, text_content, embedding)
                VALUES (%s, %s, %s)
                ON CONFLICT (section_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    created_at = CURRENT_TIMESTAMP
            """, embedding_values)

            logger.info(f"  ✓ Inserted {len(embedding_values)} embeddings")

        self.pg_conn.commit()
        logger.info("✅ PostgreSQL storage complete")

    def store_sections_neo4j(self, sections: List[Dict]):
        """Store sections in Neo4j as Section nodes."""
        if self.dry_run:
            logger.info(f"\n🕸️  [DRY RUN] Would store {len(sections)} sections in Neo4j")
            return

        logger.info(f"\n🕸️  Storing {len(sections)} sections in Neo4j...")

        with self.neo4j_driver.session() as session:
            # Batch create Section nodes with HAS_SECTION relationships
            section_data = []
            for s in sections:
                section_data.append({
                    'id': s['id'],
                    'parent_document_id': s['parent_document_id'],
                    'parent_document_type': s['parent_metadata']['doc_type'],
                    'section_number': s['section_number'],
                    'section_title': s['section_title'],
                    'word_count': s['word_count'],
                    'section_type': s['section_type'],
                    'boundary_type': s['boundary_type'],
                    'boundary_confidence': float(s['boundary_confidence'])
                })

            result = session.run("""
                UNWIND $sections AS section
                MERGE (s:Section {id: section.id})
                SET s.parent_document_id = section.parent_document_id,
                    s.parent_document_type = section.parent_document_type,
                    s.section_number = section.section_number,
                    s.section_title = section.section_title,
                    s.word_count = section.word_count,
                    s.section_type = section.section_type,
                    s.boundary_type = section.boundary_type,
                    s.boundary_confidence = section.boundary_confidence
                WITH s, section
                MATCH (parent)
                WHERE parent.id = section.parent_document_id
                  AND (parent:Decision OR parent:Policy)
                MERGE (parent)-[:HAS_SECTION]->(s)
                RETURN count(s) AS sections_created
            """, sections=section_data)

            count = result.single()['sections_created']
            logger.info(f"  ✓ Created {count} Section nodes with HAS_SECTION relationships")

            # Create sequential PRECEDES/FOLLOWS relationships
            result = session.run("""
                MATCH (s1:Section), (s2:Section)
                WHERE s1.parent_document_id = s2.parent_document_id
                  AND s1.section_number + 1 = s2.section_number
                MERGE (s1)-[:PRECEDES]->(s2)
                MERGE (s2)-[:FOLLOWS]->(s1)
                RETURN count(*) AS links_created
            """)

            links = result.single()['links_created']
            logger.info(f"  ✓ Created {links} sequential relationships")

        logger.info("✅ Neo4j storage complete")

    def verify_migration(self):
        """Verify that migration completed successfully."""
        logger.info("\n🔍 Verifying migration...")

        # PostgreSQL verification
        cursor = self.pg_conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM document_sections")
        pg_sections = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM section_embeddings")
        pg_embeddings = cursor.fetchone()[0]

        logger.info(f"  PostgreSQL:")
        logger.info(f"    • document_sections: {pg_sections} rows")
        logger.info(f"    • section_embeddings: {pg_embeddings} rows")

        # Section statistics
        cursor.execute("""
            SELECT parent_document_type, COUNT(*) as count, AVG(word_count) as avg_words
            FROM document_sections
            GROUP BY parent_document_type
        """)
        for row in cursor.fetchall():
            logger.info(f"    • {row[0]}: {row[1]} sections, avg {int(row[2])} words")

        # Neo4j verification
        with self.neo4j_driver.session() as session:
            result = session.run("MATCH (s:Section) RETURN count(s) AS total")
            neo4j_sections = result.single()['total']

            result = session.run("MATCH ()-[:HAS_SECTION]->() RETURN count(*) AS total")
            has_section_rels = result.single()['total']

            result = session.run("MATCH ()-[:PRECEDES]->() RETURN count(*) AS total")
            precedes_rels = result.single()['total']

        logger.info(f"  Neo4j:")
        logger.info(f"    • Section nodes: {neo4j_sections}")
        logger.info(f"    • HAS_SECTION relationships: {has_section_rels}")
        logger.info(f"    • PRECEDES relationships: {precedes_rels}")

        # Consistency check
        if pg_sections != neo4j_sections:
            logger.warning(f"⚠️  Mismatch: PostgreSQL has {pg_sections} sections, Neo4j has {neo4j_sections}")
        else:
            logger.info("✅ Section counts match across databases")

    def rollback(self):
        """Rollback migration (delete all sections)."""
        logger.warning("\n⚠️  Rolling back migration...")

        if self.dry_run:
            logger.info("[DRY RUN] Would delete all sections")
            return

        try:
            # Delete from PostgreSQL
            cursor = self.pg_conn.cursor()
            cursor.execute("DELETE FROM section_embeddings")
            cursor.execute("DELETE FROM document_sections")
            self.pg_conn.commit()
            logger.info("✅ PostgreSQL sections deleted")

            # Delete from Neo4j
            with self.neo4j_driver.session() as session:
                session.run("MATCH (s:Section) DETACH DELETE s")
            logger.info("✅ Neo4j sections deleted")

        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            raise

    def close_connections(self):
        """Close database connections."""
        if self.pg_conn:
            self.pg_conn.close()
        if self.neo4j_driver:
            self.neo4j_driver.close()
        logger.info("\n📡 Database connections closed")

    def run(self, rollback_first: bool = False):
        """
        Run the migration.

        Args:
            rollback_first: If True, delete existing sections before migrating
        """
        try:
            # Connect
            self.connect_databases()

            # Verify schemas
            if not self.verify_schemas():
                logger.error("❌ Schema verification failed. Exiting.")
                return False

            # Rollback if requested
            if rollback_first:
                self.rollback()

            # Initialize chunker
            self.initialize_chunker()

            # Fetch documents
            decisions, policies = self.fetch_documents()
            all_documents = decisions + policies

            if not all_documents:
                logger.warning("⚠️  No documents found to migrate")
                return False

            # Chunk documents
            sections = self.chunk_documents(all_documents)

            if not sections:
                logger.error("❌ No sections created. Exiting.")
                return False

            # Store in databases
            self.store_sections_postgresql(sections)
            self.store_sections_neo4j(sections)

            # Verify
            self.verify_migration()

            logger.info("\n" + "=" * 70)
            logger.info("✅ Migration completed successfully!")
            logger.info("=" * 70)

            return True

        except Exception as e:
            logger.error(f"\n❌ Migration failed: {e}")
            logger.error(traceback.format_exc())
            logger.error("\nConsider running with --rollback to clean up partial migration")
            return False

        finally:
            self.close_connections()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Migrate documents to semantic sections')
    parser.add_argument('--dry-run', action='store_true', help='Preview migration without writing')
    parser.add_argument('--rollback', action='store_true', help='Delete existing sections before migrating')
    parser.add_argument('--rollback-only', action='store_true', help='Only rollback, don\'t migrate')

    args = parser.parse_args()

    migration = SectionMigration(dry_run=args.dry_run)

    if args.rollback_only:
        migration.connect_databases()
        migration.rollback()
        migration.close_connections()
        return

    success = migration.run(rollback_first=args.rollback)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
