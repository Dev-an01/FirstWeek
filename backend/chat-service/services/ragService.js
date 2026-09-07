// backend/chat-service/services/ragService.js
const axios = require("axios");
const {
  createLogger,
  // eslint-disable-next-line
} = require('../shared/utils/logger');

const logger = createLogger("rag-service", process.env.LOG_LEVEL || "info");

// RAG API Configuration
const RAG_API_URL = process.env.RAG_API_URL || "http://rag-api:8000";
const RAG_API_TIMEOUT = parseInt(process.env.RAG_API_TIMEOUT || "60000", 10); // 60 seconds for LLM generation
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1000; // 1 second base delay

/**
 * Axios instance for RAG API calls
 */
const ragClient = axios.create({
  baseURL: RAG_API_URL,
  timeout: RAG_API_TIMEOUT,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * Sleep utility for retry delays
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise<void>}
 */
// eslint-disable-next-line no-promise-executor-return
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Retry wrapper with exponential backoff
 * @param {Function} fn - Async function to retry
 * @param {number} retries - Number of retry attempts
 * @returns {Promise<any>}
 */
const retryWithBackoff = async (fn, retries = MAX_RETRIES) => {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      const isLastAttempt = attempt === retries;
      const isRetriableError =
        error.code === "ECONNREFUSED" ||
        error.code === "ETIMEDOUT" ||
        error.response?.status >= 500;

      if (isLastAttempt || !isRetriableError) {
        throw error;
      }

      const delayMs = RETRY_DELAY_MS * 2 ** (attempt - 1); // Exponential backoff
      logger.warn(
        `RAG API request failed (attempt ${attempt}/${retries}), retrying in ${delayMs}ms...`,
        {
          error: error.message,
          code: error.code,
        },
      );

      await sleep(delayMs);
    }
  }
};

/**
 * Map user role to RAG API format
 * Ensures role is one of: guest, employee, manager, executive
 * @param {Object} user - User object from auth middleware
 * @returns {string} Valid RAG API role
 */
const mapUserRole = (user) => {
  // If no user (anonymous), default to guest
  if (!user) {
    return "guest";
  }

  // User model has role field (UserRole enum: GUEST, EMPLOYEE, EXECUTIVE, COMPANY_ADMIN, SUPER_ADMIN)
  // Convert from Prisma enum format (uppercase) to RAG API format (lowercase)
  const role = user.role?.toLowerCase() || "employee";

  // Validate role is one of the allowed values
  const validRoles = ["guest", "employee", "executive", "company_admin", "super_admin"];
  return validRoles.includes(role) ? role : "employee";
};

/**
 * Query RAG API for document retrieval (no LLM)
 * Returns raw retrieval results with scores and metadata
 *
 * @param {Object} params - Query parameters
 * @param {string} params.query - User's query text
 * @param {Object} params.user - User object from auth middleware
 * @param {number} params.topK - Number of results to return (default: 5)
 * @param {number} params.minScore - Minimum similarity score (default: 0.6)
 * @returns {Promise<Object>} RAG query response
 */
const queryDocuments = async ({ query, user, topK = 5, minScore = 0.15 }) => {
  try {
    logger.info("Querying RAG API for document retrieval", {
      query: query.substring(0, 50),
      userId: user?.id,
      topK,
      minScore,
    });

    const requestBody = {
      query,
      user_id: user?.id || "anonymous",
      user_role: mapUserRole(user),
      company_id: user?.companyId || null,
      top_k: topK,
      min_score: minScore,
    };

    const response = await retryWithBackoff(async () => {
      return await ragClient.post("/api/v1/query", requestBody);
    });

    logger.info("RAG API query successful", {
      resultsCount: response.data.results?.length || 0,
      performanceMs: response.data.metadata?.performance_ms,
    });

    return {
      success: true,
      results: response.data.results || [],
      metadata: response.data.metadata || {},
      requestId: response.data.request_id,
    };
  } catch (error) {
    logger.error("RAG API query failed", {
      error: error.message,
      query: query.substring(0, 50),
      userId: user?.id,
      status: error.response?.status,
      responseData: error.response?.data,
    });

    // Return graceful degradation instead of throwing
    return {
      success: false,
      error: {
        message: "Failed to retrieve documents from RAG system",
        code: "RAG_QUERY_FAILED",
        details: error.message,
      },
      results: [],
      metadata: {},
    };
  }
};

