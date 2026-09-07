const express = require("express");

const router = express.Router();
const RAGClient = require("../services/rag-client");
const botSessionStore = require("../models/bot-session");
const logger = require("../utils/logger");

/**
 * POST /api/webhook/recall
 * Receive webhooks from Recall.ai
 * Event types: bot.status_change, bot.analysis_done, etc.
 */
router.post("/recall", async (req, res) => {
  try {
    const event = req.body;

    logger.info("[WebhookRoutes] Received webhook:", event.event?.code);
    logger.debug(
      "[WebhookRoutes] Webhook data:",
      JSON.stringify(event, null, 2),
    );

    // Acknowledge receipt immediately
    res.status(200).json({ received: true });

    // Process webhook asynchronously
    processWebhook(event);
  } catch (error) {
    logger.error("[WebhookRoutes] Failed to process webhook:", error);
    res.status(500).json({
      error: "Failed to process webhook",
    });
  }
});

/**
 * Process webhook event asynchronously
 * @param {Object} event - Webhook event data
 */
async function processWebhook(event) {
  try {
    const eventCode = event.event?.code;
    const botId = event.data?.bot_id;

    if (!botId) {
      logger.warn("[WebhookRoutes] Webhook missing bot_id");
      return;
    }

    // Update session based on event type
    switch (eventCode) {
      case "bot.status_change":
        handleBotStatusChange(event);
        break;

      case "bot.join_call":
        handleBotJoinCall(event);
        break;

      case "bot.leave_call":
        handleBotLeaveCall(event);
        break;

      case "bot.analysis_done":
        handleAnalysisDone(event);
        break;

      case "bot.recording_done":
        handleRecordingDone(event);
        break;

      case "bot.transcript.gladia":
      case "bot.transcript.deepgram":
      case "bot.transcript.assembly_ai":
        handleTranscript(event);
        break;

      default:
        logger.debug("[WebhookRoutes] Unhandled event type:", eventCode);
    }
  } catch (error) {
    logger.error("[WebhookRoutes] Error processing webhook:", error);
  }
}

/**
 * Handle bot status change event
 * @param {Object} event - Event data
 */
function handleBotStatusChange(event) {
  const botId = event.data.bot_id;
  const status = event.data.status?.code;

  logger.info("[WebhookRoutes] Bot status changed:", botId, "→", status);

  botSessionStore.updateByBotId(botId, {
    status: status,
    statusMessage: event.data.status?.message,
  });
}

/**
 * Handle bot join call event
 * @param {Object} event - Event data
 */
function handleBotJoinCall(event) {
  const botId = event.data.bot_id;

  logger.info("[WebhookRoutes] Bot joined call:", botId);

  botSessionStore.updateByBotId(botId, {
    status: "in_call",
    joinedAt: event.data.created_at || new Date().toISOString(),
  });
}

/**
 * Handle bot leave call event
 * @param {Object} event - Event data
 */
function handleBotLeaveCall(event) {
  const botId = event.data.bot_id;

  logger.info("[WebhookRoutes] Bot left call:", botId);

  botSessionStore.updateByBotId(botId, {
    status: "left_call",
    leftAt: event.data.created_at || new Date().toISOString(),
  });
}

/**
 * Handle analysis done event
 * @param {Object} event - Event data
 */
function handleAnalysisDone(event) {
  const botId = event.data.bot_id;

  logger.info("[WebhookRoutes] Analysis done for bot:", botId);

  botSessionStore.updateByBotId(botId, {
    analysisCompleted: true,
    transcriptUrl: event.data.transcript_url,
  });
}

/**
 * Handle recording done event
 * @param {Object} event - Event data
 */
function handleRecordingDone(event) {
  const botId = event.data.bot_id;

  logger.info("[WebhookRoutes] Recording done for bot:", botId);

  botSessionStore.updateByBotId(botId, {
    recordingCompleted: true,
    recordingUrl: event.data.video_url,
    audioUrl: event.data.audio_url,
  });
}

/**
 * Handle real-time transcript event
 * @param {Object} event - Event data
 */
async function handleTranscript(event) {
  const botId = event.data.bot_id;
  const transcript = event.data.transcript;

  if (!transcript || !transcript.words || transcript.words.length === 0) {
    return;
  }

  // Combine words into full text
  const text = transcript.words.map((w) => w.text).join(" ");
  const speaker = transcript.speaker;

  logger.info("[WebhookRoutes] Transcript received:", {
    botId,
    speaker,
    text: `${text.substring(0, 50)}...`,
  });

  // Get session for this bot
  const session = botSessionStore.getByBotId(botId);
  if (!session) {
    logger.warn("[WebhookRoutes] No session found for bot:", botId);
    return;
  }

  // Process transcript with RAG
  const ragClient = new RAGClient();

  try {
    const response = await ragClient.chat(text, {
      profileId: session.profileId,
      userId: `bot_${botId}`,
      userRole: "executive",
    });

    if (response.success) {
      logger.info("[WebhookRoutes] RAG response generated for transcript");

      // TODO: Send response back to Avatar Interface via WebSocket or SSE
      // For now, just log it
      logger.info(
        "[WebhookRoutes] Response:",
        `${response.answer.substring(0, 100)}...`,
      );
    }
  } catch (error) {
    logger.error("[WebhookRoutes] Failed to process transcript:", error);
  }
}

module.exports = router;
