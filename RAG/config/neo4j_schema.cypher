// ============================================================================
// AI Officer Neo4j Graph Schema
// Multi-tenant knowledge graph for companies and executives
// ============================================================================

// ============================================================================
// 1. Constraints (Unique IDs)
// ============================================================================
CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT executive_id IF NOT EXISTS FOR (e:Executive) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT policy_id IF NOT EXISTS FOR (p:Policy) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT domain_id IF NOT EXISTS FOR (d:Domain) REQUIRE d.id IS UNIQUE;

// ============================================================================
// 2. Indexes for Fast Lookups
// ============================================================================

// Company indexes
CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name);
CREATE INDEX company_industry IF NOT EXISTS FOR (c:Company) ON (c.industry);

// Executive indexes
CREATE INDEX executive_name IF NOT EXISTS FOR (e:Executive) ON (e.name);
CREATE INDEX executive_company IF NOT EXISTS FOR (e:Executive) ON (e.company_id);
CREATE INDEX executive_hierarchy IF NOT EXISTS FOR (e:Executive) ON (e.hierarchy_level);
CREATE INDEX executive_title IF NOT EXISTS FOR (e:Executive) ON (e.title);

// Decision indexes
CREATE INDEX decision_company IF NOT EXISTS FOR (d:Decision) ON (d.company_id);
CREATE INDEX decision_executive IF NOT EXISTS FOR (d:Decision) ON (d.executive_id);
CREATE INDEX decision_category IF NOT EXISTS FOR (d:Decision) ON (d.category);

// Policy indexes
CREATE INDEX policy_company IF NOT EXISTS FOR (p:Policy) ON (p.company_id);
CREATE INDEX policy_category IF NOT EXISTS FOR (p:Policy) ON (p.category);

// ============================================================================
// 3. Full-text search indexes (for entity matching)
// ============================================================================
CREATE FULLTEXT INDEX company_fulltext IF NOT EXISTS FOR (c:Company) ON EACH [c.name, c.industry, c.description];
CREATE FULLTEXT INDEX executive_fulltext IF NOT EXISTS FOR (e:Executive) ON EACH [e.name, e.name_english, e.title];
CREATE FULLTEXT INDEX decision_fulltext IF NOT EXISTS FOR (d:Decision) ON EACH [d.title, d.situation, d.decision, d.rationale];
CREATE FULLTEXT INDEX policy_fulltext IF NOT EXISTS FOR (p:Policy) ON EACH [p.name, p.category];

// ============================================================================
// Note: Relationships are created dynamically by Neo4jDeployer
//
// Relationship Types:
// - (:Company)-[:HAS_EXECUTIVE]->(:Executive)
// - (:Company)-[:HAS_POLICY]->(:Policy)
// - (:Executive)-[:MADE_DECISION]->(:Decision)
// - (:Executive)-[:HAS_EXPERTISE]->(:Domain)
// - (:Executive)-[:OWNS_POLICY]->(:Policy)
// ============================================================================
