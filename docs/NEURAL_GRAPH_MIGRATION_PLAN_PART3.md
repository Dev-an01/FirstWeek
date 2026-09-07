# Neural Graph Migration Plan - Part 3

## 5. Phase 3: Neural Routing & MoE (Continued)

### 5.3 MoE Implementation

**File**: `RAG/neural_engine/moe_router.py`

```python
"""
Mixture of Experts Router - Learns optimal expert selection.

Replaces hardcoded routing with learned classification.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class MoEConfig:
    """Configuration for Mixture of Experts."""
    exec_dna_dim: int = 512
    query_dim: int = 512
    rules_dim: int = 128
    hidden_dim: int = 256
    num_experts: int = 5
    top_k: int = 2  # Sparse selection
    dropout: float = 0.1
    temperature: float = 1.0
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


@dataclass
class ExpertDefinition:
    """Definition of an expert."""
    id: str
    name: str
    domain: str
    prompt_template: str
    keywords: List[str]


@dataclass
class MoEResult:
    """Result of MoE routing."""
    selected_experts: List[Tuple[ExpertDefinition, float]]  # (expert, weight)
    all_weights: Dict[str, float]
    gating_entropy: float  # Measure of uncertainty
    explanation: str


class GatingNetwork(nn.Module):
    """
    Neural network that learns expert selection.

    Architecture:
        Input[1152] → Linear[256] → ReLU → Dropout
                   → Linear[128] → ReLU → Dropout
                   → Linear[num_experts] → Softmax
    """

    def __init__(self, config: MoEConfig):
        super().__init__()
        self.config = config

        input_dim = config.exec_dna_dim + config.query_dim + config.rules_dim

        self.network = nn.Sequential(
            nn.Linear(input_dim, config.hidden_dim),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim // 2, config.num_experts)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through gating network.

        Args:
            x: Input tensor [batch, input_dim]

        Returns:
            Expert weights [batch, num_experts]
        """
        logits = self.network(x)
        weights = F.softmax(logits / self.config.temperature, dim=-1)
        return weights


class MoERouter:
    """
    Mixture of Experts Router.

    Learns to select the best expert(s) based on:
    - Executive DNA (who is asking)
    - Query embedding (what they're asking)
    - Activated rules (contextual modifiers)

    Uses sparse selection (top-k) for efficiency.
    """

    def __init__(
        self,
        config: Optional[MoEConfig] = None,
        experts: Optional[List[ExpertDefinition]] = None
    ):
        self.config = config or MoEConfig()
        self.gating_network = GatingNetwork(self.config)
        self.gating_network.to(self.config.device)

        # Default experts
        self.experts = experts or self._default_experts()
        self.expert_id_to_idx = {e.id: i for i, e in enumerate(self.experts)}

        # Rules encoder (simple pooling for now)
        self.rules_encoder = nn.Sequential(
            nn.Linear(self.config.rules_dim, self.config.rules_dim),
            nn.ReLU()
        ).to(self.config.device)

    def _default_experts(self) -> List[ExpertDefinition]:
        """Default expert definitions."""
        return [
            ExpertDefinition(
                id="expert_financial",
                name="Financial Analyst",
                domain="finance",
                prompt_template="Analyze from a financial perspective. Consider ROI, cash flow, budget impact.",
                keywords=["budget", "cost", "revenue", "roi", "margin", "financial"]
            ),
            ExpertDefinition(
                id="expert_technical",
                name="Technical Advisor",
                domain="technology",
                prompt_template="Provide technical analysis. Consider architecture, scalability, technical debt.",
                keywords=["technical", "architecture", "code", "system", "engineering"]
            ),
            ExpertDefinition(
                id="expert_strategic",
                name="Strategic Thinker",
                domain="strategy",
                prompt_template="Think strategically. Consider long-term implications and competitive positioning.",
                keywords=["strategy", "vision", "long-term", "competitive", "market"]
            ),
            ExpertDefinition(
                id="expert_people",
                name="People & Culture",
                domain="hr",
                prompt_template="Consider the human element. Think about team dynamics and organizational culture.",
                keywords=["team", "hire", "culture", "morale", "performance", "people"]
            ),
            ExpertDefinition(
                id="expert_legal",
                name="Legal & Compliance",
                domain="legal",
                prompt_template="Assess legal and compliance implications. Flag potential risks.",
                keywords=["legal", "compliance", "contract", "regulation", "liability"]
            )
        ]

    def encode_rules(self, activated_rules: List[Dict]) -> torch.Tensor:
        """
        Encode activated rules into a fixed-size vector.

        Simple approach: Hash rule IDs and create a sparse vector,
        then project to rules_dim.
        """
        # Create rule presence vector
        rule_vector = torch.zeros(self.config.rules_dim, device=self.config.device)

        for i, rule in enumerate(activated_rules[:self.config.rules_dim]):
            # Simple encoding: hash rule_id to index
            idx = hash(rule.get('rule_id', '')) % self.config.rules_dim
            weight = rule.get('weight', 1.0)
            rule_vector[idx] = weight

        # Normalize
        if rule_vector.sum() > 0:
            rule_vector = rule_vector / rule_vector.sum()

        return rule_vector

    def route(
        self,
        exec_dna: np.ndarray,
        query_embedding: np.ndarray,
        activated_rules: List[Dict],
        force_expert: Optional[str] = None
    ) -> MoEResult:
        """
        Route query to appropriate expert(s).

        Args:
            exec_dna: Executive DNA embedding [512]
            query_embedding: Query embedding [512]
            activated_rules: List of activated cognitive rules
            force_expert: Optional expert ID to force selection

        Returns:
            MoEResult with selected experts and weights
        """
        # Handle forced expert
        if force_expert and force_expert in self.expert_id_to_idx:
            idx = self.expert_id_to_idx[force_expert]
            expert = self.experts[idx]
            return MoEResult(
                selected_experts=[(expert, 1.0)],
                all_weights={e.id: 1.0 if e.id == force_expert else 0.0 for e in self.experts},
                gating_entropy=0.0,
                explanation=f"Forced expert selection: {expert.name}"
            )

        # Prepare inputs
        exec_tensor = torch.tensor(exec_dna, dtype=torch.float32, device=self.config.device)
        query_tensor = torch.tensor(query_embedding, dtype=torch.float32, device=self.config.device)
        rules_tensor = self.encode_rules(activated_rules)

        # Concatenate inputs
        combined = torch.cat([exec_tensor, query_tensor, rules_tensor])
        combined = combined.unsqueeze(0)  # Add batch dimension

        # Get expert weights
        with torch.no_grad():
            weights = self.gating_network(combined)
            weights = weights.squeeze(0)  # Remove batch dimension

        # Sparse selection (top-k)
        top_weights, top_indices = torch.topk(weights, k=self.config.top_k)

        # Renormalize selected weights
        top_weights = top_weights / top_weights.sum()

        # Build result
        selected_experts = []
        for weight, idx in zip(top_weights.tolist(), top_indices.tolist()):
            expert = self.experts[idx]
            selected_experts.append((expert, weight))

        # All weights for logging
        all_weights = {
            self.experts[i].id: w
            for i, w in enumerate(weights.tolist())
        }

        # Calculate entropy (measure of uncertainty)
        entropy = -torch.sum(weights * torch.log(weights + 1e-10)).item()

        # Build explanation
        primary = selected_experts[0]
        explanation = f"Primary: {primary[0].name} ({primary[1]:.0%})"
        if len(selected_experts) > 1:
            secondary = selected_experts[1]
            explanation += f", Secondary: {secondary[0].name} ({secondary[1]:.0%})"

        return MoEResult(
            selected_experts=selected_experts,
            all_weights=all_weights,
            gating_entropy=entropy,
            explanation=explanation
        )

    def build_expert_prompt(self, result: MoEResult) -> str:
        """
        Build prompt section from expert selection.

        Combines selected expert templates weighted by their selection weights.
        """
        if not result.selected_experts:
            return ""

        lines = ["YOUR EXPERT PERSPECTIVES FOR THIS QUERY:"]
        lines.append("")

        for expert, weight in result.selected_experts:
            weight_label = "Primary" if weight > 0.5 else "Secondary"
            lines.append(f"[{weight_label}] {expert.name} ({weight:.0%}):")
            lines.append(f"  {expert.prompt_template}")
            lines.append("")

        return "\n".join(lines)

    def save_checkpoint(self, path: str):
        """Save model checkpoint."""
        torch.save({
            'gating_network': self.gating_network.state_dict(),
            'rules_encoder': self.rules_encoder.state_dict(),
            'config': self.config
        }, path)
        logger.info(f"Saved MoE checkpoint to {path}")

    def load_checkpoint(self, path: str):
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.config.device)
        self.gating_network.load_state_dict(checkpoint['gating_network'])
        self.rules_encoder.load_state_dict(checkpoint['rules_encoder'])
        logger.info(f"Loaded MoE checkpoint from {path}")


class MoETrainer:
    """
    Trainer for the MoE gating network.

    Uses feedback signals to learn optimal expert selection:
    - Positive feedback → reinforce current selection
    - Negative feedback → explore alternatives
    """

    def __init__(
        self,
        router: MoERouter,
        learning_rate: float = 1e-4,
        feedback_weight: float = 1.0
    ):
        self.router = router
        self.optimizer = torch.optim.Adam(
            list(router.gating_network.parameters()) +
            list(router.rules_encoder.parameters()),
            lr=learning_rate
        )
        self.feedback_weight = feedback_weight

    def train_step(
        self,
        exec_dna: np.ndarray,
        query_embedding: np.ndarray,
        activated_rules: List[Dict],
        target_expert_id: str,
        feedback_score: float  # -1 to 1
    ) -> float:
        """
        Single training step from feedback.

        Args:
            exec_dna: Executive DNA embedding
            query_embedding: Query embedding
            activated_rules: Activated rules
            target_expert_id: Expert that was selected
            feedback_score: User feedback (-1 = bad, 1 = good)

        Returns:
            Loss value
        """
        self.optimizer.zero_grad()

        # Prepare inputs
        exec_tensor = torch.tensor(exec_dna, dtype=torch.float32, device=self.router.config.device)
        query_tensor = torch.tensor(query_embedding, dtype=torch.float32, device=self.router.config.device)
        rules_tensor = self.router.encode_rules(activated_rules)

        combined = torch.cat([exec_tensor, query_tensor, rules_tensor])
        combined = combined.unsqueeze(0).requires_grad_(True)

        # Get current weights
        weights = self.router.gating_network(combined).squeeze(0)

        # Get target index
        target_idx = self.router.expert_id_to_idx.get(target_expert_id)
        if target_idx is None:
            return 0.0

        # Compute loss based on feedback
        # Positive feedback → increase probability of selected expert
        # Negative feedback → decrease probability (entropy bonus)
        if feedback_score > 0:
            # Cross-entropy loss to reinforce selection
            target_tensor = torch.tensor([target_idx], device=self.router.config.device)
            loss = F.cross_entropy(weights.unsqueeze(0), target_tensor)
            loss = loss * feedback_score * self.feedback_weight
        else:
            # Negative feedback: add entropy to encourage exploration
            entropy = -torch.sum(weights * torch.log(weights + 1e-10))
            loss = -entropy * abs(feedback_score) * self.feedback_weight

        loss.backward()
        self.optimizer.step()

        return loss.item()

    def train_batch(
        self,
        batch: List[Tuple[np.ndarray, np.ndarray, List[Dict], str, float]]
    ) -> float:
        """
        Train on batch of feedback samples.

        Args:
            batch: List of (exec_dna, query_emb, rules, expert_id, feedback) tuples

        Returns:
            Average loss
        """
        total_loss = 0.0
        for sample in batch:
            loss = self.train_step(*sample)
            total_loss += loss

        return total_loss / len(batch) if batch else 0.0
```

