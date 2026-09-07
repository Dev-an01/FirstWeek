# QUERY-TO-RESPONSE FLOWCHART - PART 3 (FINAL)

## Continuation from Cognitive Enhancement...

```
                                         │
                                         ▼
╔═════════════════════════════════════════════════════════════════════════════════╗
║                   ⑮ NODE: GENERATE_STANDARD (LLM Generation)                    ║
╚═════════════════════════════════════════════════════════════════════════════════╝
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  File: langgraph_workflow/nodes.py:generate_standard()                          │
│  ────────────────────────────────────────────────────────────────────────────── │
│  Decision: Use ConversationEngine? TRUE ✓                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
╔═════════════════════════════════════════════════════════════════════════════════╗
║              CONVERSATIONENGINE 5-STAGE PIPELINE                                ║
║  File: conversation_engine/engine.py:generate()                                 ║
╚═════════════════════════════════════════════════════════════════════════════════╝
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    STAGE 1: CONTEXT ANALYSIS                                     │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: conversation_engine/context/analyzer.py                           │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  INPUT:                                                                   │  │
│  │    • query: "What are sample-san's thoughts on technical debt?"           │  │
│  │    • conversation_history: [2 previous turns]                             │  │
│  │    • situation_analysis: {tone: "neutral", urgency: "low", ...}           │  │
│  │                                                                           │  │
│  │  ANALYSIS DIMENSIONS:                                                     │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ 1. THEME CLASSIFICATION                                           │   │  │
│  │  │    ────────────────────                                           │   │  │
│  │  │    Analyze content domain:                                        │   │  │
│  │  │      • "technical debt" → TECHNICAL ✓                             │   │  │
│  │  │      • Not about business metrics → not BUSINESS                  │   │  │
│  │  │      • Not about company strategy → not STRATEGIC                 │   │  │
│  │  │      • "thoughts" suggests high-level → STRATEGIC tinge           │   │  │
│  │  │                                                                    │   │  │
│  │  │    RESULT: theme = "technical"                                    │   │  │
│  │  │                                                                    │   │  │
│  │  │ 2. URGENCY DETECTION                                              │   │  │
│  │  │    ────────────────────                                           │   │  │
│  │  │    Keywords: none                                                 │   │  │
│  │  │    History context: no pressing issues                            │   │  │
│  │  │    Query structure: exploratory                                   │   │  │
│  │  │                                                                    │   │  │
│  │  │    RESULT: urgency = "low"                                        │   │  │
│  │  │                                                                    │   │  │
│  │  │ 3. EMOTION DETECTION                                              │   │  │
│  │  │    ────────────────────                                           │   │  │
│  │  │    Sentiment analysis: 0.05 (neutral)                             │   │  │
│  │  │    Emotion markers: none                                          │   │  │
│  │  │                                                                    │   │  │
│  │  │    RESULT: emotion = "neutral"                                    │   │  │
│  │  │                                                                    │   │  │
│  │  │ 4. TURN TYPE CLASSIFICATION                                       │   │  │
│  │  │    ────────────────────────                                       │   │  │
│  │  │    Is greeting?: No                                               │   │  │
│  │  │    Is followup?: No (new topic)                                   │   │  │
│  │  │    Is clarification?: No                                          │   │  │
│  │  │    Is question?: Yes ✓                                            │   │  │
│  │  │                                                                    │   │  │
│  │  │    RESULT: turn_type = "question"                                 │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  OUTPUT: ContextAnalysis {                                                │  │
│  │    theme: "technical",                                                    │  │
│  │    urgency: "low",                                                        │  │
│  │    emotion: "neutral",                                                    │  │
│  │    turn_type: "question"                                                  │  │
│  │  }                                                                        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Time: 15ms                                                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    STAGE 2: RESPONSE CALIBRATION                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: conversation_engine/context/calibrator.py                         │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  INPUT: ContextAnalysis + RelationshipAdaptation                         │  │
│  │                                                                           │  │
│  │  CALIBRATION LOGIC:                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ 1. ATTENTION WEIGHTS (how much to emphasize each section)        │   │  │
│  │  │    ──────────────────────────────────────────────────────────    │   │  │
│  │  │    Base weights: [all 0.5]                                        │   │  │
│  │  │                                                                    │   │  │
│  │  │    Theme multiplier (technical):                                  │   │  │
│  │  │      identity_weight: 0.5 × 1.4 = 0.7                            │   │  │
│  │  │      values_weight: 0.5 × 1.6 = 0.8  (tech principles important) │   │  │
│  │  │      style_weight: 0.5 × 1.2 = 0.6                               │   │  │
│  │  │      examples_weight: 0.5 × 1.4 = 0.7                            │   │  │
│  │  │      precedents_weight: 0.5 × 1.0 = 0.5 (not decision query)     │   │  │
│  │  │                                                                    │   │  │
│  │  │    Urgency adjustment (low):                                      │   │  │
│  │  │      No adjustments (all × 1.0)                                   │   │  │
│  │  │                                                                    │   │  │
│  │  │    User role adjustment (Engineer):                               │   │  │
│  │  │      examples_weight: 0.7 × 1.2 = 0.84  (show technical examples)│   │  │
│  │  │                                                                    │   │  │
│  │  │    FINAL WEIGHTS:                                                 │   │  │
│  │  │      identity_weight: 0.7                                         │   │  │
│  │  │      values_weight: 0.8                                           │   │  │
│  │  │      style_weight: 0.6                                            │   │  │
│  │  │      examples_weight: 0.84                                        │   │  │
│  │  │      precedents_weight: 0.5                                       │   │  │
│  │  │                                                                    │   │  │
│  │  │ 2. TONE ADJUSTMENT                                                │   │  │
│  │  │    ───────────────                                                │   │  │
│  │  │    From situation: neutral tone, low urgency                      │   │  │
│  │  │    From user role: collaborative with Engineer                    │   │  │
│  │  │                                                                    │   │  │
│  │  │    DECISIONS:                                                     │   │  │
│  │  │      formality: "less_formal" (peer-to-peer)                      │   │  │
│  │  │      directness: "balanced"                                       │   │  │
│  │  │      detail_level: "more_detailed" (technical depth)              │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  OUTPUT: CalibrationResult {                                             │  │
│  │    attention_weights: {                                                   │  │
│  │      identity: 0.7, values: 0.8, style: 0.6,                              │  │
│  │      examples: 0.84, precedents: 0.5                                      │  │
│  │    },                                                                     │  │
│  │    tone_adjustment: {                                                     │  │
│  │      formality: "less_formal",                                            │  │
│  │      directness: "balanced",                                              │  │
│  │      detail_level: "more_detailed"                                        │  │
│  │    }                                                                      │  │
│  │  }                                                                        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Time: 18ms                                                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      STAGE 3: EXAMPLE SELECTION                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: conversation_engine/examples/selector.py                          │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  PURPOSE: Select 1 communication example (Slack/YouTube)                 │  │
│  │                                                                           │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ STEP 1: Load Communication Examples                               │   │  │
│  │  │ ───────────────────────────────────────                           │   │  │
│  │  │ SQL:                                                               │   │  │
│  │  │   SELECT id, message_text, channel, embedding_id                  │   │  │
│  │  │   FROM communications                                             │   │  │
│  │  │   WHERE executive_id = 'sample-san'                               │   │  │
│  │  │   AND channel IN ('slack', 'youtube')                             │   │  │
│  │  │                                                                    │   │  │
│  │  │ RESULT: 12 examples (8 Slack, 4 YouTube)                          │   │  │
│  │  │ Time: 25ms                                                        │   │  │
│  │  │                                                                    │   │  │
│  │  │ STEP 2: Get Query Embedding                                       │   │  │
│  │  │ ──────────────────────────                                        │   │  │
│  │  │ query_embedding: [already cached from earlier, reuse]             │   │  │
│  │  │ Time: 0ms (cache hit)                                             │   │  │
│  │  │                                                                    │   │  │
│  │  │ STEP 3: Semantic Similarity Matching                              │   │  │
│  │  │ ────────────────────────────────────                              │   │  │
│  │  │ For each example:                                                 │   │  │
│  │  │   example_embedding = get_embedding(example.embedding_id)         │   │  │
│  │  │   similarity = cosine(query_embedding, example_embedding)         │   │  │
│  │  │                                                                    │   │  │
│  │  │ Similarities:                                                     │   │  │
│  │  │   slack_msg_7: 0.78 (about code quality & tech debt) ✓✓✓         │   │  │
│  │  │   youtube_4:   0.71 (about architecture decisions)                │   │  │
│  │  │   slack_msg_3: 0.68 (about team process)                          │   │  │
│  │  │   slack_msg_1: 0.64 (general discussion)                          │   │  │
│  │  │   ... (rest lower)                                                │   │  │
│  │  │                                                                    │   │  │
│  │  │ Time: 8ms                                                         │   │  │
│  │  │                                                                    │   │  │
│  │  │ STEP 4: Select Best Match                                         │   │  │
│  │  │ ──────────────────────                                            │   │  │
│  │  │ SELECTED: slack_msg_7 (similarity: 0.78)                          │   │  │
│  │  │                                                                    │   │  │
│  │  │ Content: "We need to address tech debt systematically...          │   │  │
│  │  │           It's not about perfection, but sustainable pace.        │   │  │
│  │  │           Let's allocate 20% of each sprint to refactoring."      │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  OUTPUT: SelectedExample {                                               │  │
│  │    example: Communication(id=slack_msg_7, channel="slack", ...),         │  │
│  │    similarity_score: 0.78                                                 │  │
│  │  }                                                                        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Time: 33ms                                                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    STAGE 4: PRECEDENT SELECTION                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: conversation_engine/precedents/selector.py                        │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  PURPOSE: Select 1 decision case (if query_type == "decision")           │  │
│  │                                                                           │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ CHECK QUERY TYPE:                                                 │   │  │
│  │  │   query_type: "analysis" (NOT "decision")                         │   │  │
│  │  │                                                                    │   │  │
│  │  │ DECISION: SKIP precedent selection                                │   │  │
│  │  │                                                                    │   │  │
│  │  │ (If this were a decision query, would load decision_cases         │   │  │
│  │  │  and do semantic matching similar to example selection)           │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  OUTPUT: None                                                             │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Time: 2ms                                                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     STAGE 5: PROMPT ASSEMBLY                                     │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: conversation_engine/prompt/assembler.py                           │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  PURPOSE: Assemble 10 modular sections into system + user prompts        │  │
│  │                                                                           │  │
│  │  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓   │  │
│  │  ┃  TOKEN BUDGET ALLOCATION (Standard Path: 8000 tokens)           ┃   │  │
│  │  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛   │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ File: conversation_engine/prompt/budget.py                        │   │  │
│  │  │                                                                    │   │  │
│  │  │ ALLOCATION:                                                       │   │  │
│  │  │   IdentitySection:          800 tokens                            │   │  │
│  │  │   ValuesSection:            600 tokens                            │   │  │
│  │  │   SpeakingStyleSection:     400 tokens                            │   │  │
│  │  │   InstructionsSection:      400 tokens                            │   │  │
│  │  │   ReasoningSection:         0 tokens (agentic path only)          │   │  │
│  │  │   CalibrationSection:       200 tokens                            │   │  │
│  │  │   ExampleSection:           600 tokens                            │   │  │
│  │  │   PrecedentSection:         0 tokens (not decision query)         │   │  │
│  │  │   ConversationContext:      200 tokens (2 previous turns)         │   │  │
│  │  │   RetrievedContext:         4800 tokens (remaining)               │   │  │
│  │  │   ────────────────────────────────────────────────────            │   │  │
│  │  │   TOTAL:                    8000 tokens                           │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓   │  │
│  │  ┃  SYSTEM PROMPT CONSTRUCTION                                      ┃   │  │
│  │  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛   │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ SECTION 1: IDENTITY (800 tokens, weight: 0.7)                    │   │  │
│  │  │ ──────────────────────────────────────────────────────────       │   │  │
│  │  │ File: conversation_engine/prompt/sections/identity.py            │   │  │
│  │  │                                                                    │   │  │
│  │  │ Content:                                                          │   │  │
│  │  │   """                                                             │   │  │
│  │  │   You are sample-san, Chief Technology Officer at TechCorp.       │   │  │
│  │  │                                                                    │   │  │
│  │  │   Your Role:                                                      │   │  │
│  │  │   • Lead technical strategy and architecture decisions            │   │  │
│  │  │   • Guide engineering teams on best practices                     │   │  │
│  │  │   • Balance technical excellence with business needs              │   │  │
│  │  │                                                                    │   │  │
│  │  │   Core Expertise Areas:                                           │   │  │
│  │  │   • Software Architecture (expert)                                │   │  │
│  │  │   • Technical Debt Management (expert)                            │   │  │
│  │  │   • System Design (expert)                                        │   │  │
│  │  │   • Code Quality Standards (advanced)                             │   │  │
│  │  │   • Team Leadership (advanced)                                    │   │  │
│  │  │                                                                    │   │  │
│  │  │   Background:                                                     │   │  │
│  │  │   15 years of experience building scalable systems, with          │   │  │
│  │  │   deep focus on maintainable architectures and sustainable        │   │  │
│  │  │   engineering practices.                                          │   │  │
│  │  │   """                                                             │   │  │
│  │  │ Actual tokens: 560 (weighted allocation: 560 × 0.7 = ~400 effective)│  │
│  │  │                                                                    │   │  │
│  │  │ SECTION 2: VALUES (600 tokens, weight: 0.8)                      │   │  │
│  │  │ ────────────────────────────────────────────                     │   │  │
│  │  │ File: conversation_engine/prompt/sections/values.py              │   │  │
│  │  │                                                                    │   │  │
│  │  │ Content:                                                          │   │  │
│  │  │   """                                                             │   │  │
│  │  │   Core Decision Principles:                                       │   │  │
│  │  │   1. Long-term sustainability over short-term gains               │   │  │
│  │  │   2. Technical excellence enables business velocity               │   │  │
│  │  │   3. Team capability compounds over time                          │   │  │
│  │  │   4. Architecture evolves with learning                           │   │  │
│  │  │                                                                    │   │  │
│  │  │   Priorities (in order):                                          │   │  │
│  │  │   • System reliability and maintainability                        │   │  │
│  │  │   • Developer experience and productivity                         │   │  │
│  │  │   • Scalability and performance                                   │   │  │
│  │  │   • Cost efficiency                                               │   │  │
│  │  │                                                                    │   │  │
│  │  │   Red Flags You Watch For:                                        │   │  │
│  │  │   • Ignoring technical debt                                       │   │  │
│  │  │   • Short-term thinking in architecture                           │   │  │
│  │  │   • Lack of testing coverage                                      │   │  │
│  │  │   """                                                             │   │  │
│  │  │ Actual tokens: 485 (weighted: 485 × 0.8 = ~390 effective)        │   │  │
│  │  │                                                                    │   │  │
│  │  │ SECTION 3: SPEAKING STYLE (400 tokens, weight: 0.6)              │   │  │
│  │  │ ────────────────────────────────────────────────────             │   │  │
│  │  │ File: conversation_engine/prompt/sections/speaking_style.py      │   │  │
│  │  │                                                                    │   │  │
│  │  │ Content:                                                          │   │  │
│  │  │   """                                                             │   │  │
│  │  │   Communication Style:                                            │   │  │
│  │  │   • Direct but warm                                               │   │  │
│  │  │   • Technical precision with clarity                              │   │  │
│  │  │   • Use concrete examples                                         │   │  │
│  │  │   • Acknowledge trade-offs explicitly                             │   │  │
│  │  │                                                                    │   │  │
│  │  │   Tone Characteristics:                                           │   │  │
│  │  │   • Collaborative (especially with engineers) ← ADJUSTED          │   │  │
│  │  │   • Patient and educational                                       │   │  │
│  │  │   • Pragmatic, not dogmatic                                       │   │  │
│  │  │                                                                    │   │  │
│  │  │   Formality: Less formal with technical peers ← ADJUSTED          │   │  │
│  │  │   """                                                             │   │  │
│  │  │ Actual tokens: 312 (weighted: 312 × 0.6 = ~190 effective)        │   │  │
│  │  │                                                                    │   │  │
│  │  │ SECTION 4: INSTRUCTIONS (400 tokens, no weight adjustment)       │   │  │
│  │  │ ───────────────────────────────────────────────────              │   │  │
│  │  │ File: conversation_engine/prompt/sections/instructions.py        │   │  │
│  │  │                                                                    │   │  │
│  │  │ Content:                                                          │   │  │
│  │  │   """                                                             │   │  │
│  │  │   Response Guidelines:                                            │   │  │
│  │  │   • Keep responses under 300 words (standard path)                │   │  │
│  │  │   • Provide technical depth for engineers ← ADJUSTED              │   │  │
│  │  │   • Cite sources using [Source: X] format                         │   │  │
│  │  │   • Be specific with examples and data                            │   │  │
│  │  │   • Acknowledge what you don't know                               │   │  │
│  │  │                                                                    │   │  │
│  │  │   Language: English                                               │   │  │
│  │  │   Citations: Required for factual claims                          │   │  │
│  │  │   """                                                             │   │  │
│  │  │ Actual tokens: 285                                                │   │  │
│  │  │                                                                    │   │  │
│  │  │ SECTION 6: CALIBRATION (200 tokens)                              │   │  │
│  │  │ ───────────────────────────────────────                          │   │  │
│  │  │ File: conversation_engine/prompt/sections/calibration.py         │   │  │
│  │  │                                                                    │   │  │
│  │  │ Content:                                                          │   │  │
│  │  │   """                                                             │   │  │
│  │  │   Current Situation Calibration:                                  │   │  │
│  │  │   • Topic: Technical (provide implementation details)             │   │  │
│  │  │   • Urgency: Low (unhurried, comprehensive response)              │   │  │
│  │  │   • Tone: Neutral (balanced, thoughtful)                          │   │  │
│  │  │   • User context: Engineer colleague (technical depth OK)         │   │  │
│  │  │                                                                    │   │  │
│  │  │   Cognitive Guidance:                                             │   │  │
│  │  │   • Prioritize technical debt expertise                           │   │  │
│  │  │   • Consider: Long-term vs. short-term trade-offs                 │   │  │
│  │  │   • Apply: "Invest in quality early" principle                    │   │  │
│  │  │   """                                                             │   │  │
│  │  │ Actual tokens: 187                                                │   │  │
│  │  │                                                                    │   │  │
│  │  │ SYSTEM PROMPT TOTAL: ~1829 tokens                                │   │  │
│  │  │ Time to build: 45ms                                               │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓   │  │
│  │  ┃  USER PROMPT CONSTRUCTION                                        ┃   │  │
│  │  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛   │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ SECTION 7: EXAMPLE (600 tokens, weight: 0.84)                    │   │  │
│  │  │ ──────────────────────────────────────────────────               │   │  │
│  │  │ File: conversation_engine/prompt/sections/example.py             │   │  │
│  │  │                                                                    │   │  │
│  │  │ Content:                                                          │   │  │
│  │  │   """                                                             │   │  │
│  │  │   Here's an example of how you communicate (Slack):               │   │  │
│  │  │   ───────────────────────────────────────────────                │   │  │
│  │  │   [From: #engineering channel, 2024-02-15]                        │   │  │
│  │  │                                                                    │   │  │
│  │  │   "We need to address tech debt systematically, not reactively.   │   │  │
│  │  │   Here's my thinking:                                             │   │  │
│  │  │                                                                    │   │  │
│  │  │   The 20% rule isn't arbitrary—it's about sustainable pace.       │   │  │
│  │  │   When we allocate sprint time to refactoring, we're not          │   │  │
│  │  │   'slowing down'—we're maintaining velocity long-term.            │   │  │
│  │  │                                                                    │   │  │
│  │  │   Last quarter, Team B tried to skip refactoring sprints.         │   │  │
│  │  │   Result? Velocity dropped 30% within 8 weeks due to brittle      │   │  │
│  │  │   code and bug debt.                                              │   │  │
│  │  │                                                                    │   │  │
│  │  │   It's not about perfection—it's about not letting complexity     │   │  │
│  │  │   compound to the point where it crushes productivity."           │   │  │
│  │  │   ───────────────────────────────────────────────                │   │  │
│  │  │   """                                                             │   │  │
│  │  │ Actual tokens: 478 (weighted: 478 × 0.84 = ~400 effective)       │   │  │
│  │  │                                                                    │   │  │
│  │  │ SECTION 9: CONVERSATION CONTEXT (200 tokens)                     │   │  │
│  │  │ ────────────────────────────────────────────                     │   │  │
│  │  │ File: conversation_engine/prompt/sections/                        │   │  │
│  │  │       conversation_context.py                                     │   │  │
│  │  │                                                                    │   │  │
│  │  │ Content:                                                          │   │  │
│  │  │   """                                                             │   │  │
│  │  │   Previous conversation:                                          │   │  │
│  │  │   ───────────────────────                                         │   │  │
│  │  │   User: "How is the migration to microservices going?"            │   │  │
│  │  │   You: "We're in phase 2 of 4. User service migrated             │   │  │
│  │  │         successfully, seeing 40% latency improvement..."          │   │  │
│  │  │                                                                    │   │  │
│  │  │   User: "What about the monolith?"                                │   │  │
│  │  │   You: "Still handling 70% of traffic. We're extracting           │   │  │
│  │  │         bounded contexts methodically..."                         │   │  │
│  │  │   ───────────────────────                                         │   │  │
│  │  │   """                                                             │   │  │
│  │  │ Actual tokens: 193                                                │   │  │
│  │  │                                                                    │   │  │
│  │  │ SECTION 10: RETRIEVED CONTEXT (4800 tokens allocated)            │   │  │
│  │  │ ─────────────────────────────────────────────────                │   │  │
│  │  │ File: conversation_engine/prompt/sections/                        │   │  │
│  │  │       retrieved_context.py                                        │   │  │
│  │  │                                                                    │   │  │
│  │  │ Content:                                                          │   │  │
│  │  │   """                                                             │   │  │
│  │  │   Relevant information from knowledge base:                       │   │  │
│  │  │   ────────────────────────────────────────                       │   │  │
│  │  │   [Source 1: Policy - Technical Debt Management]                  │   │  │
│  │  │   Technical debt should be tracked, prioritized, and              │   │  │
│  │  │   addressed systematically. Key principles:                       │   │  │
│  │  │   • Allocate 15-20% of sprint capacity to debt reduction          │   │  │
│  │  │   • Classify debt by impact (P0: blocks features, P1: ...)        │   │  │
│  │  │   • Use architectural decision records (ADRs) to document...      │   │  │
│  │  │   [~600 tokens]                                                   │   │  │
│  │  │                                                                    │   │  │
│  │  │   [Source 2: Policy - Code Quality Standards]                     │   │  │
│  │  │   All production code must meet these standards...                │   │  │
│  │  │   [~550 tokens]                                                   │   │  │
│  │  │                                                                    │   │  │
│  │  │   [Source 3: Decision Case - Refactoring Payment System]          │   │  │
│  │  │   Situation: Payment service had accumulated 18 months of...      │   │  │
│  │  │   Decision: Allocated dedicated 2-month refactoring sprint...     │   │  │
│  │  │   [~700 tokens]                                                   │   │  │
│  │  │                                                                    │   │  │
│  │  │   [Sources 4-10: Additional relevant documents]                   │   │  │
│  │  │   [~2950 tokens total for remaining 7 sources]                    │   │  │
│  │  │   ────────────────────────────────────────                       │   │  │
│  │  │   """                                                             │   │  │
│  │  │ Actual tokens: 4800 (uses all remaining budget)                  │   │  │
│  │  │                                                                    │   │  │
│  │  │ CURRENT QUERY:                                                    │   │  │
│  │  │   """                                                             │   │  │
│  │  │   Current question: What are sample-san's thoughts on             │   │  │
│  │  │                     technical debt?                               │   │  │
│  │  │   """                                                             │   │  │
│  │  │ Actual tokens: 18                                                 │   │  │
│  │  │                                                                    │   │  │
│  │  │ USER PROMPT TOTAL: ~5489 tokens                                  │   │  │
│  │  │ Time to build: 50ms                                               │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  OUTPUT:                                                                  │  │
│  │    system_prompt: str (~1829 tokens)                                      │  │
│  │    user_prompt: str (~5489 tokens)                                        │  │
│  │    TOTAL: ~7318 tokens (within 8000 budget)                               │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 95ms                                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ (system_prompt, user_prompt)
                                         ▼
╔═════════════════════════════════════════════════════════════════════════════════╗
║                      ⑯ LLM EXECUTION (LLMOrchestrator)                          ║
╚═════════════════════════════════════════════════════════════════════════════════╝
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  File: llm_integration/orchestrator.py:generate_with_prompts()                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  STEP 1: Build Messages Array                                            │  │
│  │  ────────────────────────────────────────────────────────────────────    │  │
│  │  messages = [                                                             │  │
│  │    {                                                                      │  │
│  │      "role": "system",                                                    │  │
│  │      "content": system_prompt  # 1829 tokens                              │  │
│  │    },                                                                     │  │
│  │    {                                                                      │  │
│  │      "role": "user",                                                      │  │
│  │      "content": user_prompt    # 5489 tokens                              │  │
│  │    }                                                                      │  │
│  │  ]                                                                        │  │
│  │  Time: 2ms                                                                │  │
│  │                                                                           │  │
│  │  STEP 2: LLM Client Creation                                             │  │
│  │  ───────────────────────────────                                         │  │
│  │  File: llm_integration/client_factory.py                                 │  │
│  │                                                                           │  │
│  │  provider: "groq" (from config.active_provider)                           │  │
│  │  path: "standard"                                                         │  │
│  │                                                                           │  │
│  │  model = providers["groq"].models["standard"]                             │  │
│  │       = "llama-3.1-70b-versatile"                                         │  │
│  │                                                                           │  │
│  │  settings = path_settings["standard"]                                     │  │
│  │           = {                                                             │  │
│  │               temperature: 0.5,                                           │  │
│  │               max_tokens: 1500,                                           │  │
│  │               timeout: 15000  # 15 seconds                                │  │
│  │             }                                                             │  │
│  │                                                                           │  │
│  │  llm_client = GroqClient(model, settings)                                 │  │
│  │  Time: 8ms                                                                │  │
│  │                                                                           │  │
│  │  STEP 3: API Call Execution                                              │  │
│  │  ──────────────────────────────                                          │  │
│  │  File: llm_integration/clients/groq_client.py                            │  │
│  │                                                                           │  │
│  │  API Request:                                                             │  │
│  │  ────────────                                                             │  │
│  │  POST https://api.groq.com/openai/v1/chat/completions                     │  │
│  │  Headers: {                                                               │  │
│  │    "Authorization": "Bearer $GROQ_API_KEY",                               │  │
│  │    "Content-Type": "application/json"                                     │  │
│  │  }                                                                        │  │
│  │  Body: {                                                                  │  │
│  │    "model": "llama-3.1-70b-versatile",                                    │  │
│  │    "messages": messages,  # 7318 input tokens                             │  │
│  │    "temperature": 0.5,                                                    │  │
│  │    "max_tokens": 1500,                                                    │  │
│  │    "stream": false                                                        │  │
│  │  }                                                                        │  │
│  │                                                                           │  │
│  │  [Request sent... waiting for LLM inference]                              │  │
│  │                                                                           │  │
│  │  ⏱️  LLM Processing Time: ~1200ms                                          │  │
│  │                                                                           │  │
│  │  API Response:                                                            │  │
│  │  ─────────────                                                            │  │
│  │  {                                                                        │  │
│  │    "id": "chatcmpl-...",                                                  │  │
│  │    "model": "llama-3.1-70b-versatile",                                    │  │
│  │    "choices": [{                                                          │  │
│  │      "message": {                                                         │  │
│  │        "role": "assistant",                                               │  │
│  │        "content": "When it comes to technical debt, my philosophy..."     │  │
│  │                   [~348 tokens of generated response]                     │  │
│  │      },                                                                   │  │
│  │      "finish_reason": "stop"                                              │  │
│  │    }],                                                                    │  │
│  │    "usage": {                                                             │  │
│  │      "prompt_tokens": 7318,                                               │  │
│  │      "completion_tokens": 348,                                            │  │
│  │      "total_tokens": 7666                                                 │  │
│  │    }                                                                      │  │
│  │  }                                                                        │  │
│  │                                                                           │  │
│  │  Time: 1200ms (API call)                                                  │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 1210ms                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ LLMResponse
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                   ⑰ RESPONSE POST-PROCESSING                                    │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: llm_integration/response_formatter.py                             │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  INPUT: LLM response text (348 tokens)                                   │  │
│  │                                                                           │  │
│  │  GENERATED RESPONSE TEXT:                                                │  │
│  │  """                                                                      │  │
│  │  When it comes to technical debt, my philosophy is grounded in           │  │
│  │  pragmatism and long-term thinking [Source: Technical Debt Management    │  │
│  │  Policy].                                                                 │  │
│  │                                                                           │  │
│  │  First, let me be clear: technical debt isn't inherently bad. Like       │  │
│  │  financial debt, it's a tool—you borrow time now to deliver value        │  │
│  │  faster, with the understanding you'll pay it back with interest.        │  │
│  │  The problem starts when teams treat debt as "free money" and never      │  │
│  │  schedule repayment.                                                      │  │
│  │                                                                           │  │
│  │  Here's my approach:                                                      │  │
│  │                                                                           │  │
│  │  1. **Systematic tracking**: We use a debt register, categorizing by     │  │
│  │     impact [Source: Code Quality Standards]. P0 debt blocks new          │  │
│  │     features—that gets immediate attention.                               │  │
│  │                                                                           │  │
│  │  2. **20% rule**: Each sprint allocates 15-20% capacity to debt          │  │
│  │     reduction [Source: Technical Debt Management Policy]. It's not       │  │
│  │     negotiable overhead—it's velocity insurance.                          │  │
│  │                                                                           │  │
│  │  3. **Real example**: When we refactored the payment system after        │  │
│  │     18 months of accumulated debt, velocity initially dropped            │  │
│  │     [Source: Refactoring Payment System Decision]. But within 6          │  │
│  │     weeks, the team was 40% faster than before, with 60% fewer           │  │
│  │     production incidents.                                                 │  │
│  │                                                                           │  │
│  │  The key insight: technical debt compounds. A messy codebase doesn't     │  │
│  │  just slow down current work—it makes every future change harder,        │  │
│  │  creating a vicious cycle that can cripple a team.                       │  │
│  │                                                                           │  │
│  │  My stance? Address debt systematically, not heroically. Sustainable     │  │
│  │  pace beats death marches every time.                                    │  │
│  │  """                                                                      │  │
│  │                                                                           │  │
│  │  STEP 1: Citation Extraction                                             │  │
│  │  ────────────────────────────                                            │  │
│  │  Regex: r'\[Source:\s*([^\]]+)\]'                                         │  │
│  │                                                                           │  │
│  │  Found citations:                                                         │  │
│  │    1. "Technical Debt Management Policy"                                  │  │
│  │    2. "Code Quality Standards"                                            │  │
│  │    3. "Technical Debt Management Policy" (duplicate)                      │  │
│  │    4. "Refactoring Payment System Decision"                               │  │
│  │                                                                           │  │
│  │  Unique citations: 3                                                      │  │
│  │  Time: 8ms                                                                │  │
│  │                                                                           │  │
│  │  STEP 2: Source Linking                                                  │  │
│  │  ─────────────────────                                                   │  │
│  │  Match citations to retrieval_results by title/content:                  │  │
│  │                                                                           │  │
│  │  sources = [                                                              │  │
│  │    {                                                                      │  │
│  │      source_id: "doc_3",                                                  │  │
│  │      source_type: "policy",                                               │  │
│  │      title: "Technical Debt Management Policy",                           │  │
│  │      snippet: "Technical debt should be tracked...",                      │  │
│  │      score: 0.641                                                         │  │
│  │    },                                                                     │  │
│  │    {                                                                      │  │
│  │      source_id: "doc_1",                                                  │  │
│  │      source_type: "policy",                                               │  │
│  │      title: "Code Quality Standards",                                     │  │
│  │      snippet: "All production code must...",                              │  │
│  │      score: 0.612                                                         │  │
│  │    },                                                                     │  │
│  │    {                                                                      │  │
│  │      source_id: "doc_14",                                                 │  │
│  │      source_type: "decision_case",                                        │  │
│  │      title: "Refactoring Payment System Decision",                        │  │
│  │      snippet: "Situation: Payment service had...",                        │  │
│  │      score: 0.571                                                         │  │
│  │    }                                                                      │  │
│  │  ]                                                                        │  │
│  │  Time: 7ms                                                                │  │
│  │                                                                           │  │
│  │  OUTPUT: FormattedResponse {                                             │  │
│  │    response: str (cleaned, 348 tokens),                                   │  │
│  │    citations: ["Technical Debt Management Policy", ...],                  │  │
│  │    sources: [{source_id, title, snippet, score}, ...]                     │  │
│  │  }                                                                        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 15ms                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    ⑱ QUALITY EVALUATION (Sampling)                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  NOTE: Evaluation runs for ~10% of requests (sampling)                   │  │
│  │        This request selected for evaluation ✓                             │  │
│  │                                                                           │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ RAGAS Evaluation                                                    │  │  │
│  │  │ File: llm_integration/evaluation/ragas_evaluator.py                │  │  │
│  │  │                                                                     │  │  │
│  │  │ METRIC 1: Faithfulness                                             │  │  │
│  │  │ ─────────────────────                                              │  │  │
│  │  │ Extract claims from response using LLM:                            │  │  │
│  │  │   Claims = [                                                       │  │  │
│  │  │     "Technical debt isn't inherently bad",                         │  │  │
│  │  │     "20% rule allocates sprint capacity",                          │  │  │
│  │  │     "Payment system refactoring improved velocity by 40%",         │  │  │
│  │  │     "Payment system incidents reduced by 60%",                     │  │  │
│  │  │     ...  # 8 claims total                                          │  │  │
│  │  │   ]                                                                │  │  │
│  │  │                                                                     │  │  │
│  │  │ Verify each claim against retrieved context:                       │  │  │
│  │  │   For each claim:                                                  │  │  │
│  │  │     LLM prompt: "Is this claim supported by context?"             │  │  │
│  │  │     [LLM API call for verification]                                │  │  │
│  │  │                                                                     │  │  │
│  │  │ Results:                                                           │  │  │
│  │  │   Claim 1: ✓ Supported                                            │  │  │
│  │  │   Claim 2: ✓ Supported                                            │  │  │
│  │  │   Claim 3: ✓ Supported                                            │  │  │
│  │  │   Claim 4: ✓ Supported                                            │  │  │
│  │  │   Claims 5-8: ✓ All supported                                     │  │  │
│  │  │                                                                     │  │  │
│  │  │ faithfulness_score = 8/8 = 1.00                                   │  │  │
│  │  │ Time: 450ms (8 LLM verification calls)                             │  │  │
│  │  │                                                                     │  │  │
│  │  │ METRIC 2: Relevancy                                                │  │  │
│  │  │ ─────────────────────                                              │  │  │
│  │  │ For each context chunk in retrieved_results:                       │  │  │
│  │  │   similarity = cosine(query_emb, chunk_emb)                        │  │  │
│  │  │                                                                     │  │  │
│  │  │ Similarities: [0.87, 0.82, 0.78, 0.71, ...]                        │  │  │
│  │  │ relevancy_score = mean(similarities) = 0.79                        │  │  │
│  │  │ Time: 25ms                                                         │  │  │
│  │  │                                                                     │  │  │
│  │  │ METRIC 3: Precision                                                │  │  │
│  │  │ ──────────────────                                                 │  │  │
│  │  │ Verify citations exist in sources:                                 │  │  │
│  │  │   Citation 1: ✓ Found (doc_3)                                     │  │  │
│  │  │   Citation 2: ✓ Found (doc_1)                                     │  │  │
│  │  │   Citation 3: ✓ Found (doc_14)                                    │  │  │
│  │  │                                                                     │  │  │
│  │  │ precision_score = 3/3 = 1.00                                      │  │  │
│  │  │ Time: 5ms                                                          │  │  │
│  │  │                                                                     │  │  │
│  │  │ RAGAS RESULTS:                                                     │  │  │
│  │  │   faithfulness: 1.00                                               │  │  │
│  │  │   relevancy: 0.79                                                  │  │  │
│  │  │   precision: 1.00                                                  │  │  │
│  │  │ Total time: 480ms                                                  │  │  │
│  │  └────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                           │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ Quality Metrics (Sampling: 5%)                                      │  │  │
│  │  │ File: llm_integration/evaluation/quality_evaluator.py              │  │  │
│  │  │                                                                     │  │  │
│  │  │ METRIC 1: Citation Coverage                                        │  │  │
│  │  │ ────────────────────────                                           │  │  │
│  │  │ citations_count = 4 (including duplicate)                          │  │  │
│  │  │ response_words = 290                                               │  │  │
│  │  │ coverage_rate = 4/290 = 0.0138 = 1.38%                            │  │  │
│  │  │                                                                     │  │  │
│  │  │ METRIC 2: Factual Grounding                                        │  │  │
│  │  │ ───────────────────────                                            │  │  │
│  │  │ Identify factual statements: 6 statements                          │  │  │
│  │  │ Verify against retrieved context:                                  │  │  │
│  │  │   Statement 1: ✓ Grounded                                          │  │  │
│  │  │   Statement 2: ✓ Grounded                                          │  │  │
│  │  │   Statements 3-6: ✓ All grounded                                   │  │  │
│  │  │                                                                     │  │  │
│  │  │ grounding_rate = 6/6 = 1.00 = 100%                                │  │  │
│  │  │ Time: 35ms                                                         │  │  │
│  │  └────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                           │  │
│  │  Store in database:                                                       │  │
│  │  INSERT INTO quality_metrics (                                            │  │
│  │    request_id, executive_id,                                              │  │
│  │    citation_coverage, grounding_rate,                                     │  │
│  │    faithfulness, relevancy, precision                                     │  │
│  │  ) VALUES (...)                                                           │  │
│  │  Time: 12ms                                                               │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 527ms                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      ⑲ STATE PERSISTENCE                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  Update RAGState conversation_history                                     │  │
│  │  ────────────────────────────────────────────────────────────────────    │  │
│  │  state.conversation_history.append({                                      │  │
│  │    "role": "user",                                                        │  │
│  │    "content": "What are sample-san's thoughts on technical debt?"         │  │
│  │  })                                                                       │  │
│  │  state.conversation_history.append({                                      │  │
│  │    "role": "assistant",                                                   │  │
│  │    "content": "When it comes to technical debt..."  # 348 tokens          │  │
│  │  })                                                                       │  │
│  │  Time: 2ms                                                                │  │
│  │                                                                           │  │
│  │  LangGraph Checkpointer Save                                             │  │
│  │  ───────────────────────────────                                         │  │
│  │  File: langgraph_workflow/checkpointer.py                                │  │
│  │                                                                           │  │
│  │  Serialize state to JSONB:                                                │  │
│  │  INSERT INTO checkpoints (                                                │  │
│  │    checkpoint_ns,         -- 'sess_123' (thread_id)                       │  │
│  │    checkpoint_id,         -- UUID generated                               │  │
│  │    parent_checkpoint_id,  -- Previous checkpoint                          │  │
│  │    channel_values,        -- RAGState as JSONB                            │  │
│  │    metadata               -- {path, timestamp, user_id}                   │  │
│  │  )                                                                        │  │
│  │  Time: 35ms                                                               │  │
│  │                                                                           │  │
│  │  SessionManager Store Turn                                               │  │
│  │  ──────────────────────────                                              │  │
│  │  File: utils/session_manager.py                                          │  │
│  │                                                                           │  │
│  │  Calculate importance_score:                                              │  │
│  │    factors = [                                                            │  │
│  │      query_complexity: 0.5,                                               │  │
│  │      decision_involvement: 0.1,                                           │  │
│  │      context_richness: 0.7                                                │  │
│  │    ]                                                                      │  │
│  │    importance = mean(factors) = 0.43                                      │  │
│  │                                                                           │  │
│  │  INSERT INTO conversation_turns (                                         │  │
│  │    session_id, query, response,                                           │  │
│  │    sources_used,      -- JSONB array of source objects                    │  │
│  │    importance_score,  -- 0.43                                             │  │
│  │    feedback_score     -- NULL (to be filled later)                        │  │
│  │  )                                                                        │  │
│  │  Time: 18ms                                                               │  │
│  │                                                                           │  │
│  │  UPDATE conversation_sessions                                             │  │
│  │  SET last_activity = NOW()                                                │  │
│  │  WHERE id = 'sess_123'                                                    │  │
│  │  Time: 8ms                                                                │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 63ms                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                   ⑳ OBSERVABILITY LOGGING                                       │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  LangSmith Tracing                                                        │  │
│  │  ─────────────────                                                        │  │
│  │  File: observability/langsmith_integration.py                             │  │
│  │                                                                           │  │
│  │  Log run with metadata:                                                   │  │
│  │    • thread_id: "sess_123"                                                │  │
│  │    • run_id: UUID                                                         │  │
│  │    • node_executions: [                                                   │  │
│  │        {node: "analyze_query", duration: 70ms},                           │  │
│  │        {node: "route_query", duration: 10ms},                             │  │
│  │        {node: "retrieve_parallel_standard", duration: 210ms},             │  │
│  │        ... (all 15 nodes)                                                 │  │
│  │      ]                                                                    │  │
│  │    • total_latency: 2835ms                                                │  │
│  │    • tokens_used: 7666                                                    │  │
│  │  Time: 18ms (async, non-blocking)                                         │  │
│  │                                                                           │  │
│  │  Prometheus Metrics                                                       │  │
│  │  ──────────────────                                                       │  │
│  │  File: observability/prometheus_exporter.py                               │  │
│  │                                                                           │  │
│  │  Update metrics:                                                          │  │
│  │    rag_requests_total{path="standard", status="success"}.inc()            │  │
│  │    rag_latency_seconds{path="standard"}.observe(2.835)                    │  │
│  │    rag_path_selection_count{path="standard"}.inc()                        │  │
│  │    rag_llm_tokens_used{provider="groq", model="llama-3.1-70b"}.add(7666) │  │
│  │  Time: 3ms (local metrics update)                                         │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 21ms (non-blocking)                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    ㉑ BUILD FINAL RESPONSE                                       │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: api/langgraph_endpoints.py:build_chat_response()                  │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  ChatResponse = {                                                         │  │
│  │    response: "When it comes to technical debt, my philosophy...",         │  │
│  │    sources: [                                                             │  │
│  │      {                                                                    │  │
│  │        source_id: "doc_3",                                                │  │
│  │        source_type: "policy",                                             │  │
│  │        title: "Technical Debt Management Policy",                         │  │
│  │        snippet: "Technical debt should be tracked...",                    │  │
│  │        score: 0.641                                                       │  │
│  │      },                                                                   │  │
│  │      {                                                                    │  │
│  │        source_id: "doc_1",                                                │  │
│  │        source_type: "policy",                                             │  │
│  │        title: "Code Quality Standards",                                   │  │
│  │        snippet: "All production code must...",                            │  │
│  │        score: 0.612                                                       │  │
│  │      },                                                                   │  │
│  │      {                                                                    │  │
│  │        source_id: "doc_14",                                               │  │
│  │        source_type: "decision_case",                                      │  │
│  │        title: "Refactoring Payment System Decision",                      │  │
│  │        snippet: "Situation: Payment service had...",                      │  │
│  │        score: 0.571                                                       │  │
│  │      }                                                                    │  │
│  │    ],                                                                     │  │
│  │    citations: [                                                           │  │
│  │      "Technical Debt Management Policy",                                  │  │
│  │      "Code Quality Standards",                                            │  │
│  │      "Refactoring Payment System Decision"                                │  │
│  │    ],                                                                     │  │
│  │    metadata: {                                                            │  │
│  │      path: "standard",                                                    │  │
│  │      latency_ms: 2835,                                                    │  │
│  │      model_used: "llama-3.1-70b-versatile",                               │  │
│  │      tokens_used: 7666,                                                   │  │
│  │      quality_scores: {                                                    │  │
│  │        faithfulness: 1.00,                                                │  │
│  │        relevancy: 0.79,                                                   │  │
│  │        precision: 1.00,                                                   │  │
│  │        citation_coverage: 0.0138,                                         │  │
│  │        grounding_rate: 1.00                                               │  │
│  │      },                                                                   │  │
│  │      routing_info: {                                                      │  │
│  │        query_type: "analysis",                                            │  │
│  │        complexity: "medium",                                              │  │
│  │        confidence: 0.82,                                                  │  │
│  │        reasoning: "Medium complexity analysis query with entities"        │  │
│  │      }                                                                    │  │
│  │    },                                                                     │  │
│  │    session_id: "sess_123"                                                 │  │
│  │  }                                                                        │  │
│  │                                                                           │  │
│  │  Time: 5ms                                                                │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
╔═════════════════════════════════════════════════════════════════════════════════╗
║                         RETURN HTTP 200 RESPONSE                                ║
║  Content-Type: application/json                                                 ║
║  Body: ChatResponse (JSON)                                                      ║
╚═════════════════════════════════════════════════════════════════════════════════╝
                                         │
                                         ▼
                                    USER RECEIVES
                                      RESPONSE

╔═════════════════════════════════════════════════════════════════════════════════╗
║                            TOTAL LATENCY BREAKDOWN                              ║
╠═════════════════════════════════════════════════════════════════════════════════╣
║  ① API Reception:                       5ms                                     ║
║  ② Session Management:                  5ms                                     ║
║  ③ LangGraph Init:                     10ms                                     ║
║  ④ Query Analysis:                     70ms                                     ║
║  ⑤ Routing:                            10ms                                     ║
║  ⑥ GraphRAG (skipped):                  5ms                                     ║
║  ⑦ Parallel Retrieval:                210ms  ← Parallel (Graph:100 + Vec:125   ║
║                                                 + Mem:135 = max 135ms effective) ║
║  ⑧ Fusion:                             26ms                                     ║
║  ⑨ Reranking:                         188ms                                     ║
║  ⑩-⑭ Cognitive Enhancement:            50ms  (5 layers + assembly)              ║
║  ⑮ ConversationEngine:                273ms  (5 stages)                         ║
║  ⑯ LLM Execution:                    1210ms  ← BOTTLENECK (42.7%)               ║
║  ⑰ Response Formatting:                15ms                                     ║
║  ⑱ Quality Evaluation:                527ms  (async, sampling 10%)              ║
║  ⑲ State Persistence:                  63ms                                     ║
║  ⑳ Observability:                      21ms  (non-blocking)                     ║
║  ㉑ Build Response:                      5ms                                     ║
║  ─────────────────────────────────────────────────────────────────────────────  ║
║  TOTAL (user-perceived):            ~2835ms (2.8 seconds)                       ║
║  TOTAL (with async ops):            ~3362ms (including evaluation)              ║
╚═════════════════════════════════════════════════════════════════════════════════╝
```

## END OF COMPLETE QUERY-TO-RESPONSE FLOWCHART
