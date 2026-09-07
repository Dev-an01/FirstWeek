"""Quick verification of Neo4j embeddings"""
from neo4j import GraphDatabase

driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', '12341234'))
session = driver.session()

print("\n=== NEO4J EMBEDDING VERIFICATION ===\n")

# Count decisions
result = session.run('MATCH (d:Decision) WHERE d.embedding IS NOT NULL RETURN count(d) AS count')
dec_count = result.single()['count']
print(f"✓ Decisions with embeddings: {dec_count}/20")

# Count policies
result = session.run('MATCH (p:Policy) WHERE p.embedding IS NOT NULL RETURN count(p) AS count')
pol_count = result.single()['count']
print(f"✓ Policies with embeddings: {pol_count}/12")

# Sample decision embeddings
print("\nSample Decision embeddings:")
result = session.run('MATCH (d:Decision) WHERE d.embedding IS NOT NULL RETURN d.id, size(d.embedding) AS dims, d.embedding_model LIMIT 3')
for record in result:
    print(f"  {record['d.id']}: {record['dims']} dimensions ({record['d.embedding_model']})")

# Sample policy embeddings
print("\nSample Policy embeddings:")
result = session.run('MATCH (p:Policy) WHERE p.embedding IS NOT NULL RETURN p.id, size(p.embedding) AS dims, p.embedding_model LIMIT 3')
for record in result:
    print(f"  {record['p.id']}: {record['dims']} dimensions ({record['p.embedding_model']})")

print(f"\n✅ Total nodes with embeddings: {dec_count + pol_count}/32\n")

session.close()
driver.close()
