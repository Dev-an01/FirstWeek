# Neural Graph Migration Plan - Part 2

## 4. Phase 2: Logic Graph Engine (Weeks 5-8)

### 4.1 Objective
Transform Neo4j from data storage to behavior controller by adding cognitive rules as nodes and activation relationships.

### 4.2 Logic Graph Schema

```cypher
// ============================================================
// LOGIC GRAPH SCHEMA - Neo4j
// Rules encoded as nodes, behavior driven by traversal
// ============================================================

// ------------------------------------------------------------
// CORE ENTITY NODES
// ------------------------------------------------------------

// Executive Node (enhanced with DNA reference)
CREATE CONSTRAINT executive_id IF NOT EXISTS
FOR (e:Executive) REQUIRE e.id IS UNIQUE;

// Company Node
CREATE CONSTRAINT company_id IF NOT EXISTS
FOR (c:Company) REQUIRE c.id IS UNIQUE;

// Industry Node
CREATE CONSTRAINT industry_id IF NOT EXISTS
FOR (i:Industry) REQUIRE i.id IS UNIQUE;

// ------------------------------------------------------------
// COGNITIVE RULE NODES (The "Neurons")
// ------------------------------------------------------------

// CognitiveRule - Behavioral rules that get activated
CREATE CONSTRAINT rule_id IF NOT EXISTS
FOR (r:CognitiveRule) REQUIRE r.id IS UNIQUE;

// Rule categories:
// - decision_making: How decisions are approached
// - communication: How responses are formatted
// - risk_management: Risk assessment behaviors
// - delegation: Delegation preferences
// - values: Value-based guidance
// - domain: Domain-specific expertise

// Example rules:
CREATE (r:CognitiveRule {
    id: 'rule_speed_over_perfection',
    category: 'decision_making',
    priority: 1,
    prompt_injection: 'Prioritize speed over perfection. Done is better than perfect. Ship fast, iterate based on feedback.',
    anti_patterns: ['extensive analysis paralysis', 'waiting for perfect information'],
    activation_keywords: ['decision', 'should we', 'timeline', 'deadline']
});

CREATE (r:CognitiveRule {
    id: 'rule_compliance_check',
    category: 'risk_management',
    priority: 0,  -- 0 = mandatory, always check
    prompt_injection: 'Always verify regulatory and compliance implications before proceeding. Flag any potential violations.',
    anti_patterns: ['skip compliance', 'worry about rules later'],
    activation_keywords: ['compliance', 'regulation', 'legal', 'policy']
});

CREATE (r:CognitiveRule {
    id: 'rule_maximum_delegation',
    category: 'delegation',
    priority: 2,
    prompt_injection: 'Delegate maximally. Only decide what only you can decide. Empower team members to own their domains.',
    anti_patterns: ['micromanage', 'need to control everything'],
    activation_keywords: ['who should', 'assign', 'responsibility', 'ownership']
});

CREATE (r:CognitiveRule {
    id: 'rule_data_driven',
    category: 'decision_making',
    priority: 1,
    prompt_injection: 'Base decisions on data and facts. Ask "What does the data show?" before forming opinions.',
    anti_patterns: ['gut feeling only', 'assume without evidence'],
    activation_keywords: ['evidence', 'data', 'metrics', 'numbers']
});

CREATE (r:CognitiveRule {
    id: 'rule_transparency',
    category: 'values',
    priority: 1,
    prompt_injection: 'Maintain radical transparency. Share context openly, including bad news early. No hidden agendas.',
    anti_patterns: ['hide problems', 'sugarcoat issues'],
    activation_keywords: ['honest', 'transparent', 'share', 'communicate']
});

// ------------------------------------------------------------
// EXPERT NODES (Specialized response generators)
// ------------------------------------------------------------

CREATE CONSTRAINT expert_id IF NOT EXISTS
FOR (ex:Expert) REQUIRE ex.id IS UNIQUE;

CREATE (ex:Expert {
    id: 'expert_financial',
    name: 'Financial Analyst',
    domain: 'finance',
    prompt_template: 'Analyze from a financial perspective. Consider ROI, cash flow implications, budget impact, and financial risk. Use specific numbers when available.',
    keywords: ['budget', 'cost', 'revenue', 'roi', 'margin', 'financial', 'investment']
});

CREATE (ex:Expert {
    id: 'expert_technical',
    name: 'Technical Advisor',
    domain: 'technology',
    prompt_template: 'Provide technical analysis. Consider architecture implications, scalability, technical debt, and implementation complexity. Reference relevant technical concepts.',
    keywords: ['technical', 'architecture', 'code', 'system', 'engineering', 'infrastructure']
});

CREATE (ex:Expert {
    id: 'expert_strategic',
    name: 'Strategic Thinker',
    domain: 'strategy',
    prompt_template: 'Think strategically. Consider long-term implications, competitive positioning, market dynamics, and alignment with mission. Connect to broader business goals.',
    keywords: ['strategy', 'vision', 'long-term', 'competitive', 'market', 'growth']
});

CREATE (ex:Expert {
    id: 'expert_people',
    name: 'People & Culture',
    domain: 'hr',
    prompt_template: 'Consider the human element. Think about team dynamics, morale, career development, and organizational culture. Emphasize empathy and support.',
    keywords: ['team', 'hire', 'culture', 'morale', 'performance', 'career', 'people']
});

CREATE (ex:Expert {
    id: 'expert_legal',
    name: 'Legal & Compliance',
    domain: 'legal',
    prompt_template: 'Assess legal and compliance implications. Flag potential risks, regulatory requirements, and contractual obligations. Recommend consultation when uncertain.',
    keywords: ['legal', 'compliance', 'contract', 'regulation', 'liability', 'risk']
});

// ------------------------------------------------------------
// VALUE NODES (Decision philosophy)
// ------------------------------------------------------------

CREATE CONSTRAINT value_id IF NOT EXISTS
FOR (v:Value) REQUIRE v.id IS UNIQUE;

CREATE (v:Value {
    id: 'value_transparency',
    name: 'Transparency',
    description: 'Open communication, visible progress, no hidden agendas',
    trade_off_dimension: 'transparency_vs_discretion',
    default_weight: 0.8
});

CREATE (v:Value {
    id: 'value_speed',
    name: 'Speed',
    description: 'Bias toward action, iteration over perfection',
    trade_off_dimension: 'speed_vs_perfection',
    default_weight: 0.9
});

CREATE (v:Value {
    id: 'value_delegation',
    name: 'Maximum Delegation',
    description: 'Empower others, avoid micromanagement',
    trade_off_dimension: 'delegation_vs_control',
    default_weight: 0.85
});

// ------------------------------------------------------------
// RED FLAG NODES (Hard constraints - NEVER violated)
// ------------------------------------------------------------

CREATE CONSTRAINT redflag_id IF NOT EXISTS
FOR (rf:RedFlag) REQUIRE rf.id IS UNIQUE;

CREATE (rf:RedFlag {
    id: 'redflag_compliance_violation',
    category: 'compliance',
    condition: 'Any action that violates regulatory requirements',
    action: 'BLOCK',
    message: 'This may involve compliance violations. I cannot proceed without proper review.'
});

CREATE (rf:RedFlag {
    id: 'redflag_hidden_activity',
    category: 'transparency',
    condition: 'Activities happening without visibility',
    action: 'FLAG',
    message: 'This seems to involve hidden activities. Let me flag this for discussion.'
});

CREATE (rf:RedFlag {
    id: 'redflag_uncontrolled_risk',
    category: 'risk',
    condition: 'Risks that cannot be managed or controlled',
    action: 'ESCALATE',
    message: 'This involves uncontrollable risks. We should discuss this in person.'
});

// ------------------------------------------------------------
// RELATIONSHIPS (The "Synapses")
// ------------------------------------------------------------

// Executive → Company
// (exec)-[:WORKS_AT {role, since}]->(company)

// Company → Industry
// (company)-[:IN_INDUSTRY]->(industry)

// Industry → CognitiveRule (ACTIVATION EDGES)
// These determine which rules fire based on industry context
// (industry)-[:ACTIVATES_RULE {weight, context}]->(rule)

// Examples:
MATCH (i:Industry {id: 'ai_startup'}), (r:CognitiveRule {id: 'rule_speed_over_perfection'})
CREATE (i)-[:ACTIVATES_RULE {weight: 0.9, context: 'startup_culture'}]->(r);

MATCH (i:Industry {id: 'ai_startup'}), (r:CognitiveRule {id: 'rule_compliance_check'})
CREATE (i)-[:ACTIVATES_RULE {weight: 0.3, context: 'early_stage'}]->(r);

MATCH (i:Industry {id: 'pharma'}), (r:CognitiveRule {id: 'rule_compliance_check'})
CREATE (i)-[:ACTIVATES_RULE {weight: 0.95, context: 'heavily_regulated'}]->(r);

MATCH (i:Industry {id: 'pharma'}), (r:CognitiveRule {id: 'rule_speed_over_perfection'})
CREATE (i)-[:ACTIVATES_RULE {weight: 0.2, context: 'safety_first'}]->(r);

MATCH (i:Industry {id: 'finance'}), (r:CognitiveRule {id: 'rule_compliance_check'})
CREATE (i)-[:ACTIVATES_RULE {weight: 0.85, context: 'regulated'}]->(r);

// Executive → Value (Personal value weights)
// (exec)-[:HAS_VALUE {priority, personal_weight}]->(value)

// Executive → Expert (Domain affinity)
// (exec)-[:PREFERS_EXPERT {affinity}]->(expert)

// CognitiveRule → RedFlag (Guard relationships)
// (rule)-[:GUARDED_BY]->(redflag)

// Value → Value (Conflict relationships)
// (value1)-[:CONFLICTS_WITH {resolution_guidance}]->(value2)
```

