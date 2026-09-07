import { useState, useRef, useEffect, useCallback, memo, useMemo } from 'react';
import { Send, Loader2, Settings, Mic, MicOff, Square } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useChatStore } from '../../store/chatStore';
import { useUIStore } from '../../store/uiStore';
import { socketManager } from '../../services/socket';
import { PathSelector } from './PathSelector';
import { TTSToggle } from './TTSToggle';
import { useVoiceInput } from '../../hooks/useVoiceInput';
import logger from '../../utils/logger';

/**
 * MessageInput Component
 *
 * Input area for sending messages
 *
 * Features:
 * - Auto-expanding textarea
 * - Enter to send, Shift+Enter for new line
 * - Character limit indicator
 * - Disabled state while sending
 * - Loading indicator
 * - Keyboard shortcuts
 * - Direct Zustand store access (no prop drilling)
 * - Optimized with useCallback and useMemo to prevent unnecessary re-renders
 */
function MessageInputComponent({
  maxLength = 2000,
  onStopAudio,
  currentSessionId,
}) {
  const { t } = useTranslation();

  // Zustand stores (optimized with selectors to prevent unnecessary re-renders)
  const currentConversation = useChatStore(
    (state) => state.currentConversation
  );
  const isSendingMessage = useChatStore((state) => state.isSendingMessage);
  const isStreaming = useChatStore((state) => state.isStreaming);
  const selectedProfile = useChatStore((state) => state.selectedProfile);
  const conversationProfiles = useChatStore(
    (state) => state.conversationProfiles
  );
  const ttsEnabled = useChatStore((state) => state.ttsEnabled);

  const showErrorToast = useUIStore((state) => state.showErrorToast);

  // Check socket connection
  const socketConnected = socketManager.getConnectionStatus();
  const [input, setInput] = useState('');
  const [isComposing, setIsComposing] = useState(false);
  const [forcePath, setForcePath] = useState(''); // LLM processing path: '', 'fast', 'standard', 'agentic'
  const [isPathSelectorOpen, setIsPathSelectorOpen] = useState(false);
  const textareaRef = useRef(null);

  // Get current language from localStorage (used by TTS and STT)
  const currentLanguage = localStorage.getItem('language') || 'en';

  // Voice input hook
  const {
    isRecording,
    isConnecting,
    error: voiceError,
    startRecording,
    stopRecording,
  } = useVoiceInput({
    language: currentLanguage,
    onTranscript: (transcript) => {
      // Append transcript to input
      setInput((prev) => {
        const separator = prev.trim() ? ' ' : '';
        return prev + separator + transcript;
      });
    },
  });

  // Memoize calculated values to prevent recalculation on every render
  const charCount = input.length;
  const isNearLimit = useMemo(
    () => charCount > maxLength * 0.8,
    [charCount, maxLength]
  );
  const isOverLimit = useMemo(
    () => charCount > maxLength,
    [charCount, maxLength]
  );

  /**
   * Auto-resize textarea based on content
   */
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  }, [input]);

  /**
   * Handle form submission
   * Memoized to prevent re-creation on every render (critical for typing performance)
   */
  const handleSubmit = useCallback(
    async (e) => {
      e?.preventDefault();

      const trimmedInput = input.trim();
      const disabled = isSendingMessage || isStreaming || !socketConnected;

      if (!trimmedInput || disabled || isOverLimit || isComposing) {
        return;
      }

      if (!currentConversation) {
        showErrorToast(t('chat.errors.noConversationSelected'));
        return;
      }

      if (!socketConnected) {
        showErrorToast('Not connected to chat service');
        return;
      }

      try {
        // Interrupt any ongoing response before sending new message
        if (currentSessionId) {
          try {
            logger.log(
              '[MessageInput] Interrupting previous session:',
              currentSessionId
            );
            await socketManager.interruptSession(currentSessionId);
          } catch (interruptError) {
            // Don't block message sending if interrupt fails
            logger.error(
              '[MessageInput] Failed to interrupt session (continuing anyway):',
              interruptError
            );
          }
        }

        // Stop audio playback immediately
        if (onStopAudio) {
          onStopAudio();
        }

        // Add user message optimistically
        const optimisticUserMessage = {
          id: `temp-${Date.now()}`,
          role: 'user',
          content: trimmedInput,
          createdAt: new Date().toISOString(),
          isOptimistic: true,
        };

        // Add "Thinking..." placeholder immediately after user message
        const thinkingMessage = {
          id: `thinking-${Date.now()}`,
          role: 'assistant',
          content: '',
          createdAt: new Date().toISOString(),
          isThinking: true,
        };

        // Add both messages immediately (user message + thinking indicator)
        useChatStore.setState((state) => ({
          messages: [...state.messages, optimisticUserMessage, thinkingMessage],
          isSendingMessage: true,
        }));

        // Get profile for this conversation
        const conversationProfileId =
          conversationProfiles[currentConversation.id];
        const profileToUse = conversationProfileId || selectedProfile?.id;

        // Get current language preference from i18n

        // Build RAG options with profile, language preference, force path, and TTS settings
        // Use conversationId as sessionId for multi-turn conversation continuity
        const ragOptions = {
          ...(profileToUse && { profileId: profileToUse }),
          language: currentLanguage,
          ...(forcePath && { forcePath }), // Add force path if selected
          sessionId: currentConversation.id, // Use conversation ID for LangGraph threading
          // TTS settings - voice profile defaults to selected executive if not set
          ...(ttsEnabled && {
            ttsEnabled: true,
            voiceProfileId: profileToUse, // Use selected executive profile for TTS
          }),
        };

        logger.log(
          '[MessageInput] Sending with profile, language, path, and TTS:',
          {
            conversationProfileId,
            currentlySelectedProfile: selectedProfile?.id,
            profileUsed: profileToUse,
            language: currentLanguage,
            forcePath: forcePath || 'auto',
            ttsEnabled,
            voiceProfileIdToUse: profileToUse,
            ragOptions,
            conversationId: currentConversation.id,
          }
        );

        // Send via Socket.IO
        const response = await socketManager.sendMessage(
          currentConversation.id,
          trimmedInput,
          ragOptions
        );

        logger.log('[MessageInput] Message sent via socket:', response);

        // Replace optimistic message with real user message IN PLACE (preserve order)
        const { userMessage } = response;
        useChatStore.setState((state) => ({
          messages: state.messages.map((msg) =>
            msg.isOptimistic ? userMessage : msg
          ),
          isSendingMessage: false,
        }));

        // Clear input and reset height
        setInput('');
        if (textareaRef.current) {
          textareaRef.current.style.height = 'auto';
        }

        // Streaming events will come from 'message:stream' listener
        // The thinking message will be replaced when first chunk arrives
      } catch (error) {
        logger.error('[MessageInput] Failed to send message:', error);
        showErrorToast(error.message || t('chat.errors.sendMessageFailed'));

        // Remove optimistic message and thinking indicator on error
        useChatStore.setState((state) => ({
          messages: state.messages.filter(
            (msg) => !msg.isOptimistic && !msg.isThinking
          ),
          isSendingMessage: false,
        }));
      }
    },
    [
      input,
      isSendingMessage,
      isStreaming,
      socketConnected,
      isOverLimit,
      isComposing,
      currentConversation,
      currentSessionId,
      selectedProfile,
      conversationProfiles,
      forcePath,
      ttsEnabled,
      onStopAudio,
      t,
      showErrorToast,
    ]
  );

  /**
   * Handle keyboard shortcuts
   * - Enter: Send message (if not composing)
   * - Shift+Enter: New line
   * Memoized to prevent re-creation on every render (critical for typing performance)
   */
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [isComposing, handleSubmit]
  );

  /**
   * Handle input change
   * Memoized to prevent re-creation on every render (critical for typing performance)
   */
  const handleChange = useCallback(
    (e) => {
      const { value } = e.target;
      if (value.length <= maxLength) {
        setInput(value);
      }
    },
    [maxLength]
  );

  /**
   * Handle IME composition (for Asian languages)
   * Memoized to prevent re-creation on every render
   */
  const handleCompositionStart = useCallback(() => {
    setIsComposing(true);
  }, []);

  const handleCompositionEnd = useCallback(() => {
    setIsComposing(false);
  }, []);

  // Handler for closing path selector
  const handleClosePathSelector = useCallback(() => {
    setIsPathSelectorOpen(false);
  }, []);

  // Voice input handlers
  const handleVoiceToggle = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  /**
   * Handle Stop button - interrupt current AI response
   */
  const handleStop = useCallback(() => {
    console.log('[MessageInput] Stop button clicked - interrupting response');

    // Stop audio playback
    if (onStopAudio) {
      onStopAudio();
    }

    // Emit interrupt event to backend with sessionId
    if (currentSessionId) {
      socketManager.interruptSession(currentSessionId).catch((err) => {
        logger.error('[MessageInput] Failed to interrupt session:', err);
      });
    }

    // Update store state
    useChatStore.setState((state) => ({
      isStreaming: false,
      isSendingMessage: false,
      audioPlaying: false,
      messages: state.messages.filter((msg) => !msg.isThinking),
    }));
  }, [currentSessionId, onStopAudio]);

  // Show voice error as toast
  useEffect(() => {
    if (voiceError) {
      showErrorToast(`Voice input error: ${voiceError}`);
    }
  }, [voiceError, showErrorToast]);

  const disabled = isSendingMessage || isStreaming || !socketConnected;
  const isProcessing = isSendingMessage || isStreaming;
  const placeholder = !socketConnected
    ? 'Connecting to chat service...'
    : t('chat.messagePlaceholder');

  // Get path display info - memoized to prevent recalculation on every render
  const pathDisplay = useMemo(() => {
    switch (forcePath) {
      case 'fast':
        return { icon: '⚡', name: 'Fast', color: 'text-orange-600' };
      case 'standard':
        return { icon: '🎯', name: 'Standard', color: 'text-blue-600' };
      case 'agentic':
        return { icon: '🧠', name: 'Agentic', color: 'text-pink-600' };
      default:
        return { icon: '🤖', name: 'Auto', color: 'text-purple-600' };
    }
  }, [forcePath]);

  return (
    <>
      {/* Path Selector Modal */}
      <PathSelector
        isOpen={isPathSelectorOpen}
        onClose={handleClosePathSelector}
        selectedPath={forcePath}
        onSelectPath={setForcePath}
      />

      <form onSubmit={handleSubmit} className="border-t bg-white p-4">
        <div className="max-w-4xl mx-auto">
          {/* Query Path & TTS Toggle Row */}
          <div className="mb-3 flex gap-3">
            {/* Query Path Button */}
            <button
              type="button"
              onClick={() => setIsPathSelectorOpen(true)}
              disabled={disabled}
              className="flex-1 flex items-center justify-between gap-3 p-3 bg-gray-50 rounded-xl border border-gray-200
                         hover:bg-gray-100 hover:border-gray-300 transition-all duration-200
                         disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Select query processing path"
            >
              <div className="flex items-center gap-2">
                <Settings className="w-4 h-4 text-gray-600" />
                <span className="text-sm font-medium text-gray-700">
                  Query Path:
                </span>
                <span className={`text-sm font-semibold ${pathDisplay.color}`}>
                  {pathDisplay.icon} {pathDisplay.name}
                </span>
              </div>
              <span className="text-xs text-gray-500">Click to change</span>
            </button>

            {/* TTS Toggle */}
            <TTSToggle disabled={disabled} onStopAudio={onStopAudio} />
          </div>

          <div className="flex gap-3 items-end">
            {/* Voice Input Button */}
            <button
              type="button"
              onClick={handleVoiceToggle}
              disabled={disabled || isConnecting}
              className={`
                flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center
                transition-all duration-200
                ${
                  isRecording
                    ? 'bg-red-500 text-white hover:bg-red-600 animate-pulse'
                    : disabled || isConnecting
                      ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200 active:scale-95'
                }
              `}
              aria-label={isRecording ? 'Stop recording' : 'Start voice input'}
              title={isRecording ? 'Stop recording' : 'Start voice input'}
            >
              {isConnecting ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : isRecording ? (
                <MicOff className="w-5 h-5" />
              ) : (
                <Mic className="w-5 h-5" />
              )}
            </button>

            {/* Textarea */}
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleChange}
                onKeyDown={handleKeyDown}
                onCompositionStart={handleCompositionStart}
                onCompositionEnd={handleCompositionEnd}
                placeholder={placeholder}
                disabled={disabled}
                rows={1}
                className={`
                w-full resize-none rounded-xl border-2 px-4 py-3 pr-12
                focus:outline-none focus:ring-2 focus:ring-primary focus:ring-opacity-50
                disabled:bg-gray-100 disabled:cursor-not-allowed
                transition-all
                ${isOverLimit ? 'border-red-400 focus:border-red-400' : 'border-gray-200 focus:border-primary'}
              `}
                style={{
                  minHeight: '48px',
                  maxHeight: '150px',
                }}
                aria-label={t('chat.messagePlaceholder')}
              />

              {/* Character Count */}
              {(isNearLimit || isOverLimit) && (
                <div
                  className={`absolute bottom-2 right-2 text-xs ${
                    isOverLimit ? 'text-red-500' : 'text-gray-400'
                  }`}
                >
                  {charCount}/{maxLength}
                </div>
              )}
            </div>

            {/* Send / Stop Button */}
            {isProcessing ? (
              /* Stop Button - shown during processing */
              <button
                type="button"
                onClick={handleStop}
                className="
                  flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center
                  transition-all duration-200
                  bg-red-500 text-white hover:bg-red-600 active:scale-95
                "
                aria-label="Stop AI response"
                title="Stop AI response"
              >
                <Square className="w-5 h-5 fill-current" />
              </button>
            ) : (
              /* Send Button - shown when ready to send */
              <button
                type="submit"
                disabled={!input.trim() || disabled || isOverLimit}
                className={`
                  flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center
                  transition-all duration-200
                  ${
                    !input.trim() || disabled || isOverLimit
                      ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                      : 'bg-primary text-white hover:bg-primary-dark active:scale-95'
                  }
                `}
                aria-label={t('chat.sendMessage')}
                title={t('chat.sendMessage')}
              >
                {disabled ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </button>
            )}
          </div>

          {/* Helper Text */}
          <div className="flex justify-between items-center mt-2 px-1">
            <p className="text-xs text-gray-400">{t('chat.enterToSend')}</p>

            {disabled && (
              <p className="text-xs text-gray-500 italic">
                {t('chat.aiTyping')}
              </p>
            )}
          </div>
        </div>
      </form>
    </>
  );
}

// Export memoized version to prevent unnecessary re-renders
// This is critical for typing performance
export const MessageInput = memo(MessageInputComponent);
