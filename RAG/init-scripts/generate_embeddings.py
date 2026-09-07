#!/usr/bin/env python3
"""
Generate Embeddings for FIRSTWEEK Data (Docker or Local)
===================================================

Generates embeddings for:
- Executive profiles
- Decision cases
- Policy documents
- Slack messages

Usage:
    python generate_embeddings.py --docker    # For Docker database
    python generate_embeddings.py --local     # For Local database
    python generate_embeddings.py --skip-slack  # Skip Slack message ingestion
"""

import sys
import os
import io
import argparse
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Database configurations
# Docker config reads from environment variables (for running inside container)
def get_docker_config():
    return {
        'POSTGRES_DB': os.getenv('POSTGRES_DB', 'ai_officer'),
        'POSTGRES_USER': os.getenv('POSTGRES_USER', 'postgres'),
        'POSTGRES_PASSWORD': os.getenv('POSTGRES_PASSWORD', 'postgres123'),
        'POSTGRES_HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'POSTGRES_PORT': os.getenv('POSTGRES_PORT', '5433'),
        'NEO4J_URI': os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        'NEO4J_USER': os.getenv('NEO4J_USER', 'neo4j'),
        'NEO4J_PASSWORD': os.getenv('NEO4J_PASSWORD', '12341234')
    }

LOCAL_CONFIG = {
    'POSTGRES_DB': 'ai_officer_dev',
    'POSTGRES_USER': 'postgres',
    'POSTGRES_PASSWORD': '1234',
    'POSTGRES_HOST': 'localhost',
    'POSTGRES_PORT': '5432',
    'NEO4J_URI': 'bolt://localhost:7687',
    'NEO4J_USER': 'neo4j',
    'NEO4J_PASSWORD': '12341234'
}


def set_environment(config):
    """Set environment variables for database connections"""
    for key, value in config.items():
        os.environ[key] = value


def main():
    parser = argparse.ArgumentParser(description='Generate embeddings for FIRSTWEEK data')
    parser.add_argument('--docker', action='store_true', help='Use Docker database settings')
    parser.add_argument('--local', action='store_true', help='Use Local database settings')
    parser.add_argument('--skip-slack', action='store_true', help='Skip Slack message ingestion')
    parser.add_argument('--sections-only', action='store_true',
                        help='Only generate missing section embeddings (fast startup check)')
    args = parser.parse_args()

    # Determine which config to use
    if args.docker:
        config = get_docker_config()
        mode = "DOCKER"
    elif args.local:
        config = LOCAL_CONFIG
        mode = "LOCAL"
    else:
        print("ERROR: Please specify --docker or --local")
        print("  --docker  Use Docker database (port 5433)")
        print("  --local   Use Local database (port 5432)")
        return 1

    print("\n" + "="*70)
    print(f"  EMBEDDING GENERATION - {mode} Database")
    print("="*70)
    print(f"\n  Database: {config['POSTGRES_DB']}")
    print(f"  Port:     {config['POSTGRES_PORT']}")
    print()

    # Set environment variables BEFORE importing embedding modules
    set_environment(config)

    # Now import and run embedding generation
    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent))

    # Handle --sections-only mode
    if args.sections_only:
        try:
            print("\n[SECTIONS-ONLY] Generating missing section embeddings...")
            from embedding_generation.main import generate_missing_section_embeddings
            count = generate_missing_section_embeddings()
            print(f"[SECTIONS-ONLY] Done — {count} section embeddings generated.")
            return 0
        except Exception as e:
            print(f"\n[ERROR] Section embedding generation failed: {e}")
            import traceback
            traceback.print_exc()
            return 1

    try:
        # Step 1: Run main embedding generation
        print("\n" + "="*60)
        print("[STEP 1] Generating embeddings for profiles, decisions, policies...")
        print("="*60)

        from embedding_generation.main import main as embedding_main
        result = embedding_main()

        if result != 0:
            print(f"\n[WARN] Embedding generation returned code {result}")

        # Step 2: Ingest Slack messages (unless skipped)
        if not args.skip_slack:
            print("\n" + "="*60)
            print("[STEP 2] Ingesting Slack messages...")
            print("="*60)

            from embedding_generation.ingest_slack_messages import ingest_slack_messages

            slack_file = Path(__file__).parent.parent / 'docs' / 'sample_data' / 'slack messages.md'
            if slack_file.exists():
                stats = ingest_slack_messages(str(slack_file))
                print(f"\n  Messages: {stats['total_messages']}")
                print(f"  Chunks: {stats['chunks_created']}")
                print(f"  Stored: {stats['embeddings_stored']}")
            else:
                print(f"  [WARN] Slack file not found: {slack_file}")
        else:
            print("\n[SKIP] Skipping Slack message ingestion (--skip-slack)")

        # Step 3: Verify embeddings
        print("\n" + "="*60)
        print("[STEP 3] Verifying embeddings...")
        print("="*60)

        import psycopg2
        conn = psycopg2.connect(
            host=config['POSTGRES_HOST'],
            port=int(config['POSTGRES_PORT']),
            database=config['POSTGRES_DB'],
            user=config['POSTGRES_USER'],
            password=config['POSTGRES_PASSWORD']
        )
        cur = conn.cursor()

        cur.execute("""
            SELECT source_type, COUNT(*)
            FROM embeddings
            GROUP BY source_type
            ORDER BY count DESC
        """)

        print("\n  Embeddings by type:")
        total = 0
        for row in cur.fetchall():
            print(f"    {row[0]}: {row[1]}")
            total += row[1]

        print(f"\n  Total embeddings: {total}")

        conn.close()

        print("\n" + "="*70)
        print(f"[SUCCESS] Embeddings generated for {mode} database!")
        print("="*70)
        print(f"\n  Total embeddings: {total}")

        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