### 4.3 Logic Graph Provider

**File**: `RAG/neural_engine/logic_graph_provider.py`

```python
"""
Logic Graph Provider - Traverses graph to activate cognitive rules.

This replaces hardcoded if/else logic with graph traversal.
Behavior emerges from graph structure, not code.
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from neo4j import AsyncGraphDatabase, AsyncDriver
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ActivatedRule:
    """A cognitive rule that has been activated by graph traversal."""
    rule_id: str
    category: str
    priority: int
    weight: float
    prompt_injection: str
    activation_path: str  # How we got here (for explainability)
    anti_patterns: List[str] = field(default_factory=list)


@dataclass
class ActivatedExpert:
    """An expert that has been selected for this query."""
    expert_id: str
    name: str
    domain: str
    affinity: float
    prompt_template: str


@dataclass
class RedFlagAlert:
    """A red flag that was triggered."""
    flag_id: str
    category: str
    condition: str
    action: str  # BLOCK, FLAG, ESCALATE
    message: str


@dataclass
class GraphActivationResult:
    """Complete result of graph traversal for a query."""
    executive_id: str
    activated_rules: List[ActivatedRule]
    selected_experts: List[ActivatedExpert]
    red_flags: List[RedFlagAlert]
    value_weights: Dict[str, float]
    context_explanation: str


class LogicGraphProvider:
    """
    Provides cognitive context via graph traversal.

    Instead of:
        if industry == "pharma": add_compliance_rules()

    We do:
        traverse(exec) → industry → activated_rules → prompt_injection

    The graph structure determines behavior.
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        min_rule_weight: float = 0.4,
        max_rules: int = 10
    ):
        self.driver: AsyncDriver = AsyncGraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password)
        )
        self.min_rule_weight = min_rule_weight
        self.max_rules = max_rules

    async def close(self):
        """Close the Neo4j connection."""
        await self.driver.close()

    async def activate_rules(
        self,
        executive_id: str,
        query_text: str,
        query_embedding: Optional[np.ndarray] = None
    ) -> GraphActivationResult:
        """
        Traverse graph to activate cognitive rules for this executive and query.

        Steps:
        1. Find executive's company and industry
        2. Traverse industry → rule activation edges
        3. Traverse executive → personal value weights
        4. Check for red flag triggers
        5. Select relevant experts
        6. Return activated context

        Args:
            executive_id: The executive's ID
            query_text: The user's query
            query_embedding: Optional query embedding for keyword matching

        Returns:
            GraphActivationResult with all activated context
        """
        async with self.driver.session() as session:
            # Step 1: Get industry-activated rules
            industry_rules = await self._get_industry_rules(session, executive_id)

            # Step 2: Get executive-specific value weights
            value_weights = await self._get_value_weights(session, executive_id)

            # Step 3: Get keyword-activated rules from query
            keyword_rules = await self._get_keyword_rules(session, query_text)

            # Step 4: Merge and deduplicate rules
            all_rules = self._merge_rules(industry_rules, keyword_rules)

            # Step 5: Check red flags
            red_flags = await self._check_red_flags(session, executive_id, query_text)

            # Step 6: Select experts based on query and executive affinity
            experts = await self._select_experts(session, executive_id, query_text)

            # Step 7: Build explanation
            explanation = self._build_explanation(
                executive_id, all_rules, experts, red_flags
            )

            return GraphActivationResult(
                executive_id=executive_id,
                activated_rules=all_rules,
                selected_experts=experts,
                red_flags=red_flags,
                value_weights=value_weights,
                context_explanation=explanation
            )

    async def _get_industry_rules(
        self,
        session,
        executive_id: str
    ) -> List[ActivatedRule]:
        """Get rules activated by executive's industry."""
        query = """
        MATCH (e:Executive {id: $exec_id})-[:WORKS_AT]->(c:Company)-[:IN_INDUSTRY]->(i:Industry)
        MATCH (i)-[a:ACTIVATES_RULE]->(r:CognitiveRule)
        WHERE a.weight >= $min_weight
        RETURN
            r.id as rule_id,
            r.category as category,
            r.priority as priority,
            a.weight as weight,
            r.prompt_injection as prompt_injection,
            r.anti_patterns as anti_patterns,
            i.name as industry_name,
            a.context as activation_context
        ORDER BY r.priority ASC, a.weight DESC
        LIMIT $max_rules
        """

        result = await session.run(
            query,
            exec_id=executive_id,
            min_weight=self.min_rule_weight,
            max_rules=self.max_rules
        )

        rules = []
        async for record in result:
            rules.append(ActivatedRule(
                rule_id=record['rule_id'],
                category=record['category'],
                priority=record['priority'],
                weight=record['weight'],
                prompt_injection=record['prompt_injection'],
                anti_patterns=record['anti_patterns'] or [],
                activation_path=f"Industry:{record['industry_name']}→{record['activation_context']}"
            ))

        return rules

    async def _get_keyword_rules(
        self,
        session,
        query_text: str
    ) -> List[ActivatedRule]:
        """Get rules activated by query keywords."""
        query_lower = query_text.lower()

        query = """
        MATCH (r:CognitiveRule)
        WHERE any(kw IN r.activation_keywords WHERE $query CONTAINS kw)
        RETURN
            r.id as rule_id,
            r.category as category,
            r.priority as priority,
            r.prompt_injection as prompt_injection,
            r.anti_patterns as anti_patterns,
            r.activation_keywords as keywords
        ORDER BY r.priority ASC
        LIMIT $max_rules
        """

        result = await session.run(
            query,
            query=query_lower,
            max_rules=self.max_rules
        )

        rules = []
        async for record in result:
            # Find which keywords matched
            matched_keywords = [
                kw for kw in (record['keywords'] or [])
                if kw in query_lower
            ]

            # Weight based on keyword match count
            weight = min(1.0, 0.5 + 0.1 * len(matched_keywords))

            rules.append(ActivatedRule(
                rule_id=record['rule_id'],
                category=record['category'],
                priority=record['priority'],
                weight=weight,
                prompt_injection=record['prompt_injection'],
                anti_patterns=record['anti_patterns'] or [],
                activation_path=f"Keywords:{','.join(matched_keywords)}"
            ))

        return rules

    async def _get_value_weights(
        self,
        session,
        executive_id: str
    ) -> Dict[str, float]:
        """Get executive's personal value weights."""
        query = """
        MATCH (e:Executive {id: $exec_id})-[hv:HAS_VALUE]->(v:Value)
        RETURN v.id as value_id, v.name as value_name, hv.personal_weight as weight
        ORDER BY hv.priority ASC
        """

        result = await session.run(query, exec_id=executive_id)

        weights = {}
        async for record in result:
            weights[record['value_id']] = record['weight']

        return weights

    async def _check_red_flags(
        self,
        session,
        executive_id: str,
        query_text: str
    ) -> List[RedFlagAlert]:
        """Check for red flag triggers."""
        query_lower = query_text.lower()

        # Check for compliance-related keywords
        compliance_keywords = [
            'compliance', 'regulation', 'legal', 'violation',
            'liability', 'lawsuit', 'hidden', 'secret'
        ]

        triggered_categories = set()
        for kw in compliance_keywords:
            if kw in query_lower:
                if kw in ['compliance', 'regulation', 'legal', 'violation', 'liability', 'lawsuit']:
                    triggered_categories.add('compliance')
                if kw in ['hidden', 'secret']:
                    triggered_categories.add('transparency')

        if not triggered_categories:
            return []

        # Get relevant red flags
        query = """
        MATCH (rf:RedFlag)
        WHERE rf.category IN $categories
        RETURN rf.id, rf.category, rf.condition, rf.action, rf.message
        """

        result = await session.run(query, categories=list(triggered_categories))

        flags = []
        async for record in result:
            flags.append(RedFlagAlert(
                flag_id=record['rf.id'],
                category=record['rf.category'],
                condition=record['rf.condition'],
                action=record['rf.action'],
                message=record['rf.message']
            ))

        return flags

    async def _select_experts(
        self,
        session,
        executive_id: str,
        query_text: str
    ) -> List[ActivatedExpert]:
        """Select relevant experts based on query and executive affinity."""
        query_lower = query_text.lower()

        # Get all experts with executive affinity
        query = """
        MATCH (ex:Expert)
        OPTIONAL MATCH (e:Executive {id: $exec_id})-[pe:PREFERS_EXPERT]->(ex)
        RETURN
            ex.id as expert_id,
            ex.name as name,
            ex.domain as domain,
            ex.prompt_template as prompt_template,
            ex.keywords as keywords,
            COALESCE(pe.affinity, 0.5) as affinity
        """

        result = await session.run(query, exec_id=executive_id)

        experts = []
        async for record in result:
            # Check keyword match
            keywords = record['keywords'] or []
            keyword_match = any(kw in query_lower for kw in keywords)

            if keyword_match:
                # Boost affinity for keyword match
                affinity = min(1.0, record['affinity'] + 0.3)
            else:
                affinity = record['affinity']

            if keyword_match or affinity > 0.5:
                experts.append(ActivatedExpert(
                    expert_id=record['expert_id'],
                    name=record['name'],
                    domain=record['domain'],
                    affinity=affinity,
                    prompt_template=record['prompt_template']
                ))

        # Sort by affinity and return top 2
        experts.sort(key=lambda x: x.affinity, reverse=True)
        return experts[:2]

    def _merge_rules(
        self,
        industry_rules: List[ActivatedRule],
        keyword_rules: List[ActivatedRule]
    ) -> List[ActivatedRule]:
        """Merge rules from different sources, deduplicating by ID."""
        rules_by_id: Dict[str, ActivatedRule] = {}

        # Industry rules first
        for rule in industry_rules:
            rules_by_id[rule.rule_id] = rule

        # Keyword rules (merge weights if duplicate)
        for rule in keyword_rules:
            if rule.rule_id in rules_by_id:
                # Combine weights (but cap at 1.0)
                existing = rules_by_id[rule.rule_id]
                combined_weight = min(1.0, existing.weight + rule.weight * 0.3)
                existing.weight = combined_weight
                existing.activation_path += f" + {rule.activation_path}"
            else:
                rules_by_id[rule.rule_id] = rule

        # Sort by priority then weight
        sorted_rules = sorted(
            rules_by_id.values(),
            key=lambda r: (r.priority, -r.weight)
        )

        return sorted_rules[:self.max_rules]

    def _build_explanation(
        self,
        executive_id: str,
        rules: List[ActivatedRule],
        experts: List[ActivatedExpert],
        red_flags: List[RedFlagAlert]
    ) -> str:
        """Build human-readable explanation of graph activation."""
        parts = [f"Context for {executive_id}:"]

        if rules:
            rule_summary = ", ".join([r.rule_id.replace('rule_', '') for r in rules[:5]])
            parts.append(f"Active rules: {rule_summary}")

        if experts:
            expert_summary = ", ".join([e.name for e in experts])
            parts.append(f"Expert lens: {expert_summary}")

        if red_flags:
            flag_summary = ", ".join([f.category for f in red_flags])
            parts.append(f"⚠️ Red flags: {flag_summary}")

        return " | ".join(parts)


class LogicGraphPromptInjector:
    """
    Converts graph activation results into prompt sections.

    This replaces hardcoded prompt sections with dynamically
    generated content based on graph traversal.
    """

    def __init__(self, max_tokens_per_rule: int = 50):
        self.max_tokens_per_rule = max_tokens_per_rule

    def build_rules_section(
        self,
        result: GraphActivationResult,
        max_tokens: int = 300
    ) -> str:
        """
        Build prompt section from activated rules.

        Returns a prompt section that can be injected into the
        system prompt's dynamic content area.
        """
        if not result.activated_rules:
            return ""

        lines = ["YOUR ACTIVE COGNITIVE RULES:"]
        lines.append("(Apply these based on context relevance)")
        lines.append("")

        token_count = 0
        for rule in result.activated_rules:
            if token_count > max_tokens:
                break

            # Format rule
            rule_text = f"• [{rule.category.upper()}] {rule.prompt_injection}"
            lines.append(rule_text)

            # Add anti-patterns if space allows
            if rule.anti_patterns and token_count < max_tokens - 50:
                anti = ", ".join(rule.anti_patterns[:2])
                lines.append(f"  (Avoid: {anti})")

            token_count += len(rule_text.split()) + 10

        return "\n".join(lines)

    def build_expert_section(
        self,
        result: GraphActivationResult,
        max_tokens: int = 150
    ) -> str:
        """Build prompt section from selected experts."""
        if not result.selected_experts:
            return ""

        lines = ["YOUR EXPERT PERSPECTIVE FOR THIS QUERY:"]
        lines.append("")

        for expert in result.selected_experts[:2]:
            lines.append(f"As {expert.name} (affinity: {expert.affinity:.0%}):")
            lines.append(f"  {expert.prompt_template}")
            lines.append("")

        return "\n".join(lines)

    def build_red_flag_section(
        self,
        result: GraphActivationResult
    ) -> str:
        """Build red flag warnings section."""
        if not result.red_flags:
            return ""

        lines = ["⚠️ RED FLAG ALERTS:"]
        lines.append("(These constraints CANNOT be overridden)")
        lines.append("")

        for flag in result.red_flags:
            lines.append(f"• [{flag.action}] {flag.category}: {flag.message}")

        return "\n".join(lines)

    def build_values_section(
        self,
        result: GraphActivationResult,
        max_tokens: int = 100
    ) -> str:
        """Build values section with personal weights."""
        if not result.value_weights:
            return ""

        lines = ["YOUR VALUE PRIORITIES:"]

        # Sort by weight
        sorted_values = sorted(
            result.value_weights.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for value_id, weight in sorted_values[:5]:
            value_name = value_id.replace('value_', '').replace('_', ' ').title()
            weight_bar = "█" * int(weight * 5) + "░" * (5 - int(weight * 5))
            lines.append(f"  {value_name}: {weight_bar} ({weight:.0%})")

        return "\n".join(lines)

    def build_complete_injection(
        self,
        result: GraphActivationResult,
        max_tokens: int = 600
    ) -> str:
        """
        Build complete dynamic prompt injection.

        This replaces the hardcoded cognitive layers with
        dynamically generated content from graph traversal.
        """
        sections = []

        # Red flags first (most important)
        red_flag_section = self.build_red_flag_section(result)
        if red_flag_section:
            sections.append(red_flag_section)

        # Then rules
        rules_section = self.build_rules_section(result, max_tokens=250)
        if rules_section:
            sections.append(rules_section)

        # Then experts
        expert_section = self.build_expert_section(result, max_tokens=150)
        if expert_section:
            sections.append(expert_section)

        # Then values
        values_section = self.build_values_section(result, max_tokens=100)
        if values_section:
            sections.append(values_section)

        # Join with separators
        if sections:
            separator = "\n" + "─" * 50 + "\n"
            return separator.join(sections)

        return ""
```

