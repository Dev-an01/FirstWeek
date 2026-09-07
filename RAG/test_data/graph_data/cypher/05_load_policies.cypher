// ============================================
// 05_load_policies.cypher
// ============================================
// Purpose: Load company policies
// Prerequisite: 02_load_executives.cypher
// ============================================

LOAD CSV WITH HEADERS FROM 'file:///policies.csv' AS row
CREATE (p:Policy {
  id: row.id,
  name: row.name,
  version: row.version,
  effective_date: date(row.effective_date),
  owner_executive: row.owner_executive,
  category: row.category,
  confidentiality: row.confidentiality,
  file_path: row.file_path,
  last_updated: date(row.last_updated),
  review_frequency: row.review_frequency
})
RETURN count(p) AS PoliciesLoaded;

// Expected: 12 policies

// ============================================
// Verification
// ============================================

// Count policies
MATCH (p:Policy)
RETURN count(p) AS TotalPolicies;
// Expected: 12

// List all policies
MATCH (p:Policy)
RETURN p.id, p.name, p.version, p.owner_executive
ORDER BY p.id;

// Group by category
MATCH (p:Policy)
RETURN p.category, count(p) AS Count
ORDER BY Count DESC;

// ============================================
// Script Complete
// ============================================
// Next: Run 06_create_relationships.cypher