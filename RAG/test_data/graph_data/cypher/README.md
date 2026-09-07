# Graph Data - Neo4j Ingestion Files

This directory contains scripts and data files to populate the Neo4j knowledge graph for the AI Officer system.

## Overview

The knowledge graph stores:
- **Executives** (4 nodes): Akiko, Raj, Yuki, Sarah
- **Companies** (42 nodes): Customers, competitors, partners
- **People** (38 nodes): Employees, customer contacts, board members
- **Decisions** (20 nodes): Executive decision cases
- **Policies** (12 nodes): Company policies
- **Projects** (12 nodes): Internal projects and initiatives
- **Products** (3 nodes): WorkFlow Pro, TeamSync, TalentHub
- **Departments** (8 nodes): Engineering, Sales, Marketing, etc.

**Total Nodes**: ~139 nodes  
**Total Relationships**: ~400+ relationships

## Directory Structure
graph_data/ ├── cypher/ # Cypher scripts (run in order) │ ├── 01_create_constraints.cypher │ ├── 02_load_executives.cypher │ ├── 03_load_entities.cypher │ ├── 04_load_decisions.cypher │ ├── 05_load_policies.cypher │ └── 06_create_relationships.cypher └── neo4j_import/ # CSV files for bulk import ├── executives.csv ├── companies.csv ├── people.csv ├── decisions.csv └── policies.csv


## Setup Instructions

### Prerequisites

1. **Neo4j installed** (version 4.4+ or 5.x)
2. **Neo4j Browser** or `cypher-shell` CLI
3. **CSV files** placed in Neo4j import directory

### Step 1: Copy CSV Files

