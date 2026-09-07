// ============================================
// 01_create_constraints.cypher
// ============================================
// Purpose: Create uniqueness constraints and indexes
// Run this FIRST before loading any data
// ============================================

// Executive constraints
CREATE CONSTRAINT executive_id IF NOT EXISTS
FOR (e:Executive) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT executive_email IF NOT EXISTS
FOR (e:Executive) REQUIRE e.email IS UNIQUE;

// Company constraints
CREATE CONSTRAINT company_id IF NOT EXISTS
FOR (c:Company) REQUIRE c.id IS UNIQUE;

// Person constraints
CREATE CONSTRAINT person_id IF NOT EXISTS
FOR (p:Person) REQUIRE p.id IS UNIQUE;

// Decision constraints
CREATE CONSTRAINT decision_id IF NOT EXISTS
FOR (d:Decision) REQUIRE d.id IS UNIQUE;

// Policy constraints
CREATE CONSTRAINT policy_id IF NOT EXISTS
FOR (pol:Policy) REQUIRE pol.id IS UNIQUE;

// Product constraints
CREATE CONSTRAINT product_id IF NOT EXISTS
FOR (prod:Product) REQUIRE prod.id IS UNIQUE;

// Project constraints
CREATE CONSTRAINT project_id IF NOT EXISTS
FOR (proj:Project) REQUIRE proj.id IS UNIQUE;

// Department constraints
CREATE CONSTRAINT department_id IF NOT EXISTS
FOR (dept:Department) REQUIRE dept.id IS UNIQUE;

// ============================================
// Indexes for frequent lookups
// ============================================

// Index on names for search
CREATE INDEX executive_name IF NOT EXISTS
FOR (e:Executive) ON (e.name);

CREATE INDEX company_name IF NOT EXISTS
FOR (c:Company) ON (c.name);

CREATE INDEX person_name IF NOT EXISTS
FOR (p:Person) ON (p.name);

CREATE INDEX decision_title IF NOT EXISTS
FOR (d:Decision) ON (d.title);

CREATE INDEX policy_name IF NOT EXISTS
FOR (pol:Policy) ON (pol.name);

// Index on dates for temporal queries
CREATE INDEX decision_date IF NOT EXISTS
FOR (d:Decision) ON (d.date);

CREATE INDEX policy_effective_date IF NOT EXISTS
FOR (pol:Policy) ON (pol.effective_date);

// Index on categories for filtering
CREATE INDEX decision_category IF NOT EXISTS
FOR (d:Decision) ON (d.category);

CREATE INDEX company_type IF NOT EXISTS
FOR (c:Company) ON (c.type);

CREATE INDEX company_industry IF NOT EXISTS
FOR (c:Company) ON (c.industry);

// ============================================
// Verification
// ============================================

// Show all constraints
SHOW CONSTRAINTS;

// Show all indexes
SHOW INDEXES;

// Expected output:
// - 9 uniqueness constraints
// - 10 indexes

// ============================================
// Script Complete
// ============================================
// Next: Run 02_load_executives.cypher