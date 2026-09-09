#!/usr/bin/env python3
"""
Load FIRSTWEEK Data into Neo4j (Docker or Local)
==========================================

Loads all FIRSTWEEK entities, executive profile, decisions, and policies into Neo4j.

Usage:
    python load_neo4j_data.py --docker    # For Docker mode
    python load_neo4j_data.py --local     # For Local mode
    python load_neo4j_data.py --confirm   # Skip confirmation prompt
"""

raise SystemExit("Bundled persona seeding was retired. Use the FirstWeek runbook in docs/firstweek/ instead; no database changes were made.")

import sys
import os
import io
import json
import argparse
from pathlib import Path
from neo4j import GraphDatabase
import psycopg2

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Neo4j config - uses environment variables for Docker container
def get_neo4j_config():
    return {
        'uri': os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        'user': os.getenv('NEO4J_USER', 'neo4j'),
        'password': os.getenv('NEO4J_PASSWORD', '12341234')
    }

# PostgreSQL configs (for loading policies)
def get_docker_pg_config():
    return {
        'dbname': os.getenv('POSTGRES_DB', 'ai_officer'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'postgres123'),
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', '5433'))
    }

LOCAL_PG_CONFIG = {
    'dbname': 'ai_officer_dev',
    'user': 'postgres',
    'password': '1234',
    'host': 'localhost',
    'port': 5432
}


