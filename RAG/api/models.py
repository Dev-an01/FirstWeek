"""
Request and Response Models (Pydantic schemas)
"""

from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================================
# REQUEST MODELS
# ============================================================

class QueryRequest(BaseModel):
    """Request model for /api/v1/query endpoint"""
    
    query: str = Field(
        ..., 
        description="User's question",
        min_length=1,
        max_length=500,
        examples=["What decisions did Raj Patel make about technical architecture?"]
    )
    
    user_id: str = Field(
        ...,
        description="Executive ID for personalization and memory retrieval",
        examples=["sample_profile"],
        alias="executive_id"
    )
    
    user_role: str = Field(
        default="employee",
        description="User's role for RBAC",
        examples=["employee", "executive", "manager"]
    )
    
    top_k: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Number of results to return"
    )
    
    min_score: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold"
    )
    
    session_id: Optional[str] = Field(
        default=None,
        description="Conversation session ID (for multi-turn)"
    )

    company_id: Optional[str] = Field(
        default=None,
        description="Company ID for tenant isolation"
    )

    enable_dual_stream: Optional[bool] = Field(
        default=None,
        description="Enable dual-stream prompt building (overrides global setting)"
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "query": "What are the company's data privacy policies?",
                "executive_id": "sample_profile",
                "user_role": "employee",
                "top_k": 10,
                "min_score": 0.4
            }
        }


# ============================================================
# RESPONSE MODELS
# ============================================================

class SourceScore(BaseModel):
    """Source-specific scores"""
    vector: Optional[float] = Field(default=None, description="Vector similarity score")
    graph: Optional[float] = Field(default=None, description="Graph context score")


class Provenance(BaseModel):
    """Provenance information explaining why result is relevant"""
    found_via: str = Field(description="How this result was found (vector/graph/both)")
    entities_matched: Optional[List[str]] = Field(default=None, description="Entities matched from query")
    graph_paths: Optional[List[str]] = Field(default=None, description="Graph traversal paths used")


class RetrievalResult(BaseModel):
    """Single retrieval result"""
    rank: int
    id: str
    title: Optional[str] = None
    content: str
    score: float
    doc_type: str
    scope: str
    source_scores: Optional[SourceScore] = None
    provenance: Optional[Provenance] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalMetadata(BaseModel):
    """Metadata about the retrieval process"""
    total_results: int
    results_returned: int
    query_length: int
    filters_applied: Dict[str, Any]
    performance_ms: float
    sources_used: List[str]