### 5.4 Adaptive Weight Network

**File**: `RAG/neural_engine/adaptive_weights.py`

```python
"""
Adaptive Weight Network - Learns optimal retrieval weights.

Replaces fixed 60/40/10 weights with learned per-context weights.
"""

import torch
import torch.nn as nn
import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class WeightConfig:
    """Configuration for adaptive weights."""
    exec_dna_dim: int = 512
    query_dim: int = 512
    expert_dim: int = 64
    hidden_dim: int = 128
    num_sources: int = 3  # vector, graph, memory
    min_weight: float = 0.05  # Minimum weight per source
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


@dataclass
class WeightResult:
    """Result of weight prediction."""
    vector_weight: float
    graph_weight: float
    memory_weight: float
    confidence: float
    explanation: str


class WeightPredictionNetwork(nn.Module):
    """
    Neural network that predicts retrieval source weights.

    Input: exec_dna ⊕ query_embedding ⊕ expert_selection
    Output: [vector_weight, graph_weight, memory_weight]
    """

    def __init__(self, config: WeightConfig):
        super().__init__()
        self.config = config

        input_dim = config.exec_dna_dim + config.query_dim + config.expert_dim

        self.network = nn.Sequential(
            nn.Linear(input_dim, config.hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(config.hidden_dim // 2, config.num_sources)
        )

        # Confidence head
        self.confidence_head = nn.Sequential(
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid()
        )

        # Store intermediate for confidence
        self.intermediate = None

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Returns:
            weights: [batch, num_sources] summing to 1
            confidence: [batch, 1] between 0 and 1
        """
        # Pass through network
        h = x
        for layer in list(self.network.children())[:-1]:
            h = layer(h)

        self.intermediate = h

        # Get raw weights
        raw_weights = self.network[-1](h)

        # Apply softmax with minimum weight constraint
        weights = torch.softmax(raw_weights, dim=-1)
        weights = weights * (1 - self.config.min_weight * self.config.num_sources)
        weights = weights + self.config.min_weight

        # Get confidence
        confidence = self.confidence_head(h)

        return weights, confidence


class AdaptiveWeightPredictor:
    """
    Predicts optimal retrieval weights based on context.

    Instead of fixed weights:
        hybrid_score = 0.60 * vector + 0.30 * graph + 0.10 * memory

    We predict optimal weights:
        weights = predict(exec_dna, query, expert)
        hybrid_score = weights[0] * vector + weights[1] * graph + weights[2] * memory
    """

    def __init__(self, config: Optional[WeightConfig] = None):
        self.config = config or WeightConfig()
        self.network = WeightPredictionNetwork(self.config)
        self.network.to(self.config.device)

        # Default weights (used as fallback and initialization target)
        self.default_weights = {
            'vector': 0.60,
            'graph': 0.30,
            'memory': 0.10
        }

    def predict(
        self,
        exec_dna: np.ndarray,
        query_embedding: np.ndarray,
        expert_embedding: np.ndarray,
        use_defaults: bool = False
    ) -> WeightResult:
        """
        Predict optimal retrieval weights.

        Args:
            exec_dna: Executive DNA [512]
            query_embedding: Query embedding [512]
            expert_embedding: Expert selection embedding [64]
            use_defaults: If True, return default weights

        Returns:
            WeightResult with predicted weights
        """
        if use_defaults:
            return WeightResult(
                vector_weight=self.default_weights['vector'],
                graph_weight=self.default_weights['graph'],
                memory_weight=self.default_weights['memory'],
                confidence=1.0,
                explanation="Using default weights"
            )

        # Prepare inputs
        exec_tensor = torch.tensor(exec_dna, dtype=torch.float32, device=self.config.device)
        query_tensor = torch.tensor(query_embedding, dtype=torch.float32, device=self.config.device)
        expert_tensor = torch.tensor(expert_embedding, dtype=torch.float32, device=self.config.device)

        combined = torch.cat([exec_tensor, query_tensor, expert_tensor])
        combined = combined.unsqueeze(0)

        # Predict
        with torch.no_grad():
            weights, confidence = self.network(combined)
            weights = weights.squeeze(0)
            confidence = confidence.squeeze().item()

        # Extract weights
        vector_w = weights[0].item()
        graph_w = weights[1].item()
        memory_w = weights[2].item()

        # Build explanation
        dominant = "vector" if vector_w > graph_w and vector_w > memory_w else \
                   "graph" if graph_w > memory_w else "memory"

        explanation = f"Weights: vector={vector_w:.0%}, graph={graph_w:.0%}, memory={memory_w:.0%} (dominant: {dominant})"

        return WeightResult(
            vector_weight=vector_w,
            graph_weight=graph_w,
            memory_weight=memory_w,
            confidence=confidence,
            explanation=explanation
        )

    def apply_weights(
        self,
        result: WeightResult,
        vector_score: float,
        graph_score: float,
        memory_score: float
    ) -> float:
        """
        Apply predicted weights to compute hybrid score.

        Args:
            result: Weight prediction result
            vector_score: Score from vector search
            graph_score: Score from graph context
            memory_score: Score from memory search

        Returns:
            Weighted hybrid score
        """
        return (
            result.vector_weight * vector_score +
            result.graph_weight * graph_score +
            result.memory_weight * memory_score
        )

    def save_checkpoint(self, path: str):
        """Save model checkpoint."""
        torch.save({
            'network': self.network.state_dict(),
            'config': self.config,
            'default_weights': self.default_weights
        }, path)

    def load_checkpoint(self, path: str):
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.config.device)
        self.network.load_state_dict(checkpoint['network'])
        self.default_weights = checkpoint.get('default_weights', self.default_weights)
```