class FIRSTWEEKNeo4jLoader:
    """Load FIRSTWEEK data into Neo4j"""

    def __init__(self, uri, user, password, pg_config=None):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.pg_config = pg_config
        print(f"[OK] Connected to Neo4j: {uri}")

    def close(self):
        self.driver.close()

    def clear_database(self):
        """Clear all existing data from Neo4j"""
        print("\n[0] Clearing existing Neo4j data...")
        with self.driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            count_before = result.single()['count']
            print(f"  Nodes before: {count_before}")

            result = session.run("MATCH (n) DETACH DELETE n")
            summary = result.consume()
            print(f"  Deleted {summary.counters.nodes_deleted} nodes")
            print(f"  Deleted {summary.counters.relationships_deleted} relationships")

    def create_constraints(self):
        """Create unique constraints and indexes"""
        print("\n[1] Creating constraints and indexes...")

        constraints = [
            "CREATE CONSTRAINT executive_id IF NOT EXISTS FOR (e:Executive) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (pr:Product) REQUIRE pr.id IS UNIQUE",
            "CREATE CONSTRAINT department_id IF NOT EXISTS FOR (d:Department) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT policy_id IF NOT EXISTS FOR (p:Policy) REQUIRE p.id IS UNIQUE",
        ]

        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    print(f"  [OK] Constraint created")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        pass
                    else:
                        print(f"  [WARN] {e}")

    def load_executive(self, profile_path):
        """Load sample's executive profile"""
        print("\n[2] Loading executive profile...")

        with open(profile_path, 'r', encoding='utf-8') as f:
            profile = json.load(f)

        background = profile.get('background', {})
        if isinstance(background, dict):
            background_str = json.dumps(background, ensure_ascii=False)
        else:
            background_str = str(background) if background else ''

        with self.driver.session() as session:
            session.run("""
                CREATE (e:Executive {
                    id: $id,
                    name: $name,
                    title: $title,
                    department: $department,
                    email: $email,
                    formality_scale: $formality_scale,
                    directness_scale: $directness_scale,
                    warmth_scale: $warmth_scale,
                    technical_depth: $technical_depth,
                    decision_speed: $decision_speed,
                    risk_tolerance: $risk_tolerance,
                    background: $background,
                    years_at_company: $years_at_company,
                    years_in_role: $years_in_role
                })
            """, {
                'id': profile['id'],
                'name': profile['name'],
                'title': profile['title'],
                'department': profile['department'],
                'email': profile['email'],
                'formality_scale': profile['communication_style']['formality_scale'],
                'directness_scale': profile['communication_style']['directness_scale'],
                'warmth_scale': profile['communication_style']['warmth_scale'],
                'technical_depth': profile['communication_style'].get('technical_depth', 'high'),
                'decision_speed': profile['communication_style'].get('decision_speed', 'fast'),
                'risk_tolerance': profile['communication_style'].get('risk_tolerance', 'moderate'),
                'background': background_str,
                'years_at_company': profile.get('years_at_company', 1),
                'years_in_role': profile.get('years_in_role', 1)
            })
            print(f"  [OK] Executive: {profile['name']}")

        return profile

    def load_decisions(self, decisions, executive_id):
        """Load decision cases"""
        print("\n[3] Loading decision cases...")

        with self.driver.session() as session:
            for i, decision in enumerate(decisions):
                decision_id = decision.get('case_id', f"DC_{executive_id}_{i+1:03d}")
                session.run("""
                    CREATE (d:Decision {
                        id: $id,
                        executive_id: $executive_id,
                        title: $title,
                        category: $category,
                        situation: $situation,
                        decision_made: $decision_made,
                        rationale: $rationale,
                        outcome: $outcome,
                        lessons_learned: $lessons_learned,
                        confidence: $confidence
                    })
                """, {
                    'id': decision_id,
                    'executive_id': executive_id,
                    'title': decision.get('title', decision.get('situation', '')[:50]),
                    'category': decision.get('category', 'general'),
                    'situation': decision.get('situation', ''),
                    'decision_made': decision.get('decision_made', ''),
                    'rationale': decision.get('rationale', ''),
                    'outcome': decision.get('outcome', ''),
                    'lessons_learned': decision.get('lessons_learned', ''),
                    'confidence': float(decision.get('confidence', 0.8))
                })
                print(f"  [OK] Decision: {decision.get('category', 'general')}")

    def load_companies(self, companies_path):
        """Load companies from FIRSTWEEK entities"""
        print("\n[4] Loading companies...")

        with open(companies_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        companies = data.get('companies', [])

        with self.driver.session() as session:
            for company in companies:
                session.run("""
                    CREATE (c:Company {
                        id: $id,
                        name: $name,
                        name_local: $name_local,
                        type: $type,
                        industry: $industry,
                        size: $size,
                        region: $region
                    })
                """, {
                    'id': company['id'],
                    'name': company['name'],
                    'name_local': company.get('name_local', company['name']),
                    'type': company.get('type', 'external'),
                    'industry': company.get('industry', ''),
                    'size': company.get('size', ''),
                    'region': company.get('region', 'Japan')
                })
                print(f"  [OK] Company: {company['name']}")

        return len(companies)

    def load_people(self, people_path):
        """Load people from FIRSTWEEK entities"""
        print("\n[5] Loading people...")

        with open(people_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        people = data.get('people', [])

        with self.driver.session() as session:
            for person in people:
                session.run("""
                    CREATE (p:Person {
                        id: $id,
                        name: $name,
                        name_local: $name_local,
                        company_id: $company_id,
                        role: $role,
                        title: $title,
                        type: $type,
                        email: $email
                    })
                """, {
                    'id': person['id'],
                    'name': person['name'],
                    'name_local': person.get('name_local', person['name']),
                    'company_id': person.get('company', ''),
                    'role': person.get('role', ''),
                    'title': person.get('title', person.get('role', '')),
                    'type': person.get('type', 'employee'),
                    'email': person.get('email', '')
                })
                print(f"  [OK] Person: {person['name']}")

        return len(people)

    def load_products(self, products_path):
        """Load products/services from FIRSTWEEK entities"""
        print("\n[6] Loading products...")

        with open(products_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        products = data.get('products', [])

        with self.driver.session() as session:
            for product in products:
                session.run("""
                    CREATE (pr:Product {
                        id: $id,
                        name: $name,
                        name_local: $name_local,
                        type: $type,
                        category: $category,
                        description: $description,
                        status: $status
                    })
                """, {
                    'id': product['id'],
                    'name': product['name'],
                    'name_local': product.get('name_local', product['name']),
                    'type': product.get('type', 'service'),
                    'category': product.get('category', 'general'),
                    'description': product.get('description', ''),
                    'status': product.get('status', 'active')
                })
                print(f"  [OK] Product: {product['name']}")

        return len(products)

    def load_departments(self, departments_path):
        """Load departments from FIRSTWEEK entities"""
        print("\n[7] Loading departments...")

        with open(departments_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        departments = data.get('departments', [])

        with self.driver.session() as session:
            for dept in departments:
                session.run("""
                    CREATE (d:Department {
                        id: $id,
                        name: $name,
                        name_local: $name_local,
                        type: $type,
                        head_count: $head_count,
                        description: $description
                    })
                """, {
                    'id': dept['id'],
                    'name': dept['name'],
                    'name_local': dept.get('name_local', dept['name']),
                    'type': dept.get('type', 'department'),
                    'head_count': dept.get('head_count', 0),
                    'description': dept.get('description', '')
                })
                print(f"  [OK] Department: {dept['name']}")

        return len(departments)

    def load_policies(self, policies_dir):
        """Load policy nodes from PostgreSQL data"""
        print("\n[8] Loading policies...")

        if not self.pg_config:
            print("  [SKIP] No PostgreSQL config, skipping policies")
            return 0

        pg_conn = psycopg2.connect(**self.pg_config)
        pg_cur = pg_conn.cursor()

        pg_cur.execute("SELECT id, name, category FROM policy_documents")
        policies = pg_cur.fetchall()

        with self.driver.session() as session:
            for policy in policies:
                session.run("""
                    CREATE (p:Policy {
                        id: $id,
                        name: $name,
                        category: $category
                    })
                """, {
                    'id': policy[0],
                    'name': policy[1],
                    'category': policy[2]
                })
                print(f"  [OK] Policy: {policy[1]}")

        pg_cur.close()
        pg_conn.close()
        return len(policies)

    def create_relationships(self):
        """Create relationships between nodes"""
        print("\n[9] Creating relationships...")

        with self.driver.session() as session:
            # Executive WORKS_FOR Company (FIRSTWEEK)
            session.run("""
                MATCH (e:Executive {id: 'sample_profile'})
                MATCH (c:Company {id: 'ai_talent_force'})
                CREATE (e)-[:WORKS_FOR]->(c)
            """)
            print("  [OK] Executive WORKS_FOR Company")

            # Executive MADE Decision
            result = session.run("""
                MATCH (e:Executive {id: 'sample_profile'})
                MATCH (d:Decision {executive_id: 'sample_profile'})
                CREATE (e)-[:MADE]->(d)
                RETURN count(*) as count
            """)
            count = result.single()['count']
            print(f"  [OK] Executive MADE Decision ({count} relationships)")

            # Person WORKS_FOR Company
            result = session.run("""
                MATCH (p:Person)
                MATCH (c:Company {id: p.company_id})
                CREATE (p)-[:WORKS_FOR]->(c)
                RETURN count(*) as count
            """)
            count = result.single()['count']
            print(f"  [OK] Person WORKS_FOR Company ({count} relationships)")

            # Company OFFERS Product
            result = session.run("""
                MATCH (c:Company {id: 'ai_talent_force'})
                MATCH (pr:Product)
                CREATE (c)-[:OFFERS]->(pr)
                RETURN count(*) as count
            """)
            count = result.single()['count']
            print(f"  [OK] Company OFFERS Product ({count} relationships)")

            # Company HAS Department
            result = session.run("""
                MATCH (c:Company {id: 'ai_talent_force'})
                MATCH (d:Department)
                CREATE (c)-[:HAS]->(d)
                RETURN count(*) as count
            """)
            count = result.single()['count']
            print(f"  [OK] Company HAS Department ({count} relationships)")

            # Company GOVERNED_BY Policy
            result = session.run("""
                MATCH (c:Company {id: 'ai_talent_force'})
                MATCH (p:Policy)
                CREATE (c)-[:GOVERNED_BY]->(p)
                RETURN count(*) as count
            """)
            count = result.single()['count']
            print(f"  [OK] Company GOVERNED_BY Policy ({count} relationships)")

    def verify_data(self):
        """Verify loaded data"""
        print("\n[10] Verifying data...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] AS Label, count(n) AS Count
                ORDER BY Count DESC
            """)

            print("\n  Node counts:")
            for record in result:
                print(f"    {record['Label']}: {record['Count']}")

            result = session.run("MATCH ()-[r]->() RETURN count(r) AS total")
            total_rels = result.single()['total']
            print(f"\n  Total relationships: {total_rels}")


def main():
    parser = argparse.ArgumentParser(description='Load FIRSTWEEK data into Neo4j')
    parser.add_argument('--docker', action='store_true', help='Use Docker database settings')
    parser.add_argument('--local', action='store_true', help='Use Local database settings')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    # Determine which PostgreSQL config to use for policies
    if args.docker:
        PG_CONFIG = get_docker_pg_config()
        NEO4J_CFG = get_neo4j_config()
        mode = "DOCKER"
    elif args.local:
        PG_CONFIG = LOCAL_PG_CONFIG
        NEO4J_CFG = {'uri': 'bolt://localhost:7687', 'user': 'neo4j', 'password': '12341234'}
        mode = "LOCAL"
    else:
        print("ERROR: Please specify --docker or --local")
        print("  --docker  Use Docker PostgreSQL (port 5433)")
        print("  --local   Use Local PostgreSQL (port 5432)")
        return 1

    print("\n" + "=" * 60)
    print(f"  FIRSTWEEK NEO4J LOADER - {mode} Mode")
    print("=" * 60)
    print(f"\n  Neo4j: {NEO4J_CFG['uri']}")
    print(f"  PostgreSQL: port {PG_CONFIG['port']} (for policies)")

    # Data paths
    BASE_DIR = Path(__file__).parent.parent
    sample_PROFILE = BASE_DIR / 'test_data' / 'executive_profiles' / 'sample_profile.json'
    ENTITIES_DIR = BASE_DIR / 'test_data' / 'entities'

    if not sample_PROFILE.exists():
        print(f"[ERROR] sample profile not found: {sample_PROFILE}")
        return 1

    if not args.confirm:
        print("\n[WARNING] This will CLEAR all existing Neo4j data!")
        response = input("Continue? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Aborted.")
            return 0

    loader = FIRSTWEEKNeo4jLoader(
        NEO4J_CFG['uri'],
        NEO4J_CFG['user'],
        NEO4J_CFG['password'],
        PG_CONFIG
    )

    try:
        # 0. Clear existing data
        loader.clear_database()

        # 1. Create constraints
        loader.create_constraints()

        # 2. Load executive profile
        profile = loader.load_executive(sample_PROFILE)

        # 3. Load decisions
        decisions = profile.get('decision_cases', [])
        loader.load_decisions(decisions, profile['id'])

        # 4. Load companies
        loader.load_companies(ENTITIES_DIR / 'companies_firstweek.json')

        # 5. Load people
        loader.load_people(ENTITIES_DIR / 'people_firstweek.json')

        # 6. Load products
        loader.load_products(ENTITIES_DIR / 'products_firstweek.json')

        # 7. Load departments
        loader.load_departments(ENTITIES_DIR / 'departments_firstweek.json')

        # 8. Load policies (from PostgreSQL)
        loader.load_policies(BASE_DIR / 'test_data' / 'policies')

        # 9. Create relationships
        loader.create_relationships()

        # 10. Verify
        loader.verify_data()

        print("\n" + "=" * 60)
        print(f"[SUCCESS] FIRSTWEEK data loaded to Neo4j ({mode} mode)!")
        print("=" * 60)
        print("\nNext step:")
        print(f"  Generate embeddings: python generate_embeddings.py --{mode.lower()}")

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
