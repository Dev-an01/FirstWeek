const logger = require("../utils/logger");

class TTSHelper {
  constructor() {
    this.ragApiUrl = process.env.RAG_API_URL || "http://rag-api:8000";
  }

  /**
   * Get TTS audio URL for text
   * Simplified approach: Use browser TTS for Phase 1
   * Future: Integrate with Kokoro TTS endpoint
   */
  // eslint-disable-next-line no-unused-vars
  async getAudioForText(text, language = "en") {
    try {
      // For Phase 1: Return null and let browser handle TTS
      // Avatar Interface will use Web Speech API
      logger.debug(
        `[TTSHelper] Using browser TTS for: ${text.substring(0, 50)} (RAG API: ${this.ragApiUrl})`,
      );
      return null;

      /* Future implementation with Kokoro TTS:
      const response = await axios.post(
        `${this.ragApiUrl}/api/v1/tts`,
        { text, language },
        { responseType: 'arraybuffer' }
      );

      // Save audio and return URL
      const audioId = `audio_${Date.now()}`;
      const audioPath = `/tmp/${audioId}.wav`;
      await fs.promises.writeFile(audioPath, response.data);
      return `${this.ragApiUrl}/audio/${audioId}`;
      */
    } catch (error) {
      logger.error("[TTSHelper] TTS error:", error);
      return null;
    }
  }
}

module.exports = TTSHelper;
