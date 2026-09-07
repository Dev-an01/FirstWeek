# Neural Graph Cognitive Engine: Migration Summary

## Quick Reference Guide

### What We're Building

```
CURRENT STATE                          TARGET STATE
─────────────                          ────────────
Hardcoded JSON profiles (1600 lines)   → DNA embeddings (512-dim vectors)
if/else routing patterns               → Learned MoE gating network
Fixed 60/40/10 weights                 → Adaptive weight prediction
6 hardcoded cognitive layers           → Graph-activated rule injection
Manual voiceprint rules                → Style encoder + transfer
No learning from feedback              → Continuous learning loop
```

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                 NEURAL GRAPH COGNITIVE ENGINE                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Layer 1: DNA EMBEDDINGS                                            │
│  ├─ Executive profiles → 512-dim vectors                            │
│  ├─ Similar executives cluster automatically                        │
│  └─ New exec onboarding: 50 samples → embedding                     │
│                                                                     │
│  Layer 2: LOGIC GRAPH (Neo4j)                                       │
│  ├─ Rules encoded as nodes                                          │
│  ├─ Industry → Rule edges with weights                              │
│  └─ Behavior emerges from traversal, not code                       │
│                                                                     │
│  Layer 3: MoE ROUTING                                               │
│  ├─ Gating network selects experts                                  │
│  ├─ Top-k sparse selection                                          │
│  └─ Learns from user feedback                                       │
│                                                                     │
│  Layer 4: ADAPTIVE WEIGHTS                                          │
│  ├─ Predicts vector/graph/memory weights                            │
│  ├─ Context-aware retrieval                                         │
│  └─ Updates from feedback                                           │
│                                                                     │
│  Layer 5: DYNAMIC PROMPT ASSEMBLY                                   │
│  ├─ Fixed skeleton (preserved from current)                         │
│  ├─ Dynamic content from graph activation                           │
│  └─ Token budgets enforced                                          │
│                                                                     │
│  Layer 6: SYMBOLIC GUARDRAILS                                       │
│  ├─ Red flags (NEVER overridden)                                    │
│  ├─ Escalation triggers                                             │
│  └─ Citation requirements                                           │
│                                                                     │
│  Layer 7: LEARNING LOOP                                             │
│  ├─ Collects feedback signals                                       │
│  ├─ Updates neural components                                       │
│  └─ Strengthens/weakens graph edges                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Principle

> **Neural components handle SOFT patterns (style, routing, weights)**
> **Symbolic rules handle HARD constraints (compliance, safety, identity)**

### Migration Phases

| Phase | Weeks | Focus | Key Deliverables |
|-------|-------|-------|------------------|
| **1** | 1-4 | Foundation | DNA Encoder, DNA Manager, Database migrations |
| **2** | 5-8 | Logic Graph | Graph schema, Rule activation, Prompt injection |
| **3** | 9-12 | Neural Routing | MoE system, Adaptive weights, Unified router |
| **4** | 13-16 | Learning | Feedback collection, Training loop, Optimization |

### Files Created

| File | Description |
|------|-------------|
| `NEURAL_GRAPH_MIGRATION_PLAN.md` | Part 1: Overview, Architecture, Phase 1 details |
| `NEURAL_GRAPH_MIGRATION_PLAN_PART2.md` | Part 2: Logic Graph, Neo4j schema, Phase 2 details |
| `NEURAL_GRAPH_MIGRATION_PLAN_PART3.md` | Part 3: MoE, Adaptive Weights, Learning Loop |

### New Code Structure

```
RAG/neural_engine/
├── __init__.py
├── dna_encoder.py           # Executive DNA + Style encoding
├── dna_manager.py           # DNA storage, caching, similarity
├── logic_graph_provider.py  # Graph traversal for rule activation
├── moe_router.py            # Mixture of Experts implementation
├── adaptive_weights.py      # Learned retrieval weights
├── neural_router.py         # Unified routing interface
├── feedback_collector.py    # Feedback signal collection
├── learning_loop.py         # Continuous learning orchestration
└── compatibility_layer.py   # Bridge to existing ProfileManager

RAG/config/migrations/
└── 001_neural_engine_foundation.sql  # Database schema

RAG/init-scripts/
└── initialize_logic_graph.py  # Populate Neo4j with rules
```

### Database Changes

**PostgreSQL (new tables)**:
- `executive_dna` - DNA embeddings with pgvector index
- `company_dna` - Company embeddings
- `query_embeddings` - Query history for analysis
- `feedback_signals` - User feedback collection
- `model_checkpoints` - Model versioning

**Neo4j (new node types)**:
- `:CognitiveRule` - Behavioral rules
- `:Expert` - Domain experts
- `:Value` - Core values
- `:RedFlag` - Hard constraints

**Neo4j (new relationships)**:
- `ACTIVATES_RULE` - Industry → Rule with weight
- `HAS_VALUE` - Executive → Value with priority
- `PREFERS_EXPERT` - Executive → Expert affinity
- `GUARDED_BY` - Rule → RedFlag protection

### Feature Flags for Rollout

```python
FEATURE_FLAGS = {
    "use_neural_routing": False,      # Phase 3
    "use_moe_experts": False,         # Phase 3
    "use_adaptive_weights": False,    # Phase 3
    "use_logic_graph": False,         # Phase 2
    "learning_loop_enabled": False,   # Phase 4
    "rollout_percent": 0              # Gradual rollout
}
```

### Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| New executive onboarding | Weeks (manual JSON) | Hours (50 samples) |
| Code changes for new industry | ~500 lines | 0 (graph config) |
| Response quality (RAGAS) | Baseline | No degradation |
| Routing latency overhead | N/A | <100ms |
| Feedback-driven improvement | None | Measurable |

### Risk Mitigations

1. **Quality degradation** → A/B testing, gradual rollout
2. **Learning drift** → Checkpointing, monitoring
3. **Performance issues** → Caching, pagination
4. **Breaking changes** → Compatibility layer, feature flags

### Next Steps

1. Review and approve plan
2. Set up development environment
3. Implement Phase 1 (DNA Foundation)
4. Create test fixtures
5. Begin integration testing

---

## Quick Commands

```bash
# Run database migrations
python -m alembic upgrade head

# Initialize logic graph
python RAG/init-scripts/initialize_logic_graph.py

# Migrate existing profiles to DNA
python RAG/init-scripts/migrate_profiles_to_dna.py

# Run tests
pytest RAG/tests/test_neural_engine/ -v

# Start learning loop (background)
python -m RAG.neural_engine.learning_loop --daemon
```

---

*This migration transforms the RAG system from a hardcoded, single-executive system to a scalable, learning-enabled multi-executive platform while preserving reliability and control.*
