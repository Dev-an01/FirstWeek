// ============================================
// 04_load_decisions.cypher
// ============================================
// Purpose: Load executive decision cases
// Prerequisite: 02_load_executives.cypher, 03_load_entities.cypher
// ============================================

LOAD CSV WITH HEADERS FROM 'file:///decisions.csv' AS row
CREATE (d:Decision {
  id: row.id,
  title: row.title,
  date: date(row.date),
  category: row.category,
  executive_id: row.executive_id,
  executive_name: row.executive_name,
  outcome: row.outcome,
  confidence: toFloat(row.confidence),
  financial_impact: CASE WHEN row.financial_impact IS NOT NULL THEN toFloat(row.financial_impact) ELSE null END,
  decision_made: row.decision_made,
  rationale_summary: row.rationale_summary,
  lessons_learned: row.lessons_learned,
  precedent: row.precedent = 'true'
})
RETURN count(d) AS DecisionsLoaded;

// Expected: 20 decisions

// ============================================
// Verification
// ============================================

// Count decisions
MATCH (d:Decision)
RETURN count(d) AS TotalDecisions;
// Expected: 20

// List decisions by executive
MATCH (d:Decision)
RETURN d.executive_name, count(d) AS DecisionCount
ORDER BY DecisionCount DESC;

// Expected:
// Akiko Tanaka: 5
// Raj Patel: 5
// Yuki Nakamura: 5
// Sarah Kim: 5

// List all decision titles
MATCH (d:Decision)
RETURN d.id, d.title, d.date, d.outcome
ORDER BY d.date DESC;

// ============================================
// Script Complete
// ============================================
// Next: Run 05_load_policies.cypher