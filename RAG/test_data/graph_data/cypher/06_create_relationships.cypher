// ============================================
// 06_create_relationships.cypher
// ============================================
// Purpose: Create all relationships between nodes
// Prerequisite: All previous scripts (01-05)
// This is the FINAL script - creates the knowledge graph
// ============================================

// ============================================
// PART 1: Executive → Decision Relationships
// ============================================

// Connect executives to their decisions
MATCH (e:Executive), (d:Decision)
WHERE e.id = d.executive_id
CREATE (e)-[:MADE_DECISION {
  date: d.date,
  confidence: d.confidence
}]->(d)
RETURN count(*) AS ExecutiveDecisionLinks;

// Expected: 20 relationships (all decisions)

// ============================================
// PART 2: Executive → Department Relationships
// ============================================

// Akiko leads Executive
MATCH (e:Executive {id: 'exec_001_test'}), (dept:Department {id: 'dept_executive'})
CREATE (e)-[:LEADS]->(dept);

// Raj leads Finance
MATCH (e:Executive {id: 'exec_002_test'}), (dept:Department {id: 'dept_finance'})
CREATE (e)-[:LEADS]->(dept);

// Yuki leads Engineering
MATCH (e:Executive {id: 'exec_003_test'}), (dept:Department {id: 'dept_engineering'})
CREATE (e)-[:LEADS]->(dept);

// Sarah leads Marketing
MATCH (e:Executive {id: 'exec_004_test'}), (dept:Department {id: 'dept_marketing'})
CREATE (e)-[:LEADS]->(dept);

// ============================================
// PART 3: Executive → Project Relationships
// ============================================

// Akiko owns Career Development
MATCH (e:Executive {id: 'exec_001_test'}), (proj:Project {id: 'project_career_dev'})
CREATE (e)-[:OWNS_PROJECT]->(proj);

// Raj owns AWS Optimization, Working Capital, Pricing Strategy
MATCH (e:Executive {id: 'exec_002_test'}), (proj:Project {id: 'project_aws_optimization'})
CREATE (e)-[:OWNS_PROJECT]->(proj);

MATCH (e:Executive {id: 'exec_002_test'}), (proj:Project {id: 'project_working_capital'})
CREATE (e)-[:OWNS_PROJECT]->(proj);

MATCH (e:Executive {id: 'exec_002_test'}), (proj:Project {id: 'project_pricing_strategy'})
CREATE (e)-[:OWNS_PROJECT]->(proj);

// Yuki owns AI Search, Tech Debt, Intercom, SOC 2, Mobile
MATCH (e:Executive {id: 'exec_003_test'}), (proj:Project {id: 'project_ai_search'})
CREATE (e)-[:OWNS_PROJECT]->(proj);

MATCH (e:Executive {id: 'exec_003_test'}), (proj:Project {id: 'project_tech_debt'})
CREATE (e)-[:OWNS_PROJECT]->(proj);

MATCH (e:Executive {id: 'exec_003_test'}), (proj:Project {id: 'project_intercom'})
CREATE (e)-[:OWNS_PROJECT]->(proj);

MATCH (e:Executive {id: 'exec_003_test'}), (proj:Project {id: 'project_soc2'})
CREATE (e)-[:OWNS_PROJECT]->(proj);

MATCH (e:Executive {id: 'exec_003_test'}), (proj:Project {id: 'project_mobile_rebuild'})
CREATE (e)-[:OWNS_PROJECT]->(proj);

// Sarah owns Mid-Market Brand
MATCH (e:Executive {id: 'exec_004_test'}), (proj:Project {id: 'project_mid_market_brand'})
CREATE (e)-[:OWNS_PROJECT]->(proj);

// ============================================
// PART 4: Decision → Company Relationships
// ============================================

// DC_AKIKO_001 involves MegaCorp
MATCH (d:Decision {id: 'DC_AKIKO_001'}), (c:Company {id: 'company_megacorp'})
CREATE (d)-[:INVOLVES_COMPANY {
  role: 'customer',
  context: 'Strategic account renewal negotiation'
}]->(c);