class QueryResponse(BaseModel):
    """Response model for /api/v1/query endpoint"""
    
    success: bool = True
    
    results: List[RetrievalResult] = Field(
        description="Ranked retrieval results"
    )
    
    metadata: RetrievalMetadata = Field(
        description="Retrieval metadata and diagnostics"
    )
    
    request_id: str = Field(
        description="Unique request identifier"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "results": [
                    {
                        "rank": 1,
                        "id": "POLICY-HR-001",
                        "title": "Data Privacy Policy",
                        "content": "TechNova is committed to protecting employee and customer data...",
                        "score": 0.89,
                        "doc_type": "policy",
                        "scope": "public",
                        "source_scores": {
                            "vector": 0.87,
                            "graph": None
                        },
                        "provenance": {
                            "found_via": "vector",
                            "entities_matched": ["data", "privacy"]
                        },
                        "metadata": {}
                    }
                ],
                "metadata": {
                    "total_results": 5,
                    "results_returned": 5,
                    "query_length": 42,
                    "filters_applied": {"role": "employee", "scopes": ["public", "internal"]},
                    "performance_ms": 214.5,
                    "sources_used": ["vector"]
                },
                "request_id": "req_abc123",
                "timestamp": "2025-10-26T07:30:00Z"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(description="Service status")
    version: str = Field(description="API version")
    services: Dict[str, str] = Field(description="Service health statuses")
    uptime_seconds: Optional[float] = None
    cache_metrics: Optional[Dict[str, Any]] = Field(default=None, description="Cache performance metrics")


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error info")
    request_id: Optional[str] = Field(default=None)


# ============================================================
# CHAT ENDPOINT MODELS (LLM Integration)
# ============================================================

class ChatRequest(BaseModel):
    """Request model for /api/v1/chat endpoint with LLM integration"""

    query: str = Field(
        default="",
        description="User's question (use query_base64 for Japanese text on Windows)",
        max_length=500,
        examples=["What decisions did Raj Patel make about technical architecture?"]
    )

    query_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded UTF-8 query (use this for Japanese text on Windows to avoid encoding issues). "
                    "Example: 'こんにちは' -> 'eyJxdWVyeSI6ICLjgZPjgpPjgavjgaHjga8ifQ=='",
        examples=["44K344Oz44Ks44Od44O844Or5biC5aC044G444Gu5ouh5aSn44Gr44Gk44GE44Gm44Gp44GG5oCd44GE44G+44GZ44GL77yf"]
    )
    
    user_id: str = Field(
        ...,
        description="User making the request",
        examples=["U12345", "user@company.com"]
    )
    
    user_role: str = Field(
        default="employee",
        description="User's role for RBAC",
        examples=["employee", "executive", "manager"]
    )
    
    profile_id: str = Field(
        ...,
        description="Executive profile to use for response personality (sample_profile=sample_profile CEO)",
        examples=["sample_profile"]
    )

    language: str = Field(
        default="en",
        description="Response language preference (en for English, ja for Japanese)",
        examples=["en", "ja"]
    )

    voice_profile_id: Optional[str] = Field(
        default=None,
        description="Voice profile ID for TTS synthesis (for future voice cloning)",
        examples=["exec_004_test", "exec_001_test", "ceo_voice"]
    )

    streaming_mode: str = Field(
        default="immediate",
        description="Audio streaming mode: immediate (real-time), buffered (2-sec blocks for video), sentence (sentence-level buffering)",
        examples=["immediate", "buffered", "sentence"]
    )

    force_path: Optional[str] = Field(
        default=None,
        description="Override automatic routing (fast/standard/agentic)",
        examples=["fast", "standard", "agentic"]
    )
    
    session_id: Optional[str] = Field(
        default=None,
        description="Conversation session ID for multi-turn chat"
    )
    
    top_k: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Number of retrieval results to use"
    )
    
    min_score: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for retrieval"
    )

    enable_evaluation: bool = Field(
        default=False,
        description="Enable RAGAS quality evaluation. Returns evaluation_metrics in response."
    )

    company_id: Optional[str] = Field(
        default=None,
        description="Company ID for tenant isolation"
    )

    enable_video_push: Optional[bool] = Field(
        default=False,
        description="Enable direct audio push to Video Service (GCP) for avatar lip-sync."
    )

    @model_validator(mode='after')
    def decode_base64_query(self) -> 'ChatRequest':
        """
        Decode base64-encoded query if provided.

        This allows Japanese text to be sent from Windows clients that have
        UTF-8 encoding issues with curl/PowerShell.

        Usage:
            # Encode Japanese query as base64:
            # echo -n "シンガポール市場への拡大についてどう思いますか？" | base64
            # Result: 44K344Oz44Ks44Od44O844Or5biC5aC044G444Gu5ouh5aSn44Gr44Gk44GE44Gm44Gp44GG5oCd44GE44G+44GZ44GL77yf

            curl -X POST .../chat -d '{"query_base64": "44K344Oz44Ks44...", "user_id": "..."}'
        """
        import base64

        # If query_base64 is provided, decode it and use as query
        if self.query_base64:
            try:
                decoded_bytes = base64.b64decode(self.query_base64)
                self.query = decoded_bytes.decode('utf-8')
            except Exception as e:
                raise ValueError(f"Invalid base64 encoding in query_base64: {e}")

        # Validate that we have a query
        if not self.query or len(self.query.strip()) == 0:
            raise ValueError("Either 'query' or 'query_base64' must be provided")

        return self

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Should we invest in building our own data center or use cloud infrastructure?",
                "user_id": "U12345",
                "user_role": "executive",
                "profile_id": "akiko_tanaka",
                "top_k": 10,
                "min_score": 0.4
            }
        }


class Citation(BaseModel):
    """Citation extracted from LLM response"""
    source: str = Field(description="Source document name/ID")
    raw_text: str = Field(description="Raw citation text from response")
    position: int = Field(description="Character position in response")
    context: str = Field(description="Surrounding context snippet")


