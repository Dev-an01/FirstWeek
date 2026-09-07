# Neural Graph Cognitive Engine: Migration Plan

## Executive Summary

This document outlines the complete migration strategy from the current hardcoded RAG system to a scalable, learning-enabled "Neural Graph Cognitive Engine" architecture. The migration preserves existing strengths (reliability, control, debuggability) while adding neural components for scalability.

**Current State**: Single-executive system with 1600+ line JSON profiles, hardcoded routing rules, fixed weights, explicit voiceprints.

**Target State**: Multi-executive, multi-company system with learned embeddings, graph-driven behavior, MoE routing, and continuous learning.

**Migration Duration**: 4 phases over 16-20 weeks

---

## Table of Contents

1. [Current Architecture Analysis](#1-current-architecture-analysis)
2. [Target Architecture Design](#2-target-architecture-design)
3. [Phase 1: Foundation Layer](#3-phase-1-foundation-layer)
4. [Phase 2: Logic Graph Engine](#4-phase-2-logic-graph-engine)
5. [Phase 3: Neural Routing & MoE](#5-phase-3-neural-routing--moe)
6. [Phase 4: Learning Loop & Optimization](#6-phase-4-learning-loop--optimization)
7. [Data Migration Strategy](#7-data-migration-strategy)
8. [Testing & Validation](#8-testing--validation)
9. [Rollback Strategy](#9-rollback-strategy)
10. [Risk Assessment](#10-risk-assessment)

---

## 1. Current Architecture Analysis

### 1.1 Components That Will Be REPLACED

| Component | Location | Lines | Replacement |
|-----------|----------|-------|-------------|
| Profile JSON schemas | `test_data/executive_profiles/*.json` | ~1600/exec | DNA Embeddings |
| Voiceprint JSONs | `test_data/voiceprints/*.json` | ~400/exec | Style Encoder |
| ProfileManager.get_profile() | `profile_management/profile_manager.py` | 200+ | DNAManager |
| QueryRouter patterns | `hybrid_retrieval/query_router.py` | 150+ | MoE Gating Network |
| Fixed retrieval weights | `hybrid_retrieval/config.py` | 50+ | Adaptive Weight Network |
| ConversationalRouter patterns | `cognitive_twin/conversational_router.py` | 300+ | Intent Classifier |
| Hardcoded cognitive layers | `cognitive_twin/*.py` | 1000+ | Graph-Activated Rules |

### 1.2 Components That Will Be PRESERVED

| Component | Location | Reason |
|-----------|----------|--------|
| Prompt section structure | `conversation_engine/prompt/assembler.py` | Token budgeting essential |
| Section ordering (Reasoning→Instructions) | `conversation_engine/prompt/sections/` | Recency bias exploitation |
| Red flags / escalation triggers | `rules.py`, profile data | Compliance non-negotiable |
| Citation format requirements | `llm_integration/prompt_builder.py` | Business requirement |
| Anti-AI pattern blocklist | `rules.py` | Brand protection |
| LangGraph workflow skeleton | `langgraph_workflow/graph.py` | Proven orchestration |
| Neo4j infrastructure | `graph_context/` | Will be extended |
| pgvector infrastructure | `vector_search/` | Will be extended |

### 1.3 Current Data Flow (To Be Preserved)

```
Query → Analysis → Routing → Retrieval → Cognitive Layers → Prompt Assembly → LLM → Response
```

This flow remains the same. What changes is HOW each step makes decisions.

---

## 2. Target Architecture Design

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     NEURAL GRAPH COGNITIVE ENGINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    LAYER 1: DNA EMBEDDING SPACE                       │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │ │
│  │  │ Executive   │  │ Company     │  │ Industry    │  │ Query       │  │ │
│  │  │ DNA Encoder │  │ DNA Encoder │  │ Embedding   │  │ Encoder     │  │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │ │
│  │         │                │                │                │         │ │
│  │         └────────────────┴────────────────┴────────────────┘         │ │
│  │                              ↓                                        │ │
│  │                    UNIFIED EMBEDDING SPACE                            │ │
│  │                    (512-dim, cosine similarity)                       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    LAYER 2: LOGIC GRAPH ENGINE                        │ │
│  │                                                                       │ │
│  │    ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐   │ │
│  │    │Executive│──────│Company  │──────│Industry │──────│Cognitive│   │ │
│  │    │  Node   │      │  Node   │      │  Node   │      │  Rule   │   │ │
│  │    └─────────┘      └─────────┘      └─────────┘      └─────────┘   │ │
│  │         │                │                │                │         │ │
│  │         │    ACTIVATES_RULE (weighted edges)              │         │ │
│  │         └────────────────┴────────────────┴───────────────┘         │ │
│  │                                                                       │ │
│  │    Query → Traverse → Activated Rules → Prompt Injection             │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    LAYER 3: MoE ROUTING LAYER                         │ │
│  │                                                                       │ │
│  │    ┌─────────────────────────────────────────────────────────────┐   │ │
│  │    │              GATING NETWORK (Learned)                        │   │ │
│  │    │    Input: exec_dna ⊕ query_emb ⊕ activated_rules            │   │ │
│  │    │    Output: expert_weights [0.6, 0.2, 0.1, 0.1]              │   │ │
│  │    └─────────────────────────────────────────────────────────────┘   │ │
│  │                              ↓                                        │ │
│  │    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│  │    │Financial │ │Technical │ │Strategic │ │HR/People │ │Legal/    │ │ │
│  │    │Expert    │ │Expert    │ │Expert    │ │Expert    │ │Compliance│ │ │
│  │    └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    LAYER 4: ADAPTIVE RETRIEVAL                        │ │
│  │                                                                       │ │
│  │    ┌─────────────────────────────────────────────────────────────┐   │ │
│  │    │           WEIGHT PREDICTION NETWORK                          │   │ │
│  │    │    Input: exec_dna ⊕ query_type ⊕ expert_selection          │   │ │
│  │    │    Output: retrieval_weights {vector: 0.55, graph: 0.40,    │   │ │
│  │    │                               memory: 0.05}                  │   │ │
│  │    └─────────────────────────────────────────────────────────────┘   │ │
│  │                              ↓                                        │ │
│  │    ┌──────────┐      ┌──────────┐      ┌──────────┐                 │ │
│  │    │ Vector   │ w1   │  Graph   │ w2   │ Memory   │ w3              │ │
│  │    │ Search   │──────│ Context  │──────│ Search   │                 │ │
│  │    └──────────┘      └──────────┘      └──────────┘                 │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    LAYER 5: DYNAMIC PROMPT ASSEMBLY                   │ │
│  │                                                                       │ │
│  │    FIXED SKELETON:                                                    │ │
│  │    ┌────────────┐                                                    │ │
│  │    │ Reasoning  │ ← ALWAYS FIRST (cognitive script)                  │ │
│  │    ├────────────┤                                                    │ │
│  │    │ Identity   │ ← From DNA embedding → natural language            │ │
│  │    ├────────────┤                                                    │ │
│  │    │ [Dynamic]  │ ← Graph-activated rules injected here              │ │
│  │    │ [Dynamic]  │ ← Expert-specific content injected here            │ │
│  │    ├────────────┤                                                    │ │
│  │    │ Examples   │ ← Selected by similarity in embedding space        │ │
│  │    ├────────────┤                                                    │ │
│  │    │ Calibration│ ← Tone/length from DNA + situation                 │ │
│  │    ├────────────┤                                                    │ │
│  │    │Instructions│ ← ALWAYS LAST (anti-AI rules, citations)           │ │
│  │    └────────────┘                                                    │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    LAYER 6: SYMBOLIC GUARDRAILS                       │ │
│  │                    (NEVER OVERRIDDEN BY LEARNING)                     │ │
│  │                                                                       │ │
│  │    ┌─────────────────────────────────────────────────────────────┐   │ │
│  │    │ RED FLAGS          │ Compliance violations → BLOCK           │   │ │
│  │    │ ESCALATION         │ Legal/M&A/Ethics → FLAG                 │   │ │
│  │    │ IDENTITY OATH      │ "You ARE [name]" → ENFORCE              │   │ │
│  │    │ CITATION FORMAT    │ [Source: name] → VALIDATE               │   │ │
│  │    │ ANTI-AI PATTERNS   │ "I'd be happy to..." → REJECT           │   │ │
│  │    └─────────────────────────────────────────────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    LAYER 7: LEARNING LOOP                             │ │
│  │                                                                       │ │
│  │    Response → User Feedback → Update:                                 │ │
│  │    • DNA embeddings (fine-tune)                                       │ │
│  │    • Graph edge weights (strengthen/weaken)                           │ │
│  │    • Gating network (retrain)                                         │ │
│  │    • Weight prediction network (retrain)                              │ │
│  │    • Example selection model (retrain)                                │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 New Database Schema Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  POSTGRESQL (pgvector)                                                      │
│  ─────────────────────                                                      │
│  • executive_dna (id, embedding[512], metadata JSONB)                       │
│  • company_dna (id, embedding[512], metadata JSONB)                         │
│  • query_embeddings (id, embedding[512], query_text, created_at)            │
│  • style_embeddings (exec_id, style_vector[256], created_at)                │
│  • expert_prompts (expert_id, prompt_template, version)                     │
│  • feedback_signals (interaction_id, signal_type, value, created_at)        │
│  • model_checkpoints (model_name, version, weights BYTEA, metrics JSONB)    │
│                                                                             │
│  NEO4J (Logic Graph)                                                        │
│  ───────────────────                                                        │
│  Nodes:                                                                     │
│  • (:Executive {id, name, dna_embedding, company_id})                       │
│  • (:Company {id, name, industry_id, culture_embedding})                    │
│  • (:Industry {id, name, characteristics})                                  │
│  • (:CognitiveRule {id, category, prompt_injection, priority})              │
│  • (:Expert {id, name, domain, prompt_template_id})                         │
│  • (:Value {id, name, description, trade_off_dimensions})                   │
│  • (:RedFlag {id, category, condition, action})                             │
│                                                                             │
│  Relationships:                                                             │
│  • (Executive)-[:WORKS_AT {since, role}]->(Company)                         │
│  • (Company)-[:IN_INDUSTRY]->(Industry)                                     │
│  • (Industry)-[:ACTIVATES_RULE {weight, context}]->(CognitiveRule)          │
│  • (Executive)-[:HAS_VALUE {priority, weight}]->(Value)                     │
│  • (Executive)-[:PREFERS_EXPERT {affinity}]->(Expert)                       │
│  • (Value)-[:CONFLICTS_WITH {resolution}]->(Value)                          │
│  • (CognitiveRule)-[:GUARDED_BY]->(RedFlag)                                 │
│                                                                             │
│  REDIS (Caching)                                                            │
│  ───────────────                                                            │
│  • dna_cache:{exec_id} → embedding (TTL: 1 hour)                            │
│  • activated_rules:{exec_id}:{query_hash} → rules (TTL: 5 min)              │
│  • expert_selection:{exec_id}:{query_hash} → expert_id (TTL: 5 min)         │
│  • retrieval_weights:{exec_id}:{query_type} → weights (TTL: 30 min)         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 1: Foundation Layer (Weeks 1-4)

### 3.1 Objective
Build the DNA Embedding infrastructure and Executive Encoder without disrupting current system.

### 3.2 Components to Build

#### 3.2.1 Executive DNA Encoder

**Purpose**: Convert executive profile data into dense vector representations.

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTIVE DNA ENCODER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input: Executive Profile (structured or text)                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  TEXT ENCODER (Frozen)                                   │   │
│  │  Model: sentence-transformers/all-mpnet-base-v2          │   │
│  │  Output: 768-dim base embedding                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          ↓                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  PROJECTION HEAD (Trainable)                             │   │
│  │  768 → 512 → 512 (with LayerNorm, GELU)                  │   │
│  │  Output: 512-dim DNA embedding                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          ↓                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CONTRASTIVE LOSS (Training)                             │   │
│  │  Similar executives → close in space                     │   │
│  │  Different executives → far in space                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Output: executive_dna_embedding[512]                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**File**: `RAG/neural_engine/dna_encoder.py`

```python
"""
Executive DNA Encoder - Converts profiles to dense embeddings.

This module provides the foundation for the Neural Graph Cognitive Engine
by encoding executive profiles into a unified embedding space.
"""

import torch
import torch.nn as nn
from sentence_transformers import SentenceTransformer
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np


@dataclass
class DNAEncoderConfig:
    """Configuration for DNA Encoder."""
    base_model: str = "sentence-transformers/all-mpnet-base-v2"
    base_dim: int = 768
    projection_dim: int = 512
    dropout: float = 0.1
    normalize_embeddings: bool = True
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


class ProjectionHead(nn.Module):
    """
    Projection head that maps base embeddings to DNA space.

    Architecture:
        768 → 512 → LayerNorm → GELU → Dropout → 512 → LayerNorm
    """

    def __init__(self, config: DNAEncoderConfig):
        super().__init__()
        self.config = config

        self.projection = nn.Sequential(
            nn.Linear(config.base_dim, config.projection_dim),
            nn.LayerNorm(config.projection_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.projection_dim, config.projection_dim),
            nn.LayerNorm(config.projection_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        projected = self.projection(x)
        if self.config.normalize_embeddings:
            projected = nn.functional.normalize(projected, p=2, dim=-1)
        return projected


class ExecutiveDNAEncoder(nn.Module):
    """
    Encodes executive profiles into dense DNA embeddings.

    The encoder combines multiple profile aspects:
    - Communication style (formality, directness, warmth)
    - Decision patterns (risk tolerance, delegation preferences)
    - Values and priorities
    - Domain expertise
    - Industry context

    These are encoded into a unified 512-dim space where:
    - Similar executives cluster together
    - Industry patterns emerge naturally
    - Cross-executive knowledge transfer is possible via similarity
    """

    def __init__(self, config: Optional[DNAEncoderConfig] = None):
        super().__init__()
        self.config = config or DNAEncoderConfig()

        # Frozen base encoder
        self.base_encoder = SentenceTransformer(self.config.base_model)
        for param in self.base_encoder.parameters():
            param.requires_grad = False

        # Trainable projection head
        self.projection = ProjectionHead(self.config)

        self.to(self.config.device)

    def _profile_to_text(self, profile: Dict) -> str:
        """
        Convert structured profile to semantic text for embedding.

        This creates a rich text representation that captures:
        - Role and responsibilities
        - Communication preferences
        - Decision-making style
        - Values and priorities
        """
        sections = []

        # Identity
        name = profile.get('name_english', profile.get('name', 'Unknown'))
        title = profile.get('title', '')
        company = profile.get('company', {}).get('name', '')
        sections.append(f"{name} is {title} at {company}.")

        # Communication style
        comm = profile.get('communication_style', {})
        if comm:
            formality = comm.get('formality_scale', 5)
            directness = comm.get('directness_scale', 5)
            warmth = comm.get('warmth_scale', 5)

            style_desc = []
            if formality >= 7:
                style_desc.append("formal")
            elif formality <= 3:
                style_desc.append("casual")

            if directness >= 7:
                style_desc.append("direct")
            elif directness <= 3:
                style_desc.append("indirect")

            if warmth >= 7:
                style_desc.append("warm")
            elif warmth <= 3:
                style_desc.append("reserved")

            if style_desc:
                sections.append(f"Communication style: {', '.join(style_desc)}.")

            # Core principles
            principles = comm.get('core_principles', [])
            if principles:
                sections.append(f"Core principles: {', '.join(principles[:5])}.")

        # Decision making
        decision = profile.get('decision_making', {})
        if decision:
            risk = decision.get('risk_tolerance', 5)
            if risk >= 7:
                sections.append("High risk tolerance, comfortable with uncertainty.")
            elif risk <= 3:
                sections.append("Risk-averse, prefers careful analysis.")

            philosophy = decision.get('philosophy', '')
            if philosophy:
                sections.append(f"Decision philosophy: {philosophy[:200]}")

        # Values
        values = profile.get('core_values', [])
        if values:
            value_names = [v.get('name', '') for v in values[:5] if v.get('name')]
            if value_names:
                sections.append(f"Core values: {', '.join(value_names)}.")

        # Domain affinity
        domain = profile.get('domain_affinity', {})
        if domain:
            primary = domain.get('primary_domain', '')
            secondary = domain.get('secondary_domains', [])
            if primary:
                sections.append(f"Primary domain: {primary}.")
            if secondary:
                sections.append(f"Also experienced in: {', '.join(secondary[:3])}.")

        # Industry context
        company_info = profile.get('company', {})
        industry = company_info.get('industry', '')
        if industry:
            sections.append(f"Industry: {industry}.")

        return " ".join(sections)

    def encode_profile(self, profile: Dict) -> np.ndarray:
        """
        Encode a single executive profile to DNA embedding.

        Args:
            profile: Executive profile dictionary

        Returns:
            512-dim numpy array (normalized)
        """
        text = self._profile_to_text(profile)
        return self.encode_text(text)

    def encode_text(self, text: str) -> np.ndarray:
        """
        Encode text to DNA embedding.

        Args:
            text: Semantic description text

        Returns:
            512-dim numpy array (normalized)
        """
        with torch.no_grad():
            # Base encoding
            base_embedding = self.base_encoder.encode(
                text,
                convert_to_tensor=True,
                device=self.config.device
            )

            # Project to DNA space
            if base_embedding.dim() == 1:
                base_embedding = base_embedding.unsqueeze(0)

            dna_embedding = self.projection(base_embedding)

            return dna_embedding.squeeze(0).cpu().numpy()

    def encode_batch(self, profiles: List[Dict]) -> np.ndarray:
        """
        Encode multiple profiles efficiently.

        Args:
            profiles: List of executive profile dictionaries

        Returns:
            (N, 512) numpy array
        """
        texts = [self._profile_to_text(p) for p in profiles]

        with torch.no_grad():
            base_embeddings = self.base_encoder.encode(
                texts,
                convert_to_tensor=True,
                device=self.config.device,
                batch_size=32
            )

            dna_embeddings = self.projection(base_embeddings)

            return dna_embeddings.cpu().numpy()

    def similarity(self, dna1: np.ndarray, dna2: np.ndarray) -> float:
        """
        Compute cosine similarity between two DNA embeddings.

        Args:
            dna1: First DNA embedding (512-dim)
            dna2: Second DNA embedding (512-dim)

        Returns:
            Cosine similarity score (-1 to 1)
        """
        return float(np.dot(dna1, dna2))

    def find_similar(
        self,
        query_dna: np.ndarray,
        candidate_dnas: np.ndarray,
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Find most similar executives by DNA.

        Args:
            query_dna: Query DNA embedding (512-dim)
            candidate_dnas: Candidate embeddings (N, 512)
            top_k: Number of results

        Returns:
            List of (index, similarity) tuples
        """
        similarities = np.dot(candidate_dnas, query_dna)
        top_indices = np.argsort(similarities)[::-1][:top_k]

        return [(int(idx), float(similarities[idx])) for idx in top_indices]


class StyleEncoder(nn.Module):
    """
    Encodes communication style separately for fine-grained control.

    This captures the "voice" aspects:
    - Signature openers/closers
    - Emoji usage patterns
    - Formality markers
    - Tone characteristics

    Output: 256-dim style vector
    """

    def __init__(self, config: Optional[DNAEncoderConfig] = None):
        super().__init__()
        self.config = config or DNAEncoderConfig()

        self.base_encoder = SentenceTransformer(self.config.base_model)
        for param in self.base_encoder.parameters():
            param.requires_grad = False

        self.projection = nn.Sequential(
            nn.Linear(self.config.base_dim, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Linear(256, 256),
            nn.LayerNorm(256)
        )

        self.to(self.config.device)

    def _voiceprint_to_text(self, voiceprint: Dict) -> str:
        """Convert voiceprint to semantic text."""
        sections = []

        # Signature opener
        opener = voiceprint.get('signature_opener', {})
        if opener:
            pattern = opener.get('pattern', '')
            examples = opener.get('examples', [])
            if pattern:
                sections.append(f"Opens conversations with {pattern} style.")
            if examples:
                sections.append(f"Example openers: {', '.join(examples[:3])}")

        # Decision cadence
        cadence = voiceprint.get('decision_cadence', {})
        if cadence:
            pattern = cadence.get('pattern', '')
            if pattern:
                sections.append(f"Expresses decisions using {pattern}.")

        # Style markers
        markers = voiceprint.get('style_markers', {})
        if markers:
            formality = markers.get('formality', 5)
            directness = markers.get('directness', 5)
            warmth = markers.get('warmth', 5)
            emoji = markers.get('emoji_usage', 'rarely')

            sections.append(
                f"Style: formality {formality}/10, directness {directness}/10, "
                f"warmth {warmth}/10, uses emojis {emoji}."
            )

        # Sign-off
        signoff = voiceprint.get('sign_off_patterns', {})
        if signoff:
            pattern = signoff.get('pattern', '')
            if pattern:
                sections.append(f"Closes with {pattern} style.")

        return " ".join(sections)

    def encode_voiceprint(self, voiceprint: Dict) -> np.ndarray:
        """
        Encode voiceprint to style embedding.

        Args:
            voiceprint: Voiceprint dictionary

        Returns:
            256-dim numpy array
        """
        text = self._voiceprint_to_text(voiceprint)

        with torch.no_grad():
            base_embedding = self.base_encoder.encode(
                text,
                convert_to_tensor=True,
                device=self.config.device
            )

            if base_embedding.dim() == 1:
                base_embedding = base_embedding.unsqueeze(0)

            style_embedding = self.projection(base_embedding)
            style_embedding = nn.functional.normalize(style_embedding, p=2, dim=-1)

            return style_embedding.squeeze(0).cpu().numpy()
```

#### 3.2.2 DNA Manager Service

**Purpose**: Manage DNA embeddings with caching and persistence.

**File**: `RAG/neural_engine/dna_manager.py`

```python
"""
DNA Manager - Manages executive DNA embeddings.

Provides:
- Embedding storage and retrieval
- Caching layer
- Similarity search
- Batch operations
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import asyncpg
import redis.asyncio as redis

from .dna_encoder import ExecutiveDNAEncoder, StyleEncoder, DNAEncoderConfig


logger = logging.getLogger(__name__)


class DNAManager:
    """
    Manages executive DNA embeddings with caching and persistence.

    Architecture:
        Request → Redis Cache → PostgreSQL → Encoder (if miss)

    Features:
        - Lazy encoding on first request
        - Cache with configurable TTL
        - Batch encoding for efficiency
        - Similarity search via pgvector
    """

    def __init__(
        self,
        pg_pool: asyncpg.Pool,
        redis_client: redis.Redis,
        encoder_config: Optional[DNAEncoderConfig] = None,
        cache_ttl: int = 3600  # 1 hour
    ):
        self.pg_pool = pg_pool
        self.redis = redis_client
        self.cache_ttl = cache_ttl

        # Initialize encoders
        self.dna_encoder = ExecutiveDNAEncoder(encoder_config)
        self.style_encoder = StyleEncoder(encoder_config)

        logger.info("DNAManager initialized")

    async def initialize_schema(self):
        """Create required database tables."""
        async with self.pg_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS executive_dna (
                    id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    dna_embedding vector(512) NOT NULL,
                    style_embedding vector(256),
                    metadata JSONB DEFAULT '{}',
                    profile_hash VARCHAR(64),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_executive_dna_embedding
                ON executive_dna USING ivfflat (dna_embedding vector_cosine_ops)
                WITH (lists = 100);

                CREATE TABLE IF NOT EXISTS company_dna (
                    id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    industry VARCHAR(255),
                    dna_embedding vector(512) NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_company_dna_embedding
                ON company_dna USING ivfflat (dna_embedding vector_cosine_ops)
                WITH (lists = 50);
            """)

        logger.info("DNA schema initialized")

    def _cache_key(self, exec_id: str) -> str:
        """Generate cache key for executive DNA."""
        return f"dna:exec:{exec_id}"

    def _profile_hash(self, profile: Dict) -> str:
        """Generate hash of profile for change detection."""
        # Sort keys for consistent hashing
        profile_str = json.dumps(profile, sort_keys=True, default=str)
        return hashlib.sha256(profile_str.encode()).hexdigest()[:16]

    async def get_dna(self, exec_id: str) -> Optional[np.ndarray]:
        """
        Get DNA embedding for executive.

        Checks:
        1. Redis cache
        2. PostgreSQL

        Returns None if not found (caller should encode).
        """
        # Check cache
        cache_key = self._cache_key(exec_id)
        cached = await self.redis.get(cache_key)
        if cached:
            return np.frombuffer(cached, dtype=np.float32)

        # Check database
        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT dna_embedding FROM executive_dna WHERE id = $1",
                exec_id
            )

            if row:
                embedding = np.array(row['dna_embedding'], dtype=np.float32)

                # Populate cache
                await self.redis.setex(
                    cache_key,
                    self.cache_ttl,
                    embedding.tobytes()
                )

                return embedding

        return None

    async def encode_and_store(
        self,
        exec_id: str,
        profile: Dict,
        voiceprint: Optional[Dict] = None
    ) -> np.ndarray:
        """
        Encode executive profile and store DNA embedding.

        Args:
            exec_id: Executive ID
            profile: Executive profile dictionary
            voiceprint: Optional voiceprint dictionary

        Returns:
            512-dim DNA embedding
        """
        # Encode profile
        dna_embedding = self.dna_encoder.encode_profile(profile)

        # Encode style if voiceprint provided
        style_embedding = None
        if voiceprint:
            style_embedding = self.style_encoder.encode_voiceprint(voiceprint)

        # Store in database
        profile_hash = self._profile_hash(profile)
        name = profile.get('name_english', profile.get('name', exec_id))

        metadata = {
            'title': profile.get('title', ''),
            'company': profile.get('company', {}).get('name', ''),
            'industry': profile.get('company', {}).get('industry', ''),
            'encoded_at': datetime.utcnow().isoformat()
        }

        async with self.pg_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO executive_dna
                (id, name, dna_embedding, style_embedding, metadata, profile_hash, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    dna_embedding = EXCLUDED.dna_embedding,
                    style_embedding = EXCLUDED.style_embedding,
                    metadata = EXCLUDED.metadata,
                    profile_hash = EXCLUDED.profile_hash,
                    updated_at = NOW()
            """,
                exec_id,
                name,
                dna_embedding.tolist(),
                style_embedding.tolist() if style_embedding is not None else None,
                json.dumps(metadata),
                profile_hash
            )

        # Update cache
        cache_key = self._cache_key(exec_id)
        await self.redis.setex(
            cache_key,
            self.cache_ttl,
            dna_embedding.tobytes()
        )

        logger.info(f"Encoded and stored DNA for {exec_id}")

        return dna_embedding

    async def find_similar_executives(
        self,
        query_dna: np.ndarray,
        top_k: int = 5,
        exclude_ids: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Find executives with similar DNA embeddings.

        Args:
            query_dna: 512-dim query embedding
            top_k: Number of results
            exclude_ids: IDs to exclude from results

        Returns:
            List of {id, name, similarity, metadata}
        """
        exclude_ids = exclude_ids or []

        async with self.pg_pool.acquire() as conn:
            # Use pgvector cosine distance
            rows = await conn.fetch("""
                SELECT
                    id,
                    name,
                    1 - (dna_embedding <=> $1::vector) as similarity,
                    metadata
                FROM executive_dna
                WHERE id != ALL($2)
                ORDER BY dna_embedding <=> $1::vector
                LIMIT $3
            """,
                query_dna.tolist(),
                exclude_ids,
                top_k
            )

            return [
                {
                    'id': row['id'],
                    'name': row['name'],
                    'similarity': float(row['similarity']),
                    'metadata': json.loads(row['metadata']) if row['metadata'] else {}
                }
                for row in rows
            ]

    async def check_profile_changed(self, exec_id: str, profile: Dict) -> bool:
        """
        Check if profile has changed since last encoding.

        Useful for deciding whether to re-encode.
        """
        new_hash = self._profile_hash(profile)

        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT profile_hash FROM executive_dna WHERE id = $1",
                exec_id
            )

            if not row:
                return True  # Not encoded yet

            return row['profile_hash'] != new_hash

    async def invalidate_cache(self, exec_id: str):
        """Invalidate cached DNA for executive."""
        cache_key = self._cache_key(exec_id)
        await self.redis.delete(cache_key)
        logger.info(f"Invalidated DNA cache for {exec_id}")

    async def batch_encode(
        self,
        profiles: List[Tuple[str, Dict, Optional[Dict]]]
    ) -> Dict[str, np.ndarray]:
        """
        Batch encode multiple executives.

        Args:
            profiles: List of (exec_id, profile, voiceprint) tuples

        Returns:
            Dict mapping exec_id to DNA embedding
        """
        results = {}

        # Encode in batches
        batch_size = 32
        for i in range(0, len(profiles), batch_size):
            batch = profiles[i:i + batch_size]

            # Parallel encoding
            tasks = [
                self.encode_and_store(exec_id, profile, voiceprint)
                for exec_id, profile, voiceprint in batch
            ]

            embeddings = await asyncio.gather(*tasks)

            for (exec_id, _, _), embedding in zip(batch, embeddings):
                results[exec_id] = embedding

        logger.info(f"Batch encoded {len(profiles)} executives")

        return results

    async def get_all_embeddings(self) -> Dict[str, np.ndarray]:
        """
        Get all executive DNA embeddings.

        Useful for clustering analysis and visualization.
        """
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, dna_embedding FROM executive_dna"
            )

            return {
                row['id']: np.array(row['dna_embedding'], dtype=np.float32)
                for row in rows
            }
```

#### 3.2.3 Database Migrations

**File**: `RAG/config/migrations/001_neural_engine_foundation.sql`

```sql
-- Migration: Neural Engine Foundation
-- Phase 1: DNA Embedding Infrastructure

-- Enable pgvector extension if not exists
CREATE EXTENSION IF NOT EXISTS vector;

-- Executive DNA embeddings table
CREATE TABLE IF NOT EXISTS executive_dna (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    dna_embedding vector(512) NOT NULL,
    style_embedding vector(256),
    metadata JSONB DEFAULT '{}',
    profile_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for similarity search (IVFFlat for large scale)
CREATE INDEX IF NOT EXISTS idx_executive_dna_embedding
ON executive_dna USING ivfflat (dna_embedding vector_cosine_ops)
WITH (lists = 100);

-- Index for style embedding similarity
CREATE INDEX IF NOT EXISTS idx_executive_style_embedding
ON executive_dna USING ivfflat (style_embedding vector_cosine_ops)
WITH (lists = 50);

-- Company DNA embeddings table
CREATE TABLE IF NOT EXISTS company_dna (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(255),
    dna_embedding vector(512) NOT NULL,
    culture_embedding vector(256),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_dna_embedding
ON company_dna USING ivfflat (dna_embedding vector_cosine_ops)
WITH (lists = 50);

-- Query embeddings for analysis
CREATE TABLE IF NOT EXISTS query_embeddings (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_embedding vector(512) NOT NULL,
    exec_id VARCHAR(255) REFERENCES executive_dna(id),
    query_type VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_embedding
ON query_embeddings USING ivfflat (query_embedding vector_cosine_ops)
WITH (lists = 100);

-- Feedback signals for learning
CREATE TABLE IF NOT EXISTS feedback_signals (
    id SERIAL PRIMARY KEY,
    interaction_id VARCHAR(255) NOT NULL,
    exec_id VARCHAR(255) REFERENCES executive_dna(id),
    signal_type VARCHAR(50) NOT NULL, -- 'thumbs_up', 'thumbs_down', 'edit', 'implicit'
    signal_value FLOAT DEFAULT 1.0,
    query_text TEXT,
    response_text TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_exec ON feedback_signals(exec_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_feedback_time ON feedback_signals(created_at);

-- Model checkpoints for versioning
CREATE TABLE IF NOT EXISTS model_checkpoints (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    checkpoint_path TEXT,
    metrics JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(model_name, version)
);

-- DNA similarity cache (materialized view for common queries)
CREATE MATERIALIZED VIEW IF NOT EXISTS executive_similarity_matrix AS
SELECT
    e1.id as exec1_id,
    e2.id as exec2_id,
    1 - (e1.dna_embedding <=> e2.dna_embedding) as similarity
FROM executive_dna e1
CROSS JOIN executive_dna e2
WHERE e1.id < e2.id
AND 1 - (e1.dna_embedding <=> e2.dna_embedding) > 0.5;

CREATE UNIQUE INDEX IF NOT EXISTS idx_similarity_matrix_pair
ON executive_similarity_matrix(exec1_id, exec2_id);

-- Function to refresh similarity matrix
CREATE OR REPLACE FUNCTION refresh_similarity_matrix()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY executive_similarity_matrix;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_executive_dna_updated
BEFORE UPDATE ON executive_dna
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_company_dna_updated
BEFORE UPDATE ON company_dna
FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### 3.3 Integration with Current System

**File**: `RAG/neural_engine/compatibility_layer.py`

```python
"""
Compatibility Layer - Bridges old ProfileManager with new DNAManager.

This allows gradual migration without breaking existing code.
"""

import logging
from typing import Dict, Optional
import numpy as np

from profile_management.profile_manager import ProfileManager
from .dna_manager import DNAManager


logger = logging.getLogger(__name__)


class HybridProfileManager:
    """
    Hybrid manager that provides both old and new interfaces.

    Usage:
        # Old code continues to work
        profile = manager.get_profile("sample_profile")

        # New code can use DNA
        dna = await manager.get_dna("sample_profile")
        similar = await manager.find_similar("sample_profile")
    """

    def __init__(
        self,
        profile_manager: ProfileManager,
        dna_manager: DNAManager
    ):
        self.profile_manager = profile_manager
        self.dna_manager = dna_manager
        self._initialized = False

    async def initialize(self):
        """Initialize and sync DNA embeddings with existing profiles."""
        if self._initialized:
            return

        # Get all existing profiles
        profiles = self.profile_manager.get_all_profiles()

        # Encode any missing DNA
        for exec_id, profile in profiles.items():
            existing_dna = await self.dna_manager.get_dna(exec_id)

            if existing_dna is None:
                logger.info(f"Encoding DNA for existing profile: {exec_id}")
                voiceprint = profile.get('voiceprint', {})
                await self.dna_manager.encode_and_store(exec_id, profile, voiceprint)
            else:
                # Check if profile changed
                if await self.dna_manager.check_profile_changed(exec_id, profile):
                    logger.info(f"Re-encoding DNA for changed profile: {exec_id}")
                    voiceprint = profile.get('voiceprint', {})
                    await self.dna_manager.encode_and_store(exec_id, profile, voiceprint)

        self._initialized = True
        logger.info(f"HybridProfileManager initialized with {len(profiles)} profiles")

    # ==================== OLD INTERFACE (Preserved) ====================

    def get_profile(self, executive_id: str) -> Optional[Dict]:
        """Get profile (old interface)."""
        return self.profile_manager.get_profile(executive_id)

    def get_all_profiles(self) -> Dict[str, Dict]:
        """Get all profiles (old interface)."""
        return self.profile_manager.get_all_profiles()

    def reload_profile(self, executive_id: str):
        """Reload profile and update DNA."""
        self.profile_manager.reload_profile(executive_id)
        # Will re-encode DNA on next get_dna call due to hash check

    # ==================== NEW INTERFACE (DNA-based) ====================

    async def get_dna(self, executive_id: str) -> Optional[np.ndarray]:
        """Get DNA embedding for executive."""
        dna = await self.dna_manager.get_dna(executive_id)

        if dna is None:
            # Lazy encode from profile
            profile = self.get_profile(executive_id)
            if profile:
                voiceprint = profile.get('voiceprint', {})
                dna = await self.dna_manager.encode_and_store(
                    executive_id, profile, voiceprint
                )

        return dna

    async def find_similar(
        self,
        executive_id: str,
        top_k: int = 5
    ) -> list:
        """Find executives similar to given one."""
        dna = await self.get_dna(executive_id)
        if dna is None:
            return []

        return await self.dna_manager.find_similar_executives(
            dna, top_k, exclude_ids=[executive_id]
        )

    async def get_dna_with_profile(
        self,
        executive_id: str
    ) -> Optional[Dict]:
        """
        Get profile enhanced with DNA embedding.

        Returns profile dict with additional 'dna_embedding' field.
        """
        profile = self.get_profile(executive_id)
        if not profile:
            return None

        dna = await self.get_dna(executive_id)

        return {
            **profile,
            'dna_embedding': dna.tolist() if dna is not None else None
        }
```

### 3.4 Phase 1 Deliverables

| Deliverable | Description | Success Criteria |
|-------------|-------------|------------------|
| `ExecutiveDNAEncoder` | Encodes profiles to 512-dim vectors | Similarity test: similar execs cluster |
| `StyleEncoder` | Encodes voiceprints to 256-dim vectors | Style similarity correlates with human judgment |
| `DNAManager` | Manages embeddings with caching | <10ms retrieval with cache hit |
| Database migrations | pgvector tables for DNA storage | All tables created, indexes working |
| `HybridProfileManager` | Compatibility layer | Old code works unchanged |
| Unit tests | Test coverage for new components | 90%+ coverage |
| Integration tests | End-to-end DNA flow | Profile → DNA → Similar executives |

### 3.5 Phase 1 Testing Plan

```python
# File: RAG/tests/test_dna_encoder.py

import pytest
import numpy as np
from neural_engine.dna_encoder import ExecutiveDNAEncoder, StyleEncoder


class TestExecutiveDNAEncoder:
    """Tests for DNA encoding."""

    @pytest.fixture
    def encoder(self):
        return ExecutiveDNAEncoder()

    @pytest.fixture
    def sample_profile(self):
        """Sample sample profile."""
        return {
            "name_english": "Sample Executive",
            "title": "CEO",
            "company": {"name": "Example Company", "industry": "AI_Startup"},
            "communication_style": {
                "formality_scale": 6,
                "directness_scale": 8,
                "warmth_scale": 7,
                "core_principles": ["soft_assertion", "context_before_direction"]
            },
            "decision_making": {
                "risk_tolerance": 8,
                "philosophy": "Speed over perfection, data-driven decisions"
            },
            "core_values": [
                {"name": "Transparency"},
                {"name": "Speed"},
                {"name": "Delegation"}
            ],
            "domain_affinity": {
                "primary_domain": "Technology",
                "secondary_domains": ["Strategy", "Leadership"]
            }
        }

    @pytest.fixture
    def similar_profile(self):
        """Profile similar to sample (tech startup CEO)."""
        return {
            "name_english": "Tech Startup CEO",
            "title": "CEO",
            "company": {"name": "TechCorp", "industry": "AI_Startup"},
            "communication_style": {
                "formality_scale": 5,
                "directness_scale": 9,
                "warmth_scale": 6
            },
            "decision_making": {
                "risk_tolerance": 9,
                "philosophy": "Move fast and iterate"
            },
            "core_values": [
                {"name": "Speed"},
                {"name": "Innovation"}
            ],
            "domain_affinity": {
                "primary_domain": "Technology"
            }
        }

    @pytest.fixture
    def different_profile(self):
        """Profile different from sample (conservative CFO)."""
        return {
            "name_english": "Conservative CFO",
            "title": "CFO",
            "company": {"name": "BigBank", "industry": "Finance"},
            "communication_style": {
                "formality_scale": 9,
                "directness_scale": 4,
                "warmth_scale": 3
            },
            "decision_making": {
                "risk_tolerance": 2,
                "philosophy": "Careful analysis before any decision"
            },
            "core_values": [
                {"name": "Compliance"},
                {"name": "Risk Management"}
            ],
            "domain_affinity": {
                "primary_domain": "Finance"
            }
        }

    def test_encoding_produces_correct_shape(self, encoder, sample_profile):
        """Test that encoding produces 512-dim vector."""
        dna = encoder.encode_profile(sample_profile)
        assert dna.shape == (512,)

    def test_encoding_is_normalized(self, encoder, sample_profile):
        """Test that embeddings are L2 normalized."""
        dna = encoder.encode_profile(sample_profile)
        norm = np.linalg.norm(dna)
        assert abs(norm - 1.0) < 0.001

    def test_similar_profiles_have_high_similarity(
        self, encoder, sample_profile, similar_profile
    ):
        """Test that similar executives cluster together."""
        dna1 = encoder.encode_profile(sample_profile)
        dna2 = encoder.encode_profile(similar_profile)

        similarity = encoder.similarity(dna1, dna2)

        # Similar profiles should have high similarity
        assert similarity > 0.7

    def test_different_profiles_have_lower_similarity(
        self, encoder, sample_profile, different_profile
    ):
        """Test that different executives are far apart."""
        dna1 = encoder.encode_profile(sample_profile)
        dna2 = encoder.encode_profile(different_profile)

        similarity = encoder.similarity(dna1, dna2)

        # Different profiles should have lower similarity
        assert similarity < 0.6

    def test_encoding_is_deterministic(self, encoder, sample_profile):
        """Test that same profile always produces same embedding."""
        dna1 = encoder.encode_profile(sample_profile)
        dna2 = encoder.encode_profile(sample_profile)

        np.testing.assert_array_almost_equal(dna1, dna2, decimal=5)

    def test_batch_encoding(self, encoder, sample_profile, similar_profile):
        """Test batch encoding produces correct results."""
        embeddings = encoder.encode_batch([sample_profile, similar_profile])

        assert embeddings.shape == (2, 512)

        # Should match individual encoding
        individual1 = encoder.encode_profile(sample_profile)
        np.testing.assert_array_almost_equal(embeddings[0], individual1, decimal=5)

    def test_find_similar(
        self, encoder, sample_profile, similar_profile, different_profile
    ):
        """Test finding similar executives."""
        query_dna = encoder.encode_profile(sample_profile)
        candidates = encoder.encode_batch([similar_profile, different_profile])

        results = encoder.find_similar(query_dna, candidates, top_k=2)

        # Similar profile should rank first
        assert results[0][0] == 0  # Index of similar_profile
        assert results[0][1] > results[1][1]  # Higher similarity
```

---

## 4. Phase 2: Logic Graph Engine (Weeks 5-8)

### 4.1 Objective
Transform Neo4j from data storage to behavior controller by adding cognitive rules as nodes and activation relationships.

### 4.2 Logic Graph Schema
