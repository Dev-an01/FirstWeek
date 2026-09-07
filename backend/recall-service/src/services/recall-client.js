const axios = require("axios");
const logger = require("../utils/logger");

class RecallClient {
  constructor() {
    this.apiKey = process.env.RECALL_API_KEY;
    this.apiUrl = process.env.RECALL_API_URL || "https://api.recall.ai/api/v1";
    this.botName = process.env.RECALL_BOT_NAME || "Sample Executive";
    this.avatarInterfaceUrl = process.env.AVATAR_INTERFACE_URL;

    if (!this.apiKey) {
      throw new Error("RECALL_API_KEY environment variable is required");
    }

    if (!this.avatarInterfaceUrl) {
      throw new Error("AVATAR_INTERFACE_URL environment variable is required");
    }

    this.client = axios.create({
      baseURL: this.apiUrl,
      headers: {
        Authorization: `Token ${this.apiKey}`,
        "Content-Type": "application/json",
      },
    });

    logger.info("[RecallClient] Initialized with API URL:", this.apiUrl);
  }

  /**
   * Create a new bot and join meeting
   * @param {string} meetingUrl - Meeting URL (Zoom, Google Meet, etc.)
   * @param {Object} options - Bot configuration options
   * @returns {Promise<Object>} Bot data including bot_id
   */
  async createBot(meetingUrl, options = {}) {
    try {
      logger.info("[RecallClient] Creating bot for meeting:", meetingUrl);

      logger.info("[RecallClient] Creating bot with name: ", this.botName);

      const payload = {
        meeting_url: meetingUrl,
        bot_name: "Sample Executive",

        // Bot variant - MUST be object with platform-specific variants
        // Per docs: https://docs.recall.ai/docs/stream-media#addressing-audio-and-video-issues-bot-variants
        // web_4_core gives more CPU power for better audio/video quality
        variant: {
          zoom: "web_4_core",
          google_meet: "web_4_core",
          microsoft_teams: "web_4_core",
        },

        // CRITICAL: Enable media processing so meeting audio flows to webpage
        // Without this, MediaStream will be silent!
        media_retention: {
          // This tells Recall to process meeting audio and make it available to the bot
          in_memory_recording: true, // Required for Output Media bots to access live audio
        },

        // Output Media Configuration
        // Bot automatically provides meeting audio to webpage via getUserMedia()
        output_media: {
          camera: {
            kind: "webpage",
            config: {
              // Include bot_id as query parameter so Avatar Interface knows which bot it's serving
              url: `${this.avatarInterfaceUrl}?bot_id=${meetingUrl.replace(/[^a-zA-Z0-9]/g, "_")}_${Date.now()}&lang=${options.language || "en"}`,
            },
          },
        },

        // Automatic leave settings
        automatic_leave: {
          waiting_room_timeout: options.waitingRoomTimeout || 600, // 10 minutes
          noone_joined_timeout: options.nooneJoinedTimeout || 300, // 5 minutes
        },
      };

      logger.info(
        "[RecallClient] Sending payload to Recall.ai:",
        JSON.stringify(payload, null, 2),
      );

      const response = await this.client.post("/bot", payload);

      logger.info("[RecallClient] Bot created successfully:", response.data.id);
      logger.info(
        "[RecallClient] Bot response:",
        JSON.stringify(response.data, null, 2),
      );
      return response.data;
    } catch (error) {
      logger.error(
        "[RecallClient] Failed to create bot:",
        error.response?.data || error.message,
      );
      throw error;
    }
  }

  /**
   * Get bot status and details
   * @param {string} botId - Bot ID
   * @returns {Promise<Object>} Bot details
   */
  async getBot(botId) {
    try {
      const response = await this.client.get(`/bot/${botId}`);
      return response.data;
    } catch (error) {
      logger.error(
        "[RecallClient] Failed to get bot:",
        error.response?.data || error.message,
      );
      throw error;
    }
  }

  /**
   * Delete bot and leave meeting
   * @param {string} botId - Bot ID
   * @returns {Promise<void>}
   */
  async deleteBot(botId) {
    try {
      logger.info("[RecallClient] Deleting bot:", botId);
      await this.client.delete(`/bot/${botId}`);
      logger.info("[RecallClient] Bot deleted successfully:", botId);
    } catch (error) {
      logger.error(
        "[RecallClient] Failed to delete bot:",
        error.response?.data || error.message,
      );
      throw error;
    }
  }

  /**
   * List all bots
   * @returns {Promise<Array>} List of bots
   */
  async listBots() {
    try {
      const response = await this.client.get("/bot");
      return response.data;
    } catch (error) {
      logger.error(
        "[RecallClient] Failed to list bots:",
        error.response?.data || error.message,
      );
      throw error;
    }
  }

  /**
   * Send output audio to bot (if needed for manual control)
   * @param {string} botId - Bot ID
   * @param {Buffer} audioData - Audio data
   * @returns {Promise<void>}
   */
  async sendOutputAudio(botId, audioData) {
    try {
      await this.client.post(`/bot/${botId}/output_audio`, audioData, {
        headers: {
          "Content-Type": "audio/wav",
        },
      });
      logger.debug("[RecallClient] Sent output audio to bot:", botId);
    } catch (error) {
      logger.error(
        "[RecallClient] Failed to send output audio:",
        error.response?.data || error.message,
      );
      throw error;
    }
  }
}

module.exports = RecallClient;