### 5.5 Unified Neural Router

**File**: `RAG/neural_engine/neural_router.py`

```python
"""
Unified Neural Router - Combines all neural routing components.

This is the main entry point that replaces the old hardcoded QueryRouter.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

from .dna_manager import DNAManager
from .logic_graph_provider import LogicGraphProvider, GraphActivationResult
from .moe_router import MoERouter, MoEResult
from .adaptive_weights import AdaptiveWeightPredictor, WeightResult

logger = logging.getLogger(__name__)


@dataclass
class NeuralRoutingResult:
    """Complete result of neural routing."""
    # DNA
    exec_dna: np.ndarray
    similar_executives: List[Dict]

    # Graph activation
    graph_activation: GraphActivationResult

    # Expert selection
    moe_result: MoEResult

    # Retrieval weights
    weight_result: WeightResult

    # Computed values
    processing_path: str  # "fast", "standard", "agentic"
    confidence: float
    explanation: str


class NeuralRouter:
    """
    Unified neural router that replaces hardcoded QueryRouter.

    Flow:
    1. Get/compute executive DNA
    2. Activate rules via graph traversal
    3. Select experts via MoE
    4. Predict retrieval weights
    5. Determine processing path

    This replaces all if/else routing logic with learned decisions.
    """

    def __init__(
        self,
        dna_manager: DNAManager,
        logic_graph: LogicGraphProvider,
        moe_router: MoERouter,
        weight_predictor: AdaptiveWeightPredictor,
        query_encoder  # Sentence transformer for query encoding
    ):
        self.dna_manager = dna_manager
        self.logic_graph = logic_graph
        self.moe_router = moe_router
        self.weight_predictor = weight_predictor
        self.query_encoder = query_encoder

    async def route(
        self,
        executive_id: str,
        query_text: str,
        force_path: Optional[str] = None,
        force_expert: Optional[str] = None
    ) -> NeuralRoutingResult:
        """
        Route query using neural components.

        Args:
            executive_id: Executive ID
            query_text: User's query
            force_path: Optional path override
            force_expert: Optional expert override

        Returns:
            NeuralRoutingResult with all routing decisions
        """
        # 1. Get executive DNA
        exec_dna = await self.dna_manager.get_dna(executive_id)
        if exec_dna is None:
            raise ValueError(f"No DNA found for executive: {executive_id}")

        # 2. Get similar executives (for knowledge transfer)
        similar = await self.dna_manager.find_similar_executives(
            exec_dna, top_k=3, exclude_ids=[executive_id]
        )

        # 3. Encode query
        query_embedding = self.query_encoder.encode(query_text)

        # 4. Activate rules via graph
        graph_result = await self.logic_graph.activate_rules(
            executive_id, query_text, query_embedding
        )

        # 5. Select experts via MoE
        activated_rules_dicts = [
            {'rule_id': r.rule_id, 'weight': r.weight}
            for r in graph_result.activated_rules
        ]

        moe_result = self.moe_router.route(
            exec_dna, query_embedding, activated_rules_dicts, force_expert
        )

        # 6. Create expert embedding for weight prediction
        expert_embedding = self._create_expert_embedding(moe_result)

        # 7. Predict retrieval weights
        weight_result = self.weight_predictor.predict(
            exec_dna, query_embedding, expert_embedding
        )

        # 8. Determine processing path
        path = self._determine_path(
            query_text, graph_result, moe_result, force_path
        )

        # 9. Compute confidence
        confidence = self._compute_confidence(
            moe_result, weight_result, graph_result
        )

        # 10. Build explanation
        explanation = self._build_explanation(
            path, graph_result, moe_result, weight_result
        )

        return NeuralRoutingResult(
            exec_dna=exec_dna,
            similar_executives=similar,
            graph_activation=graph_result,
            moe_result=moe_result,
            weight_result=weight_result,
            processing_path=path,
            confidence=confidence,
            explanation=explanation
        )

    def _create_expert_embedding(self, moe_result: MoEResult) -> np.ndarray:
        """Create fixed-size embedding from expert selection."""
        # Simple approach: one-hot-ish encoding weighted by selection
        num_experts = len(self.moe_router.experts)
        embedding = np.zeros(64)  # Fixed size

        for expert, weight in moe_result.selected_experts:
            idx = self.moe_router.expert_id_to_idx.get(expert.id, 0)
            start = idx * (64 // num_experts)
            end = start + (64 // num_experts)
            embedding[start:end] = weight

        return embedding

    def _determine_path(
        self,
        query_text: str,
        graph_result: GraphActivationResult,
        moe_result: MoEResult,
        force_path: Optional[str]
    ) -> str:
        """Determine processing path based on all signals."""
        if force_path:
            return force_path

        # Check for red flags → standard or agentic
        if graph_result.red_flags:
            return "standard"  # Need careful handling

        # Check query complexity signals
        query_lower = query_text.lower()

        # Simple queries → fast
        simple_patterns = ["what is", "who is", "define", "tell me about"]
        if any(p in query_lower for p in simple_patterns) and len(query_text) < 50:
            return "fast"

        # Complex queries → agentic
        complex_patterns = ["compare", "analyze", "evaluate", "trade-off", "pros and cons"]
        if any(p in query_lower for p in complex_patterns):
            return "agentic"

        # Multi-expert selection with low confidence → agentic
        if len(moe_result.selected_experts) > 1 and moe_result.gating_entropy > 1.0:
            return "agentic"

        # Default to standard
        return "standard"

    def _compute_confidence(
        self,
        moe_result: MoEResult,
        weight_result: WeightResult,
        graph_result: GraphActivationResult
    ) -> float:
        """Compute overall routing confidence."""
        # Average of component confidences
        moe_confidence = 1.0 - (moe_result.gating_entropy / 2.0)  # Normalize entropy
        weight_confidence = weight_result.confidence

        # Penalize if red flags present
        red_flag_penalty = 0.1 * len(graph_result.red_flags)

        confidence = (moe_confidence + weight_confidence) / 2.0 - red_flag_penalty
        return max(0.0, min(1.0, confidence))

    def _build_explanation(
        self,
        path: str,
        graph_result: GraphActivationResult,
        moe_result: MoEResult,
        weight_result: WeightResult
    ) -> str:
        """Build human-readable routing explanation."""
        parts = [f"Path: {path.upper()}"]
        parts.append(moe_result.explanation)
        parts.append(weight_result.explanation)

        if graph_result.red_flags:
            flags = ", ".join(f.category for f in graph_result.red_flags)
            parts.append(f"⚠️ Flags: {flags}")

        return " | ".join(parts)
```

