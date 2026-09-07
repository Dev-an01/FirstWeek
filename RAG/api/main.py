"""
FastAPI Server - AI Officer RAG API
Main entry point for the API

Updated to integrate with True Hybrid Retrieval system
"""

# ============================================================
# CRITICAL: Fix Windows UTF-8 Encoding for Japanese Input
# ============================================================
# Windows uses cp1252/cp932 by default, which corrupts Japanese characters
# This MUST be at the very top, before any other imports that might print
import sys
import io
import os

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    # Set environment variable for Python UTF-8 mode
    os.environ['PYTHONUTF8'] = '1'

    # Wrap stdout/stderr with UTF-8 encoding
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    # Set default encoding for file operations
    if hasattr(sys, 'setdefaultencoding'):
        sys.setdefaultencoding('utf-8')

# ============================================================
# CRITICAL: Fix Windows asyncio event loop for psycopg
# ============================================================
# Windows uses ProactorEventLoop by default, but psycopg requires
# SelectorEventLoop for async PostgreSQL connections
# This MUST be set before any asyncio operations
import asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print("✅ [Windows] Set WindowsSelectorEventLoopPolicy for psycopg compatibility")
import logging
import time
import uuid
import json
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from api.config import settings
from api.models import (
    QueryRequest,
    QueryResponse,
    ChatRequest,
    ChatResponse,
    Citation,
    ChatMetadata,
    HealthResponse,
    ErrorResponse,
    RetrievalResult,
    SourceScore,
    Provenance,
    RetrievalMetadata,
    InterruptRequest,
    InterruptResponse
)
from api.dependencies import get_vector_engine, get_graph_provider, retrieval_system, get_db_pool, resolve_company_id
from vector_search.search_engine import VectorSearchEngine
from graph_context.provider import GraphContextProvider
from llm_integration.orchestrator import LLMOrchestrator
from profile_management.profile_id_mapper import normalize_profile_id
import asyncpg
from memory.session_manager import SessionManager
from memory.conversation_sessions import ConversationSessions

# Memory integration
from hybrid_retrieval.memory_search import MultiSignalMemorySearch

# ConversationEngine integration
try:
    from conversation_engine import get_conversation_engine
    CONVERSATION_ENGINE_AVAILABLE = True
except ImportError:
    CONVERSATION_ENGINE_AVAILABLE = False
    get_conversation_engine = None

# GraphRAG and RAGAS evaluation
try:
    from graph_rag import GraphRAGProvider
    GRAPHRAG_AVAILABLE = True
except ImportError:
    GRAPHRAG_AVAILABLE = False
    GraphRAGProvider = None

try:
    from evaluation import RAGASEvaluator
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    RAGASEvaluator = None

# Import caching and response formatting
from cache import CacheManager, create_cache_manager
from cache.cache_integration import CacheIntegrationManager
from llm_integration.advanced_response_formatter import AdvancedResponseFormatter
# Import session and feedback endpoints
from api import session_endpoints, feedback_endpoints
# Import meeting scheduler
from services.scheduler_service import start_scheduler, stop_scheduler

