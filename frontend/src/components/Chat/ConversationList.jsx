import { useState, useCallback, useMemo } from 'react';
import { Plus, MessageSquare, Search, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '../ui/Button';
import { useChatStore } from '../../store/chatStore';
import { useUIStore } from '../../store/uiStore';
import { useDebounce } from '../../hooks/useDebounce';
import { ConversationItem } from './ConversationItem';

/**
 * ConversationList Component
 *
 * Sidebar displaying list of conversations
 *
 * Features:
 * - List of conversations with preview
 * - Create new conversation (via parent handler)
 * - Delete conversation
 * - Active conversation highlighting
 * - Search/filter conversations
 * - Load more pagination
 * - Empty state
 * - Direct Zustand store access (no prop drilling)
 */
export function ConversationList() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  // Zustand stores
  const {
    conversations,
    currentConversation,
    conversationsLoading,
    conversationsPagination,
    deleteConversation,
    loadMoreConversations,
  } = useChatStore();

  const { showSuccessToast, showErrorToast } = useUIStore();

  // Local UI state
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);

  // Debounce search query to avoid filtering on every keystroke
  const debouncedSearchQuery = useDebounce(searchQuery, 300);

  /**
   * Filter conversations by search query (memoized to avoid re-computation)
   */
  const filteredConversations = useMemo(() => {
    if (!debouncedSearchQuery) return conversations;

    const query = debouncedSearchQuery.toLowerCase();
    return conversations.filter((conv) =>
      conv.title.toLowerCase().includes(query)
    );
  }, [conversations, debouncedSearchQuery]);

  /**
   * Format timestamp for conversation (memoized to avoid re-computation)
   */
  const formatDate = useCallback(
    (dateString) => {
      const date = new Date(dateString);
      const now = new Date();
      const diffInHours = (now - date) / (1000 * 60 * 60);

      if (diffInHours < 24) {
        return date.toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
        });
      }
      if (diffInHours < 48) {
        return t('chat.yesterday');
      }
      if (diffInHours < 168) {
        return date.toLocaleDateString('en-US', { weekday: 'short' });
      }
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
    },
    [t]
  );

  /**
   * Handle conversation selection
   */
  const handleSelectConversation = useCallback(
    (conversation) => {
      navigate(`/chat/${conversation.id}`);
      // Close sidebar on mobile
      if (window.innerWidth < 768) {
        // Sidebar will auto-close via responsive design
      }
    },
    [navigate]
  );

  /**
   * Handle create conversation - navigate to chat page
   */
  const handleCreateConversation = useCallback(() => {
    navigate('/chat');
  }, [navigate]);

  /**
   * Handle delete with confirmation
   */
  const handleDeleteClick = useCallback((e, conversationId) => {
    e.stopPropagation();
    setDeleteConfirmId(conversationId);
  }, []);

  const confirmDelete = useCallback(
    async (e, conversationId) => {
      e.stopPropagation();
      try {
        await deleteConversation(conversationId);
        showSuccessToast(t('chat.conversationDeleted'));

        // If deleted conversation was current, navigate away
        if (conversationId === currentConversation?.id) {
          navigate('/chat');
        }
      } catch (error) {
        showErrorToast(t('chat.errors.deleteConversationFailed'));
        console.error('Failed to delete conversation:', error);
      }
      setDeleteConfirmId(null);
    },
    [
      deleteConversation,
      showSuccessToast,
      showErrorToast,
      t,
      currentConversation,
      navigate,
    ]
  );

  const cancelDelete = useCallback((e) => {
    e.stopPropagation();
    setDeleteConfirmId(null);
  }, []);

  return (
    <div className="w-80 border-r bg-gray-50 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b bg-white">
        <Button
          onClick={handleCreateConversation}
          className="w-full flex items-center justify-center gap-2"
          variant="primary"
        >
          <Plus className="w-5 h-5" />
          {t('chat.newChat')}
        </Button>

        {/* Search */}
        <div className="mt-3 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('chat.searchConversations')}
            className="w-full pl-10 pr-8 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:ring-opacity-50"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto">
        {conversationsLoading && conversations.length === 0 ? (
          // Loading skeleton
          <div className="p-2 space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="p-3 rounded-lg bg-white animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
                <div className="h-3 bg-gray-200 rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : filteredConversations.length === 0 ? (
          // Empty state
          <div className="flex flex-col items-center justify-center p-8 text-center">
            <MessageSquare className="w-12 h-12 text-gray-300 mb-3" />
            <p className="text-gray-500 text-sm">
              {searchQuery
                ? t('chat.noConversationsFound')
                : t('chat.noConversations')}
            </p>
            {!searchQuery && (
              <p className="text-gray-400 text-xs mt-1">
                {t('chat.createFirstConversation')}
              </p>
            )}
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {filteredConversations.map((conversation) => (
              <ConversationItem
                key={conversation.id}
                conversation={conversation}
                isActive={conversation.id === currentConversation?.id}
                isDeleting={deleteConfirmId === conversation.id}
                formatDate={formatDate}
                onSelect={handleSelectConversation}
                onDeleteClick={handleDeleteClick}
                onConfirmDelete={confirmDelete}
                onCancelDelete={cancelDelete}
              />
            ))}

            {/* Load More Button */}
            {conversationsPagination.hasMore && !conversationsLoading && (
              <div className="p-2">
                <Button
                  onClick={loadMoreConversations}
                  variant="outline"
                  className="w-full text-sm"
                >
                  {t('chat.loadMore')}
                </Button>
              </div>
            )}

            {/* Loading More Indicator */}
            {conversationsLoading && conversations.length > 0 && (
              <div className="flex justify-center p-4">
                <div className="animate-spin rounded-full h-6 w-6 border-2 border-primary border-t-transparent" />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
