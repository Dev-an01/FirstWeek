// ============================================
// 08_load_sections_template.cypher
// ============================================
// Purpose: Template for loading semantic chunking sections
// This file shows the pattern - actual sections loaded by migration script
// ============================================

// ============================================
// Example: Create Section Nodes
// ============================================

// Decision Section Example
// Pattern: (Decision)-[:HAS_SECTION]->(Section)
MERGE (d:Decision {id: "DC_AKIKO_001"})
MERGE (s:Section {
    id: "DC_AKIKO_001_section_0",
    parent_document_id: "DC_AKIKO_001",
    parent_document_type: "decision",
    section_number: 0,
    section_title: "Background and Context",
    word_count: 156,
    section_type: "introduction",
    boundary_type: "explicit_heading",
    boundary_confidence: 0.95
})
MERGE (d)-[:HAS_SECTION]->(s);

// Policy Section Example
// Pattern: (Policy)-[:HAS_SECTION]->(Section)
MERGE (p:Policy {id: "POLICY-FIN-001"})
MERGE (s:Section {
    id: "POLICY-FIN-001_section_0",
    parent_document_id: "POLICY-FIN-001",
    parent_document_type: "policy",
    section_number: 0,
    section_title: "Policy Overview",
    word_count: 203,
    section_type: "introduction",
    boundary_type: "markdown",
    boundary_confidence: 0.95
})
MERGE (p)-[:HAS_SECTION]->(s);

// ============================================
// Example: Create Sequential Relationships
// ============================================

// Pattern: (Section)-[:PRECEDES]->(Section)
// Pattern: (Section)-[:FOLLOWS]->(Section)

// Connect sections in sequence
MATCH (s1:Section {id: "DC_AKIKO_001_section_0"})
MATCH (s2:Section {id: "DC_AKIKO_001_section_1"})
MERGE (s1)-[:PRECEDES]->(s2)
MERGE (s2)-[:FOLLOWS]->(s1);

// ============================================
// Bulk Load Pattern (for migration script)
// ============================================

// UNWIND pattern for batch loading sections
// This is what the migration script will use:

/*
UNWIND $sections AS section
MERGE (s:Section {id: section.id})
SET s += section.properties
WITH s, section
MATCH (parent) WHERE parent.id = section.parent_document_id
  AND (parent:Decision OR parent:Policy)
MERGE (parent)-[:HAS_SECTION]->(s)
RETURN count(s) AS sections_created;
*/

// Create sequential relationships after sections loaded:
/*
MATCH (s1:Section), (s2:Section)
WHERE s1.parent_document_id = s2.parent_document_id
  AND s1.section_number + 1 = s2.section_number
MERGE (s1)-[:PRECEDES]->(s2)
MERGE (s2)-[:FOLLOWS]->(s1)
RETURN count(*) AS sequential_links_created;
*/

// ============================================
// Verification Queries
// ============================================

// Count sections by parent document type
// MATCH (s:Section)
// RETURN s.parent_document_type AS DocumentType, count(s) AS SectionCount
// ORDER BY SectionCount DESC;

// Count sections per document
// MATCH (d)-[:HAS_SECTION]->(s:Section)
// RETURN labels(d)[0] AS ParentType, d.id AS DocumentID, count(s) AS Sections
// ORDER BY Sections DESC;

// Verify sequential relationships
// MATCH (s1:Section)-[:PRECEDES]->(s2:Section)
// WHERE s1.parent_document_id = s2.parent_document_id
// RETURN s1.parent_document_id, s1.section_number, s2.section_number
// LIMIT 10;

// Find sections by type
// MATCH (s:Section {section_type: "methodology"})
// RETURN s.parent_document_id, s.section_title, s.word_count
// LIMIT 10;

// ============================================
// Graph Traversal Examples
// ============================================

// Find all sections of a decision
// MATCH (d:Decision {id: "DC_AKIKO_001"})-[:HAS_SECTION]->(s:Section)
// RETURN s.section_number, s.section_title, s.section_type, s.word_count
// ORDER BY s.section_number;

// Navigate sections sequentially
// MATCH path = (s1:Section {id: "DC_AKIKO_001_section_0"})-[:PRECEDES*]->(s2:Section)
// RETURN path;

// Find decisions with methodology sections
// MATCH (d:Decision)-[:HAS_SECTION]->(s:Section {section_type: "methodology"})
// RETURN d.id, d.title, s.section_title
// LIMIT 10;

// Find long sections (potential for further chunking)
// MATCH (s:Section)
// WHERE s.word_count > 500
// RETURN s.id, s.section_title, s.word_count
// ORDER BY s.word_count DESC;

// ============================================
// Section-Enhanced Graph Queries
// ============================================

// Find sections mentioning specific entities (after entity linking)
// MATCH (s:Section)-[:MENTIONS]->(e)
// WHERE e:Company OR e:Person OR e:Product
// RETURN s.id, s.section_title, labels(e)[0] AS EntityType, e.name
// LIMIT 20;

// Multi-hop: Find related sections via shared entities
// MATCH (s1:Section)-[:MENTIONS]->(e)<-[:MENTIONS]-(s2:Section)
// WHERE s1.id <> s2.id
// RETURN s1.section_title, e.name, s2.section_title
// LIMIT 10;

// Find precedent sections (sections from precedent decisions)
// MATCH (d1:Decision)-[:PRECEDENT_FOR]->(d2:Decision)
// MATCH (d1)-[:HAS_SECTION]->(s1:Section)
// MATCH (d2)-[:HAS_SECTION]->(s2:Section)
// WHERE s1.section_type = s2.section_type
// RETURN d1.title, s1.section_title, d2.title, s2.section_title
// LIMIT 10;

// ============================================
// Script Complete
// ============================================
// This is a template. Actual sections will be loaded by:
// - Python migration script (scripts/migrate_to_sections.py)
// - Which reads from PostgreSQL document_sections table
// - And bulk loads to Neo4j using the patterns above