/**
 * Query RAG API with LLM integration
 * Returns natural language response with citations
 *
 * @param {Object} params - Chat parameters
 * @param {string} params.query - User's query text
 * @param {Object} params.user - User object from auth middleware
 * @param {string} params.profileId - Executive profile ID (optional)
 * @param {number} params.topK - Number of retrieval results (default: 5)
 * @param {number} params.minScore - Minimum similarity score (default: 0.6)
 * @param {string} params.forcePath - Force specific LLM path: fast|standard|agentic (optional)
 * @param {string} params.language - Language for AI response: en|ja (default: en)
 * @returns {Promise<Object>} RAG chat response with LLM-generated answer
 */
const chatWithRAG = async ({
  query,
  user,
  profileId = null,
  topK = 5,
  minScore = 0.15,
  forcePath = null,
  language = "en",
}) => {
  try {
    logger.info("Querying RAG API with LLM integration", {
      query: query.substring(0, 50),
      userId: user?.id,
      profileId,
      topK,
      minScore,
      forcePath,
      language,
    });

    const requestBody = {
      query,
      user_id: user?.id || "anonymous",
      user_role: mapUserRole(user),
      company_id: user?.companyId || null,
      profile_id: profileId,
      top_k: topK,
      min_score: minScore,
      language: language, // Language preference for AI response
    };

    if (forcePath) {
      requestBody.force_path = forcePath;
    }

    const response = await retryWithBackoff(async () => {
      return await ragClient.post("/api/v1/langgraph/chat", requestBody);
    });

    logger.info("RAG API chat successful", {
      answerLength: response.data.answer?.length || 0,
      citationCount: response.data.citations?.length || 0,
      totalLatencyMs: response.data.metadata?.total_latency_ms,
      llmPath: response.data.metadata?.path,
    });

    return {
      success: true,
      answer: response.data.answer,
      citations: response.data.citations || [],
      sources: response.data.sources || [],
      metadata: response.data.metadata || {},
      requestId: response.data.request_id,
    };
  } catch (error) {
    logger.error("RAG API chat failed", {
      error: error.message,
      query: query.substring(0, 50),
      userId: user?.id,
      profileId,
      status: error.response?.status,
      responseData: error.response?.data,
    });

    // Return graceful degradation instead of throwing
    return {
      success: false,
      error: {
        message: "Failed to generate response from RAG system",
        code: "RAG_CHAT_FAILED",
        details: error.message,
      },
      answer: null,
      citations: [],
      sources: [],
      metadata: {},
    };
  }
};

/**
 * Get available executive profiles from RAG API
 * @returns {Promise<Object>} List of available profiles
 */
const getProfiles = async (companyId = null, userRole = null) => {
  try {
    logger.info("Fetching available executive profiles from RAG API", { companyId, userRole });

    const params = {};
    if (companyId) {
      params.company_id = companyId;
    }
    if (userRole) {
      params.user_role = userRole;
    }

    const response = await retryWithBackoff(async () => {
      return await ragClient.get("/api/v1/profiles", { params });
    });

    logger.info("RAG API profiles fetched successfully", {
      profileCount: response.data.count,
    });

    return {
      success: true,
      profiles: response.data.profiles || [],
      count: response.data.count,
    };
  } catch (error) {
    logger.error("Failed to fetch RAG profiles", {
      error: error.message,
      status: error.response?.status,
    });

    return {
      success: false,
      error: {
        message: "Failed to fetch executive profiles",
        code: "RAG_PROFILES_FAILED",
        details: error.message,
      },
      profiles: [],
      count: 0,
    };
  }
};

/**
 * Get detailed information about a specific executive profile
 * @param {string} profileId - Profile ID
 * @returns {Promise<Object>} Profile details
 */
const getProfile = async (profileId) => {
  try {
    logger.info("Fetching executive profile details", { profileId });

    const response = await retryWithBackoff(async () => {
      return await ragClient.get(`/api/v1/profiles/${profileId}`);
    });

    logger.info("RAG API profile fetched successfully", { profileId });

    return {
      success: true,
      profile: response.data.profile,
    };
  } catch (error) {
    logger.error("Failed to fetch RAG profile details", {
      profileId,
      error: error.message,
      status: error.response?.status,
    });

    return {
      success: false,
      error: {
        message: `Failed to fetch profile: ${profileId}`,
        code: "RAG_PROFILE_FAILED",
        details: error.message,
      },
      profile: null,
    };
  }
};

/**
 * Check RAG API health status
 * @returns {Promise<Object>} Health status
 */
const checkHealth = async () => {
  try {
    const response = await ragClient.get("/api/v1/health", {
      timeout: 5000, // 5 second timeout for health checks
    });

    return {
      success: true,
      status: response.data.status,
      services: response.data.services,
      uptime: response.data.uptime_seconds,
    };
  } catch (error) {
    logger.error("RAG API health check failed", {
      error: error.message,
      code: error.code,
    });

    return {
      success: false,
      status: "unavailable",
      error: error.message,
    };
  }
};

