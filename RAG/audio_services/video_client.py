
import asyncio
import json
import logging
import base64
import os
import time
import websockets
from typing import Optional, Dict
import numpy as np

logger = logging.getLogger(__name__)

class VideoServiceClient:
    """
    Client for the External Video Service (Avatar Audio Source).
    Handles sending audio data for avatar lip-sync.
    """

    def __init__(self, ws_url: str = None):
        # Update default URL to port 3000
        self.ws_url = ws_url or os.getenv("GCP_VIDEO_SERVICE_URL", "wss://example.invalid/audio")
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.session_id: Optional[str] = None
        self.last_used_time = time.time()

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is actually open"""
        from websockets.protocol import State
        return self.websocket is not None and self.websocket.state == State.OPEN

    async def connect(self, session_id: str):
        """
        Connect to the Audio Ingest Server.
        session_id is REQUIRED and must match the Frontend session_id.
        """
        if not session_id:
            raise ValueError("session_id is required for VideoService connection")

        self.session_id = session_id
        
        # New Endpoint is simple, no subpaths required by docs (ws://IP:3000)
        endpoint = self.ws_url
        
        try:
            logger.info(f"🔌 VideoService: Connecting to {endpoint} (session: {session_id})...")
            self.websocket = await websockets.connect(
                endpoint,
                open_timeout=5,
                close_timeout=5,
                ping_interval=5,
                ping_timeout=10
            )

            logger.info(f"✅ VideoService: Connected")
            
        except Exception as e:
            logger.error(f"❌ VideoService: Connection failed: {e}")
            raise

    async def send_audio(self, audio_data: bytes, sample_rate: int = 24000):
        """
        Send a chunk of audio to the avatar.
        Audio should be 16-bit PCM.
        """
        if not self.is_connected:
            logger.warning("⚠️ VideoService: Cannot send audio - not connected")
            return

        try:
            self.last_used_time = time.time()

            # Encode audio to base64
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')

            # New Protocol
            payload = {
                "type": "audio",
                "session_id": self.session_id,
                "data": audio_b64
            }

            await self.websocket.send(json.dumps(payload))
            # logger.debug(f"🔊 VideoService: Sent {len(audio_data)} bytes") 

        except websockets.exceptions.ConnectionClosed:
            logger.error("❌ VideoService: Connection closed unexpectedly")
        except Exception as e:
            logger.error(f"❌ VideoService: Failed to send audio: {e}")

    async def stop_speaking(self):
        """Signal end of speech (reset to idle)"""
        if not self.is_connected: 
            return

        self.last_used_time = time.time()
        
        try:
            msg = {
                "type": "stop_speaking",
                "session_id": self.session_id
            }
            await self.websocket.send(json.dumps(msg))
            logger.info("🛑 VideoService: Sent stop_speaking")
        except Exception as e:
            logger.error(f"VideoService: Failed to send stop_speaking: {e}")

    # --- Deprecated / No-op methods kept for interface compatibility ---
    
    async def start_speaking(self):
        # implicit in audio stream now
        pass

    async def send_json(self, data: Dict):
        # Internal use mainly
        if self.is_connected:
             await self.websocket.send(json.dumps(data))

    def is_stale(self, max_idle_seconds: int = 300) -> bool:
        return (time.time() - self.last_used_time) > max_idle_seconds

    async def disconnect(self):
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("VideoService: Disconnected")
            except Exception:
                pass
        self.websocket = None