```bash
# Find your Neo4j import directory
# Default locations:
# - Mac: /Users/<username>/Library/Application Support/Neo4j Desktop/Application/relate-data/dbmss/<dbms-id>/import/
# - Linux: /var/lib/neo4j/import/
# - Windows: C:\Users\<username>\.Neo4jDesktop\relate-data\dbmss\<dbms-id>\import\

# Copy CSV files
cp test_data/graph_data/neo4j_import/*.csv <neo4j-import-directory>/
Step 2: Run Cypher Scripts in Order
Option A: Neo4j Browser (Recommended)

Open Neo4j Browser: http://localhost:7474
Connect to your database
Copy/paste each Cypher script in order (01 → 06)
Execute each script
Option B: cypher-shell CLI

bash
# Connect to Neo4j
cypher-shell -u neo4j -p <your-password>

# Run scripts in order
cat test_data/graph_data/cypher/01_create_constraints.cypher | cypher-shell -u neo4j -p <password>
cat test_data/graph_data/cypher/02_load_executives.cypher | cypher-shell -u neo4j -p <password>
cat test_data/graph_data/cypher/03_load_entities.cypher | cypher-shell -u neo4j -p <password>
cat test_data/graph_data/cypher/04_load_decisions.cypher | cypher-shell -u neo4j -p <password>
cat test_data/graph_data/cypher/05_load_policies.cypher | cypher-shell -u neo4j -p <password>
cat test_data/graph_data/cypher/06_create_relationships.cypher | cypher-shell -u neo4j -p <password>
Option C: Python Script (Automated)

bash
# Use the provided setup script
python scripts/setup_neo4j.py
Step 3: Verify Data Loaded
Cypher
// Count nodes by label
MATCH (n) RETURN labels(n) AS Label, count(*) AS Count ORDER BY Count DESC;

// Expected output:
// Label          Count
// ────────────────────
// Person         38
// Company        42
// Decision       20
// Policy         12
// Project        12
// Executive      4
// Product        3
// Department     8

// Count relationships
MATCH ()-[r]->() RETURN type(r) AS RelationType, count(*) AS Count ORDER BY Count DESC;

// Sample the graph
MATCH (e:Executive)-[r]->(d:Decision) RETURN e.name, type(r), d.title LIMIT 10;
Graph Schema
Node Labels
Executive

Properties: id, name, title, department, email, communication_style
Example: (e:Executive {name: "Akiko Tanaka", title: "CEO"})
Company

Properties: id, name, type, industry, size, region
Example: (c:Company {name: "MegaCorp Japan", type: "customer"})
Person

Properties: id, name, title, company, email
Example: (p:Person {name: "Takeshi Yamamoto", title: "CIO"})
Decision

Properties: id, title, date, category, outcome, confidence, executive_id
Example: (d:Decision {id: "DC_AKIKO_001", title: "MegaCorp Renewal"})
Policy

Properties: id, name, version, effective_date, owner, category
Example: (p:Policy {id: "POLICY-FIN-001", name: "Discount Policy v2.1"})
Product

Properties: id, name, description, launch_date, pricing_tier
Example: (prod:Product {name: "WorkFlow Pro"})
Project

Properties: id, name, status, start_date, owner
Example: (proj:Project {name: "AI Search Implementation"})
Department

Properties: id, name, headcount, budget
Example: (dept:Department {name: "Engineering"})
Relationship Types
Executive Relationships:

(Executive)-[:MADE_DECISION]->(Decision)
(Executive)-[:CREATED_POLICY]->(Policy)
(Executive)-[:LEADS]->(Department)
(Executive)-[:MANAGES]->(Person)
(Executive)-[:OWNS_PROJECT]->(Project)
Decision Relationships:

(Decision)-[:INVOLVES_COMPANY]->(Company)
(Decision)-[:REFERENCES_POLICY]->(Policy)
(Decision)-[:AFFECTS_PROJECT]->(Project)
(Decision)-[:PRECEDENT_FOR]->(Decision)
(Decision)-[:INFLUENCED_BY]->(Decision)
Company Relationships:

(Company)-[:HAS_CONTACT]->(Person)
(Company)-[:COMPETITOR_OF]->(Company)
(Company)-[:PARTNER_WITH]->(Company)
(Company)-[:CUSTOMER_OF]->(Product)
Person Relationships:

(Person)-[:WORKS_FOR]->(Company)
(Person)-[:REPORTS_TO]->(Executive)
(Person)-[:MEMBER_OF]->(Department)
Policy Relationships:

(Policy)-[:OWNED_BY]->(Executive)
(Policy)-[:APPLIES_TO]->(Department)
(Policy)-[:SUPERSEDES]->(Policy) (version history)
Sample Queries
Find all decisions by an executive
Cypher
MATCH (e:Executive {name: "Akiko Tanaka"})-[:MADE_DECISION]->(d:Decision)
RETURN d.title, d.date, d.outcome
ORDER BY d.date DESC;
Find decisions referencing a specific policy
Cypher
MATCH (d:Decision)-[:REFERENCES_POLICY]->(p:Policy {id: "POLICY-FIN-001"})
RETURN d.title, d.date, d.executive_id;
Find decision precedent chain
Cypher
MATCH path = (d1:Decision)-[:PRECEDENT_FOR*]->(d2:Decision)
WHERE d1.id = "DC_AKIKO_001"
RETURN path;
Find all customer contacts
Cypher
MATCH (c:Company {type: "customer"})-[:HAS_CONTACT]->(p:Person)
RETURN c.name AS Company, p.name AS Contact, p.title
ORDER BY c.name;
Find executive's sphere of influence
Cypher
MATCH (e:Executive {name: "Raj Patel"})-[r]->(n)
RETURN e.name, type(r) AS Relationship, labels(n) AS ConnectedTo, count(*) AS Count
ORDER BY Count DESC;
Find decisions involving specific company
Cypher
MATCH (d:Decision)-[:INVOLVES_COMPANY]->(c:Company {name: "MegaCorp Japan"})
MATCH (e:Executive)-[:MADE_DECISION]->(d)
RETURN d.title, e.name, d.date, d.outcome;
Troubleshooting
CSV Import Errors
Error: Couldn't load the external resource
Solution: Ensure CSV files are in Neo4j's import directory

Error: Constraint already exists
Solution: Run 01_create_constraints.cypher only once, or drop constraints first:

Cypher
DROP CONSTRAINT executive_id IF EXISTS;
DROP CONSTRAINT company_id IF EXISTS;
// ... etc
Clear All Data
Cypher
// WARNING: This deletes everything!
MATCH (n) DETACH DELETE n;
Check Import Progress
Cypher
// After each load script
MATCH (n) RETURN labels(n), count(*);
Performance Tips
Create constraints first (script 01) - Enables indexing
Use LOAD CSV with PERIODIC COMMIT for large datasets
Create relationships last (script 06) - Faster bulk import
Use APOC plugin for advanced operations (optional)
Next Steps
After loading the graph:

Explore in Neo4j Browser (http://localhost:7474)
Run sample queries (see above)
Integrate with AI Officer backend (Python/FastAPI)
Build graph-based retrieval for RAG system