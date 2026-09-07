import { memo } from 'react';
import PropTypes from 'prop-types';
import { Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

/**
 * ConversationItem Component
 *
 * Individual conversation item in the sidebar list
 *
 * Features:
 * - Active state highlighting
 * - Delete confirmation UI
 * - Hover effects
 * - Message count display
 * - Last message preview
 *
 * Memoized to prevent unnecessary re-renders when conversation data hasn't changed
 */
function ConversationItemComponent({
  conversation,
  isActive,
  isDeleting,
  formatDate,
  onSelect,
  onDeleteClick,
  onConfirmDelete,
  onCancelDelete,
}) {
  const { t } = useTranslation();

  return (
    <div
      onClick={() => !isDeleting && onSelect(conversation)}
      className={`
        group relative p-3 rounded-lg cursor-pointer transition-all
        ${isActive ? 'bg-primary text-white' : 'bg-white hover:bg-gray-100'}
        ${isDeleting ? 'ring-2 ring-red-400' : ''}
      `}
    >
      {/* Conversation Content */}
      {!isDeleting ? (
        <>
          <div className="flex items-start justify-between gap-2">
            <h3
              className={`font-medium text-sm truncate ${
                isActive ? 'text-white' : 'text-gray-900'
              }`}
            >
              {conversation.title}
            </h3>
            <span
              className={`text-xs flex-shrink-0 ${
                isActive ? 'text-white/80' : 'text-gray-400'
              }`}
            >
              {formatDate(conversation.lastMessageAt || conversation.createdAt)}
            </span>
          </div>

          {conversation.lastMessagePreview && (
            <p
              className={`text-xs mt-1 truncate ${
                isActive ? 'text-white/80' : 'text-gray-500'
              }`}
            >
              {conversation.lastMessagePreview}
            </p>
          )}

          {conversation.messageCount > 0 && (
            <div
              className={`text-xs mt-1 ${
                isActive ? 'text-white/70' : 'text-gray-400'
              }`}
            >
              {conversation.messageCount}{' '}
              {conversation.messageCount === 1
                ? t('chat.message')
                : t('chat.messages')}
            </div>
          )}

          {/* Delete Button */}
          <button
            onClick={(e) => onDeleteClick(e, conversation.id)}
            className={`
              absolute top-2 right-2 p-1.5 rounded-lg opacity-0 group-hover:opacity-100
              transition-opacity
              ${
                isActive
                  ? 'hover:bg-white/20 text-white'
                  : 'hover:bg-gray-200 text-gray-400 hover:text-red-500'
              }
            `}
            aria-label={t('chat.deleteConversation')}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </>
      ) : (
        // Delete Confirmation
        <div className="text-center py-2">
          <p className="text-sm text-gray-700 mb-3">
            {t('chat.deleteConfirm')}
          </p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={(e) => onConfirmDelete(e, conversation.id)}
              className="px-3 py-1 bg-red-500 text-white text-sm rounded-lg hover:bg-red-600 transition-colors"
            >
              {t('common.delete')}
            </button>
            <button
              onClick={onCancelDelete}
              className="px-3 py-1 bg-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-400 transition-colors"
            >
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

ConversationItemComponent.propTypes = {
  conversation: PropTypes.shape({
    id: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    lastMessageAt: PropTypes.string,
    createdAt: PropTypes.string.isRequired,
    lastMessagePreview: PropTypes.string,
    messageCount: PropTypes.number,
  }).isRequired,
  isActive: PropTypes.bool.isRequired,
  isDeleting: PropTypes.bool.isRequired,
  formatDate: PropTypes.func.isRequired,
  onSelect: PropTypes.func.isRequired,
  onDeleteClick: PropTypes.func.isRequired,
  onConfirmDelete: PropTypes.func.isRequired,
  onCancelDelete: PropTypes.func.isRequired,
};

// Memoized export - only re-renders if props change
export const ConversationItem = memo(ConversationItemComponent);
