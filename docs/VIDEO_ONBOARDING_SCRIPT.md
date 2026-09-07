# AI Officer RAG System - Developer Onboarding Video Script

> **Total Duration**: ~45-60 minutes
> **Prerequisites**: Developer has read `AI-OFFICER_RAG_COMPLETE_GUIDE.md`
> **Tools Needed**: VS Code, Terminal, Browser (LangSmith), Postman/curl

---

## Video Structure Overview

```
Part 1: Introduction & Philosophy (5 min)
Part 2: Architecture Walkthrough (10 min)
Part 3: Live Query Trace - End to End (15 min)
Part 4: LangSmith Deep Dive (10 min)
Part 5: Code Walkthrough - Key Files (10 min)
Part 6: Common Tasks & Debugging (5 min)
```

---

## PART 1: Introduction & Philosophy (5 minutes)

### What to Show
- Open the documentation file in VS Code
- Show the system diagram (Section 2.1)

### Talking Points

```
"Welcome to the AI Officer RAG system. Before we dive into code,
let me explain WHAT we're building and WHY the architecture looks this way."

KEY MESSAGE: "This is NOT a chatbot. We're building Cognitive Twins -
AI representations that think and decide like specific executives."
```

**Explain the 6 Core Principles** (show on screen):
1. **Database is the Brain** - All cognitive data from PostgreSQL/Neo4j
2. **Graph Constrains Vector** - Graph narrows search BEFORE vector similarity
3. **Never Say "I Don't Know" for Opinions** - Executives have opinions
4. **Recency Bias Exploitation** - Critical instructions go LAST in prompts
5. **Soft Targets, Not Hard Limits** - Word limits are guidelines
6. **Symbolic Guardrails Are Sacred** - Safety is non-negotiable

### Screen Recording Actions
1. Open `docs/AI-OFFICER_RAG_COMPLETE_GUIDE.md`
2. Scroll to Section 1 - System Philosophy
3. Highlight the ASCII diagram of principles

---

## PART 2: Architecture Walkthrough (10 minutes)

### What to Show
- VS Code folder structure
- Architecture diagram from docs

### Talking Points

```
"Let me walk you through the architecture layer by layer,
then we'll trace a real query through the system."
```

**Folder Structure Tour** (open each folder briefly):
```
RAG/
├── api/                    # FastAPI endpoints - START HERE
│   ├── main.py            # Server entry point
│   ├── langgraph_endpoints.py  # Main chat endpoint
│   └── models.py          # Pydantic request/response models
│
├── langgraph_workflow/     # Query orchestration - THE BRAIN
│   ├── graph.py           # StateGraph definition
│   ├── state.py           # WorkflowState TypedDict
│   └── nodes.py           # Node implementations
│
├── cognitive_twin/         # Executive personality layer
│   ├── conversational_router.py  # Intent detection
│   └── prompt_assembler.py       # Cognitive prompt building
│
├── conversation_engine/    # Prompt calibration
│   └── prompt/
│       ├── rules.py       # Word limits, anti-AI patterns
│       └── sections/      # Prompt section builders
│
├── hybrid_retrieval/       # Search layer
│   ├── true_hybrid.py     # Vector + Graph fusion
│   └── query_type_classifier.py
│
├── llm_integration/        # LLM providers
│   ├── orchestrator.py    # Fast/Standard/Agentic handlers
│   └── client_factory.py  # OpenAI/Groq/Gemini clients
│
└── config/                 # Settings & environment
    └── settings.py
```

### Screen Recording Actions
1. Open VS Code in `D:\ai officer\RAG`
2. Expand folder tree, explain each folder's purpose
3. Open `api/main.py` - "This is where the server starts"
4. Open `langgraph_workflow/graph.py` - "This defines the query flow"

---

## PART 3: Live Query Trace - End to End (15 minutes)

### What to Show
- Terminal running the server
- Postman or curl sending a request
- Server logs showing the flow
- LangSmith trace

### Setup Before Recording
```powershell
# Terminal 1: Start the server
cd "D:\ai officer\RAG"
python -m api.main

# Terminal 2: Ready for curl commands
```

### Talking Points

```
"Now let's trace a REAL query through the system.
I'll show you exactly what happens at each step."
```

### Live Demo Script

**Step 1: Send a Simple Query**
```powershell
curl -X POST http://localhost:8000/api/v1/langgraph/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"query\": \"What are sample-san's top priorities?\", \"user_id\": \"demo\", \"profile_id\": \"sample_profile\"}"
```

**While waiting, explain:**
```
"Watch the server logs. You'll see:
1. Request received with a request_id
2. Cognitive routing decision (is this conversational or needs retrieval?)
3. Query analysis and path selection (fast/standard/agentic)
4. Retrieval from PostgreSQL + Neo4j
5. LLM generation with the assembled prompt
6. Response returned"
```

**Step 2: Show Server Logs**
Point out key log lines:
```
INFO: [req_xxx] Cognitive routing: path=standard, skip_retrieval=False
INFO: [req_xxx] Vector search: 20 results in 145ms
INFO: [req_xxx] Graph context: 5 relationships found
INFO: [req_xxx] LLM generation: 234 tokens in 1.2s
```

