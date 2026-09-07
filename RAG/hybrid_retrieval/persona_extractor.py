"""
PersonaExtractor - Extract persona-rich snippets with style-aware ranking

This module extracts snippets that contain the executive's authentic voice,
using multi-factor scoring based on:
1. First-person language ("I believe", "My take")
2. Lexicon matching (executive's unique phrases)
3. Syntax patterns (sentence structure)
4. Punctuation markers (emoji, em-dash)

Usage:
    extractor = PersonaExtractor(voiceprint_cache)
    snippets = extractor.extract(
        results=search_results,
        executive_id="exec_003_test",
        top_k=5
    )
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging
from fuzzywuzzy import fuzz
from profile_management.voiceprint_cache import VoiceprintCache, Voiceprint

logger = logging.getLogger(__name__)


@dataclass
class PersonaSnippet:
    """A snippet with high persona score"""
    text: str
    score: float
    context_before: str
    context_after: str
    source_doc: str
    source_section: str
    score_breakdown: Dict[str, float]
    matched_phrases: List[str]


class PersonaExtractor:
    """Extract persona-rich snippets from search results"""

    # First-person pronouns and patterns
    FIRST_PERSON_PRONOUNS = {
        "I", "I'm", "I've", "I'd", "my", "me", "mine", "myself",
        "we", "we're", "we've", "we'd", "our", "us", "ours", "ourselves"
    }

    FIRST_PERSON_PATTERNS = [
        r'\bI\s+(believe|think|feel|see|know|want|need|recommend|suggest|propose)\b',
        r'\bmy\s+(take|view|opinion|perspective|concern|recommendation)\b',
        r'\bI\'m\s+(concerned|excited|worried|confident|convinced)\b',
        r'\bIn\s+my\s+(experience|view|opinion)\b',
    ]

    # Third-person narration patterns (to penalize)
    THIRD_PERSON_PATTERNS = [
        r'\b(he|she|they)\s+said\b',
        r'\baccording\s+to\s+\w+\b',
        r'\b\w+\s+stated\s+that\b',
        r'\b\w+\s+mentioned\s+that\b',
    ]

    # Scoring weights
    WEIGHTS = {
        "first_person": 0.4,
        "lexicon_match": 0.3,
        "syntax": 0.2,
        "punctuation": 0.1
    }

    # Boost values
    BOOST_FIRST_PERSON_START = 1.0
    BOOST_NUMBERS_WITH_FIRST_PERSON = 0.5
    PENALTY_THIRD_PERSON = 0.5

    # Fuzzy matching threshold
    FUZZY_THRESHOLD = 85  # 85% similarity

    def __init__(self, voiceprint_cache: VoiceprintCache):
        """
        Initialize PersonaExtractor

        Args:
            voiceprint_cache: Cache for loading executive voiceprints
        """
        self.voiceprint_cache = voiceprint_cache
        self.first_person_regex = [re.compile(p, re.IGNORECASE) for p in self.FIRST_PERSON_PATTERNS]
        self.third_person_regex = [re.compile(p, re.IGNORECASE) for p in self.THIRD_PERSON_PATTERNS]

    def extract(
        self,
        results: List[Dict],
        executive_id: str,
        top_k: int = 5
    ) -> List[PersonaSnippet]:
        """
        Extract top persona-rich snippets from search results

        Args:
            results: Search results from retrieval (sections or documents)
            executive_id: Executive identifier for voiceprint lookup
            top_k: Number of snippets to extract (default: 5)

        Returns:
            List of PersonaSnippet objects, ranked by persona score
        """
        # Load voiceprint
        voiceprint = self.voiceprint_cache.get(executive_id)
        if not voiceprint:
            logger.warning(f"[PersonaExtractor] No voiceprint found for {executive_id}")
            return []

        logger.info(f"[PersonaExtractor] Extracting persona snippets for {voiceprint.name}")
        logger.info(f"[PersonaExtractor] Lexicon size: {len(voiceprint.lexicon)} phrases")

        # Score all results
        scored_snippets = []
        for result in results:
            snippets = self._extract_from_result(result, voiceprint)
            scored_snippets.extend(snippets)

        # Sort by score and return top K
        scored_snippets.sort(key=lambda s: s.score, reverse=True)
        top_snippets = scored_snippets[:top_k]

        logger.info(f"[PersonaExtractor] Extracted {len(top_snippets)} snippets from {len(results)} results")
        if top_snippets:
            logger.info(f"[PersonaExtractor] Top score: {top_snippets[0].score:.3f}")
            logger.info(f"[PersonaExtractor] Avg score: {sum(s.score for s in top_snippets) / len(top_snippets):.3f}")

        return top_snippets

    def _extract_from_result(
        self,
        result: Dict,
        voiceprint: Voiceprint
    ) -> List[PersonaSnippet]:
        """
        Extract persona snippets from a single result

        Args:
            result: Single search result
            voiceprint: Executive voiceprint

        Returns:
            List of PersonaSnippet objects from this result
        """
        text = result.get("content", "")
        if not text:
            return []

        # Split into sentences
        sentences = self._split_into_sentences(text)

        # Score each sentence
        snippets = []
        for i, sentence in enumerate(sentences):
            score, breakdown, matched_phrases = self._score_sentence(sentence, voiceprint)

            # Only keep sentences with score > 0.1
            if score > 0.1:
                # Get context (2 sentences before and after)
                context_before = " ".join(sentences[max(0, i-2):i])
                context_after = " ".join(sentences[i+1:min(len(sentences), i+3)])

                snippet = PersonaSnippet(
                    text=sentence,
                    score=score,
                    context_before=context_before,
                    context_after=context_after,
                    source_doc=result.get("document_name", "unknown"),
                    source_section=result.get("section_title", ""),
                    score_breakdown=breakdown,
                    matched_phrases=matched_phrases
                )
                snippets.append(snippet)

        return snippets

    def _score_sentence(
        self,
        sentence: str,
        voiceprint: Voiceprint
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """
        Calculate persona score for a sentence

        Args:
            sentence: Sentence to score
            voiceprint: Executive voiceprint

        Returns:
            Tuple of (total_score, score_breakdown, matched_phrases)
        """
        # Component scores
        first_person_score = self._score_first_person(sentence)
        lexicon_score, matched_phrases = self._score_lexicon_match(sentence, voiceprint.lexicon)
        syntax_score = self._score_syntax(sentence)
        punctuation_score = self._score_punctuation(sentence)

        # Weighted sum
        base_score = (
            self.WEIGHTS["first_person"] * first_person_score +
            self.WEIGHTS["lexicon_match"] * lexicon_score +
            self.WEIGHTS["syntax"] * syntax_score +
            self.WEIGHTS["punctuation"] * punctuation_score
        )

        # Apply boosts and penalties
        boost = 0.0

        # Boost: Starts with first-person
        if self._starts_with_first_person(sentence):
            boost += self.BOOST_FIRST_PERSON_START

        # Boost: Contains numbers with first-person
        if self._has_numbers_with_first_person(sentence):
            boost += self.BOOST_NUMBERS_WITH_FIRST_PERSON

        # Penalty: Third-person narration
        if self._is_third_person_narration(sentence):
            boost -= self.PENALTY_THIRD_PERSON

        total_score = base_score + boost

        breakdown = {
            "first_person": first_person_score,
            "lexicon_match": lexicon_score,
            "syntax": syntax_score,
            "punctuation": punctuation_score,
            "boost": boost,
            "total": total_score
        }

        return total_score, breakdown, matched_phrases

    def _score_first_person(self, text: str) -> float:
        """
        Score based on first-person language

        Args:
            text: Text to analyze

        Returns:
            Score between 0.0 and 1.0
        """
        score = 0.0

        # Check for first-person pronouns
        words = text.split()
        first_person_count = sum(1 for word in words if word in self.FIRST_PERSON_PRONOUNS)

        # Normalize by word count
        if len(words) > 0:
            score += min(1.0, first_person_count / len(words) * 10)  # Scale up

        # Check for first-person patterns
        pattern_matches = sum(1 for regex in self.first_person_regex if regex.search(text))
        score += min(0.5, pattern_matches * 0.2)

        return min(1.0, score)

    def _score_lexicon_match(
        self,
        text: str,
        lexicon: List[str]
    ) -> Tuple[float, List[str]]:
        """
        Score based on lexicon phrase matching (exact + fuzzy)

        Args:
            text: Text to analyze
            lexicon: List of executive's unique phrases

        Returns:
            Tuple of (score, matched_phrases)
        """
        text_lower = text.lower()
        matched_phrases = []

        # Exact matching
        exact_matches = 0
        for phrase in lexicon:
            if phrase.lower() in text_lower:
                exact_matches += 1
                matched_phrases.append(phrase)

        # Fuzzy matching for phrases not exactly matched
        fuzzy_matches = 0
        for phrase in lexicon:
            if phrase.lower() not in text_lower:
                # Use partial ratio for substring matching
                similarity = fuzz.partial_ratio(phrase.lower(), text_lower)
                if similarity >= self.FUZZY_THRESHOLD:
                    fuzzy_matches += 1
                    matched_phrases.append(f"{phrase} (fuzzy)")

        # Score: exact matches weighted higher than fuzzy
        total_matches = exact_matches + (fuzzy_matches * 0.5)

        # Normalize by lexicon size
        score = min(1.0, total_matches / max(1, len(lexicon)) * 10)  # Scale up

        return score, matched_phrases

    def _score_syntax(self, text: str) -> float:
        """
        Score based on sentence syntax patterns

        Args:
            text: Text to analyze

        Returns:
            Score between 0.0 and 1.0
        """
        score = 0.0

        # Short, punchy sentences (< 20 words)
        word_count = len(text.split())
        if word_count < 20:
            score += 0.3

        # Fragment detection (no subject-verb)
        # Simple heuristic: starts with verb or adverb
        if re.match(r'^(Let|Quick|Real|Bottom|Here|After|Looking|Based)\s+', text, re.IGNORECASE):
            score += 0.2

        # Question form (engages reader)
        if text.strip().endswith('?'):
            score += 0.2

        # Command/imperative form
        if re.match(r'^(Let\'s|We should|I recommend|You should)\s+', text, re.IGNORECASE):
            score += 0.3

        return min(1.0, score)

    def _score_punctuation(self, text: str) -> float:
        """
        Score based on punctuation markers (emoji, em-dash, etc.)

        Args:
            text: Text to analyze

        Returns:
            Score between 0.0 and 1.0
        """
        score = 0.0

        # Emoji detection
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "]+",
            flags=re.UNICODE
        )
        if emoji_pattern.search(text):
            score += 0.5

        # Em-dash usage
        if '—' in text or ' - ' in text:
            score += 0.2

        # Exclamation points
        if text.count('!') > 0:
            score += 0.2

        # Multiple punctuation (e.g., "...")
        if '...' in text:
            score += 0.1

        return min(1.0, score)

    def _starts_with_first_person(self, text: str) -> bool:
        """Check if sentence starts with first-person pronoun"""
        return bool(re.match(r'^\s*(I|My|We|Our)\s+', text, re.IGNORECASE))

    def _has_numbers_with_first_person(self, text: str) -> bool:
        """Check if sentence contains numbers AND first-person language"""
        has_numbers = bool(re.search(r'[¥$€£]\s*[\d,]+|\d+%|\d+\s*(months|years|days)', text))
        has_first_person = any(pronoun in text.split() for pronoun in self.FIRST_PERSON_PRONOUNS)
        return has_numbers and has_first_person

    def _is_third_person_narration(self, text: str) -> bool:
        """Check if sentence is third-person narration (e.g., 'Yuki said...')"""
        return any(regex.search(text) for regex in self.third_person_regex)

    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitter (handles basic cases)
        # Split on . ! ? followed by space and capital letter
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)

        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences


# Test function
if __name__ == "__main__":
    from profile_management.voiceprint_cache import VoiceprintCache

    logging.basicConfig(level=logging.INFO)

    # Initialize
    cache = VoiceprintCache()
    extractor = PersonaExtractor(cache)

    # Test with sample result
    test_result = {
        "content": """
        Quick thought: I'm concerned about the technical debt we're accumulating.
        Looking at the numbers, our velocity has dropped 15% over the last quarter.
        The team mentioned they're spending too much time on bug fixes.
        I committed to ¥8M for the refactoring initiative.
        Bottom line: We need to ship it and iterate, but quality matters.
        Let me nerd out for a sec - our architecture won't scale past 10k users.
        """,
        "document_name": "engineering_update.txt",
        "section_title": "Q3 Technical Review"
    }

    # Extract snippets for Yuki
    snippets = extractor.extract(
        results=[test_result],
        executive_id="exec_003_test",
        top_k=3
    )

    print("\n=== Extracted Persona Snippets ===\n")
    for i, snippet in enumerate(snippets, 1):
        print(f"Snippet {i} (score: {snippet.score:.3f}):")
        print(f"  Text: {snippet.text}")
        print(f"  Matched phrases: {snippet.matched_phrases}")
        print(f"  Breakdown: {snippet.score_breakdown}")
        print()
