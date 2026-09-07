# AI Officer RAG System - Video Narration Script

> **Instructions**: Read this script while recording. Actions in [brackets] tell you what to do on screen.

---

## PART 1: Introduction (5 minutes)

---

[SCREEN: Show desktop with VS Code open]

**SAY:**
"Hey! Welcome to the AI Officer RAG system onboarding. I'm going to walk you through the entire codebase, show you how queries flow through the system, and most importantly, show you how to trace and debug using LangSmith."

[SCREEN: Open the documentation file - AI-OFFICER_RAG_COMPLETE_GUIDE.md]

**SAY:**
"I've already sent you this documentation file - the Complete Developer Guide. I'm assuming you've read through it. This video is going to bring that documentation to life with real examples."

---

**SAY:**
"Before we dive into code, let me explain WHAT we're building. This is important because it affects every design decision."

[SCREEN: Scroll to Section 1.1 in the doc]

**SAY:**
"This is NOT a chatbot. We're building what we call Cognitive Twins. These are AI representations that don't just SPEAK like executives - they THINK like them. They use the executive's actual decision-making frameworks, they reference real past decisions, and they maintain personality consistency."

**SAY:**
"For example, if you ask sample-san about expanding to Singapore, the system doesn't just give a generic business answer. It retrieves sample's actual past decisions about market expansion, his risk tolerance, his strategic priorities - and generates a response that reflects HIS thinking pattern."

---

[SCREEN: Scroll to the 6 Core Principles box in the doc]

**SAY:**
"There are 6 core principles that drive this architecture. Let me quickly go through them:"

**SAY:**
"Number 1: Database is the Brain. All cognitive data - personality traits, decision patterns, past decisions - everything comes from PostgreSQL and Neo4j. Nothing is hardcoded. This means we can add new executives without changing code."

**SAY:**
"Number 2: Graph Constrains Vector. This is key. We use the knowledge graph to narrow down the search space BEFORE doing vector similarity search. This makes retrieval 10 to 100 times faster and more relevant."

**SAY:**
"Number 3: Never Say 'I Don't Know' for Opinions. Executives have opinions about everything. If we don't have specific data, the system infers an opinion based on the executive's values and thinking patterns."

**SAY:**
"Number 4: Recency Bias Exploitation. LLMs pay about 2x more attention to the end of prompts. So we put critical instructions LAST. Reasoning goes FIRST to force deeper thinking."

**SAY:**
"Number 5: Soft Targets, Not Hard Limits. Word limits are targets, not ceilings. We say 'aim for 35 words' not 'maximum 35 words'. This allows natural expression."

**SAY:**
"Number 6: Symbolic Guardrails Are Sacred. Safety rules, compliance checks, red flags - these are NEVER overridden by any optimization. Safety is non-negotiable."

---

## PART 2: Architecture Walkthrough (10 minutes)

---

[SCREEN: Open VS Code, show folder tree of RAG directory]

**SAY:**
"Alright, let's look at the codebase structure. I'll walk you through each folder so you know where to find things."

---

[SCREEN: Expand api/ folder]

**SAY:**
"Starting with the API folder. This is your entry point. When a request comes in, it hits these files first."

[SCREEN: Click on api/main.py]

**SAY:**
"main.py is where the FastAPI server is defined. It sets up middleware, CORS, and includes all the routers. If you need to add a new endpoint category, you'd register it here."

[SCREEN: Click on api/langgraph_endpoints.py]

**SAY:**
"langgraph_endpoints.py - this is the main chat endpoint. When users send queries, this file handles the request, invokes the LangGraph workflow, and formats the response. This is probably the file you'll look at most when debugging."

[SCREEN: Click on api/models.py]

**SAY:**
"models.py defines all the Pydantic models - ChatRequest, ChatResponse, and so on. If you need to add a new field to requests or responses, this is where you do it."

---

[SCREEN: Collapse api/, expand langgraph_workflow/]

