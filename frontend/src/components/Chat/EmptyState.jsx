import PropTypes from 'prop-types';
import { MessageSquare, Sparkles, ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '../ui/Button';

/**
 * EmptyState Component
 *
 * Displayed when no conversation is selected or when starting fresh
 *
 * Features:
 * - Welcome message
 * - Suggested actions
 * - Create conversation button
 * - Quick prompts (optional)
 */
export function EmptyState({ onCreateConversation, showSuggestions }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const suggestedPrompts = [
    t('chat.prompts.vacationPolicy'),
    t('chat.prompts.benefits'),
    t('chat.prompts.companyInfo'),
    t('chat.prompts.hrQuestions'),
  ];

  return (
    <div className="flex-1 flex flex-col bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header with Back Button */}
      <div className="border-b bg-white px-4 py-3 flex items-center gap-2">
        <button
          onClick={() => navigate('/dashboard')}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-600 hover:text-primary"
          aria-label={t('common.back') || 'Back to Dashboard'}
          title="Back to Dashboard"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 text-center">
          <p className="text-gray-600 text-sm font-medium">
            {t('chat.newChatTitle')}
          </p>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-2xl">
          {/* Icon */}
          <div className="w-20 h-20 rounded-full bg-primary bg-opacity-10 flex items-center justify-center mx-auto mb-6">
            <MessageSquare className="w-10 h-10 text-primary" />
          </div>

          {/* Welcome Text */}
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            {t('chat.welcome')}
          </h1>
          <p className="text-gray-600 text-lg mb-8">
            {t('chat.welcomeSubtitle')}
          </p>

          {/* Create Conversation Button */}
          <Button
            onClick={onCreateConversation}
            variant="primary"
            className="mx-auto px-8 py-3 text-lg flex items-center gap-2"
          >
            <Sparkles className="w-5 h-5" />
            {t('chat.startNewChat')}
          </Button>

          {/* Suggested Prompts */}
          {showSuggestions && (
            <div className="mt-12">
              <p className="text-sm text-gray-500 mb-4">
                {t('chat.tryAsking')}:
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {suggestedPrompts.map((prompt, index) => (
                  <button
                    key={index}
                    onClick={onCreateConversation}
                    className="p-4 bg-white rounded-xl border-2 border-gray-200 hover:border-primary hover:shadow-md transition-all text-left group"
                  >
                    <p className="text-sm text-gray-700 group-hover:text-primary transition-colors">
                      "{prompt}"
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Features List */}
          <div className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-6 text-left">
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                <svg
                  className="w-5 h-5 text-blue-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm mb-1">
                  {t('chat.features.instant')}
                </h3>
                <p className="text-xs text-gray-500">
                  {t('chat.features.instantDesc')}
                </p>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                <svg
                  className="w-5 h-5 text-green-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                  />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm mb-1">
                  {t('chat.features.secure')}
                </h3>
                <p className="text-xs text-gray-500">
                  {t('chat.features.secureDesc')}
                </p>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                <svg
                  className="w-5 h-5 text-purple-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                  />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm mb-1">
                  {t('chat.features.knowledge')}
                </h3>
                <p className="text-xs text-gray-500">
                  {t('chat.features.knowledgeDesc')}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

EmptyState.propTypes = {
  onCreateConversation: PropTypes.func.isRequired,
  showSuggestions: PropTypes.bool,
};

EmptyState.defaultProps = {
  showSuggestions: true,
};
