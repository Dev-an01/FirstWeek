import { create } from 'zustand';
import * as api from '../services/api';
import logger from '../utils/logger';

/**
 * Chat Store - Manages conversations, messages, and RAG integration
 *
 * Features:
 * - Conversation list management with pagination
 * - Message history for current conversation
 * - Message sending with RAG integration
 * - Optimistic UI updates
 * - Error handling with toast notifications
 */
export const useChatStore = create((set, get) => ({
  // ============================================
  // STATE - Conversations
  // ============================================
  conversations: [],
  currentConversation: null,
  conversationsLoading: false,
  conversationsPagination: {
    total: 0,
    limit: 20,
    offset: 0,
    hasMore: false,
  },

  // ============================================
  // STATE - Messages
  // ============================================
  messages: [],
  messagesLoading: false,
  messagesPagination: {
    total: 0,
    limit: 50,
    offset: 0,
    hasMore: false,
  },

  // ============================================
  // STATE - Message Sending
  // ============================================
  isSendingMessage: false,

  // ============================================
  // STATE - Streaming Messages
  // ============================================
  streamingMessage: null, // Current message being streamed
  isStreaming: false,
  streamingCancelledByUser: false, // Track if user manually stopped streaming

  // ============================================
  // STATE - RAG
  // ============================================
  ragProfiles: [],
  ragProfilesLoading: false,
  selectedProfile: null,
  conversationProfiles: {}, // Map of conversationId -> profileId to persist per conversation

  // ============================================
  // STATE - TTS (Text-to-Speech)
  // ============================================
  ttsEnabled: false, // Whether TTS is enabled
  audioPlaying: false, // Whether audio is currently playing

  // ============================================
  // ACTIONS - Conversations
  // ============================================

  /**
   * Fetch conversations with pagination
   */
  fetchConversations: async (limit = 20, offset = 0) => {
    set({ conversationsLoading: true });

    try {
      const response = await api.getConversations(limit, offset);
      // Axios interceptor already extracts response.data, so we access response.data directly
      const { conversations, pagination } = response.data;

      set({
        conversations:
          offset === 0
            ? conversations
            : [...get().conversations, ...conversations],
        conversationsPagination: pagination,
        conversationsLoading: false,
      });

      return conversations;
    } catch (error) {
      logger.error('Failed to fetch conversations:', error);
      set({ conversationsLoading: false });
      throw error;
    }
  },

  /**
   * Load more conversations (pagination)
   */
  loadMoreConversations: async () => {
    const { conversationsPagination, conversationsLoading } = get();

    if (conversationsLoading || !conversationsPagination.hasMore) {
      return;
    }

    const newOffset =
      conversationsPagination.offset + conversationsPagination.limit;
    await get().fetchConversations(conversationsPagination.limit, newOffset);
  },

  /**
   * Create a new conversation
   */
  createConversation: async (title = 'New Chat') => {
    try {
      const response = await api.createConversation(title);
      const newConversation = response.data;

      // Add to beginning of list
      set((state) => ({
        conversations: [newConversation, ...state.conversations],
        currentConversation: newConversation,
        conversationsPagination: {
          ...state.conversationsPagination,
          total: state.conversationsPagination.total + 1,
        },
      }));

      // Clear messages for new conversation
      get().clearMessages();

      return newConversation;
    } catch (error) {
      logger.error('Failed to create conversation:', error);
      throw error;
    }
  },

  /**
   * Get a specific conversation by ID
   */
  getConversation: async (id) => {
    try {
      const response = await api.getConversation(id);
      const conversation = response.data;

      set({ currentConversation: conversation });

      return conversation;
    } catch (error) {
      logger.error('Failed to get conversation:', error);
      throw error;
    }
  },

  /**
   * Update conversation title
   */
  updateConversation: async (id, title) => {
    try {
      const response = await api.updateConversation(id, title);
      const updatedConversation = response.data;

      // Update in conversations list
      set((state) => ({
        conversations: state.conversations.map((conv) =>
          conv.id === id ? { ...conv, title: updatedConversation.title } : conv
        ),
        currentConversation:
          state.currentConversation?.id === id
            ? { ...state.currentConversation, title: updatedConversation.title }
            : state.currentConversation,
      }));

      return updatedConversation;
    } catch (error) {
      logger.error('Failed to update conversation:', error);
      throw error;
    }
  },

  /**
   * Delete a conversation
   */
  deleteConversation: async (id) => {
    try {
      await api.deleteConversation(id);

      // Remove from list
      set((state) => {
        const newConversations = state.conversations.filter(
          (conv) => conv.id !== id
        );
        const wasCurrentConversation = state.currentConversation?.id === id;

        return {
          conversations: newConversations,
          currentConversation: wasCurrentConversation
            ? null
            : state.currentConversation,
          conversationsPagination: {
            ...state.conversationsPagination,
            total: Math.max(0, state.conversationsPagination.total - 1),
          },
        };
      });

      // Clear messages if deleted conversation was current
      if (get().currentConversation === null) {
        get().clearMessages();
      }
    } catch (error) {
      logger.error('Failed to delete conversation:', error);
      throw error;
    }
  },

  /**
   * Set current conversation
   */
  setCurrentConversation: (conversation) => {
    set({ currentConversation: conversation });

    // Clear previous messages when switching conversations
    if (conversation) {
      get().clearMessages();
    }
  },

  // ============================================
  // ACTIONS - Messages
  // ============================================

  /**
   * Fetch messages for a conversation
   */
  fetchMessages: async (conversationId, limit = 50, offset = 0) => {
    set({ messagesLoading: true });

    try {
      const response = await api.getMessages(conversationId, limit, offset);
      const { messages, pagination } = response.data;

      set({
        messages: offset === 0 ? messages : [...messages, ...get().messages],
        messagesPagination: pagination,
        messagesLoading: false,
      });

      return messages;
    } catch (error) {
      logger.error('Failed to fetch messages:', error);
      set({ messagesLoading: false });
      throw error;
    }
  },

  /**
   * Load more messages (pagination - older messages)
   */
  loadMoreMessages: async () => {
    const { messagesPagination, messagesLoading, currentConversation } = get();

    if (
      messagesLoading ||
      !messagesPagination.hasMore ||
      !currentConversation
    ) {
      return;
    }

    const newOffset = messagesPagination.offset + messagesPagination.limit;
    await get().fetchMessages(
      currentConversation.id,
      messagesPagination.limit,
      newOffset
    );
  },

  /**
   * Send a message with optimistic UI update
   */
  sendMessage: async (conversationId, content, ragOptions = {}) => {
    if (!content.trim()) {
      return undefined;
    }

    const optimisticUserMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      createdAt: new Date().toISOString(),
      isOptimistic: true,
    };

    // Optimistic update - add user message immediately
    set((state) => ({
      messages: [...state.messages, optimisticUserMessage],
      isSendingMessage: true,
    }));

    try {
      const response = await api.sendMessage(
        conversationId,
        content,
        ragOptions
      );
      const { userMessage, assistantMessage } = response.data;

      // Replace optimistic message with real messages
      set((state) => ({
        messages: [
          ...state.messages.filter((msg) => !msg.isOptimistic),
          userMessage,
          assistantMessage,
        ],
        isSendingMessage: false,
      }));

      // Update conversation lastMessageAt in list
      set((state) => ({
        conversations: state.conversations.map((conv) =>
          conv.id === conversationId
            ? {
                ...conv,
                lastMessageAt: assistantMessage.createdAt,
                lastMessagePreview: assistantMessage.content.substring(0, 100),
                messageCount: (conv.messageCount || 0) + 2,
              }
            : conv
        ),
      }));

      return { userMessage, assistantMessage };
    } catch (error) {
      logger.error('Failed to send message:', error);

      // Remove optimistic message on error
      set((state) => ({
        messages: state.messages.filter((msg) => !msg.isOptimistic),
        isSendingMessage: false,
      }));

      throw error;
    }
  },

  /**
   * Clear messages (when switching conversations)
   */
  clearMessages: () => {
    set({
      messages: [],
      messagesPagination: {
        total: 0,
        limit: 50,
        offset: 0,
        hasMore: false,
      },
      streamingMessage: null,
      isStreaming: false,
      streamingCancelledByUser: false,
    });
  },

  // ============================================
  // ACTIONS - Streaming Messages
  // ============================================

  /**
   * Start streaming a new assistant message
   */
  startStreamingMessage: (messageId) => {
    const streamingMessage = {
      id: messageId || `streaming-${Date.now()}`,
      role: 'assistant',
      content: '',
      createdAt: new Date().toISOString(),
      isStreaming: true,
    };

    set((state) => ({
      messages: [...state.messages, streamingMessage],
      streamingMessage,
      isStreaming: true,
      streamingCancelledByUser: false, // Reset cancel flag for new message
    }));
  },

  /**
   * Append content to the streaming message
   */
  appendStreamingContent: (chunk) => {
    set((state) => {
      if (!state.streamingMessage) {
        logger.warn('[chatStore] No streaming message to append to');
        return state;
      }

      const updatedStreamingMessage = {
        ...state.streamingMessage,
        content: state.streamingMessage.content + chunk,
      };

      // Create completely new messages array to force React re-render
      const newMessages = state.messages.map((msg) =>
        msg.id === state.streamingMessage.id
          ? { ...updatedStreamingMessage } // Create new object reference
          : msg
      );

      return {
        messages: newMessages,
        streamingMessage: updatedStreamingMessage,
      };
    });
  },

  /**
   * Complete the streaming message with final data
   */
  completeStreamingMessage: (finalMessage) => {
    set((state) => {
      // If user manually cancelled, ignore the complete event
      if (state.streamingCancelledByUser) {
        logger.log(
          '[chatStore] Ignoring message:complete - user cancelled streaming'
        );
        return state;
      }

      if (!state.streamingMessage) {
        logger.warn('[chatStore] No streaming message to complete');
        return state;
      }

      // Replace streaming message with final message
      const completedMessage = {
        ...finalMessage,
        isStreaming: false,
      };

      return {
        messages: state.messages.map((msg) =>
          msg.id === state.streamingMessage.id ? completedMessage : msg
        ),
        streamingMessage: null,
        isStreaming: false,
        streamingCancelledByUser: false, // Reset flag
      };
    });
  },

  /**
   * Cancel streaming (on error or user request)
   */
  cancelStreaming: () => {
    set((state) => {
      if (!state.streamingMessage) {
        return state;
      }

      // Keep the partial message (don't remove it) but mark as stopped
      const stoppedMessage = {
        ...state.streamingMessage,
        isStreaming: false,
        content: state.streamingMessage.content, // Don't add [Stopped] text
        isCancelled: true, // Mark as cancelled
      };

      return {
        messages: state.messages.map((msg) =>
          msg.id === state.streamingMessage.id ? stoppedMessage : msg
        ),
        streamingMessage: null,
        isStreaming: false,
        isSendingMessage: false,
        streamingCancelledByUser: true, // Set flag to ignore complete event
      };
    });
  },

  // ============================================
  // ACTIONS - RAG
  // ============================================

  /**
   * Fetch available RAG profiles
   * Cached: Only fetches if profiles array is empty
   */
  fetchRagProfiles: async (force = false) => {
    // Check cache - skip if profiles already loaded (unless forced)
    const currentProfiles = get().ragProfiles;
    if (!force && currentProfiles.length > 0) {
      logger.log('[chatStore] RAG profiles already cached, skipping fetch');
      return currentProfiles;
    }

    set({ ragProfilesLoading: true });

    try {
      // Get companyId from auth store for tenant isolation
      const { useAuthStore } = await import('./authStore');
      const companyId = useAuthStore.getState().user?.companyId || null;
      logger.log('[chatStore] Fetching RAG profiles...', { companyId });
      const response = await api.getRagProfiles(companyId);
      logger.log('[chatStore] RAG profiles response:', response);

      // The axios interceptor already extracts response.data
      // So the structure is: { success, message, data: { profiles, count } }
      const { profiles } = response.data;

      // Map backend fields to frontend format
      const mappedProfiles = profiles.map((profile) => ({
        id: profile.id,
        name: profile.name,
        description: profile.title, // Use title as description
        title: profile.title,
        department: profile.department,
        expertise: profile.expertise,
        communication_style: profile.communication_style,
      }));

      set({
        ragProfiles: mappedProfiles,
        ragProfilesLoading: false,
      });

      // Don't auto-select any profile - let user choose explicitly
      logger.log('[chatStore] RAG profiles loaded, no auto-selection');

      return mappedProfiles;
    } catch (error) {
      logger.error('[chatStore] Failed to fetch RAG profiles');
      logger.error('[chatStore] Error object:', error);
      logger.error('[chatStore] Error details:', {
        message: error.message,
        response: error.response,
        status: error.status,
        name: error.name,
        stack: error.stack,
      });

      // Check if it's an axios error with response
      if (error.response) {
        logger.error('[chatStore] Response data:', error.response.data);
        logger.error('[chatStore] Response status:', error.response.status);
      }

      set({ ragProfilesLoading: false });

      // Don't throw - just fail silently since profiles are optional
      // Return empty array on error
      return [];
    }
  },

  /**
   * Set selected RAG profile
   */
  setSelectedProfile: (profile) => {
    set({ selectedProfile: profile });
  },

  /**
   * Query RAG directly (for testing/debugging)
   */
  queryRag: async (query, topK = 5, minScore = 0.15) => {
    try {
      const response = await api.ragQuery(query, topK, minScore);
      return response.data;
    } catch (error) {
      logger.error('Failed to query RAG:', error);
      throw error;
    }
  },

  // ============================================
  // ACTIONS - TTS (Text-to-Speech)
  // ============================================

  /**
   * Toggle TTS on/off
   */
  toggleTTS: () => {
    set((state) => ({ ttsEnabled: !state.ttsEnabled }));
  },

  /**
   * Set audio playing state
   */
  setAudioPlaying: (playing) => {
    set({ audioPlaying: playing });
  },

  // ============================================
  // ACTIONS - Reset
  // ============================================

  /**
   * Reset store to initial state (on logout)
   */
  reset: () => {
    set({
      conversations: [],
      currentConversation: null,
      conversationsLoading: false,
      conversationsPagination: {
        total: 0,
        limit: 20,
        offset: 0,
        hasMore: false,
      },
      messages: [],
      messagesLoading: false,
      messagesPagination: {
        total: 0,
        limit: 50,
        offset: 0,
        hasMore: false,
      },
      isSendingMessage: false,
      streamingMessage: null,
      isStreaming: false,
      streamingCancelledByUser: false,
      ragProfiles: [],
      ragProfilesLoading: false,
      selectedProfile: null,
      ttsEnabled: false,
      audioPlaying: false,
    });
  },
}));
