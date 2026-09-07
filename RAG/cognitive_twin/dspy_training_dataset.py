"""
DSPy Training Dataset Generator

Generates training examples from:
1. Actual test questions (test_data/test_questions/questions.json)
2. Decision cases from PostgreSQL database
3. Executive profiles from PostgreSQL database

Training examples include:
- Query: Real question from test data or decision case
- Profile context: Executive's communication style, thinking patterns
- Expected response: From test data or derived from decision case
- Quality score: Based on confidence and outcome

Usage:
    from cognitive_twin.dspy_training_dataset import DSPyTrainingDatasetGenerator

    generator = DSPyTrainingDatasetGenerator()
    dataset = await generator.generate_dataset()

    # Export to JSON/CSV
    generator.export_to_json(dataset, "training_data.json")
"""

import logging
import json
import asyncio
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import asyncpg for database access
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger.warning("asyncpg not available - database sources disabled")


@dataclass
class TrainingExample:
    """A single training example for DSPy optimization."""
    # Core fields for DSPy
    query: str
    profile_id: str
    expected_response: str

    # Executive context
    executive_name: str
    executive_title: str
    executive_style: str  # Communication style summary
    reasoning_patterns: str  # Thinking patterns summary

    # Quality indicators
    quality_score: float  # 0-1 based on confidence
    confidence: float
    category: str  # Question category

    # Metadata
    source: str  # 'test_questions', 'decision_cases'
    source_id: str  # Original ID
    contexts: List[str] = field(default_factory=list)  # Retrieved documents
    key_points: List[str] = field(default_factory=list)  # Expected key points

    def to_dspy_dict(self) -> Dict[str, Any]:
        """Convert to dict format for DSPy training."""
        return {
            "query": self.query,
            "profile_id": self.profile_id,
            "executive_name": self.executive_name,
            "executive_style": self.executive_style,
            "reasoning_patterns": self.reasoning_patterns,
            "expected_response": self.expected_response,
            "contexts": self.contexts,
            "key_points": self.key_points,
            "quality_score": self.quality_score,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to full dict."""
        return asdict(self)


# Executive name to profile_id mapping
EXECUTIVE_PROFILE_MAP = {
    "Akiko Tanaka": "exec_001_test",
    "田中明子": "exec_001_test",
    "Raj Patel": "exec_002_test",
    "Yuki Nakamura": "exec_003_test",
    "中村ユキ": "exec_003_test",
    "Sarah Kim": "exec_004_test",
}


class DSPyTrainingDatasetGenerator:
    """
    Generates DSPy training dataset from multiple sources.

    Sources:
    1. Test questions (test_data/test_questions/questions.json)
    2. Decision cases (PostgreSQL)
    3. Executive profiles (PostgreSQL)
    """

    def __init__(
        self,
        test_data_path: Optional[str] = None,
        postgres_config: Optional[Dict] = None
    ):
        """
        Initialize the generator.

        Args:
            test_data_path: Path to test_data folder. If None, auto-detect.
            postgres_config: Database connection config. If None, uses env vars.
        """
        # Auto-detect test_data path
        if test_data_path is None:
            # Try common paths
            candidates = [
                Path(__file__).parent.parent / "test_data",
                Path.cwd() / "test_data",
                Path.cwd() / "RAG" / "test_data",
            ]
            for path in candidates:
                if path.exists():
                    test_data_path = str(path)
                    break

        self.test_data_path = test_data_path
        self.postgres_config = postgres_config
        self._pool: Optional[asyncpg.Pool] = None
        self._executive_profiles: Dict[str, Dict] = {}

        logger.info(f"DSPyTrainingDatasetGenerator initialized (test_data: {test_data_path})")

    async def _get_pool(self) -> Optional[asyncpg.Pool]:
        """Get or create connection pool."""
        if not ASYNCPG_AVAILABLE:
            return None

        if self._pool is None:
            try:
                if self.postgres_config:
                    self._pool = await asyncpg.create_pool(**self.postgres_config)
                else:
                    self._pool = await asyncpg.create_pool(
                        host=os.getenv("POSTGRES_HOST", "localhost"),
                        port=int(os.getenv("POSTGRES_PORT", "5432")),
                        database=os.getenv("POSTGRES_DB", "ai_officer_dev"),
                        user=os.getenv("POSTGRES_USER", "postgres"),
                        password=os.getenv("POSTGRES_PASSWORD", ""),
                    )
            except Exception as e:
                logger.warning(f"Failed to connect to database: {e}")
                return None
        return self._pool

    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def _load_executive_profiles(self) -> Dict[str, Dict]:
        """Load executive profiles from database."""
        if self._executive_profiles:
            return self._executive_profiles

        pool = await self._get_pool()
        if not pool:
            # Fallback to file-based profiles
            return self._load_executive_profiles_from_files()

        try:
            query = """
                SELECT
                    id,
                    name,
                    title,
                    formality_scale,
                    directness_scale,
                    warmth_scale,
                    profile_data
                FROM executive_profiles
            """
            async with pool.acquire() as conn:
                rows = await conn.fetch(query)

            for row in rows:
                profile = dict(row)
                if profile.get("profile_data"):
                    profile["profile_data"] = json.loads(profile["profile_data"]) if isinstance(profile["profile_data"], str) else profile["profile_data"]
                self._executive_profiles[profile["id"]] = profile

            logger.info(f"Loaded {len(self._executive_profiles)} executive profiles from database")
        except Exception as e:
            logger.warning(f"Failed to load profiles from database: {e}")
            return self._load_executive_profiles_from_files()

        return self._executive_profiles

    def _load_executive_profiles_from_files(self) -> Dict[str, Dict]:
        """Load executive profiles from JSON files."""
        if not self.test_data_path:
            return {}

        profiles_dir = Path(self.test_data_path) / "executive_profiles"
        if not profiles_dir.exists():
            return {}

        for filepath in profiles_dir.glob("*.json"):
            if "mapping" in filepath.name:
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
                    profile_id = profile.get("id", filepath.stem)
                    self._executive_profiles[profile_id] = profile
            except Exception as e:
                logger.warning(f"Failed to load profile {filepath}: {e}")

        logger.info(f"Loaded {len(self._executive_profiles)} executive profiles from files")
        return self._executive_profiles

    def _extract_style_summary(self, profile: Dict[str, Any]) -> str:
        """Extract communication style summary."""
        profile_data = profile.get("profile_data", profile)
        comm_style = profile_data.get("communication_style", {})

        parts = []
        parts.append(f"Formality: {profile.get('formality_scale', comm_style.get('formality_scale', 5))}/10")
        parts.append(f"Directness: {profile.get('directness_scale', comm_style.get('directness_scale', 5))}/10")
        parts.append(f"Warmth: {profile.get('warmth_scale', comm_style.get('warmth_scale', 5))}/10")
        parts.append(f"Tone: {comm_style.get('overall_tone', 'professional')}")

        phrases = comm_style.get("frequent_phrases", [])[:3]
        if phrases:
            parts.append(f"Phrases: {', '.join(phrases)}")

        return "; ".join(parts)

    def _extract_reasoning_summary(self, profile: Dict[str, Any]) -> str:
        """Extract reasoning patterns summary."""
        profile_data = profile.get("profile_data", profile)
        thinking = profile_data.get("thinking_patterns", {})

        parts = []
        parts.append(thinking.get("approach", "Analytical"))

        frameworks = thinking.get("framework_examples", [])[:2]
        if frameworks:
            parts.append(f"Frameworks: {', '.join(frameworks)}")

        questions = thinking.get("typical_questions", [])[:3]
        if questions:
            parts.append(f"Key questions: {'; '.join(questions)}")

        return "; ".join(parts)

    def load_test_questions(self) -> List[Dict[str, Any]]:
        """Load test questions from JSON file."""
        if not self.test_data_path:
            logger.warning("test_data_path not set, skipping test questions")
            return []

        questions_file = Path(self.test_data_path) / "test_questions" / "questions.json"
        if not questions_file.exists():
            logger.warning(f"Test questions file not found: {questions_file}")
            return []

        try:
            with open(questions_file, 'r', encoding='utf-8') as f:
                questions = json.load(f)
            logger.info(f"Loaded {len(questions)} test questions")
            return questions
        except Exception as e:
            logger.error(f"Failed to load test questions: {e}")
            return []

    async def generate_from_test_questions(self) -> List[TrainingExample]:
        """Generate training examples from test questions."""
        questions = self.load_test_questions()
        profiles = await self._load_executive_profiles()

        examples = []
        for q in questions:
            # Get executive name and map to profile_id
            exec_name = q.get("executive", "")
            profile_id = EXECUTIVE_PROFILE_MAP.get(exec_name, "exec_001_test")
            profile = profiles.get(profile_id, {})

            # Get expected answer data
            expected = q.get("expected_answer", {})
            answer = expected.get("answer", "")
            key_points = expected.get("key_points", [])
            confidence = expected.get("confidence_threshold", 0.85)
            sources = expected.get("sources", [])

            if not answer:
                continue

            example = TrainingExample(
                query=q.get("question", ""),
                profile_id=profile_id,
                expected_response=answer,
                executive_name=exec_name,
                executive_title=profile.get("title", "Executive"),
                executive_style=self._extract_style_summary(profile),
                reasoning_patterns=self._extract_reasoning_summary(profile),
                quality_score=confidence,
                confidence=confidence,
                category=q.get("category", "unknown"),
                source="test_questions",
                source_id=q.get("id", ""),
                contexts=sources,
                key_points=key_points,
            )
            examples.append(example)

        logger.info(f"Generated {len(examples)} examples from test questions")
        return examples

    async def generate_from_decision_cases(self) -> List[TrainingExample]:
        """Generate training examples from decision cases."""
        pool = await self._get_pool()
        if not pool:
            logger.warning("Database not available, skipping decision cases")
            return []

        profiles = await self._load_executive_profiles()

        query = """
            SELECT
                dc.id,
                dc.executive_id,
                dc.title,
                dc.category,
                dc.situation,
                dc.decision_made,
                dc.rationale,
                dc.outcome,
                dc.lessons_learned,
                dc.confidence,
                ep.name as executive_name,
                ep.title as executive_title
            FROM decision_cases dc
            JOIN executive_profiles ep ON dc.executive_id = ep.id
        """

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query)
        except Exception as e:
            logger.error(f"Failed to load decision cases: {e}")
            return []

        examples = []
        for row in rows:
            case = dict(row)
            profile_id = case.get("executive_id", "")
            profile = profiles.get(profile_id, {})

            # Generate a natural question from the situation
            situation = case.get("situation", "")
            category = case.get("category", "")
            query_text = self._generate_query_from_situation(situation, category)

            # Build expected response from decision + rationale
            response = self._build_response_from_decision(case, profile)

            # Calculate quality score
            confidence = float(case.get("confidence", 0.75))
            outcome = case.get("outcome", "").upper()
            if "SUCCESS" in outcome:
                quality_score = min(1.0, confidence + 0.15)
            elif "MIXED" in outcome:
                quality_score = confidence
            else:
                quality_score = max(0.5, confidence - 0.1)

            example = TrainingExample(
                query=query_text,
                profile_id=profile_id,
                expected_response=response,
                executive_name=case.get("executive_name", ""),
                executive_title=case.get("executive_title", ""),
                executive_style=self._extract_style_summary(profile),
                reasoning_patterns=self._extract_reasoning_summary(profile),
                quality_score=quality_score,
                confidence=confidence,
                category=category,
                source="decision_cases",
                source_id=case.get("id", ""),
                contexts=[situation],
                key_points=[case.get("lessons_learned", "")],
            )
            examples.append(example)

        logger.info(f"Generated {len(examples)} examples from decision cases")
        return examples

    def _generate_query_from_situation(self, situation: str, category: str) -> str:
        """Generate a natural query from situation text."""
        # Extract first sentence as summary
        sentences = situation.split('.')
        summary = sentences[0].strip()[:100] if sentences else situation[:100]

        # Simple category-based prefix
        prefixes = {
            "pricing_strategy": "How should we handle this pricing decision",
            "product_investment": "What's your view on this product investment",
            "personnel_crisis": "How should we handle this personnel situation",
            "market_expansion": "Should we pursue this expansion opportunity",
            "crisis_management": "How should we respond to this situation",
            "budget_approval": "What's your view on this budget request",
            "cost_optimization": "How should we approach cost optimization",
            "financial_planning": "What's your recommendation on this",
            "financial_risk": "How do you assess this risk",
            "security_incident": "How should we handle this security issue",
            "architecture_decision": "What's your view on this architecture decision",
            "build_vs_buy": "Should we build or buy here",
            "team_management": "How should we handle this team situation",
            "technical_debt": "How should we address this technical debt",
            "budget_allocation": "How should we allocate budget for this",
            "campaign_strategy": "What's your strategy for this campaign",
            "marketing_sales_alignment": "How do we align on this",
            "content_strategy": "What content approach do you recommend",
            "brand_crisis": "How should we handle this brand situation",
        }

        prefix = prefixes.get(category, "What's your recommendation on this")
        return f"{prefix}: {summary}..."

    def _build_response_from_decision(self, case: Dict[str, Any], profile: Dict[str, Any]) -> str:
        """Build expected response in executive's voice."""
        decision = case.get("decision_made", "")
        rationale = case.get("rationale", "")

        # Get communication style
        profile_data = profile.get("profile_data", profile)
        comm_style = profile_data.get("communication_style", {})

        # Build response
        parts = []

        # Opening
        openings = comm_style.get("typical_openings", [])
        if openings:
            parts.append(openings[0])

        # Decision
        parts.append(f"\n\n{decision}")

        # Rationale (truncated if long)
        if rationale:
            if len(rationale) > 600:
                rationale = rationale[:600] + "..."
            parts.append(f"\n\nHere's my reasoning:\n{rationale}")

        # Closing
        closings = comm_style.get("typical_closings", [])
        if closings:
            parts.append(f"\n\n{closings[0]}")

        return "".join(parts)

    async def generate_dataset(
        self,
        include_test_questions: bool = True,
        include_decision_cases: bool = True,
        min_quality_score: float = 0.5,
    ) -> List[TrainingExample]:
        """
        Generate complete training dataset from all sources.

        Args:
            include_test_questions: Include test questions (recommended)
            include_decision_cases: Include decision cases from DB
            min_quality_score: Minimum quality score to include (0-1)

        Returns:
            List of TrainingExample objects
        """
        examples = []

        # Load from test questions (primary source - high quality)
        if include_test_questions:
            test_examples = await self.generate_from_test_questions()
            examples.extend(test_examples)

        # Load from decision cases (secondary source)
        if include_decision_cases:
            decision_examples = await self.generate_from_decision_cases()
            examples.extend(decision_examples)

        # Filter by quality score
        filtered = [ex for ex in examples if ex.quality_score >= min_quality_score]

        logger.info(f"Total dataset: {len(filtered)} examples (filtered from {len(examples)})")
        return filtered

    def export_to_json(
        self,
        examples: List[TrainingExample],
        filepath: str,
        format: str = "dspy"
    ):
        """Export training examples to JSON file."""
        if format == "dspy":
            data = [ex.to_dspy_dict() for ex in examples]
        else:
            data = [ex.to_dict() for ex in examples]

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(examples)} examples to {filepath}")

    def export_to_csv(self, examples: List[TrainingExample], filepath: str):
        """Export training examples to CSV file."""
        import csv

        if not examples:
            return

        fieldnames = ['query', 'profile_id', 'executive_name', 'category',
                      'expected_response', 'quality_score', 'source', 'source_id']

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for ex in examples:
                row = {k: getattr(ex, k, "") for k in fieldnames}
                writer.writerow(row)

        logger.info(f"Exported {len(examples)} examples to {filepath}")

    def get_dataset_statistics(self, examples: List[TrainingExample]) -> Dict[str, Any]:
        """Get statistics about the training dataset."""
        if not examples:
            return {"error": "No examples"}

        # By executive
        by_executive = {}
        for ex in examples:
            name = ex.executive_name
            by_executive[name] = by_executive.get(name, 0) + 1

        # By source
        by_source = {}
        for ex in examples:
            src = ex.source
            by_source[src] = by_source.get(src, 0) + 1

        # By category
        by_category = {}
        for ex in examples:
            cat = ex.category
            by_category[cat] = by_category.get(cat, 0) + 1

        # Quality stats
        quality_scores = [ex.quality_score for ex in examples]
        avg_quality = sum(quality_scores) / len(quality_scores)

        return {
            "total_examples": len(examples),
            "by_source": by_source,
            "by_executive": by_executive,
            "by_category": by_category,
            "avg_quality_score": round(avg_quality, 3),
            "min_quality_score": round(min(quality_scores), 3),
            "max_quality_score": round(max(quality_scores), 3),
        }


# Convenience function
async def generate_training_dataset(
    output_path: str = "dspy_training_data.json",
    min_quality: float = 0.5,
    format: str = "dspy"
) -> List[TrainingExample]:
    """
    Generate and export DSPy training dataset.

    Args:
        output_path: Output JSON file path
        min_quality: Minimum quality score (0-1)
        format: "dspy" or "full"

    Returns:
        List of TrainingExample objects
    """
    generator = DSPyTrainingDatasetGenerator()
    try:
        examples = await generator.generate_dataset(min_quality_score=min_quality)
        generator.export_to_json(examples, output_path, format=format)

        stats = generator.get_dataset_statistics(examples)
        logger.info(f"Dataset statistics: {json.dumps(stats, indent=2)}")

        return examples
    finally:
        await generator.close()