**Step 3: Multi-Turn Conversation Demo**
```powershell
# First query - get a list
curl -X POST http://localhost:8000/api/v1/langgraph/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"query\": \"What projects is sample working on?\", \"user_id\": \"demo\", \"profile_id\": \"sample_profile\"}"

# Note the session_id from response, then:
curl -X POST http://localhost:8000/api/v1/langgraph/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"query\": \"Tell me more about the first one\", \"user_id\": \"demo\", \"profile_id\": \"sample_profile\", \"session_id\": \"<session_id_from_above>\"}"
```

**Explain:**
```
"Notice how the second query says 'the first one' - this is reference resolution.
The system maintains conversation history via LangGraph checkpointer,
so it knows what 'the first one' refers to from the previous response."
```

**Step 4: Japanese Query Demo**
```powershell
# Using base64 for Windows compatibility
curl -X POST http://localhost:8000/api/v1/langgraph/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"query_base64\": \"44K344Oz44Ks44Od44O844Or5biC5aC044G444Gu5ouh5aSn44Gr44Gk44GE44Gm44Gp44GG5oCd44GE44G+44GZ44GL77yf\", \"user_id\": \"demo\", \"profile_id\": \"sample_profile\", \"language\": \"ja\"}"
```

**Explain:**
```
"For Japanese queries on Windows, we use base64 encoding to avoid
UTF-8 corruption issues with curl. The system automatically decodes it."
```

---

## PART 4: LangSmith Deep Dive (10 minutes)