**SAY:**
"Now the langgraph_workflow folder. This is the brain of the system - it orchestrates the entire query flow."

[SCREEN: Click on langgraph_workflow/graph.py]

**SAY:**
"graph.py defines the StateGraph - think of it as a flowchart in code. Each node is a processing step, and edges define the flow between steps. This is where you see the big picture of how queries are processed."

[SCREEN: Click on langgraph_workflow/state.py]

**SAY:**
"state.py defines WorkflowState - a TypedDict that holds all the data as it flows through the graph. Query, results, LLM response - everything is in this state object."

[SCREEN: Click on langgraph_workflow/nodes.py]

**SAY:**
"nodes.py contains the actual node implementations. Each function here corresponds to a node in the graph. retrieve_vector_node does vector search, generate_response_node calls the LLM, and so on. This is where the business logic lives."

---

[SCREEN: Collapse langgraph_workflow/, expand cognitive_twin/]

**SAY:**
"The cognitive_twin folder handles executive personality and intent detection."

[SCREEN: Click on cognitive_twin/conversational_router.py]

**SAY:**
"conversational_router.py is the first decision point. It looks at the query and decides: is this small talk or does it need retrieval? If someone says 'Hello', we don't need to search the database. If they ask about strategy, we do."

[SCREEN: Click on cognitive_twin/prompt_assembler.py]

**SAY:**
"prompt_assembler.py builds the cognitive prompts using the executive's profile - their values, communication style, decision patterns. This is what makes responses sound like the specific executive."

---

[SCREEN: Collapse cognitive_twin/, expand conversation_engine/prompt/]

**SAY:**
"The conversation_engine folder handles prompt calibration and formatting."

[SCREEN: Click on conversation_engine/prompt/rules.py]

**SAY:**
"rules.py is important - it defines word limits, anti-AI patterns, and response calibration. The word limits here are based on analyzing real sample response patterns. Fast path targets 15 words, standard targets 35, agentic targets 60."

---

[SCREEN: Collapse conversation_engine/, expand hybrid_retrieval/]

**SAY:**
"hybrid_retrieval folder handles the search layer."

[SCREEN: Click on hybrid_retrieval/true_hybrid.py]

**SAY:**
"true_hybrid.py combines vector search from PostgreSQL pgvector with graph context from Neo4j. It uses Reciprocal Rank Fusion to merge results from both sources."

---

[SCREEN: Collapse hybrid_retrieval/, expand llm_integration/]

**SAY:**
"Finally, llm_integration handles all LLM provider communication."

[SCREEN: Click on llm_integration/orchestrator.py]

**SAY:**
"orchestrator.py routes to different handlers based on the path - fast, standard, or agentic. Each path has different prompt strategies and model configurations."

[SCREEN: Click on llm_integration/client_factory.py]

**SAY:**
"client_factory.py abstracts the LLM providers. We support OpenAI, Groq, Gemini, and others. If you need to add a new provider, you'd add it here."

---

**SAY:**
"That's the folder structure. Now let's see this in action with a real query."

---

## PART 3: Live Query Trace (15 minutes)

---

[SCREEN: Open a terminal, navigate to RAG folder]

**SAY:**
"Let me start the server and trace a real query through the system."

[SCREEN: Type and run: python -m api.main]

**SAY:**
"I'm starting the server with python -m api.main. This ensures the Windows-specific asyncio configuration is applied correctly."

[SCREEN: Wait for server to start, show the startup banner]

**SAY:**
"You can see the server is running on port 8000. The banner shows our configuration - host, port, platform. On Windows, reload is disabled to preserve the asyncio event loop policy."

---

[SCREEN: Open a second terminal]

**SAY:**
"Now let me send a query. I'll use curl to send a POST request to our chat endpoint."

