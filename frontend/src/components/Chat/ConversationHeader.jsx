import { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { Edit2, Check, X, Trash2, Menu, ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '../../store/chatStore';
import { useUIStore } from '../../store/uiStore';

/**
 * ConversationHeader Component
 *
 * Header bar for current conversation
 *
 * Features:
 * - Display conversation title
 * - Inline title editing
 * - Delete conversation button
 * - Mobile menu toggle
 * - Conversation info (message count)
 * - Direct Zustand store access (no prop drilling)
 */
export function ConversationHeader({
  onToggleSidebar = null,
  showMenuButton = false,
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [editedTitle, setEditedTitle] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Zustand stores - direct access, no props
  const {
    currentConversation: conversation,
    updateConversation,
    deleteConversation,
    ragProfiles,
    selectedProfile,
    conversationProfiles,
  } = useChatStore();

  const { showSuccessToast, showErrorToast } = useUIStore();

  // Calculate executive name from conversation profile or selected profile
  const executiveName = (() => {
    if (!conversation) return null;
    const profileId =
      conversationProfiles[conversation.id] || selectedProfile?.id;
    const profile = ragProfiles.find((p) => p.id === profileId);
    return profile?.name || null;
  })();

  /**
   * Cancel editing
   */
  const cancelEdit = useCallback(() => {
    setIsEditing(false);
    setEditedTitle('');
  }, []);

  /**
   * Start editing title
   */
  const startEdit = useCallback(() => {
    setEditedTitle(conversation.title);
    setIsEditing(true);
  }, [conversation]);

  /**
   * Save edited title
   */
  const saveEdit = useCallback(async () => {
    const trimmedTitle = editedTitle.trim();

    if (!trimmedTitle || trimmedTitle === conversation.title) {
      cancelEdit();
      return;
    }

    setIsSaving(true);
    try {
      await updateConversation(conversation.id, trimmedTitle);
      showSuccessToast(t('chat.titleUpdated'));
      setIsEditing(false);
    } catch (error) {
      showErrorToast(t('chat.errors.updateTitleFailed'));
      console.error('Failed to update title:', error);
    } finally {
      setIsSaving(false);
    }
  }, [
    editedTitle,
    conversation,
    updateConversation,
    showSuccessToast,
    showErrorToast,
    t,
    cancelEdit,
  ]);

  /**
   * Handle Enter key to save
   */
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        saveEdit();
      } else if (e.key === 'Escape') {
        cancelEdit();
      }
    },
    [saveEdit, cancelEdit]
  );

  /**
   * Handle delete conversation
   */
  const handleDelete = useCallback(async () => {
    if (!conversation) return;

    try {
      await deleteConversation(conversation.id);
      showSuccessToast(t('chat.conversationDeleted'));
      // Navigate away from deleted conversation
      navigate('/chat');
    } catch (error) {
      showErrorToast(t('chat.errors.deleteConversationFailed'));
      console.error('Failed to delete conversation:', error);
    }
  }, [
    conversation,
    deleteConversation,
    showSuccessToast,
    showErrorToast,
    t,
    navigate,
  ]);

  if (!conversation) {
    return (
      <div className="border-b bg-white px-4 py-3 flex items-center justify-between gap-2">
        {/* Back to Dashboard Button */}
        <button
          onClick={() => navigate('/dashboard')}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-600 hover:text-primary"
          aria-label={t('common.back') || 'Back to Dashboard'}
          title="Back to Dashboard"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>

        {showMenuButton && (
          <button
            onClick={onToggleSidebar}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors md:hidden"
            aria-label={t('common.menu')}
          >
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
        )}
        <div className="flex-1 text-center">
          <p className="text-gray-400 text-sm">
            {t('chat.noConversationSelected')}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="border-b bg-white px-4 py-3 flex items-center justify-between gap-2">
      {/* Back to Dashboard Button */}
      <button
        onClick={() => navigate('/dashboard')}
        className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-600 hover:text-primary flex-shrink-0"
        aria-label={t('common.back') || 'Back to Dashboard'}
        title="Back to Dashboard"
      >
        <ArrowLeft className="w-5 h-5" />
      </button>

      {/* Mobile Menu Button */}
      {showMenuButton && (
        <button
          onClick={onToggleSidebar}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors md:hidden flex-shrink-0"
          aria-label={t('common.menu')}
        >
          <Menu className="w-5 h-5 text-gray-600" />
        </button>
      )}

      {/* Title Section */}
      <div className="flex-1 flex items-center gap-2 min-w-0">
        {isEditing ? (
          // Edit Mode
          <>
            <input
              type="text"
              value={editedTitle}
              onChange={(e) => setEditedTitle(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={saveEdit}
              // eslint-disable-next-line jsx-a11y/no-autofocus
              autoFocus
              maxLength={100}
              disabled={isSaving}
              className="flex-1 px-2 py-1 text-lg font-semibold border-2 border-primary rounded-lg focus:outline-none"
            />
            <button
              onClick={saveEdit}
              disabled={isSaving}
              className="p-1.5 hover:bg-green-100 text-green-600 rounded-lg transition-colors"
              aria-label={t('common.save')}
            >
              <Check className="w-5 h-5" />
            </button>
            <button
              onClick={cancelEdit}
              disabled={isSaving}
              className="p-1.5 hover:bg-red-100 text-red-600 rounded-lg transition-colors"
              aria-label={t('common.cancel')}
            >
              <X className="w-5 h-5" />
            </button>
          </>
        ) : (
          // View Mode
          <>
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-semibold text-gray-900 truncate">
                {conversation.title}
              </h1>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                {executiveName && (
                  <span className="font-medium text-blue-600">
                    {executiveName}
                  </span>
                )}
                {conversation.messageCount > 0 && (
                  <>
                    {executiveName && <span>•</span>}
                    <span>
                      {conversation.messageCount}{' '}
                      {conversation.messageCount === 1
                        ? t('chat.message')
                        : t('chat.messages')}
                    </span>
                  </>
                )}
              </div>
            </div>
            <button
              onClick={startEdit}
              className="p-1.5 hover:bg-gray-100 text-gray-600 rounded-lg transition-colors"
              aria-label={t('chat.editTitle')}
              title={t('chat.editTitle')}
            >
              <Edit2 className="w-4 h-4" />
            </button>
          </>
        )}
      </div>

      {/* Delete Button */}
      {!isEditing && (
        <button
          onClick={handleDelete}
          className="p-1.5 hover:bg-red-50 text-gray-600 hover:text-red-600 rounded-lg transition-colors"
          aria-label={t('chat.deleteConversation')}
          title={t('chat.deleteConversation')}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

ConversationHeader.propTypes = {
  onToggleSidebar: PropTypes.func,
  showMenuButton: PropTypes.bool,
};