# Observability
from observability import StructuredLogger, setup_logging
from observability.middleware import ObservabilityMiddleware
from observability.tracing import setup_tracing, shutdown_tracing
from observability.metrics import get_metrics
from observability.business_metrics_updater import start_metrics_updater, stop_metrics_updater
from fastapi.responses import Response as FastAPIResponse

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
obs_logger = StructuredLogger(__name__)  # Observability logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events
    Handles startup and shutdown
    """
    # STARTUP
    logger.info("=" * 70)
    logger.info("STARTING AI OFFICER RAG API")
    logger.info("=" * 70)
    
    # ============================================================
    # OBSERVABILITY SETUP (NEW)
    # ============================================================
    try:
        # Initialize structured logging
        setup_logging(level="INFO", log_file="logs/app.log")
        obs_logger.info("Observability logging initialized")
        
        # Initialize distributed tracing
        setup_tracing()
        obs_logger.info("Distributed tracing initialized")
        
    except Exception as e:
        logger.warning(f"Observability initialization failed (non-critical): {e}")
    
    try:
        # Initialize retrieval system
        retrieval_system.initialize()
        
        # Initialize cache manager
        app.state.cache_manager = create_cache_manager()
        
        # Initialize cache integration manager
        app.state.cache_integration = CacheIntegrationManager(app.state.cache_manager)
        
        # Initialize database pool for session management
        async def _init_db_connection(conn):
            """Set up JSON/JSONB codecs for proper serialization."""
            await conn.set_type_codec(
                'jsonb',
                encoder=json.dumps,
                decoder=json.loads,
                schema='pg_catalog',
                format='text',
            )

        app.state.db_pool = await asyncpg.create_pool(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            min_size=5,
            max_size=20,
            init=_init_db_connection
        )
        
        # Initialize session management
        conversation_sessions = ConversationSessions(app.state.db_pool)
        app.state.session_manager = SessionManager(conversation_sessions)
        await app.state.session_manager.initialize()

        # Initialize active_sessions tracker for audio streaming (Phase 8 - Audio Integration)
        app.state.active_sessions = {}
        logger.info("✅ Audio streaming session tracker initialized")

        # Initialize video_clients connection pool (WebRTC video service)
        app.state.video_clients = {}
        logger.info("✅ Video service connection pool initialized")

        # Start video client cleanup task (remove stale connections every 2 minutes)
        async def cleanup_stale_video_clients():
            """Background task to cleanup stale video service connections"""
            while True:
                try:
                    await asyncio.sleep(120)  # Check every 2 minutes
                    if hasattr(app.state, 'video_clients'):
                        stale_sessions = []
                        for session_id, client in list(app.state.video_clients.items()):
                            if client.is_stale(max_idle_seconds=300):  # 5 minutes idle
                                stale_sessions.append(session_id)
                                try:
                                    await client.disconnect()
                                    logger.info(f"🧹 Cleaned up stale video client: {session_id}")
                                except Exception as e:
                                    logger.warning(f"Error disconnecting stale client {session_id}: {e}")

                        for session_id in stale_sessions:
                            app.state.video_clients.pop(session_id, None)

                        if stale_sessions:
                            logger.info(f"🧹 Cleaned up {len(stale_sessions)} stale video connections")

                except Exception as e:
                    logger.error(f"Error in video client cleanup task: {e}")

        app.state.cleanup_task = asyncio.create_task(cleanup_stale_video_clients())
        logger.info("✅ Video client cleanup task started (2min interval, 5min timeout)")

        # Start meeting scheduler (Phase 8 - Bot Scheduling)
        start_scheduler()
        logger.info("✅ Meeting scheduler started")

        # Initialize LLM orchestrator (NEW: Direct initialization for all features)
        from config.llm_config_loader import LLMConfig
        llm_config = LLMConfig()
        active_provider = llm_config.active_provider
        base_llm_orchestrator = LLMOrchestrator(provider=active_provider)
        app.state.llm_orchestrator = app.state.cache_integration.integrate_llm_orchestrator(
            base_llm_orchestrator
        )
        # Store base orchestrator for LangGraph (it needs unwrapped version)
        app.state.base_llm_orchestrator = base_llm_orchestrator
        logger.info(f"✅ LLM Orchestrator initialized with {active_provider} provider")

        # Initialize Query Router (NEW: For 3-path routing)
        from hybrid_retrieval.query_router import QueryRouter
        app.state.query_router = QueryRouter()
        logger.info("✅ Query Router initialized (fast/standard/agentic paths)")

        # Initialize Vector Search Engine (for direct access in endpoints)
        app.state.vector_engine = retrieval_system.get_vector_engine()
        logger.info("✅ Vector Search Engine initialized")

        # Initialize Graph Provider (for direct access in endpoints)
        app.state.graph_provider = retrieval_system.get_graph_provider()
        logger.info("✅ Graph Context Provider initialized")

        # Initialize TTS Manager and start warmup (Phase 8 - Audio Integration)
        # This prevents cold start delay on first TTS request
        from audio_services.tts_manager import get_tts_manager
        tts_manager = await get_tts_manager()
        # Set DB pool on TTS service for per-executive voice key loading
        if hasattr(tts_manager._tts_service, 'set_db_pool'):
            tts_manager._tts_service.set_db_pool(app.state.db_pool)
            logger.info("✅ TTS Service DB pool set for per-executive voice keys")
        # Fire and forget warmup (don't block startup)
        asyncio.create_task(tts_manager.warmup())
        logger.info("✅ TTS Service warmup started in background")

        # Initialize STT Service and start warmup
        from audio_services.stt_service import get_stt_service
        stt_service = get_stt_service()
        asyncio.create_task(stt_service.warmup())
        logger.info("✅ STT Service warmup started in background")

        #
        # Memory Search Engine Initialization
        #
        try:
            # Build postgres_config for MultiSignalMemorySearch
            postgres_config = {
                'host': settings.POSTGRES_HOST,
                'port': int(settings.POSTGRES_PORT),
                'database': settings.POSTGRES_DB,
                'user': settings.POSTGRES_USER,
                'password': settings.POSTGRES_PASSWORD
            }

            # Initialize MultiSignalMemorySearch for episodic memory retrieval
            app.state.memory_search_engine = MultiSignalMemorySearch(
                postgres_config=postgres_config,
                preload_model=True  # Pre-load embedding model to eliminate first-query delay
            )
            logger.info("✅ MultiSignalMemorySearch initialized")
            logger.info("   - 5-signal scoring: semantic(40%) + temporal(25%) + importance(20%) + multipliers")
            logger.info("   - Executive memory separation enabled")
        except Exception as e:
            logger.warning(f"⚠️  MultiSignalMemorySearch initialization failed: {e}")
            logger.warning("   Memory retrieval will be disabled")
            app.state.memory_search_engine = None

        #
        # LangGraph Checkpointer Initialization
        # Using AsyncPostgresSaver for async streaming support (astream)
        #
        app.state.langgraph_checkpointer = None
        app.state.checkpointer_pool = None  # Store pool reference for cleanup
        try:
            # Try to use AsyncPostgresSaver for async checkpointing (required for astream)
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool

            # Build connection string for PostgresSaver
            checkpoint_conn_string = (
                f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
                f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
            )

            # Initialize async connection pool (required for AsyncPostgresSaver)
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
            }
            app.state.checkpointer_pool = AsyncConnectionPool(
                conninfo=checkpoint_conn_string,
                max_size=10,
                kwargs=connection_kwargs,
            )
            # Open the async connection pool
            await app.state.checkpointer_pool.open()

            # Initialize AsyncPostgresSaver with async connection pool
            app.state.langgraph_checkpointer = AsyncPostgresSaver(app.state.checkpointer_pool)

            # Setup checkpointer (creates tables if needed) - async version
            await app.state.langgraph_checkpointer.setup()

            logger.info("✅ AsyncPostgresSaver checkpointer initialized")
            logger.info("   - Async conversation threading enabled")
            logger.info("   - State checkpointing enabled (supports astream)")
        except ImportError as e:
            logger.warning(f"⚠️  AsyncPostgresSaver dependencies not available: {e}")
            logger.warning("   Falling back to MemorySaver (in-memory checkpointing)")
            try:
                from langgraph.checkpoint.memory import MemorySaver
                app.state.langgraph_checkpointer = MemorySaver()
                logger.info("✅ MemorySaver checkpointer initialized (fallback)")
                logger.info("   - In-memory conversation threading enabled")
                logger.info("   - Note: State will be lost on restart")
            except ImportError:
                logger.warning("⚠️  No checkpointer available - threading disabled")
                app.state.langgraph_checkpointer = None
        except Exception as e:
            logger.warning(f"⚠️  Checkpointer initialization failed: {e}")
            logger.warning("   Falling back to MemorySaver")
            try:
                from langgraph.checkpoint.memory import MemorySaver
                app.state.langgraph_checkpointer = MemorySaver()
                logger.info("✅ MemorySaver checkpointer initialized (after AsyncPostgresSaver failure)")
            except Exception as fallback_e:
                logger.warning(f"⚠️  MemorySaver also failed: {fallback_e}")
                logger.warning("   LangGraph threading will be disabled")
                app.state.langgraph_checkpointer = None

        #
        # GraphRAG Provider Initialization
        #
        app.state.graphrag_provider = None
        if GRAPHRAG_AVAILABLE:
            try:
                # Get Neo4j driver from graph provider
                neo4j_driver = app.state.graph_provider.driver if hasattr(app.state.graph_provider, 'driver') else None

                if neo4j_driver:
                    # Get embedding model from retrieval system
                    embedding_model = retrieval_system.get_embedding_model() if hasattr(retrieval_system, 'get_embedding_model') else None

                    app.state.graphrag_provider = GraphRAGProvider(
                        neo4j_driver=neo4j_driver,
                        embedding_model=embedding_model,
                        llm_client=app.state.base_llm_orchestrator,
                        cache_ttl_seconds=3600  # 1 hour cache
                    )
                    logger.info("✅ GraphRAGProvider initialized")
                    logger.info("   - Global search for broad/thematic queries")
                    logger.info("   - Community-based summarization enabled")
                else:
                    logger.warning("⚠️  GraphRAGProvider skipped - Neo4j driver not available")
            except Exception as e:
                logger.warning(f"⚠️  GraphRAGProvider initialization failed: {e}")
                logger.warning("   Global search will be disabled")
        else:
            logger.info("⚠️  GraphRAGProvider not available (graph_rag module not found)")

        #
        # RAGAS Evaluator Initialization
        #
        app.state.ragas_evaluator = None
        if RAGAS_AVAILABLE:
            try:
                # Get embedding model for lightweight evaluation
                embedding_model = retrieval_system.get_embedding_model() if hasattr(retrieval_system, 'get_embedding_model') else None

                app.state.ragas_evaluator = RAGASEvaluator(
                    llm_client=app.state.base_llm_orchestrator,  # Pass LLM for RAGAS evaluation
                    embedding_model=embedding_model,
                    enable_async=True,
                    use_lightweight_fallback=True
                )
                logger.info("✅ RAGASEvaluator initialized")
                logger.info(f"   - RAGAS library: {'available' if app.state.ragas_evaluator.is_ragas_available() else 'not available (using lightweight)'}")
                logger.info("   - Metrics: faithfulness, relevancy, context precision")
            except Exception as e:
                logger.warning(f"⚠️  RAGASEvaluator initialization failed: {e}")
                logger.warning("   Quality evaluation will be disabled")
        else:
            logger.info("⚠️  RAGASEvaluator not available (evaluation module not found)")

        #
        # Conversation Engine Initialization
        #
        app.state.conversation_engine = None
        if CONVERSATION_ENGINE_AVAILABLE:
            try:
                # Get profile manager from LLM orchestrator
                profile_manager = app.state.base_llm_orchestrator.profile_manager

                # Initialize ConversationEngine with session manager and profile manager
                app.state.conversation_engine = get_conversation_engine(
                    session_manager=app.state.session_manager,
                    profile_manager=profile_manager
                )
                logger.info("✅ ConversationEngine initialized")
                logger.info("   - 5-stage prompt pipeline enabled")
                logger.info("   - Modes: STATELESS, SESSION, MEMORY_AWARE")

                # Warm VoiceprintEmbeddingCache for semantic attention
                # Pre-computes category embeddings at startup for zero-cost semantic similarity
                try:
                    from conversation_engine.calibration import get_voiceprint_embedding_cache
                    vp_cache = get_voiceprint_embedding_cache()
                    warm_stats = vp_cache.warm_cache()
                    logger.info(f"✅ VoiceprintEmbeddingCache warmed")
                    logger.info(f"   - Executives: {warm_stats['executives_loaded']}")
                    logger.info(f"   - Category embeddings: {warm_stats['total_embeddings']}")
                    logger.info(f"   - Warm time: {warm_stats['warm_time_ms']:.0f}ms")
                except Exception as cache_error:
                    logger.warning(f"⚠️  VoiceprintEmbeddingCache warm failed: {cache_error}")
                    logger.warning("   Semantic attention will use pattern-only fallback")

            except Exception as e:
                logger.warning(f"⚠️  ConversationEngine initialization failed: {e}")
                logger.warning("   Legacy prompt builders will be used")
        else:
            logger.info("⚠️  ConversationEngine not available (conversation_engine module not found)")

        # Initialize Unified Retrieval (for /query endpoint compatibility)
        from hybrid_retrieval.manager import HybridRetrievalManager
        app.state.unified_retrieval = HybridRetrievalManager(
            vector_search_engine=retrieval_system.get_vector_engine(),
            graph_context_provider=retrieval_system.get_graph_provider(),
            memory_search_engine=app.state.memory_search_engine,
            enable_cache=True,
            enable_metrics=True,
            enable_decomposition=False  # Disable to avoid SubQueryProcessor initialization issue
        )
        logger.info("✅ Unified Retrieval (HybridRetrievalManager) initialized")

        # NOTE: We use LLMOrchestrator directly in /chat endpoint for better integration
        
        # Initialize advanced response formatter
        app.state.response_formatter = AdvancedResponseFormatter(
            citation_style=settings.CITATION_STYLE,
            enable_validation=settings.CITATION_VALIDATION_ENABLED,
            confidence_threshold=settings.CITATION_CONFIDENCE_THRESHOLD
        )
        
        #
        # LANGGRAPH WORKFLOW INITIALIZATION
        #
        try:
            from langgraph_workflow import create_rag_workflow
            from hybrid_retrieval.query_analyzer import QueryAnalyzer
            from hybrid_retrieval.result_fusion import ResultFusion
            from hybrid_retrieval.adaptive_reranker import AdaptiveReranker
            
            logger.info("Initializing LangGraph workflow...")

            # Create workflow with dependency injection
            # Initialize LangGraph workflow with all integrations
            app.state.langgraph_workflow = create_rag_workflow(
                vector_engine=app.state.vector_engine,
                graph_provider=app.state.graph_provider,
                query_analyzer=QueryAnalyzer(),
                query_router=app.state.query_router,
                result_fusion=ResultFusion(),
                adaptive_reranker=AdaptiveReranker(),
                llm_orchestrator=app.state.base_llm_orchestrator,  # Use unwrapped version for LangGraph
                session_manager=app.state.session_manager,
                hybrid_retrieval_manager=app.state.unified_retrieval,
                memory_search_engine=app.state.memory_search_engine,
                checkpointer=app.state.langgraph_checkpointer,
                graphrag_provider=app.state.graphrag_provider,
                ragas_evaluator=app.state.ragas_evaluator,
                conversation_engine=app.state.conversation_engine
            )

            # Log initialization status
            memory_status = "enabled" if app.state.memory_search_engine else "disabled"
            checkpoint_status = "enabled" if app.state.langgraph_checkpointer else "disabled"
            graphrag_status = "enabled" if app.state.graphrag_provider else "disabled"
            ragas_status = "enabled" if app.state.ragas_evaluator else "disabled"
            conv_engine_status = "enabled" if app.state.conversation_engine else "disabled"

            logger.info("✅ LangGraph workflow initialized")
            logger.info("   - 3 paths: fast/standard/agentic")
            logger.info("   - ReAct sub-graph enabled")
            logger.info(f"   - Memory integration: {memory_status}")
            logger.info(f"   - Threading/checkpointing: {checkpoint_status}")
            logger.info(f"   - GraphRAG global search: {graphrag_status}")
            logger.info(f"   - RAGAS evaluation: {ragas_status}")
            logger.info(f"   - ConversationEngine: {conv_engine_status}")
            logger.info("   - Endpoints: /api/v1/langgraph/*")
            
        except Exception as e:
            logger.warning(f"⚠️  LangGraph workflow initialization failed (non-critical): {e}")
            logger.warning("   Legacy orchestrator will be used")
            app.state.langgraph_workflow = None
        
        # Store startup time
        app.state.startup_time = time.time()

        #
        # DYNAMIC PROFILE REGISTRY (Multi-tenant support)
        #
        try:
            from profile_management.profile_id_mapper import ProfileIDMapper
            profile_count = await ProfileIDMapper.refresh_from_db(app.state.db_pool)
            logger.info(f"✅ Dynamic profile registry loaded: {profile_count} profiles")
        except Exception as e:
            logger.warning(f"⚠️  Dynamic profile registry refresh failed (non-critical): {e}")

        #
        # START BUSINESS METRICS UPDATER (TEMPORARILY DISABLED)
        #
        # DISABLED: Missing user_activity table in database
        # TODO: Create user_activity table, then uncomment this
        # try:
        #     app.state.metrics_updater = await start_metrics_updater(update_interval_seconds=60)
        #     logger.info("✅ Business metrics updater started (60s interval)")
        # except Exception as e:
        #     logger.warning(f"Business metrics updater failed to start (non-critical): {e}")
        logger.info("⚠️  Business metrics updater disabled (missing user_activity table)")

        logger.info("✅ API Server ready")
        logger.info(f"   Listening on http://{settings.HOST}:{settings.PORT}")
        logger.info(f"   Swagger UI: http://{settings.HOST}:{settings.PORT}/docs")
        logger.info("✅ Cache system initialized")
        logger.info("✅ Advanced response formatter initialized")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    
    yield  # Server is running
    
    # SHUTDOWN
    logger.info("Shutting down API server...")

    # Stop business metrics updater (NEW)
    try:
        await stop_metrics_updater()
        logger.info("✅ Business metrics updater stopped")
    except Exception as e:
        logger.warning(f"Business metrics updater shutdown error: {e}")

    # Shutdown session manager
    if hasattr(app.state, 'session_manager'):
        await app.state.session_manager.shutdown()

    # Close database pool
    if hasattr(app.state, 'db_pool'):
        await app.state.db_pool.close()

    # Close checkpointer async connection pool
    if hasattr(app.state, 'checkpointer_pool') and app.state.checkpointer_pool:
        try:
            await app.state.checkpointer_pool.close()
            logger.info("✅ Checkpointer async connection pool closed")
        except Exception as e:
            logger.warning(f"Checkpointer pool shutdown error: {e}")

    # Shutdown observability (NEW)
    try:
        shutdown_tracing()
        obs_logger.info("Observability shutdown complete")
    except Exception as e:
        logger.warning(f"Observability shutdown error: {e}")
    
    # Stop meeting scheduler
    try:
        stop_scheduler()
        logger.info("✅ Meeting scheduler stopped")
    except Exception as e:
        logger.warning(f"Meeting scheduler shutdown error: {e}")

    # Stop video client cleanup task and disconnect all clients
    if hasattr(app.state, 'cleanup_task'):
        app.state.cleanup_task.cancel()
        try:
            await app.state.cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("✅ Video client cleanup task stopped")

    if hasattr(app.state, 'video_clients'):
        for session_id, client in list(app.state.video_clients.items()):
            try:
                await client.disconnect()
                logger.info(f"Disconnected video client: {session_id}")
            except Exception as e:
                logger.warning(f"Error disconnecting video client {session_id}: {e}")
        app.state.video_clients.clear()
        logger.info("✅ All video clients disconnected")

    logger.info("✅ Shutdown complete")


# ============================================================
# FASTAPI APP INITIALIZATION
# ============================================================

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",  # Swagger UI at http://localhost:8000/docs
    redoc_url="/redoc"  # ReDoc at http://localhost:8000/redoc
)

from firstweek.api import router as firstweek_router
app.include_router(firstweek_router)


# ============================================================
# OBSERVABILITY MIDDLEWARE (NEW)
# ============================================================
app.add_middleware(ObservabilityMiddleware)

# Proxy Headers Middleware - Must be before CORS
# Handles X-Forwarded-Proto and X-Forwarded-Host from Caddy
@app.middleware("http")
async def proxy_headers_middleware(request: Request, call_next):
    """Handle X-Forwarded-* headers from reverse proxy"""
    # Get the forwarded protocol (http/https)
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
    forwarded_host = request.headers.get("X-Forwarded-Host", request.headers.get("host", ""))

    # Update request scope with correct scheme and host
    request.scope["scheme"] = forwarded_proto
    if forwarded_host:
        request.scope["server"] = (forwarded_host, 443 if forwarded_proto == "https" else 80)

    response = await call_next(request)
    return response

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# UTF-8 ENCODING MIDDLEWARE (Windows Japanese Fix)
# ============================================================
# This middleware ensures proper UTF-8 decoding of request bodies
# Critical for Japanese text input on Windows systems

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest


class UTF8EncodingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to ensure proper UTF-8 encoding of request bodies.

    Windows systems often have encoding issues with non-ASCII characters.
    This middleware explicitly handles UTF-8 decoding for JSON bodies.

    CRITICAL: Windows curl/PowerShell may corrupt UTF-8 Japanese text before
    it even reaches Python. This middleware logs the RAW BYTES to diagnose.
    """

    async def dispatch(self, request: StarletteRequest, call_next):
        # Only process for content types that might have encoding issues
        content_type = request.headers.get('content-type', '')

        if 'application/json' in content_type:
            try:
                # Read the raw body BYTES (before any decoding)
                body = await request.body()

                if body:
                    # Log raw bytes for diagnosis (first 200 bytes)
                    raw_hex = body[:200].hex()

                    # Check if raw bytes contain valid UTF-8 Japanese (look for e3 xx xx patterns)
                    has_utf8_japanese = b'\xe3' in body[:200] or b'\xe5' in body[:200] or b'\xe4' in body[:200]

                    # Check if we see 3f (question mark) where Japanese should be
                    # Japanese text in JSON would be: "query":"[japanese]"
                    has_suspicious_qmarks = body.count(b'?') > 5

                    if has_suspicious_qmarks and not has_utf8_japanese:
                        logger.warning(
                            f"[UTF8-RAW-BYTES] ⚠️ ENCODING CORRUPTION DETECTED AT HTTP LAYER!"
                        )
                        logger.warning(
                            f"[UTF8-RAW-BYTES] Raw bytes contain {body.count(b'?')} question marks "
                            f"but no UTF-8 Japanese patterns (e3/e4/e5)"
                        )
                        logger.warning(
                            f"[UTF8-RAW-BYTES] First 100 bytes hex: {raw_hex[:200]}"
                        )
                        logger.warning(
                            f"[UTF8-RAW-BYTES] This means the CLIENT (curl/PowerShell) sent corrupted data."
                        )
                        logger.warning(
                            f"[UTF8-RAW-BYTES] Fix: Use UTF-8 encoded file input or PowerShell with proper encoding."
                        )
                    elif has_utf8_japanese:
                        logger.info(
                            f"[UTF8-RAW-BYTES] ✅ Valid UTF-8 Japanese detected in raw request"
                        )
                        # Log a snippet to confirm
                        logger.info(f"[UTF8-RAW-BYTES] Raw hex snippet: {raw_hex[:100]}")

            except Exception as e:
                logger.debug(f"[UTF8-MIDDLEWARE] Could not inspect body: {e}")

        response = await call_next(request)
        return response


