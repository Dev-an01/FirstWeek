import { useState, useCallback, memo } from 'react';
import PropTypes from 'prop-types';
import { User, Bot, Copy, Check, Clock } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAuthStore } from '../../store/authStore';

/**
 * MessageBubble Component
 *
 * Displays individual messages with different styles for user/assistant
 *
 * Features:
 * - Different styling for user vs assistant messages
 * - Avatar display
 * - Copy message functionality
 * - Source citations for assistant messages
 * - Processing time indicator
 * - Timestamp display
 *
 * Memoized to prevent unnecessary re-renders when message props haven't changed
 */
function MessageBubbleComponent({ message }) {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const [copied, setCopied] = useState(false);

  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';
  const { isOptimistic } = message;
  const { isStreaming } = message;
  const { isThinking } = message;

  /**
   * Copy message content to clipboard
   */
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy message:', error);
    }
  }, [message.content]);

  /**
   * Format timestamp
   */
  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} w-full`}>
      <div
        className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} ${
          isOptimistic ? 'opacity-60' : 'opacity-100'
        } max-w-3xl w-full px-4`}
      >
        {/* Avatar */}
        <div className="flex-shrink-0">
          {isUser ? (
            <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
              {user?.profilePic ? (
                <img
                  src={user.profilePic}
                  alt={user.username}
                  className="w-full h-full rounded-full object-cover"
                />
              ) : (
                <User className="w-5 h-5 text-white" />
              )}
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
          )}
        </div>

        {/* Message Content */}
        <div
          className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} flex-1 min-w-0`}
        >
          {/* Message Bubble */}
          <div
            className={`rounded-2xl px-4 py-3 ${
              isUser
                ? 'bg-primary text-white rounded-tr-sm'
                : 'bg-gray-100 text-gray-900 rounded-tl-sm'
            }`}
          >
            {/* Thinking Indicator */}
            {isThinking ? (
              <div className="flex items-center gap-2 text-gray-600">
                <div className="flex gap-1">
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '0ms' }}
                  />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '150ms' }}
                  />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '300ms' }}
                  />
                </div>
                <span className="text-sm italic">Thinking...</span>
              </div>
            ) : (
              <>
                {/* Message Text */}
                {isUser ? (
                  // User messages: plain text (no markdown)
                  <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                    {message.content}
                  </p>
                ) : (
                  // Assistant messages: rendered markdown
                  <div className="prose prose-sm max-w-none text-sm leading-relaxed">
                    {/* eslint-disable react/no-unstable-nested-components, react/jsx-props-no-spreading, jsx-a11y/heading-has-content, jsx-a11y/anchor-has-content */}
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        // Headings
                        h1: ({ node, ...props }) => (
                          <h1
                            className="text-lg font-bold mt-4 mb-2 text-gray-900"
                            {...props}
                          />
                        ),
                        h2: ({ node, ...props }) => (
                          <h2
                            className="text-base font-bold mt-3 mb-2 text-gray-900"
                            {...props}
                          />
                        ),
                        h3: ({ node, ...props }) => (
                          <h3
                            className="text-sm font-bold mt-2 mb-1 text-gray-900"
                            {...props}
                          />
                        ),
                        // Paragraphs
                        p: ({ node, ...props }) => (
                          <p
                            className="mb-2 last:mb-0 text-gray-800"
                            {...props}
                          />
                        ),
                        // Lists
                        ul: ({ node, ...props }) => (
                          <ul
                            className="list-disc list-inside mb-2 space-y-1 text-gray-800"
                            {...props}
                          />
                        ),
                        ol: ({ node, ...props }) => (
                          <ol
                            className="list-decimal list-inside mb-2 space-y-1 text-gray-800"
                            {...props}
                          />
                        ),
                        li: ({ node, ...props }) => (
                          <li className="text-gray-800" {...props} />
                        ),
                        // Links
                        a: ({ node, ...props }) => (
                          <a
                            className="text-blue-600 hover:text-blue-800 underline"
                            target="_blank"
                            rel="noopener noreferrer"
                            {...props}
                          />
                        ),
                        // Code blocks
                        code: ({ node, inline, ...props }) =>
                          inline ? (
                            <code
                              className="bg-gray-200 text-red-600 px-1.5 py-0.5 rounded text-xs font-mono"
                              {...props}
                            />
                          ) : (
                            <code
                              className="block bg-gray-800 text-gray-100 p-3 rounded-lg overflow-x-auto text-xs font-mono my-2"
                              {...props}
                            />
                          ),
                        pre: ({ node, ...props }) => (
                          <pre
                            className="bg-gray-800 rounded-lg overflow-x-auto my-2"
                            {...props}
                          />
                        ),
                        // Blockquotes
                        blockquote: ({ node, ...props }) => (
                          <blockquote
                            className="border-l-4 border-gray-300 pl-4 italic text-gray-700 my-2"
                            {...props}
                          />
                        ),
                        // Tables
                        table: ({ node, ...props }) => (
                          <table
                            className="min-w-full border-collapse border border-gray-300 my-2"
                            {...props}
                          />
                        ),
                        th: ({ node, ...props }) => (
                          <th
                            className="border border-gray-300 bg-gray-100 px-2 py-1 font-semibold text-left"
                            {...props}
                          />
                        ),
                        td: ({ node, ...props }) => (
                          <td
                            className="border border-gray-300 px-2 py-1"
                            {...props}
                          />
                        ),
                        // Strong/Bold
                        strong: ({ node, ...props }) => (
                          <strong
                            className="font-bold text-gray-900"
                            {...props}
                          />
                        ),
                        // Emphasis/Italic
                        em: ({ node, ...props }) => (
                          <em className="italic" {...props} />
                        ),
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                    {/* eslint-enable react/no-unstable-nested-components, react/jsx-props-no-spreading, jsx-a11y/heading-has-content, jsx-a11y/anchor-has-content */}
                    {/* Streaming cursor indicator */}
                    {isStreaming && (
                      <span className="inline-block w-1.5 h-4 ml-0.5 bg-gray-600 animate-pulse" />
                    )}
                  </div>
                )}
              </>
            )}

            {/* Only show metadata if NOT thinking */}
            {!isThinking && (
              <>
                {/* Assistant Message Metadata */}
                {isAssistant && message.metadata && (
                  <div className="mt-3 pt-3 border-t border-gray-300">
                    {/* Sources */}
                    {message.metadata.sources &&
                      message.metadata.sources.length > 0 && (
                        <div className="text-xs text-gray-600 mb-1">
                          <span className="font-semibold">
                            {t('chat.sources')}:
                          </span>{' '}
                          {message.metadata.resultsCount} {t('chat.documents')}
                          {message.metadata.topScore && (
                            <span className="ml-2">
                              ({t('chat.relevance')}:{' '}
                              {(message.metadata.topScore * 100).toFixed(0)}%)
                            </span>
                          )}
                        </div>
                      )}

                    {/* Processing Time */}
                    {message.metadata.processingTime && (
                      <div className="flex items-center gap-1 text-xs text-gray-500">
                        <Clock className="w-3 h-3" />
                        <span>
                          {(message.metadata.processingTime / 1000).toFixed(2)}s
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Message Footer */}
          <div className="flex items-center gap-2 mt-1 px-1">
            {/* Timestamp */}
            <span className="text-xs text-gray-500">
              {formatTime(message.createdAt)}
            </span>

            {/* Copy Button */}
            <button
              onClick={handleCopy}
              className="text-gray-400 hover:text-gray-600 transition-colors"
              aria-label={t('chat.copyMessage')}
              title={t('chat.copyMessage')}
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-green-500" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>

            {/* Status Indicators */}
            {!isThinking && isOptimistic && (
              <span className="text-xs text-gray-400 italic">
                {t('chat.sending')}
              </span>
            )}
            {!isThinking && isStreaming && message.content && (
              <span className="text-xs text-gray-400 italic flex items-center gap-1">
                <span className="flex gap-0.5">
                  <span
                    className="w-1 h-1 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '0ms' }}
                  />
                  <span
                    className="w-1 h-1 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '150ms' }}
                  />
                  <span
                    className="w-1 h-1 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '300ms' }}
                  />
                </span>
                <span>Streaming...</span>
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

MessageBubbleComponent.propTypes = {
  message: PropTypes.shape({
    id: PropTypes.string.isRequired,
    role: PropTypes.oneOf(['user', 'assistant', 'system']).isRequired,
    content: PropTypes.string.isRequired,
    createdAt: PropTypes.string.isRequired,
    isOptimistic: PropTypes.bool,
    isStreaming: PropTypes.bool,
    isThinking: PropTypes.bool,
    metadata: PropTypes.shape({
      resultsCount: PropTypes.number,
      topScore: PropTypes.number,
      sources: PropTypes.arrayOf(
        PropTypes.shape({
          id: PropTypes.string,
          type: PropTypes.string,
          score: PropTypes.number,
        })
      ),
      processingTime: PropTypes.number,
    }),
  }).isRequired,
};

// Memoized export - only re-renders if message prop changes
export const MessageBubble = memo(MessageBubbleComponent);
