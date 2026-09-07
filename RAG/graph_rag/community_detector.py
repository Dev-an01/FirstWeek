"""
Community Detector for GraphRAG Global Search

Detects and manages communities in the Neo4j knowledge graph.
Communities are clusters of related entities that share thematic connections.

Uses Neo4j's Graph Data Science (GDS) library for community detection
with fallback to simple connected component analysis.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from collections import defaultdict
import hashlib
import time

logger = logging.getLogger(__name__)


@dataclass
class Community:
    """Represents a detected community in the graph."""
    id: str
    name: str
    member_count: int
    central_entities: List[str]
    entity_types: List[str]
    summary: Optional[str] = None
    embedding: Optional[List[float]] = None
    keywords: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "member_count": self.member_count,
            "central_entities": self.central_entities,
            "entity_types": self.entity_types,
            "summary": self.summary,
            "keywords": self.keywords
        }


class CommunityDetector:
    """
    Detects and manages communities in the Neo4j knowledge graph.

    Community detection strategies:
    1. GDS-based: Uses Neo4j GDS library (Louvain, Label Propagation)
    2. Semantic clustering: Groups entities by relationship patterns
    3. Fallback: Simple connected components

    Communities are cached and can be pre-computed for faster retrieval.
    """

    def __init__(
        self,
        neo4j_driver,
        embedding_model=None,
        llm_client=None,
        cache_ttl_seconds: int = 3600
    ):
        """
        Initialize community detector.

        Args:
            neo4j_driver: Neo4j driver instance
            embedding_model: Optional embedding model for community embeddings
            llm_client: Optional LLM client for generating community summaries
            cache_ttl_seconds: Cache TTL for community data
        """
        self.driver = neo4j_driver
        self.embedding_model = embedding_model
        self.llm_client = llm_client
        self.cache_ttl = cache_ttl_seconds

        # Community cache
        self._communities: Dict[str, Community] = {}
        self._community_embeddings: Dict[str, List[float]] = {}
        self._last_detection_time: float = 0
        self._gds_available: Optional[bool] = None

        logger.info("CommunityDetector initialized")

    def _check_gds_availability(self) -> bool:
        """Check if Neo4j GDS library is available."""
        if self._gds_available is not None:
            return self._gds_available

        try:
            with self.driver.session() as session:
                result = session.run("RETURN gds.version() AS version")
                version = result.single()
                if version:
                    logger.info(f"Neo4j GDS available: {version['version']}")
                    self._gds_available = True
                    return True
        except Exception as e:
            logger.info(f"Neo4j GDS not available: {e}")
            self._gds_available = False

        return False

    def detect_communities(
        self,
        force_refresh: bool = False,
        algorithm: str = "auto"
    ) -> List[Community]:
        """
        Detect communities in the graph.

        Args:
            force_refresh: Force re-detection even if cache is valid
            algorithm: Detection algorithm ('louvain', 'label_propagation', 'auto')

        Returns:
            List of detected communities
        """
        # Check cache validity
        if not force_refresh and self._communities:
            age = time.time() - self._last_detection_time
            if age < self.cache_ttl:
                logger.info(f"Using cached communities ({len(self._communities)} communities, age={age:.0f}s)")
                return list(self._communities.values())

        logger.info(f"Detecting communities (algorithm={algorithm})")
        start_time = time.time()

        # Choose detection method
        if algorithm == "auto":
            if self._check_gds_availability():
                communities = self._detect_with_gds()
            else:
                communities = self._detect_with_relationships()
        elif algorithm == "louvain" and self._check_gds_availability():
            communities = self._detect_with_louvain()
        elif algorithm == "label_propagation" and self._check_gds_availability():
            communities = self._detect_with_label_propagation()
        else:
            communities = self._detect_with_relationships()

        # Cache results
        self._communities = {c.id: c for c in communities}
        self._last_detection_time = time.time()

        detection_time = (time.time() - start_time) * 1000
        logger.info(f"Detected {len(communities)} communities in {detection_time:.0f}ms")

        return communities

    def _detect_with_gds(self) -> List[Community]:
        """Detect communities using Neo4j GDS Louvain algorithm."""
        return self._detect_with_louvain()

    def _detect_with_louvain(self) -> List[Community]:
        """Use Louvain algorithm for community detection."""
        communities = []

        try:
            with self.driver.session() as session:
                # Create in-memory graph projection
                session.run("""
                    CALL gds.graph.project(
                        'community_graph',
                        ['Executive', 'Department', 'Project', 'Company', 'Policy', 'Decision'],
                        {
                            WORKS_IN: {orientation: 'UNDIRECTED'},
                            MANAGES: {orientation: 'UNDIRECTED'},
                            PARTICIPATES_IN: {orientation: 'UNDIRECTED'},
                            MADE_BY: {orientation: 'UNDIRECTED'},
                            RELATED_TO: {orientation: 'UNDIRECTED'}
                        }
                    )
                """)

                # Run Louvain
                result = session.run("""
                    CALL gds.louvain.stream('community_graph')
                    YIELD nodeId, communityId
                    WITH communityId, collect(gds.util.asNode(nodeId)) AS nodes
                    RETURN communityId,
                           size(nodes) AS memberCount,
                           [n IN nodes | labels(n)[0]] AS types,
                           [n IN nodes | n.name][..5] AS sampleNames
                    ORDER BY memberCount DESC
                """)

                for record in result:
                    comm_id = f"louvain_{record['communityId']}"
                    types = list(set(record['types']))
                    sample_names = [n for n in record['sampleNames'] if n]

                    communities.append(Community(
                        id=comm_id,
                        name=self._generate_community_name(types, sample_names),
                        member_count=record['memberCount'],
                        central_entities=sample_names[:3],
                        entity_types=types,
                        keywords=self._extract_keywords(types, sample_names)
                    ))

                # Drop projection
                session.run("CALL gds.graph.drop('community_graph', false)")

        except Exception as e:
            logger.warning(f"GDS Louvain failed: {e}, falling back to relationship-based")
            return self._detect_with_relationships()

        return communities

    def _detect_with_label_propagation(self) -> List[Community]:
        """Use Label Propagation algorithm for community detection."""
        # Similar to Louvain but uses label propagation
        return self._detect_with_louvain()  # Fallback to Louvain for now

    def _detect_with_relationships(self) -> List[Community]:
        """
        Fallback: Detect communities using relationship-based clustering.
        Groups entities by their relationship patterns.
        """
        communities = []

        try:
            with self.driver.session() as session:
                # Group by department/project clusters
                result = session.run("""
                    MATCH (d:Department)<-[:WORKS_IN]-(e:Executive)
                    WITH d, collect(e) AS executives
                    OPTIONAL MATCH (d)<-[:BELONGS_TO]-(p:Project)
                    WITH d, executives, collect(p) AS projects
                    RETURN d.name AS department,
                           d.id AS deptId,
                           size(executives) AS execCount,
                           size(projects) AS projectCount,
                           [e IN executives | e.name][..3] AS sampleExecs,
                           [p IN projects | p.name][..3] AS sampleProjects
                    ORDER BY execCount DESC
                """)

                for record in result:
                    dept_name = record['department'] or "Unknown Department"
                    dept_id = record['deptId'] or hashlib.md5(dept_name.encode()).hexdigest()[:8]

                    sample_names = (record['sampleExecs'] or []) + (record['sampleProjects'] or [])
                    sample_names = [n for n in sample_names if n]

                    communities.append(Community(
                        id=f"dept_{dept_id}",
                        name=f"{dept_name} Team",
                        member_count=record['execCount'] + record['projectCount'],
                        central_entities=sample_names[:3],
                        entity_types=["Executive", "Project", "Department"],
                        keywords=[dept_name.lower()] + [n.lower() for n in sample_names[:2]]
                    ))

                # Also detect decision/policy clusters
                result = session.run("""
                    MATCH (dec:Decision)-[:MADE_BY]->(e:Executive)
                    WITH e, collect(dec) AS decisions
                    WHERE size(decisions) >= 2
                    RETURN e.name AS executive,
                           e.id AS execId,
                           size(decisions) AS decisionCount,
                           [d IN decisions | d.title][..3] AS sampleDecisions
                    ORDER BY decisionCount DESC
                    LIMIT 10
                """)

                for record in result:
                    exec_name = record['executive'] or "Unknown Executive"
                    exec_id = record['execId'] or hashlib.md5(exec_name.encode()).hexdigest()[:8]

                    sample_decisions = [d for d in (record['sampleDecisions'] or []) if d]

                    if sample_decisions:
                        communities.append(Community(
                            id=f"decisions_{exec_id}",
                            name=f"{exec_name}'s Decision Domain",
                            member_count=record['decisionCount'],
                            central_entities=[exec_name] + sample_decisions[:2],
                            entity_types=["Executive", "Decision"],
                            keywords=[exec_name.lower(), "decision", "policy"]
                        ))

        except Exception as e:
            logger.error(f"Relationship-based community detection failed: {e}")
            # Return empty list rather than failing
            return []

        return communities

    def _generate_community_name(self, types: List[str], sample_names: List[str]) -> str:
        """Generate a descriptive name for a community."""
        if "Department" in types and sample_names:
            return f"{sample_names[0]} Community"
        elif "Executive" in types and sample_names:
            return f"{sample_names[0]}'s Network"
        elif "Project" in types and sample_names:
            return f"{sample_names[0]} Project Group"
        else:
            type_str = "/".join(types[:2]) if types else "Mixed"
            return f"{type_str} Community"

    def _extract_keywords(self, types: List[str], names: List[str]) -> List[str]:
        """Extract keywords from community members."""
        keywords = []

        # Add entity types as keywords
        keywords.extend([t.lower() for t in types])

        # Add name parts as keywords
        for name in names:
            if name:
                # Split on spaces and common separators
                parts = name.lower().replace("-", " ").replace("_", " ").split()
                keywords.extend([p for p in parts if len(p) > 2])

        # Deduplicate and limit
        return list(dict.fromkeys(keywords))[:10]

    def get_community(self, community_id: str) -> Optional[Community]:
        """Get a community by ID."""
        if not self._communities:
            self.detect_communities()
        return self._communities.get(community_id)

    def get_all_communities(self) -> List[Community]:
        """Get all detected communities."""
        if not self._communities:
            self.detect_communities()
        return list(self._communities.values())

    def find_communities_by_keyword(
        self,
        keywords: List[str],
        min_match_score: float = 0.3
    ) -> List[tuple]:
        """
        Find communities matching keywords.

        Args:
            keywords: List of keywords to match
            min_match_score: Minimum matching score (0-1)

        Returns:
            List of (community, score) tuples, sorted by score descending
        """
        if not self._communities:
            self.detect_communities()

        keywords_lower = set(k.lower() for k in keywords)
        results = []

        for community in self._communities.values():
            if not community.keywords:
                continue

            community_keywords = set(community.keywords)

            # Calculate Jaccard-like overlap score
            intersection = len(keywords_lower & community_keywords)
            union = len(keywords_lower | community_keywords)

            if union > 0:
                score = intersection / union
                if score >= min_match_score:
                    results.append((community, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    async def generate_community_summary(
        self,
        community: Community,
        force_regenerate: bool = False
    ) -> str:
        """
        Generate or retrieve summary for a community.

        Args:
            community: The community to summarize
            force_regenerate: Force regeneration even if summary exists

        Returns:
            Community summary string
        """
        if community.summary and not force_regenerate:
            return community.summary

        if not self.llm_client:
            # Generate basic summary without LLM
            return self._generate_basic_summary(community)

        # Use LLM to generate summary
        try:
            prompt = f"""Generate a brief 2-3 sentence summary for this organizational community:

Community Name: {community.name}
Member Count: {community.member_count}
Entity Types: {', '.join(community.entity_types)}
Central Entities: {', '.join(community.central_entities)}
Keywords: {', '.join(community.keywords or [])}

The summary should describe the community's focus, key members, and role in the organization."""

            messages = [
                {"role": "system", "content": "You are an organizational analyst. Be concise and factual."},
                {"role": "user", "content": prompt}
            ]

            response = self.llm_client.generate(messages, temperature=0.3, max_tokens=150)
            summary = response.content.strip()

            # Cache the summary
            community.summary = summary
            if community.id in self._communities:
                self._communities[community.id].summary = summary

            return summary

        except Exception as e:
            logger.warning(f"LLM summary generation failed: {e}")
            return self._generate_basic_summary(community)

    def _generate_basic_summary(self, community: Community) -> str:
        """Generate a basic summary without LLM."""
        types_str = " and ".join(community.entity_types[:2])
        entities_str = ", ".join(community.central_entities[:3])

        return (
            f"{community.name} is a community of {community.member_count} "
            f"{types_str} entities. Key members include {entities_str}."
        )

    def compute_community_embeddings(self) -> Dict[str, List[float]]:
        """
        Compute embeddings for all communities.

        Returns:
            Dict mapping community_id to embedding vector
        """
        if not self.embedding_model:
            logger.warning("No embedding model available for community embeddings")
            return {}

        if not self._communities:
            self.detect_communities()

        logger.info(f"Computing embeddings for {len(self._communities)} communities")

        for community in self._communities.values():
            # Build text representation
            text_parts = [
                community.name,
                " ".join(community.central_entities),
                " ".join(community.keywords or []),
                community.summary or ""
            ]
            text = " ".join(text_parts)

            # Compute embedding
            try:
                embedding = self.embedding_model.encode(text, show_progress_bar=False)
                self._community_embeddings[community.id] = embedding.tolist()
                community.embedding = embedding.tolist()
            except Exception as e:
                logger.warning(f"Failed to compute embedding for {community.id}: {e}")

        logger.info(f"Computed {len(self._community_embeddings)} community embeddings")
        return self._community_embeddings

    def get_community_embedding(self, community_id: str) -> Optional[List[float]]:
        """Get embedding for a specific community."""
        return self._community_embeddings.get(community_id)