[SCREEN: Type the curl command but don't press Enter yet]

```
curl -X POST http://localhost:8000/api/v1/langgraph/chat -H "Content-Type: application/json" -d "{\"query\": \"What are sample-san's top priorities right now?\", \"user_id\": \"demo\", \"profile_id\": \"sample_profile\"}"
```

**SAY:**
"I'm sending a query asking about sample-san's top priorities. Notice the parameters: query is the question, user_id identifies who's asking, and profile_id tells the system which executive to emulate."

[SCREEN: Press Enter, watch the response come back]

**SAY:**
"There's our response. Let me format this so we can see it better."

[SCREEN: Show the JSON response - answer, metadata, session_id]

**SAY:**
"Look at the response structure. We have the answer - that's what the user sees. We have metadata showing the path used, latency, token count. And we have a session_id - this is important for multi-turn conversations."

---

[SCREEN: Switch to the server terminal, scroll up to show logs]

**SAY:**
"Now let's look at what happened on the server side. These logs tell the story of how the query was processed."

[SCREEN: Point to different log lines as you explain]

**SAY:**
"Here you can see... the request came in with a request ID. The cognitive router decided this needs retrieval - it's not just small talk. Vector search found 20 results. The LLM generated a response. Total time was about X milliseconds."

---

**SAY:**
"Now let me show you multi-turn conversation. This is where it gets interesting."

[SCREEN: Copy the session_id from the previous response]

**SAY:**
"I'm going to take that session_id and use it in a follow-up question. Watch what happens when I ask 'Tell me more about the first one'."

[SCREEN: Type and run the second curl command with session_id]

```
curl -X POST http://localhost:8000/api/v1/langgraph/chat -H "Content-Type: application/json" -d "{\"query\": \"Tell me more about the first one\", \"user_id\": \"demo\", \"profile_id\": \"sample_profile\", \"session_id\": \"<paste_session_id>\"}"
```

**SAY:**
"Notice my query just says 'the first one'. I didn't specify what 'the first one' refers to."

[SCREEN: Show the response]

**SAY:**
"But look - the system understood! It knew 'the first one' refers to the first priority mentioned in the previous response. This is reference resolution working. The system maintains conversation history using LangGraph's checkpoint system."

[SCREEN: Switch to server logs]

**SAY:**
"In the logs, you can see 'Restored conversation_history: 2 messages'. That's the previous exchange being loaded from the checkpoint."

---

**SAY:**
"One more demo - Japanese queries. On Windows, curl has encoding issues with Japanese characters. So we added base64 support."

[SCREEN: Run the encode_query.py script]

```
python encode_query.py "シンガポール市場への拡大についてどう思いますか？"
```

**SAY:**
"This script encodes Japanese text to base64. The original question asks 'What do you think about expanding to the Singapore market?'"

[SCREEN: Copy the base64 output and use in curl]

```
curl -X POST http://localhost:8000/api/v1/langgraph/chat -H "Content-Type: application/json" -d "{\"query_base64\": \"<paste_base64>\", \"user_id\": \"demo\", \"profile_id\": \"sample_profile\", \"language\": \"ja\"}"
```

**SAY:**
"I'm using query_base64 instead of query, and setting language to 'ja' for Japanese response."

[SCREEN: Show the Japanese response]

**SAY:**
"And we get a Japanese response! The system decoded the base64, detected the Japanese patterns, routed to retrieval, and generated a response in Japanese. Cross-lingual retrieval working - English documents informing a Japanese response."

---

## PART 4: LangSmith Deep Dive (10 minutes)

---

[SCREEN: Open browser, go to smith.langchain.com]

**SAY:**
"Now let's look at LangSmith. This is our observability platform. Every query creates a trace that shows exactly what happened."

[SCREEN: Log in if needed, navigate to your project]

**SAY:**
"I'm in our project. You can see a list of recent traces. Each row is one query."

[SCREEN: Click on the most recent trace (from our demo)]

**SAY:**
"Let me open the trace from the query we just ran."

---

[SCREEN: Show the trace overview]

**SAY:**
"At the top, you see the overview. Total latency - how long the entire request took. Token usage - prompt tokens and completion tokens. And the status - success or error."

---

[SCREEN: Show the waterfall/tree view of nodes]

**SAY:**
"This waterfall view is gold for debugging. Each row is a step in our LangGraph workflow. Let me walk through them."

[SCREEN: Point to each node as you explain]

**SAY:**
"First, cognitive_route - this is where we decide if retrieval is needed. You can see the input was our query, and the output was 'path: standard, skip_retrieval: false'."

**SAY:**
"Next, analyze_query - query understanding. It classified the intent and complexity."

**SAY:**
"Then retrieve_vector - this is our PostgreSQL pgvector search. You can see it returned 20 results in about 150 milliseconds."

**SAY:**
"retrieve_graph - Neo4j graph context. Found related entities and relationships."

**SAY:**
"fuse_results - combines vector and graph results using Reciprocal Rank Fusion."

**SAY:**
"And finally, generate_response - the LLM call. This is usually the longest step."

---

[SCREEN: Click on the generate_response node to expand it]

**SAY:**
"Let me click on generate_response. This is where you can see the EXACT prompt sent to the LLM."

[SCREEN: Show the input section with system prompt and user prompt]

**SAY:**
"Here's the system prompt. You can see... the executive identity, their values, communication style, word limit instructions. And here's the user prompt with the query and retrieved context."

**SAY:**
"If you ever get a wrong response, THIS is where you debug. Was the prompt wrong? Was the context missing? Was the instruction unclear? It's all here."

---

[SCREEN: Show the output section]

**SAY:**
"And here's the output - the raw LLM response before any post-processing."

---

[SCREEN: Show latency breakdown if available]

**SAY:**
"LangSmith also shows latency breakdown. You can see exactly where time was spent. In this case, the LLM call took about 70% of total time. Retrieval was fast."

---

[SCREEN: Go back to trace list, show filtering options]

**SAY:**
"A few more useful features. You can filter traces by status - find all errors. You can search by metadata - find traces for a specific user or session. And you can compare traces side by side."

**SAY:**
"When you're debugging why one query worked and another didn't, comparing traces is incredibly helpful."

---

## PART 5: Code Walkthrough - Key Files (10 minutes)

---

[SCREEN: Switch back to VS Code]

**SAY:**
"Now let me show you the key code files in more detail. I'll highlight the parts you'll work with most."

---

[SCREEN: Open api/langgraph_endpoints.py, go to line ~80]

**SAY:**
"First, the main chat endpoint in langgraph_endpoints.py."

[SCREEN: Highlight the function definition]

**SAY:**
"This is the langgraph_chat function. It's an async POST endpoint that takes a ChatRequest."

[SCREEN: Scroll through the function, pointing out key sections]

**SAY:**
"First section - request validation and session handling. We extract the query, user_id, profile_id. If there's a session_id, we load the checkpoint to get conversation history."

**SAY:**
"Middle section - we build the initial state and invoke the LangGraph workflow. The workflow.ainvoke call is where the magic happens."

**SAY:**
"Final section - we extract the response from the final state and format it as a ChatResponse."

---

[SCREEN: Open langgraph_workflow/graph.py, go to the graph definition]

**SAY:**
"Now graph.py - the workflow definition."

[SCREEN: Show the StateGraph creation and add_node calls]

**SAY:**
"Here we create a StateGraph with WorkflowState as the state type. Then we add nodes - each add_node call registers a function as a processing step."

[SCREEN: Show the add_edge and add_conditional_edges calls]

**SAY:**
"Then we add edges. Regular edges are unconditional - always go from A to B. Conditional edges use a function to decide the next node. That's how we implement the routing logic."

[SCREEN: Show the compile call]

**SAY:**
"Finally, we compile the graph. This creates the executable workflow. The checkpointer parameter enables conversation memory."

---

[SCREEN: Open langgraph_workflow/nodes.py, find a node function]

**SAY:**
"Let's look at a node implementation in nodes.py."

[SCREEN: Show the retrieve_vector_node function]

**SAY:**
"Here's retrieve_vector_node. Every node function takes the state and returns a dict of state updates."

**SAY:**
"We get the query from state, call the hybrid retrieval system, and return the results. The returned dict gets merged into the state for the next node."

---

[SCREEN: Open cognitive_twin/conversational_router.py, find the route method]

**SAY:**
"Now the conversational router."

[SCREEN: Show the route() method and the pattern matching]

**SAY:**
"The route method looks at the query and checks patterns. Greetings, farewells, small talk - these skip retrieval. Business questions, decisions, opinions - these need retrieval."

[SCREEN: Show the Japanese pattern section]

**SAY:**
"We also have Japanese pattern detection. Japanese business queries with patterns like 'どう思いますか' - 'what do you think' - are routed to retrieval, not treated as small talk."

---

[SCREEN: Open conversation_engine/prompt/rules.py]

**SAY:**
"Finally, rules.py - the response calibration."

[SCREEN: Show WORD_LIMITS dict]

**SAY:**
"Word limits are defined here. Fast path targets 15 words - brief acknowledgments. Standard targets 35 words - opinions with reasoning. Agentic targets 60 words - thorough analysis."

[SCREEN: Show any anti-AI patterns if defined]

**SAY:**
"We also define anti-AI patterns - phrases that sound too robotic. 'I don't have personal opinions', 'As an AI', 'I cannot provide' - these are flagged."

---

## PART 6: Common Tasks & Debugging (5 minutes)

---

[SCREEN: Open terminal]

**SAY:**
"Let me quickly cover common tasks you'll do as a developer."

---

**SAY:**
"Starting the server - always use python -m api.main on Windows. This ensures proper asyncio configuration."

[SCREEN: Type: python -m api.main]

---

**SAY:**
"After making code changes, clear the Python cache. Otherwise Python might use old cached bytecode."

[SCREEN: Type: python clear_cache.py]

---

**SAY:**
"To check if the server is healthy:"

[SCREEN: Type: curl http://localhost:8000/api/v1/health]

---

**SAY:**
"Now, common debugging scenarios."

**SAY:**
"Scenario 1: Query returns wrong results. First, check LangSmith. Look at the retrieve nodes - did we find the right documents? Then look at generate_response - was the prompt correct? Usually it's either bad retrieval or bad prompting."

**SAY:**
"Scenario 2: Multi-turn not working. Make sure you're passing the session_id from the first response. Check server logs for 'Restored conversation_history'. If it says 0 messages, the checkpoint isn't loading."

**SAY:**
"Scenario 3: Japanese characters corrupted. Use query_base64 instead of query. Run python encode_query.py with your Japanese text to get the base64 version."

**SAY:**
"Scenario 4: Server crashes on Windows. Usually an asyncio event loop issue. Make sure you're using python -m api.main, not uvicorn directly."

---

## CLOSING

---

[SCREEN: Show the documentation file]

**SAY:**
"That's the overview. To recap:"

**SAY:**
"We covered the architecture - API layer, LangGraph workflow, cognitive twin, retrieval, LLM integration."

**SAY:**
"We traced a real query through the system - saw the logs, saw the LangSmith trace."

**SAY:**
"We looked at the key code files you'll work with."

**SAY:**
"And we covered common debugging scenarios."

**SAY:**
"The documentation file has all the details. This video was meant to bring it to life."

**SAY:**
"If you have questions, check LangSmith first - the traces usually reveal what's happening. And don't hesitate to reach out."

**SAY:**
"Good luck, and welcome to the team!"

---

## END OF SCRIPT

---

### Post-Recording Checklist
- [ ] Review video for any mistakes
- [ ] Add chapter markers at each PART
- [ ] Add timestamps in description
- [ ] Test all commands shown still work
- [ ] Share LangSmith project access with new developer
