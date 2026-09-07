"""
STT Endpoints for AI Officer RAG API  

Provides speech-to-text transcription with:
- Batch file transcription
- Real-time audio streaming with VAD
- English and Japanese language support

Endpoints:
- POST /stt/transcribe: Batch transcribe audio file
- POST /stt/transcribe-stream: Real-time streaming transcription (WebSocket)
"""

import asyncio
import base64
import json
import logging
import time
from typing import AsyncIterator

from fastapi import APIRouter, UploadFile, File, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import numpy as np

from audio_services.stt_service import get_stt_service, STTServiceError
from audio_services.realtime_stt_service import get_realtime_stt

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post("/stt/transcribe", tags=["STT"])
async def transcribe_audio_file(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: str = Form("en", description="Language code: 'en' or 'ja'")
):
    """
    Batch transcribe audio file
    
    **Supported formats**: WAV, MP3, WebM, MP4, FLAC, OGG
    **Languages**: en (English), ja (Japanese)
    
    **Request:**
    - file: Audio file (multipart/form-data)
    - language: 'en' or 'ja' (default: 'en')
    
    **Response:**
    ```json
    {
        "success": true,
        "transcript": "Full transcription text",
        "language": "en",
        "language_probability": 0.95,
        "duration": 10.5,
        "segments": [
            {"start": 0.0, "end": 2.5, "text": "Hello"},
            {"start": 2.5, "end": 5.0, "text": "how are you"}
        ],
        "processing_time_ms": 450
    }
    ```
    
    **Usage (curl):**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/stt/transcribe" \\
        -F "file=@audio.wav" \\
        -F "language=en"
    ```
    
    **Usage (Python):**
    ```python
    with open('audio.wav', 'rb') as f:
        files = {'file': f}
        data = {'language': 'en'}
        response = requests.post(
            'http://localhost:8000/api/v1/stt/transcribe',
            files=files,
            data=data
        )
    result = response.json()
    print(result['transcript'])
    ```
    """
    start_time = time.time()
    
    try:
        logger.info(f"📝 Transcription request: file={file.filename}, language={language}")
        
        # Validate language
        if language not in ['en', 'ja']:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": f"Invalid language '{language}'. Supported: 'en', 'ja'"
                }
            )
        
        # Save uploaded file temporarily
        temp_path = f"/tmp/stt_{int(time.time())}_{file.filename}"
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"   Saved to: {temp_path} ({len(content)} bytes)")
        
        # Get STT service (singleton - model loaded once)
        stt_service = get_stt_service()
        
        # Transcribe
        result = await stt_service.transcribe_file(temp_path, language=language)
        
        processing_time = (time.time() - start_time) * 1000
        
        logger.info(f"✅ Transcription complete: {len(result['transcript'])} chars in {processing_time:.1f}ms")
        logger.info(f"   Transcript: {result['transcript'][:100]}...")
        
        # Clean up temp file
        import os
        try:
            os.remove(temp_path)
        except:
            pass
        
        return {
            "success": True,
            **result,
            "processing_time_ms": processing_time
        }
        
    except STTServiceError as e:
        logger.error(f"❌ STT service error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )
    except Exception as e:
        logger.error(f"❌ Transcription error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Transcription failed: {str(e)}"
            }
        )


@router.websocket("/stt/stream")
async def transcribe_stream(websocket: WebSocket):
    """
    Real-time audio streaming transcription with VAD
    
    **WebSocket Protocol:**
    
    Client sends:
    ```json
    {
        "type": "config",
        "language": "en"  // or "ja"
    }
    ```
    
    Then client streams audio chunks:
    ```json
    {
        "type": "audio",
        "data": "<base64_encoded_pcm>"  // int16, 16kHz, mono
    }
    ```
    
    Server responds with transcripts:
    ```json
    {
        "type": "transcript",
        "text": "Complete utterance",
        "language": "en",
        "timestamp": 1234567890.123
    }
    ```
    
    Or errors:
    ```json
    {
        "type": "error",
        "message": "Error description"
    }
    ```
    
    **Audio Format:**
    - Sample rate: 16000 Hz
    - Format: 16-bit PCM (int16)
    - Channels: Mono
    - Chunk duration: 100ms recommended
    - Encoding: Base64 for WebSocket transmission
    
    **Usage (JavaScript):**
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/stt/stream');
    
    // Configure language
    ws.onopen = () => {
        ws.send(JSON.stringify({
            type: 'config',
            language: 'en'
        }));
    };
    
    // Send audio chunks (100ms each)
    function sendAudioChunk(pcmData) {  // Int16Array
        const base64 = btoa(String.fromCharCode(...new Uint8Array(pcmData.buffer)));
        ws.send(JSON.stringify({
            type: 'audio',
            data: base64
        }));
    }
    
    // Receive transcripts
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'transcript') {
            console.log('Transcript:', data.text);
        }
    };
    ```
    """
    import uuid
    await websocket.accept()
    
    # Generate session ID for this interaction
    session_id = str(uuid.uuid4())
    logger.info(f"🎤 WebSocket STT stream connected. Session ID: {session_id}")
    
    # Send session ID to client
    await websocket.send_json({
        "type": "session_init",
        "session_id": session_id
    })
    
    language = "en"  # Default
    realtime_stt = get_realtime_stt()
    first_audio_logged = False  # ONE-TIME logging flag

    try:
        async def audio_stream_generator():
            """Generate audio chunks from WebSocket"""
            nonlocal first_audio_logged
            while True:
                try:
                    data = await websocket.receive_json()

                    if data.get("type") == "config":
                        # Configuration message
                        nonlocal language
                        language = data.get("language", "en")
                        logger.info(f"   Language configured: {language}")
                        await websocket.send_json({
                            "type": "config_ack",
                            "language": language
                        })
                        continue

                    elif data.get("type") == "audio":
                        # Audio chunk
                        audio_b64 = data.get("data")
                        audio_bytes = base64.b64decode(audio_b64)
                        audio_chunk = np.frombuffer(audio_bytes, dtype=np.int16)

                        # ONE-TIME: Log first audio message received
                        if not first_audio_logged:
                            logger.info(f"🔍 FIRST AUDIO MESSAGE RECEIVED:")
                            logger.info(f"   Base64 length: {len(audio_b64)}")
                            logger.info(f"   Decoded bytes: {len(audio_bytes)}")
                            logger.info(f"   Int16 samples: {len(audio_chunk)}")
                            logger.info(f"   Sample range: [{audio_chunk.min()}, {audio_chunk.max()}]")
                            logger.info(f"   First 10 samples: {audio_chunk[:10].tolist()}")
                            first_audio_logged = True

                        yield audio_chunk
                        
                except WebSocketDisconnect:
                    logger.info("   WebSocket disconnected")
                    break
                except Exception as e:
                    logger.error(f"   Error receiving audio: {e}")
                    break
        
        async def on_transcript(result):
            """Callback when utterance is transcribed"""
            try:
                await websocket.send_json({
                    "type": "transcript",
                    "text": result["transcript"],
                    "language": result["language"],
                    "timestamp": time.time()
                })
            except Exception as e:
                logger.error(f"   Error sending transcript: {e}")
        
        # Process audio stream with VAD
        # Use language getter to get current language dynamically
        await realtime_stt.process_audio_stream(
            audio_stream_generator(),
            on_transcript,
            language_getter=lambda: language  # Captures current language variable
        )
        
    except WebSocketDisconnect:
        logger.info("🎤 WebSocket STT stream disconnected")
    except Exception as e:
        logger.error(f"❌ STT stream error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