# Add UTF-8 middleware (runs before request processing)
app.add_middleware(UTF8EncodingMiddleware)


# ============================================================
# EXCEPTION HANDLERS
# ============================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "ValidationError",
            "message": "Request validation failed",
            "detail": str(exc.errors())
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "detail": str(exc) if settings.DEBUG else None
        }
    )


# ============================================================
# MIDDLEWARE - Request Logging
# ============================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # Add request ID to request state
    request.state.request_id = request_id
    
    logger.info(f"[{request_id}] {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000
    
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} "
        f"→ {response.status_code} ({duration_ms:.1f}ms)"
    )
    
    return response


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": settings.APP_DESCRIPTION,
        "docs": "/docs",
        "health": "/api/v1/health",
        "metrics": "/metrics", 
        "endpoints": {
            "query": "POST /api/v1/query",
            "chat": "POST /api/v1/chat"
        }
    }

@app.get("/metrics", tags=["Observability"])
async def metrics():
    """
    Prometheus metrics endpoint
    
    Returns metrics in Prometheus text format for scraping.
    """
    return FastAPIResponse(
        content=get_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )

@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health_check(request: Request):
    """
    Health check endpoint
    Returns service status and uptime
    """
    uptime = time.time() - request.app.state.startup_time if hasattr(request.app.state, 'startup_time') else None
    
    # Check if retrieval system is initialized
    try:
        vector_engine = retrieval_system.get_vector_engine()
        graph_provider = retrieval_system.get_graph_provider()
        unified_retrieval = request.app.state.unified_retrieval if hasattr(request.app.state, 'unified_retrieval') else None
        retrieval_status = "healthy"
        vector_status = "initialized"
        graph_status = "initialized"
        hybrid_status = "initialized" if unified_retrieval else "not_initialized"
    except Exception:
        retrieval_status = "not_initialized"
        vector_status = "unknown"
        graph_status = "unknown"
        hybrid_status = "unknown"
    
    # Check cache health if available
    cache_health = None
    cache_metrics = None
    try:
        if hasattr(request.app.state, 'cache_integration'):
            cache_health = request.app.state.cache_integration.get_cache_health()
            cache_metrics = request.app.state.cache_integration.get_cache_metrics()
    except Exception as e:
        logger.warning(f"Failed to get cache health: {e}")
    
    return HealthResponse(
        status="healthy" if retrieval_status == "healthy" else "degraded",
        version=settings.APP_VERSION,
        services={
            "retrieval_system": retrieval_status,
            "vector_search": vector_status,
            "graph_context": graph_status,
            "hybrid_retrieval": hybrid_status,
            "cache_system": cache_health.get('overall_status', 'unknown') if cache_health else 'disabled'
        },
        uptime_seconds=uptime,
        cache_metrics=cache_metrics
    )