### 5.6 Phase 3 Deliverables

| Deliverable | Description | Success Criteria |
|-------------|-------------|------------------|
| `GatingNetwork` | Neural network for expert selection | Learns from feedback |
| `MoERouter` | Complete MoE implementation | Selects appropriate experts |
| `MoETrainer` | Training from feedback | Loss decreases over time |
| `WeightPredictionNetwork` | Learns retrieval weights | Weights adapt to context |
| `AdaptiveWeightPredictor` | Full weight prediction | Better than fixed weights |
| `NeuralRouter` | Unified routing interface | Replaces old QueryRouter |
| Integration tests | End-to-end routing | All paths work correctly |
| A/B test framework | Compare old vs new routing | Metrics collection |

---

## 6. Phase 4: Learning Loop & Optimization (Weeks 13-16)

### 6.1 Objective
Implement continuous learning from user feedback to improve all neural components.

### 6.2 Feedback Collection System

**File**: `RAG/neural_engine/feedback_collector.py`

```python
"""
Feedback Collector - Captures and stores user feedback signals.

Signals:
- Explicit: thumbs up/down, ratings, edits
- Implicit: response time to next query, session length, follow-up questions
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

import asyncpg

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    RATING = "rating"
    EDIT = "edit"
    IMPLICIT_POSITIVE = "implicit_positive"
    IMPLICIT_NEGATIVE = "implicit_negative"


@dataclass
class FeedbackSignal:
    """A feedback signal from user interaction."""
    interaction_id: str
    exec_id: str
    signal_type: FeedbackType
    signal_value: float  # Normalized to [-1, 1]
    query_text: str
    response_text: str
    selected_expert_id: Optional[str] = None
    retrieval_weights: Optional[Dict[str, float]] = None
    activated_rules: Optional[List[str]] = None
    metadata: Optional[Dict] = None
    timestamp: Optional[datetime] = None

    def to_training_sample(self) -> Dict:
        """Convert to training sample format."""
        return {
            'interaction_id': self.interaction_id,
            'exec_id': self.exec_id,
            'query_text': self.query_text,
            'signal_value': self.signal_value,
            'selected_expert_id': self.selected_expert_id,
            'retrieval_weights': self.retrieval_weights,
            'activated_rules': self.activated_rules
        }


class FeedbackCollector:
    """
    Collects and stores feedback signals for learning.

    Feedback sources:
    1. Explicit UI feedback (thumbs up/down)
    2. User edits to responses
    3. Implicit signals (session patterns)
    """

    def __init__(self, pg_pool: asyncpg.Pool):
        self.pg_pool = pg_pool
        self._buffer: List[FeedbackSignal] = []
        self._buffer_size = 100

    async def record_feedback(self, signal: FeedbackSignal):
        """
        Record a feedback signal.

        Buffers signals and flushes to DB periodically.
        """
        signal.timestamp = datetime.utcnow()
        self._buffer.append(signal)

        if len(self._buffer) >= self._buffer_size:
            await self._flush_buffer()

    async def _flush_buffer(self):
        """Flush buffered signals to database."""
        if not self._buffer:
            return

        async with self.pg_pool.acquire() as conn:
            for signal in self._buffer:
                await conn.execute("""
                    INSERT INTO feedback_signals
                    (interaction_id, exec_id, signal_type, signal_value,
                     query_text, response_text, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                    signal.interaction_id,
                    signal.exec_id,
                    signal.signal_type.value,
                    signal.signal_value,
                    signal.query_text,
                    signal.response_text,
                    json.dumps({
                        'selected_expert_id': signal.selected_expert_id,
                        'retrieval_weights': signal.retrieval_weights,
                        'activated_rules': signal.activated_rules,
                        **(signal.metadata or {})
                    }),
                    signal.timestamp
                )

        logger.info(f"Flushed {len(self._buffer)} feedback signals to DB")
        self._buffer = []

    async def get_training_batch(
        self,
        exec_id: Optional[str] = None,
        min_timestamp: Optional[datetime] = None,
        batch_size: int = 100
    ) -> List[FeedbackSignal]:
        """
        Get batch of feedback for training.

        Args:
            exec_id: Optional filter by executive
            min_timestamp: Optional filter by time
            batch_size: Maximum batch size

        Returns:
            List of FeedbackSignal objects
        """
        async with self.pg_pool.acquire() as conn:
            query = """
                SELECT
                    interaction_id, exec_id, signal_type, signal_value,
                    query_text, response_text, metadata, created_at
                FROM feedback_signals
                WHERE 1=1
            """
            params = []

            if exec_id:
                params.append(exec_id)
                query += f" AND exec_id = ${len(params)}"

            if min_timestamp:
                params.append(min_timestamp)
                query += f" AND created_at >= ${len(params)}"

            query += f" ORDER BY created_at DESC LIMIT {batch_size}"

            rows = await conn.fetch(query, *params)

            signals = []
            for row in rows:
                metadata = json.loads(row['metadata']) if row['metadata'] else {}
                signals.append(FeedbackSignal(
                    interaction_id=row['interaction_id'],
                    exec_id=row['exec_id'],
                    signal_type=FeedbackType(row['signal_type']),
                    signal_value=row['signal_value'],
                    query_text=row['query_text'],
                    response_text=row['response_text'],
                    selected_expert_id=metadata.get('selected_expert_id'),
                    retrieval_weights=metadata.get('retrieval_weights'),
                    activated_rules=metadata.get('activated_rules'),
                    metadata=metadata,
                    timestamp=row['created_at']
                ))

            return signals

    async def get_feedback_stats(
        self,
        exec_id: Optional[str] = None,
        days: int = 7
    ) -> Dict:
        """Get feedback statistics."""
        async with self.pg_pool.acquire() as conn:
            query = """
                SELECT
                    signal_type,
                    COUNT(*) as count,
                    AVG(signal_value) as avg_value
                FROM feedback_signals
                WHERE created_at >= NOW() - INTERVAL '%s days'
            """
            params = [days]

            if exec_id:
                query += " AND exec_id = $2"
                params.append(exec_id)

            query += " GROUP BY signal_type"

            rows = await conn.fetch(query, *params)

            return {
                row['signal_type']: {
                    'count': row['count'],
                    'avg_value': float(row['avg_value']) if row['avg_value'] else 0
                }
                for row in rows
            }
```