// DC_AKIKO_001 involves WorkMax (competitor)
MATCH (d:Decision {id: 'DC_AKIKO_001'}), (c:Company {id: 'company_workmax'})
CREATE (d)-[:INVOLVES_COMPANY {
  role: 'competitor',
  context: 'Competitive threat in renewal'
}]->(c);

// DC_AKIKO_002 involves AWS (vendor)
MATCH (d:Decision {id: 'DC_AKIKO_002'}), (c:Company {id: 'company_aws'})
CREATE (d)-[:INVOLVES_COMPANY {
  role: 'vendor',
  context: 'Cloud infrastructure for AI features'
}]->(c);

// DC_SARAH_002 involves multiple mid-market customers (example: TechFlow Solutions)
MATCH (d:Decision {id: 'DC_SARAH_002'}), (c:Company {id: 'company_techflow'})
CREATE (d)-[:INVOLVES_COMPANY {
  role: 'target_segment',
  context: 'Mid-market brand transformation'
}]->(c);

// DC_YUKI_002 involves Intercom
MATCH (d:Decision {id: 'DC_YUKI_002'}), (c:Company {id: 'company_intercom'})
CREATE (d)-[:INVOLVES_COMPANY {
  role: 'vendor_selected',
  context: 'Customer support platform replacement'
}]->(c);

// DC_YUKI_002 involves Zendesk (replaced)
MATCH (d:Decision {id: 'DC_YUKI_002'}), (c:Company {id: 'company_zendesk'})
CREATE (d)-[:INVOLVES_COMPANY {
  role: 'vendor_replaced',
  context: 'Replaced by Intercom'
}]->(c);

// ============================================
// PART 5: Decision → Policy Relationships
// ============================================

// DC_AKIKO_001 references Discount Policy
MATCH (d:Decision {id: 'DC_AKIKO_001'}), (p:Policy {id: 'POLICY-FIN-001'})
CREATE (d)-[:REFERENCES_POLICY {
  context: 'Established precedent for strategic account discounting'
}]->(p);

// DC_RAJ_001 references Hiring Approval Policy
MATCH (d:Decision {id: 'DC_RAJ_001'}), (p:Policy {id: 'POLICY-HR-005'})
CREATE (d)-[:REFERENCES_POLICY {
  context: 'Sales team expansion approval process'
}]->(p);

// DC_RAJ_002 references Discount Policy (pricing strategy)
MATCH (d:Decision {id: 'DC_RAJ_002'}), (p:Policy {id: 'POLICY-FIN-001'})
CREATE (d)-[:REFERENCES_POLICY {
  context: 'Pricing increase impacts discount policy'
}]->(p);

// DC_RAJ_003 references Procurement Policy
MATCH (d:Decision {id: 'DC_RAJ_003'}), (p:Policy {id: 'POLICY-FIN-006'})
CREATE (d)-[:REFERENCES_POLICY {
  context: 'Vendor management and cost optimization'
}]->(p);

// DC_RAJ_005 references Sales Compensation Policy
MATCH (d:Decision {id: 'DC_RAJ_005'}), (p:Policy {id: 'POLICY-SALES-001'})
CREATE (d)-[:REFERENCES_POLICY {
  context: 'Updated sales comp to incentivize cash collection'
}]->(p);

// DC_YUKI_005 references Information Security Policy
MATCH (d:Decision {id: 'DC_YUKI_005'}), (p:Policy {id: 'POLICY-IT-001'})
CREATE (d)-[:REFERENCES_POLICY {
  context: 'Security incident led to policy updates'
}]->(p);

// DC_AKIKO_003 references Professional Development Policy
MATCH (d:Decision {id: 'DC_AKIKO_003'}), (p:Policy {id: 'POLICY-HR-003'})
CREATE (d)-[:REFERENCES_POLICY {
  context: 'Career development program launch'
}]->(p);

// DC_SARAH_003 references Sales Compensation Policy (lead quality affects comp)
MATCH (d:Decision {id: 'DC_SARAH_003'}), (p:Policy {id: 'POLICY-SALES-001'})
CREATE (d)-[:REFERENCES_POLICY {
  context: 'Marketing-sales alignment affects sales metrics'
}]->(p);

// ============================================
// PART 6: Decision → Project Relationships
// ============================================