### What to Show
- LangSmith dashboard (https://smith.langchain.com)
- A specific trace from the query we just ran
- Breakdown of each step

### Setup Before Recording
1. Ensure `LANGCHAIN_TRACING_V2=true` in `.env`
2. Have LangSmith open in browser
3. Run a query so there's a fresh trace

### Talking Points

```
"LangSmith is our observability platform. Every query creates a trace
that shows EXACTLY what happened - inputs, outputs, latencies, tokens, everything."
```

### LangSmith Tour

**1. Finding Your Trace**
- Open LangSmith → Projects → Select your project
- Find recent trace by timestamp or search by request_id
- Click to open the trace

**2. Trace Overview**
```
"Each trace shows:
- Total latency (how long the entire request took)
- Token usage (prompt + completion tokens)
- Cost estimate
- Success/failure status"
```

**3. Trace Waterfall View**
Walk through each node:
```
├── cognitive_route          # First decision point
│   └── Input: query, profile_id
│   └── Output: path="standard", skip_retrieval=false
│
├── analyze_query            # Query understanding
│   └── Complexity score, intent classification
│
├── route_query              # Path selection
│   └── Decision: fast/standard/agentic
│
├── retrieve_vector          # PostgreSQL pgvector search
│   └── 20 results, 145ms
│
├── retrieve_graph           # Neo4j graph context
│   └── 5 relationships found
│
├── fuse_results             # Combine vector + graph
│   └── RRF fusion, deduplication
│
├── generate_response        # LLM call
│   └── System prompt: 2400 tokens
│   └── Response: 156 tokens
│   └── Model: gpt-4o-mini
│
└── END
```

**4. Inspecting a Node**
Click on `generate_response` node:
```
"Here you can see the EXACT prompt sent to the LLM.
This is invaluable for debugging - if the response is wrong,
check if the prompt was wrong."
```

Show:
- Input (system prompt + user prompt)
- Output (LLM response)
- Latency breakdown
- Token counts

**5. Comparing Traces**
```
"You can compare two traces side-by-side to see why
one query worked and another didn't."
```

**6. Feedback & Evaluation**
```
"LangSmith also supports feedback collection.
When users rate responses, it's stored here for analysis."
```

### Screen Recording Actions
1. Open LangSmith in browser
2. Navigate to your project
3. Open a recent trace
4. Expand each node, explain what it does
5. Show the prompt inspection feature
6. Show latency breakdown

---

## PART 5: Code Walkthrough - Key Files (10 minutes)

### What to Show
- VS Code with key files open
- Highlight important code sections

### Files to Cover

**1. `api/langgraph_endpoints.py` - The Entry Point**
```python
# Show the main chat endpoint (around line 80-120)
@router.post("/chat", response_model=ChatResponse)
async def langgraph_chat(chat_request: ChatRequest, ...):
    # Explain:
    # 1. Request validation
    # 2. Session/checkpoint handling
    # 3. Workflow invocation
    # 4. Response formatting
```

**2. `langgraph_workflow/graph.py` - The State Machine**
```python
# Show the graph definition (around line 200-300)
workflow = StateGraph(WorkflowState)
workflow.add_node("cognitive_route", cognitive_route_node)
workflow.add_node("analyze_query", analyze_query_node)
# ... etc

# Explain:
# "This is like a flowchart in code. Each node is a function,
#  and edges define which node runs next based on conditions."
```

**3. `langgraph_workflow/nodes.py` - The Business Logic**
```python
# Show a node function (around line 200-300)
async def retrieve_vector_node(state: WorkflowState) -> dict:
    # Explain:
    # 1. Get query from state
    # 2. Call hybrid_retrieval
    # 3. Return results to update state
```

**4. `cognitive_twin/conversational_router.py` - Intent Detection**
```python
# Show the route() method (around line 200-300)
def route(self, query: str, ...):
    # Explain:
    # "This decides if we need retrieval or can just chat.
    #  Greetings skip retrieval, business questions don't."
```

**5. `conversation_engine/prompt/rules.py` - Response Calibration**
```python
# Show word limits and anti-AI patterns
WORD_LIMITS = {
    "fast": WordLimitConfig(target=15, soft_max=25, hard_max=40),
    "standard": WordLimitConfig(target=35, soft_max=50, hard_max=80),
    # ...
}

# Explain:
# "These aren't arbitrary numbers - they're based on analyzing
#  real sample response patterns. Fast path = brief acknowledgment,
#  Standard = opinion with reasoning."
```

### Screen Recording Actions
1. Open each file in VS Code
2. Use Ctrl+G to go to specific line numbers
3. Highlight code sections as you explain
4. Use VS Code's minimap to show file structure

---

## PART 6: Common Tasks & Debugging (5 minutes)

### What to Show
- Terminal commands
- Common debugging scenarios

### Common Developer Tasks

**1. Starting the Server**
```powershell
cd "D:\ai officer\RAG"
python -m api.main
# Server starts on port 8000
```

**2. Running Tests**
```powershell
python test_japanese_encoding.py  # Japanese + multi-turn tests
```

**3. Clearing Cache (after code changes)**
```powershell
python clear_cache.py
```

**4. Checking Server Health**
```powershell
curl http://localhost:8000/api/v1/health
```

### Debugging Tips

**Problem: Query returns wrong results**
```
1. Check LangSmith trace - was retrieval correct?
2. Check the prompt in generate_response node
3. Verify profile_id is correct
```

**Problem: Japanese characters corrupted**
```
1. Use query_base64 instead of query
2. Encode with: python encode_query.py "your Japanese text"
```

**Problem: Multi-turn not working**
```
1. Ensure session_id is passed in second request
2. Check server logs for "Restored conversation_history"
3. Verify checkpointer is working (LangGraph checkpoint)
```

**Problem: Server crashes on Windows**
```
1. Use python -m api.main (not uvicorn directly)
2. This ensures WindowsSelectorEventLoopPolicy is set
```

---

## Recording Tips

### Technical Setup
- **Resolution**: 1920x1080 minimum
- **Audio**: Use a good microphone, minimize background noise
- **VS Code**: Use a light theme for better visibility
- **Terminal**: Increase font size to 14-16pt
- **Browser**: Zoom to 125% for LangSmith

### Presentation Tips
1. **Pause after important points** - Let information sink in
2. **Use cursor to point** - Guide viewer's attention
3. **Read error messages aloud** - They're often skipped
4. **Show failures too** - Debugging is part of learning
5. **Summarize each section** - "So what we learned here is..."

### Post-Recording
1. Add chapter markers for easy navigation
2. Include timestamps in video description
3. Provide links to:
   - Documentation file
   - LangSmith project (if shareable)
   - Relevant code files on GitHub

---

## Quick Reference Commands for Demo

```powershell
# Start server
cd "D:\ai officer\RAG"
python -m api.main

# Health check
curl http://localhost:8000/api/v1/health

# Simple query
curl -X POST http://localhost:8000/api/v1/langgraph/chat -H "Content-Type: application/json" -d "{\"query\": \"What are sample's priorities?\", \"user_id\": \"demo\", \"profile_id\": \"sample_profile\"}"

# Multi-turn (replace SESSION_ID)
curl -X POST http://localhost:8000/api/v1/langgraph/chat -H "Content-Type: application/json" -d "{\"query\": \"Tell me more about the first one\", \"user_id\": \"demo\", \"profile_id\": \"sample_profile\", \"session_id\": \"SESSION_ID\"}"

# Japanese (base64)
curl -X POST http://localhost:8000/api/v1/langgraph/chat -H "Content-Type: application/json" -d "{\"query_base64\": \"44K344Oz44Ks44Od44O844Or5biC5aC044G444Gu5ouh5aSn44Gr44Gk44GE44Gm44Gp44GG5oCd44GE44G+44GZ44GL77yf\", \"user_id\": \"demo\", \"profile_id\": \"sample_profile\", \"language\": \"ja\"}"

# Encode Japanese query
python encode_query.py "シンガポール市場への拡大についてどう思いますか？"
```

---

## Checklist Before Recording

- [ ] Server is running and healthy
- [ ] LangSmith has recent traces
- [ ] VS Code has all key files open in tabs
- [ ] Terminal font size increased
- [ ] Documentation file is open
- [ ] Test queries work correctly
- [ ] Screen recording software ready
- [ ] Microphone tested

---

*Good luck with your onboarding video!*