### 6.3 Learning Loop Orchestrator

**File**: `RAG/neural_engine/learning_loop.py`

```python
"""
Learning Loop Orchestrator - Coordinates continuous learning from feedback.

Runs periodic training updates based on collected feedback.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import numpy as np

from .feedback_collector import FeedbackCollector, FeedbackSignal, FeedbackType
from .dna_manager import DNAManager
from .moe_router import MoERouter, MoETrainer
from .adaptive_weights import AdaptiveWeightPredictor
from .logic_graph_provider import LogicGraphProvider

logger = logging.getLogger(__name__)


class LearningLoopConfig:
    """Configuration for learning loop."""
    # Training frequency
    training_interval_minutes: int = 60
    min_samples_for_training: int = 10

    # Learning rates
    moe_learning_rate: float = 1e-4
    weight_learning_rate: float = 1e-4
    dna_learning_rate: float = 1e-5  # Lower for stability

    # Graph weight updates
    graph_weight_decay: float = 0.01
    graph_weight_boost: float = 0.02

    # Checkpointing
    checkpoint_interval_hours: int = 6
    checkpoint_dir: str = "/app/checkpoints"


class LearningLoopOrchestrator:
    """
    Orchestrates continuous learning from feedback.

    Updates:
    1. MoE gating network (expert selection)
    2. Weight prediction network (retrieval weights)
    3. Graph edge weights (rule activation strengths)
    4. DNA embeddings (via fine-tuning, optional)
    """

    def __init__(
        self,
        feedback_collector: FeedbackCollector,
        dna_manager: DNAManager,
        moe_router: MoERouter,
        weight_predictor: AdaptiveWeightPredictor,
        logic_graph: LogicGraphProvider,
        query_encoder,
        config: Optional[LearningLoopConfig] = None
    ):
        self.feedback = feedback_collector
        self.dna_manager = dna_manager
        self.moe_router = moe_router
        self.weight_predictor = weight_predictor
        self.logic_graph = logic_graph
        self.query_encoder = query_encoder
        self.config = config or LearningLoopConfig()

        # Initialize trainers
        self.moe_trainer = MoETrainer(
            moe_router,
            learning_rate=self.config.moe_learning_rate
        )

        # Tracking
        self.last_training_time = datetime.utcnow()
        self.last_checkpoint_time = datetime.utcnow()
        self.training_stats = {
            'total_samples_processed': 0,
            'moe_loss_history': [],
            'weight_loss_history': []
        }

        self._running = False

    async def start(self):
        """Start the learning loop."""
        self._running = True
        logger.info("Learning loop started")

        while self._running:
            try:
                await self._training_iteration()
            except Exception as e:
                logger.error(f"Learning loop error: {e}")

            await asyncio.sleep(self.config.training_interval_minutes * 60)

    async def stop(self):
        """Stop the learning loop."""
        self._running = False
        await self._save_checkpoint()
        logger.info("Learning loop stopped")

    async def _training_iteration(self):
        """Single training iteration."""
        logger.info("Starting training iteration...")

        # Get recent feedback
        samples = await self.feedback.get_training_batch(
            min_timestamp=self.last_training_time,
            batch_size=1000
        )

        if len(samples) < self.config.min_samples_for_training:
            logger.info(f"Insufficient samples ({len(samples)}), skipping training")
            return

        # Separate by feedback type
        positive_samples = [s for s in samples if s.signal_value > 0]
        negative_samples = [s for s in samples if s.signal_value < 0]

        logger.info(f"Training on {len(samples)} samples "
                   f"({len(positive_samples)} positive, {len(negative_samples)} negative)")

        # Update MoE
        moe_loss = await self._update_moe(samples)
        self.training_stats['moe_loss_history'].append(moe_loss)

        # Update graph weights
        await self._update_graph_weights(samples)

        # Update tracking
        self.last_training_time = datetime.utcnow()
        self.training_stats['total_samples_processed'] += len(samples)

        # Checkpoint if needed
        if (datetime.utcnow() - self.last_checkpoint_time).total_seconds() > \
           self.config.checkpoint_interval_hours * 3600:
            await self._save_checkpoint()

        logger.info(f"Training iteration complete. MoE loss: {moe_loss:.4f}")

    async def _update_moe(self, samples: list) -> float:
        """Update MoE gating network from feedback."""
        total_loss = 0.0
        count = 0

        for sample in samples:
            if not sample.selected_expert_id:
                continue

            # Get DNA and encode query
            exec_dna = await self.dna_manager.get_dna(sample.exec_id)
            if exec_dna is None:
                continue

            query_embedding = self.query_encoder.encode(sample.query_text)

            # Get activated rules (simplified)
            activated_rules = [
                {'rule_id': r, 'weight': 1.0}
                for r in (sample.activated_rules or [])
            ]

            # Train step
            loss = self.moe_trainer.train_step(
                exec_dna,
                query_embedding,
                activated_rules,
                sample.selected_expert_id,
                sample.signal_value
            )

            total_loss += loss
            count += 1

        return total_loss / count if count > 0 else 0.0

    async def _update_graph_weights(self, samples: list):
        """
        Update graph edge weights based on feedback.

        Positive feedback → strengthen activated rule edges
        Negative feedback → weaken activated rule edges
        """
        async with self.logic_graph.driver.session() as session:
            for sample in samples:
                if not sample.activated_rules:
                    continue

                for rule_id in sample.activated_rules:
                    # Calculate weight adjustment
                    if sample.signal_value > 0:
                        adjustment = self.config.graph_weight_boost * sample.signal_value
                    else:
                        adjustment = self.config.graph_weight_decay * sample.signal_value

                    # Update edge weight (capped at 0.1 to 0.95)
                    await session.run("""
                        MATCH (e:Executive {id: $exec_id})-[:WORKS_AT]->(c:Company)
                              -[:IN_INDUSTRY]->(i:Industry)
                        MATCH (i)-[a:ACTIVATES_RULE]->(r:CognitiveRule {id: $rule_id})
                        SET a.weight = CASE
                            WHEN a.weight + $adjustment < 0.1 THEN 0.1
                            WHEN a.weight + $adjustment > 0.95 THEN 0.95
                            ELSE a.weight + $adjustment
                        END,
                        a.last_updated = datetime(),
                        a.update_count = COALESCE(a.update_count, 0) + 1
                    """,
                        exec_id=sample.exec_id,
                        rule_id=rule_id,
                        adjustment=adjustment
                    )

        logger.info(f"Updated graph weights for {len(samples)} samples")

    async def _save_checkpoint(self):
        """Save model checkpoints."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # Save MoE
        moe_path = f"{self.config.checkpoint_dir}/moe_{timestamp}.pt"
        self.moe_router.save_checkpoint(moe_path)

        # Save weight predictor
        weight_path = f"{self.config.checkpoint_dir}/weights_{timestamp}.pt"
        self.weight_predictor.save_checkpoint(weight_path)

        self.last_checkpoint_time = datetime.utcnow()
        logger.info(f"Saved checkpoints at {timestamp}")

    def get_training_stats(self) -> Dict:
        """Get training statistics."""
        return {
            **self.training_stats,
            'last_training_time': self.last_training_time.isoformat(),
            'last_checkpoint_time': self.last_checkpoint_time.isoformat()
        }
```

