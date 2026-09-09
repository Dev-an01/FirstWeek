#!/usr/bin/env python3
"""
Load FIRSTWEEK Data into PostgreSQL (Docker or Local)
================================================

This script loads sample executive data into PostgreSQL:
- Executive profile
- Decision cases (10)
- FIRSTWEEK policies (3)
- Document sections

Usage:
    python load_postgres_data.py --docker    # For Docker (port 5433)
    python load_postgres_data.py --local     # For Local (port 5432)
    python load_postgres_data.py --confirm   # Skip confirmation prompt
"""

raise SystemExit("Bundled persona seeding was retired. Use the FirstWeek runbook in docs/firstweek/ instead; no database changes were made.")

import sys
import os
import io
from pathlib import Path
import json
import psycopg2
from datetime import datetime
import re
import argparse

# Fix Windows console encoding for Japanese characters
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Database configurations
# Docker config uses environment variables (for running inside container)
# or defaults for running from host machine
def get_docker_config():
    return {
        'dbname': os.getenv('POSTGRES_DB', 'ai_officer'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'postgres123'),
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', '5433'))
    }

LOCAL_CONFIG = {
    'dbname': 'ai_officer_dev',
    'user': 'postgres',
    'password': '1234',
    'host': 'localhost',
    'port': 5432
}