@app.post("/api/v1/query", response_model=QueryResponse, tags=["Query"])
async def process_query(
    request: Request,
    query_request: QueryRequest,
    vector_engine: VectorSearchEngine = Depends(get_vector_engine),
    graph_provider: GraphContextProvider = Depends(get_graph_provider)
):
    """
    Main query endpoint - Returns retrieval results (no LLM)
    
    Processes user query through RAG system and returns structured retrieval results.
    
    **Flow:**
    1. Extract entities from query using spaCy NER
    2. Search vector database for similar documents
    3. Optionally enhance with graph context
    4. Apply RBAC filtering based on user role
    5. Return ranked results with scores and provenance
    
    **Returns:** JSON retrieval results (documents + metadata)
    
    **Note:** For natural language responses, use /api/v1/chat endpoint
    """
    
    request_id = request.state.request_id
    start_time = time.time()
    
    logger.info(f"[{request_id}] Processing query: '{query_request.query[:50]}...'")
    logger.info(f"[{request_id}] User: {query_request.user_id}, Role: {query_request.user_role}")
    
    try:
        # Use unified hybrid retrieval system
        unified_retrieval = request.app.state.unified_retrieval
        
        # Determine user's allowed scopes based on role
        allowed_scopes = _get_allowed_scopes(query_request.user_role)
        
        # Build user context for RBAC
        resolved_company_id = _resolve_company_id(query_request.company_id, query_request.user_role)
        user_context = {
            "user_id": query_request.user_id,
            "role": query_request.user_role,
            "allowed_scopes": allowed_scopes,
            "company_id": resolved_company_id
        }
        
        # Process query through unified retrieval
        logger.info(f"[{request_id}] Using unified hybrid retrieval system...")
        results = unified_retrieval.retrieve(
            query=query_request.query,
            executive_id=query_request.user_id,  # Fixed: use user_id (has alias executive_id)
            user_context=user_context,
            top_k=query_request.top_k
        )
        
        # Calculate performance
        total_time_ms = (time.time() - start_time) * 1000
        
        # Build metadata
        metadata = RetrievalMetadata(
            total_results=len(results),
            results_returned=len(results),
            query_length=len(query_request.query),
            filters_applied={
                "role": query_request.user_role,
                "scopes": allowed_scopes,
                "min_score": query_request.min_score
            },
            performance_ms=total_time_ms,
            sources_used=["hybrid_retrieval"]
        )
        
        logger.info(
            f"[{request_id}] ✅ Retrieved {len(results)} results "
            f"in {total_time_ms:.1f}ms"
        )
        
        return QueryResponse(
            success=True,
            results=results,
            metadata=metadata,
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] ❌ Query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )

@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Chat"])
async def process_chat(
    request: Request,
    chat_request: ChatRequest
):
    """
    Chat endpoint with full RAG + LLM pipeline

    **NEW Features (Updated):**
    - ✅ Automatic query routing (fast/standard/agentic paths)
    - ✅ Document summarization (prevents 413 errors)
    - ✅ ReAct reasoning for complex queries
    - ✅ Profile-based personality responses
    - ✅ Adaptive reranking
    - ✅ Session memory
    - ✅ Citations and source tracking

    **Flow:**
    1. Route query → Selects path (fast/standard/agentic)
    2. Vector search → Retrieves relevant documents
    3. Graph context → Enhances with knowledge graph (if available)
    4. Memory search → Adds conversation history
    5. Adaptive reranking → Quality-based reranking strategy
    6. Document summarization → Compresses context for agentic path
    7. LLM generation → Creates personalized response
    8. Store in memory → For future context

    **Paths:**
    - **Fast** (<2s): Simple factual queries - "What is...", "Who is..."
    - **Standard** (<3s): Decision queries - "Should we...", "How to..."
    - **Agentic** (<5s): Complex analysis - "Compare...", "Analyze trade-offs..."
    """

    request_id = request.state.request_id
    start_time = time.time()

    logger.info(f"[{request_id}] Chat query: '{chat_request.query[:50]}...'")
    
    # === PROFILE ID NORMALIZATION ===
    # Normalize profile IDs to database format
    original_profile_id = chat_request.profile_id
    normalized_profile_id = normalize_profile_id(chat_request.profile_id)

    if not normalized_profile_id:
        logger.error(f"[{request_id}] Invalid profile_id: {original_profile_id}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid profile_id: {original_profile_id}. "
                   f"Valid IDs: sample_profile"
        )
    
    if original_profile_id != normalized_profile_id:
        logger.info(
            f"[{request_id}] Normalized profile_id: "
            f"{original_profile_id} → {normalized_profile_id}"
        )
    
    # Update request with normalized ID
    chat_request.profile_id = normalized_profile_id
    logger.info(f"[{request_id}] Using profile: {normalized_profile_id}")

    try:
        # === STEP 1: Query Routing ===
        route_start = time.time()
        route_decision = request.app.state.query_router.route(
            query=chat_request.query
        )
        routing_time = (time.time() - route_start) * 1000

        logger.info(
            f"[{request_id}] Routed to {route_decision.path} path "
            f"(confidence: {route_decision.confidence:.2%})"
        )

        # === STEP 2: Vector Search ===
        vector_start = time.time()
        vector_engine = request.app.state.vector_engine
        resolved_company_id = _resolve_company_id(chat_request.company_id, chat_request.user_role)
        vector_results = vector_engine.search(
            query=chat_request.query,
            top_k=chat_request.top_k,
            role=chat_request.user_role,
            company_id=resolved_company_id
        )
        vector_time = (time.time() - vector_start) * 1000

        # === STEP 3: Graph Context (if available) ===
        graph_start = time.time()
        graph_context = {}
        try:
            graph_provider = request.app.state.graph_provider
            graph_context = graph_provider.discover_context(
                query=chat_request.query,
                allowed_scopes=_get_allowed_scopes(chat_request.user_role),
                company_id=resolved_company_id,
            )
        except Exception as e:
            logger.warning(f"[{request_id}] Graph context unavailable: {e}")
        graph_time = (time.time() - graph_start) * 1000

        # === STEP 4: Memory Search (session context) ===
        memory_start = time.time()
        memory_docs = []
        session_id = chat_request.session_id

        # Get or create session
        if not session_id:
            session_id = await request.app.state.session_manager.get_or_create_session(
                user_id=chat_request.user_id,
                executive_id=chat_request.profile_id
            )

        # TODO: Retrieve session history if needed
        # For now, session context is managed by session_manager
        memory_time = (time.time() - memory_start) * 1000

        # === STEP 5: LLM Generation with Orchestrator ===
        llm_start = time.time()

        # Use orchestrator (handles summarization, reranking, profiling automatically!)
        response = request.app.state.llm_orchestrator.generate(
            query=chat_request.query,
            vector_results=vector_results.get('results', []),
            profile_id=chat_request.profile_id or "exec_001_test",
            graph_results=[] if not graph_context else [graph_context],
            memory=memory_docs,
            force_path=chat_request.force_path or route_decision.path
        )

        llm_time = (time.time() - llm_start) * 1000
        total_time = (time.time() - start_time) * 1000
        
        #Capture LangSmith run_id (CRITICAL FIX #2)
        langsmith_run_id = None
        try:
            # Check if LangSmith is enabled
            import os
            if os.getenv('LANGCHAIN_TRACING_V2', 'false').lower() == 'true':
                from langsmith import get_current_run_tree
                run_tree = get_current_run_tree()
                langsmith_run_id = str(run_tree.id) if run_tree else None
                
                # Also try to get from LLM response metadata
                if not langsmith_run_id:
                    langsmith_run_id = response.get('metadata', {}).get('langsmith_run_id')
                
                if langsmith_run_id:
                    logger.info(f"[{request_id}] ✅ Captured LangSmith run_id: {langsmith_run_id}")
        except Exception as e:
            logger.debug(f"[{request_id}] Could not capture LangSmith run_id: {e}")

        # === STEP 6: Format Response ===
        # Extract citations
        api_citations = []
        for citation in response.get('citations', []):
            api_citations.append(Citation(
                source=citation.get('source', ''),
                raw_text=citation.get('raw_text', ''),
                position=citation.get('position', 0),
                context=citation.get('context', '')
            ))

        # Build metadata
        metadata = ChatMetadata(
            total_latency_ms=total_time,
            llm_latency_ms=llm_time,
            retrieval_latency_ms=vector_time + graph_time + memory_time,
            path=response.get('path', route_decision.path),
            routing_confidence=route_decision.confidence,
            routing_reasoning=route_decision.reasoning,
            llm_model=response.get('metadata', {}).get('llm_model', 'openai/gpt-oss-120b'),
            llm_provider="groq",
            llm_tokens=response.get('metadata', {}).get('llm_tokens', {}),
            profile_id=chat_request.profile_id,
            results_used=len(vector_results.get('results', [])),
            citation_count=len(api_citations),
            unique_sources=len(set(c.source for c in api_citations))
        )

        # ADD NEW FIELDS: Summarization stats
        if 'summarization_stats' in response.get('metadata', {}):
            metadata.summarization_stats = response['metadata']['summarization_stats']

        # ADD NEW FIELDS: ReAct metadata (for agentic path)
        if 'react_steps' in response.get('metadata', {}):
            metadata.react_steps = response['metadata']['react_steps']

        # ADD NEW FIELDS: Reranking strategy
        if 'reranking_strategy' in response.get('metadata', {}):
            metadata.reranking_strategy = response['metadata']['reranking_strategy']

        # ADD NEW FIELDS: Context quality
        if 'context_quality' in response.get('metadata', {}):
            metadata.context_quality = response['metadata']['context_quality']

        # ADD NEW FIELDS: Trace ID
        metadata.trace_id = request_id
        
        # Add LangSmith run_id (CRITICAL FIX #2)
        metadata.langsmith_run_id = langsmith_run_id

        logger.info(
            f"[{request_id}] ✅ Chat completed in {total_time:.0f}ms "
            f"(routing: {routing_time:.0f}ms, retrieval: {vector_time:.0f}ms, "
            f"LLM: {llm_time:.0f}ms)"
        )

        # === STEP 7: Store in Session Memory ===
        try:
            await request.app.state.session_manager.store_conversation_turn(
                session_id=session_id,
                query=chat_request.query,
                response=response.get('answer', ''),
                sources_used=response.get('sources', []),
                reasoning_trace=response.get('reasoning_trace'),
                importance_score=0.5,
                embedding=None
            )
            logger.debug(f"[{request_id}] Stored conversation turn in session {session_id}")
        except Exception as e:
            logger.error(f"[{request_id}] Failed to store conversation turn: {e}")
            # Continue without failing

        return ChatResponse(
            success=True,
            answer=response.get('answer', ''),
            citations=api_citations,
            sources=response.get('sources', []),
            metadata=metadata,
            session_id=session_id,
            request_id=request_id
        )

    except Exception as e:
        logger.error(f"[{request_id}] ❌ Chat processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}"
        )