### 6.4 Phase 4 Deliverables

| Deliverable | Description | Success Criteria |
|-------------|-------------|------------------|
| `FeedbackCollector` | Captures all feedback signals | All signal types captured |
| `LearningLoopOrchestrator` | Coordinates training | Periodic updates work |
| MoE training integration | Updates from feedback | Loss decreases |
| Graph weight updates | Strengthens/weakens edges | Weights change appropriately |
| Checkpoint system | Model versioning | Can rollback if needed |
| Monitoring dashboard | Training metrics | Stats visible |
| A/B comparison | Old vs new system | Measurable improvement |

---

## 7. Data Migration Strategy

### 7.1 Profile Migration

```python
"""
Migration script: Convert JSON profiles to DNA embeddings.
"""

async def migrate_profiles():
    # 1. Load all existing profiles
    profiles = load_json_profiles("test_data/executive_profiles/")

    # 2. For each profile, generate DNA embedding
    for profile_id, profile_data in profiles.items():
        # 3. Load corresponding voiceprint
        voiceprint = load_voiceprint(profile_id)

        # 4. Encode to DNA
        dna = await dna_manager.encode_and_store(
            profile_id, profile_data, voiceprint
        )

        # 5. Create graph nodes and relationships
        await create_executive_graph_node(profile_id, profile_data)
        await create_value_relationships(profile_id, profile_data)
        await create_expert_affinities(profile_id, profile_data)

    # 6. Verify migration
    verify_migration()
```

