const { v4: uuidv4 } = require("uuid");
const logger = require("../utils/logger");

/**
 * In-memory store for bot sessions
 * For production, use Redis or PostgreSQL
 */
class BotSessionStore {
    constructor() {
        this.sessions = new Map();
    }

    /**
     * Create a new bot session
     * @param {Object} botData - Bot data from Recall.ai
     * @param {Object} metadata - Additional metadata
     * @returns {Object} Session data
     */
    create(botData, metadata = {}) {
        const session = {
            id: uuidv4(),
            botId: botData.id,
            meetingUrl: botData.meeting_url,
            status: botData.status_changes?.[0]?.code || "created",
            profileId: metadata.profileId || process.env.DEFAULT_PROFILE_ID,
            userId: metadata.userId || "meeting_bot",
            createdAt: new Date().toISOString(),
            lastActivity: new Date().toISOString(),
            ...metadata,
        };

        this.sessions.set(session.id, session);
        logger.info("[BotSession] Created session:", session.id);
        return session;
    }

    /**
     * Get session by ID
     * @param {string} sessionId - Session ID
     * @returns {Object|null} Session data
     */
    get(sessionId) {
        return this.sessions.get(sessionId) || null;
    }

    /**
     * Get session by bot ID
     * @param {string} botId - Bot ID from Recall.ai
     * @returns {Object|null} Session data
     */
    getByBotId(botId) {
        for (const session of this.sessions.values()) {
            if (session.botId === botId) {
                return session;
            }
        }
        return null;
    }

    /**
     * Update session
     * @param {string} sessionId - Session ID
     * @param {Object} updates - Fields to update
     * @returns {Object|null} Updated session
     */
    update(sessionId, updates) {
        const session = this.sessions.get(sessionId);
        if (!session) {
            logger.warn("[BotSession] Session not found:", sessionId);
            return null;
        }

        Object.assign(session, updates, {
            lastActivity: new Date().toISOString(),
        });

        this.sessions.set(sessionId, session);
        logger.debug("[BotSession] Updated session:", sessionId);
        return session;
    }

    /**
     * Update session by bot ID
     * @param {string} botId - Bot ID
     * @param {Object} updates - Fields to update
     * @returns {Object|null} Updated session
     */
    updateByBotId(botId, updates) {
        const session = this.getByBotId(botId);
        if (!session) {
            logger.warn("[BotSession] Session not found for bot:", botId);
            return null;
        }

        return this.update(session.id, updates);
    }

    /**
     * Delete session
     * @param {string} sessionId - Session ID
     * @returns {boolean} True if deleted
     */
    delete(sessionId) {
        const result = this.sessions.delete(sessionId);
        if (result) {
            logger.info("[BotSession] Deleted session:", sessionId);
        }
        return result;
    }

    /**
     * Delete session by bot ID
     * @param {string} botId - Bot ID
     * @returns {boolean} True if deleted
     */
    deleteByBotId(botId) {
        const session = this.getByBotId(botId);
        if (!session) {
            return false;
        }
        return this.delete(session.id);
    }

    /**
     * List all sessions
     * @returns {Array} Array of sessions
     */
    list() {
        return Array.from(this.sessions.values());
    }

    /**
     * Clean up old sessions (older than ttl in ms)
     * @param {number} ttl - Time to live in milliseconds
     * @returns {number} Number of sessions cleaned
     */
    cleanup(ttl = 24 * 60 * 60 * 1000) {
        // Default 24 hours
        const now = Date.now();
        let cleaned = 0;

        for (const [id, session] of this.sessions.entries()) {
            const age = now - new Date(session.lastActivity).getTime();
            if (age > ttl) {
                this.sessions.delete(id);
                cleaned++;
            }
        }

        if (cleaned > 0) {
            logger.info("[BotSession] Cleaned up", cleaned, "old sessions");
        }

        return cleaned;
    }
}

// Singleton instance
const botSessionStore = new BotSessionStore();

// Run cleanup every hour
setInterval(
    () => {
        botSessionStore.cleanup();
    },
    60 * 60 * 1000,
);

module.exports = botSessionStore;
