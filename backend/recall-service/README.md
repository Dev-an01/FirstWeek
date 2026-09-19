# Recall Service

> Meeting bot management service for FirstWeek using Recall.ai

## Overview

The Recall Service manages Recall.ai bots that join video meetings (Google Meet, Zoom, Teams, Webex) and enables the FirstWeek to participate in conversations using RAG + LLM responses.

## Architecture

```
Meeting → Recall.ai Bot → Your STT Service → RAG API → TTS → Avatar Interface → Recall.ai → Meeting
```

## Features

- ✅ Create and manage Recall.ai bots
- ✅ Join meetings across multiple platforms
- ✅ Integrate with existing RAG pipeline
- ✅ Process meeting audio via STT (your implementation)
- ✅ Stream TTS responses back to meetings
- ✅ Handle bot lifecycle events via webhooks
- ✅ Session management and tracking

## Setup

### 1. Get Recall.ai API Key

1. Sign up at [recall.ai](https://www.recall.ai)
2. Get API key from [API Settings](https://app.recall.ai/settings/api-keys)
3. Add to `.env`:
   ```bash
   RECALL_API_KEY=your_api_key_here
   ```

### 2. Setup Avatar Interface URL

The Avatar Interface must be **publicly accessible** for Recall.ai to render it.

**Production**
```bash
# Provide an externally hosted avatar interface
AVATAR_INTERFACE_URL=https://yourdomain.com/avatar
```

### 3. Environment Configuration

Update `.env`:
```bash
# Recall.ai
RECALL_API_KEY=your_recall_api_key
RECALL_BOT_NAME=FIRSTWEEK Assistant
AVATAR_INTERFACE_URL=https://your-public-url

# RAG API (internal Docker network)
RAG_API_URL=http://rag-api:8000

# Default profile
DEFAULT_PROFILE_ID=exec_001_test
```

### 4. Start Services

```bash
# Start all services
docker-compose up

# Or start individually
docker-compose up recall-service
```

## API Endpoints

### Create Bot
```bash
POST /api/bot/create
```

**Request Body:**
```json
{
  "meeting_url": "https://meet.google.com/abc-defg-hij",
  "profile_id": "exec_001_test",
  "user_id": "user_123",
  "bot_name": "FIRSTWEEK Assistant"
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "session-uuid",
  "bot_id": "bot-uuid",
  "status": "joining_call",
  "meeting_url": "https://meet.google.com/abc-defg-hij"
}
```

### Get Bot Status
```bash
GET /api/bot/:botId
```

**Response:**
```json
{
  "success": true,
  "bot": {
    "id": "bot-uuid",
    "meeting_url": "...",
    "status": "in_call_not_recording",
    "join_at": "2025-01-02T10:00:00Z"
  },
  "session": {
    "id": "session-uuid",
    "profileId": "exec_001_test",
    "status": "in_call"
  }
}
```

### Delete Bot
```bash
DELETE /api/bot/:botId
```

**Response:**
```json
{
  "success": true,
  "message": "Bot removed from meeting"
}
```

### Process Transcript (called by your STT service)
```bash
POST /api/bot/:botId/process-transcript
```

**Request Body:**
```json
{
  "transcript": "What was decided about the Acme project?",
  "confidence": 0.95
}
```

**Response:**
```json
{
  "success": true,
  "answer": "Based on the decision documents...",
  "citations": [...],
  "metadata": {
    "latency_ms": 2500,
    "path": "standard"
  }
}
```

### Webhook (Recall.ai callback)
```bash
POST /api/webhook/recall
```

**Automatically processes bot status changes, join/leave events, etc.**

## Integration with Your STT Service

Your STT service should:

1. **Receive audio** from Recall.ai (via webhook/WebSocket)
2. **Transcribe** to text
3. **Call** `/api/bot/:botId/process-transcript` with the transcription
4. **Receive** RAG response with TTS audio URL
5. **Send audio** to Avatar Interface (via WebSocket or direct URL)

Example flow:
```javascript
// Your STT service receives audio
async function onAudioReceived(botId, audioBuffer) {
  // Transcribe
  const transcript = await yourSTTService.transcribe(audioBuffer);

  // Send to Recall Service
  const response = await axios.post(
    `http://recall-service:3003/api/bot/${botId}/process-transcript`,
    { transcript, confidence: 0.95 }
  );

  // response.answer contains the RAG response
  // Audio is automatically played by Avatar Interface
}
```

## Testing

### 1. Test Bot Creation (without STT)

```bash
# Create a test Google Meet
# Visit: https://meet.google.com/new

# Create bot
curl -X POST http://localhost:3003/api/bot/create \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_url": "https://meet.google.com/your-meeting-code",
    "profile_id": "exec_001_test"
  }'

# Check bot status
curl http://localhost:3003/api/bot/<bot_id>

# Delete bot
curl -X DELETE http://localhost:3003/api/bot/<bot_id>
```

### 2. Test RAG Integration

```bash
# Simulate a transcript
curl -X POST http://localhost:3003/api/bot/<bot_id>/process-transcript \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "What is the Acme project?",
    "confidence": 0.95
  }'
```

## Troubleshooting

### Bot can't join meeting

**Issue**: `Bot failed to join` error

**Solutions**:
- Ensure meeting URL is valid
- Check if meeting requires host approval (Google Meet setting)
- Verify Recall.ai API key is correct
- Check Recall.ai account has available bot quota

### Avatar Interface not loading

**Issue**: Recall.ai shows blank screen

**Solutions**:
- Verify `AVATAR_INTERFACE_URL` is publicly accessible
- Test URL in browser: `curl https://your-avatar-url`
- Check HTTPS (required by Recall.ai)
- Ensure no CORS issues

### No audio playback in meeting

**Issue**: Bot joins but participants can't hear responses

**Solutions**:
- Check Avatar Interface audio element is playing
- Verify TTS audio URL is accessible
- Test audio playback through the configured `AVATAR_INTERFACE_URL`
- Check browser console for errors

### STT integration issues

**Issue**: Transcripts not being processed

**Solutions**:
- Verify your STT service can reach Recall Service
- Check network connectivity: `curl http://recall-service:3003/health`
- Validate transcript format matches API schema
- Check Recall Service logs: `docker logs firstweek-recall-service`

## Development

```bash
cd backend/recall-service

# Install dependencies
npm install

# Run locally (requires .env)
npm run dev

# Run tests (when implemented)
npm test
```

## Production Deployment

1. **Deploy Avatar Interface** to a public domain
2. **Configure webhook URL** in Recall.ai dashboard
3. **Set environment variables** in production
4. **Monitor logs** for bot activity
5. **Set up alerts** for failed bot joins

## Resources

- [Recall.ai Documentation](https://docs.recall.ai)
- [Output Media API Guide](https://docs.recall.ai/docs/stream-media)
- [Bot API Reference](https://docs.recall.ai/reference/bot_create)
- [Webhook Events](https://docs.recall.ai/docs/bot-status-change-events)

## License

ISC