class ChatMetadata(BaseModel):
    """Metadata for chat response"""
    total_latency_ms: float = Field(description="Total request latency")
    llm_latency_ms: float = Field(description="LLM generation latency")
    retrieval_latency_ms: Optional[float] = None
    path: str = Field(description="Processing path used (fast/standard/agentic)")
    routing_confidence: Optional[float] = None
    routing_reasoning: Optional[str] = None
    llm_model: str = Field(description="LLM model used")
    llm_provider: str = Field(description="LLM provider (openai/groq)")
    llm_tokens: Dict[str, int] = Field(description="Token usage breakdown")
    profile_id: str = Field(description="Executive profile used")
    results_used: int = Field(description="Number of retrieval results used")
    citation_count: int = Field(description="Number of citations in response")
    unique_sources: int = Field(description="Number of unique sources cited")

    # NEW FIELDS - Advanced Features
    summarization_stats: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Document summarization statistics (docs compressed, tokens saved, compression ratio)"
    )
    react_steps: Optional[int] = Field(
        default=None,
        description="Number of ReAct reasoning steps (for agentic path)"
    )
    reranking_strategy: Optional[str] = Field(
        default=None,
        description="Adaptive reranking strategy used (lightweight/medium/full)"
    )
    context_quality: Optional[str] = Field(
        default=None,
        description="Context quality level (HIGH/MEDIUM/LOW)"
    )
    trace_id: Optional[str] = Field(
        default=None,
        description="Trace ID for linking to detailed execution trace"
    )
    
    # LangSmith Integration 
    langsmith_run_id: Optional[str] = Field(
        default=None,
        description="LangSmith run ID for feedback linkage and trace visualization"
    )

    # Response formatting metadata (existing fields)
    formatting_time_ms: Optional[float] = None
    citation_accuracy: Optional[float] = None
    source_diversity: Optional[float] = None
    citation_density: Optional[float] = None

    # RAGAS Evaluation Metrics
    evaluation_metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="RAGAS quality evaluation metrics (faithfulness, relevancy, precision, overall score, grade)"
    )


class ChatResponse(BaseModel):
    """Response model for /api/v1/chat endpoint"""
    
    success: bool = True
    
    answer: str = Field(
        description="Natural language response from LLM"
    )
    
    citations: List[Citation] = Field(
        description="Citations extracted from response",
        default_factory=list
    )
    
    sources: List[str] = Field(
        description="List of unique source documents used",
        default_factory=list
    )
    
    metadata: ChatMetadata = Field(
        description="Response metadata and diagnostics"
    )
    
    request_id: str = Field(
        description="Unique request identifier"
    )
    
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for conversation tracking"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "answer": "Based on our current strategic priorities and technical infrastructure, I recommend we adopt a hybrid approach...",
                "citations": [
                    {
                        "source": "Infrastructure Decision Memo 2024",
                        "raw_text": "[Source: Infrastructure Decision Memo 2024]",
                        "position": 45,
                        "context": "...our strategic priorities and technical infrastructure [Source: Infrastructure Decision Memo 2024] suggest a hybrid approach..."
                    }
                ],
                "sources": ["Infrastructure Decision Memo 2024", "Cloud Cost Analysis Report"],
                "metadata": {
                    "total_latency_ms": 2145.3,
                    "llm_latency_ms": 1834.2,
                    "path": "standard",
                    "routing_confidence": 0.87,
                    "llm_model": "gpt-4",
                    "llm_provider": "openai",
                    "llm_tokens": {"prompt_tokens": 1250, "completion_tokens": 420, "total_tokens": 1670},
                    "profile_id": "akiko_tanaka",
                    "results_used": 10,
                    "citation_count": 2,
                    "unique_sources": 2
                },
                "request_id": "req_xyz789",
                "timestamp": "2025-10-26T07:30:00Z"
            }
        }


# ============================================================
# AUDIO STREAMING MODELS (For Interruption Support)
# ============================================================

class InterruptRequest(BaseModel):
    """Request to interrupt streaming session"""
    session_id: str = Field(
        ...,
        description="Session ID to interrupt",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )


class InterruptResponse(BaseModel):
    """Response from interruption request"""
    success: bool = Field(description="Whether interruption was successful")
    session_id: str = Field(description="Session ID that was interrupted")
    state: str = Field(description="New session state after interruption")
    message: str = Field(description="Human-readable status message")
