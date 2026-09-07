const express = require("express");

const router = express.Router();
const RecallClient = require("../services/recall-client");
const RAGClient = require("../services/rag-client");
const botSessionStore = require("../models/bot-session");
const logger = require("../utils/logger");

const recallClient = new RecallClient();
const ragClient = new RAGClient();

/**
 * POST /api/bot/create
 * Create a new bot and join meeting
 */
router.post("/create", async (req, res) => {
  try {
    const { meeting_url, profile_id, user_id, bot_name, options } = req.body;

    // Validate meeting URL
    if (!meeting_url) {
      return res.status(400).json({
        error: "meeting_url is required",
      });
    }

    logger.info("[BotRoutes] Creating bot for meeting:", meeting_url);

    // Create bot via Recall.ai
    // Note: Real-time transcript webhooks require additional Recall.ai configuration
    // For now, the bot will join and display the avatar, but won't automatically
    // transcribe audio. You can manually test by sending transcripts to:
    // POST /api/bot/:botId/process-transcript
    const botData = await recallClient.createBot(meeting_url, {
      botName: bot_name,
      ...options,
    });

    // Create session
    const session = botSessionStore.create(botData, {
      profileId: profile_id,
      userId: user_id,
    });

    logger.info("[BotRoutes] Bot created successfully:", {
      botId: botData.id,
      sessionId: session.id,
    });

    res.status(201).json({
      success: true,
      session_id: session.id,
      bot_id: botData.id,
      status: botData.status_changes?.[0]?.code || "created",
      meeting_url: meeting_url,
      join_at: botData.join_at,
    });
  } catch (error) {
    logger.error("[BotRoutes] Failed to create bot:", error);
    res.status(500).json({
      error: "Failed to create bot",
      message: error.response?.data?.message || error.message,
    });
  }
});

/**
 * GET /api/bot/:botId
 * Get bot status and details
 */
router.get("/:botId", async (req, res) => {
  try {
    const { botId } = req.params;

    logger.debug("[BotRoutes] Getting bot status:", botId);

    // Get bot from Recall.ai
    const botData = await recallClient.getBot(botId);

    // Get session if exists
    const session = botSessionStore.getByBotId(botId);

    res.json({
      success: true,
      bot: botData,
      session: session,
    });
  } catch (error) {
    logger.error("[BotRoutes] Failed to get bot:", error);
    res.status(500).json({
      error: "Failed to get bot",
      message: error.response?.data?.message || error.message,
    });
  }
});

/**
 * DELETE /api/bot/:botId
 * Remove bot from meeting
 */
router.delete("/:botId", async (req, res) => {
  try {
    const { botId } = req.params;

    logger.info("[BotRoutes] Deleting bot:", botId);

    // Delete bot via Recall.ai
    await recallClient.deleteBot(botId);

    // Delete session
    botSessionStore.deleteByBotId(botId);

    res.json({
      success: true,
      message: "Bot removed from meeting",
    });
  } catch (error) {
    logger.error("[BotRoutes] Failed to delete bot:", error);
    res.status(500).json({
      error: "Failed to delete bot",
      message: error.response?.data?.message || error.message,
    });
  }
});

/**
 * GET /api/bot
 * List all bots
 */
router.get("/", async (req, res) => {
  try {
    logger.debug("[BotRoutes] Listing all bots");

    // Get bots from Recall.ai
    const bots = await recallClient.listBots();

    // Get sessions
    const sessions = botSessionStore.list();

    res.json({
      success: true,
      bots: bots,
      sessions: sessions,
    });
  } catch (error) {
    logger.error("[BotRoutes] Failed to list bots:", error);
    res.status(500).json({
      error: "Failed to list bots",
      message: error.response?.data?.message || error.message,
    });
  }
});

/**
 * POST /api/bot/:botId/process-transcript
 * Process transcript and get RAG response
 * This endpoint will be called by your STT service
 */
router.post("/:botId/process-transcript", async (req, res) => {
  try {
    const { botId } = req.params;
    const { transcript } = req.body;

    if (!transcript) {
      return res.status(400).json({
        error: "transcript is required",
      });
    }

    logger.info("[BotRoutes] Processing transcript for bot:", botId);
    logger.debug("[BotRoutes] Transcript:", transcript);

    // Get session
    const session = botSessionStore.getByBotId(botId);
    if (!session) {
      return res.status(404).json({
        error: "Session not found for bot",
      });
    }

    // Send to RAG API
    const ragResponse = await ragClient.chat(transcript, {
      profileId: session.profileId,
      userId: session.userId,
    });

    // Update session
    botSessionStore.updateByBotId(botId, {
      lastQuery: transcript,
      lastResponse: ragResponse.answer,
    });

    logger.info("[BotRoutes] RAG response received");

    res.json({
      success: true,
      answer: ragResponse.answer,
      citations: ragResponse.citations,
      metadata: ragResponse.metadata,
    });
  } catch (error) {
    logger.error("[BotRoutes] Failed to process transcript:", error);
    res.status(500).json({
      error: "Failed to process transcript",
      message: error.message,
    });
  }
});

module.exports = router;