### 4.4 Graph Initialization Script

**File**: `RAG/init-scripts/initialize_logic_graph.py`

```python
"""
Initialize Logic Graph with base cognitive rules and relationships.

This script:
1. Creates constraint and indexes
2. Loads base cognitive rules
3. Loads industry → rule relationships
4. Sets default weights

Run once during deployment, then maintain via admin API.
"""

import asyncio
import logging
from neo4j import AsyncGraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Base cognitive rules
COGNITIVE_RULES = [
    {
        "id": "rule_speed_over_perfection",
        "category": "decision_making",
        "priority": 1,
        "prompt_injection": "Prioritize speed over perfection. Done is better than perfect. Ship fast, iterate based on feedback.",
        "anti_patterns": ["analysis paralysis", "waiting for perfect information", "endless planning"],
        "activation_keywords": ["decision", "should we", "timeline", "deadline", "quickly", "urgent"]
    },
    {
        "id": "rule_compliance_check",
        "category": "risk_management",
        "priority": 0,
        "prompt_injection": "Always verify regulatory and compliance implications. Flag potential violations immediately.",
        "anti_patterns": ["skip compliance", "worry about rules later", "bypass approval"],
        "activation_keywords": ["compliance", "regulation", "legal", "policy", "audit", "governance"]
    },
    {
        "id": "rule_maximum_delegation",
        "category": "delegation",
        "priority": 2,
        "prompt_injection": "Delegate maximally. Only decide what only you can decide. Empower team members to own their domains.",
        "anti_patterns": ["micromanage", "need to control everything", "do it myself"],
        "activation_keywords": ["who should", "assign", "responsibility", "ownership", "delegate", "team"]
    },
    {
        "id": "rule_data_driven",
        "category": "decision_making",
        "priority": 1,
        "prompt_injection": "Base decisions on data and facts. Ask 'What does the data show?' before forming opinions.",
        "anti_patterns": ["gut feeling only", "assume without evidence", "skip analysis"],
        "activation_keywords": ["evidence", "data", "metrics", "numbers", "analysis", "measure"]
    },
    {
        "id": "rule_transparency",
        "category": "values",
        "priority": 1,
        "prompt_injection": "Maintain radical transparency. Share context openly, including bad news early. No hidden agendas.",
        "anti_patterns": ["hide problems", "sugarcoat issues", "avoid difficult conversations"],
        "activation_keywords": ["honest", "transparent", "share", "communicate", "open", "visible"]
    },
    {
        "id": "rule_focus_resources",
        "category": "strategy",
        "priority": 2,
        "prompt_injection": "Focus is strategy. Avoid spreading resources thin. Concentrate effort on high-impact areas.",
        "anti_patterns": ["do everything", "spread too thin", "say yes to everything"],
        "activation_keywords": ["focus", "priority", "concentrate", "resources", "allocate", "limited"]
    },
    {
        "id": "rule_soft_assertion",
        "category": "communication",
        "priority": 3,
        "prompt_injection": "Use soft assertions: 'I think...', 'In my view...', '〜と思います'. Express opinions while inviting dialogue.",
        "anti_patterns": ["absolute statements", "this is the only way", "you must"],
        "activation_keywords": ["opinion", "think", "believe", "view", "perspective"]
    },
    {
        "id": "rule_context_before_direction",
        "category": "communication",
        "priority": 3,
        "prompt_injection": "Explain the 'why' before the 'what'. Provide context so others understand the reasoning.",
        "anti_patterns": ["just do it", "because I said so", "no explanation"],
        "activation_keywords": ["explain", "why", "context", "background", "reasoning"]
    }
]

# Industries with default rule weights
INDUSTRIES = [
    {
        "id": "ai_startup",
        "name": "AI Startup",
        "characteristics": "Fast-moving, high risk tolerance, innovation-focused",
        "rule_weights": {
            "rule_speed_over_perfection": 0.9,
            "rule_compliance_check": 0.3,
            "rule_maximum_delegation": 0.8,
            "rule_data_driven": 0.7,
            "rule_transparency": 0.8,
            "rule_focus_resources": 0.9
        }
    },
    {
        "id": "pharma",
        "name": "Pharmaceutical",
        "characteristics": "Heavily regulated, safety-critical, long development cycles",
        "rule_weights": {
            "rule_speed_over_perfection": 0.2,
            "rule_compliance_check": 0.95,
            "rule_maximum_delegation": 0.5,
            "rule_data_driven": 0.9,
            "rule_transparency": 0.7,
            "rule_focus_resources": 0.6
        }
    },
    {
        "id": "finance",
        "name": "Financial Services",
        "characteristics": "Regulated, risk-conscious, data-driven",
        "rule_weights": {
            "rule_speed_over_perfection": 0.4,
            "rule_compliance_check": 0.85,
            "rule_maximum_delegation": 0.6,
            "rule_data_driven": 0.95,
            "rule_transparency": 0.7,
            "rule_focus_resources": 0.7
        }
    },
    {
        "id": "tech_enterprise",
        "name": "Enterprise Technology",
        "characteristics": "Process-oriented, scalability-focused, B2B relationships",
        "rule_weights": {
            "rule_speed_over_perfection": 0.6,
            "rule_compliance_check": 0.6,
            "rule_maximum_delegation": 0.7,
            "rule_data_driven": 0.8,
            "rule_transparency": 0.6,
            "rule_focus_resources": 0.7
        }
    },
    {
        "id": "retail",
        "name": "Retail & E-commerce",
        "characteristics": "Customer-focused, fast-paced, competitive",
        "rule_weights": {
            "rule_speed_over_perfection": 0.8,
            "rule_compliance_check": 0.5,
            "rule_maximum_delegation": 0.7,
            "rule_data_driven": 0.85,
            "rule_transparency": 0.6,
            "rule_focus_resources": 0.8
        }
    }
]

# Expert definitions
EXPERTS = [
    {
        "id": "expert_financial",
        "name": "Financial Analyst",
        "domain": "finance",
        "prompt_template": "Analyze from a financial perspective. Consider ROI, cash flow, budget impact, and financial risk.",
        "keywords": ["budget", "cost", "revenue", "roi", "margin", "financial", "investment", "pricing"]
    },
    {
        "id": "expert_technical",
        "name": "Technical Advisor",
        "domain": "technology",
        "prompt_template": "Provide technical analysis. Consider architecture, scalability, technical debt, and implementation.",
        "keywords": ["technical", "architecture", "code", "system", "engineering", "infrastructure", "api"]
    },
    {
        "id": "expert_strategic",
        "name": "Strategic Thinker",
        "domain": "strategy",
        "prompt_template": "Think strategically. Consider long-term implications, competitive positioning, and market dynamics.",
        "keywords": ["strategy", "vision", "long-term", "competitive", "market", "growth", "roadmap"]
    },
    {
        "id": "expert_people",
        "name": "People & Culture",
        "domain": "hr",
        "prompt_template": "Consider the human element. Think about team dynamics, morale, and organizational culture.",
        "keywords": ["team", "hire", "culture", "morale", "performance", "career", "people", "talent"]
    },
    {
        "id": "expert_legal",
        "name": "Legal & Compliance",
        "domain": "legal",
        "prompt_template": "Assess legal and compliance implications. Flag risks and recommend consultation when uncertain.",
        "keywords": ["legal", "compliance", "contract", "regulation", "liability", "risk", "ip"]
    }
]

# Red flags (hard constraints)
RED_FLAGS = [
    {
        "id": "redflag_compliance_violation",
        "category": "compliance",
        "condition": "Any action that violates regulatory requirements",
        "action": "BLOCK",
        "message": "This may involve compliance violations. Cannot proceed without proper review."
    },
    {
        "id": "redflag_hidden_activity",
        "category": "transparency",
        "condition": "Activities happening without visibility",
        "action": "FLAG",
        "message": "This involves hidden activities. Flagging for discussion."
    },
    {
        "id": "redflag_uncontrolled_risk",
        "category": "risk",
        "condition": "Risks that cannot be managed or controlled",
        "action": "ESCALATE",
        "message": "This involves uncontrollable risks. Recommend in-person discussion."
    },
    {
        "id": "redflag_scattered_resources",
        "category": "strategy",
        "condition": "Spreading resources across too many initiatives",
        "action": "FLAG",
        "message": "This may spread resources too thin. Consider focusing on fewer priorities."
    }
]


async def initialize_logic_graph(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str
):
    """Initialize the logic graph with base data."""
    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password)
    )

    async with driver.session() as session:
        # Create constraints
        logger.info("Creating constraints...")
        await session.run("CREATE CONSTRAINT rule_id IF NOT EXISTS FOR (r:CognitiveRule) REQUIRE r.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT industry_id IF NOT EXISTS FOR (i:Industry) REQUIRE i.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT expert_id IF NOT EXISTS FOR (e:Expert) REQUIRE e.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT redflag_id IF NOT EXISTS FOR (rf:RedFlag) REQUIRE rf.id IS UNIQUE")

        # Load cognitive rules
        logger.info(f"Loading {len(COGNITIVE_RULES)} cognitive rules...")
        for rule in COGNITIVE_RULES:
            await session.run("""
                MERGE (r:CognitiveRule {id: $id})
                SET r.category = $category,
                    r.priority = $priority,
                    r.prompt_injection = $prompt_injection,
                    r.anti_patterns = $anti_patterns,
                    r.activation_keywords = $activation_keywords
            """, **rule)

        # Load industries
        logger.info(f"Loading {len(INDUSTRIES)} industries...")
        for industry in INDUSTRIES:
            await session.run("""
                MERGE (i:Industry {id: $id})
                SET i.name = $name,
                    i.characteristics = $characteristics
            """,
                id=industry["id"],
                name=industry["name"],
                characteristics=industry["characteristics"]
            )

            # Create activation edges
            for rule_id, weight in industry["rule_weights"].items():
                await session.run("""
                    MATCH (i:Industry {id: $industry_id})
                    MATCH (r:CognitiveRule {id: $rule_id})
                    MERGE (i)-[a:ACTIVATES_RULE]->(r)
                    SET a.weight = $weight,
                        a.context = $context
                """,
                    industry_id=industry["id"],
                    rule_id=rule_id,
                    weight=weight,
                    context=f"{industry['name']}_default"
                )

        # Load experts
        logger.info(f"Loading {len(EXPERTS)} experts...")
        for expert in EXPERTS:
            await session.run("""
                MERGE (e:Expert {id: $id})
                SET e.name = $name,
                    e.domain = $domain,
                    e.prompt_template = $prompt_template,
                    e.keywords = $keywords
            """, **expert)

        # Load red flags
        logger.info(f"Loading {len(RED_FLAGS)} red flags...")
        for flag in RED_FLAGS:
            await session.run("""
                MERGE (rf:RedFlag {id: $id})
                SET rf.category = $category,
                    rf.condition = $condition,
                    rf.action = $action,
                    rf.message = $message
            """, **flag)

        logger.info("Logic graph initialization complete!")

    await driver.close()


if __name__ == "__main__":
    import os

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    asyncio.run(initialize_logic_graph(neo4j_uri, neo4j_user, neo4j_password))
```

