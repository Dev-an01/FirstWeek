import { useState, useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import { X, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '../ui/Button';
import { useChatStore } from '../../store/chatStore';
import { useUIStore } from '../../store/uiStore';
import { socketManager } from '../../services/socket';

/**
 * ExecutiveSelector Component
 *
 * Modal that displays executives in a horizontal carousel for selection
 *
 * Features:
 * - Draggable horizontal carousel of executive cards
 * - Loading state while fetching executives
 * - Executive selection with highlighted state
 * - Smooth animations and transitions
 * - Responsive design
 * - Keyboard navigation (ESC to close)
 * - Touch-friendly mobile experience
 * - Direct Zustand store access (no prop drilling)
 */
export function ExecutiveSelector({ isOpen, onClose }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  // Zustand stores - direct access, no props
  const {
    ragProfiles: executives,
    ragProfilesLoading: isLoading,
    currentConversation,
    setSelectedProfile,
    createConversation,
  } = useChatStore();

  const { showErrorToast, showSuccessToast } = useUIStore();

  // Log executives array when component renders
  useEffect(() => {
    if (isOpen && executives.length > 0) {
      console.log(
        '[ExecutiveSelector] Executives in order:',
        executives.map((e) => ({
          id: e.id,
          name: e.name,
          title: e.title,
        }))
      );
    }
  }, [isOpen, executives]);

  // Local state
  const [selectedExecutive, setSelectedExecutive] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [startX, setStartX] = useState(0);
  const [scrollLeft, setScrollLeft] = useState(0);

  // Refs
  const carouselRef = useRef(null);

  /**
   * Reset selection when modal opens
   */
  useEffect(() => {
    if (isOpen) {
      setSelectedExecutive(null);
    }
  }, [isOpen]);

  /**
   * Handle modal close on escape key
   */
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  /**
   * Prevent body scroll when modal is open
   */
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  /**
   * Mouse drag handlers for carousel
   */
  const handleMouseDown = (e) => {
    if (!carouselRef.current) return;
    setIsDragging(true);
    setStartX(e.pageX - carouselRef.current.offsetLeft);
    setScrollLeft(carouselRef.current.scrollLeft);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleMouseMove = (e) => {
    if (!isDragging || !carouselRef.current) return;
    e.preventDefault();
    const x = e.pageX - carouselRef.current.offsetLeft;
    const walk = (x - startX) * 2; // Scroll speed multiplier
    carouselRef.current.scrollLeft = scrollLeft - walk;
  };

  const handleMouseLeave = () => {
    setIsDragging(false);
  };

  /**
   * Touch handlers for mobile
   */
  const handleTouchStart = (e) => {
    if (!carouselRef.current) return;
    setIsDragging(true);
    setStartX(e.touches[0].pageX - carouselRef.current.offsetLeft);
    setScrollLeft(carouselRef.current.scrollLeft);
  };

  const handleTouchEnd = () => {
    setIsDragging(false);
  };

  const handleTouchMove = (e) => {
    if (!isDragging || !carouselRef.current) return;
    const x = e.touches[0].pageX - carouselRef.current.offsetLeft;
    const walk = (x - startX) * 2;
    carouselRef.current.scrollLeft = scrollLeft - walk;
  };

  /**
   * Scroll carousel with buttons
   */
  const scrollCarousel = (direction) => {
    if (!carouselRef.current) return;
    const scrollAmount = 300;
    const newScrollLeft =
      direction === 'left'
        ? carouselRef.current.scrollLeft - scrollAmount
        : carouselRef.current.scrollLeft + scrollAmount;

    carouselRef.current.scrollTo({
      left: newScrollLeft,
      behavior: 'smooth',
    });
  };

  /**
   * Handle executive card click
   */
  const handleExecutiveClick = (executive) => {
    console.log('[ExecutiveSelector] Card clicked:', {
      id: executive.id,
      name: executive.name,
      title: executive.title,
    });
    setSelectedExecutive(executive);
  };

  /**
   * Handle confirm selection and start chat
   * Handles executive selection internally using Zustand
   */
  const handleConfirmSelection = async () => {
    if (!selectedExecutive) return;

    try {
      console.log('[ExecutiveSelector] Executive selected:', {
        id: selectedExecutive.id,
        name: selectedExecutive.name,
        title: selectedExecutive.title,
      });

      // Close modal first
      onClose();

      // Store selected profile globally
      setSelectedProfile(selectedExecutive);

      // Create new conversation
      const displayName = selectedExecutive.name || selectedExecutive.title || selectedExecutive.id;
      const newConversation = await createConversation(
        t('chat.newChatWithExecutive', { name: displayName }) ||
          `Chat with ${displayName}`
      );

      // Store profile for this specific conversation
      useChatStore.setState((state) => ({
        conversationProfiles: {
          ...state.conversationProfiles,
          [newConversation.id]: selectedExecutive.id,
        },
      }));

      // Check if socket is connected
      const socketConnected = socketManager.getConnectionStatus();

      // Leave current room and join new conversation room
      if (socketConnected) {
        try {
          // Leave old conversation room if there was one
          if (currentConversation?.id) {
            await socketManager.leaveConversation(currentConversation.id);
            console.log(
              '[ExecutiveSelector] Left old conversation room:',
              currentConversation.id
            );
          }

          // Join the new conversation room
          await socketManager.joinConversation(newConversation.id);
          console.log(
            '[ExecutiveSelector] Joined new conversation room:',
            newConversation.id
          );
        } catch (error) {
          console.error(
            '[ExecutiveSelector] Failed to switch conversation rooms:',
            error
          );
          showErrorToast('Failed to connect to conversation');
        }
      }

      showSuccessToast(t('chat.conversationCreated'));
      navigate(`/chat/${newConversation.id}`);
    } catch (error) {
      showErrorToast(t('chat.errors.createConversationFailed'));
      console.error('Failed to create conversation:', error);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              {t(
                'chat.selectExecutive.title',
                'Select an Executive to Chat With'
              )}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {t(
                'chat.selectExecutive.subtitle',
                'Choose a project guide to start your conversation'
              )}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {isLoading ? (
            // Loading state
            <div className="flex flex-col items-center justify-center py-16">
              <div className="relative w-16 h-16 mb-4">
                <div className="absolute inset-0 border-4 border-primary border-opacity-20 rounded-full" />
                <div className="absolute inset-0 border-4 border-primary border-t-transparent rounded-full animate-spin" />
              </div>
              <p className="text-gray-600 text-lg animate-pulse">
                {t('chat.selectExecutive.loading', 'Thinking…')}
              </p>
            </div>
          ) : executives.length === 0 ? (
            // Empty state
            <div className="flex flex-col items-center justify-center py-16">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                <Sparkles className="w-8 h-8 text-gray-400" />
              </div>
              <p className="text-gray-600 text-lg">
                {t(
                  'chat.selectExecutive.noExecutives',
                  'No executives available'
                )}
              </p>
              <p className="text-gray-500 text-sm mt-2">
                {t(
                  'chat.selectExecutive.noExecutivesDesc',
                  'Please try again later'
                )}
              </p>
            </div>
          ) : (
            // Executives carousel
            <div>
              <p className="text-sm text-gray-600 mb-4">
                {t(
                  'chat.selectExecutive.instruction',
                  'Select one executive from the list below:'
                )}
              </p>

              {/* Carousel container */}
              <div className="relative">
                {/* Left scroll button */}
                <button
                  onClick={() => scrollCarousel('left')}
                  className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 bg-white rounded-full shadow-lg flex items-center justify-center hover:bg-gray-50 transition-colors"
                  aria-label="Scroll left"
                >
                  <ChevronLeft className="w-5 h-5 text-gray-700" />
                </button>

                {/* Right scroll button */}
                <button
                  onClick={() => scrollCarousel('right')}
                  className="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 bg-white rounded-full shadow-lg flex items-center justify-center hover:bg-gray-50 transition-colors"
                  aria-label="Scroll right"
                >
                  <ChevronRight className="w-5 h-5 text-gray-700" />
                </button>

                {/* Carousel */}
                <div
                  ref={carouselRef}
                  className={`flex gap-4 overflow-x-auto scrollbar-hide py-4 px-12 ${
                    isDragging ? 'cursor-grabbing' : 'cursor-grab'
                  }`}
                  onMouseDown={handleMouseDown}
                  onMouseUp={handleMouseUp}
                  onMouseMove={handleMouseMove}
                  onMouseLeave={handleMouseLeave}
                  onTouchStart={handleTouchStart}
                  onTouchEnd={handleTouchEnd}
                  onTouchMove={handleTouchMove}
                  style={{
                    scrollbarWidth: 'none',
                    msOverflowStyle: 'none',
                  }}
                >
                  {executives.map((executive) => (
                    <div
                      key={executive.id}
                      onClick={() => handleExecutiveClick(executive)}
                      className={`flex-shrink-0 w-64 bg-white rounded-xl border-2 transition-all cursor-pointer select-none ${
                        selectedExecutive?.id === executive.id
                          ? 'border-primary shadow-lg scale-105'
                          : 'border-gray-200 hover:border-gray-300 hover:shadow-md'
                      }`}
                    >
                      {/* Executive image */}
                      <div className="aspect-square bg-gradient-to-br from-primary to-primary-dark rounded-t-xl overflow-hidden flex items-center justify-center">
                        {executive.image ? (
                          <img
                            src={executive.image}
                            alt={executive.name || executive.id}
                            className="w-full h-full object-cover"
                            draggable="false"
                          />
                        ) : (
                          // Placeholder with initials
                          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-blue-400 to-indigo-600">
                            <span className="text-5xl font-bold text-white">
                              {(executive.name || executive.id || 'EX')
                                .split(' ')
                                .map((n) => n[0])
                                .join('')
                                .toUpperCase()
                                .slice(0, 2)}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Executive info */}
                      <div className="p-4">
                        <h3 className="font-semibold text-lg text-gray-900 mb-1">
                          {executive.name || executive.title || executive.id}
                        </h3>
                        {executive.description && (
                          <p className="text-sm text-gray-600 line-clamp-2">
                            {executive.description}
                          </p>
                        )}
                        {selectedExecutive?.id === executive.id && (
                          <div className="mt-2 flex items-center gap-1 text-primary text-sm font-medium">
                            <div className="w-2 h-2 bg-primary rounded-full" />
                            {t('chat.selectExecutive.selected', 'Selected')}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {!isLoading && executives.length > 0 && (
          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
            <Button onClick={onClose} variant="secondary" className="px-6">
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button
              onClick={handleConfirmSelection}
              variant="primary"
              disabled={!selectedExecutive}
              className="px-6 flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4" />
              {t('chat.selectExecutive.startChat', 'Start Chat')}
            </Button>
          </div>
        )}
      </div>

      <style>
        {`
          .scrollbar-hide::-webkit-scrollbar {
            display: none;
          }

          @keyframes fade-in {
            from {
              opacity: 0;
            }
            to {
              opacity: 1;
            }
          }

          @keyframes scale-in {
            from {
              opacity: 0;
              transform: scale(0.9);
            }
            to {
              opacity: 1;
              transform: scale(1);
            }
          }

          .animate-fade-in {
            animation: fade-in 0.2s ease-out;
          }

          .animate-scale-in {
            animation: scale-in 0.3s ease-out;
          }
        `}
      </style>
    </div>
  );
}

ExecutiveSelector.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};