/**
 * Transform SSE event from RAG API to format expected by chatHandlers.js
 * @param {string} eventType - SSE event type (start, routing, token, complete, error, etc.)
 * @param {Object} data - Event data
 * @returns {Object|null} Transformed chunk or null to skip
 */
const transformSSEEvent = (eventType, data) => {
  switch (eventType) {
    case "token":
      // RAG sends: {token: "word", index: 0}
      // chatHandlers expects: {type: "token", content: "word"}
      return {
        type: "token",
        content: data.token || "",
      };

    case "complete":
      // RAG sends: {success: true, answer: "...", citations: [...], metadata: {...}}
      // Send citations first, then complete
      // chatHandlers will collect both
      return {
        type: "complete",
        citations: data.citations || [],
        metadata: data.metadata || {},
        answer: data.answer || "",
      };

    case "error":
      // RAG sends: {error: "..."}
      // chatHandlers expects: {type: "error", message: "..."}
      return {
        type: "error",
        message: data.error || data.message || "Unknown error",
      };

    case "start":
    case "routing":
    case "retrieval":
    case "react_step":
      // These are progress events - forward as metadata for potential UI updates
      return {
        type: "progress",
        event: eventType,
        data: data,
      };

    case "audio_frame":
      // TTS audio frame - forward to chatHandlers for Socket.IO emission
      // RAG sends: {data: "base64...", index: 0, samples: 1024, segment_id: "seg_1"}
      return {
        type: "audio_frame",
        data: data.data,
        index: data.index,
        samples: data.samples,
        segment_id: data.segment_id,
      };

    default:
      // Unknown event type - log and skip
      logger.debug("Unknown SSE event type", { eventType, data });
      return null;
  }
};

/**
 * Stream chat response from RAG API
 * Uses Server-Sent Events (SSE) for real-time token streaming
 *
 * @param {Object} params - Chat parameters
 * @param {string} params.query - User's query text
 * @param {Object} params.user - User object from auth middleware
 * @param {string} params.profileId - Executive profile ID (optional)
 * @param {number} params.topK - Number of retrieval results (default: 5)
 * @param {number} params.minScore - Minimum similarity score (default: 0.6)
 * @param {string} params.forcePath - Force specific LLM path (optional)
 * @param {boolean} params.ttsEnabled - Enable TTS audio streaming (default: false)
 * @param {string} params.voiceProfileId - Voice profile ID for TTS (optional)
 * @param {string} params.language - Response language (en|ja, default: en)
 * @param {string} params.sessionId - Session ID for interrupt support (optional)
 * @returns {AsyncGenerator} Yields chunks as they arrive from RAG API
 */