### 4.5 Phase 2 Deliverables

| Deliverable | Description | Success Criteria |
|-------------|-------------|------------------|
| Logic Graph Schema | Neo4j schema with rules as nodes | All constraints, indexes created |
| `LogicGraphProvider` | Traverses graph to activate rules | Correct rules activated per industry |
| `LogicGraphPromptInjector` | Converts graph results to prompts | Dynamic content matches old hardcoded |
| Industry initialization | Base industries with weights | 5+ industries configured |
| Cognitive rules | Base rules library | 10+ rules loaded |
| Expert definitions | Domain experts | 5 experts configured |
| Admin API | CRUD for rules/weights | Can modify without code deploy |
| Integration tests | Graph traversal tests | All paths tested |

---

## 5. Phase 3: Neural Routing & MoE (Weeks 9-12)

### 5.1 Objective
Replace hardcoded routing patterns with learned classifiers and implement Mixture of Experts.

### 5.2 MoE Gating Network Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MIXTURE OF EXPERTS SYSTEM                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  INPUT FEATURES:                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ exec_dna[512] ⊕ query_emb[512] ⊕ activated_rules_emb[128]      │   │
│  │                                                                 │   │
│  │ Total: 1152-dim input vector                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  GATING NETWORK:                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Linear(1152 → 256) → ReLU → Dropout(0.1)                       │   │
│  │  Linear(256 → 128) → ReLU → Dropout(0.1)                        │   │
│  │  Linear(128 → num_experts) → Softmax                            │   │
│  │                                                                 │   │
│  │  Output: expert_weights = [0.6, 0.2, 0.1, 0.05, 0.05]          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  EXPERT SELECTION:                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Mode: SPARSE (top-k selection)                                 │   │
│  │  k = 2 (select top 2 experts)                                   │   │
│  │                                                                 │   │
│  │  Selected: [Financial (0.6), Technical (0.2)]                   │   │
│  │  Renormalized: [0.75, 0.25]                                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  EXPERT OUTPUTS:                                                        │
│  ┌──────────────────┐  ┌──────────────────┐                           │
│  │ Financial Expert │  │ Technical Expert │                           │
│  │ prompt_template  │  │ prompt_template  │                           │
│  │ weight: 0.75     │  │ weight: 0.25     │                           │
│  └──────────────────┘  └──────────────────┘                           │
│                              ↓                                          │
│  COMBINED OUTPUT:                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Primary perspective: Financial (analyze ROI, costs, margins)     │   │
│  │ Secondary perspective: Technical (consider implementation)       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

