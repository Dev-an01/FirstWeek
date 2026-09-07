// ============================================
// 07_create_section_schema.cypher
// ============================================
// Purpose: Create schema for semantic chunking sections
// Run this after loading base data (01-06)
//
// Benefits:
// - Enables section-level graph traversal
// - Maintains document context via relationships
// - Supports graph-enhanced section retrieval
// - Enables sequential navigation (PRECEDES/FOLLOWS)
// ============================================

// ============================================
// Section Constraints
// ============================================

// Section uniqueness constraint
CREATE CONSTRAINT section_id IF NOT EXISTS
FOR (s:Section) REQUIRE s.id IS UNIQUE;

// ============================================
// Section Indexes
// ============================================

// Index on parent document ID for quick lookups
CREATE INDEX section_parent_doc IF NOT EXISTS
FOR (s:Section) ON (s.parent_document_id);

// Index on section type for filtering
CREATE INDEX section_type IF NOT EXISTS
FOR (s:Section) ON (s.section_type);

// Index on section title for search
CREATE INDEX section_title IF NOT EXISTS
FOR (s:Section) ON (s.section_title);

// Index on section number for ordering
CREATE INDEX section_number IF NOT EXISTS
FOR (s:Section) ON (s.section_number);

// Index on boundary type for analytics
CREATE INDEX section_boundary_type IF NOT EXISTS
FOR (s:Section) ON (s.boundary_type);

// ============================================
// Verification
// ============================================

// Show section-related constraints
SHOW CONSTRAINTS WHERE entityType = "NODE" AND labelsOrTypes CONTAINS "Section";

// Show section-related indexes
SHOW INDEXES WHERE labelsOrTypes CONTAINS "Section";

// ============================================
// Expected Output
// ============================================
// - 1 uniqueness constraint (section_id)
// - 5 indexes (parent_doc, type, title, number, boundary_type)

// ============================================
// Script Complete
// ============================================
// Next: Run 08_load_sections.cypher to populate sections