async function* chatWithRAGStream({
  query,
  user,
  profileId = null,
  topK = 5,
  minScore = 0.15,
  forcePath = null,
  ttsEnabled = false,
  voiceProfileId = null,
  language = "en",
  sessionId = null,
}) {
  try {
    logger.info("Starting RAG streaming", {
      query: query.substring(0, 50),
      userId: user?.id,
      profileId,
      topK,
      minScore,
      forcePath,
      ttsEnabled,
      voiceProfileId,
      language,
    });

    const requestBody = {
      query,
      user_id: user?.id || "anonymous",
      user_role: mapUserRole(user),
      company_id: user?.companyId || null,
      profile_id: profileId,
      top_k: topK,
      min_score: minScore,
      language: language,
    };

    if (forcePath) {
      requestBody.force_path = forcePath;
    }

    // Add voice profile ID for TTS
    if (ttsEnabled && voiceProfileId) {
      requestBody.voice_profile_id = voiceProfileId;
      logger.info(`Voice profile for TTS: ${voiceProfileId}`);
    }

    // Add session ID for interrupt support
    if (sessionId) {
      requestBody.session_id = sessionId;
      logger.info(`Session ID for interrupt support: ${sessionId}`);
    }

    // Route to audio endpoint if TTS is enabled, otherwise use text-only endpoint
    const endpoint = ttsEnabled
      ? "/api/v1/langgraph/chat/stream-audio"
      : "/api/v1/langgraph/chat/stream";
    const url = `${RAG_API_URL}${endpoint}`;

    logger.info(`Using RAG endpoint: ${endpoint}`, { ttsEnabled });

    // Use native fetch for SSE streaming
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      throw new Error(
        `RAG streaming failed: ${response.status} ${response.statusText}`,
      );
    }

    // Read stream using ReadableStream API
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentEventType = null; // Track current SSE event type

    let chunkCount = 0;
    let tokenCount = 0;
    const eventTypeCounts = {};

    try {
      while (true) {
        const { done, value } = await reader.read();
        chunkCount++;

        if (done) {
          logger.info("RAG streaming complete", {
            totalChunks: chunkCount,
            totalTokens: tokenCount,
            eventTypes: eventTypeCounts,
          });
          break;
        }

        // Decode chunk and add to buffer
        const decodedChunk = decoder.decode(value, { stream: true });
        buffer += decodedChunk;

        if (chunkCount % 10 === 0) {
          // Log every 10th chunk
          logger.debug(`Received chunk #${chunkCount}`, {
            bufferSize: buffer.length,
          });
        }

        // Process complete lines from buffer
        const lines = buffer.split("\n");
        buffer = lines.pop(); // Keep incomplete line in buffer

        for (const line of lines) {
          // SSE format has two types of lines:
          // LangGraph format: "event: <type>" followed by "data: {json}"
          // Main endpoint format: "data: {type: ..., content: ...}"

          if (line.startsWith("event: ")) {
            // LangGraph format - Track current event type
            currentEventType = line.slice(7).trim();
            eventTypeCounts[currentEventType] =
              (eventTypeCounts[currentEventType] || 0) + 1;
            logger.info("📥 SSE event received", {
              eventType: currentEventType,
            });
          } else if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();

            if (data === "[DONE]") {
              logger.info("Received stream end marker");
              return;
            }

            if (data) {
              try {
                const parsed = JSON.parse(data);

                // Check if this is main endpoint format (has 'type' field) or LangGraph format
                let transformedChunk;
                if (parsed.type) {
                  // Main endpoint format: {type: 'token', content: '...'}
                  // Already in correct format for chatHandlers!
                  transformedChunk = parsed;
                  currentEventType = parsed.type; // Track for logging
                  eventTypeCounts[currentEventType] =
                    (eventTypeCounts[currentEventType] || 0) + 1;
                } else {
                  // LangGraph format: needs transformation
                  transformedChunk = transformSSEEvent(
                    currentEventType,
                    parsed,
                  );
                }

                if (transformedChunk) {
                  if (transformedChunk.type === "token") {
                    tokenCount++;
                    if (tokenCount % 10 === 0) {
                      // Log every 10th token
                      logger.debug(
                        `📤 Yielding token #${tokenCount}: "${transformedChunk.content}"`,
                      );
                    }
                  } else {
                    logger.info("📤 Yielding transformed chunk", {
                      eventType: currentEventType,
                      chunkType: transformedChunk.type,
                    });
                  }
                  yield transformedChunk;
                }

                // Reset event type after processing (LangGraph format only)
                if (!parsed.type) {
                  currentEventType = null;
                }
              } catch (parseError) {
                logger.warn("Failed to parse SSE data", {
                  data: data.substring(0, 100), // Log first 100 chars
                  eventType: currentEventType,
                  error: parseError.message,
                });
              }
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
      logger.info("Stream reader released", {
        totalChunks: chunkCount,
        totalTokens: tokenCount,
        eventTypes: eventTypeCounts,
      });
    }
  } catch (error) {
    logger.error("RAG streaming failed", {
      error: error.message,
      query: query.substring(0, 50),
      userId: user?.id,
      stack: error.stack,
    });

    // Yield error to caller
    yield {
      type: "error",
      message: "Failed to stream response from RAG system",
      details: error.message,
    };
  }
}

/**
 * Interrupt an active streaming session
 * @param {string} sessionId - Session ID to interrupt
 * @returns {Promise<Object>} Interrupt response
 */
const interruptSession = async (sessionId) => {
  try {
    logger.info("Interrupting session", { sessionId });

    const response = await ragClient.post("/api/v1/interrupt", {
      session_id: sessionId,
    });

    logger.info("Session interrupted successfully", {
      sessionId,
      state: response.data.state,
    });

    return {
      success: true,
      sessionId: response.data.session_id,
      state: response.data.state,
      message: response.data.message || "Session interrupted",
    };
  } catch (error) {
    logger.error("Failed to interrupt session", {
      sessionId,
      error: error.message,
      status: error.response?.status,
    });

    // Return graceful degradation - don't throw, just report failure
    return {
      success: false,
      sessionId,
      error: {
        message: "Failed to interrupt session",
        code: "INTERRUPT_FAILED",
        details: error.message,
      },
    };
  }
};

module.exports = {
  queryDocuments,
  chatWithRAG,
  chatWithRAGStream, // NEW: Streaming endpoint
  getProfiles,
  getProfile,
  checkHealth,
  interruptSession, // NEW: Session interrupt
};
