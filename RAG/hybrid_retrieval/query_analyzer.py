"""
Query Analyzer
==============

Analyzes query characteristics for intelligent routing and strategy selection.

Extracts:
- Query type (factual, decision, analysis, navigation)
- Complexity (simple, medium, complex)
- Entities (using enhanced spaCy NER from Blueprint #3.5)
- Keywords and intent
- Recommended retrieval strategy
"""

import re
import logging
from typing import Dict, List, Optional

from .utils import get_logger

logger = get_logger(__name__)


class QueryAnalyzer:
    """
    Analyze query characteristics to determine retrieval strategy
    
    Uses enhanced spaCy NER from Blueprint #3.5 for accurate entity extraction
    """
    
    def __init__(self, use_spacy: bool = True, entity_confidence_threshold: float = 0.4):
        """
        Initialize query analyzer
        
        Args:
            use_spacy: Whether to use spaCy NER (recommended, from Blueprint #3.5)
            entity_confidence_threshold: Min confidence for entity matching (default: 0.4, lowered from 0.5 for broader matching)
        """
        self.use_spacy = use_spacy
        self.entity_extractor = None
        self.entity_confidence_threshold = entity_confidence_threshold
        
        # Lazy load entity extractor (from Blueprint #3.5)
        # IMPORTANT: Use singleton to prevent multiple GLiNER loads (OOM on 6GB GPUs)
        if use_spacy:
            try:
                from graph_context.entity_extractor import get_entity_extractor
                from graph_context.config import NEO4J_CONFIG
                from neo4j import GraphDatabase
                
                # Initialize Neo4j driver for entity matching
                neo4j_driver = GraphDatabase.driver(
                    NEO4J_CONFIG['uri'],
                    auth=(NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
                )
                
                # Use singleton getter to avoid multiple GLiNER loads
                self.entity_extractor = get_entity_extractor(
                    neo4j_driver=neo4j_driver,
                    use_spacy=True,
                    confidence_threshold=entity_confidence_threshold
                )
                logger.info(f"[QueryAnalyzer] Using shared EntityExtractor singleton (confidence threshold: {entity_confidence_threshold})")
            except Exception as e:
                logger.warning(f"[QueryAnalyzer] Could not load spaCy NER: {e}. Using basic extraction.")
                self.entity_extractor = None
        
        logger.info("[QueryAnalyzer] Initialized")
    
    def analyze(self, query: str) -> Dict:
        """
        Extract features and classify query
        
        Args:
            query: User's natural language question
        
        Returns:
            {
                "length": 57,
                "has_entities": true,
                "entities": [{"text": "Akiko", "type": "PERSON", ...}],
                "entity_count": 1,
                "query_type": "decision",
                "complexity": "medium",
                "keywords": ["approve", "discount"],
                "question_word": "Should",
                "intent": "approval_request",
                "strategy_recommendation": "full_hybrid"
            }
        """
        # Extract entities (using enhanced spaCy NER from Blueprint #3.5!)
        entities = self._extract_entities(query)
        
        # Classify query type
        query_type = self._classify_type(query)
        
        # Determine complexity
        complexity = self._assess_complexity(query, entities, query_type)
        
        # Extract keywords
        keywords = self._extract_keywords(query)
        
        # Identify intent
        intent = self._identify_intent(query, query_type, keywords)
        
        # Recommend strategy
        strategy = self._recommend_strategy(query_type, complexity, len(entities) > 0)
        
        analysis = {
            "length": len(query),
            "has_entities": len(entities) > 0,
            "entities": entities,
            "entity_count": len(entities),
            "query_type": query_type,
            "complexity": complexity,
            "keywords": keywords[:10],  # Top 10 keywords
            "question_word": self._extract_question_word(query),
            "intent": intent,
            "strategy_recommendation": strategy
        }
        
        logger.debug(f"[QueryAnalyzer] Analyzed query: type={query_type}, complexity={complexity}, entities={len(entities)}")
        
        return analysis
    
    def _extract_entities(self, query: str) -> List[Dict]:
        """
        Extract entities from query using enhanced spaCy NER
        
        Args:
            query: Query text
        
        Returns:
            List of entity dictionaries with text, type, confidence
        """
        entities = []
        
        if self.entity_extractor:
            try:
                # Use enhanced entity extractor from Blueprint #3.5
                # Note: neo4j_driver can be None for basic entity extraction
                extracted = self.entity_extractor.extract(query)
                
                # Convert to simplified format
                for entity in extracted:
                    entities.append({
                        "text": entity.get("text", ""),
                        "type": entity.get("type", "UNKNOWN"),
                        "confidence": entity.get("confidence", 0.0),
                        "source": entity.get("source", "spacy")
                    })
            except Exception as e:
                logger.warning(f"[QueryAnalyzer] Entity extraction failed: {e}")
        
        return entities
    
    def _classify_type(self, query: str) -> str:
        """
        Classify query type
        
        Types:
        - factual: "What is X?"
        - decision: "Should we Y?"
        - analysis: "Compare A and B"
        - navigation: "Show me Z"
        
        Args:
            query: Query text
        
        Returns:
            Query type string
        """
        lower = query.lower()
        
        # Decision queries
        if any(word in lower for word in ["should", "approve", "recommend", "would you"]):
            return "decision"
        
        # Analysis queries
        elif any(word in lower for word in ["compare", "analyze", "difference", "versus", "vs"]):
            return "analysis"
        
        # Navigation queries
        elif any(word in lower for word in ["show", "find", "list", "get", "display"]):
            return "navigation"
        
        # Factual queries (default)
        else:
            return "factual"
    
    def _assess_complexity(
        self,
        query: str,
        entities: List,
        query_type: str
    ) -> str:
        """
        Assess query complexity
        
        Factors:
        - Length (short/medium/long)
        - Number of entities (0, 1-2, 3+)
        - Query type (factual < decision < analysis)
        - Multi-part questions (contains "and", "but", "or")
        
        Args:
            query: Query text
            entities: Extracted entities
            query_type: Classified query type
        
        Returns:
            "simple" | "medium" | "complex"
        """
        score = 0
        
        # Length factor
        if len(query) < 50:
            score += 0
        elif len(query) < 100:
            score += 1
        else:
            score += 2
        
        # Entity factor
        score += min(len(entities), 2)
        
        # Type factor
        if query_type == "decision":
            score += 1
        elif query_type == "analysis":
            score += 2
        
        # Multi-part factor
        if any(word in query.lower() for word in [" and ", " but ", " or ", "compare"]):
            score += 1
        
        # Classify complexity
        if score <= 1:
            return "simple"
        elif score <= 4:
            return "medium"
        else:
            return "complex"
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract important keywords from query
        
        Args:
            query: Query text
        
        Returns:
            List of keywords
        """
        # Simple stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "what", "how", "why", 
            "when", "where", "who", "which", "this", "that", "these", "those",
            "can", "could", "should", "would", "will", "do", "does", "did"
        }
        
        # Extract words
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Filter stop words and short words
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        
        return keywords
    
    def _extract_question_word(self, query: str) -> Optional[str]:
        """
        Extract question word (What, How, Should, etc.)
        
        Args:
            query: Query text
        
        Returns:
            Question word or None
        """
        words = query.split()
        if words:
            first_word = words[0].lower()
            question_words = ["what", "how", "why", "when", "where", "who", "should", "can", "will", "could", "would"]
            if first_word in question_words:
                return words[0]  # Return with original case
        return None
    
    def _identify_intent(
        self,
        query: str,
        query_type: str,
        keywords: List[str]
    ) -> str:
        """
        Identify user intent

        Intents:
        - approval_request: "Should we approve..."
        - information_lookup: "What is..."
        - precedent_search: "Have we done..."
        - comparison: "Compare X and Y"
        - recommendation: "What would you recommend..."
        - experience_story: "Tell me about a time when..." (asks for decision cases)
        - decision_example: "Give an example of..." (asks for specific decision)

        Args:
            query: Query text
            query_type: Classified query type
            keywords: Extracted keywords

        Returns:
            Intent string
        """
        lower = query.lower()

        # Experience/story queries - HIGHEST PRIORITY (maps to decision cases)
        # These should retrieve decision cases, not general documents
        experience_patterns = [
            "tell me about a time",
            "time you",
            "time when you",
            "have you ever",
            "when did you",
            "share an example",
            "give me an example",
            "example of when",
            "story about",
            "experience with",
            "how did you handle",
            "how did you overcome",
            "what happened when",
        ]
        for pattern in experience_patterns:
            if pattern in lower:
                return "experience_story"

        # Decision example queries - ask for specific decision types
        decision_example_patterns = [
            "pivoted", "pivot",
            "delegated", "delegation",
            "rejected", "turned down",
            "failed", "failure",
            "succeeded", "success",
            "changed direction",
            "crisis", "turnaround",
        ]
        if any(pattern in lower for pattern in decision_example_patterns):
            # Check if it's asking for a story/experience
            if any(word in lower for word in ["tell", "share", "example", "time", "when", "how"]):
                return "decision_example"

        if "approve" in keywords or "should we" in lower:
            return "approval_request"
        elif query_type == "analysis":
            return "comparison"
        elif "recommend" in keywords or "suggest" in keywords:
            return "recommendation"
        elif "have we" in lower or "did we" in lower or "has" in lower:
            return "precedent_search"
        else:
            return "information_lookup"
    
    def _recommend_strategy(
        self,
        query_type: str,
        complexity: str,
        has_entities: bool
    ) -> str:
        """
        Recommend retrieval strategy based on query characteristics
        
        Strategies:
        - "vector_only": Simple factual queries, no entities
        - "vector_graph": Entity queries, graph context helpful
        - "full_hybrid": Complex queries, need memory + precedents
        
        Args:
            query_type: Classified query type
            complexity: Assessed complexity
            has_entities: Whether entities were found
        
        Returns:
            Recommended strategy
        """
        # Simple factual queries without entities → vector only
        if complexity == "simple" and not has_entities and query_type == "factual":
            return "vector_only"
        
        # Entity-based non-decision queries → vector + graph
        elif has_entities and query_type not in ["decision", "analysis"]:
            return "vector_graph"
        
        # Decision/analysis queries → full hybrid (vector + graph + memory)
        else:
            return "full_hybrid"


__all__ = ['QueryAnalyzer']