class FIRSTWEEKDataLoader:
    """Load FIRSTWEEK-only data into PostgreSQL"""

    def __init__(self, pg_config):
        """Initialize database connection"""
        self.pg_conn = psycopg2.connect(**pg_config)
        self.pg_cur = self.pg_conn.cursor()
        print(f"[OK] Connected to PostgreSQL: {pg_config['dbname']} (port {pg_config['port']})")

    def close(self):
        """Close database connection"""
        self.pg_cur.close()
        self.pg_conn.close()

    def clear_all_data(self):
        """Clear sample seed data, preserving onboarding data"""
        print("\n" + "="*60)
        print("[CLEAR] CLEARING sample SEED DATA (preserving onboarding)")
        print("="*60)

        # Safe to fully clear (regenerable — no onboarding data)
        regenerable = [
            'section_embeddings',
            'embeddings',
            'communication_examples',
            'episodic_memory',
            'conversation_sessions',
            'conversations',
            'executive_memories',
        ]

        for table in regenerable:
            try:
                self.pg_cur.execute(f"DELETE FROM {table}")
                count = self.pg_cur.rowcount
                if count > 0:
                    print(f"  [OK] Cleared {table}: {count} rows")
            except Exception as e:
                print(f"  [WARN] Could not clear {table}: {e}")
                self.pg_conn.rollback()

        # Only clear sample-specific data (preserve onboarding executives' data)
        try:
            self.pg_cur.execute("DELETE FROM document_sections WHERE executive_id = 'sample_profile'")
            count = self.pg_cur.rowcount
            if count > 0:
                print(f"  [OK] Cleared document_sections (sample): {count} rows")

            self.pg_cur.execute("DELETE FROM decision_cases WHERE executive_id = 'sample_profile'")
            count = self.pg_cur.rowcount
            if count > 0:
                print(f"  [OK] Cleared decision_cases (sample): {count} rows")

            self.pg_cur.execute("DELETE FROM policy_documents WHERE owner_executive = 'sample_profile' OR owner_executive IS NULL")
            count = self.pg_cur.rowcount
            if count > 0:
                print(f"  [OK] Cleared policy_documents (sample/unowned): {count} rows")
        except Exception as e:
            print(f"  [WARN] Could not clear sample data: {e}")
            self.pg_conn.rollback()

        # Do NOT delete from executive_profiles — sample handled by upsert in load_sample_profile()

        self.pg_conn.commit()
        print("\n[OK] sample seed data cleared (onboarding data preserved)!")

    def load_sample_profile(self, profile_path):
        """Load sample's executive profile"""
        print("\n" + "="*60)
        print("[EXEC] LOADING sample PROFILE")
        print("="*60)

        with open(profile_path, 'r', encoding='utf-8') as f:
            profile = json.load(f)

        print(f"  Loading: {profile['name']} ({profile['id']})")

        # Ensure company exists if profile has company_id
        company_id = profile.get('company_id')
        if company_id:
            company_name = profile.get('company', profile.get('background', {}).get('company_info', {}).get('name', company_id))
            self.pg_cur.execute("""
                INSERT INTO companies (id, name)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (company_id, company_name))
            print(f"  [OK] Ensured company exists: {company_id} ({company_name})")

        self.pg_cur.execute("""
            INSERT INTO executive_profiles
            (id, name, title, department, email, company_id, profile_data,
             formality_scale, directness_scale, warmth_scale)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                company_id = EXCLUDED.company_id,
                profile_data = EXCLUDED.profile_data,
                updated_at = NOW()
        """, (
            profile['id'],
            profile['name'],
            profile['title'],
            profile['department'],
            profile['email'],
            profile.get('company_id'),
            json.dumps(profile),
            profile['communication_style']['formality_scale'],
            profile['communication_style']['directness_scale'],
            profile['communication_style']['warmth_scale']
        ))

        print(f"  [OK] Executive profile inserted")

        # Load decision cases
        decisions = profile.get('decision_cases', [])
        print(f"\n  Loading {len(decisions)} decision cases...")

        for idx, decision in enumerate(decisions):
            decision_id = decision.get('case_id') or f"DC_sample_{idx+1:03d}"

            decision_date = decision.get('date', '2024-01-01')
            if isinstance(decision_date, str):
                if len(decision_date) == 4:
                    decision_date = f"{decision_date}-01-01"
                try:
                    decision_date = datetime.strptime(decision_date, '%Y-%m-%d').date()
                except ValueError:
                    decision_date = datetime.strptime('2024-01-01', '%Y-%m-%d').date()

            self.pg_cur.execute("""
                INSERT INTO decision_cases
                (id, executive_id, title, date, category, situation,
                 decision_made, rationale, outcome, lessons_learned,
                 confidence, precedent, full_content)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    situation = EXCLUDED.situation,
                    decision_made = EXCLUDED.decision_made,
                    updated_at = NOW()
            """, (
                decision_id,
                profile['id'],
                decision.get('title', decision.get('situation', 'Decision')[:100]),
                decision_date,
                decision.get('category', 'General'),
                decision.get('situation', ''),
                decision.get('decision_made', ''),
                decision.get('rationale', ''),
                decision.get('outcome', ''),
                decision.get('lessons_learned', ''),
                float(decision.get('confidence', 0.8)),
                decision.get('is_precedent', decision.get('precedent', True)),
                json.dumps(decision)
            ))
            print(f"    [OK] {decision_id}: {decision.get('category', 'General')}")

        self.pg_conn.commit()
        print(f"\n[OK] Loaded sample profile + {len(decisions)} decisions")
        return len(decisions)

    def load_firstweek_policies(self, policies_dir):
        """Load FIRSTWEEK-specific policy documents"""
        print("\n" + "="*60)
        print("[POLICY] LOADING FIRSTWEEK POLICIES")
        print("="*60)

        firstweek_policy_files = list(Path(policies_dir).glob('*_firstweek.md'))

        if not firstweek_policy_files:
            print("  [WARN] No FIRSTWEEK policy files found")
            return 0

        count = 0
        for filepath in firstweek_policy_files:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            policy_name = None
            policy_id = None

            for line in lines[:20]:
                if line.startswith('# ') and not policy_name:
                    policy_name = line[2:].strip()
                if 'POLICY-' in line.upper():
                    match = re.search(r'POLICY-[\w-]+', line.upper())
                    if match:
                        policy_id = match.group()

            if not policy_id:
                policy_id = f"POLICY-FIRSTWEEK-{filepath.stem.upper()}"
            if not policy_name:
                policy_name = filepath.stem.replace('_', ' ').title()

            self.pg_cur.execute("""
                INSERT INTO policy_documents
                (id, name, version, category, content_markdown, file_path, confidentiality)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    content_markdown = EXCLUDED.content_markdown,
                    updated_at = NOW()
            """, (
                policy_id,
                policy_name,
                '1.0',
                'FIRSTWEEK Internal',
                content,
                str(filepath),
                'Internal'
            ))
            count += 1
            print(f"  [OK] {policy_name}")

        self.pg_conn.commit()
        print(f"\n[OK] Loaded {count} FIRSTWEEK policies")
        return count

    def load_firstweek_documents(self, documents_dir):
        """Load FIRSTWEEK documents into document_sections for RAG"""
        print("\n" + "="*60)
        print("[DOC] LOADING FIRSTWEEK DOCUMENTS")
        print("="*60)

        firstweek_docs = []

        presentations_dir = Path(documents_dir) / 'presentations'
        if presentations_dir.exists():
            firstweek_docs.extend(presentations_dir.glob('*firstweek*.md'))
            firstweek_docs.extend(presentations_dir.glob('*ai_officer*.md'))

        meetings_dir = Path(documents_dir) / 'meeting_notes'
        if meetings_dir.exists():
            firstweek_docs.extend(meetings_dir.glob('*ai_officers*.md'))

        if not firstweek_docs:
            print("  [WARN] No FIRSTWEEK documents found")
            return 0

        section_count = 0
        for filepath in firstweek_docs:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            doc_title = filepath.stem
            for line in lines[:5]:
                if line.startswith('# '):
                    doc_title = line[2:].strip()
                    break

            sections = self._chunk_document(content, filepath.stem)

            for idx, section in enumerate(sections):
                section_id = f"{filepath.stem}_SEC_{idx+1:03d}"

                if 'meeting_notes' in str(filepath):
                    doc_type = 'meeting_notes'
                    doc_category = 'Internal Meeting'
                elif 'presentations' in str(filepath):
                    doc_type = 'presentation'
                    doc_category = 'Product Documentation'
                else:
                    doc_type = 'document'
                    doc_category = 'General'

                self.pg_cur.execute("""
                    INSERT INTO document_sections
                    (id, parent_document_id, parent_document_type, section_number,
                     section_title, content, word_count, section_type,
                     executive_id, document_category)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        updated_at = NOW()
                """, (
                    section_id,
                    filepath.stem,
                    doc_type,
                    idx + 1,
                    section['title'],
                    section['content'],
                    len(section['content'].split()),
                    'body',
                    'sample_profile',
                    doc_category
                ))
                section_count += 1

            print(f"  [OK] {doc_title}: {len(sections)} sections")

        self.pg_conn.commit()
        print(f"\n[OK] Loaded {section_count} document sections from {len(firstweek_docs)} documents")
        return section_count

    def _chunk_document(self, content, doc_id):
        """Chunk document by ## headers"""
        sections = []
        current_section = {'title': 'Introduction', 'content': ''}

        for line in content.split('\n'):
            if line.startswith('## '):
                if current_section['content'].strip():
                    sections.append(current_section)
                current_section = {
                    'title': line[3:].strip(),
                    'content': ''
                }
            else:
                current_section['content'] += line + '\n'

        if current_section['content'].strip():
            sections.append(current_section)

        if not sections:
            sections = [{'title': 'Full Document', 'content': content}]

        return sections

    def verify_data(self):
        """Verify FIRSTWEEK data was loaded"""
        print("\n" + "="*60)
        print("[VERIFY] VERIFYING FIRSTWEEK DATA")
        print("="*60)

        self.pg_cur.execute("SELECT COUNT(*) FROM executive_profiles")
        exec_count = self.pg_cur.fetchone()[0]

        self.pg_cur.execute("SELECT COUNT(*) FROM decision_cases")
        decision_count = self.pg_cur.fetchone()[0]

        self.pg_cur.execute("SELECT COUNT(*) FROM policy_documents")
        policy_count = self.pg_cur.fetchone()[0]

        self.pg_cur.execute("SELECT COUNT(*) FROM document_sections")
        section_count = self.pg_cur.fetchone()[0]

        print(f"\n  Executives:        {exec_count}")
        print(f"  Decision Cases:    {decision_count}")
        print(f"  Policy Documents:  {policy_count}")
        print(f"  Document Sections: {section_count}")

        self.pg_cur.execute("SELECT id, name, title FROM executive_profiles")
        for row in self.pg_cur.fetchall():
            print(f"\n  Executive: {row[1]}")
            print(f"    ID: {row[0]}")
            print(f"    Title: {row[2]}")

        return exec_count > 0


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Load FIRSTWEEK data into PostgreSQL')
    parser.add_argument('--docker', action='store_true', help='Use Docker database (port 5433)')
    parser.add_argument('--local', action='store_true', help='Use Local database (port 5432)')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    # Determine which config to use
    if args.docker:
        PG_CONFIG = get_docker_config()
        mode = "DOCKER"
    elif args.local:
        PG_CONFIG = LOCAL_CONFIG
        mode = "LOCAL"
    else:
        print("ERROR: Please specify --docker or --local")
        print("  --docker  Use Docker database (port 5433, ai_officer)")
        print("  --local   Use Local database (port 5432, ai_officer_dev)")
        return 1

    print("\n" + "="*70)
    print(f"  FIRSTWEEK DATA LOADER - {mode} Database")
    print("="*70)
    print(f"\n  Database: {PG_CONFIG['dbname']}")
    print(f"  Port:     {PG_CONFIG['port']}")
    print("\nThis will:")
    print("  1. Clear sample seed data (preserving onboarding data)")
    print("  2. Load FIRSTWEEK data (sample + policies/docs)")
    print()

    # Data paths
    BASE_DIR = Path(__file__).parent.parent
    sample_PROFILE = BASE_DIR / 'test_data' / 'executive_profiles' / 'sample_profile.json'
    POLICIES_DIR = BASE_DIR / 'test_data' / 'policies'
    DOCUMENTS_DIR = BASE_DIR / 'test_data' / 'documents'

    if not sample_PROFILE.exists():
        print(f"[ERROR] sample profile not found: {sample_PROFILE}")
        return 1

    print(f"[FILE] sample profile: {sample_PROFILE.name}")
    print(f"[FILE] Policies dir: {POLICIES_DIR}")
    print(f"[FILE] Documents dir: {DOCUMENTS_DIR}")

    if not args.confirm:
        print("\n[WARNING] This will clear sample seed data (onboarding data preserved)!")
        response = input("Continue? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Aborted.")
            return 0

    loader = FIRSTWEEKDataLoader(PG_CONFIG)

    try:
        loader.clear_all_data()
        loader.load_sample_profile(sample_PROFILE)
        loader.load_firstweek_policies(POLICIES_DIR)
        loader.load_firstweek_documents(DOCUMENTS_DIR)
        loader.verify_data()

        print("\n" + "="*70)
        print(f"[SUCCESS] FIRSTWEEK DATA LOADED TO {mode} DATABASE!")
        print("="*70)
        print("\nNext steps:")
        print(f"  1. Load Neo4j: python load_neo4j_data.py --{mode.lower()}")
        print(f"  2. Generate embeddings: python generate_embeddings.py --{mode.lower()}")

        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        loader.close()


if __name__ == "__main__":
    sys.exit(main())