### 7.2 Graph Migration

```cypher
// Migrate existing executive data to logic graph

// 1. Create executive nodes with DNA reference
MATCH (old:ExecutiveProfile)
CREATE (e:Executive {
    id: old.id,
    name: old.name,
    dna_pg_id: old.id  // Reference to PostgreSQL DNA
})

// 2. Create company and industry nodes
MATCH (e:Executive)
WITH e, e.company_name as company, e.industry as industry
MERGE (c:Company {name: company})
MERGE (i:Industry {id: toLower(replace(industry, ' ', '_'))})
CREATE (e)-[:WORKS_AT]->(c)
CREATE (c)-[:IN_INDUSTRY]->(i)

// 3. Create value relationships from profile
MATCH (e:Executive), (v:Value)
WHERE v.id IN e.core_values
CREATE (e)-[:HAS_VALUE {priority: index, personal_weight: 0.8}]->(v)

// 4. Create expert affinities from domain
MATCH (e:Executive), (ex:Expert)
WHERE ex.domain = e.primary_domain
CREATE (e)-[:PREFERS_EXPERT {affinity: 0.8}]->(ex)
```

---

## 8. Testing & Validation

### 8.1 Test Categories

| Category | Tests | Criteria |
|----------|-------|----------|
| **Unit Tests** | DNA encoding, graph traversal, MoE routing | 90%+ coverage |
| **Integration Tests** | Full routing pipeline | All paths work |
| **Regression Tests** | Compare old vs new output | <5% degradation |
| **Performance Tests** | Latency under load | <100ms routing overhead |
| **A/B Tests** | Live traffic comparison | Improvement in metrics |

