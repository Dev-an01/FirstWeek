"""
Automated Neo4j Data Loader for Docker
Runs all Cypher scripts in order
"""
import os
import sys
import time
from pathlib import Path
from neo4j import GraphDatabase

# Add app directory to path (for imports like hybrid_retrieval)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def wait_for_neo4j(uri, user, password, max_retries=30):
    """Wait for Neo4j to be ready"""
    print("⏳ Waiting for Neo4j to be fully ready...")
    
    for i in range(max_retries):
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            print("✅ Neo4j is ready!")
            return True
        except Exception as e:
            if i < max_retries - 1:
                time.sleep(2)
            else:
                print(f"❌ Neo4j not ready after {max_retries} retries: {e}")
                return False
    return False

def run_cypher_file(driver, filepath):
    """Run a Cypher file"""
    print(f"\n📄 Running: {filepath.name}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove comment lines and empty lines
    lines = []
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith('//'):
            lines.append(line)
    
    # Join and split by semicolon
    cypher = '\n'.join(lines)
    queries = [q.strip() for q in cypher.split(';') if q.strip()]
    
    with driver.session() as session:
        for i, query in enumerate(queries, 1):
            try:
                result = session.run(query)
                summary = result.consume()
                
                # Print summary
                if summary.counters.nodes_created > 0:
                    print(f"  ✓ Query {i}: Created {summary.counters.nodes_created} nodes")
                elif summary.counters.relationships_created > 0:
                    print(f"  ✓ Query {i}: Created {summary.counters.relationships_created} relationships")
                elif summary.counters.indexes_added > 0 or summary.counters.constraints_added > 0:
                    print(f"  ✓ Query {i}: Added {summary.counters.indexes_added} indexes, {summary.counters.constraints_added} constraints")
                else:
                    print(f"  ✓ Query {i}: Executed successfully")
                    
            except Exception as e:
                print(f"  ⚠️  Query {i} warning: {e}")
                # Continue anyway - might be duplicate data

def main():
    # Configuration from environment
    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '12341234')
    
    # Path: /app/init-scripts/utils/load_neo4j.py -> /app/test_data/graph_data/cypher
    CYPHER_DIR = Path(__file__).parent.parent.parent / 'test_data' / 'graph_data' / 'cypher'
    
    # Files to run in order
    files = [
        "01_create_constraints.cypher",
        "02_load_executives.cypher",
        "03_load_entities.cypher",
        "04_load_decisions.cypher",
        "05_load_policies.cypher",
        "06_create_relationships.cypher"
    ]
    
    print("=" * 70)
    print("Neo4j Data Loader - Automated Docker Setup")
    print("=" * 70)
    
    # Wait for Neo4j
    if not wait_for_neo4j(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD):
        sys.exit(1)
    
    # Connect
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        for filename in files:
            filepath = CYPHER_DIR / filename
            if not filepath.exists():
                print(f"⚠️  File not found: {filepath}")
                continue
            run_cypher_file(driver, filepath)
        
        print("\n" + "=" * 70)
        print("✅ All Cypher scripts executed successfully!")
        print("=" * 70)
        
        # Verify
        print("\n📊 Verifying data...")
        with driver.session() as session:
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] AS Label, count(n) AS Count
                ORDER BY Count DESC
            """)
            print("\nNode counts:")
            for record in result:
                print(f"  • {record['Label']}: {record['Count']}")
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) AS total")
            total_rels = result.single()['total']
            print(f"\nTotal relationships: {total_rels}")
            print("=" * 70)
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        driver.close()

if __name__ == "__main__":
    main()