@app.post("/api/v1/chat/stream", tags=["Chat"])
async def process_chat_stream(
    request: Request,
    chat_request: ChatRequest,
    vector_engine: VectorSearchEngine = Depends(get_vector_engine),
    graph_provider: GraphContextProvider = Depends(get_graph_provider)
):
    """
    Streaming chat endpoint with real-time LLM token streaming

    Returns Server-Sent Events (SSE) stream for real-time response generation.
    Same functionality as /api/v1/chat but streams tokens as they're generated by the LLM.

    **Stream format (newline-delimited JSON):**
    - `{"type": "token", "content": "..."}` - LLM token chunk
    - `{"type": "citations", "citations": [...]}` - Citations array
    - `{"type": "complete", "metadata": {...}}` - Final metadata
    - `[DONE]` - Stream end marker

    **Benefits:**
    - First token in ~500ms (vs 3-60s wait for complete response)
    - Real-time user feedback
    - ChatGPT-like streaming experience

    **Usage:**
    ```javascript
    const response = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query: "What is...", ...})
    });

    const reader = response.body.getReader();
    while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        // Process chunks...
    }
    ```
    """
    request_id = request.state.request_id
    start_time = time.time()

    logger.info(f"[{request_id}] Streaming chat query: '{chat_request.query[:50]}...'")

    async def generate_stream():
        """Generator function for streaming response"""
        try:
            # Step 1: Extract entities
            logger.info(f"[{request_id}] Extracting entities...")
            entities = graph_provider.entity_extractor.extract(chat_request.query)
            entity_names = [e['text'] for e in entities]

            query_analysis = {
                'entities': entities,
                'entity_count': len(entities),
                'query_type': 'unknown',
                'complexity': 'medium'
            }

            logger.info(f"[{request_id}] Found entities: {entity_names}")

            # Step 2 & 3: Parallel retrieval (Vector + Graph)
            retrieval_start = time.time()
            logger.info(f"[{request_id}] Starting parallel retrieval (vector + graph)...")

            # Define async wrappers for blocking operations
            resolved_company_id = _resolve_company_id(chat_request.company_id, chat_request.user_role)

            async def run_vector_search():
                """Run vector search in thread pool"""
                return await asyncio.to_thread(
                    vector_engine.search,
                    query=chat_request.query,
                    top_k=chat_request.top_k,
                    min_score=chat_request.min_score,
                    role=chat_request.user_role,
                    company_id=resolved_company_id
                )

            async def run_graph_context():
                """Run graph context retrieval in thread pool"""
                if not entity_names or len(entity_names) == 0:
                    return None

                try:
                    # Use discover_context (the actual method name)
                    graph_context = await asyncio.to_thread(
                        graph_provider.discover_context,
                        query=chat_request.query,
                        entities=entities,  # Pass full entity dicts
                        max_candidates=20,
                        allowed_scopes=_get_allowed_scopes(chat_request.user_role),
                        company_id=resolved_company_id,
                    )

                    if graph_context and graph_context.get('has_context'):
                        return [graph_context]
                    return None
                except Exception as e:
                    logger.warning(f"[{request_id}] Graph retrieval failed: {e}")
                    return None

            # Run both retrievals in parallel
            search_response, graph_results = await asyncio.gather(
                run_vector_search(),
                run_graph_context()
            )

            vector_results = search_response.get('results', [])
            retrieval_time = (time.time() - retrieval_start) * 1000

            logger.info(
                f"[{request_id}] Parallel retrieval complete in {retrieval_time:.1f}ms: "
                f"{len(vector_results)} vector results, "
                f"{'graph context found' if graph_results else 'no graph context'}"
            )

            # Step 4: Optional precedents/memory
            precedents = None
            memory = None

            # Step 5: Stream LLM response
            logger.info(f"[{request_id}] Starting LLM streaming...")
            llm_start = time.time()

            # Use base orchestrator for streaming (cache wrapper doesn't support streaming)
            orchestrator = request.app.state.base_llm_orchestrator

            # Stream tokens as they arrive
            async for chunk in orchestrator.generate_stream(
                query=chat_request.query,
                vector_results=vector_results,
                profile_id=chat_request.profile_id,
                graph_results=graph_results,
                precedents=precedents,
                memory=memory,
                force_path=chat_request.force_path,
                query_analysis=query_analysis
            ):
                # Yield SSE format
                yield f"data: {json.dumps(chunk)}\n\n"

            # Stream complete
            llm_time = (time.time() - llm_start) * 1000
            total_time = (time.time() - start_time) * 1000

            logger.info(
                f"[{request_id}] ✅ Streaming complete in {total_time:.1f}ms "
                f"(retrieval: {retrieval_time:.1f}ms, LLM: {llm_time:.1f}ms)"
            )

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"[{request_id}] ❌ Streaming failed: {e}", exc_info=True)
            error_chunk = {
                'type': 'error',
                'message': f"Streaming failed: {str(e)}"
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Connection": "keep-alive",
        }
    )