### 8.2 Validation Metrics

```python
VALIDATION_METRICS = {
    # Quality
    "response_relevance": "RAGAS relevance score",
    "citation_accuracy": "% correct citations",
    "personality_consistency": "Style similarity to profile",

    # Performance
    "routing_latency_p50": "Median routing time",
    "routing_latency_p99": "99th percentile routing time",
    "total_latency_p50": "Median total response time",

    # Learning
    "feedback_positive_rate": "% positive feedback",
    "moe_loss_trend": "Training loss over time",
    "graph_weight_stability": "Edge weight variance"
}
```

---

## 9. Rollback Strategy

### 9.1 Feature Flags

```python
FEATURE_FLAGS = {
    "use_neural_routing": False,  # Start disabled
    "use_moe_experts": False,
    "use_adaptive_weights": False,
    "use_logic_graph": False,
    "learning_loop_enabled": False
}

# Gradual rollout
def get_routing_system(exec_id: str):
    if FEATURE_FLAGS["use_neural_routing"]:
        # Check if this exec is in rollout
        if is_in_rollout(exec_id, rollout_percent=10):
            return neural_router
    return legacy_router
```

### 9.2 Checkpoint Restoration

```python
async def rollback_to_checkpoint(checkpoint_timestamp: str):
    """Rollback all neural components to a checkpoint."""
    # 1. Stop learning loop
    await learning_loop.stop()

    # 2. Load checkpoint
    moe_router.load_checkpoint(f"checkpoints/moe_{checkpoint_timestamp}.pt")
    weight_predictor.load_checkpoint(f"checkpoints/weights_{checkpoint_timestamp}.pt")

    # 3. Restore graph weights
    await restore_graph_weights(checkpoint_timestamp)

    # 4. Clear caches
    await redis.flushdb()

    # 5. Restart services
    await restart_services()
```

---

## 10. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Neural routing degrades quality | Medium | High | A/B testing, gradual rollout |
| Learning loop causes drift | Medium | High | Checkpointing, monitoring |
| Graph traversal too slow | Low | Medium | Caching, query optimization |
| DNA encoding inconsistent | Low | Medium | Deterministic encoding, versioning |
| Feedback gaming | Low | Medium | Rate limiting, anomaly detection |
| Memory issues with large graphs | Medium | Medium | Pagination, streaming |

---

## Summary

This migration plan provides a comprehensive path from hardcoded rules to a neural-symbolic hybrid architecture:

1. **Phase 1 (Weeks 1-4)**: DNA embedding foundation
2. **Phase 2 (Weeks 5-8)**: Logic graph engine
3. **Phase 3 (Weeks 9-12)**: Neural routing & MoE
4. **Phase 4 (Weeks 13-16)**: Learning loop & optimization

The key principle: **Neural components handle soft patterns, symbolic rules handle hard constraints.**

This achieves:
- Scalability to 100+ executives without code changes
- Continuous improvement from feedback
- Maintained control over compliance and safety
- Gradual migration without breaking existing functionality