// DC_AKIKO_002 affects AI Search project
MATCH (d:Decision {id: 'DC_AKIKO_002'}), (proj:Project {id: 'project_ai_search'})
CREATE (d)-[:AFFECTS_PROJECT {
  impact: 'Approved pilot, limited initial investment'
}]->(proj);

// DC_SARAH_002 affects Mid-Market Brand project
MATCH (d:Decision {id: 'DC_SARAH_002'}), (proj:Project {id: 'project_mid_market_brand'})
CREATE (d)-[:AFFECTS_PROJECT {
  impact: 'Initiated project with ¥25M budget'
}]->(proj);

// DC_RAJ_003 affects AWS Optimization project
MATCH (d:Decision {id: 'DC_RAJ_003'}), (proj:Project {id: 'project_aws_optimization'})
CREATE (d)-[:AFFECTS_PROJECT {
  impact: 'Phased approach, target ¥45M run-rate'
}]->(proj);

// DC_YUKI_004 affects Tech Debt project
MATCH (d:Decision {id: 'DC_YUKI_004'}), (proj:Project {id: 'project_tech_debt'})
CREATE (d)-[:AFFECTS_PROJECT {
  impact: 'Approved 6-week sprint, ¥75M opportunity cost'
}]->(proj);

// DC_AKIKO_003 affects Career Development project
MATCH (d:Decision {id: 'DC_AKIKO_003'}), (proj:Project {id: 'project_career_dev'})
CREATE (d)-[:AFFECTS_PROJECT {
  impact: 'Launched program post-VP Engineering departure'
}]->(proj);

// DC_YUKI_002 affects Intercom project
MATCH (d:Decision {id: 'DC_YUKI_002'}), (proj:Project {id: 'project_intercom'})
CREATE (d)-[:AFFECTS_PROJECT {
  impact: 'Selected Intercom over Zendesk and Freshdesk'
}]->(proj);

// DC_RAJ_001 affects Sales Expansion project
MATCH (d:Decision {id: 'DC_RAJ_001'}), (proj:Project {id: 'project_sales_expansion'})
CREATE (d)-[:AFFECTS_PROJECT {
  impact: 'Approved 6 AEs (phased), not 10 as requested'
}]->(proj);

// DC_RAJ_005 affects Working Capital project
MATCH (d:Decision {id: 'DC_RAJ_005'}), (proj:Project {id: 'project_working_capital'})
CREATE (d)-[:AFFECTS_PROJECT {
  impact: 'Initiated DSO reduction program'
}]->(proj);

// DC_RAJ_002 affects Pricing Strategy project
MATCH (d:Decision {id: 'DC_RAJ_002'}), (proj:Project {id: 'project_pricing_strategy'})
CREATE (d)-[:AFFECTS_PROJECT {
  impact: 'Implemented 10-15% price increase'
}]->(proj);

// ============================================
// PART 7: Decision Precedent Relationships
// ============================================

// DC_AKIKO_001 is precedent for future discount decisions
MATCH (d1:Decision {id: 'DC_AKIKO_001'}), (d2:Decision {id: 'DC_AKIKO_004'})
CREATE (d1)-[:PRECEDENT_FOR {
  context: 'MegaCorp discount strategy used for other strategic accounts'
}]->(d2);

// DC_RAJ_001 influenced by DC_AKIKO_003 (hiring after attrition)
MATCH (d1:Decision {id: 'DC_AKIKO_003'}), (d2:Decision {id: 'DC_RAJ_001'})
CREATE (d1)-[:INFLUENCED_BY {
  context: 'Attrition concerns led to cautious sales hiring approach'
}]->(d2);

// DC_YUKI_005 influenced future security decisions
MATCH (d1:Decision {id: 'DC_YUKI_005'}), (d2:Decision {id: 'DC_YUKI_003'})
CREATE (d1)-[:PRECEDENT_FOR {
  context: 'Security incident informed quarterly audit decision'
}]->(d2);

// ============================================
// PART 8: Company → Person Relationships
// ============================================

// MegaCorp → Takeshi Yamamoto (CIO)
MATCH (c:Company {id: 'company_megacorp'}), (p:Person {id: 'person_takeshi_yamamoto'})
CREATE (c)-[:HAS_CONTACT {
  role: 'CIO',
  primary: true
}]->(p);

