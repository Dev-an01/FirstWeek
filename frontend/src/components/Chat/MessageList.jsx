import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageBubble } from './MessageBubble';
import { Button } from '../ui/Button';
import { useChatStore } from '../../store/chatStore';

/**
 * MessageList Component
 *
 * Scrollable container for chat messages
 *
 * Features:
 * - Auto-scroll to latest message
 * - Load more messages (pagination)
 * - Loading states
 * - Empty state for new conversations
 * - Optimistic UI updates
 * - Direct Zustand store access (no prop drilling)
 */
export function MessageList() {
  const { t } = useTranslation();

  // Zustand store (optimized with selectors to prevent unnecessary re-renders)
  const messages = useChatStore((state) => state.messages);
  const messagesLoading = useChatStore((state) => state.messagesLoading);
  const messagesPagination = useChatStore((state) => state.messagesPagination);
  const loadMoreMessages = useChatStore((state) => state.loadMoreMessages);
  const isStreaming = useChatStore((state) => state.isStreaming);
  const streamingMessage = useChatStore((state) => state.streamingMessage);
  const isSendingMessage = useChatStore((state) => state.isSendingMessage);

  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const prevMessagesLengthRef = useRef(messages.length);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);

  /**
   * Auto-scroll to bottom when new messages arrive
   * Only scroll if user was already at bottom
   */
  useEffect(() => {
    // Check if new messages were added
    if (messages.length > prevMessagesLengthRef.current) {
      const container = messagesContainerRef.current;
      if (container) {
        // Check if user was near bottom (within 150px)
        const scrollBottom =
          container.scrollHeight - container.scrollTop - container.clientHeight;
        const isNearBottom = scrollBottom < 150;

        setShouldAutoScroll(isNearBottom);

        if (isNearBottom) {
          // Smooth scroll for new messages (not streaming yet)
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
      }
    }

    prevMessagesLengthRef.current = messages.length;
  }, [messages]);

  /**
   * Auto-scroll during streaming
   * Continuously scroll to bottom while message is being streamed
   */
  useEffect(() => {
    if (isStreaming && shouldAutoScroll && streamingMessage) {
      // Instant scroll to bottom during streaming (no smooth animation for better responsiveness)
      const scrollToBottom = () => {
        const container = messagesContainerRef.current;
        if (container) {
          // Use scrollTop for instant scroll during streaming
          container.scrollTop = container.scrollHeight;
        }
      };

      // Scroll immediately on every content change
      scrollToBottom();
    }
  }, [isStreaming, streamingMessage?.content, shouldAutoScroll]);

  /**
   * Scroll to bottom on initial load
   */
  useEffect(() => {
    if (messages.length > 0 && !messagesLoading) {
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
      }, 100);
    }
  }, [messagesLoading, messages.length]);

  /**
   * Force scroll to bottom when user sends a message (presses Enter)
   * This ensures the chat immediately scrolls down to show the user's message
   * and enables auto-scroll for the upcoming streaming response
   */
  useEffect(() => {
    if (isSendingMessage) {
      // Immediately scroll to bottom
      const container = messagesContainerRef.current;
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
      // Enable auto-scroll for the upcoming response
      setShouldAutoScroll(true);
    }
  }, [isSendingMessage]);

  /**
   * Handle scroll events
   * - Load more messages when scrolled to top
   * - Detect if user scrolled away from bottom (disable auto-scroll)
   */
  const handleScroll = () => {
    const container = messagesContainerRef.current;
    if (!container) return;

    // Load more at top
    if (
      container.scrollTop === 0 &&
      messagesPagination.hasMore &&
      !messagesLoading
    ) {
      loadMoreMessages();
    }

    // Check if user is near bottom (within 150px to be more forgiving)
    const scrollBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const isNearBottom = scrollBottom < 150;

    // Update auto-scroll state
    // If user manually scrolls up (scrollBottom > 150), disable auto-scroll
    // If user scrolls back to bottom (scrollBottom < 150), re-enable auto-scroll
    setShouldAutoScroll(isNearBottom);
  };

  // Loading skeleton
  if (messagesLoading && messages.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-200 animate-pulse" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-gray-200 rounded animate-pulse w-3/4" />
              <div className="h-4 bg-gray-200 rounded animate-pulse w-1/2" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Empty state
  if (!messagesLoading && messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
            <svg
              className="w-8 h-8 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
          </div>
          <p className="text-gray-600 text-lg">{t('chat.noMessages')}</p>
          <p className="text-gray-400 text-sm mt-2">
            {t('chat.startConversation')}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={messagesContainerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto scroll-smooth"
    >
      <div className="max-w-4xl mx-auto py-4 space-y-6">
        {/* Load More Button */}
        {messagesPagination.hasMore && !messagesLoading && (
          <div className="flex justify-center pb-4">
            <Button
              onClick={loadMoreMessages}
              variant="outline"
              className="text-sm"
            >
              {t('chat.loadMore')}
            </Button>
          </div>
        )}

        {/* Loading indicator at top */}
        {messagesLoading && messagesPagination.hasMore && (
          <div className="flex justify-center pb-4">
            <div className="animate-spin rounded-full h-6 w-6 border-2 border-primary border-t-transparent" />
          </div>
        )}

        {/* Messages */}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
