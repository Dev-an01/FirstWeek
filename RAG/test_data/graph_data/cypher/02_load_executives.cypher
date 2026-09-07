// ============================================
// 02_load_executives.cypher
// ============================================
// Purpose: Load executive profiles into Neo4j
// Prerequisite: 01_create_constraints.cypher
// ============================================

// Load executives from CSV
LOAD CSV WITH HEADERS FROM 'file:///executives.csv' AS row
CREATE (e:Executive {
  id: row.id,
  name: row.name,
  title: row.title,
  department: row.department,
  email: row.email,
  formality_scale: toInteger(row.formality_scale),
  directness_scale: toInteger(row.directness_scale),
  warmth_scale: toInteger(row.warmth_scale),
  technical_depth: row.technical_depth,
  decision_speed: row.decision_speed,
  risk_tolerance: row.risk_tolerance,
  background: row.background,
  years_at_company: toInteger(row.years_at_company),
  years_in_role: toInteger(row.years_in_role)
})
RETURN e.name, e.title;

// Expected output:
// - Akiko Tanaka, CEO & Co-Founder
// - Raj Patel, CFO
// - Yuki Nakamura, CTO
// - Sarah Kim, CMO

// ============================================
// Verification
// ============================================

// Count executives loaded
MATCH (e:Executive)
RETURN count(e) AS TotalExecutives;
// Expected: 4

// List all executives
MATCH (e:Executive)
RETURN e.name, e.title, e.email, e.department
ORDER BY e.name;

// ============================================
// Script Complete
// ============================================
// Next: Run 03_load_entities.cypher