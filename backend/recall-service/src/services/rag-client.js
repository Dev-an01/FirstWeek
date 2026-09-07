const axios = require("axios");
const logger = require("../utils/logger");

class RAGClient {
  constructor() {
    this.ragApiUrl = process.env.RAG_API_URL || "http://rag-api:8000";
    this.defaultProfileId = process.env.DEFAULT_PROFILE_ID || "sample_profile";

    this.client = axios.create({
      baseURL: this.ragApiUrl,
      headers: {
        "Content-Type": "application/json",
      },
      timeout: 10000, // 10 second timeout
    });

    logger.info("[RAGClient] Initialized with API URL:", this.ragApiUrl);
  }

  /**
   * Send chat query to RAG API
   * @param {string} query - User query text
   * @param {Object} options - Additional options
   * @returns {Promise<Object>} RAG response with answer, citations, and audio
   */
  async chat(query, options = {}) {
    try {
      logger.info(
        "[RAGClient] Sending query to RAG API:",
        query.substring(0, 100),
      );

      const payload = {
        query: query,
        profile_id: options.profileId || this.defaultProfileId,
        user_id: options.userId || "meeting_bot",
        user_role: options.userRole || "executive",
        top_k: options.topK || 10,
      };

      const response = await this.client.post("/api/v1/chat", payload);

      logger.info("[RAGClient] Received response from RAG API");
      logger.debug("[RAGClient] Response metadata:", response.data.metadata);

      return response.data;
    } catch (error) {
      logger.error(
        "[RAGClient] Failed to get RAG response:",
        error.response?.data || error.message,
      );
      throw error;
    }
  }

  /**
   * Get streaming chat response (for future streaming support)
   * @param {string} query - User query text
   * @param {Object} options - Additional options
   * @returns {Promise<Stream>} Streaming response
   */
  async chatStream(query, options = {}) {
    try {
      logger.info("[RAGClient] Requesting streaming chat from RAG API");

      const payload = {
        query: query,
        profile_id: options.profileId || this.defaultProfileId,
        user_id: options.userId || "meeting_bot",
        user_role: options.userRole || "executive",
      };

      const response = await this.client.post("/api/v1/chat/stream", payload, {
        responseType: "stream",
      });

      return response.data;
    } catch (error) {
      logger.error(
        "[RAGClient] Failed to get streaming chat:",
        error.response?.data || error.message,
      );
      throw error;
    }
  }

  /**
   * Get TTS audio for text
   * @param {string} text - Text to convert to speech
   * @param {Object} options - TTS options
   * @returns {Promise<Buffer>} Audio buffer
   */
  async getTTSAudio(text, options = {}) {
    try {
      logger.info("[RAGClient] Requesting TTS audio");

      const response = await this.client.post(
        "/api/v1/tts",
        {
          text: text,
          language: options.language || "en",
          voice: options.voice || "default",
        },
        {
          responseType: "arraybuffer",
        },
      );

      logger.info(
        "[RAGClient] Received TTS audio:",
        response.data.byteLength,
        "bytes",
      );
      return response.data;
    } catch (error) {
      logger.error(
        "[RAGClient] Failed to get TTS audio:",
        error.response?.data || error.message,
      );
      throw error;
    }
  }

  /**
   * Check RAG API health
   * @returns {Promise<Object>} Health status
   */
  async healthCheck() {
    try {
      const response = await this.client.get("/api/v1/health");
      return response.data;
    } catch (error) {
      logger.error("[RAGClient] Health check failed:", error.message);
      throw error;
    }
  }
}

module.exports = RAGClient;
