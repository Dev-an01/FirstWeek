"""
Audio Streaming Endpoints for AI Officer RAG API

Provides text-to-speech (TTS) audio streaming with real-time generation using Kokoro TTS.
Supports multiple streaming modes for different use cases (chat, video sync, etc.).

Endpoints:
- POST /chat/stream-audio: Stream both text and audio (sentence-by-sentence)
- POST /chat/audio-only: Stream only audio (for video service integration)
"""

import asyncio
import base64
import json
import logging
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse

from api.models import ChatRequest
from api.dependencies import get_vector_engine, get_graph_provider, resolve_company_id
from shared.rbac import get_allowed_scopes as _get_allowed_scopes
from vector_search.search_engine import VectorSearchEngine
from graph_context.provider import GraphContextProvider

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post("/chat/stream-audio", tags=["Audio"])
async def process_chat_stream_audio(
    request: Request,
    chat_request: ChatRequest,
    vector_engine: VectorSearchEngine = Depends(get_vector_engine),
    graph_provider: GraphContextProvider = Depends(get_graph_provider)
):
    """
    Streaming chat endpoint with AUDIO + text streaming

    Returns Server-Sent Events (SSE) with both text tokens AND audio frames.
    Audio is generated sentence-by-sentence for real-time playback.

    **Stream format (newline-delimited JSON):**
    - `{"type": "text", "content": "..."}` - Text token
    - `{"type": "audio_frame", "data": "...", "index": N, "samples": 480}` - Audio PCM frame (base64)
    - `{"type": "audio_complete", "text": "...", "chars": N}` - Sentence audio complete
    - `{"type": "citations", "citations": [...]}` - Citations array
    - `{"type": "complete", "metadata": {...}}` - Final metadata
    - `[DONE]` - Stream end marker

    **Audio format:**
    - Sample rate: 24kHz
    - Format: 16-bit PCM (LINEAR16), mono
    - Frame size: 480 samples (20ms @ 24kHz)
    - Encoding: Base64 for JSON transmission

    **Usage:**
    ```javascript
    const response = await fetch('/api/v1/chat/stream-audio', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query: "What is...", ...})
    });

    const reader = response.body.getReader();
    while (true) {
        const {done, value} = await reader.read();
        if (done) break;

        // Parse SSE
        const chunk = JSON.parse(data);
        if (chunk.type === 'text') {
            displayText(chunk.content);
        } else if (chunk.type === 'audio_frame') {
            playAudioFrame(chunk.data); // Base64 PCM frame
        }
    }
    ```
    """
    request_id = request.state.request_id
    start_time = time.time()

    logger.info(f"[{request_id}] Streaming chat with audio: '{chat_request.query[:50]}...'")
    logger.info(f"[{request_id}] Request Payload: {chat_request.model_dump()}")

    # Initialize connection manager for this session
    from audio_services.connection_manager import ConnectionManager

    session_id = chat_request.session_id or request_id
    manager = ConnectionManager(session_id)
    await manager.connect()
    await manager.start_streaming()

    # Store in app state for interruption access
    request.app.state.active_sessions[session_id] = manager

    async def generate_stream_with_audio():
        try:
            # Get singleton TTS manager (with GPU semaphore)
            from audio_services.tts_manager import get_tts_manager
            tts_manager = await get_tts_manager()

            # Video Service Client (for backend-driven lip-sync)
            video_client = None
            if chat_request.enable_video_push:
                try:
                    from audio_services.video_client import VideoServiceClient
                    # Use 'anand_idle_v2' or map from chat_request.profile_id if needed
                    video_client = VideoServiceClient()
                    await video_client.connect(session_id=session_id)
                    logger.info(f"[{request_id}] 🎥 Connected to Video Service with session_id: {session_id}")
                    # await video_client.start_speaking() # Deprecated/Implicit
                except Exception as e:
                    logger.error(f"[{request_id}] ❌ Failed to connect to Video Service: {e}")
                    # Don't fail the whole request, just disable video push
                    video_client = None

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
            async def run_vector_search():
                """Run vector search in thread pool"""
                return await asyncio.to_thread(
                    vector_engine.search,
                    query=chat_request.query,
                    top_k=chat_request.top_k,
                    min_score=chat_request.min_score,
                    role=chat_request.user_role,
                    company_id=resolve_company_id(chat_request.company_id, chat_request.user_role)
                )

            async def run_graph_context():
                """Run graph context retrieval in thread pool"""
                if not entity_names or len(entity_names) == 0:
                    return None

                try:
                    graph_context = await asyncio.to_thread(
                        graph_provider.discover_context,
                        query=chat_request.query,
                        entities=entities,
                        max_candidates=20,
                        allowed_scopes=_get_allowed_scopes(chat_request.user_role),
                        company_id=resolve_company_id(chat_request.company_id, chat_request.user_role),
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

            # Step 5: Stream LLM response with audio
            logger.info(f"[{request_id}] Starting LLM + audio streaming...")
            llm_start = time.time()

            # Use base orchestrator (not cache-wrapped) for streaming support
            orchestrator = request.app.state.base_llm_orchestrator

            # Create text token stream
            text_stream = orchestrator.generate_stream(
                query=chat_request.query,
                vector_results=vector_results,
                profile_id=chat_request.profile_id,
                graph_results=graph_results,
                precedents=precedents,
                memory=memory,
                force_path=chat_request.force_path,
                query_analysis=query_analysis
                # Note: language param is for TTS, not LLM generation
            )

            # HYBRID SENTENCE-BY-SENTENCE STREAMING ARCHITECTURE
            from audio_services.streaming_utils import (
                has_complete_sentence,
                extract_first_sentence,
                clean_text_for_tts
            )
            from audio_services.audio_queue import AudioQueue

            streaming_mode = chat_request.streaming_mode
            logger.info(f"[{request_id}] Audio streaming mode: {streaming_mode}")

            full_response_text = ""  # Accumulate complete response
            sentence_buffer = ""  # Buffer for accumulating sentence
            frame_index = 0  # Global frame counter
            sentence_id = 0  # Sentence counter for ordering
            audio_metrics = {'text_chunks': 0, 'frames_generated': 0, 'audio_segments': 0}

            # Initialize AudioQueue for buffered mode
            audio_queue = None
            if streaming_mode == "buffered":
                audio_queue = AudioQueue()
                logger.info(f"[{request_id}] AudioQueue initialized for buffered mode")

            # Step 1: Stream text tokens + Generate audio sentence-by-sentence
            async for chunk in text_stream:
                # Check for interruption
                if manager.is_interrupted():
                    logger.warning(f"[{request_id}] Audio stream interrupted by user")
                    yield f"data: {json.dumps({'type': 'interrupted', 'message': 'Stream interrupted'})}\n\n"
                    break

                chunk_type = chunk.get('type')

                if chunk_type == 'token':
                    content = chunk.get('content', '')
                    audio_metrics['text_chunks'] += 1
                    full_response_text += content
                    sentence_buffer += content
                    await manager.add_text_token(content)

                    # Forward text immediately (FAST!)
                    yield f"data: {json.dumps(chunk)}\n\n"
                    
                    # Check if we have a complete sentence
                    while has_complete_sentence(sentence_buffer):
                        # Extract first complete sentence
                        sentence, sentence_buffer = extract_first_sentence(sentence_buffer)

                        if sentence.strip():
                            clean_sentence = clean_text_for_tts(sentence)
                            sentence_id += 1

                            logger.info(
                                f"[{request_id}] 🎵 Sentence {sentence_id}: '{clean_sentence[:50]}...' "
                                f"({len(clean_sentence)} chars) - starting TTS"
                            )

                            # Generate and stream audio for this sentence
                            try:
                                sentence_frame_count = 0
                                async for audio_frame in tts_manager.synthesize_with_gpu_lock(
                                    clean_sentence,
                                    voice_config={'language': chat_request.language, 'executive_id': chat_request.voice_profile_id or chat_request.profile_id},
                                    is_last_sentence=False
                                ):
                                    if manager.is_interrupted():
                                        break
                                    
                                    # [CHANGED] Video Service Integration:
                                    # If enabled (enable_video_push=True), we push the generated audio frame
                                    # directly to the external Video Service via WebSocket.
                                    # This is fire-and-forget logic to avoid blocking the main stream response.
                                    if video_client:
                                        await video_client.send_audio(audio_frame)

                                    # [CHANGED] Streaming Mode Handling:
                                    # - "buffered": Use AudioQueue to buffer 2s chunks (restored logic).
                                    # - "immediate" (default): Stream frames instantly to client (for chatbot).
                                    if streaming_mode == "buffered":
                                        # Buffered mode: Use AudioQueue with 2-sec blocking
                                        await audio_queue.push_frame(audio_frame)

                                        # Check if we have a complete 2-second block
                                        if await audio_queue.has_complete_block():
                                            block = await audio_queue.get_block()

                                            # Send all frames in block
                                            for frame_bytes in block.frames:
                                                audio_b64 = base64.b64encode(frame_bytes).decode('ascii')
                                                frame_msg = {
                                                    'type': 'audio_frame',
                                                    'data': audio_b64,
                                                    'index': frame_index,
                                                    'block_id': audio_queue.blocks_created,
                                                    'sentence_id': sentence_id
                                                }
                                                yield f"data: {json.dumps(frame_msg)}\n\n"
                                                await manager.add_audio_frame(frame_bytes)
                                                frame_index += 1
                                                audio_metrics['frames_generated'] += 1
                                    else:
                                        # Immediate mode logic
                                        audio_b64 = base64.b64encode(audio_frame).decode('ascii')
                                        frame_msg = {
                                            'type': 'audio_frame',
                                            'data': audio_b64,
                                            'index': frame_index,
                                            'sentence_id': sentence_id
                                        }
                                        yield f"data: {json.dumps(frame_msg)}\n\n"
                                        await manager.add_audio_frame(audio_frame)
                                        frame_index += 1
                                        audio_metrics['frames_generated'] += 1

                                    sentence_frame_count += 1
                                
                                audio_metrics['audio_segments'] = audio_metrics.get('audio_segments', 0) + 1
                                logger.info(
                                    f"[{request_id}] ✅ Sentence {sentence_id} audio complete: "
                                    f"{sentence_frame_count} frames ({sentence_frame_count * 20}ms)"
                                )
                            except Exception as e:
                                logger.error(f"[{request_id}] Audio generation failed for sentence {sentence_id}: {e}", exc_info=True)
                                yield f"data: {json.dumps({'type': 'audio_error', 'message': str(e), 'sentence_id': sentence_id})}\n\n"

                elif chunk_type in ['citations', 'metadata']:
                    yield f"data: {json.dumps(chunk)}\n\n"

                elif chunk_type == 'complete':
                    # Text streaming complete
                    yield f"data: {json.dumps(chunk)}\n\n"
                    break

            # Step 2: Process any remaining text in sentence buffer
            if sentence_buffer.strip() and not manager.is_interrupted():
                clean_sentence = clean_text_for_tts(sentence_buffer)
                sentence_id += 1

                logger.info(f"[{request_id}] 🎵 Final sentence: '{clean_sentence[:50]}...'")

                try:
                    async for audio_frame in tts_manager.synthesize_with_gpu_lock(
                        clean_sentence,
                        voice_config={'language': chat_request.language, 'executive_id': chat_request.voice_profile_id or chat_request.profile_id},
                        is_last_sentence=True
                    ):
                        if manager.is_interrupted():
                            break

                        # PUSH TO VIDEO SERVICE
                        if video_client:
                            await video_client.send_audio(audio_frame)

                        # ... yield logic ...
                        # Immediate mode logic
                        audio_b64 = base64.b64encode(audio_frame).decode('ascii')
                        frame_msg = {
                            'type': 'audio_frame',
                            'data': audio_b64,
                            'index': frame_index,
                            'sentence_id': sentence_id
                        }
                        yield f"data: {json.dumps(frame_msg)}\n\n"
                        await manager.add_audio_frame(audio_frame)
                        frame_index += 1
                        audio_metrics['frames_generated'] += 1

                except Exception as e:
                   # ...
                   pass

            # ... flushing ...
            
            # Stop speaking on video service
            if video_client:
                await video_client.stop_speaking()

            # ... completion logic ...

            yield "data: [DONE]\n\n"

        except asyncio.CancelledError:
            logger.warning(f"[{request_id}] Audio stream cancelled")
            await manager.clear_buffers()
            yield f"data: {json.dumps({'type': 'cancelled', 'message': 'Audio stream cancelled'})}\n\n"
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Audio streaming failed: {e}", exc_info=True)
            await manager.handle_error(e)
            error_chunk = {
                'type': 'error',
                'message': f"Streaming failed: {str(e)}"
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
        finally:
            # Cleanup Video Client
            if 'video_client' in locals() and video_client:
                logger.info(f"[{request_id}] Disconnecting Video Service")
                await video_client.disconnect()

            # Cleanup: remove from active sessions
            if session_id in request.app.state.active_sessions:
                del request.app.state.active_sessions[session_id]
            await manager.disconnect()

    return StreamingResponse(
        generate_stream_with_audio(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Connection": "keep-alive",
        }
    )


@router.post("/chat/audio-only", tags=["Audio"])
async def process_chat_audio_only(
    request: Request,
    chat_request: ChatRequest,
    vector_engine: VectorSearchEngine = Depends(get_vector_engine),
    graph_provider: GraphContextProvider = Depends(get_graph_provider)
):
    """
    Audio-only streaming endpoint for video service integration

    Generates AI response internally, but streams ONLY audio frames (no text tokens).
    Text generation happens in the background to feed TTS, but is not sent to client.

    **Use case**: Video service needs audio frames only to sync with video generation.

    **Stream format (newline-delimited JSON):**
    - `{"type": "audio_frame", "data": "...", "index": N}` - Audio PCM frame (base64)
    - `{"type": "complete", "metadata": {...}, "full_text": "..."}` - Final metadata with complete text
    - `[DONE]` - Stream end marker

    **Audio format:**
    - Sample rate: 24kHz
    - Format: 16-bit PCM (LINEAR16), mono
    - Frame size: 480 samples (20ms @ 24kHz)
    - Encoding: Base64 for JSON transmission
    - TTS Engine: Kokoro TTS (af_bella voice)

    **Differences from /chat/stream-audio:**
    - NO text tokens streamed (silent text generation)
    - NO citations streamed during response
    - Full text included in final metadata only
    - Optimized for video service (audio-first)

    **Usage:**
    ```javascript
    const response = await fetch('/api/v1/chat/audio-only', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query: "What is...", ...})
    });

    const reader = response.body.getReader();
    while (true) {
        const {done, value} = await reader.read();
        if (done) break;

        const chunk = JSON.parse(data);
        if (chunk.type === 'audio_frame') {
            sendToVideoService(chunk.data); // Base64 PCM frame
        } else if (chunk.type === 'complete') {
            console.log('Audio complete:', chunk.metadata);
        }
    }
    ```
    """
    request_id = request.state.request_id
    start_time = time.time()

    logger.info(f"[{request_id}] Audio-only streaming: '{chat_request.query[:50]}...'")

    # Initialize connection manager for this session
    from audio_services.connection_manager import ConnectionManager

    session_id = chat_request.session_id or request_id
    manager = ConnectionManager(session_id)
    await manager.connect()
    await manager.start_streaming()

    # Store in app state for interruption access
    request.app.state.active_sessions[session_id] = manager

    async def generate_audio_only_stream():
        """Generator function for streaming ONLY audio (no text)"""
        try:
            # Get singleton TTS manager (with GPU semaphore)
            from audio_services.tts_manager import get_tts_manager
            tts_manager = await get_tts_manager()

            # Metrics
            audio_metrics = {'frames_generated': 0, 'audio_duration_ms': 0}

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
            logger.info(f"[{request_id}] Starting parallel retrieval...")

            # Define async wrappers for blocking operations
            async def run_vector_search():
                return await asyncio.to_thread(
                    vector_engine.search,
                    query=chat_request.query,
                    top_k=chat_request.top_k,
                    min_score=chat_request.min_score,
                    role=chat_request.user_role,
                    company_id=resolve_company_id(chat_request.company_id, chat_request.user_role)
                )

            async def run_graph_context():
                if not entity_names or len(entity_names) == 0:
                    return None

                try:
                    graph_context = await asyncio.to_thread(
                        graph_provider.discover_context,
                        query=chat_request.query,
                        entities=entities,
                        max_candidates=20,
                        allowed_scopes=_get_allowed_scopes(chat_request.user_role),
                        company_id=resolve_company_id(chat_request.company_id, chat_request.user_role),
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
                f"[{request_id}] Retrieval complete in {retrieval_time:.1f}ms: "
                f"{len(vector_results)} vector results"
            )

            # Step 4: Optional precedents/memory
            precedents = None
            memory = None

            # Step 5: Generate complete text response (silently)
            logger.info(f"[{request_id}] Generating text response (silent)...")
            llm_start = time.time()

            # Use base orchestrator (not cache-wrapped) for streaming support
            orchestrator = request.app.state.base_llm_orchestrator

            # Create text token stream
            text_stream = orchestrator.generate_stream(
                query=chat_request.query,
                vector_results=vector_results,
                profile_id=chat_request.profile_id,
                graph_results=graph_results,
                precedents=precedents,
                memory=memory,
                force_path=chat_request.force_path,
                query_analysis=query_analysis
                # Note: language param is for TTS, not LLM generation
            )

            # Collect complete text response (DON'T stream to client)
            full_response_text = ""
            citations = []
            response_metadata = {}

            async for chunk in text_stream:
                # Check for interruption
                if manager.is_interrupted():
                    logger.warning(f"[{request_id}] Audio-only stream interrupted")
                    yield f"data: {json.dumps({'type': 'interrupted', 'message': 'Stream interrupted'})}\n\n"
                    break

                chunk_type = chunk.get('type')

                if chunk_type == 'token':
                    content = chunk.get('content', '')
                    full_response_text += content
                    # DON'T yield text tokens - silent generation

                elif chunk_type == 'citations':
                    citations = chunk.get('citations', [])

                elif chunk_type == 'complete':
                    response_metadata = chunk.get('metadata', {})
                    break

            text_generation_time = (time.time() - llm_start) * 1000
            logger.info(f"[{request_id}] Text complete ({len(full_response_text)} chars) in {text_generation_time:.1f}ms")

            # Step 6: Generate and stream audio frames (sentence-by-sentence)
            if full_response_text.strip() and not manager.is_interrupted():
                from audio_services.streaming_utils import extract_all_sentences, clean_text_for_tts
                from audio_services.audio_queue import AudioQueue

                streaming_mode = chat_request.streaming_mode
                logger.info(f"[{request_id}] Audio streaming mode: {streaming_mode}")

                # Initialize AudioQueue for buffered mode
                audio_queue = None
                if streaming_mode == "buffered":
                    audio_queue = AudioQueue()
                    logger.info(f"[{request_id}] AudioQueue initialized for buffered mode")

                try:
                    audio_start = time.time()
                    frame_idx = 0

                    # Extract all sentences from complete text
                    sentences = extract_all_sentences(full_response_text)
                    logger.info(f"[{request_id}] 🎵 Generating audio for {len(sentences)} sentences...")

                    # Generate audio sentence-by-sentence
                    for sentence_num, sentence in enumerate(sentences, 1):
                        if manager.is_interrupted():
                            logger.warning(f"[{request_id}] Audio generation interrupted")
                            break

                        clean_sentence = clean_text_for_tts(sentence)
                        is_last = (sentence_num == len(sentences))
                        logger.info(
                            f"[{request_id}] 🎵 Sentence {sentence_num}/{len(sentences)}: "
                            f"'{clean_sentence[:50]}...' ({len(clean_sentence)} chars){' [LAST]' if is_last else ''}"
                        )

                        # Stream audio frames for this sentence (using GPU semaphore)
                        sentence_frame_count = 0
                        async for audio_frame in tts_manager.synthesize_with_gpu_lock(
                            clean_sentence,
                            voice_config={'language': chat_request.language, 'executive_id': chat_request.voice_profile_id or chat_request.profile_id},
                            is_last_sentence=is_last
                        ):
                            if manager.is_interrupted():
                                break

                            if streaming_mode == "buffered":
                                # Buffered mode: Use AudioQueue with 2-sec blocking
                                await audio_queue.push_frame(audio_frame)

                                # Check if we have a complete 2-second block
                                if await audio_queue.has_complete_block():
                                    block = await audio_queue.get_block()

                                    # Send all frames in block
                                    for frame_bytes in block.frames:
                                        audio_b64 = base64.b64encode(frame_bytes).decode('ascii')
                                        frame_msg = {
                                            'type': 'audio_frame',
                                            'data': audio_b64,
                                            'index': frame_idx,
                                            'block_id': audio_queue.blocks_created,
                                            'sentence_id': sentence_num
                                        }
                                        yield f"data: {json.dumps(frame_msg)}\n\n"
                                        await manager.add_audio_frame(frame_bytes)
                                        frame_idx += 1
                                        audio_metrics['frames_generated'] += 1

                            else:
                                # Immediate/Sentence mode: Stream frames immediately
                                audio_b64 = base64.b64encode(audio_frame).decode('ascii')
                                frame_msg = {
                                    'type': 'audio_frame',
                                    'data': audio_b64,
                                    'index': frame_idx,
                                    'sentence_id': sentence_num
                                }
                                yield f"data: {json.dumps(frame_msg)}\n\n"
                                await manager.add_audio_frame(audio_frame)
                                frame_idx += 1
                                audio_metrics['frames_generated'] += 1

                            sentence_frame_count += 1

                        logger.info(
                            f"[{request_id}] ✅ Sentence {sentence_num} audio complete: "
                            f"{sentence_frame_count} frames ({sentence_frame_count * 20}ms)"
                        )

                    # Flush remaining buffered frames (for buffered mode)
                    if streaming_mode == "buffered" and audio_queue and not manager.is_interrupted():
                        remaining_frames = await audio_queue.get_all_frames()
                        logger.info(f"[{request_id}] Flushing {len(remaining_frames)} remaining frames from queue")

                        for frame_bytes in remaining_frames:
                            if manager.is_interrupted():
                                break

                            audio_b64 = base64.b64encode(frame_bytes).decode('ascii')
                            frame_msg = {
                                'type': 'audio_frame',
                                'data': audio_b64,
                                'index': frame_idx,
                                'is_final': True
                            }
                            yield f"data: {json.dumps(frame_msg)}\n\n"
                            await manager.add_audio_frame(frame_bytes)
                            frame_idx += 1
                            audio_metrics['frames_generated'] += 1

                    audio_generation_time = (time.time() - audio_start) * 1000
                    audio_metrics['audio_duration_ms'] = frame_idx * 20  # 20ms per frame

                    logger.info(
                        f"[{request_id}] 🎵 Audio complete: {frame_idx} frames "
                        f"({audio_metrics['audio_duration_ms']}ms audio) in {audio_generation_time:.1f}ms"
                    )

                except Exception as e:
                    logger.error(f"[{request_id}] Audio generation failed: {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'audio_error', 'message': str(e)})}\n\n"

            # Send final metadata with complete text
            await manager.end_streaming()

            total_time = (time.time() - start_time) * 1000

            complete_metadata = {
                'type': 'complete',
                'full_text': full_response_text,
                'citations': citations,
                'metadata': {
                    'total_latency_ms': total_time,
                    'retrieval_latency_ms': retrieval_time,
                    'text_generation_ms': text_generation_time,
                    'audio_generation_ms': audio_generation_time if 'audio_generation_time' in locals() else 0,
                    'audio_frames_sent': audio_metrics['frames_generated'],
                    'audio_duration_ms': audio_metrics['audio_duration_ms'],
                    'llm_model': response_metadata.get('model', 'unknown'),
                    'llm_provider': response_metadata.get('provider', 'unknown'),
                    'profile_id': chat_request.profile_id,
                    'path': response_metadata.get('path', 'unknown'),
                    'results_used': len(vector_results),
                    'citation_count': len(citations)
                }
            }

            yield f"data: {json.dumps(complete_metadata)}\n\n"

            logger.info(
                f"[{request_id}] ✅ Audio-only stream complete in {total_time:.1f}ms "
                f"({audio_metrics['frames_generated']} frames, {audio_metrics['audio_duration_ms']}ms audio)"
            )

            yield "data: [DONE]\n\n"

        except asyncio.CancelledError:
            logger.warning(f"[{request_id}] Audio-only stream cancelled")
            await manager.clear_buffers()
            yield f"data: {json.dumps({'type': 'cancelled', 'message': 'Stream cancelled'})}\n\n"
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Audio-only streaming failed: {e}", exc_info=True)
            await manager.handle_error(e)
            error_chunk = {
                'type': 'error',
                'message': f"Audio-only streaming failed: {str(e)}"
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
        finally:
            # Cleanup: remove from active sessions
            if session_id in request.app.state.active_sessions:
                del request.app.state.active_sessions[session_id]
            await manager.disconnect()

    return StreamingResponse(
        generate_audio_only_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Connection": "keep-alive",
        }
    )


@router.post("/voice/reload-keys/{executive_id}", tags=["Audio"])
async def reload_voice_keys(executive_id: str, request: Request):
    """Reload voice keys from DB into TTS LRU cache after key generation."""
    from audio_services.tts_manager import get_tts_manager

    try:
        tts_manager = await get_tts_manager()
        tts_service = tts_manager._tts_service
        if hasattr(tts_service, 'reload_executive_keys'):
            db_pool = request.app.state.db_pool
            await tts_service.reload_executive_keys(db_pool, executive_id)
            logger.info(f"Reloaded voice keys for {executive_id}")
        return {"success": True, "executive_id": executive_id}
    except Exception as e:
        logger.error(f"Failed to reload voice keys for {executive_id}: {e}")
        return {"success": False, "error": str(e)}