# ============================================================
# SESSION INTERRUPT ENDPOINT
# ============================================================

@app.post("/api/v1/interrupt", response_model=InterruptResponse, tags=["Session"])
async def interrupt_session(
    request: Request,
    interrupt_request: InterruptRequest
):
    """
    Interrupt an active streaming session.

    **Use cases:**
    - User wants to stop current response generation
    - User wants to start a new query while one is running
    - User interrupts with voice/button

    **Actions:**
    1. Stop LLM text generation
    2. Stop TTS audio generation
    3. Clear all buffers (text + audio)
    4. Transition session to READY state

    **Response:**
    Returns new session state after interruption
    """
    session_id = interrupt_request.session_id
    logger.info(f"[{session_id}] 🛑 Interruption requested")

    # Get session manager
    if not hasattr(request.app.state, 'active_sessions'):
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )

    manager = request.app.state.active_sessions.get(session_id)
    if not manager:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )

    try:
        # Perform interruption
        await manager.interrupt()

        return InterruptResponse(
            success=True,
            session_id=session_id,
            state=manager.get_state().value,
            message="Session interrupted successfully and ready for new request"
        )

    except Exception as e:
        logger.error(f"[{session_id}] Interruption failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to interrupt session: {str(e)}"
        )


@app.get("/api/v1/profiles", tags=["Profiles"])
async def list_profiles(request: Request, company_id: Optional[str] = None, user_role: Optional[str] = None):
    """
    List all available executive profiles

    Returns profile IDs, names, roles, and expertise areas.
    Use these IDs in the `profile_id` field of chat requests.

    Includes both filesystem profiles and database profiles (from onboarding pipeline).

    Tenant isolation:
    - company_id provided → only profiles for that company
    - user_role=super_admin without company_id → all profiles (admin access)
    - No company_id and not super_admin → only filesystem profiles (no DB profiles)
    """
    is_super_admin = user_role and user_role.lower() == "super_admin"
    show_all_db_profiles = is_super_admin and not company_id

    try:
        profiles = []
        seen_ids = set()

        # 1. Get profiles from ProfileManager (filesystem)
        # Filesystem profiles don't have company association — only include when
        # no company_id filter is active (super_admin or anonymous/development)
        if not company_id:
            orchestrator = request.app.state.llm_orchestrator
            base_orchestrator = getattr(orchestrator, 'llm_orchestrator', orchestrator)
            all_profiles = base_orchestrator.profile_manager.get_all_profiles()

            for profile_id, profile_data in all_profiles.items():
                seen_ids.add(profile_id)
                profiles.append({
                    "id": profile_id,
                    "name": profile_data.get("name_english", profile_data.get("name", "Unknown")),
                    "title": profile_data.get("title", ""),
                    "department": profile_data.get("department", ""),
                    "expertise": profile_data.get("background", {}).get("expertise", []),
                    "communication_style": profile_data.get("communication_style", {}).get("overall_tone", ""),
                    "source": "filesystem"
                })


        # 2. Get profiles from database (onboarded executives)
        # Secure-by-default: require company_id unless super_admin
        db_pool = getattr(request.app.state, 'db_pool', None)
        logger.info(f"[list_profiles] db_pool available: {db_pool is not None}, company_id: {company_id}, is_super_admin: {is_super_admin}")
        if db_pool and (company_id or show_all_db_profiles):
            try:
                if company_id:
                    rows = await db_pool.fetch("""
                        SELECT ep.id, ep.name, ep.title, ep.department, ep.profile_data,
                               c.name as company_name, c.id as company_id
                        FROM executive_profiles ep
                        LEFT JOIN companies c ON ep.company_id = c.id
                        WHERE ep.profile_data IS NOT NULL
                          AND ep.company_id = $1
                    """, company_id)
                else:
                    # super_admin without company_id — return all
                    rows = await db_pool.fetch("""
                        SELECT ep.id, ep.name, ep.title, ep.department, ep.profile_data,
                               c.name as company_name, c.id as company_id
                        FROM executive_profiles ep
                        LEFT JOIN companies c ON ep.company_id = c.id
                        WHERE ep.profile_data IS NOT NULL
                    """)
                request.state._db_profiles_count = len(rows)
                request.state._db_profiles_added = 0
                logger.info(f"[list_profiles] Found {len(rows)} profiles in database")
                db_profile_ids = []
                for row in rows:
                    try:
                        profile_id = row["id"]
                        db_profile_ids.append(profile_id)
                        if profile_id not in seen_ids:
                            seen_ids.add(profile_id)
                            # With jsonb codec registered, profile_data is auto-decoded as dict
                            # Handle legacy double-encoded data (string) for backwards compatibility
                            profile_data = row.get("profile_data") or {}
                            if isinstance(profile_data, str):
                                try:
                                    profile_data = json.loads(profile_data)
                                    # Handle double-encoding
                                    if isinstance(profile_data, str):
                                        profile_data = json.loads(profile_data)
                                except (json.JSONDecodeError, TypeError):
                                    profile_data = {}

                            new_profile = {
                                "id": profile_id,
                                # Use name_english if available, fall back to row name or profile name
                                "name": profile_data.get("name_english") or row.get("name") or profile_data.get("name") or "Unknown",
                                "title": row.get("title") or profile_data.get("title", ""),
                                "department": row.get("department") or profile_data.get("department", ""),
                                "expertise": profile_data.get("background", {}).get("expertise", []),
                                "communication_style": profile_data.get("communication_style", {}).get("overall_tone", ""),
                                "company_id": row.get("company_id"),
                                "company_name": row.get("company_name"),
                                "source": "database"
                            }
                            profiles.append(new_profile)
                            request.state._db_profiles_added = getattr(request.state, '_db_profiles_added', 0) + 1
                    except Exception as row_err:
                        logger.error(f"[list_profiles] Error processing row {row.get('id', 'unknown')}: {row_err}")
                request.state._db_profile_ids = db_profile_ids
            except Exception as db_err:
                logger.error(f"[list_profiles] Failed to fetch profiles from database: {db_err}", exc_info=True)
        else:
            if not db_pool:
                logger.warning("[list_profiles] No db_pool available in app.state")
            else:
                logger.info("[list_profiles] Skipping DB profiles (no company_id and not super_admin)")

        # Debug info
        db_pool_status = "available" if getattr(request.app.state, 'db_pool', None) else "not_available"
        db_profiles_found = getattr(request.state, '_db_profiles_count', 0)
        db_profiles_added = getattr(request.state, '_db_profiles_added', 0)
        db_profile_ids = getattr(request.state, '_db_profile_ids', [])

        # Final count before return
        final_profile_count = len(profiles)
        profile_ids_in_list = [p["id"] for p in profiles]
        logger.info(f"[list_profiles] FINAL: {final_profile_count} profiles, ids: {profile_ids_in_list}")

        return {
            "success": True,
            "profiles": profiles,
            "count": final_profile_count,
            "debug": {
                "db_pool": db_pool_status,
                "seen_ids": list(seen_ids),
                "db_profiles_found": db_profiles_found,
                "db_profiles_added": db_profiles_added,
                "db_profile_ids": db_profile_ids,
                "final_profile_ids": profile_ids_in_list
            }
        }

    except Exception as e:
        logger.error(f"Failed to list profiles: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list profiles: {str(e)}"
        )

