import { useState } from 'react';
import { Plus, Trash2, MessageSquare, Search, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '../ui/Button';
import { useChatStore } from '../../store/chatStore';
import { useUIStore } from '../../store/uiStore';

/**
 * ChatSidebarContent Component
 *
 * Chat-specific sidebar content (New Chat, Search, Past Chats)
 * Designed to be used as children of the main Sidebar component
 */
export function ChatSidebarContent() {
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

  const { showSuccessToast, showErrorToast, closeSidebar } = useUIStore();

  // Local UI state
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);

  /**
   * Filter conversations by search query
   */
  const filteredConversations = conversations.filter((conv) =>
    conv.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  /**
   * Handle conversation selection
   */
  const handleSelectConversation = (conversation) => {
    navigate(`/chat/${conversation.id}`);
    // Close sidebar on mobile
    if (window.innerWidth < 768) {
      closeSidebar();
    }
  };

  /**
   * Handle create conversation - navigate to chat page
   */
  const handleCreateConversation = () => {
    navigate('/chat');
    if (window.innerWidth < 768) {
      closeSidebar();
    }
  };

  /**
   * Handle delete with confirmation
   */
  const handleDeleteClick = (e, conversationId) => {
    e.stopPropagation();
    setDeleteConfirmId(conversationId);
  };

  const confirmDelete = async (e, conversationId) => {
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
  };

  const cancelDelete = (e) => {
    e.stopPropagation();
    setDeleteConfirmId(null);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* New Chat Button */}
      <div className="flex-shrink-0 px-3 pb-3">
        <Button
          onClick={handleCreateConversation}
          className="w-full flex items-center justify-center gap-2"
          variant="primary"
        >
          <Plus className="w-5 h-5" />
          {t('chat.newChat')}
        </Button>
      </div>

      {/* Search */}
      <div className="flex-shrink-0 px-3 pb-3">
        <div className="relative">
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
      <div className="flex-1 overflow-y-auto px-3">
        {conversationsLoading && conversations.length === 0 ? (
          // Loading skeleton
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="p-3 rounded-lg bg-gray-100 animate-pulse">
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
          <div className="space-y-1">
            {filteredConversations.map((conversation) => {
              const isActive = conversation.id === currentConversation?.id;
              const isDeleting = deleteConfirmId === conversation.id;

              return (
                <div
                  key={conversation.id}
                  onClick={() =>
                    !isDeleting && handleSelectConversation(conversation)
                  }
                  className={`
                    group relative px-3 py-2.5 rounded-lg cursor-pointer transition-all
                    ${
                      isActive
                        ? 'bg-primary text-white'
                        : 'bg-gray-50 hover:bg-gray-100'
                    }
                    ${isDeleting ? 'ring-2 ring-red-400' : ''}
                  `}
                >
                  {/* Conversation Content */}
                  {!isDeleting ? (
                    <div className="flex items-center justify-between gap-2">
                      <h3
                        className={`font-medium text-sm truncate flex-1 pr-2 ${
                          isActive ? 'text-white' : 'text-gray-900'
                        }`}
                      >
                        {conversation.title}
                      </h3>

                      {/* Delete Button */}
                      <button
                        onClick={(e) => handleDeleteClick(e, conversation.id)}
                        className={`
                          flex-shrink-0 p-1.5 rounded-lg opacity-0 group-hover:opacity-100
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
                    </div>
                  ) : (
                    // Delete Confirmation
                    <div className="text-center py-2">
                      <p className="text-sm text-gray-700 mb-3">
                        {t('chat.deleteConfirm')}
                      </p>
                      <div className="flex gap-2 justify-center">
                        <button
                          onClick={(e) => confirmDelete(e, conversation.id)}
                          className="px-3 py-1 bg-red-500 text-white text-sm rounded-lg hover:bg-red-600 transition-colors"
                        >
                          {t('common.delete')}
                        </button>
                        <button
                          onClick={cancelDelete}
                          className="px-3 py-1 bg-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-400 transition-colors"
                        >
                          {t('common.cancel')}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Load More Button */}
            {conversationsPagination.hasMore && !conversationsLoading && (
              <div className="pt-2">
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
