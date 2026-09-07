// ============================================
// 03_load_entities.cypher
// ============================================
// Purpose: Load companies, people, products, departments, projects
// Prerequisite: 02_load_executives.cypher
// ============================================

// ============================================
// PART 1: Load Companies
// ============================================

LOAD CSV WITH HEADERS FROM 'file:///companies.csv' AS row
CREATE (c:Company {
  id: row.id,
  name: row.name,
  type: row.type,
  industry: row.industry,
  size: row.size,
  region: row.region,
  relationship: row.relationship,
  arr: CASE WHEN row.arr IS NOT NULL THEN toFloat(row.arr) ELSE null END,
  customer_since: row.customer_since,
  description: row.description
})
RETURN count(c) AS CompaniesLoaded;

// Expected: 42 companies

// ============================================
// PART 2: Load People
// ============================================

LOAD CSV WITH HEADERS FROM 'file:///people.csv' AS row
CREATE (p:Person {
  id: row.id,
  name: row.name,
  title: row.title,
  company: row.company,
  email: row.email,
  role_type: row.role_type,
  department: row.department,
  location: row.location
})
RETURN count(p) AS PeopleLoaded;

// Expected: 38 people

// ============================================
// PART 3: Load Products
// ============================================

CREATE (prod1:Product {
  id: 'product_workflow_pro',
  name: 'WorkFlow Pro',
  description: 'Enterprise project management and collaboration platform',
  launch_date: '2020-06-15',
  pricing_tier: 'Professional, Enterprise',
  arr_contribution: 65.0,
  customer_count: 420
});

CREATE (prod2:Product {
  id: 'product_teamsync',
  name: 'TeamSync',
  description: 'Real-time team communication and messaging platform',
  launch_date: '2021-03-10',
  pricing_tier: 'Professional, Enterprise',
  arr_contribution: 23.0,
  customer_count: 380
});

CREATE (prod3:Product {
  id: 'product_talenthub',
  name: 'TalentHub',
  description: 'HR management and employee development platform',
  launch_date: '2021-11-01',
  pricing_tier: 'Professional, Enterprise',
  arr_contribution: 12.0,
  customer_count: 195
});

// Expected: 3 products

// ============================================
// PART 4: Load Departments
// ============================================

CREATE (dept1:Department {
  id: 'dept_engineering',
  name: 'Engineering',
  headcount: 67,
  budget: 450000000,
  leader: 'Yuki Nakamura'
});

CREATE (dept2:Department {
  id: 'dept_sales',
  name: 'Sales',
  headcount: 15,
  budget: 180000000,
  leader: 'Kenji Sato'
});

CREATE (dept3:Department {
  id: 'dept_marketing',
  name: 'Marketing',
  headcount: 22,
  budget: 120000000,
  leader: 'Sarah Kim'
});

CREATE (dept4:Department {
  id: 'dept_customer_success',
  name: 'Customer Success',
  headcount: 22,
  budget: 85000000,
  leader: 'Miho Suzuki'
});

CREATE (dept5:Department {
  id: 'dept_product',
  name: 'Product',
  headcount: 18,
  budget: 90000000,
  leader: 'Kenji Tanaka'
});

CREATE (dept6:Department {
  id: 'dept_finance',
  name: 'Finance',
  headcount: 14,
  budget: 55000000,
  leader: 'Raj Patel'
});

CREATE (dept7:Department {
  id: 'dept_people_ops',
  name: 'People Operations',
  headcount: 10,
  budget: 45000000,
  leader: 'Mika Tanaka'
});

CREATE (dept8:Department {
  id: 'dept_executive',
  name: 'Executive',
  headcount: 4,
  budget: 0,
  leader: 'Akiko Tanaka'
});

// Expected: 8 departments

// ============================================
// PART 5: Load Projects
// ============================================

CREATE (proj1:Project {
  id: 'project_ai_search',
  name: 'AI Search Implementation',
  status: 'In Progress',
  start_date: '2024-01-15',
  owner: 'Yuki Nakamura',
  budget: 40000000,
  description: 'AI-powered search for WorkFlow Pro'
});

