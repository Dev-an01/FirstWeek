import { useEffect, useState, useRef, useCallback, memo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useChatStore } from '../store/chatStore';
import { useUIStore } from '../store/uiStore';
import { Navbar } from '../components/Navbar/Navbar';
import { Sidebar } from '../components/Sidebar/Sidebar';
import { ChatSidebarContent } from '../components/Chat/ChatSidebarContent';
import { ConversationHeader } from '../components/Chat/ConversationHeader';
import { MessageList } from '../components/Chat/MessageList';
import { MessageInput } from '../components/Chat/MessageInput';
import { EmptyState } from '../components/Chat/EmptyState';
import { ExecutiveSelector } from '../components/Chat/ExecutiveSelector';
import { socketManager } from '../services/socket';
import { audioManager } from '../utils/audioManager';
import logger from '../utils/logger';

/**
 * ChatPage Component
 *
 * Main chat interface with conversation management
 *
 * Features:
 * - Conversation sidebar (desktop) / drawer (mobile)
 * - Message display with auto-scroll
 * - Send messages with optimistic updates
 * - Create/update/delete conversations
 * - Responsive layout
 * - Direct Zustand store access (following codebase pattern)
 * - Optimized with React.memo and useCallback to prevent unnecessary re-renders
 */
function ChatPageComponent() {
  const { t } = useTranslation();
  const { conversationId } = useParams();
  const navigate = useNavigate();

  // UI state
  const [executiveSelectorOpen, setExecutiveSelectorOpen] = useState(false);
  const [socketConnected, setSocketConnected] = useState(false);
  // eslint-disable-next-line no-unused-vars
  const [roomJoined, setRoomJoined] = useState(false); // Track if joined conversation room

  // Refs
  const currentConversationIdRef = useRef(null);
  const currentSessionIdRef = useRef(null); // Track current session for interrupt support
  const listenersRef = useRef({}); // Store listener references for cleanup
  const isMountedRef = useRef(true); // Track if component is mounted

  // Audio processing queue to ensure batches are processed in order
  const audioQueueRef = useRef([]);
  const isProcessingAudioRef = useRef(false);

  // Chat store (optimized with selectors to prevent unnecessary re-renders)
  // Only subscribe to state values, not actions
  const currentConversation = useChatStore(
    (state) => state.currentConversation
  );
  const messages = useChatStore((state) => state.messages);
  const messagesLoading = useChatStore((state) => state.messagesLoading);
  const isStreaming = useChatStore((state) => state.isStreaming);
  const messagesPagination = useChatStore((state) => state.messagesPagination);

  const fetchConversations = useChatStore((state) => state.fetchConversations);
  const getConversation = useChatStore((state) => state.getConversation);
  const setCurrentConversation = useChatStore(
    (state) => state.setCurrentConversation
  );
  const fetchMessages = useChatStore((state) => state.fetchMessages);
  const loadMoreMessages = useChatStore((state) => state.loadMoreMessages);
  const fetchRagProfiles = useChatStore((state) => state.fetchRagProfiles);
  const setSelectedProfile = useChatStore((state) => state.setSelectedProfile);
  const appendStreamingContent = useChatStore(
    (state) => state.appendStreamingContent
  );
  const completeStreamingMessage = useChatStore(
    (state) => state.completeStreamingMessage
  );
  const cancelStreaming = useChatStore((state) => state.cancelStreaming);
  const setAudioPlaying = useChatStore((state) => state.setAudioPlaying);

  // UI store (optimized with selectors)
  const showSuccessToast = useUIStore((state) => state.showSuccessToast);
  const showErrorToast = useUIStore((state) => state.showErrorToast);
  const sidebarOpen = useUIStore((state) => state.sidebarOpen);
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);

  /**
   * Process audio batch queue sequentially
   */
  const processAudioQueue = useCallback(async () => {
    if (isProcessingAudioRef.current) return;
    if (audioQueueRef.current.length === 0) return;

    isProcessingAudioRef.current = true;

    while (audioQueueRef.current.length > 0) {
      const batch = audioQueueRef.current.shift();
      try {
        await audioManager.addBatch(batch);
      } catch (err) {
        console.error('[ChatPage] Failed to process queued batch:', err);
      }
    }

    isProcessingAudioRef.current = false;
  }, []);

  /**
   * Stop audio playback
   */
  const handleStopAudio = useCallback(() => {
    audioQueueRef.current = [];
    isProcessingAudioRef.current = false;
    audioManager.stop();
    setAudioPlaying(false);
  }, [setAudioPlaying]);

  /**
   * Setup Socket.IO event listeners
   */
  const setupSocketListeners = () => {
    // Create listener functions and store references for cleanup
    const onTitleUpdated = (data) => {
      logger.log('[ChatPage] Conversation title updated:', data);
      const { conversationId: convId, title } = data;

      // Update conversation title in the store
      // This does NOT affect socket connection (still uses conversationId)
      useChatStore.setState((currentState) => ({
        conversations: currentState.conversations.map((conv) =>
          conv.id === convId ? { ...conv, title } : conv
        ),
        currentConversation:
          currentState.currentConversation?.id === convId
            ? { ...currentState.currentConversation, title }
            : currentState.currentConversation,
      }));
    };

    const onUserMessage = async (data) => {
      // When user sends a message, stop any previous audio and clear session
      audioQueueRef.current = [];
      isProcessingAudioRef.current = false;
      audioManager.stop();
      useChatStore.getState().setAudioPlaying(false);
      currentSessionIdRef.current = null; // Clear previous session

      // Auto-set conversation title from first user message
      const { message, conversationId: msgConvId } = data || {};

      // Use ref and store to get current values (avoid closure issues)
      if (
        message &&
        msgConvId &&
        msgConvId === currentConversationIdRef.current
      ) {
        const store = useChatStore.getState();
        const { messages: storeMessages, currentConversation: conv } = store;

        // Check if this is the first user message (only the just-sent message exists)
        // Note: The message is already in the store via optimistic update, so we check <= 1
        const userMessages = storeMessages.filter((m) => m.role === 'user');
        const content = message.content?.trim() || '';

        logger.log('[ChatPage] Title auto-update check:', {
          userMessageCount: userMessages.length,
          contentLength: content.length,
          hasConv: !!conv,
          convTitle: conv?.title,
        });

        if (userMessages.length <= 1 && content && conv) {
          // Use message as title if it's long enough (>= 10 chars)
          // Otherwise keep the default title
          if (content.length >= 10) {
            // Truncate to 50 chars if needed
            const newTitle =
              content.length > 50 ? `${content.substring(0, 47)}...` : content;

            try {
              await store.updateConversation(conv.id, newTitle);
              logger.log(
                '[ChatPage] Auto-updated conversation title to:',
                newTitle
              );
            } catch (err) {
              logger.error(
                '[ChatPage] Failed to update conversation title:',
                err
              );
            }
          } else {
            logger.log(
              '[ChatPage] Skipping title update - content too short:',
              content.length
            );
          }
        } else {
          logger.log(
            '[ChatPage] Skipping title update - not first message or missing conv'
          );
        }
      }
    };

    const onMessageStream = (data) => {
      const { conversationId: msgConvId, chunk, messageId, sessionId } = data;

      // Track session ID for interrupt support
      if (sessionId && !currentSessionIdRef.current) {
        currentSessionIdRef.current = sessionId;
      }

      // Only process if it's for the current conversation
      if (msgConvId === currentConversationIdRef.current) {
        const storeState = useChatStore.getState();

        // If this is the first chunk, replace thinking message with streaming message
        if (!storeState.isStreaming) {
          // Remove "Thinking..." messages and start streaming in one update
          useChatStore.setState((currentState) => {
            const messagesWithoutThinking = currentState.messages.filter(
              (msg) => !msg.isThinking
            );

            // Create new streaming message
            const streamingMessage = {
              id: messageId,
              role: 'assistant',
              content: chunk,
              createdAt: new Date().toISOString(),
              isStreaming: true,
            };

            return {
              messages: [...messagesWithoutThinking, streamingMessage],
              streamingMessage,
              isStreaming: true,
            };
          });
        } else {
          // Append the chunk to existing streaming message
          appendStreamingContent(chunk);
        }
      }
    };

    const onMessageComplete = (data) => {
      const { conversationId: msgConvId, message } = data;

      // Only process if it's for the current conversation
      if (msgConvId === currentConversationIdRef.current) {
        // Complete the streaming message
        completeStreamingMessage(message);
        // Note: Don't clear session ID - it's needed for interrupt support
        // Multi-turn continuity now uses conversationId as sessionId
      }
    };

    const onError = (data) => {
      logger.error('[ChatPage] Socket error:', data);
      showErrorToast(data.message || 'An error occurred');

      // Remove thinking messages on error
      useChatStore.setState((currentState) => ({
        messages: currentState.messages.filter((msg) => !msg.isThinking),
      }));

      cancelStreaming();
      // Note: Don't clear session ID - multi-turn uses conversationId as sessionId
    };

    const onDisconnect = (reason) => {
      logger.error('[ChatPage] Socket disconnected:', reason);
      setSocketConnected(false);
      showErrorToast('Chat connection lost. Reconnecting...');
    };

    const onConnect = () => {
      setSocketConnected(true);
    };

    /**
     * AUDIO HANDLERS
     */
    const onAudioBatch = async (data) => {
      logger.log('[ChatPage] Audio batch received:', {
        conversationId: data.conversationId,
        frameCount: data.frames?.length,
        currentConv: currentConversationIdRef.current,
      });

      const { conversationId: msgConvId, frames } = data;

      if (msgConvId !== currentConversationIdRef.current) {
        logger.log('[ChatPage] Skipping audio - wrong conversation');
        return;
      }
      if (!frames || !frames.length) {
        logger.log('[ChatPage] Skipping audio - no frames');
        return;
      }

      logger.log('[ChatPage] Processing audio batch:', frames.length, 'frames');

      // Set audio playing state on first batch
      if (!audioManager.isPlaying) {
        setAudioPlaying(true);
      }

      // Add to queue and process sequentially (ensures correct order!)
      audioQueueRef.current.push(frames);
      processAudioQueue();
    };

    const onAudioComplete = async (data) => {
      const { conversationId: msgConvId } = data;

      if (msgConvId !== currentConversationIdRef.current) return;

      try {
        // Wait for all queued batches to finish processing
        const maxWaitTime = 5000;
        const startWait = Date.now();

        while (
          (audioQueueRef.current.length > 0 || isProcessingAudioRef.current) &&
          Date.now() - startWait < maxWaitTime
        ) {
          // eslint-disable-next-line
          await new Promise((resolve) => setTimeout(resolve, 50));
        }

        // Wait for all audio to finish playing
        await audioManager.flushRemaining();

        // Audio finished playing
        setAudioPlaying(false);
      } catch (err) {
        console.error('[ChatPage] Failed to complete audio playback:', err);
        setAudioPlaying(false);
      }
    };

    const onAudioError = (data) => {
      const { conversationId: msgConvId, error } = data;
      if (msgConvId !== currentConversationIdRef.current) return;

      logger.error('[ChatPage] Audio stream error:', error);
      showErrorToast('Failed to generate audio');

      audioManager.stop();
      setAudioPlaying(false);
    };

    // Store listener references for cleanup
    listenersRef.current = {
      onTitleUpdated,
      onUserMessage,
      onMessageStream,
      onMessageComplete,
      onError,
      onDisconnect,
      onConnect,
      onAudioBatch,
      onAudioComplete,
      onAudioError,
    };

    // Register all listeners
    socketManager.on('conversation:title-updated', onTitleUpdated);
    socketManager.on('message:user', onUserMessage);
    socketManager.on('message:stream', onMessageStream);
    socketManager.on('message:complete', onMessageComplete);
    socketManager.on('error', onError);
    socketManager.on('message:audio:batch', onAudioBatch);
    socketManager.on('message:audio:complete', onAudioComplete);
    socketManager.on('message:audio:error', onAudioError);
    socketManager.on('disconnect', onDisconnect);
    socketManager.on('connect', onConnect);
  };

  /**
   * Initialize: Connect to Socket.IO, fetch conversations and RAG profiles
   */
  useEffect(() => {
    // Initialize socket connection if not already connected
    const initializeSocket = async () => {
      // Check if already connected
      if (socketManager.getConnectionStatus()) {
        setupSocketListeners();
        setSocketConnected(true);
        return;
      }

      try {
        // Note: Socket.IO will use cookies for auth automatically
        await socketManager.connect();

        // Socket object is now initialized (even if not fully connected yet)
        // Register listeners immediately after connect() call
        setupSocketListeners();

        // Only update state if component is still mounted
        if (!isMountedRef.current) {
          return;
        }

        setSocketConnected(true);
      } catch (error) {
        logger.error('[ChatPage] Failed to connect socket:', error);

        // Only show error if component is still mounted
        if (isMountedRef.current) {
          showErrorToast('Failed to connect to chat service');
        }
      }
    };

    // Fetch initial data in parallel for faster initialization
    // All three operations are independent and can run concurrently
    Promise.all([
      fetchConversations().catch((error) => {
        showErrorToast(t('chat.errors.fetchConversationsFailed'));
        logger.error('Failed to fetch conversations:', error);
      }),
      fetchRagProfiles().catch((error) => {
        logger.error('Failed to fetch RAG profiles:', error);
        // Don't show error toast here, as profiles are optional
      }),
      initializeSocket(),
    ]);

    // Cleanup on unmount - disconnect socket when leaving chat page
    // Socket only needed on chat page, not on dashboard or other pages
    return () => {
      // Mark component as unmounted to prevent state updates
      isMountedRef.current = false;

      // IMPORTANT: Remove all listeners BEFORE disconnecting
      // This prevents the disconnect/error listeners from showing toasts during intentional cleanup
      const listeners = listenersRef.current;
      if (listeners) {
        socketManager.off(
          'conversation:title-updated',
          listeners.onTitleUpdated
        );
        socketManager.off('message:user', listeners.onUserMessage);
        socketManager.off('message:stream', listeners.onMessageStream);
        socketManager.off('message:complete', listeners.onMessageComplete);
        socketManager.off('error', listeners.onError);
        socketManager.off('disconnect', listeners.onDisconnect);
        socketManager.off('connect', listeners.onConnect);
      }

      // Now safe to disconnect without triggering error toasts
      // The disconnect() method will also clear any pending connection timeouts
      socketManager.disconnect();
    };
  }, []);

  /**
   * Stop generating AI response
   * Memoized to prevent re-creation on every render
   */
  const handleStopGenerating = useCallback(async () => {
    // Try session interrupt first (preferred method)
    const sessionId = currentSessionIdRef.current;
    if (sessionId) {
      try {
        await socketManager.interruptSession(sessionId);
      } catch (err) {
        logger.error('[ChatPage] Failed to interrupt session:', err);
      }
    } else {
      // Fallback to old method if no session ID
      const { streamingMessage } = useChatStore.getState();
      if (streamingMessage && currentConversation) {
        socketManager.stopStreaming(
          currentConversation.id,
          streamingMessage.id
        );
      }
    }

    // Cancel streaming on frontend
    cancelStreaming();
    // Clear session ID
    currentSessionIdRef.current = null;
    // Stop audio
    audioManager.stop();
    useChatStore.getState().setAudioPlaying(false);
    showSuccessToast('Response generation stopped');
  }, [currentConversation, cancelStreaming, showSuccessToast]);

  /**
   * Handle conversation selection from URL params
   */
  useEffect(() => {
    const handleConversationChange = async () => {
      // Update ref for socket listeners
      currentConversationIdRef.current = conversationId;

      // Reset room joined status when conversation changes
      setRoomJoined(false);

      if (conversationId) {
        // Only fetch conversation and messages if it's different from current
        if (conversationId !== currentConversation?.id) {
          try {
            // Fetch conversation details
            const conversation = await getConversation(conversationId);
            setCurrentConversation(conversation);

            // Fetch messages for this conversation
            await fetchMessages(conversationId);
          } catch (error) {
            showErrorToast(t('chat.errors.fetchConversationFailed'));
            logger.error('Failed to load conversation:', error);
            navigate('/chat');
            return;
          }
        }

        // Always join socket room when conversationId changes or socket reconnects
        // Check ACTUAL socket status, not just state (state may be stale after navigation)
        const actualSocketStatus = socketManager.getConnectionStatus();

        if (actualSocketStatus) {
          try {
            await socketManager.joinConversation(conversationId);
            setRoomJoined(true); // Mark room as joined
            setSocketConnected(true); // Update state to match reality
          } catch (error) {
            logger.error('[ChatPage] Failed to join conversation room:', error);
            setRoomJoined(false);
          }
        } else {
          setRoomJoined(false);
        }
      } else {
        // No conversation selected
        setCurrentConversation(null);
        currentConversationIdRef.current = null;
        setRoomJoined(false);
      }
    };

    handleConversationChange();

    // Cleanup: leave conversation room when switching
    return () => {
      // Only try to leave if we have a conversationId and socket is still connected
      if (conversationId && socketManager.getConnectionStatus()) {
        setRoomJoined(false); // Mark room as left
        socketManager.leaveConversation(conversationId).catch(() => {
          // Don't throw error - this is not critical for UX
        });
      }
    };
  }, [conversationId, socketConnected]);

  /**
   * Open executive selector modal instead of directly creating conversation
   * Memoized to prevent re-creation on every render
   */
  const handleCreateConversation = useCallback(() => {
    // Clear previously selected profile when opening selector
    setSelectedProfile(null);
    setExecutiveSelectorOpen(true);
  }, [setSelectedProfile]);

  /**
   * Toggle sidebar (mobile)
   * Memoized to prevent re-creation on every render
   */
  const handleToggleSidebar = useCallback(() => {
    toggleSidebar();
  }, [toggleSidebar]);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      {/* Executive Selector Modal - uses Zustand directly */}
      <ExecutiveSelector
        isOpen={executiveSelectorOpen}
        onClose={() => setExecutiveSelectorOpen(false)}
      />

      <div className="flex h-[calc(100vh-64px)]">
        {/* Unified Sidebar with Chat Content */}
        <Sidebar>
          <ChatSidebarContent />
        </Sidebar>

        {/* Overlay for mobile sidebar */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
            onClick={handleToggleSidebar}
          />
        )}

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col bg-white">
          {currentConversation ? (
            <>
              {/* Header - uses Zustand directly */}
              <ConversationHeader
                onToggleSidebar={handleToggleSidebar}
                showMenuButton
              />

              {/* Messages */}
              <MessageList
                messages={messages}
                isLoading={messagesLoading}
                hasMore={messagesPagination.hasMore}
                onLoadMore={loadMoreMessages}
                emptyMessage={t('chat.startConversation')}
              />

              {/* Stop Generating Button */}
              {isStreaming && (
                <div className="px-4 py-2 bg-gray-50 border-t border-gray-200">
                  <button
                    onClick={handleStopGenerating}
                    className="w-full px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                  >
                    <svg
                      className="w-4 h-4"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <rect x="6" y="6" width="8" height="8" rx="1" />
                    </svg>
                    Stop Generating
                  </button>
                </div>
              )}

              {/* Input - uses Zustand directly, pass onStopAudio for TTS */}
              <MessageInput
                onStopAudio={handleStopAudio}
                currentSessionId={currentSessionIdRef.current}
              />
            </>
          ) : (
            // Empty state - no conversation selected
            <EmptyState
              onCreateConversation={handleCreateConversation}
              showSuggestions
            />
          )}
        </div>
      </div>
    </div>
  );
}

// Export memoized version to prevent unnecessary re-renders
export const ChatPage = memo(ChatPageComponent);