@app.get("/api/v1/profiles/{profile_id}", tags=["Profiles"])
async def get_profile(profile_id: str, request: Request, company_id: Optional[str] = None):
    """
    Get detailed information about a specific executive profile

    Returns complete profile data including communication style,
    decision-making framework, and example responses.
    """
    try:
        orchestrator = request.app.state.llm_orchestrator
        # Access the underlying orchestrator's profile_manager
        base_orchestrator = getattr(orchestrator, 'llm_orchestrator', orchestrator)
        profile = base_orchestrator.profile_manager.get_profile(profile_id)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile not found: {profile_id}"
            )
        
        # Return sanitized profile (remove internal fields)
        return {
            "success": True,
            "profile": {
                "id": profile.get("id"),
                "name": profile.get("name_english", profile.get("name")),
                "title": profile.get("title"),
                "department": profile.get("department"),
                "company": profile.get("company"),
                "background": profile.get("background"),
                "communication_style": profile.get("communication_style"),
                "decision_framework": profile.get("decision_framework"),
                "domain_expertise": profile.get("domain_expertise")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile {profile_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )


@app.post("/api/v1/profiles/refresh", tags=["Profiles"])
async def refresh_profiles(request: Request):
    """
    Refresh executive profiles from database.

    Call this endpoint after onboarding new executives to make them
    available for chat without restarting the API.

    This refreshes the in-memory profile cache by reloading from
    the PostgreSQL database.
    """
    try:
        orchestrator = request.app.state.llm_orchestrator
        base_orchestrator = getattr(orchestrator, 'llm_orchestrator', orchestrator)

        # Get count before refresh
        before_count = len(base_orchestrator.profile_manager.get_all_profiles())

        # Refresh database profiles
        base_orchestrator.profile_manager.refresh_database_profiles()

        # Get count after refresh
        after_count = len(base_orchestrator.profile_manager.get_all_profiles())
        profile_ids = list(base_orchestrator.profile_manager.get_all_profiles().keys())

        logger.info(f"Profiles refreshed: {before_count} -> {after_count}")

        return {
            "success": True,
            "message": "Profiles refreshed from database",
            "profiles_before": before_count,
            "profiles_after": after_count,
            "profile_ids": profile_ids
        }

    except Exception as e:
        logger.error(f"Failed to refresh profiles: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh profiles: {str(e)}"
        )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _get_allowed_scopes(user_role: str) -> list:
    """Delegate to shared RBAC module for role-to-scope mapping."""
    from shared.rbac import get_allowed_scopes
    return get_allowed_scopes(user_role)


_resolve_company_id = resolve_company_id  # Alias for local use


# ============================================================
# SESSION MANAGEMENT ENDPOINTS
# ============================================================

# Include all session endpoints
app.include_router(session_endpoints.router, prefix="/api/v1/sessions", tags=["Sessions"])

# ============================================================
# USER FEEDBACK ENDPOINTS
# ============================================================

# Include feedback endpoints
app.include_router(feedback_endpoints.router)

# ============================================================
# LANGGRAPH ENDPOINTS 
# ============================================================

# Include LangGraph endpoints
try:
    from api import langgraph_endpoints
    app.include_router(langgraph_endpoints.router)
    logger.info("✅ LangGraph endpoints registered: /api/v1/langgraph/*")
except ImportError as e:
    logger.warning(f"⚠️  LangGraph endpoints not available: {e}")

# ============================================================
# AUDIO STREAMING ENDPOINTS
# ============================================================

# Include audio endpoints (TTS streaming with Kokoro)
try:
    from api import audio_endpoints
    app.include_router(audio_endpoints.router, prefix="/api/v1", tags=["audio"])
    logger.info("✅ Audio streaming endpoints registered: /api/v1/chat/stream-audio, /api/v1/chat/audio-only")
except ImportError as e:
    logger.warning(f"⚠️  Audio endpoints not available (Kokoro TTS may not be installed): {e}")

# ============================================================
# STT (SPEECH-TO-TEXT) ENDPOINTS
# ============================================================

# Include STT endpoints (Faster Whisper - local, free)
try:
    from api import stt_endpoints
    app.include_router(stt_endpoints.router, prefix="/api/v1", tags=["stt"])
    logger.info("✅ STT endpoints registered: /api/v1/stt/transcribe, /api/v1/stt/stream")
except ImportError as e:
    logger.warning(f"⚠️  STT endpoints not available (Faster Whisper may not be installed): {e}")

# ============================================================
# MEETING SCHEDULER ENDPOINTS
# ============================================================

# Include meeting scheduling endpoints
try:
    from endpoints import meetings
    app.include_router(meetings.router, prefix="/api/v1", tags=["meetings"])
    logger.info("✅ Meeting scheduler endpoints registered: /api/v1/meetings")
except ImportError as e:
    logger.warning(f"⚠️  Meeting scheduler endpoints not available: {e}")

# ============================================================
# RUN SERVER (for development)
# ============================================================

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("  AI OFFICER API SERVER")
    print("=" * 60)
    print(f"  Host: {settings.HOST}")
    print(f"  Port: {settings.PORT}")
    print(f"  Debug: {settings.DEBUG}")
    print(f"  Platform: {sys.platform}")

    # On Windows, disable reload to preserve asyncio event loop policy
    # (reload spawns subprocess that doesn't inherit the policy)
    use_reload = settings.DEBUG
    if sys.platform == 'win32':
        use_reload = False
        print("  Reload: Disabled (Windows - required for async PostgreSQL)")
    else:
        print(f"  Reload: {use_reload}")

    print("=" * 60 + "\n")

    uvicorn.run(
        "api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=use_reload,
        log_level="info"
    )