// Link other people to their companies
MATCH (p:Person), (c:Company)
WHERE p.company = c.name
CREATE (p)-[:WORKS_FOR]->(c);

// ============================================
// PART 9: Company Competitive Relationships
// ============================================

// WorkMax competes with NexaTech (implied)
MATCH (c1:Company {id: 'company_workmax'}), (c2:Company {id: 'company_enterpriseflow'})
CREATE (c1)-[:COMPETITOR_OF]->(c2);

// EnterpriseFlow competes with WorkMax
CREATE (c2)-[:COMPETITOR_OF]->(c1);

// ============================================
// PART 10: Policy Ownership
// ============================================

// Discount Policy owned by CFO Raj
MATCH (p:Policy {id: 'POLICY-FIN-001'}), (e:Executive {id: 'exec_002_test'})
CREATE (p)-[:OWNED_BY]->(e);

// Travel Expense Policy owned by CFO Raj
MATCH (p:Policy {id: 'POLICY-FIN-004'}), (e:Executive {id: 'exec_002_test'})
CREATE (p)-[:OWNED_BY]->(e);

// Remote Work Policy owned by People Ops (implied CEO oversight)
MATCH (p:Policy {id: 'POLICY-HR-001'}), (e:Executive {id: 'exec_001_test'})
CREATE (p)-[:OWNED_BY]->(e);

// Information Security Policy owned by CTO Yuki
MATCH (p:Policy {id: 'POLICY-IT-001'}), (e:Executive {id: 'exec_003_test'})
CREATE (p)-[:OWNED_BY]->(e);

// Data Privacy Policy owned by CTO Yuki + Legal
MATCH (p:Policy {id: 'POLICY-IT-003'}), (e:Executive {id: 'exec_003_test'})
CREATE (p)-[:OWNED_BY]->(e);

// Procurement Policy owned by CFO Raj
MATCH (p:Policy {id: 'POLICY-FIN-006'}), (e:Executive {id: 'exec_002_test'})
CREATE (p)-[:OWNED_BY]->(e);

// Sales Compensation Policy co-owned by VP Sales + CFO
MATCH (p:Policy {id: 'POLICY-SALES-001'}), (e:Executive {id: 'exec_002_test'})
CREATE (p)-[:OWNED_BY]->(e);

// Professional Development Policy owned by CEO Akiko
MATCH (p:Policy {id: 'POLICY-HR-003'}), (e:Executive {id: 'exec_001_test'})
CREATE (p)-[:OWNED_BY]->(e);

// Time Off Policy owned by People Ops (CEO oversight)
MATCH (p:Policy {id: 'POLICY-HR-002'}), (e:Executive {id: 'exec_001_test'})
CREATE (p)-[:OWNED_BY]->(e);

// Expense Reimbursement Policy owned by CFO Raj
MATCH (p:Policy {id: 'POLICY-FIN-005'}), (e:Executive {id: 'exec_002_test'})
CREATE (p)-[:OWNED_BY]->(e);

// Code of Conduct owned by CEO Akiko
MATCH (p:Policy {id: 'POLICY-HR-004'}), (e:Executive {id: 'exec_001_test'})
CREATE (p)-[:OWNED_BY]->(e);

// Hiring Approval Policy owned by People Ops + CFO
MATCH (p:Policy {id: 'POLICY-HR-005'}), (e:Executive {id: 'exec_002_test'})
CREATE (p)-[:OWNED_BY]->(e);

// ============================================
// FINAL VERIFICATION
// ============================================

// Count all relationships
MATCH ()-[r]->()
RETURN type(r) AS RelationshipType, count(r) AS Count
ORDER BY Count DESC;

// Count total nodes and relationships
MATCH (n)
WITH count(n) AS NodeCount
MATCH ()-[r]->()
RETURN NodeCount, count(r) AS RelationshipCount;

// Sample the graph
MATCH (e:Executive)-[r1]->(d:Decision)-[r2]->(c:Company)
RETURN e.name, type(r1), d.title, type(r2), c.name
LIMIT 10;

// ============================================
// Script Complete
// ============================================
// Knowledge graph is now fully loaded!
// Open Neo4j Browser to explore: http://localhost:7474