CREATE (proj2:Project {
  id: 'project_mid_market_brand',
  name: 'Mid-Market Brand Transformation',
  status: 'Complete',
  start_date: '2024-01-01',
  end_date: '2024-06-30',
  owner: 'Sarah Kim',
  budget: 25000000,
  description: 'Reposition brand for mid-market segment'
});

CREATE (proj3:Project {
  id: 'project_aws_optimization',
  name: 'AWS Cost Optimization',
  status: 'In Progress',
  start_date: '2024-02-01',
  owner: 'Raj Patel',
  budget: 5000000,
  description: 'Reduce AWS costs from ¥70M to ¥45M annually'
});

CREATE (proj4:Project {
  id: 'project_tech_debt',
  name: '6-Week Technical Debt Sprint',
  status: 'Complete',
  start_date: '2024-07-01',
  end_date: '2024-08-12',
  owner: 'Yuki Nakamura',
  budget: 75000000,
  description: 'Pay down technical debt, improve velocity'
});

CREATE (proj5:Project {
  id: 'project_career_dev',
  name: 'Career Development Program',
  status: 'In Progress',
  start_date: '2024-06-30',
  owner: 'Akiko Tanaka',
  budget: 5000000,
  description: 'Company-wide career development initiative'
});

CREATE (proj6:Project {
  id: 'project_intercom',
  name: 'Intercom Implementation',
  status: 'Complete',
  start_date: '2023-11-01',
  end_date: '2024-02-28',
  owner: 'Yuki Nakamura',
  budget: 12000000,
  description: 'Replace Zendesk with Intercom for customer support'
});

CREATE (proj7:Project {
  id: 'project_self_serve',
  name: 'Self-Serve / PLG Initiative',
  status: 'Planned',
  start_date: '2024-10-01',
  owner: 'Kenji Tanaka',
  budget: 40000000,
  description: 'Product-led growth with free trial and self-serve'
});

CREATE (proj8:Project {
  id: 'project_soc2',
  name: 'SOC 2 Type II Certification',
  status: 'In Progress',
  start_date: '2024-09-01',
  owner: 'Yuki Nakamura',
  budget: 20000000,
  description: 'Security certification for enterprise customers'
});

CREATE (proj9:Project {
  id: 'project_mobile_rebuild',
  name: 'Mobile App Rebuild',
  status: 'In Progress',
  start_date: '2024-07-01',
  owner: 'Yuki Nakamura',
  budget: 30000000,
  description: 'Rebuild mobile apps with offline mode'
});

CREATE (proj10:Project {
  id: 'project_sales_expansion',
  name: 'Sales Team Expansion',
  status: 'In Progress',
  start_date: '2024-02-01',
  owner: 'Kenji Sato',
  budget: 18000000,
  description: 'Hire 6 new Account Executives (phased approach)'
});

CREATE (proj11:Project {
  id: 'project_working_capital',
  name: 'Working Capital Management',
  status: 'In Progress',
  start_date: '2024-07-01',
  owner: 'Raj Patel',
  budget: 8000000,
  description: 'Reduce DSO from 78 to 45 days'
});

CREATE (proj12:Project {
  id: 'project_pricing_strategy',
  name: 'Pricing Strategy (10-15% Increase)',
  status: 'Complete',
  start_date: '2024-02-20',
  end_date: '2024-04-01',
  owner: 'Raj Patel',
  budget: 2000000,
  description: 'Implement strategic price increases for new customers'
});

// Expected: 12 projects

// ============================================
// Verification
// ============================================

// Count all entities
MATCH (n)
RETURN labels(n) AS Label, count(n) AS Count
ORDER BY Count DESC;

// Expected output:
// Company: 42
// Person: 38
// Project: 12
// Department: 8
// Executive: 4
// Product: 3

// ============================================
// Script Complete
// ============================================
// Next: Run 04_load_decisions.cypher