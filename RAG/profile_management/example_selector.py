"""
Example Selector

Selects best few-shot examples from bootstrap and learned examples.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg
import numpy as np
import asyncpg
from asyncpg import Connection

from .dynamic_examples import DynamicExamples

logger = logging.getLogger(__name__)


class ExampleSelector:
    """
    Selects best few-shot examples for prompt generation.

    Combines bootstrap examples (from JSON) with learned examples (from DB).
    Implements intelligent selection based on context, quality, and diversity.
    """

    def __init__(
        self,
        max_bootstrap: int = 3,
        max_learned: int = 2,
        db_pool: Optional[asyncpg.Pool] = None,
        diversity_factor: float = 0.3,
        recency_weight: float = 0.25,
        quality_weight: float = 0.4,
        usage_weight: float = 0.05
    ):
        """
        Initialize ExampleSelector.

        Args:
            max_bootstrap: Maximum bootstrap examples to include
            max_learned: Maximum learned examples to include
            db_pool: PostgreSQL connection pool (optional, needed for learned examples)
            diversity_factor: How much to prioritize diversity (0-1)
            recency_weight: Weight for recency in scoring
            quality_weight: Weight for quality in scoring
            usage_weight: Weight for usage frequency in scoring
        """
        self.max_bootstrap = max_bootstrap
        self.max_learned = max_learned
        self.db_pool = db_pool
        self.diversity_factor = diversity_factor
        self.recency_weight = recency_weight
        self.quality_weight = quality_weight
        self.usage_weight = usage_weight

        # Initialize dynamic examples manager only if db_pool provided
        self.dynamic_examples = DynamicExamples(db_pool) if db_pool else None
    
    def select_bootstrap_examples(
        self, 
        profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Select bootstrap examples from profile JSON.
        
        Args:
            profile: Executive profile dict
            
        Returns:
            List of selected examples
        """
        communication_examples = profile.get('communication_examples', [])
        
        if not communication_examples:
            logger.warning(
                f"No communication examples found for {profile.get('name_english')}"
            )
            return []
        
        # Take first N examples (they're curated in order of quality)
        selected = communication_examples[:self.max_bootstrap]
        
        logger.debug(
            f"Selected {len(selected)} bootstrap examples for "
            f"{profile.get('name_english')}"
        )
        
        return selected
    
    async def select_learned_examples(
        self,
        executive_id: str,
        query: Optional[str] = None,
        query_type: Optional[str] = None,
        context_sources: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Select learned examples from communication_examples table.
        
        Implements intelligent selection based on:
        - Query similarity (if query provided)
        - Query type matching
        - Quality scores
        - Usage frequency
        - Recency
        - Diversity
        
        Args:
            executive_id: Executive profile ID
            query: Current query for similarity matching
            query_type: Optional query type filter
            context_sources: Sources used in current query
            
        Returns:
            List of learned examples
        """
        # Can't get learned examples without db_pool
        if not self.dynamic_examples:
            logger.debug("No db_pool configured - skipping learned examples")
            return []

        try:
            # Get base examples using dynamic examples manager
            examples = await self.dynamic_examples.get_examples_for_prompt(
                executive_id=executive_id,
                query_type=query_type,
                max_examples=self.max_learned * 2,  # Get more to rank
                include_bootstrap=False,
                diversity_factor=self.diversity_factor
            )
            
            if not examples:
                logger.debug(f"No learned examples found for {executive_id}")
                return []
            
            # If query provided, rank by similarity
            if query:
                examples = await self._rank_by_query_similarity(
                    examples, query, executive_id
                )
            
            # Apply context relevance boost
            if context_sources:
                examples = await self._boost_context_relevant(
                    examples, context_sources
                )
            
            # Calculate final scores
            examples = await self._calculate_final_scores(examples)
            
            # Select top examples
            selected = examples[:self.max_learned]
            
            logger.debug(
                f"Selected {len(selected)} learned examples for {executive_id}"
            )
            
            return selected
            
        except Exception as e:
            logger.error(f"Failed to select learned examples: {e}")
            return []
    
    async def select_context_relevant_examples(
        self,
        executive_id: str,
        query: str,
        context_sources: List[Dict[str, Any]],
        max_examples: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Select examples specifically relevant to current context.
        
        Args:
            executive_id: Executive profile ID
            query: Current query
            context_sources: Sources used in current query
            max_examples: Maximum examples to return
            
        Returns:
            List of context-relevant examples
        """
        # Can't query without db_pool
        if not self.db_pool:
            logger.debug("No db_pool configured - skipping context-relevant examples")
            return []

        try:
            # Extract entities and topics from context
            context_entities = self._extract_context_entities(context_sources)
            
            if not context_entities:
                return []
            
            # Get examples that mention similar entities
            async with self.db_pool.acquire() as conn:
                relevant_examples = await conn.fetch(
                    """
                    SELECT DISTINCT ce.*
                    FROM communication_examples ce
                    WHERE ce.executive_id = $1
                      AND ce.is_active = true
                      AND ce.quality_score >= 0.3
                      AND (
                          -- Query contains context entities
                          SELECT COUNT(*) FROM unnest(string_to_array(lower(ce.query))) as word
                          WHERE word = ANY($2)
                          LIMIT 1
                      )
                    ORDER BY ce.quality_score DESC, ce.timestamp DESC
                    LIMIT $3
                    """,
                    executive_id,
                    [entity.lower() for entity in context_entities],
                    max_examples
                )
            
            # Convert to dictionaries
            result = []
            for row in relevant_examples:
                result.append({
                    'id': str(row['id']),
                    'query': row['query'],
                    'response': row['response'],
                    'quality_score': float(row['quality_score']),
                    'usage_count': row['usage_count'],
                    'success_rate': float(row['success_rate']),
                    'example_type': row['example_type'],
                    'query_type': row['query_type'],
                    'is_bootstrap': row['is_bootstrap'],
                    'timestamp': row['timestamp'].isoformat(),
                    'last_used': row['last_used'].isoformat() if row['last_used'] else None,
                    'relevance_score': 1.0  # Will be calculated
                })
            
            # Calculate relevance scores
            result = await self._calculate_relevance_scores(
                result, query, context_entities
            )
            
            # Sort by relevance and quality
            result.sort(
                key=lambda x: (x['relevance_score'] * 0.6 + x['quality_score'] * 0.4),
                reverse=True
            )
            
            logger.debug(
                f"Found {len(result)} context-relevant examples for {executive_id}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to select context-relevant examples: {e}")
            return []
    
    async def _rank_by_query_similarity(
        self,
        examples: List[Dict[str, Any]],
        query: str,
        executive_id: str
    ) -> List[Dict[str, Any]]:
        """
        Rank examples by similarity to current query.
        
        Args:
            examples: List of example dictionaries
            query: Current query
            executive_id: Executive ID
            
        Returns:
            Examples ranked by similarity
        """
        try:
            # Get query embedding
            query_embedding = await self._get_query_embedding(query)
            
            if not query_embedding:
                return examples
            
            # Get example embeddings
            example_embeddings = await self._get_example_embeddings(
                [ex['id'] for ex in examples]
            )
            
            # Calculate cosine similarity
            for example in examples:
                example_id = example['id']
                if example_id in example_embeddings:
                    example_embedding = example_embeddings[example_id]
                    similarity = self._cosine_similarity(
                        query_embedding, example_embedding
                    )
                    example['query_similarity'] = similarity
                else:
                    example['query_similarity'] = 0.0
            
            # Sort by similarity
            examples.sort(
                key=lambda x: x['query_similarity'],
                reverse=True
            )
            
            return examples
            
        except Exception as e:
            logger.error(f"Failed to rank by query similarity: {e}")
            return examples
    
    async def _boost_context_relevant(
        self,
        examples: List[Dict[str, Any]],
        context_sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Boost examples that are relevant to current context.
        
        Args:
            examples: List of example dictionaries
            context_sources: Current context sources
            
        Returns:
            Examples with context relevance boost applied
        """
        try:
            # Extract document types and entities from context
            context_doc_types = set()
            context_entities = set()
            
            for source in context_sources:
                if 'type' in source:
                    context_doc_types.add(source['type'].lower())
                if 'entities' in source:
                    context_entities.update(
                        [e.lower() for e in source['entities']]
                    )
            
            # Boost examples that mention similar document types or entities
            for example in examples:
                boost = 1.0
                
                # Check document type relevance
                example_text = (example['query'] + ' ' + example['response']).lower()
                for doc_type in context_doc_types:
                    if doc_type in example_text:
                        boost += 0.1
                
                # Check entity relevance
                for entity in context_entities:
                    if entity in example_text:
                        boost += 0.05
                
                example['context_boost'] = boost
            
            return examples
            
        except Exception as e:
            logger.error(f"Failed to boost context relevance: {e}")
            return examples
    
    async def _calculate_final_scores(
        self,
        examples: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate final scores for examples.
        
        Args:
            examples: List of example dictionaries
            
        Returns:
            Examples with final scores calculated
        """
        try:
            now = datetime.utcnow()
            
            for example in examples:
                # Base score from quality and success
                base_score = (
                    example['quality_score'] * self.quality_weight +
                    example.get('success_rate', 0.5) * 0.3
                )
                
                # Recency score (newer is better)
                example_time = example['timestamp']
                if isinstance(example_time, str):
                    example_time = datetime.fromisoformat(example_time)
                
                days_ago = (now - example_time).days
                recency_score = max(0, 1 - (days_ago / 90))  # Decay over 90 days
                recency_score *= self.recency_weight
                
                # Usage score (more used is better)
                usage_score = min(1.0, example.get('usage_count', 0) / 10.0)
                usage_score *= self.usage_weight
                
                # Query similarity score (if available)
                similarity_score = example.get('query_similarity', 0) * 0.2
                
                # Context boost (if available)
                context_boost = example.get('context_boost', 1.0)
                
                # Calculate final score
                final_score = (
                    base_score + recency_score + usage_score + similarity_score
                ) * context_boost
                
                example['final_score'] = final_score
            
            # Sort by final score
            examples.sort(
                key=lambda x: x['final_score'],
                reverse=True
            )
            
            return examples
            
        except Exception as e:
            logger.error(f"Failed to calculate final scores: {e}")
            return examples
    
    async def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Get embedding for query.
        
        Args:
            query: Query text
            
        Returns:
            Query embedding vector or None
        """
        # This would integrate with the embedding service
        # For now, return None to skip similarity ranking
        return None
    
    async def _get_example_embeddings(
        self,
        example_ids: List[str]
    ) -> Dict[str, List[float]]:
        """
        Get embeddings for examples.
        
        Args:
            example_ids: List of example IDs
            
        Returns:
            Dictionary mapping example IDs to embeddings
        """
        # This would integrate with the embedding service
        # For now, return empty dict
        return {}
    
    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity (0-1)
        """
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
            
        except Exception:
            return 0.0
    
    def _extract_context_entities(
        self,
        context_sources: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Extract entities from context sources.
        
        Args:
            context_sources: List of context sources
            
        Returns:
            List of entity names
        """
        entities = []
        
        for source in context_sources:
            if 'entities' in source:
                entities.extend(source['entities'])
        
        return entities
    
    async def _calculate_relevance_scores(
        self,
        examples: List[Dict[str, Any]],
        query: str,
        context_entities: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Calculate relevance scores for examples.
        
        Args:
            examples: List of example dictionaries
            query: Current query
            context_entities: Context entities
            
        Returns:
            Examples with relevance scores
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        for example in examples:
            example_text = (
                example['query'] + ' ' + example['response']
            ).lower()
            example_words = set(example_text.split())
            
            # Calculate Jaccard similarity
            intersection = query_words.intersection(example_words)
            union = query_words.union(example_words)
            jaccard = len(intersection) / len(union) if union else 0
            
            # Check entity overlap
            entity_overlap = 0
            for entity in context_entities:
                if entity.lower() in example_text:
                    entity_overlap += 1
            
            entity_score = entity_overlap / len(context_entities) if context_entities else 0
            
            # Combined relevance score
            relevance = (jaccard * 0.7) + (entity_score * 0.3)
            example['relevance_score'] = relevance
        
        return examples
    
    def format_example_for_prompt(
        self, 
        example: Dict[str, Any]
    ) -> str:
        """
        Format an example for inclusion in system prompt.
        
        Args:
            example: Example dict (from communication_examples or DB)
            
        Returns:
            Formatted example string
        """
        example_type = example.get('type', 'unknown')
        
        if example_type == 'email':
            return self._format_email_example(example)
        elif example_type == 'slack' or example_type == 'slack_dm':
            return self._format_slack_example(example)
        else:
            return self._format_generic_example(example)
    
    def _format_email_example(self, example: Dict[str, Any]) -> str:
        """Format email example with persona highlights."""
        subject = example.get('subject', 'No subject')
        context = example.get('context', '')
        text = example.get('full_text', '')

        # Extract persona elements from the example
        persona_highlights = self._extract_persona_highlights(text)

        formatted = f"""
Example (Email - {subject}):
Context: {context}

Response:
{text}

✨ PERSONA ELEMENTS TO NOTICE (use these in YOUR responses):
  • Emojis used: {', '.join(persona_highlights['emojis']) if persona_highlights['emojis'] else 'None'}
  • Signature phrases: {', '.join([f'"{p}"' for p in persona_highlights['phrases']]) if persona_highlights['phrases'] else 'None'}
  • Tone: {persona_highlights['tone_markers']}
  • First-person: {persona_highlights['first_person_examples']}
""".strip()

        return formatted
    
    def _format_slack_example(self, example: Dict[str, Any]) -> str:
        """Format Slack message example with persona highlights."""
        context = example.get('context', '')
        text = example.get('full_text', '')

        # Extract persona elements from the example
        persona_highlights = self._extract_persona_highlights(text)

        formatted = f"""
Example (Slack):
Context: {context}

Response:
{text}

✨ PERSONA ELEMENTS TO NOTICE (use these in YOUR responses):
  • Emojis used: {', '.join(persona_highlights['emojis']) if persona_highlights['emojis'] else 'None'}
  • Signature phrases: {', '.join([f'"{p}"' for p in persona_highlights['phrases']]) if persona_highlights['phrases'] else 'None'}
  • Tone: {persona_highlights['tone_markers']}
  • First-person: {persona_highlights['first_person_examples']}
""".strip()

        return formatted
    
    def _format_generic_example(self, example: Dict[str, Any]) -> str:
        """Format generic example with persona highlights."""
        context = example.get('context', '')
        text = example.get('full_text', example.get('text', ''))

        # Extract persona elements from the example
        persona_highlights = self._extract_persona_highlights(text)

        formatted = f"""
Example:
Context: {context}

Response:
{text}

✨ PERSONA ELEMENTS TO NOTICE (use these in YOUR responses):
  • Emojis used: {', '.join(persona_highlights['emojis']) if persona_highlights['emojis'] else 'None'}
  • Signature phrases: {', '.join([f'"{p}"' for p in persona_highlights['phrases']]) if persona_highlights['phrases'] else 'None'}
  • Tone: {persona_highlights['tone_markers']}
  • First-person: {persona_highlights['first_person_examples']}
""".strip()

        return formatted

    def _extract_persona_highlights(self, text: str) -> Dict[str, Any]:
        """
        Extract persona elements from example text.

        Args:
            text: Example response text

        Returns:
            Dict with extracted persona elements
        """
        import re

        # Extract emojis (Unicode emoji pattern)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        emojis = emoji_pattern.findall(text)
        unique_emojis = list(dict.fromkeys(emojis))[:8]  # First 8 unique

        # Common signature phrases to look for
        common_phrases = [
            "Real talk:", "Quick thought:", "Here's the thing", "Let's ship it",
            "Tech debt", "That won't scale", "Shipping beats perfect",
            "Let's level up", "Data doesn't lie", "Quick win", "This is huge",
            "The numbers show", "ROI analysis", "Budget allocation",
            "Our team", "Collaboration", "Transparent communication",
            "Bottom line", "Looking at the financials"
        ]

        phrases_found = []
        for phrase in common_phrases:
            if phrase.lower() in text.lower():
                phrases_found.append(phrase)

        # Tone markers (casual vs formal indicators)
        tone_markers = []
        if any(word in text.lower() for word in ["lol", "btw", "tbh", "fyi"]):
            tone_markers.append("Very casual")
        if text.count("!") > 2:
            tone_markers.append("Enthusiastic")
        if text.count("...") > 1:
            tone_markers.append("Conversational")
        if len([s for s in text.split('.') if s.strip() and len(s.split()) < 5]) > 2:
            tone_markers.append("Short, punchy sentences")

        tone = ", ".join(tone_markers) if tone_markers else "Professional and direct"

        # Find first-person examples
        first_person_pattern = re.compile(r'\b(I|my|we|our)\s+\w+', re.IGNORECASE)
        first_person_matches = first_person_pattern.findall(text)[:3]  # First 3
        first_person_examples = ', '.join([' '.join(match) for match in first_person_matches]) if first_person_matches else "Multiple uses"

        return {
            'emojis': unique_emojis,
            'phrases': phrases_found,
            'tone_markers': tone,
            'first_person_examples': first_person_examples
        }
