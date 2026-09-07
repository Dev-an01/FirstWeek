"""
Neo4j Graph Deployer for Onboarding Service.

Creates and maintains graph nodes/relationships for:
- Companies
- Executives (with hierarchy levels)
- Decision cases
- Domain expertise

Integrates with existing graph_context system which uses Neo4j for:
1. Entity extraction (matching names to nodes)
2. Graph traversal (finding related documents)
3. Hybrid scoring (vector + graph proximity)

Data Isolation Model:
- Company-level: Shared by all executives (company_id set, executive_id=NULL)
- Executive-level: Specific to one executive (both company_id and executive_id set)
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from neo4j import GraphDatabase, AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)

# Hierarchy level mapping
HIERARCHY_LEVELS = {
    0: "CEO",
    1: "C-Suite",      # CTO, COO, CFO, CAIO, etc.
    2: "VP",           # Vice Presidents
    3: "Director",     # Directors
    4: "Manager",      # Managers
    5: "Lead",         # Team Leads
    6: "Individual",   # Individual Contributors
}

# Company name patterns for extraction from decision text
COMPANY_SUFFIXES = [
    "株式会社", "Corp", "Corporation", "Inc", "Inc.", "Ltd", "Ltd.",
    "LLC", "Co.", "Company", "Group", "Holdings", "Technologies",
    "Solutions", "Systems", "Enterprises", "International"
]


class Neo4jDeployer:
    """
    Deploys onboarding data to Neo4j graph database.

    Creates:
    - (:Company) nodes
    - (:Executive) nodes with hierarchy_level
    - (:Decision) nodes from decision_cases
    - (:Domain) nodes for expertise areas
    - Relationships: HAS_EXECUTIVE, MADE_DECISION, HAS_EXPERTISE, HAS_POLICY
    """

    def __init__(self, uri: str, user: str, password: str):
        """Initialize Neo4j connection."""
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self._connected = False

    async def connect(self) -> bool:
        """Establish connection to Neo4j."""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # Verify connection
            self.driver.verify_connectivity()
            self._connected = True
            logger.info(f"Connected to Neo4j at {self.uri}")

            # Initialize schema (constraints and indexes)
            await self._init_schema()

            return True
        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self._connected = False
            return False

    async def _init_schema(self):
        """Initialize Neo4j schema (constraints and indexes)."""
        if not self._connected:
            return

        try:
            with self.driver.session() as session:
                # Create constraints
                constraints = [
                    "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
                    "CREATE CONSTRAINT executive_id IF NOT EXISTS FOR (e:Executive) REQUIRE e.id IS UNIQUE",
                    "CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE",
                    "CREATE CONSTRAINT policy_id IF NOT EXISTS FOR (p:Policy) REQUIRE p.id IS UNIQUE",
                    "CREATE CONSTRAINT domain_id IF NOT EXISTS FOR (d:Domain) REQUIRE d.id IS UNIQUE",
                ]

                # Create indexes
                indexes = [
                    "CREATE INDEX executive_company IF NOT EXISTS FOR (e:Executive) ON (e.company_id)",
                    "CREATE INDEX executive_hierarchy IF NOT EXISTS FOR (e:Executive) ON (e.hierarchy_level)",
                    "CREATE INDEX decision_company IF NOT EXISTS FOR (d:Decision) ON (d.company_id)",
                    "CREATE INDEX decision_executive IF NOT EXISTS FOR (d:Decision) ON (d.executive_id)",
                    "CREATE INDEX policy_company IF NOT EXISTS FOR (p:Policy) ON (p.company_id)",
                ]

                for stmt in constraints + indexes:
                    try:
                        session.run(stmt)
                    except Exception:
                        pass  # Ignore if already exists

                logger.info("Neo4j schema initialized (constraints + indexes)")
        except Exception as e:
            logger.warning(f"Neo4j schema init warning: {e}")

    async def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            self._connected = False
            logger.info("Neo4j connection closed")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # =========================================================================
    # Company Operations
    # =========================================================================

    async def deploy_company(self, company_data: Dict[str, Any]) -> bool:
        """
        Create or update a Company node.

        Args:
            company_data: {id, name, industry, description, metadata}

        Returns:
            True if successful
        """
        if not self._connected:
            logger.warning("Neo4j not connected, skipping company deployment")
            return False

        try:
            with self.driver.session() as session:
                result = session.run("""
                    MERGE (c:Company {id: $id})
                    SET c.name = $name,
                        c.industry = $industry,
                        c.description = $description,
                        c.updated_at = datetime()
                    RETURN c.id as id
                """,
                    id=company_data["id"],
                    name=company_data["name"],
                    industry=company_data.get("industry", ""),
                    description=company_data.get("description", "")
                )
                record = result.single()
                logger.info(f"Deployed Company node: {record['id']}")
                return True
        except Exception as e:
            logger.error(f"Failed to deploy company: {e}")
            return False

    # =========================================================================
    # Executive Operations
    # =========================================================================

    async def deploy_executive(
        self,
        executive_data: Dict[str, Any],
        company_id: str,
        profile_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create or update an Executive node and link to Company.

        Node properties match the existing graph_context entity extraction expectations.

        Args:
            executive_data: {id, name, name_english, title, department, hierarchy_level, email}
            company_id: Company to link to
            profile_data: Optional profile for additional properties

        Returns:
            True if successful
        """
        if not self._connected:
            logger.warning("Neo4j not connected, skipping executive deployment")
            return False

        try:
            hierarchy_level = executive_data.get("hierarchy_level", 4)
            hierarchy_tier = HIERARCHY_LEVELS.get(hierarchy_level, "Individual")

            # Extract communication style scales from profile if available
            formality = directness = warmth = 5
            if profile_data:
                comm_style = profile_data.get("communication_style", {})
                formality = comm_style.get("formality_scale", 5)
                directness = comm_style.get("directness_scale", 5)
                warmth = comm_style.get("warmth_scale", 5)

            with self.driver.session() as session:
                # Create/update Executive node with properties matching existing structure
                result = session.run("""
                    MERGE (e:Executive {id: $id})
                    SET e.name = $name,
                        e.name_english = $name_english,
                        e.title = $title,
                        e.department = $department,
                        e.email = $email,
                        e.company_id = $company_id,
                        e.hierarchy_level = $hierarchy_level,
                        e.hierarchy_tier = $hierarchy_tier,
                        e.formality_scale = $formality,
                        e.directness_scale = $directness,
                        e.warmth_scale = $warmth,
                        e.updated_at = datetime()
                    WITH e
                    MATCH (c:Company {id: $company_id})
                    MERGE (c)-[:HAS_EXECUTIVE]->(e)
                    RETURN e.id as id
                """,
                    id=executive_data["id"],
                    name=executive_data["name"],
                    name_english=executive_data.get("name_english", ""),
                    title=executive_data.get("title", ""),
                    department=executive_data.get("department", ""),
                    email=executive_data.get("email", ""),
                    company_id=company_id,
                    hierarchy_level=hierarchy_level,
                    hierarchy_tier=hierarchy_tier,
                    formality=formality,
                    directness=directness,
                    warmth=warmth
                )
                record = result.single()
                logger.info(f"Deployed Executive node: {record['id']} (Level {hierarchy_level}: {hierarchy_tier})")
                return True
        except Exception as e:
            logger.error(f"Failed to deploy executive: {e}")
            return False

    # =========================================================================
    # Text Analysis Utilities
    # =========================================================================

    def _extract_company_names(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract potential company names from text.

        Returns:
            List of (company_name, company_id) tuples
        """
        if not text:
            return []

        companies = []

        # Pattern 1: Japanese company names (株式会社X or X株式会社)
        jp_pattern = r'(?:株式会社\s*([^\s、。]+)|([^\s、。]+)\s*株式会社)'
        for match in re.finditer(jp_pattern, text):
            name = match.group(1) or match.group(2)
            if name and len(name) > 1:
                company_id = f"company_{name.lower().replace(' ', '_')}"
                companies.append((f"{name}株式会社", company_id))

        # Pattern 2: English company names with suffixes
        for suffix in ["Corp", "Corporation", "Inc", "Ltd", "LLC", "Company", "Group"]:
            pattern = rf'([A-Z][A-Za-z0-9\s]+)\s+{suffix}\.?'
            for match in re.finditer(pattern, text):
                name = f"{match.group(1).strip()} {suffix}"
                company_id = f"company_{match.group(1).strip().lower().replace(' ', '_')}"
                if len(match.group(1).strip()) > 2:
                    companies.append((name, company_id))

        # Pattern 3: Capitalized multi-word names (likely company names)
        cap_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'
        for match in re.finditer(cap_pattern, text):
            name = match.group(1)
            # Filter out common non-company phrases
            skip_words = ["The", "This", "That", "When", "What", "How", "Why"]
            if not any(name.startswith(w) for w in skip_words) and len(name) > 5:
                company_id = f"company_{name.lower().replace(' ', '_')}"
                companies.append((name, company_id))

        # Deduplicate
        seen = set()
        unique = []
        for name, cid in companies:
            if cid not in seen:
                seen.add(cid)
                unique.append((name, cid))

        return unique[:5]  # Limit to 5 companies per decision

    # =========================================================================
    # Decision Case Operations
    # =========================================================================

    async def deploy_decision_cases(
        self,
        executive_id: str,
        company_id: str,
        decision_cases: List[Dict[str, Any]],
        executive_name: str = ""
    ) -> int:
        """
        Create Decision nodes from profile decision_cases.

        Also extracts company names from decision text and creates
        INVOLVES_COMPANY relationships for graph traversal.

        Args:
            executive_id: Executive who made the decisions
            company_id: Company context
            decision_cases: List of decision case dicts from profile
            executive_name: Name of the executive (for Decision node)

        Returns:
            Number of decisions deployed
        """
        if not self._connected:
            logger.warning("Neo4j not connected, skipping decision deployment")
            return 0

        if not decision_cases:
            return 0

        deployed = 0
        try:
            with self.driver.session() as session:
                for i, case in enumerate(decision_cases):
                    # Generate decision ID matching existing pattern
                    exec_short = executive_id.upper().replace("_", "")[:10]
                    decision_id = f"DC_{exec_short}_{i+1:03d}"

                    title = case.get("title", case.get("case_name", f"Decision {i+1}"))
                    situation = case.get("situation", case.get("context", ""))
                    decision_made = case.get("decision", case.get("decision_made", ""))
                    rationale = case.get("rationale", case.get("reasoning", ""))
                    outcome = case.get("outcome", "")
                    category = case.get("category", "general")

                    # Create Decision node with properties matching existing structure
                    session.run("""
                        MERGE (d:Decision {id: $decision_id})
                        SET d.title = $title,
                            d.category = $category,
                            d.executive_id = $executive_id,
                            d.executive_name = $executive_name,
                            d.decision_made = $decision_made,
                            d.rationale_summary = $rationale,
                            d.outcome = $outcome,
                            d.company_id = $company_id,
                            d.confidence = 0.8,
                            d.precedent = false,
                            d.updated_at = datetime()
                        WITH d
                        MATCH (e:Executive {id: $executive_id})
                        MERGE (e)-[:MADE_DECISION {confidence: 0.8}]->(d)
                    """,
                        decision_id=decision_id,
                        title=title,
                        category=category,
                        executive_id=executive_id,
                        executive_name=executive_name,
                        decision_made=decision_made,
                        rationale=rationale,
                        outcome=outcome,
                        company_id=company_id
                    )

                    # Extract company names from decision text
                    full_text = f"{title} {situation} {decision_made} {rationale} {outcome}"
                    involved_companies = self._extract_company_names(full_text)

                    # Create Company nodes and INVOLVES_COMPANY relationships
                    for comp_name, comp_id in involved_companies:
                        try:
                            session.run("""
                                MERGE (c:Company {id: $comp_id})
                                ON CREATE SET c.name = $comp_name,
                                              c.type = 'external',
                                              c.created_at = datetime()
                                WITH c
                                MATCH (d:Decision {id: $decision_id})
                                MERGE (d)-[:INVOLVES_COMPANY {
                                    role: 'mentioned',
                                    context: 'Extracted from decision text'
                                }]->(c)
                            """,
                                comp_id=comp_id,
                                comp_name=comp_name,
                                decision_id=decision_id
                            )
                        except Exception:
                            pass  # Ignore failures for individual company links

                    deployed += 1

                logger.info(f"Deployed {deployed} Decision nodes for {executive_id}")
        except Exception as e:
            logger.error(f"Failed to deploy decisions: {e}")

        return deployed

    # =========================================================================
    # Domain Expertise Operations
    # =========================================================================

    async def deploy_domain_expertise(
        self,
        executive_id: str,
        domains: List[str]
    ) -> int:
        """
        Create Domain nodes and link to Executive.

        Args:
            executive_id: Executive with the expertise
            domains: List of domain/expertise areas

        Returns:
            Number of domains deployed
        """
        if not self._connected:
            logger.warning("Neo4j not connected, skipping domain deployment")
            return 0

        if not domains:
            return 0

        deployed = 0
        try:
            with self.driver.session() as session:
                for domain in domains:
                    if not domain or not domain.strip():
                        continue

                    # Normalize domain name
                    domain_id = domain.lower().replace(" ", "_").replace("-", "_")

                    session.run("""
                        MERGE (d:Domain {id: $domain_id})
                        SET d.name = $domain_name
                        WITH d
                        MATCH (e:Executive {id: $executive_id})
                        MERGE (e)-[:HAS_EXPERTISE]->(d)
                    """,
                        domain_id=domain_id,
                        domain_name=domain,
                        executive_id=executive_id
                    )
                    deployed += 1

                logger.info(f"Deployed {deployed} Domain nodes for {executive_id}")
        except Exception as e:
            logger.error(f"Failed to deploy domains: {e}")

        return deployed

    # =========================================================================
    # Company Policy Operations
    # =========================================================================

    async def deploy_company_policy(
        self,
        company_id: str,
        policy_data: Dict[str, Any],
        owner_executive_id: Optional[str] = None
    ) -> bool:
        """
        Create Policy node (company-wide, not executive-specific).

        Args:
            company_id: Company the policy belongs to
            policy_data: {id, name, category, content}
            owner_executive_id: Optional executive who owns/created the policy

        Returns:
            True if successful
        """
        if not self._connected:
            logger.warning("Neo4j not connected, skipping policy deployment")
            return False

        try:
            with self.driver.session() as session:
                session.run("""
                    MERGE (p:Policy {id: $id})
                    SET p.name = $name,
                        p.category = $category,
                        p.company_id = $company_id,
                        p.owner_executive_id = $owner_executive_id,
                        p.updated_at = datetime()
                    WITH p
                    MATCH (c:Company {id: $company_id})
                    MERGE (c)-[:HAS_POLICY]->(p)
                """,
                    id=policy_data["id"],
                    name=policy_data["name"],
                    category=policy_data.get("category", "general"),
                    company_id=company_id,
                    owner_executive_id=owner_executive_id
                )

                # Link to owner executive if specified
                if owner_executive_id:
                    session.run("""
                        MATCH (e:Executive {id: $executive_id})
                        MATCH (p:Policy {id: $policy_id})
                        MERGE (e)-[:OWNS_POLICY]->(p)
                    """,
                        executive_id=owner_executive_id,
                        policy_id=policy_data["id"]
                    )

                logger.info(f"Deployed Policy node: {policy_data['id']}")
                return True
        except Exception as e:
            logger.error(f"Failed to deploy policy: {e}")
            return False

    # =========================================================================
    # Full Onboarding Deployment
    # =========================================================================

    async def deploy_onboarding_result(
        self,
        company_data: Dict[str, Any],
        executive_data: Dict[str, Any],
        profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deploy complete onboarding result to Neo4j.

        Creates:
        - Company node (if not exists)
        - Executive node (linked to company, with communication scales)
        - Decision nodes (from profile decision_cases)
        - Company nodes extracted from decision text (with INVOLVES_COMPANY)
        - Domain nodes (from profile domain_affinity)

        This enables the graph_context system to:
        1. Match executive names to nodes
        2. Traverse from Executive → Decision → Company
        3. Calculate graph proximity for hybrid scoring

        Args:
            company_data: Company info
            executive_data: Executive basic info
            profile_data: Full assembled profile

        Returns:
            Deployment summary {company, executive, decisions, domains, companies_extracted}
        """
        result = {
            "company": False,
            "executive": False,
            "decisions": 0,
            "domains": 0,
            "companies_extracted": 0,
            "success": False
        }

        if not self._connected:
            await self.connect()

        if not self._connected:
            logger.warning("Neo4j unavailable, skipping graph deployment")
            return result

        try:
            # 1. Deploy Company (the executive's company)
            result["company"] = await self.deploy_company(company_data)

            # 2. Deploy Executive with profile data for communication scales
            result["executive"] = await self.deploy_executive(
                executive_data,
                company_data["id"],
                profile_data
            )

            # 3. Deploy Decision Cases from profile
            # Also extracts and creates Company nodes mentioned in decisions
            decision_cases = profile_data.get("decision_cases", [])
            executive_name = executive_data.get("name", "")
            result["decisions"] = await self.deploy_decision_cases(
                executive_data["id"],
                company_data["id"],
                decision_cases,
                executive_name
            )

            # Count extracted companies
            if self._connected:
                try:
                    with self.driver.session() as session:
                        count_result = session.run("""
                            MATCH (d:Decision {executive_id: $exec_id})-[:INVOLVES_COMPANY]->(c:Company)
                            WHERE c.type = 'external'
                            RETURN count(DISTINCT c) as count
                        """, exec_id=executive_data["id"])
                        record = count_result.single()
                        result["companies_extracted"] = record["count"] if record else 0
                except Exception:
                    pass

            # 4. Deploy Domain Expertise from profile
            domain_affinity = profile_data.get("domain_affinity", {})
            domains = []
            if isinstance(domain_affinity, dict):
                domains.extend(domain_affinity.get("primary_domains", []))
                domains.extend(domain_affinity.get("secondary_domains", []))
            result["domains"] = await self.deploy_domain_expertise(
                executive_data["id"],
                domains
            )

            result["success"] = result["company"] and result["executive"]
            logger.info(f"Neo4j deployment complete: {result}")

        except Exception as e:
            logger.error(f"Neo4j deployment failed: {e}")

        return result

    # =========================================================================
    # Person Operations
    # =========================================================================

    async def deploy_people(
        self,
        executive_id: str,
        company_id: str,
        profile_data: Dict[str, Any]
    ) -> int:
        """
        Create Person nodes from profile leadership_team and key_relationships.

        Args:
            executive_id: Executive who knows these people
            company_id: Company context for multi-tenant isolation
            profile_data: Full assembled profile

        Returns:
            Number of Person nodes deployed
        """
        if not self._connected:
            logger.warning("Neo4j not connected, skipping people deployment")
            return 0

        people = []

        # Extract from background_identity
        bg = profile_data.get("background_identity", {})
        if isinstance(bg, dict):
            for person in bg.get("leadership_team", []):
                if isinstance(person, dict):
                    people.append({
                        "name": person.get("name", ""),
                        "role": person.get("role", person.get("title", "")),
                    })
                elif isinstance(person, str) and person.strip():
                    people.append({"name": person.strip(), "role": ""})

            for person in bg.get("key_relationships", []):
                if isinstance(person, dict):
                    people.append({
                        "name": person.get("name", ""),
                        "role": person.get("role", person.get("relationship", "")),
                    })
                elif isinstance(person, str) and person.strip():
                    people.append({"name": person.strip(), "role": ""})

        if not people:
            return 0

        deployed = 0
        try:
            with self.driver.session() as session:
                for person in people:
                    name = person.get("name", "").strip()
                    if not name:
                        continue

                    name_slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
                    person_id = f"{company_id}_person_{name_slug}"

                    session.run("""
                        MERGE (p:Person {id: $person_id})
                        SET p.name = $name,
                            p.role = $role,
                            p.company_id = $company_id,
                            p.updated_at = datetime()
                        WITH p
                        MATCH (e:Executive {id: $executive_id})
                        MERGE (e)-[:KNOWS]->(p)
                    """,
                        person_id=person_id,
                        name=name,
                        role=person.get("role", ""),
                        company_id=company_id,
                        executive_id=executive_id
                    )
                    deployed += 1

                logger.info(f"Deployed {deployed} Person nodes for {executive_id}")
        except Exception as e:
            logger.error(f"Failed to deploy people: {e}")

        return deployed

    # =========================================================================
    # Product Operations
    # =========================================================================

    async def deploy_products(
        self,
        executive_id: str,
        company_id: str,
        profile_data: Dict[str, Any]
    ) -> int:
        """
        Create Product nodes from profile domain_expertise.

        Args:
            executive_id: Executive context
            company_id: Company context for multi-tenant isolation
            profile_data: Full assembled profile

        Returns:
            Number of Product nodes deployed
        """
        if not self._connected:
            logger.warning("Neo4j not connected, skipping product deployment")
            return 0

        products = []

        domain_exp = profile_data.get("domain_expertise", {})
        if isinstance(domain_exp, dict):
            for item in domain_exp.get("products", []):
                if isinstance(item, dict):
                    products.append(item.get("name", str(item)))
                elif isinstance(item, str) and item.strip():
                    products.append(item.strip())

            for item in domain_exp.get("technologies", []):
                if isinstance(item, dict):
                    products.append(item.get("name", str(item)))
                elif isinstance(item, str) and item.strip():
                    products.append(item.strip())

        if not products:
            return 0

        deployed = 0
        try:
            with self.driver.session() as session:
                for product_name in products:
                    if not product_name:
                        continue

                    name_slug = re.sub(r'[^a-z0-9]+', '_', product_name.lower()).strip('_')
                    product_id = f"{company_id}_product_{name_slug}"

                    session.run("""
                        MERGE (p:Product {id: $product_id})
                        SET p.name = $product_name,
                            p.company_id = $company_id,
                            p.updated_at = datetime()
                        WITH p
                        MATCH (c:Company {id: $company_id})
                        MERGE (c)-[:HAS_PRODUCT]->(p)
                    """,
                        product_id=product_id,
                        product_name=product_name,
                        company_id=company_id
                    )
                    deployed += 1

                logger.info(f"Deployed {deployed} Product nodes for {executive_id}")
        except Exception as e:
            logger.error(f"Failed to deploy products: {e}")

        return deployed

    # =========================================================================
    # Department Operations
    # =========================================================================

    async def deploy_departments(
        self,
        executive_id: str,
        company_id: str,
        profile_data: Dict[str, Any]
    ) -> int:
        """
        Create Department nodes from profile background_identity.

        Args:
            executive_id: Executive context
            company_id: Company context for multi-tenant isolation
            profile_data: Full assembled profile

        Returns:
            Number of Department nodes deployed
        """
        if not self._connected:
            logger.warning("Neo4j not connected, skipping department deployment")
            return 0

        departments = []

        bg = profile_data.get("background_identity", {})
        if isinstance(bg, dict):
            # Primary department
            dept = bg.get("department", "")
            if isinstance(dept, str) and dept.strip():
                departments.append(dept.strip())

            # Organizational structure
            org_structure = bg.get("organizational_structure", [])
            if isinstance(org_structure, list):
                for item in org_structure:
                    if isinstance(item, dict):
                        name = item.get("name", item.get("department", ""))
                        if name and name.strip():
                            departments.append(name.strip())
                    elif isinstance(item, str) and item.strip():
                        departments.append(item.strip())
            elif isinstance(org_structure, dict):
                for key, val in org_structure.items():
                    if isinstance(val, str) and val.strip():
                        departments.append(val.strip())
                    elif key.strip():
                        departments.append(key.strip())

        # Deduplicate
        seen = set()
        unique_departments = []
        for d in departments:
            d_lower = d.lower()
            if d_lower not in seen:
                seen.add(d_lower)
                unique_departments.append(d)

        if not unique_departments:
            return 0

        deployed = 0
        primary_dept = unique_departments[0] if unique_departments else None

        try:
            with self.driver.session() as session:
                for dept_name in unique_departments:
                    name_slug = re.sub(r'[^a-z0-9]+', '_', dept_name.lower()).strip('_')
                    dept_id = f"{company_id}_dept_{name_slug}"

                    # Determine relationship type: LEADS for primary dept, BELONGS_TO for others
                    rel_type = "LEADS" if dept_name == primary_dept else "BELONGS_TO"

                    session.run("""
                        MERGE (d:Department {id: $dept_id})
                        SET d.name = $dept_name,
                            d.company_id = $company_id,
                            d.updated_at = datetime()
                        WITH d
                        MATCH (c:Company {id: $company_id})
                        MERGE (c)-[:HAS_DEPARTMENT]->(d)
                    """,
                        dept_id=dept_id,
                        dept_name=dept_name,
                        company_id=company_id
                    )

                    # Create executive → department relationship
                    if rel_type == "LEADS":
                        session.run("""
                            MATCH (e:Executive {id: $executive_id})
                            MATCH (d:Department {id: $dept_id})
                            MERGE (e)-[:LEADS]->(d)
                        """,
                            executive_id=executive_id,
                            dept_id=dept_id
                        )
                    else:
                        session.run("""
                            MATCH (e:Executive {id: $executive_id})
                            MATCH (d:Department {id: $dept_id})
                            MERGE (e)-[:BELONGS_TO]->(d)
                        """,
                            executive_id=executive_id,
                            dept_id=dept_id
                        )

                    deployed += 1

                logger.info(f"Deployed {deployed} Department nodes for {executive_id}")
        except Exception as e:
            logger.error(f"Failed to deploy departments: {e}")

        return deployed

    # =========================================================================
    # Query Operations
    # =========================================================================

    async def get_company_executives(
        self,
        company_id: str,
        hierarchy: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all executives for a company.

        Args:
            company_id: Company ID
            hierarchy: If True, group by hierarchy_level

        Returns:
            List of executive dicts
        """
        if not self._connected:
            return []

        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (c:Company {id: $company_id})-[:HAS_EXECUTIVE]->(e:Executive)
                    RETURN e.id as id,
                           e.name as name,
                           e.name_english as name_english,
                           e.title as title,
                           e.department as department,
                           e.hierarchy_level as hierarchy_level,
                           e.hierarchy_tier as hierarchy_tier
                    ORDER BY e.hierarchy_level, e.name
                """, company_id=company_id)

                executives = [dict(record) for record in result]

                if hierarchy:
                    # Group by hierarchy level
                    by_level = {}
                    for exec in executives:
                        level = exec.get("hierarchy_level", 4)
                        if level not in by_level:
                            by_level[level] = []
                        by_level[level].append(exec)
                    return {"by_level": by_level, "executives": executives}

                return executives
        except Exception as e:
            logger.error(f"Failed to get company executives: {e}")
            return []

    async def get_executive_decisions(
        self,
        executive_id: str,
        company_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all decisions made by an executive.

        Args:
            executive_id: Executive ID
            company_id: Optional company filter

        Returns:
            List of decision dicts
        """
        if not self._connected:
            return []

        try:
            with self.driver.session() as session:
                query = """
                    MATCH (e:Executive {id: $executive_id})-[:MADE_DECISION]->(d:Decision)
                """
                if company_id:
                    query += " WHERE d.company_id = $company_id"
                query += """
                    RETURN d.id as id,
                           d.title as title,
                           d.category as category,
                           d.situation as situation,
                           d.decision as decision,
                           d.rationale as rationale,
                           d.outcome as outcome
                    ORDER BY d.id
                """

                result = session.run(query, executive_id=executive_id, company_id=company_id)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Failed to get executive decisions: {e}")
            return []


# Singleton instance
_neo4j_deployer: Optional[Neo4jDeployer] = None


async def get_neo4j_deployer() -> Neo4jDeployer:
    """Get or create Neo4j deployer singleton."""
    global _neo4j_deployer

    if _neo4j_deployer is None:
        from onboarding.config import NEO4J_CONFIG
        _neo4j_deployer = Neo4jDeployer(
            uri=NEO4J_CONFIG["uri"],
            user=NEO4J_CONFIG["user"],
            password=NEO4J_CONFIG["password"]
        )
        await _neo4j_deployer.connect()

    return _neo4j_deployer
